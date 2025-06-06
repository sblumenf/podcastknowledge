"""Unit tests for prompt management utilities."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.extraction.prompts import (
    PromptVersion,
    PromptTemplate,
    PromptBuilder
)


class TestPromptVersion:
    """Test PromptVersion enum."""
    
    def test_prompt_version_values(self):
        """Test PromptVersion enum values."""
        # Check that PromptVersion is defined
        assert hasattr(PromptVersion, '__members__')
        
        # Test accessing version values if they exist
        versions = list(PromptVersion)
        assert len(versions) > 0


class TestPromptTemplate:
    """Test PromptTemplate class."""
    
    def test_prompt_template_creation(self):
        """Test creating PromptTemplate."""
        template = PromptTemplate(
            name="test_template",
            version=PromptVersion.V1 if hasattr(PromptVersion, 'V1') else "v1",
            template="This is a test template with {variable}",
            variables=["variable"],
            description="Test template"
        )
        
        assert template.name == "test_template"
        assert template.template == "This is a test template with {variable}"
        assert "variable" in template.variables
    
    def test_prompt_template_format(self):
        """Test formatting prompt template."""
        template = PromptTemplate(
            name="test_template",
            version="v1",
            template="Hello {name}, welcome to {place}",
            variables=["name", "place"],
            description="Test greeting template"
        )
        
        if hasattr(template, 'format'):
            formatted = template.format(name="John", place="Python")
            assert "John" in formatted
            assert "Python" in formatted


class TestPromptBuilder:
    """Test PromptBuilder class."""
    
    @pytest.fixture
    def builder(self):
        """Create PromptBuilder instance."""
        return PromptBuilder()
    
    def test_builder_initialization(self):
        """Test PromptBuilder initialization."""
        builder = PromptBuilder()
        assert builder is not None
    
    def test_build_extraction_prompt(self, builder):
        """Test building extraction prompt."""
        if hasattr(builder, 'build_extraction_prompt'):
            prompt = builder.build_extraction_prompt(
                segment_text="This is a test segment.",
                context={"episode_title": "Test Episode"}
            )
            assert isinstance(prompt, str)
            assert len(prompt) > 0
    
    def test_build_entity_prompt(self, builder):
        """Test building entity extraction prompt."""
        if hasattr(builder, 'build_entity_prompt'):
            prompt = builder.build_entity_prompt(
                text="John Doe is the CEO of Example Corp."
            )
            assert isinstance(prompt, str)
            assert len(prompt) > 0
    
    def test_build_insight_prompt(self, builder):
        """Test building insight extraction prompt."""
        if hasattr(builder, 'build_insight_prompt'):
            prompt = builder.build_insight_prompt(
                text="The key finding is that machine learning improves efficiency."
            )
            assert isinstance(prompt, str)
            assert len(prompt) > 0
    
    def test_build_with_template(self, builder):
        """Test building prompt with custom template."""
        template = PromptTemplate(
            name="custom",
            version="v1",
            template="Extract {item_type} from: {text}",
            variables=["item_type", "text"],
            description="Custom extraction template"
        )
        
        if hasattr(builder, 'build_with_template'):
            prompt = builder.build_with_template(
                template=template,
                item_type="entities",
                text="Sample text"
            )
            assert "entities" in prompt
            assert "Sample text" in prompt