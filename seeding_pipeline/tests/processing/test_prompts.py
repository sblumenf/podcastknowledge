"""
Tests for prompt management functionality
"""
from datetime import datetime

import pytest

from src.processing.prompts import PromptBuilder, PromptTemplate
class TestPromptTemplate:
    """Test suite for PromptTemplate class"""
    
    def test_prompt_template_creation(self):
        """Test creating a prompt template"""
        template = PromptTemplate(
            name="test_prompt",
            version="1.0",
            template="Hello {name}, today is {date}",
            variables=["name", "date"],
            description="Test prompt template",
            use_large_context=False
        )
        
        assert template.name == "test_prompt"
        assert template.version == "1.0"
        assert "Hello {name}" in template.template
        assert len(template.variables) == 2
        assert not template.use_large_context
    
    def test_prompt_template_format(self):
        """Test formatting a prompt template"""
        template = PromptTemplate(
            name="entity_prompt",
            version="1.0",
            template="Extract entities from: {text}\nTypes: {types}",
            variables=["text", "types"],
            description="Entity extraction prompt"
        )
        
        result = template.format(
            text="Apple announced new products",
            types="COMPANY, PRODUCT"
        )
        
        assert "Apple announced new products" in result
        assert "COMPANY, PRODUCT" in result
    
    def test_prompt_template_missing_variable(self):
        """Test formatting with missing variables"""
        template = PromptTemplate(
            name="test",
            version="1.0",
            template="Hello {name}",
            variables=["name"],
            description="Test"
        )
        
        with pytest.raises(KeyError):
            template.format()  # Missing 'name' variable


