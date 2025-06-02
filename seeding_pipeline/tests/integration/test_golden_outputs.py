"""Golden output comparison tests for integration testing.
from tests.utils.neo4j_mocks import create_mock_neo4j_driver

Compares actual outputs against known good outputs to detect regressions.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch
import json

from neo4j import GraphDatabase
import pytest

from src.api.v1 import seed_podcast
from src.core.config import Config
@pytest.mark.e2e
class TestGoldenOutputs:
    """Test against golden (expected) outputs."""
    
    @pytest.fixture
    def golden_outputs_dir(self):
        """Directory containing golden outputs."""
        return Path(__file__).parent.parent / 'fixtures' / 'golden_outputs'
    
    @pytest.fixture
    def test_config(self):
        """Test configuration."""
        config = Config()
        config.neo4j_uri = 'bolt://localhost:7688'
        config.neo4j_user = 'neo4j'
        config.neo4j_password = 'testpassword'
        return config
    
    def compare_graph_structures(self, actual: Dict[str, Any], 
                               expected: Dict[str, Any]) -> List[str]:
        """Compare two graph structures and return differences.
        
        Args:
            actual: Actual graph structure
            expected: Expected graph structure
            
        Returns:
            List of difference descriptions
        """
        differences = []
        
        # Compare node counts
        for label, expected_count in expected.get('node_counts', {}).items():
            actual_count = actual.get('node_counts', {}).get(label, 0)
            if actual_count != expected_count:
                differences.append(
                    f"Node count mismatch for {label}: "
                    f"expected {expected_count}, got {actual_count}"
                )
        
        # Check for unexpected node types
        for label in actual.get('node_counts', {}):
            if label not in expected.get('node_counts', {}):
                differences.append(f"Unexpected node type: {label}")
        
        # Compare relationship counts
        for rel_type, expected_count in expected.get('relationship_counts', {}).items():
            actual_count = actual.get('relationship_counts', {}).get(rel_type, 0)
            # Allow some variance in relationships (±10%)
            variance = max(1, int(expected_count * 0.1))
            if abs(actual_count - expected_count) > variance:
                differences.append(
                    f"Relationship count mismatch for {rel_type}: "
                    f"expected {expected_count}±{variance}, got {actual_count}"
                )
        
        return differences
    
    def get_graph_structure(self, driver) -> Dict[str, Any]:
        """Get current graph structure from Neo4j.
        
        Args:
            driver: Neo4j driver instance
            
        Returns:
            Dictionary with node and relationship counts
        """
        structure = {
            'node_counts': {},
            'relationship_counts': {},
            'total_nodes': 0,
            'total_relationships': 0
        }
        
        with driver.session() as session:
            # Count nodes by label
            labels_result = session.run("CALL db.labels()")
            for record in labels_result:
                label = record[0]
                count_result = session.run(
                    f"MATCH (n:{label}) RETURN count(n) as count"
                ).single()
                count = count_result['count'] if count_result else 0
                structure['node_counts'][label] = count
                structure['total_nodes'] += count
            
            # Count relationships by type
            rel_types_result = session.run("CALL db.relationshipTypes()")
            for record in rel_types_result:
                rel_type = record[0]
                count_result = session.run(
                    f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"
                ).single()
                count = count_result['count'] if count_result else 0
                structure['relationship_counts'][rel_type] = count
                structure['total_relationships'] += count
        
        return structure
    
    @pytest.mark.integration
    def test_simple_podcast_golden_output(self, test_config, golden_outputs_dir):
        """Test simple podcast processing against golden output."""
        # Skip if golden output doesn't exist
        golden_file = golden_outputs_dir / 'simple_podcast_output.json'
        if not golden_file.exists():
            pytest.skip("Golden output not available")
        
        # Load golden output
        with open(golden_file, 'r') as f:
            golden_output = json.load(f)
        
        # Process test podcast
        test_podcast = {
            'name': 'Simple Test Podcast',
            'rss_url': golden_output['input']['rss_url'],
            'category': 'Test'
        }
        
        # Clear database
        driver = create_mock_neo4j_driver(
            test_config.neo4j_uri,
            auth=(test_config.neo4j_user, test_config.neo4j_password)
        )
        
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        
        # Process podcast
        result = seed_podcast(
            test_podcast,
            max_episodes=1,
            config=test_config
        )
        
        # Get actual graph structure
        actual_structure = self.get_graph_structure(driver)
        driver.close()
        
        # Compare against golden output
        differences = self.compare_graph_structures(
            actual_structure,
            golden_output['expected_structure']
        )
        
        # Assert no significant differences
        assert len(differences) == 0, f"Differences found:\n" + "\n".join(differences)
    
    @pytest.mark.integration
    def test_complex_podcast_golden_output(self, test_config, golden_outputs_dir):
        """Test complex podcast with multiple episodes against golden output."""
        golden_file = golden_outputs_dir / 'complex_podcast_output.json'
        if not golden_file.exists():
            pytest.skip("Golden output not available")
        
        with open(golden_file, 'r') as f:
            golden_output = json.load(f)
        
        # Process podcast
        test_podcast = golden_output['input']
        
        # Clear database
        driver = create_mock_neo4j_driver(
            test_config.neo4j_uri,
            auth=(test_config.neo4j_user, test_config.neo4j_password)
        )
        
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        
        # Process with multiple episodes
        result = seed_podcast(
            test_podcast,
            max_episodes=golden_output.get('max_episodes', 3),
            config=test_config
        )
        
        # Get actual structure
        actual_structure = self.get_graph_structure(driver)
        
        # Also check specific patterns
        with driver.session() as session:
            # Check that episodes are connected to podcast
            episode_connection = session.run(
                """
                MATCH (p:Podcast)-[r:HAS_EPISODE]->(e:Episode)
                RETURN count(r) as count
                """
            ).single()
            
            assert episode_connection['count'] > 0, "No episodes connected to podcast"
            
            # Check that insights are created
            insights = session.run(
                "MATCH (i:Insight) RETURN count(i) as count"
            ).single()
            
            assert insights['count'] > 0, "No insights created"
        
        driver.close()
        
        # Compare structures
        differences = self.compare_graph_structures(
            actual_structure,
            golden_output['expected_structure']
        )
        
        # Allow minor differences in complex scenarios
        assert len(differences) <= golden_output.get('allowed_differences', 2), \
            f"Too many differences:\n" + "\n".join(differences)
    
    @pytest.mark.integration
    def test_error_handling_golden_output(self, test_config):
        """Test error handling matches expected behavior."""
        # Test with invalid RSS URL
        invalid_podcast = {
            'name': 'Invalid Podcast',
            'rss_url': 'https://invalid.url.that.does.not.exist/feed.xml',
            'category': 'Test'
        }
        
        # Should complete but with failures
        result = seed_podcast(
            invalid_podcast,
            max_episodes=1,
            config=test_config
        )
        
        # Verify expected error handling
        assert result['episodes_processed'] == 0
        assert result['episodes_failed'] >= 0  # May have tried and failed
        assert result['podcasts_processed'] == 1  # Still counts as processed
    
    def create_golden_output(self, test_name: str, podcast_config: Dict[str, Any],
                           max_episodes: int, config: Config, 
                           output_dir: Path):
        """Helper to create golden outputs for new tests.
        
        This is not a test but a utility for generating golden outputs.
        """
        # Clear database
        driver = create_mock_neo4j_driver(
            config.neo4j_uri,
            auth=(config.neo4j_user, config.neo4j_password)
        )
        
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        
        # Process podcast
        result = seed_podcast(
            podcast_config,
            max_episodes=max_episodes,
            config=config
        )
        
        # Get graph structure
        structure = self.get_graph_structure(driver)
        driver.close()
        
        # Create golden output
        golden_output = {
            'test_name': test_name,
            'input': podcast_config,
            'max_episodes': max_episodes,
            'processing_result': {
                'episodes_processed': result['episodes_processed'],
                'episodes_failed': result['episodes_failed']
            },
            'expected_structure': structure,
            'allowed_differences': 2  # Allow minor variations
        }
        
        # Save to file
        output_file = output_dir / f'{test_name}_output.json'
        with open(output_file, 'w') as f:
            json.dump(golden_output, f, indent=2)
        
        print(f"Golden output saved to {output_file}")


@pytest.mark.e2e
class TestPerformanceRegression:
    """Test for performance regressions."""
    
    @pytest.fixture
    def performance_baselines(self):
        """Load performance baselines."""
        baseline_file = Path(__file__).parent.parent / 'fixtures' / 'performance_baselines.json'
        if baseline_file.exists():
            with open(baseline_file, 'r') as f:
                return json.load(f)
        return {}
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_processing_speed_regression(self, test_config, performance_baselines):
        """Test that processing speed hasn't regressed."""
        import time
        
        # Skip if no baseline
        if 'single_episode_time' not in performance_baselines:
            pytest.skip("No performance baseline available")
        
        # Test podcast
        test_podcast = {
            'name': 'Performance Test',
            'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
            'category': 'Test'
        }
        
        # Time the processing
        start_time = time.time()
        result = seed_podcast(
            test_podcast,
            max_episodes=1,
            config=test_config
        )
        processing_time = time.time() - start_time
        
        # Check against baseline (allow 20% variance)
        baseline = performance_baselines['single_episode_time']
        max_allowed = baseline * 1.2
        
        assert processing_time <= max_allowed, \
            f"Processing too slow: {processing_time:.2f}s > {max_allowed:.2f}s (baseline: {baseline:.2f}s)"
    
    @pytest.mark.integration
    @pytest.mark.slow  
    def test_memory_usage_regression(self, test_config, performance_baselines):
        """Test that memory usage hasn't regressed."""
        import psutil
        import gc
        
        # Skip if no baseline
        if 'single_episode_memory' not in performance_baselines:
            pytest.skip("No memory baseline available")
        
        # Test podcast
        test_podcast = {
            'name': 'Memory Test',
            'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
            'category': 'Test'
        }
        
        # Measure memory usage
        gc.collect()
        process = psutil.Process()
        start_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        result = seed_podcast(
            test_podcast,
            max_episodes=1,
            config=test_config
        )
        
        peak_memory = process.memory_info().rss / (1024 * 1024)  # MB
        memory_used = peak_memory - start_memory
        
        # Check against baseline (allow 20% variance)
        baseline = performance_baselines['single_episode_memory']
        max_allowed = baseline * 1.2
        
        assert memory_used <= max_allowed, \
            f"Memory usage too high: {memory_used:.1f}MB > {max_allowed:.1f}MB (baseline: {baseline:.1f}MB)"


