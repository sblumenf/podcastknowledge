"""
Integration tests for semantic pipeline processing.

These tests verify that all components work together correctly
for semantic conversation-aware processing.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import tempfile

from src.seeding.semantic_orchestrator import SemanticVTTKnowledgeExtractor
from src.core.config import SeedingConfig
from src.services.conversation_analyzer import ConversationAnalyzer
from src.services.segment_regrouper import SegmentRegrouper
from src.core.interfaces import TranscriptSegment
from src.core.conversation_models.conversation import (
    ConversationStructure,
    ConversationUnit,
    ConversationTheme,
    ConversationBoundary,
    ConversationFlow,
    StructuralInsights
)


class TestSemanticPipelineIntegration:
    """Integration tests for semantic processing pipeline."""
    
    @pytest.fixture
    def test_config(self):
        """Create test configuration."""
        config = SeedingConfig()
        config.checkpoint_dir = tempfile.mkdtemp()
        config.archive_processed_vtt = False
        return config
    
    @pytest.fixture
    def sample_vtt_content(self):
        """Create sample VTT content."""
        return """WEBVTT

NOTE
Episode: AI in Healthcare
Guest: Dr. Sarah Johnson

00:00:00.000 --> 00:00:05.000
<v Host>Welcome to our podcast. Today we're discussing AI in healthcare.

00:00:05.000 --> 00:00:10.000
<v Host>I'm joined by Dr. Sarah Johnson, an expert in medical AI.

00:00:10.000 --> 00:00:15.000
<v Dr. Johnson>Thank you for having me. I'm excited to discuss this topic.

00:00:15.000 --> 00:00:20.000
<v Dr. Johnson>AI is revolutionizing how we diagnose and treat diseases.

00:00:20.000 --> 00:00:25.000
<v Host>Can you give us a specific example?

00:00:25.000 --> 00:00:30.000
<v Dr. Johnson>Certainly. We've developed neural networks for cancer detection.

00:00:30.000 --> 00:00:35.000
<v Dr. Johnson>These systems can identify tumors earlier than human radiologists.

00:00:35.000 --> 00:00:40.000
<v Dr. Johnson>The accuracy rate is over 95% in clinical trials.

00:00:40.000 --> 00:00:45.000
<v Host>That's incredible. What about ethical considerations?

00:00:45.000 --> 00:00:50.000
<v Dr. Johnson>Ethics is crucial. We need transparency and patient consent.

00:00:50.000 --> 00:00:55.000
<v Dr. Johnson>AI should augment, not replace, human medical judgment.

