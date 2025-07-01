"""Data models for conversation structure analysis."""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ConversationBoundary(BaseModel):
    """Represents a boundary between conversation topics or units."""
    model_config = ConfigDict(frozen=True)
    
    segment_index: int = Field(
        description="Index of segment where boundary occurs",
        ge=0
    )
    boundary_type: str = Field(
        description="Type of boundary: topic_shift, speaker_change, story_end, q&a_complete"
    )
    confidence: float = Field(
        description="Confidence score 0.0-1.0",
        ge=0.0,
        le=1.0
    )
    reason: str = Field(
        description="Explanation for boundary detection",
        min_length=1
    )
    
    @field_validator('boundary_type')
    @classmethod
    def validate_boundary_type(cls, v: str) -> str:
        """Validate boundary type is one of allowed values."""
        allowed_types = {'topic_shift', 'speaker_change', 'story_end', 'q&a_complete'}
        if v not in allowed_types:
            # Map common variations to allowed types
            type_mapping = {
                'conclusion': 'topic_shift',
                'segment_end': 'story_end',
                'transition': 'topic_shift',
                'end': 'story_end'
            }
            v = type_mapping.get(v, 'topic_shift')  # Default to topic_shift
        return v


class ConversationUnit(BaseModel):
    """Represents a semantically coherent group of segments."""
    model_config = ConfigDict(frozen=True)
    
    start_index: int = Field(
        description="Starting segment index (inclusive)",
        ge=0
    )
    end_index: int = Field(
        description="Ending segment index (inclusive)",
        ge=0
    )
    unit_type: str = Field(
        description="Type: topic_discussion, story, q&a_pair, introduction, conclusion"
    )
    description: str = Field(
        description="Brief description of unit content",
        min_length=1
    )
    completeness: str = Field(
        description="complete, incomplete, fragmented"
    )
    key_entities: List[str] = Field(
        default_factory=list,
        description="Main entities discussed",
        max_items=20
    )
    confidence: float = Field(
        description="Confidence score 0.0-1.0",
        ge=0.0,
        le=1.0
    )
    
    @field_validator('end_index')
    @classmethod
    def validate_end_index(cls, v: int, values) -> int:
        """Ensure end_index >= start_index."""
        if 'start_index' in values.data and v < values.data['start_index']:
            raise ValueError("end_index must be >= start_index")
        return v
    
    @field_validator('unit_type')
    @classmethod
    def validate_unit_type(cls, v: str) -> str:
        """Validate unit type is one of allowed values."""
        allowed_types = {
            'topic_discussion', 'story', 'q&a_pair', 'introduction', 'conclusion',
            'expert_explanation', 'solution', 'transition', 'host_commentary', 
            'call_to_action', 'personal_story', 'advice', 'summary'
        }
        if v not in allowed_types:
            # If not in allowed types, map to closest allowed type
            type_mapping = {
                'expert_discussion': 'topic_discussion',
                'personal_narrative': 'story',
                'recommendations': 'advice',
                'recap': 'summary',
                'commentary': 'host_commentary'
            }
            v = type_mapping.get(v, 'topic_discussion')  # Default to topic_discussion
        return v
    
    @field_validator('completeness')
    @classmethod
    def validate_completeness(cls, v: str) -> str:
        """Validate completeness is one of allowed values."""
        allowed_values = {'complete', 'incomplete', 'fragmented'}
        # Normalize to lowercase
        v_lower = v.lower() if isinstance(v, str) else str(v).lower()
        if v_lower not in allowed_values:
            raise ValueError(f"completeness must be one of {allowed_values}, got '{v}'")
        return v_lower




class ConversationTheme(BaseModel):
    """Major theme running through the conversation."""
    model_config = ConfigDict(frozen=True)
    
    theme: str = Field(
        description="Theme name",
        min_length=1,
        max_length=200
    )
    description: str = Field(
        description="What aspects are explored",
        min_length=1
    )
    evolution: str = Field(
        description="How theme develops through conversation",
        min_length=1
    )
    related_units: List[int] = Field(
        default_factory=list,
        description="Indices of units discussing this theme"
    )


class ConversationFlow(BaseModel):
    """Overall narrative arc of the conversation."""
    model_config = ConfigDict(frozen=True)
    
    opening: str = Field(
        description="How conversation starts",
        min_length=1
    )
    development: str = Field(
        description="How topics build on each other",
        min_length=1
    )
    conclusion: Optional[str] = Field(
        default=None,
        description="How it wraps up (if applicable)"
    )


class StructuralInsights(BaseModel):
    """Observations about conversation quality and structure."""
    model_config = ConfigDict(frozen=True)
    
    fragmentation_issues: List[str] = Field(
        default_factory=list,
        description="Where thoughts are unnaturally split",
        max_items=50
    )
    missing_context: List[str] = Field(
        default_factory=list,
        description="Where additional context would help",
        max_items=50
    )
    natural_boundaries: List[int] = Field(
        default_factory=list,
        description="Segment indices with clean topic breaks"
    )
    overall_coherence: float = Field(
        description="Overall coherence score 0.0-1.0",
        ge=0.0,
        le=1.0
    )


class ConversationStructure(BaseModel):
    """Complete conversation structure analysis result."""
    model_config = ConfigDict(frozen=True)
    
    units: List[ConversationUnit] = Field(
        description="Semantic conversation units",
        min_items=1
    )
    themes: List[ConversationTheme] = Field(
        description="Major themes throughout conversation",
        default_factory=list
    )
    flow: ConversationFlow = Field(
        description="Narrative arc"
    )
    insights: StructuralInsights = Field(
        description="Structural observations"
    )
    boundaries: List[ConversationBoundary] = Field(
        default_factory=list,
        description="Detected boundaries"
    )
    total_segments: int = Field(
        description="Total number of input segments",
        gt=0
    )
    
    @field_validator('units')
    @classmethod
    def validate_units_coverage(cls, v: List[ConversationUnit]) -> List[ConversationUnit]:
        """Validate units don't overlap."""
        # Sort units by start index
        sorted_units = sorted(v, key=lambda u: u.start_index)
        
        # Check for overlaps
        for i in range(1, len(sorted_units)):
            prev_unit = sorted_units[i-1]
            curr_unit = sorted_units[i]
            if prev_unit.end_index >= curr_unit.start_index:
                raise ValueError(
                    f"Units overlap: unit ending at {prev_unit.end_index} "
                    f"overlaps with unit starting at {curr_unit.start_index}"
                )
        
        return v
    
    @field_validator('themes')
    @classmethod
    def validate_theme_unit_references(cls, v: List[ConversationTheme], values) -> List[ConversationTheme]:
        """Validate theme unit references are valid."""
        if 'units' in values.data:
            unit_count = len(values.data['units'])
            for theme in v:
                for unit_idx in theme.related_units:
                    if unit_idx >= unit_count:
                        raise ValueError(
                            f"Theme '{theme.theme}' references invalid unit index {unit_idx}"
                        )
        return v
    
    @field_validator('boundaries')
    @classmethod
    def validate_boundary_indices(cls, v: List[ConversationBoundary], values) -> List[ConversationBoundary]:
        """Validate boundary indices are within range."""
        if 'total_segments' in values.data:
            total = values.data['total_segments']
            for boundary in v:
                if boundary.segment_index >= total:
                    raise ValueError(
                        f"Boundary index {boundary.segment_index} exceeds total segments {total}"
                    )
        return v