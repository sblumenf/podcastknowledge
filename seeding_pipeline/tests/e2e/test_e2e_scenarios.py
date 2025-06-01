"""End-to-end test scenarios for the podcast knowledge graph pipeline.

These tests validate complete user workflows from start to finish.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch
import json
import time

from neo4j import GraphDatabase
import pytest

from src.api.v1 import seed_podcast, seed_podcasts, VTTKnowledgeExtractor
from src.core.config import Config
from src.core.exceptions import PodcastKGError
class TestE2EScenarios:
    """End-to-end test scenarios."""
    
    @pytest.fixture
    def test_config(self):
        """Test configuration for E2E tests."""
        config = Config()
        config.neo4j_uri = 'bolt://localhost:7688'
        config.neo4j_user = 'neo4j'
        config.neo4j_password = 'testpassword'
        config.checkpoint_enabled = True
        config.checkpoint_dir = 'test_checkpoints'
        return config
    
    @pytest.fixture
    def neo4j_driver(self, test_config):
        """Neo4j driver for verification."""
        driver = GraphDatabase.driver(
            test_config.neo4j_uri,
            auth=(test_config.neo4j_user, test_config.neo4j_password)
        )
        yield driver
        driver.close()
    
    @pytest.fixture(autouse=True)
    def clean_database(self, neo4j_driver):
        """Clean database before each test."""
        with neo4j_driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        yield
        # Clean after test too
        with neo4j_driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
    
    @pytest.mark.e2e
    def test_scenario_new_user_first_podcast(self, test_config, neo4j_driver):
        """Scenario: New user processes their first podcast.
        
        Steps:
        1. User provides RSS feed URL
        2. System processes 5 episodes
        3. User can query the knowledge graph
        """
        # Step 1: User provides podcast
        podcast = {
            'name': 'My First Podcast',
            'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
            'category': 'Technology'
        }
        
        # Step 2: Process episodes
        result = seed_podcast(
            podcast,
            max_episodes=5,
            config=test_config
        )
        
        # Verify processing succeeded
        assert result['podcasts_processed'] == 1
        assert result['episodes_processed'] > 0
        assert result['episodes_failed'] == 0
        
        # Step 3: Verify knowledge graph is queryable
        with neo4j_driver.session() as session:
            # Check podcast exists
            podcast_result = session.run(
                "MATCH (p:Podcast {name: $name}) RETURN p",
                name=podcast['name']
            ).single()
            assert podcast_result is not None
            
            # Check episodes exist
            episodes = session.run(
                """
                MATCH (p:Podcast {name: $name})-[:HAS_EPISODE]->(e:Episode)
                RETURN count(e) as episode_count
                """,
                name=podcast['name']
            ).single()
            assert episodes['episode_count'] == result['episodes_processed']
            
            # Check insights were extracted
            insights = session.run(
                """
                MATCH (p:Podcast {name: $name})-[:HAS_EPISODE]->(e:Episode)
                      -[:HAS_SEGMENT]->(s:Segment)-[:HAS_INSIGHT]->(i:Insight)
                RETURN count(DISTINCT i) as insight_count
                """,
                name=podcast['name']
            ).single()
            assert insights['insight_count'] > 0
    
    @pytest.mark.e2e
    def test_scenario_batch_import_multiple_podcasts(self, test_config, neo4j_driver):
        """Scenario: User imports multiple podcasts at once.
        
        Steps:
        1. User provides list of podcast feeds
        2. System processes them concurrently
        3. All podcasts are in the graph with relationships
        """
        # Step 1: Multiple podcasts
        podcasts = [
            {
                'name': 'Tech Podcast 1',
                'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
                'category': 'Technology'
            },
            {
                'name': 'Tech Podcast 2', 
                'rss_url': 'https://lexfridman.com/feed/podcast/',
                'category': 'Technology'
            },
            {
                'name': 'Science Podcast',
                'rss_url': 'https://feeds.megaphone.fm/sciencevs',
                'category': 'Science'
            }
        ]
        
        # Step 2: Process all podcasts
        result = seed_podcasts(
            podcasts,
            max_episodes_each=2,
            config=test_config
        )
        
        # Verify all processed
        assert result['podcasts_processed'] == 3
        assert result['episodes_processed'] > 0
        
        # Step 3: Verify graph structure
        with neo4j_driver.session() as session:
            # Check all podcasts exist
            podcast_count = session.run(
                "MATCH (p:Podcast) RETURN count(p) as count"
            ).single()
            assert podcast_count['count'] == 3
            
            # Check cross-podcast relationships (shared topics/entities)
            shared_topics = session.run(
                """
                MATCH (p1:Podcast)-[:HAS_EPISODE]->()-[:HAS_SEGMENT]->()
                      -[:MENTIONS_TOPIC]->(t:Topic)<-[:MENTIONS_TOPIC]-()
                      <-[:HAS_SEGMENT]-()<-[:HAS_EPISODE]-(p2:Podcast)
                WHERE p1 <> p2
                RETURN count(DISTINCT t) as shared_topic_count
                """
            ).single()
            # May or may not have shared topics, but query should work
            assert shared_topics is not None
    
    @pytest.mark.e2e
    def test_scenario_interrupted_processing_recovery(self, test_config, neo4j_driver, tmp_path):
        """Scenario: Processing is interrupted and user resumes.
        
        Steps:
        1. Start processing a podcast
        2. Interrupt after 2 episodes
        3. Resume processing
        4. Verify no duplicate data
        """
        # Use temp checkpoint dir
        test_config.checkpoint_dir = str(tmp_path)
        
        podcast = {
            'name': 'Interrupted Podcast',
            'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
            'category': 'Test'
        }
        
        # Step 1 & 2: Process first batch
        pipeline1 = VTTKnowledgeExtractor(test_config)
        try:
            result1 = pipeline1.seed_podcast(
                podcast,
                max_episodes=2
            )
            episodes_first = result1['episodes_processed']
            assert episodes_first == 2
        finally:
            pipeline1.cleanup()
        
        # Verify checkpoint exists
        checkpoint_files = list(tmp_path.glob('*.json'))
        assert len(checkpoint_files) > 0
        
        # Get initial state
        with neo4j_driver.session() as session:
            initial_episodes = session.run(
                """
                MATCH (p:Podcast {name: $name})-[:HAS_EPISODE]->(e:Episode)
                RETURN collect(e.title) as titles
                """,
                name=podcast['name']
            ).single()
            initial_titles = set(initial_episodes['titles'])
        
        # Step 3: Resume processing
        pipeline2 = VTTKnowledgeExtractor(test_config)
        try:
            result2 = pipeline2.seed_podcast(
                podcast,
                max_episodes=5  # Try to process more
            )
            total_episodes = result2['episodes_processed']
            assert total_episodes > episodes_first
        finally:
            pipeline2.cleanup()
        
        # Step 4: Verify no duplicates
        with neo4j_driver.session() as session:
            final_episodes = session.run(
                """
                MATCH (p:Podcast {name: $name})-[:HAS_EPISODE]->(e:Episode)
                RETURN e.title as title
                """,
                name=podcast['name']
            )
            
            titles = [record['title'] for record in final_episodes]
            # Check no duplicate titles
            assert len(titles) == len(set(titles))
            
            # Check initial episodes still exist
            for title in initial_titles:
                assert title in titles
    
    @pytest.mark.e2e
    def test_scenario_error_handling_partial_success(self, test_config, neo4j_driver):
        """Scenario: Some episodes fail but others succeed.
        
        Steps:
        1. Process podcast with some problematic episodes
        2. Verify partial success
        3. Check error reporting
        4. Verify good episodes are in graph
        """
        # Mock some episodes to fail
        with patch('src.processing.extraction.KnowledgeExtractor.extract_insights') as mock_extract:
            # Make every 3rd episode fail
            call_count = 0
            
            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count % 3 == 0:
                    raise Exception("Simulated extraction failure")
                # Return minimal valid result
                return {
                    'insights': [{'text': 'Test insight', 'confidence': 0.8}],
                    'entities': [],
                    'quotes': []
                }
            
            mock_extract.side_effect = side_effect
            
            podcast = {
                'name': 'Partially Failing Podcast',
                'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
                'category': 'Test'
            }
            
            # Process with some failures expected
            result = seed_podcast(
                podcast,
                max_episodes=6,
                config=test_config
            )
        
        # Verify partial success
        assert result['podcasts_processed'] == 1
        assert result['episodes_processed'] > 0
        assert result['episodes_failed'] > 0
        assert result['episodes_processed'] + result['episodes_failed'] <= 6
        
        # Verify good episodes are in graph
        with neo4j_driver.session() as session:
            episodes = session.run(
                """
                MATCH (p:Podcast {name: $name})-[:HAS_EPISODE]->(e:Episode)
                RETURN count(e) as count
                """,
                name=podcast['name']
            ).single()
            assert episodes['count'] == result['episodes_processed']
    
    @pytest.mark.e2e
    def test_scenario_large_podcast_memory_efficiency(self, test_config, neo4j_driver):
        """Scenario: Process large podcast without memory issues.
        
        Steps:
        1. Process podcast with many episodes
        2. Monitor memory usage
        3. Verify no memory leaks
        4. Check all data is accessible
        """
        import psutil
        import gc
        
        podcast = {
            'name': 'Large Podcast Test',
            'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
            'category': 'Test'
        }
        
        # Record initial memory
        gc.collect()
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        # Process many episodes
        result = seed_podcast(
            podcast,
            max_episodes=20,
            config=test_config
        )
        
        # Force garbage collection
        gc.collect()
        final_memory = process.memory_info().rss / (1024 * 1024)
        
        # Check memory growth is reasonable (< 500MB for 20 episodes)
        memory_growth = final_memory - initial_memory
        assert memory_growth < 500, f"Excessive memory growth: {memory_growth:.1f} MB"
        
        # Verify all episodes processed
        assert result['episodes_processed'] > 10  # At least half should succeed
        
        # Verify data is accessible
        with neo4j_driver.session() as session:
            # Can query large result sets
            segments = session.run(
                """
                MATCH (s:Segment)
                RETURN count(s) as count
                """
            ).single()
            assert segments['count'] > 50  # Should have many segments
    
    @pytest.mark.e2e
    def test_scenario_concurrent_users(self, test_config, neo4j_driver):
        """Scenario: Multiple users processing podcasts simultaneously.
        
        Steps:
        1. Simulate multiple concurrent users
        2. Each processes different podcasts
        3. Verify no data corruption
        4. Check all podcasts are separate
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # Different podcasts for each "user"
        user_podcasts = [
            {
                'user_id': 'user1',
                'podcast': {
                    'name': 'User 1 Podcast',
                    'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
                    'category': 'Tech'
                }
            },
            {
                'user_id': 'user2',
                'podcast': {
                    'name': 'User 2 Podcast',
                    'rss_url': 'https://lexfridman.com/feed/podcast/',
                    'category': 'Science'
                }
            },
            {
                'user_id': 'user3',
                'podcast': {
                    'name': 'User 3 Podcast',
                    'rss_url': 'https://feeds.megaphone.fm/sciencevs',
                    'category': 'Education'
                }
            }
        ]
        
        def process_user_podcast(user_data: Dict[str, Any]) -> Dict[str, Any]:
            """Simulate a user processing their podcast."""
            try:
                result = seed_podcast(
                    user_data['podcast'],
                    max_episodes=3,
                    config=test_config
                )
                return {
                    'user_id': user_data['user_id'],
                    'success': True,
                    'result': result
                }
            except Exception as e:
                return {
                    'user_id': user_data['user_id'],
                    'success': False,
                    'error': str(e)
                }
        
        # Process concurrently
        results = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(process_user_podcast, user_data): user_data
                for user_data in user_podcasts
            }
            
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
        
        # Verify all succeeded
        assert all(r['success'] for r in results)
        assert len(results) == 3
        
        # Verify data integrity
        with neo4j_driver.session() as session:
            # Each podcast should be separate
            for user_data in user_podcasts:
                podcast_name = user_data['podcast']['name']
                
                # Check podcast exists
                podcast = session.run(
                    "MATCH (p:Podcast {name: $name}) RETURN p",
                    name=podcast_name
                ).single()
                assert podcast is not None
                
                # Check has episodes
                episodes = session.run(
                    """
                    MATCH (p:Podcast {name: $name})-[:HAS_EPISODE]->(e:Episode)
                    RETURN count(e) as count
                    """,
                    name=podcast_name
                ).single()
                assert episodes['count'] > 0
    
    @pytest.mark.e2e
    def test_scenario_api_migration(self, test_config, neo4j_driver):
        """Scenario: User migrates from old API to new versioned API.
        
        Steps:
        1. Use the versioned API
        2. Check version compatibility
        3. Process podcast with v1 guarantees
        4. Verify response schema
        """
        from src.api.v1 import (
            seed_podcast as v1_seed_podcast,
            get_api_version,
            check_api_compatibility
        )
        
        # Step 1: Check API version
        api_version = get_api_version()
        assert api_version.startswith('1.')
        
        # Step 2: Check compatibility
        assert check_api_compatibility('1.0')
        assert not check_api_compatibility('2.0')  # Future version
        
        # Step 3: Use v1 API
        podcast = {
            'name': 'API v1 Test',
            'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
            'category': 'Test'
        }
        
        result = v1_seed_podcast(
            podcast,
            max_episodes=2,
            config=test_config,
            # Future parameter that v1 should ignore
            future_param='ignored'
        )
        
        # Step 4: Verify v1 response schema
        required_fields = [
            'start_time',
            'end_time',
            'podcasts_processed',
            'episodes_processed',
            'episodes_failed',
            'processing_time_seconds',
            'api_version'
        ]
        
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"
        
        assert result['api_version'] == '1.0'
    
    @pytest.mark.e2e
    @pytest.mark.slow
    def test_scenario_real_world_podcast(self, test_config, neo4j_driver):
        """Scenario: Process a real podcast end-to-end.
        
        This test actually downloads and processes a real podcast episode.
        Mark as slow since it requires network access.
        """
        # Use a small, reliable podcast
        podcast = {
            'name': 'NASA Cast Audio',
            'rss_url': 'https://www.nasa.gov/rss/dyn/NASACast_vodcast.rss',
            'category': 'Science'
        }
        
        # Process one real episode
        start_time = time.time()
        
        result = seed_podcast(
            podcast,
            max_episodes=1,
            config=test_config
        )
        
        processing_time = time.time() - start_time
        
        # Should complete within reasonable time (5 minutes)
        assert processing_time < 300, f"Processing took too long: {processing_time:.1f}s"
        
        # Verify real data was processed
        assert result['podcasts_processed'] == 1
        
        if result['episodes_processed'] > 0:
            # If episode was processed, verify graph
            with neo4j_driver.session() as session:
                # Should have real content
                insights = session.run(
                    """
                    MATCH (i:Insight)
                    RETURN i.text as text
                    LIMIT 5
                    """
                )
                
                insight_texts = [r['text'] for r in insights]
                assert len(insight_texts) > 0
                
                # Insights should have reasonable length
                for text in insight_texts:
                    assert len(text) > 10
                    assert len(text) < 1000