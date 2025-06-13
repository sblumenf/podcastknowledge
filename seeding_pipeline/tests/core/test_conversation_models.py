"""Tests for conversation structure models."""

import pytest
from pydantic import ValidationError
from src.core.conversation_models.conversation import (
    ConversationBoundary,
    ConversationUnit,
    ConversationTheme,
    ConversationFlow,
    StructuralInsights,
    ConversationStructure
)


class TestConversationBoundary:
    """Test ConversationBoundary model validation."""
    
    def test_valid_boundary(self):
        """Test creating valid boundary."""
        boundary = ConversationBoundary(
            segment_index=5,
            boundary_type="topic_shift",
            confidence=0.85,
            reason="Clear transition from intro to main content"
        )
        assert boundary.segment_index == 5
        assert boundary.boundary_type == "topic_shift"
        assert boundary.confidence == 0.85
    
    def test_invalid_boundary_type(self):
        """Test invalid boundary type."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationBoundary(
                segment_index=5,
                boundary_type="invalid_type",
                confidence=0.85,
                reason="Test"
            )
        assert "boundary_type must be one of" in str(exc_info.value)
    
    def test_invalid_confidence(self):
        """Test confidence out of range."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationBoundary(
                segment_index=5,
                boundary_type="topic_shift",
                confidence=1.5,
                reason="Test"
            )
        assert "less than or equal to 1.0" in str(exc_info.value)


class TestConversationUnit:
    """Test ConversationUnit model validation."""
    
    def test_valid_unit(self):
        """Test creating valid unit."""
        unit = ConversationUnit(
            start_index=0,
            end_index=5,
            unit_type="introduction",
            description="Opening remarks and guest introduction",
            completeness="complete",
            key_entities=["AI", "machine learning"],
            confidence=0.9
        )
        assert unit.start_index == 0
        assert unit.end_index == 5
        assert len(unit.key_entities) == 2
    
    def test_invalid_index_range(self):
        """Test end_index < start_index."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationUnit(
                start_index=10,
                end_index=5,
                unit_type="story",
                description="Test",
                completeness="complete",
                confidence=0.8
            )
        assert "end_index must be >= start_index" in str(exc_info.value)
    
    def test_invalid_unit_type(self):
        """Test invalid unit type."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationUnit(
                start_index=0,
                end_index=5,
                unit_type="invalid_type",
                description="Test",
                completeness="complete",
                confidence=0.8
            )
        assert "unit_type must be one of" in str(exc_info.value)
    
    def test_invalid_completeness(self):
        """Test invalid completeness value."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationUnit(
                start_index=0,
                end_index=5,
                unit_type="story",
                description="Test",
                completeness="partial",
                confidence=0.8
            )
        assert "completeness must be one of" in str(exc_info.value)


class TestConversationStructure:
    """Test ConversationStructure model validation."""
    
    def test_valid_structure(self):
        """Test creating valid structure."""
        structure = ConversationStructure(
            units=[
                ConversationUnit(
                    start_index=0,
                    end_index=2,
                    unit_type="introduction",
                    description="Opening",
                    completeness="complete",
                    confidence=0.9
                ),
                ConversationUnit(
                    start_index=3,
                    end_index=5,
                    unit_type="q&a_pair",
                    description="First question",
                    completeness="complete", 
                    confidence=0.85
                )
            ],
            themes=[
                ConversationTheme(
                    theme="AI Technology",
                    description="Discussion of AI advancements",
                    evolution="From general to specific applications",
                    related_units=[0, 1]
                )
            ],
            flow=ConversationFlow(
                opening="Standard podcast intro",
                development="Question-based exploration"
            ),
            insights=StructuralInsights(
                fragmentation_issues=[],
                missing_context=[],
                natural_boundaries=[3],
                overall_coherence=0.9
            ),
            boundaries=[
                ConversationBoundary(
                    segment_index=3,
                    boundary_type="topic_shift",
                    confidence=0.85,
                    reason="Transition to main content"
                )
            ],
            total_segments=6
        )
        assert len(structure.units) == 2
        assert len(structure.themes) == 1
        assert structure.total_segments == 6
    
    def test_overlapping_units(self):
        """Test validation catches overlapping units."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationStructure(
                units=[
                    ConversationUnit(
                        start_index=0,
                        end_index=5,
                        unit_type="introduction",
                        description="Opening",
                        completeness="complete",
                        confidence=0.9
                    ),
                    ConversationUnit(
                        start_index=3,
                        end_index=8,
                        unit_type="story",
                        description="Overlapping story",
                        completeness="complete",
                        confidence=0.85
                    )
                ],
                themes=[],
                flow=ConversationFlow(
                    opening="Test",
                    development="Test"
                ),
                insights=StructuralInsights(
                    overall_coherence=0.5
                ),
                total_segments=10
            )
        assert "Units overlap" in str(exc_info.value)
    
    def test_invalid_theme_references(self):
        """Test validation catches invalid theme unit references."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationStructure(
                units=[
                    ConversationUnit(
                        start_index=0,
                        end_index=2,
                        unit_type="introduction",
                        description="Opening",
                        completeness="complete",
                        confidence=0.9
                    )
                ],
                themes=[
                    ConversationTheme(
                        theme="Test Theme",
                        description="Test",
                        evolution="Test",
                        related_units=[0, 5]  # Unit 5 doesn't exist
                    )
                ],
                flow=ConversationFlow(
                    opening="Test",
                    development="Test"
                ),
                insights=StructuralInsights(
                    overall_coherence=0.5
                ),
                total_segments=3
            )
        assert "references invalid unit index" in str(exc_info.value)
    
    def test_invalid_boundary_index(self):
        """Test validation catches boundary index out of range."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationStructure(
                units=[
                    ConversationUnit(
                        start_index=0,
                        end_index=2,
                        unit_type="introduction",
                        description="Opening",
                        completeness="complete",
                        confidence=0.9
                    )
                ],
                themes=[],
                flow=ConversationFlow(
                    opening="Test",
                    development="Test"
                ),
                insights=StructuralInsights(
                    overall_coherence=0.5
                ),
                boundaries=[
                    ConversationBoundary(
                        segment_index=10,  # Beyond total_segments
                        boundary_type="topic_shift",
                        confidence=0.8,
                        reason="Test"
                    )
                ],
                total_segments=3
            )
        assert "exceeds total segments" in str(exc_info.value)
    
    def test_frozen_models(self):
        """Test that models are frozen (immutable)."""
        unit = ConversationUnit(
            start_index=0,
            end_index=5,
            unit_type="introduction",
            description="Test",
            completeness="complete",
            confidence=0.9
        )
        
        with pytest.raises(AttributeError):
            unit.start_index = 10  # Should fail because model is frozen