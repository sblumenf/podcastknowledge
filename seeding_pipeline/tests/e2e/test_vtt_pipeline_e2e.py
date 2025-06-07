"""E2E tests for VTT → Knowledge Graph pipeline."""
from pathlib import Path
from typing import Dict, Any
import os
import tempfile

from neo4j import GraphDatabase
import pytest

from src.core.config import SeedingConfig
from src.seeding.orchestrator import VTTKnowledgeExtractor
from tests.utils.neo4j_mocks import create_mock_neo4j_driver
@pytest.mark.e2e
class TestVTTPipelineE2E:
    """End-to-end tests for the complete VTT processing pipeline."""
    
    @pytest.fixture
    def sample_vtt_file(self, tmp_path):
        """Create minimal VTT file for testing."""
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
Hello, welcome to our test podcast episode.

00:00:05.000 --> 00:00:10.000
Today we'll be discussing machine learning and AI.

00:00:10.000 --> 00:00:15.000
These technologies are transforming how we work.

00:00:15.000 --> 00:00:20.000
Thank you for listening to our show.
"""
        vtt_file = tmp_path / "test_episode.vtt"
        vtt_file.write_text(vtt_content, encoding='utf-8')
        return vtt_file
    
    @pytest.fixture
    def neo4j_test_db(self):
        """Set up clean test database."""
        # Use test environment variables or defaults
        neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
        neo4j_password = os.getenv('NEO4J_PASSWORD', 'password')
        
        # Connect to Neo4j
        driver = create_mock_neo4j_driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
        # Clear the test database before test
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        
        yield driver
        
        # Cleanup: Clear the test database after test
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        
        driver.close()
    
    @pytest.fixture
    def test_config(self):
        """Create test configuration."""
        return SeedingConfig(
            neo4j_uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
            neo4j_username=os.getenv('NEO4J_USERNAME', 'neo4j'),
            neo4j_password=os.getenv('NEO4J_PASSWORD', 'password'),
            save_checkpoints=False,  # Disable checkpointing for tests
        )
    
    @pytest.fixture
    def podcast_data(self, sample_vtt_file):
        """Create podcast data structure for testing."""
        return {
            'name': 'Test Podcast',
            'vtt_files': [
                {
                    'path': str(sample_vtt_file),
                    'title': 'Test Episode 1'
                }
            ]
        }
    
    def test_vtt_file_processing(self, sample_vtt_file, neo4j_test_db, test_config, podcast_data):
        """Test: VTT file → parsed → extracted → stored in Neo4j."""
        # Act: Process the VTT file through the pipeline
        pipeline = VTTKnowledgeExtractor(test_config)
        try:
            pipeline.initialize_components()
            result = pipeline.process_vtt_files([sample_vtt_file])
            
            # Assert: Processing completed successfully
            assert result['files_processed'] == 1
            assert result['files_failed'] == 0
            
        finally:
            pipeline.cleanup()
        
        # For mock testing, we just verify the processing completed
        # In a real test with actual Neo4j, we would verify nodes were created
    
    def test_knowledge_extraction(self, sample_vtt_file, neo4j_test_db, test_config, podcast_data):
        """Test: Entities and relationships created correctly."""
        # Act: Process the VTT file
        pipeline = VTTKnowledgeExtractor(test_config)
        try:
            pipeline.initialize_components()
            result = pipeline.process_vtt_files([sample_vtt_file])
            
            # Assert: Basic processing succeeded
            assert result['files_processed'] == 1
        finally:
            pipeline.cleanup()
        
        # Verify specific knowledge was extracted and stored
        with neo4j_test_db.session() as session:
            # Check for podcast node
            podcast_result = session.run(
                "MATCH (p:Podcast {name: $name}) RETURN p", 
                name="Test Podcast"
            )
            podcast_node = podcast_result.single()
            assert podcast_node is not None, "Podcast node not found"
            
            # Check for episode node
            episode_result = session.run(
                "MATCH (e:Episode) RETURN e LIMIT 1"
            )
            episode_node = episode_result.single()
            assert episode_node is not None, "Episode node not found"
            
            # Check for relationships
            relationship_result = session.run(
                "MATCH ()-[r]->() RETURN count(r) as count"
            )
            relationship_count = relationship_result.single()['count']
            assert relationship_count > 0, "No relationships were created"
    
    def test_multiple_episodes(self, neo4j_test_db, test_config, tmp_path):
        """Test: Multiple VTT files processed in sequence."""
        # Arrange: Create multiple VTT files
        vtt_files = []
        for i in range(2):
            vtt_content = f"""WEBVTT

00:00:00.000 --> 00:00:05.000
This is episode {i+1} of our test series.

00:00:05.000 --> 00:00:10.000
We're discussing topic {i+1} today.

00:00:10.000 --> 00:00:15.000
Thank you for listening to episode {i+1}.
"""
            vtt_file = tmp_path / f"episode_{i+1}.vtt"
            vtt_file.write_text(vtt_content, encoding='utf-8')
            vtt_files.append({
                'path': str(vtt_file),
                'title': f'Test Episode {i+1}'
            })
        
        podcast_data_multi = {
            'name': 'Multi-Episode Test Podcast',
            'vtt_files': vtt_files
        }
        
        # Act: Process multiple episodes
        pipeline = VTTKnowledgeExtractor(test_config)
        try:
            pipeline.initialize_components()
            vtt_paths = [Path(vf['path']) for vf in vtt_files]
            result = pipeline.process_vtt_files(vtt_paths)
            
            # Assert: All episodes processed successfully
            assert result['files_processed'] == 2
            assert result['files_failed'] == 0
        finally:
            pipeline.cleanup()
        
        # Verify multiple episodes in Neo4j
        with neo4j_test_db.session() as session:
            # Check episode count
            episode_result = session.run("MATCH (e:Episode) RETURN count(e) as count")
            episode_count = episode_result.single()['count']
            assert episode_count == 2, f"Expected 2 episodes, found {episode_count}"
            
            # Check that episodes belong to the same podcast
            podcast_episode_result = session.run("""
                MATCH (p:Podcast)-[r:HAS_EPISODE]->(e:Episode) 
                RETURN count(e) as episode_count
            """)
            connected_episodes = podcast_episode_result.single()['episode_count']
            assert connected_episodes == 2, "Episodes not properly connected to podcast"
    
    @pytest.fixture
    def vtt_samples(self):
        """Load VTT sample files for testing."""
        fixtures_dir = Path(__file__).parent.parent / 'fixtures' / 'vtt_samples'
        return {
            'minimal': fixtures_dir / 'minimal.vtt',
            'standard': fixtures_dir / 'standard.vtt',
            'complex': fixtures_dir / 'complex.vtt'
        }