00:00:55.000 --> 00:01:00.000
<v Host>Thank you for these insights. This has been enlightening."""
    
    @pytest.fixture
    def sample_vtt_file(self, sample_vtt_content):
        """Create a temporary VTT file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
            f.write(sample_vtt_content)
            return Path(f.name)
    
    @pytest.fixture
    def mock_providers(self):
        """Create mock providers for testing."""
        providers = {
            'llm_service': Mock(),
            'graph_service': Mock(),
            'embedding_service': Mock(),
            'knowledge_extractor': Mock(),
            'entity_resolver': Mock(),
            'segmenter': Mock()
        }
        
        # Mock LLM responses
        providers['llm_service'].generate_completion = Mock(return_value={
            'units': [
                {
                    'start_index': 0,
                    'end_index': 3,
                    'unit_type': 'introduction',
                    'summary': 'Host introduces the topic and guest',
                    'is_complete': True,
                    'completeness_note': 'Complete introduction'
                },
                {
                    'start_index': 4,
                    'end_index': 7,
                    'unit_type': 'topic_discussion',
                    'summary': 'Discussion of AI cancer detection capabilities',
                    'is_complete': True,
                    'completeness_note': 'Complete discussion'
                },
                {
                    'start_index': 8,
                    'end_index': 11,
                    'unit_type': 'topic_discussion',
                    'summary': 'Ethical considerations of medical AI',
                    'is_complete': True,
                    'completeness_note': 'Complete discussion'
                }
            ],
            'themes': [
                {
                    'name': 'AI in Healthcare',
                    'description': 'Applications of AI in medical diagnosis',
                    'related_units': [0, 1, 2]
                },
                {
                    'name': 'Medical Ethics',
                    'description': 'Ethical considerations of AI in medicine',
                    'related_units': [2]
                }
            ],
            'boundaries': [
                {
                    'segment_index': 4,
                    'boundary_type': 'topic_shift',
                    'description': 'Shift to specific examples'
                },
                {
                    'segment_index': 8,
                    'boundary_type': 'topic_shift',
                    'description': 'Shift to ethics discussion'
                }
            ],
            'flow': {
                'narrative_arc': 'introduction -> examples -> ethics',
                'pacing': 'steady',
                'coherence_score': 0.9
            },
            'insights': {
                'fragmentation_issues': [],
                'coherence_observations': ['Well-structured conversation'],
                'suggested_improvements': []
            },
            'total_segments': 12
        })
        
        # Mock entity resolver
        providers['entity_resolver'].resolve_entities = Mock(return_value={
            'resolved_entities': [
                {'value': 'Dr. Sarah Johnson', 'type': 'PERSON', 'confidence': 0.9},
                {'value': 'AI', 'type': 'TECHNOLOGY', 'confidence': 0.95},
                {'value': 'cancer detection', 'type': 'MEDICAL_APPLICATION', 'confidence': 0.8},
                {'value': 'neural networks', 'type': 'TECHNOLOGY', 'confidence': 0.85}
            ],
            'original_count': 8,
            'resolved_count': 4
        })
        
        # Mock knowledge extractor
        providers['knowledge_extractor'].extract_knowledge = Mock(return_value=Mock(
            entities=[
                {'value': 'Dr. Sarah Johnson', 'type': 'PERSON', 'confidence': 0.9},
                {'value': 'AI', 'type': 'TECHNOLOGY', 'confidence': 0.95}
            ],
            quotes=[
                {
                    'value': 'AI is revolutionizing how we diagnose and treat diseases',
                    'speaker': 'Dr. Johnson',
                    'importance_score': 0.9
                }
            ],
            relationships=[
                {
                    'source': 'Dr. Sarah Johnson',
                    'target': 'AI',
                    'type': 'DISCUSSES',
                    'confidence': 0.8
                }
            ],
            metadata={'extracted': True}
        ))
        
        # Mock graph service
        providers['graph_service'].create_node = Mock(return_value=True)
        providers['graph_service'].create_relationship = Mock(return_value=True)
        providers['graph_service'].query = Mock(return_value=[])
        
        return providers
    
    def test_semantic_pipeline_initialization(self, test_config, mock_providers):
        """Test that semantic pipeline components initialize correctly."""
        extractor = SemanticVTTKnowledgeExtractor(test_config)
        
        # Mock provider coordinator
        with patch.object(extractor.provider_coordinator, 'initialize_providers', return_value=True):
            with patch.object(extractor.provider_coordinator, 'llm_service', mock_providers['llm_service']):
                with patch.object(extractor.provider_coordinator, 'graph_service', mock_providers['graph_service']):
                    
                    success = extractor.initialize_components(use_large_context=True)
                    
                    assert success is True
                    assert extractor.semantic_pipeline_executor is not None
                    assert hasattr(extractor.semantic_pipeline_executor, 'conversation_analyzer')
                    assert hasattr(extractor.semantic_pipeline_executor, 'segment_regrouper')
    
    def test_end_to_end_semantic_processing(self, test_config, sample_vtt_file, mock_providers):
        """Test complete semantic processing workflow."""
        extractor = SemanticVTTKnowledgeExtractor(test_config)
        
        # Mock all dependencies
        with patch.multiple(
            extractor,
            initialize_components=Mock(return_value=True),
            llm_service=mock_providers['llm_service'],
            graph_service=mock_providers['graph_service'],
            embedding_service=mock_providers['embedding_service'],
            knowledge_extractor=mock_providers['knowledge_extractor'],
            entity_resolver=mock_providers['entity_resolver']
        ):
            # Mock semantic pipeline executor
            mock_semantic_executor = Mock()
            mock_semantic_executor.process_vtt_segments = Mock(return_value={
                'status': 'success',
                'processing_type': 'semantic',
                'total_segments': 12,
                'meaningful_units': 3,
                'entities': 4,
                'insights': 5,
                'quotes': 3,
                'relationships': 2,
                'unit_statistics': {
                    'average_duration': 20.0,
                    'completeness_rate': 100.0
                },
                'cross_unit_patterns': {
                    'theme_entity_connections': {
                        'AI in Healthcare': ['Dr. Sarah Johnson', 'AI', 'cancer detection'],
                        'Medical Ethics': ['Dr. Sarah Johnson', 'AI']
                    }
                }
            })
            
            extractor.semantic_pipeline_executor = mock_semantic_executor
            extractor.pipeline_executor = mock_semantic_executor
            
            # Mock episode tracker
            mock_tracker = Mock()
            mock_tracker.is_episode_processed = Mock(return_value=False)
            mock_tracker.mark_episode_complete = Mock()
            extractor.episode_tracker = mock_tracker
            
            # Process the VTT file
            result = extractor.process_vtt_files(
                [sample_vtt_file],
                use_large_context=True,
                use_semantic_processing=True
            )
            
            # Verify results
            assert result['processing_type'] == 'semantic'
            assert result['files_processed'] == 1
            assert result['files_failed'] == 0
            assert result['total_meaningful_units'] == 3
            assert result['total_themes'] == 2
            
            # Verify semantic executor was called
            mock_semantic_executor.process_vtt_segments.assert_called_once()
            
            # Clean up
            sample_vtt_file.unlink()
    
    def test_conversation_structure_analysis(self, mock_providers):
        """Test conversation structure analysis component."""
        analyzer = ConversationAnalyzer(mock_providers['llm_service'])
        
        # Create sample segments
        segments = [
            TranscriptSegment(
                id="seg_0",
                text="Welcome to our podcast.",
                start_time=0.0,
                end_time=5.0,
                speaker="Host"
            ),
            TranscriptSegment(
                id="seg_1",
                text="Today we're discussing AI.",
                start_time=5.0,
                end_time=10.0,
                speaker="Host"
            )
        ]
        
        # Analyze structure
        structure = analyzer.analyze_structure(segments)
        
        # Verify structure
        assert isinstance(structure, ConversationStructure)
        assert len(structure.units) == 3
        assert len(structure.themes) == 2
        assert structure.flow.coherence_score == 0.9
    
    def test_segment_regrouping(self):
        """Test segment regrouping into meaningful units."""
        regrouper = SegmentRegrouper()
        
        # Create sample segments and structure
        segments = [
            TranscriptSegment(f"seg_{i}", f"Text {i}", i*5.0, (i+1)*5.0, "Speaker")
            for i in range(6)
        ]
        
        structure = ConversationStructure(
            units=[
                ConversationUnit(0, 2, "introduction", "Intro", True, "Complete"),
                ConversationUnit(3, 5, "topic_discussion", "Main topic", True, "Complete")
            ],
            themes=[
                ConversationTheme("Main Theme", "Description", [0, 1])
            ],
            boundaries=[
                ConversationBoundary(3, "topic_shift", "New topic")
            ],
            flow=ConversationFlow("intro->main", "steady", 0.9),
            insights=StructuralInsights([], ["Good flow"], []),
            total_segments=6
        )
        
        # Regroup segments
        units = regrouper.regroup_segments(segments, structure)
        
        # Verify regrouping
        assert len(units) == 2
        assert units[0].unit_type == "introduction"
        assert len(units[0].segments) == 3
        assert units[1].unit_type == "topic_discussion"
        assert len(units[1].segments) == 3
    
    def test_meaningful_unit_extraction(self, mock_providers):
        """Test knowledge extraction from meaningful units."""
        from src.extraction.meaningful_unit_extractor import MeaningfulUnitExtractor
        from src.services.segment_regrouper import MeaningfulUnit
        
        base_extractor = mock_providers['knowledge_extractor']
        unit_extractor = MeaningfulUnitExtractor(base_extractor)
        
        # Create sample unit
        segments = [
            TranscriptSegment("seg_0", "AI is transforming healthcare", 0.0, 5.0, "Dr. Johnson"),
            TranscriptSegment("seg_1", "We use neural networks", 5.0, 10.0, "Dr. Johnson")
        ]
        
        unit = MeaningfulUnit(
            id="unit_001",
            segments=segments,
            unit_type="topic_discussion",
            summary="AI in healthcare discussion",
            themes=["AI Healthcare"],
            start_time=0.0,
            end_time=10.0,
            speaker_distribution={"Dr. Johnson": 100.0},
            is_complete=True
        )
        
        # Extract from unit
        result = unit_extractor.extract_from_unit(unit)
        
        # Verify extraction
        assert result.unit_id == "unit_001"
        assert len(result.entities) >= 2  # Should have deduplicated entities
        assert len(result.themes) == 1
        assert result.metadata['unit_type'] == 'topic_discussion'
    
    def test_cross_unit_entity_resolution(self, mock_providers):
        """Test entity resolution across multiple units."""
        from src.extraction.meaningful_unit_entity_resolver import MeaningfulUnitEntityResolver
        
        resolver = MeaningfulUnitEntityResolver()
        
        # Create unit results with overlapping entities
        unit_results = [
            {
                'unit_id': 'unit_001',
                'entities': [
                    {'value': 'Dr. Johnson', 'type': 'PERSON', 'confidence': 0.9},
                    {'value': 'artificial intelligence', 'type': 'TECHNOLOGY', 'confidence': 0.8}
                ]
            },
            {
                'unit_id': 'unit_002',
                'entities': [
                    {'value': 'Dr. Sarah Johnson', 'type': 'PERSON', 'confidence': 0.95},
                    {'value': 'AI', 'type': 'TECHNOLOGY', 'confidence': 0.85}
                ]
            }
        ]
        
        # Resolve across units
        resolution = resolver.resolve_entities_across_units(unit_results)
        
        # Verify cross-unit resolution
        assert resolution['total_original'] == 4
        assert resolution['total_canonical'] == 2  # Should merge similar entities
        assert resolution['reduction_ratio'] > 0
    
    def test_semantic_vs_segment_comparison(self, test_config, sample_vtt_file, mock_providers):
        """Test comparison between semantic and segment processing."""
        extractor = SemanticVTTKnowledgeExtractor(test_config)
        
        # Mock dependencies
        with patch.multiple(
            extractor,
            initialize_components=Mock(return_value=True),
            llm_service=mock_providers['llm_service'],
            process_vtt_files=Mock(side_effect=[
                # Segment processing result
                {
                    'total_segments': 12,
                    'total_entities': 20,
                    'total_insights': 10,
                    'total_relationships': 5
                },
                # Semantic processing result
                {
                    'total_segments': 12,
                    'total_meaningful_units': 3,
                    'total_entities': 8,
                    'total_insights': 15,
                    'total_relationships': 10,
                    'total_themes': 2,
                    'segment_to_unit_ratio': 4.0
                }
            ])
        ):
            # Compare methods
            comparison = extractor.compare_processing_methods(str(sample_vtt_file))
            
            # Verify comparison
            assert 'segment_processing' in comparison
            assert 'semantic_processing' in comparison
            assert comparison['semantic_processing']['meaningful_units'] == 3
            assert comparison['improvements']['entity_reduction'] > 0
            
            # Clean up
            sample_vtt_file.unlink()