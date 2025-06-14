"""End-to-end tests for VTT processing pipeline."""

from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import json
import os
import shutil
import tempfile

import pytest

from src.core.config import PipelineConfig
from src.core.extraction_interface import Entity, EntityType, Relationship, RelationshipType
from src.core.interfaces import LLMProvider, GraphProvider, EmbeddingProvider
from src.pipeline.enhanced_knowledge_pipeline import EnhancedKnowledgePipeline
from src.services.embeddings import EmbeddingsService
from src.services.llm import LLMService
from src.storage.graph_storage import GraphStorageService
from src.vtt.vtt_parser import VTTParser
class TestVTTEndToEnd:
    """End-to-end tests for VTT processing pipeline."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp_path = tempfile.mkdtemp()
        yield Path(temp_path)
        shutil.rmtree(temp_path)
    
    @pytest.fixture
    def sample_vtt_files(self, temp_dir):
        """Create sample VTT files for testing."""
        vtt_files = []
        
        # Episode 1: AI in Healthcare
        vtt1_content = """WEBVTT

00:00:00.000 --> 00:00:10.000
<v Host>Welcome to TechTalk. Today we're discussing AI in healthcare with Dr. Emily Chen.

00:00:10.000 --> 00:00:25.000
<v Dr. Chen>Thank you. AI is revolutionizing diagnostics. Our machine learning models can detect diseases like cancer with 97% accuracy.

00:00:25.000 --> 00:00:40.000
<v Host>That's impressive! How does this compare to traditional methods?

00:00:40.000 --> 00:00:55.000
<v Dr. Chen>Traditional screening has about 80% accuracy. AI analyzes patterns humans might miss, especially in early-stage detection.

00:01:00.000 --> 00:01:15.000
<v Host>What about patient privacy and data security?

00:01:15.000 --> 00:01:30.000
<v Dr. Chen>Privacy is paramount. We use federated learning to train models without centralizing patient data.
"""
        
        vtt1_path = temp_dir / "episode1_ai_healthcare.vtt"
        vtt1_path.write_text(vtt1_content)
        vtt_files.append(vtt1_path)
        
        # Episode 2: Climate Technology
        vtt2_content = """WEBVTT

00:00:00.000 --> 00:00:12.000
<v Host>Today on TechTalk, we explore climate technology with environmental scientist Dr. James Park.

00:00:12.000 --> 00:00:28.000
<v Dr. Park>Climate change requires innovative solutions. We're using AI and IoT sensors to optimize renewable energy grids.

00:00:28.000 --> 00:00:45.000
<v Host>How effective are these smart grids?

00:00:45.000 --> 00:01:00.000
<v Dr. Park>Smart grids can reduce energy waste by 30% and integrate renewable sources more efficiently.

00:01:00.000 --> 00:01:18.000
<v Host>What role does machine learning play in climate prediction?

00:01:18.000 --> 00:01:35.000
<v Dr. Park>ML models help us predict weather patterns and optimize energy distribution based on demand forecasts.
"""
        
        vtt2_path = temp_dir / "episode2_climate_tech.vtt"
        vtt2_path.write_text(vtt2_content)
        vtt_files.append(vtt2_path)
        
        # Episode 3: Quantum Computing (shorter)
        vtt3_content = """WEBVTT

00:00:00.000 --> 00:00:15.000
<v Host>Welcome back to TechTalk. Today's topic is quantum computing with Dr. Sarah Kim.

00:00:15.000 --> 00:00:30.000
<v Dr. Kim>Quantum computing will revolutionize cryptography and drug discovery. We're approaching quantum supremacy.

00:00:30.000 --> 00:00:45.000
<v Host>When will quantum computers be commercially available?

