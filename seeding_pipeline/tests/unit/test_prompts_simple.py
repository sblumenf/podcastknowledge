"""Unit tests for prompt management utilities - testing actual implementation."""

import pytest
from unittest.mock import Mock, patch

from src.extraction.prompts import (
    PromptVersion,
    PromptTemplate,
    PromptBuilder
)


class TestPromptVersion:
    """Test PromptVersion enum."""
    
    def test_prompt_version_values(self):
        """Test prompt version values."""
        assert PromptVersion.V1_0 == "1.0"
        assert PromptVersion.V1_1 == "1.1"
        assert PromptVersion.V2_0 == "2.0"
    
    def test_prompt_version_string_comparison(self):
        """Test that prompt versions can be compared as strings."""
        assert str(PromptVersion.V1_0) == "1.0"
        assert PromptVersion.V2_0.value == "2.0"


class TestPromptTemplate:
    """Test PromptTemplate dataclass."""
    
    def test_prompt_template_creation(self):
        """Test creating PromptTemplate."""
        template = PromptTemplate(
            name="test_prompt",
            version="1.0",
            template="Hello {name}, you are {age} years old.",
            variables=["name", "age"],
            description="Test greeting prompt"
        )
        
        assert template.name == "test_prompt"
        assert template.version == "1.0"
        assert template.variables == ["name", "age"]
        assert template.description == "Test greeting prompt"
        assert template.use_large_context is False
    
    def test_prompt_template_with_large_context(self):
        """Test PromptTemplate with large context flag."""
        template = PromptTemplate(
            name="large_prompt",
            version="2.0",
            template="Process this large text: {text}",
            variables=["text"],
            description="Large context prompt",
            use_large_context=True
        )
        
        assert template.use_large_context is True
    
    def test_prompt_template_format_success(self):
        """Test formatting template successfully."""
        template = PromptTemplate(
            name="test",
            version="1.0",
            template="Hello {name}, welcome to {place}!",
            variables=["name", "place"],
            description="Greeting"
        )
        
        result = template.format(name="Alice", place="Wonderland")
        assert result == "Hello Alice, welcome to Wonderland!"
    
    def test_prompt_template_format_missing_variables(self):
        """Test formatting with missing variables."""
        template = PromptTemplate(
            name="test",
            version="1.0",
            template="Hello {name}, you are {age} years old.",
            variables=["name", "age"],
            description="Test"
        )
        
        with pytest.raises(ValueError) as exc_info:
            template.format(name="Bob")  # Missing 'age'
        
        assert "Missing required variables: {'age'}" in str(exc_info.value)
    
    def test_prompt_template_format_extra_variables(self):
        """Test formatting with extra variables (should work)."""
        template = PromptTemplate(
            name="test",
            version="1.0",
            template="Hello {name}!",
            variables=["name"],
            description="Test"
        )
        
        # Extra variables should be ignored
        result = template.format(name="Charlie", age=25, extra="ignored")
        assert result == "Hello Charlie!"
    
    def test_prompt_template_format_key_error(self):
        """Test formatting with template referencing undefined variable."""
        template = PromptTemplate(
            name="test",
            version="1.0",
            template="Hello {name}, your ID is {undefined_var}!",
            variables=["name"],  # 'undefined_var' not in variables list
            description="Test"
        )
        
        with pytest.raises(ValueError) as exc_info:
            template.format(name="Dave")
        
        assert "Template formatting error" in str(exc_info.value)


class TestPromptBuilder:
    """Test PromptBuilder class."""
    
    def test_prompt_builder_initialization_default(self):
        """Test default PromptBuilder initialization."""
        builder = PromptBuilder()
        
        assert builder.use_large_context is True
        assert builder.version == PromptVersion.V2_0
        assert isinstance(builder._templates, dict)
        assert len(builder._templates) > 0
    
    def test_prompt_builder_initialization_small_context(self):
        """Test PromptBuilder with small context."""
        builder = PromptBuilder(use_large_context=False)
        
        assert builder.use_large_context is False
        assert builder.version == PromptVersion.V1_1
    
    def test_prompt_builder_template_initialization(self):
        """Test that standard templates are initialized."""
        builder = PromptBuilder()
        
        # Check for expected templates - based on what's actually in the code
        assert 'entity_extraction_large' in builder._templates
        template = builder._templates['entity_extraction_large']
        assert isinstance(template, PromptTemplate)
        assert template.name == 'entity_extraction_large'
        assert len(template.variables) > 0