class TestPromptBuilder:
    """Test suite for PromptBuilder class"""
    
    @pytest.fixture
    def builder(self):
        """Create a PromptBuilder instance"""
        return PromptBuilder(use_large_context=True)
    
    def test_entity_extraction_prompt(self, builder):
        """Test entity extraction prompt generation"""
        text = "Google CEO Sundar Pichai announced new AI features"
        
        prompt = builder.build_entity_extraction_prompt(text)
        
        assert isinstance(prompt, str)
        assert text in prompt
        assert "Extract named entities" in prompt
        assert "Entity Types" in prompt
        assert "PERSON" in prompt
        assert "COMPANY" in prompt
        assert "TECHNOLOGY" in prompt
    
    def test_insight_extraction_prompt(self, builder):
        """Test insight extraction prompt generation"""
        text = "AI is transforming healthcare"
        entity_names = ["AI", "healthcare"]
        
        prompt = builder.build_insight_extraction_prompt(text, entity_names)
        
        assert isinstance(prompt, str)
        assert text in prompt
        assert "extract key insights" in prompt
        assert "AI" in prompt
        assert "healthcare" in prompt
        assert "actionable" in prompt
    
    def test_quote_extraction_prompt(self, builder):
        """Test quote extraction prompt generation"""
        text = '"This is revolutionary," said the CEO.'
        
        prompt = builder.build_quote_extraction_prompt(text)
        
        assert isinstance(prompt, str)
        assert text in prompt
        assert "Extract notable quotes" in prompt
        assert "speaker" in prompt.lower()
        assert "context" in prompt.lower()
    
    def test_topic_identification_prompt(self, builder):
        """Test topic identification prompt generation"""
        text = "Discussion about AI ethics and regulation"
        entities = ["AI", "ethics", "regulation"]
        insights = ["AI needs ethical guidelines", "Regulation is coming"]
        
        prompt = builder.build_topic_identification_prompt(text, entities, insights)
        
        assert isinstance(prompt, str)
        assert "identify the main topics" in prompt
        assert "AI" in prompt
        assert "ethics" in prompt
        assert len(insights) > 0  # Insights should be included
    
    def test_summary_generation_prompt(self, builder):
        """Test summary generation prompt"""
        transcript = "Long discussion about technology..."
        key_points = ["AI advancement", "Ethical concerns", "Future predictions"]
        
        prompt = builder.build_summary_prompt(transcript, key_points)
        
        assert isinstance(prompt, str)
        assert "comprehensive summary" in prompt
        assert transcript in prompt
        assert all(point in prompt for point in key_points)
    
    def test_relationship_extraction_prompt(self, builder):
        """Test relationship extraction prompt"""
        text = "Google acquired DeepMind to advance AI research"
        entities = ["Google", "DeepMind", "AI"]
        
        prompt = builder.build_relationship_extraction_prompt(text, entities)
        
        assert isinstance(prompt, str)
        assert "relationships between entities" in prompt
        assert all(entity in prompt for entity in entities)
        assert "type of relationship" in prompt
    
    def test_convert_transcript_for_llm(self, builder):
        """Test transcript conversion for LLM"""
        segments = [
            {"speaker": "Host", "text": "Welcome to the show"},
            {"speaker": "Guest", "text": "Thanks for having me"}
        ]
        
        result = builder.convert_transcript_for_llm(segments)
        
        assert isinstance(result, str)
        assert "Host:" in result
        assert "Guest:" in result
        assert "Welcome to the show" in result
        assert "Thanks for having me" in result
    
    def test_small_context_prompts(self):
        """Test prompts for small context window"""
        builder = PromptBuilder(use_large_context=False)
        text = "Short text for processing"
        
        entity_prompt = builder.build_entity_extraction_prompt(text)
        assert "Focus on" in entity_prompt or "most important" in entity_prompt
        
        insight_prompt = builder.build_insight_extraction_prompt(text, [])
        assert "key insights" in insight_prompt
        assert len(insight_prompt) < 2000  # Should be concise
    
    def test_prompt_versioning(self, builder):
        """Test prompt version tracking"""
        prompt = builder.build_entity_extraction_prompt("test")
        
        # Should include version info in prompt metadata
        version = builder.get_prompt_version("entity_extraction")
        assert version is not None
        assert isinstance(version, str)
    
    def test_custom_prompt_registration(self, builder):
        """Test registering custom prompts"""
        custom_template = PromptTemplate(
            name="custom_analysis",
            version="1.0",
            template="Analyze this: {content}",
            variables=["content"],
            description="Custom analysis prompt"
        )
        
        builder.register_prompt_template("custom", custom_template)
        
        # Should be able to use the custom prompt
        result = builder.build_custom_prompt("custom", content="test data")
        assert "Analyze this: test data" in result
    
    def test_prompt_caching(self, builder):
        """Test that prompts are cached appropriately"""
        text = "Same text for caching test"
        
        # First call
        prompt1 = builder.build_entity_extraction_prompt(text)
        
        # Second call with same text
        prompt2 = builder.build_entity_extraction_prompt(text)
        
        # Should return same prompt
        assert prompt1 == prompt2
    
    def test_context_aware_prompts(self, builder):
        """Test prompts that adapt to context"""
        # Medical context
        medical_text = "The patient showed symptoms of diabetes"
        prompt = builder.build_entity_extraction_prompt(
            medical_text,
            context_hints=["medical", "clinical"]
        )
        assert "medical" in prompt.lower() or "condition" in prompt.lower()
        
        # Tech context
        tech_text = "The new API uses REST architecture"
        prompt = builder.build_entity_extraction_prompt(
            tech_text,
            context_hints=["technology", "software"]
        )
        assert "technology" in prompt.lower() or "software" in prompt.lower()
    
    def test_prompt_metadata(self, builder):
        """Test prompt metadata generation"""
        metadata = builder.get_prompt_metadata()
        
        assert isinstance(metadata, dict)
        assert "version" in metadata
        assert "supported_prompts" in metadata
        assert len(metadata["supported_prompts"]) > 0
    
    def test_error_handling_prompts(self, builder):
        """Test prompts for error scenarios"""
        # Empty text
        prompt = builder.build_entity_extraction_prompt("")
        assert "text" in prompt.lower()
        
        # None values
        prompt = builder.build_insight_extraction_prompt("text", None)
        assert isinstance(prompt, str)
        
        # Invalid template name
        with pytest.raises(ValueError):
            builder.build_custom_prompt("nonexistent", content="test")