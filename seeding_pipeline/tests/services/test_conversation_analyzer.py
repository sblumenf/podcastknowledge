"""Tests for conversation structure analyzer."""

import pytest
from unittest.mock import Mock, patch
from src.services.conversation_analyzer import ConversationAnalyzer
from src.core.conversation_models.conversation import (
    ConversationStructure,
    ConversationUnit,
    ConversationTheme,
    ConversationFlow,
    StructuralInsights,
    ConversationBoundary
)
from src.core.interfaces import TranscriptSegment
from src.core.exceptions import ProcessingError


class TestConversationAnalyzer:
    """Test conversation structure analysis."""
    
    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service."""
        return Mock()
    
    @pytest.fixture
    def analyzer(self, mock_llm_service):
        """Create analyzer instance."""
        return ConversationAnalyzer(mock_llm_service)
    
    @pytest.fixture
    def sample_segments(self):
        """Create sample transcript segments."""
        return [
            TranscriptSegment(
                id="seg_0",
                start_time=0.0,
                end_time=5.0,
                text="Welcome to our podcast. Today we're discussing AI.",
                speaker="Host",
                confidence=0.95
            ),
            TranscriptSegment(
                id="seg_1", 
                start_time=5.0,
                end_time=10.0,
                text="Thanks for having me. I'm excited to talk about",
                speaker="Guest",
                confidence=0.93
            ),
            TranscriptSegment(
                id="seg_2",
                start_time=10.0,
                end_time=15.0,
                text="the latest developments in machine learning.",
                speaker="Guest",
                confidence=0.94
            ),
            TranscriptSegment(
                id="seg_3",
                start_time=15.0,
                end_time=20.0,
                text="Let's start with neural networks. Can you explain",
                speaker="Host",
                confidence=0.92
            ),
            TranscriptSegment(
                id="seg_4",
                start_time=20.0,
                end_time=25.0,
                text="how they work for our audience?",
                speaker="Host",
                confidence=0.91
            ),
            TranscriptSegment(
                id="seg_5",
                start_time=25.0,
                end_time=30.0,
                text="Sure! Neural networks are computational models",
                speaker="Guest",
                confidence=0.95
            )
        ]
    
    @pytest.fixture
    def sample_structure(self):
        """Create sample conversation structure."""
        return ConversationStructure(
            units=[
                ConversationUnit(
                    start_index=0,
                    end_index=2,
                    unit_type="introduction",
                    description="Opening and guest introduction",
                    completeness="complete",
                    key_entities=["AI", "machine learning"],
                    confidence=0.9
                ),
                ConversationUnit(
                    start_index=3,
                    end_index=5,
                    unit_type="q&a_pair",
                    description="Host asks about neural networks, guest begins explanation",
                    completeness="incomplete",
                    key_entities=["neural networks"],
                    confidence=0.85
                )
            ],
            themes=[
                ConversationTheme(
                    theme="AI and Machine Learning",
                    description="Discussion of AI concepts and technologies",
                    evolution="Starts broad with AI mention, narrows to neural networks",
                    related_units=[0, 1]
                )
            ],
            flow=ConversationFlow(
                opening="Standard podcast introduction with topic announcement",
                development="Moves from general AI discussion to specific neural network explanation",
                conclusion=None
            ),
            insights=StructuralInsights(
                fragmentation_issues=["Guest's introduction split between segments 1-2"],
                missing_context=[],
                natural_boundaries=[3],
                overall_coherence=0.85
            ),
            boundaries=[
                ConversationBoundary(
                    segment_index=3,
                    boundary_type="topic_shift",
                    confidence=0.9,
                    reason="Shift from introduction to main content"
                )
            ],
            total_segments=6
        )
    
    def test_analyze_structure_success(self, analyzer, mock_llm_service, sample_segments, sample_structure):
        """Test successful structure analysis."""
        # Configure mock to return structure
        mock_llm_service.generate_completion.return_value = sample_structure.model_dump()
        
        # Analyze structure
        result = analyzer.analyze_structure(sample_segments)
        
        # Verify result
        assert isinstance(result, ConversationStructure)
        assert len(result.units) == 2
        assert result.units[0].unit_type == "introduction"
        assert result.units[1].unit_type == "q&a_pair"
        assert len(result.themes) == 1
        assert result.insights.overall_coherence == 0.85
        
        # Verify LLM was called
        mock_llm_service.generate_completion.assert_called_once()
        call_args = mock_llm_service.generate_completion.call_args
        assert "You are an expert conversation analyst" in call_args.kwargs["system_prompt"]
        assert call_args.kwargs["response_format"] == ConversationStructure
        assert call_args.kwargs["temperature"] == 0.1
    
    def test_analyze_structure_empty_segments(self, analyzer):
        """Test analysis with empty segments."""
        with pytest.raises(ProcessingError, match="No segments provided"):
            analyzer.analyze_structure([])
    
    def test_analyze_structure_llm_failure(self, analyzer, mock_llm_service, sample_segments):
        """Test handling of LLM failure."""
        # Configure mock to raise exception
        mock_llm_service.generate_completion.side_effect = Exception("LLM error")
        
        # Should raise ProcessingError
        with pytest.raises(ProcessingError, match="Conversation structure analysis failed"):
            analyzer.analyze_structure(sample_segments)
    
    def test_validate_structure_invalid_indices(self, analyzer, sample_segments):
        """Test validation catches invalid unit indices."""
        # Create structure with invalid indices
        invalid_structure = ConversationStructure(
            units=[
                ConversationUnit(
                    start_index=0,
                    end_index=10,  # Beyond segment count
                    unit_type="topic_discussion",
                    description="Invalid unit",
                    completeness="complete",
                    key_entities=[],
                    confidence=0.8
                )
            ],
            themes=[],
            flow=ConversationFlow(
                opening="Test",
                development="Test"
            ),
            insights=StructuralInsights(
                fragmentation_issues=[],
                missing_context=[],
                natural_boundaries=[],
                overall_coherence=0.5
            ),
            total_segments=6
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Unit indices out of range"):
            analyzer._validate_structure(invalid_structure, len(sample_segments))
    
    def test_prepare_transcript_data(self, analyzer, sample_segments):
        """Test transcript data preparation."""
        data = analyzer._prepare_transcript_data(sample_segments)
        
        # Check structure
        assert "transcript" in data
        assert "speaker_stats" in data
        assert data["total_segments"] == 6
        assert data["total_duration"] == 30.0
        
        # Check speaker stats
        assert "Host" in data["speaker_stats"]
        assert "Guest" in data["speaker_stats"]
        assert data["speaker_stats"]["Host"]["count"] == 3
        assert data["speaker_stats"]["Guest"]["count"] == 3
        
        # Check transcript format
        lines = data["transcript"].split("\n")
        assert len(lines) == 6
        assert "[0] [Host 00:00]" in lines[0]
        assert "Welcome to our podcast" in lines[0]
    
    def test_unit_type_detection(self, analyzer, mock_llm_service):
        """Test detection of different unit types."""
        # Create segments representing different unit types
        segments = [
            # Story unit
            TranscriptSegment(
                id="story_1",
                start_time=0.0,
                end_time=5.0,
                text="Let me tell you about the time I first encountered AI.",
                speaker="Guest",
                confidence=0.95
            ),
            TranscriptSegment(
                id="story_2",
                start_time=5.0,
                end_time=10.0,
                text="It was back in 2015, and I was working on a project",
                speaker="Guest", 
                confidence=0.94
            ),
            TranscriptSegment(
                id="story_3",
                start_time=10.0,
                end_time=15.0,
                text="that completely changed my perspective on technology.",
                speaker="Guest",
                confidence=0.93
            )
        ]
        
        # Configure mock response
        mock_response = ConversationStructure(
            units=[
                ConversationUnit(
                    start_index=0,
                    end_index=2,
                    unit_type="story",
                    description="Guest's personal AI discovery story",
                    completeness="complete",
                    key_entities=["AI", "2015", "technology"],
                    confidence=0.95
                )
            ],
            themes=[
                ConversationTheme(
                    theme="Personal AI Journey",
                    description="Guest's introduction to AI field",
                    evolution="Personal anecdote establishing expertise",
                    related_units=[0]
                )
            ],
            flow=ConversationFlow(
                opening="Personal story introduction",
                development="Chronological narrative"
            ),
            insights=StructuralInsights(
                fragmentation_issues=[],
                missing_context=[],
                natural_boundaries=[],
                overall_coherence=0.95
            ),
            total_segments=3
        )
        
        mock_llm_service.generate_completion.return_value = mock_response.model_dump()
        
        # Analyze
        result = analyzer.analyze_structure(segments)
        
        # Verify story unit detected
        assert result.units[0].unit_type == "story"
        assert result.units[0].completeness == "complete"
        assert "AI" in result.units[0].key_entities