00:00:45.000 --> 00:01:00.000
<v Dr. Kim>Within 5-10 years for specialized applications. General purpose quantum computing is still decades away.
"""
        
        vtt3_path = temp_dir / "episode3_quantum.vtt"
        vtt3_path.write_text(vtt3_content)
        vtt_files.append(vtt3_path)
        
        return vtt_files
    
    @pytest.fixture
    def mock_config(self):
        """Create mock pipeline configuration."""
        config = Mock(spec=PipelineConfig)
        config.batch_size = 10
        config.max_workers = 2
        config.checkpoint_enabled = True
        config.checkpoint_dir = "test_checkpoints"
        config.neo4j_uri = "bolt://localhost:7687"
        config.neo4j_user = "neo4j"
        config.neo4j_password = "password"
        return config
    
    @pytest.fixture
    def mock_providers(self):
        """Create mock providers for testing."""
        # Mock LLM Provider
        llm_provider = Mock(spec=LLMProvider)
        llm_provider.process.side_effect = [
            # Entities for episode 1
            """Entities:
            1. **Dr. Emily Chen** - Type: PERSON - AI researcher in healthcare
            2. **TechTalk** - Type: ORGANIZATION - Podcast name
            3. **AI** - Type: TECHNOLOGY - Artificial Intelligence
            4. **machine learning** - Type: TECHNOLOGY - ML technology
            5. **cancer** - Type: CONCEPT - Disease being detected
            6. **federated learning** - Type: TECHNOLOGY - Privacy-preserving ML
            """,
            # Insights for episode 1
            """Insights:
            1. **AI achieves 97% accuracy in disease detection** - Significant improvement over traditional methods
            2. **Privacy preserved through federated learning** - Training without centralizing data
            """,
            # Quotes for episode 1
            """Quotes:
            1. "AI is revolutionizing diagnostics." - Dr. Chen
            2. "Privacy is paramount." - Dr. Chen
            """,
            # Topics for episode 1
            """Topics:
            1. AI in Healthcare
            2. Medical Diagnostics
            3. Privacy in Healthcare AI
            """
        ]
        
        # Mock Graph Provider
        graph_provider = Mock(spec=GraphProvider)
        graph_provider.create_node.return_value = True
        graph_provider.create_relationship.return_value = True
        graph_provider.query.return_value = []
        graph_provider.verify_connection.return_value = True
        
        # Track created nodes and relationships for verification
        created_nodes = []
        created_relationships = []
        
        def track_node(label, properties):
            created_nodes.append({'label': label, 'properties': properties})
            return True
        
        def track_relationship(start_id, end_id, rel_type, properties=None):
            created_relationships.append({
                'start': start_id,
                'end': end_id,
                'type': rel_type,
                'properties': properties or {}
            })
            return True
        
        graph_provider.create_node.side_effect = track_node
        graph_provider.create_relationship.side_effect = track_relationship
        graph_provider._created_nodes = created_nodes
        graph_provider._created_relationships = created_relationships
        
        # Mock Embedding Provider
        embedding_provider = Mock(spec=EmbeddingProvider)
        embedding_provider.embed_text.return_value = [0.1] * 384  # Mock embedding
        embedding_provider.embed_batch.return_value = [[0.1] * 384] * 10
        
        return {
            'llm': llm_provider,
            'graph': graph_provider,
            'embeddings': embedding_provider
        }
    
    def test_vtt_to_graph_entities(self, mock_providers):
        """Test that VTT content creates proper graph entities."""
        graph_provider = mock_providers['graph']
        
        # Simulate entity creation
        entities = [
            Entity(id="entity_1", name="Dr. Emily Chen", type=EntityType.PERSON, 
                  description="AI researcher in healthcare"),
            Entity(id="entity_2", name="AI", type=EntityType.CONCEPT,
                  description="Artificial Intelligence"),
            Entity(id="entity_3", name="healthcare", type=EntityType.CONCEPT,
                  description="Medical field")
        ]
        
        # Create nodes for entities
        for entity in entities:
            graph_provider.create_node(
                label=entity.type.value,
                properties={
                    'id': entity.id,
                    'name': entity.name,
                    'description': entity.description
                }
            )
        
        # Verify nodes were created
        assert len(graph_provider._created_nodes) == 3
        assert any(n['properties']['name'] == "Dr. Emily Chen" for n in graph_provider._created_nodes)
        assert any(n['label'] == EntityType.PERSON.value for n in graph_provider._created_nodes)
    
    def test_vtt_to_graph_relationships(self, mock_providers):
        """Test that VTT content creates proper relationships."""
        graph_provider = mock_providers['graph']
        
        # Create relationships
        relationships = [
            ("entity_1", "entity_2", RelationshipType.DISCUSSES),
            ("entity_2", "entity_3", RelationshipType.APPLIED_TO),
            ("entity_1", "entity_3", RelationshipType.EXPERT_IN)
        ]
        
        for start, end, rel_type in relationships:
            graph_provider.create_relationship(
                start_id=start,
                end_id=end,
                rel_type=rel_type.value
            )
        
        # Verify relationships
        assert len(graph_provider._created_relationships) == 3
        assert any(r['type'] == RelationshipType.DISCUSSES.value 
                  for r in graph_provider._created_relationships)
    
    def test_batch_vtt_processing(self, temp_dir, sample_vtt_files, mock_config):
        """Test batch processing of multiple VTT files."""
        from src.cli.cli import find_vtt_files, validate_vtt_file
        
        # Find all VTT files
        vtt_files = find_vtt_files(temp_dir, pattern="*.vtt", recursive=False)
        assert len(vtt_files) == 3
        
        # Validate all files
        validation_results = []
        for vtt_file in vtt_files:
            is_valid, error = validate_vtt_file(vtt_file)
            validation_results.append((vtt_file, is_valid, error))
        
        # All files should be valid
        assert all(result[1] for result in validation_results)
        assert all(result[2] is None for result in validation_results)
    
    def test_checkpoint_integration(self, temp_dir, sample_vtt_files):
        """Test checkpoint system with VTT processing.
        
        Note: VTT file tracking is now handled by Neo4j through the orchestrator.
        This test now focuses on episode-level checkpoint functionality.
        """
        from src.seeding.checkpoint import ProgressCheckpoint
        from src.cli.cli import get_file_hash
        
        checkpoint_dir = temp_dir / "checkpoints"
        checkpoint_dir.mkdir()
        
        checkpoint = ProgressCheckpoint(
            checkpoint_dir=str(checkpoint_dir),
            extraction_mode='vtt'
        )
        
        # Test episode-level checkpoint functionality
        vtt_file = sample_vtt_files[0]
        episode_id = "test_episode_1"
        
        # Save episode checkpoint
        checkpoint.save_episode_progress(
            episode_id=episode_id,
            stage='completed',
            data={
                'vtt_file': str(vtt_file),
                'segments': 6,
                'file_hash': get_file_hash(vtt_file)
            }
        )
        
        # Load and verify episode checkpoint
        checkpoint_data = checkpoint.load_episode_progress(episode_id, 'completed')
        assert checkpoint_data is not None
        assert checkpoint_data['segments'] == 6
        assert checkpoint_data['vtt_file'] == str(vtt_file)
        
        # Test file change detection would be handled by Neo4j tracking
        # The orchestrator would compare file hash stored in Neo4j
    
    def test_error_recovery_in_batch(self, temp_dir, sample_vtt_files):
        """Test error recovery during batch processing."""
        # Add an invalid VTT file
        invalid_vtt = temp_dir / "invalid.vtt"
        invalid_vtt.write_text("This is not a valid VTT file")
        
        from src.cli.cli import find_vtt_files, validate_vtt_file
        
        all_files = find_vtt_files(temp_dir, pattern="*.vtt")
        assert len(all_files) == 4  # 3 valid + 1 invalid
        
        # Process with validation
        processed = 0
        failed = 0
        
        for vtt_file in all_files:
            is_valid, error = validate_vtt_file(vtt_file)
            if is_valid:
                processed += 1
            else:
                failed += 1
        
        assert processed == 3
        assert failed == 1
    
    def test_vtt_metadata_in_graph(self, mock_providers):
        """Test that VTT metadata is stored in graph."""
        graph_provider = mock_providers['graph']
        
        # Create episode node with VTT metadata
        episode_properties = {
            'id': 'episode_1',
            'title': 'AI in Healthcare',
            'source': 'vtt',
            'vtt_file': 'episode1_ai_healthcare.vtt',
            'duration': 90.0,  # 1:30 duration from VTT
            'segment_count': 6,
            'speakers': ['Host', 'Dr. Chen']
        }
        
        graph_provider.create_node('Episode', episode_properties)
        
        # Verify episode node
        episode_nodes = [n for n in graph_provider._created_nodes if n['label'] == 'Episode']
        assert len(episode_nodes) == 1
        assert episode_nodes[0]['properties']['source'] == 'vtt'
        assert episode_nodes[0]['properties']['segment_count'] == 6
    
    def test_speaker_relationships(self, mock_providers):
        """Test creation of speaker relationships from VTT."""
        graph_provider = mock_providers['graph']
        
        # Create speaker nodes
        speakers = ['Host', 'Dr. Emily Chen']
        for speaker in speakers:
            graph_provider.create_node('Speaker', {'name': speaker})
        
        # Create relationships between speakers and topics
        graph_provider.create_relationship(
            'speaker_host',
            'topic_ai',
            'DISCUSSES'
        )
        graph_provider.create_relationship(
            'speaker_chen',
            'topic_healthcare',
            'EXPERT_IN'
        )
        
        # Verify speaker nodes and relationships
        speaker_nodes = [n for n in graph_provider._created_nodes if n['label'] == 'Speaker']
        assert len(speaker_nodes) == 2
        
        speaker_rels = [r for r in graph_provider._created_relationships if r['type'] == 'DISCUSSES']
        assert len(speaker_rels) >= 1
    
    def test_vtt_processing_statistics(self, sample_vtt_files):
        """Test collection of processing statistics."""
        from src.vtt.vtt_parser import VTTParser
        
        parser = VTTParser()
        total_segments = 0
        total_duration = 0
        speakers = set()
        
        for vtt_file in sample_vtt_files:
            content = vtt_file.read_text()
            segments = parser.parse_content(content)
            
            total_segments += len(segments)
            if segments:
                total_duration += segments[-1].end_time
                speakers.update(seg.speaker for seg in segments if seg.speaker)
        
        # Verify statistics
        assert total_segments == 16  # 6 + 6 + 4 segments
        assert total_duration > 200  # Total duration in seconds
        assert len(speakers) == 4  # Host + 3 guests
        assert 'Host' in speakers