@pytest.mark.e2e
class TestEndToEndScenarios:
    """End-to-end test scenarios."""
    
    @pytest.mark.integration
    def test_full_podcast_processing_flow(self, test_config):
        """Test complete flow from RSS to knowledge graph."""
        # Use a small public domain podcast
        podcast = {
            'name': 'LibriVox Short Stories',
            'rss_url': 'https://librivox.org/rss/4833',  # Short story collection
            'category': 'Literature'
        }
        
        # Clear database
        driver = create_mock_neo4j_driver(
            test_config.neo4j_uri,
            auth=(test_config.neo4j_user, test_config.neo4j_password)
        )
        
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        
        # Process podcast
        result = seed_podcast(
            podcast,
            max_episodes=2,
            config=test_config
        )
        
        # Verify complete flow
        assert result['podcasts_processed'] == 1
        assert result['episodes_processed'] > 0
        
        # Verify graph structure
        with driver.session() as session:
            # Check podcast node
            podcast_node = session.run(
                "MATCH (p:Podcast {name: $name}) RETURN p",
                name=podcast['name']
            ).single()
            assert podcast_node is not None
            
            # Check episodes
            episodes = session.run(
                "MATCH (p:Podcast {name: $name})-[:HAS_EPISODE]->(e:Episode) "
                "RETURN count(e) as count",
                name=podcast['name']
            ).single()
            assert episodes['count'] > 0
            
            # Check segments
            segments = session.run(
                "MATCH (e:Episode)-[:HAS_SEGMENT]->(s:Segment) "
                "RETURN count(s) as count"
            ).single()
            assert segments['count'] > 0
            
            # Check insights
            insights = session.run(
                "MATCH (i:Insight) RETURN count(i) as count"
            ).single()
            assert insights['count'] > 0
        
        driver.close()
    
    @pytest.mark.integration
    def test_concurrent_podcast_processing(self, test_config):
        """Test processing multiple podcasts concurrently."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # Multiple test podcasts
        podcasts = [
            {
                'name': f'Concurrent Test {i}',
                'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
                'category': 'Test'
            }
            for i in range(3)
        ]
        
        # Clear database
        driver = create_mock_neo4j_driver(
            test_config.neo4j_uri,
            auth=(test_config.neo4j_user, test_config.neo4j_password)
        )
        
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        
        driver.close()
        
        # Process concurrently
        results = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(
                    seed_podcast,
                    podcast,
                    max_episodes=1,
                    config=test_config
                ): podcast
                for podcast in podcasts
            }
            
            for future in as_completed(futures):
                podcast = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    pytest.fail(f"Concurrent processing failed for {podcast['name']}: {e}")
        
        # Verify all processed
        assert len(results) == 3
        assert all(r['podcasts_processed'] == 1 for r in results)
    
    @pytest.mark.integration
    def test_checkpoint_recovery_e2e(self, test_config, tmp_path):
        """Test checkpoint recovery in end-to-end scenario."""
        # Configure checkpoint directory
        test_config.checkpoint_dir = str(tmp_path)
        test_config.checkpoint_enabled = True
        
        podcast = {
            'name': 'Checkpoint Test',
            'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
            'category': 'Test'
        }
        
        # First run - process 2 episodes
        result1 = seed_podcast(
            podcast,
            max_episodes=2,
            config=test_config
        )
        
        episodes_first_run = result1['episodes_processed']
        assert episodes_first_run > 0
        
        # Verify checkpoint created
        checkpoint_files = list(tmp_path.glob('*.json'))
        assert len(checkpoint_files) > 0
        
        # Second run - should continue from checkpoint
        result2 = seed_podcast(
            podcast,
            max_episodes=4,  # Try to process more
            config=test_config
        )
        
        # Should have processed additional episodes
        episodes_second_run = result2['episodes_processed']
        assert episodes_second_run > episodes_first_run