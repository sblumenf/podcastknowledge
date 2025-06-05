"""Comprehensive unit tests for prompt management utilities."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.extraction.prompts import (
    PromptVersion,
    PromptTemplate,
    PromptBuilder,
    PromptOptimizer,
    PromptMetrics,
    PromptVariant
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
        
        # Check for expected templates
        expected_templates = [
            'entity_extraction_large',
            'entity_extraction_small',
            'insight_generation_large',
            'insight_generation_small',
            'quote_extraction',
            'complexity_analysis',
            'summary_generation'
        ]
        
        for template_name in expected_templates:
            assert template_name in builder._templates
            template = builder._templates[template_name]
            assert isinstance(template, PromptTemplate)
            assert template.name == template_name
            assert len(template.variables) > 0
    
    def test_build_entity_extraction_prompt_large_context(self):
        """Test building entity extraction prompt for large context."""
        builder = PromptBuilder(use_large_context=True)
        
        prompt = builder.build_entity_extraction_prompt("Test transcript text")
        
        assert isinstance(prompt, str)
        assert "Test transcript text" in prompt
        assert "1M token context window" in prompt  # Large context marker
        assert "Entity Types to Extract:" in prompt
    
    def test_build_entity_extraction_prompt_small_context(self):
        """Test building entity extraction prompt for small context."""
        builder = PromptBuilder(use_large_context=False)
        
        prompt = builder.build_entity_extraction_prompt("Test transcript text")
        
        assert isinstance(prompt, str)
        assert "Test transcript text" in prompt
        assert "1M token context window" not in prompt
        assert "Entity Types to Extract:" in prompt
    
    def test_build_insight_generation_prompt(self):
        """Test building insight generation prompt."""
        builder = PromptBuilder()
        
        entities = [
            {"name": "Entity1", "type": "PERSON"},
            {"name": "Entity2", "type": "ORGANIZATION"}
        ]
        
        prompt = builder.build_insight_generation_prompt("Test text", entities)
        
        assert isinstance(prompt, str)
        assert "Test text" in prompt
        assert "Entity1" in prompt
        assert "Entity2" in prompt
    
    def test_build_quote_extraction_prompt(self):
        """Test building quote extraction prompt."""
        builder = PromptBuilder()
        
        prompt = builder.build_quote_extraction_prompt("Test transcript with quotes")
        
        assert isinstance(prompt, str)
        assert "Test transcript with quotes" in prompt
        assert "quotable moments" in prompt.lower()
    
    def test_build_complexity_analysis_prompt(self):
        """Test building complexity analysis prompt."""
        builder = PromptBuilder()
        
        prompt = builder.build_complexity_analysis_prompt("Technical text to analyze")
        
        assert isinstance(prompt, str)
        assert "Technical text to analyze" in prompt
        assert "complexity" in prompt.lower()
    
    def test_build_summary_prompt(self):
        """Test building summary generation prompt."""
        builder = PromptBuilder()
        
        insights = [
            {"title": "Insight 1", "description": "Description 1"},
            {"title": "Insight 2", "description": "Description 2"}
        ]
        
        prompt = builder.build_summary_prompt("Test text", insights, max_length=500)
        
        assert isinstance(prompt, str)
        assert "Test text" in prompt
        assert "500" in prompt
        assert "Insight 1" in prompt
        assert "Insight 2" in prompt
    
    def test_build_follow_up_prompt(self):
        """Test building follow-up prompt."""
        builder = PromptBuilder()
        
        prompt = builder.build_follow_up_prompt(
            original_prompt="Original question",
            response="Initial response",
            follow_up="Please clarify X"
        )
        
        assert isinstance(prompt, str)
        assert "Original question" in prompt
        assert "Initial response" in prompt
        assert "Please clarify X" in prompt
    
    def test_get_template(self):
        """Test getting a specific template."""
        builder = PromptBuilder()
        
        template = builder.get_template('entity_extraction_large')
        
        assert isinstance(template, PromptTemplate)
        assert template.name == 'entity_extraction_large'
    
    def test_get_template_not_found(self):
        """Test getting non-existent template."""
        builder = PromptBuilder()
        
        template = builder.get_template('non_existent_template')
        
        assert template is None
    
    def test_add_custom_template(self):
        """Test adding custom template."""
        builder = PromptBuilder()
        
        custom_template = PromptTemplate(
            name="custom_prompt",
            version="1.0",
            template="Custom: {input}",
            variables=["input"],
            description="Custom prompt for testing"
        )
        
        builder.add_custom_template(custom_template)
        
        assert "custom_prompt" in builder._templates
        assert builder.get_template("custom_prompt") == custom_template
    
    def test_add_custom_template_override_warning(self):
        """Test warning when overriding existing template."""
        builder = PromptBuilder()
        
        existing_name = list(builder._templates.keys())[0]
        custom_template = PromptTemplate(
            name=existing_name,
            version="1.0",
            template="Override",
            variables=[],
            description="Override"
        )
        
        with patch('src.extraction.prompts.logger') as mock_logger:
            builder.add_custom_template(custom_template)
            
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert existing_name in warning_msg


class TestPromptOptimizer:
    """Test PromptOptimizer class."""
    
    def test_prompt_optimizer_initialization(self):
        """Test PromptOptimizer initialization."""
        optimizer = PromptOptimizer()
        
        assert hasattr(optimizer, 'metrics_history')
        assert hasattr(optimizer, 'variant_performance')
        assert len(optimizer.metrics_history) == 0
        assert len(optimizer.variant_performance) == 0
    
    def test_track_prompt_performance(self):
        """Test tracking prompt performance."""
        optimizer = PromptOptimizer()
        
        metrics = PromptMetrics(
            prompt_name="test_prompt",
            version="1.0",
            tokens_used=100,
            response_time=1.5,
            success_rate=0.95,
            quality_score=0.85
        )
        
        optimizer.track_prompt_performance(metrics)
        
        assert len(optimizer.metrics_history) == 1
        assert optimizer.metrics_history[0] == metrics
    
    def test_optimize_prompt_template(self):
        """Test optimizing prompt template."""
        optimizer = PromptOptimizer()
        
        # Add some performance data
        for i in range(5):
            metrics = PromptMetrics(
                prompt_name="test_prompt",
                version="1.0",
                tokens_used=100 + i * 10,
                response_time=1.0 + i * 0.1,
                success_rate=0.9,
                quality_score=0.8
            )
            optimizer.track_prompt_performance(metrics)
        
        original_template = PromptTemplate(
            name="test_prompt",
            version="1.0",
            template="Original prompt: {text}",
            variables=["text"],
            description="Test"
        )
        
        optimized = optimizer.optimize_prompt_template(original_template)
        
        # Should return an optimized version (or same if no optimization needed)
        assert isinstance(optimized, PromptTemplate)
        assert optimized.name == original_template.name
    
    def test_suggest_prompt_improvements(self):
        """Test suggesting prompt improvements."""
        optimizer = PromptOptimizer()
        
        # Add varied performance data
        good_metrics = PromptMetrics(
            prompt_name="good_prompt",
            version="1.0",
            tokens_used=50,
            response_time=0.5,
            success_rate=0.98,
            quality_score=0.95
        )
        
        poor_metrics = PromptMetrics(
            prompt_name="poor_prompt",
            version="1.0",
            tokens_used=500,
            response_time=5.0,
            success_rate=0.6,
            quality_score=0.5
        )
        
        optimizer.track_prompt_performance(good_metrics)
        optimizer.track_prompt_performance(poor_metrics)
        
        suggestions = optimizer.suggest_prompt_improvements()
        
        assert isinstance(suggestions, list)
        assert any("poor_prompt" in s for s in suggestions)
    
    def test_compare_prompt_variants(self):
        """Test comparing prompt variants."""
        optimizer = PromptOptimizer()
        
        variants = [
            PromptVariant(
                name="variant_a",
                template="Variant A: {text}",
                test_cases=["test1", "test2"]
            ),
            PromptVariant(
                name="variant_b",
                template="Variant B: {text}",
                test_cases=["test1", "test2"]
            )
        ]
        
        # Mock evaluation function
        def mock_evaluator(prompt, test_case):
            # Variant A performs better
            if "Variant A" in prompt:
                return {"score": 0.9, "time": 0.5}
            else:
                return {"score": 0.7, "time": 1.0}
        
        results = optimizer.compare_prompt_variants(variants, mock_evaluator)
        
        assert "variant_a" in results
        assert "variant_b" in results
        assert results["variant_a"]["avg_score"] > results["variant_b"]["avg_score"]


class TestPromptMetrics:
    """Test PromptMetrics dataclass."""
    
    def test_prompt_metrics_creation(self):
        """Test creating PromptMetrics."""
        metrics = PromptMetrics(
            prompt_name="test_prompt",
            version="1.0",
            tokens_used=150,
            response_time=2.5,
            success_rate=0.9,
            quality_score=0.85
        )
        
        assert metrics.prompt_name == "test_prompt"
        assert metrics.version == "1.0"
        assert metrics.tokens_used == 150
        assert metrics.response_time == 2.5
        assert metrics.success_rate == 0.9
        assert metrics.quality_score == 0.85
        assert metrics.timestamp != ""
    
    def test_prompt_metrics_auto_timestamp(self):
        """Test automatic timestamp generation."""
        metrics = PromptMetrics(
            prompt_name="test",
            version="1.0",
            tokens_used=100,
            response_time=1.0
        )
        
        # Should have auto-generated timestamp
        assert metrics.timestamp
        datetime.fromisoformat(metrics.timestamp)
    
    def test_prompt_metrics_to_dict(self):
        """Test converting metrics to dictionary."""
        metrics = PromptMetrics(
            prompt_name="test",
            version="1.0",
            tokens_used=100,
            response_time=1.0,
            success_rate=0.95,
            quality_score=0.9,
            metadata={"model": "gpt-4"}
        )
        
        result = metrics.to_dict()
        
        assert result["prompt_name"] == "test"
        assert result["version"] == "1.0"
        assert result["tokens_used"] == 100
        assert result["metadata"]["model"] == "gpt-4"


class TestPromptVariant:
    """Test PromptVariant dataclass."""
    
    def test_prompt_variant_creation(self):
        """Test creating PromptVariant."""
        variant = PromptVariant(
            name="test_variant",
            template="Test template: {input}",
            test_cases=["case1", "case2", "case3"]
        )
        
        assert variant.name == "test_variant"
        assert variant.template == "Test template: {input}"
        assert len(variant.test_cases) == 3
        assert variant.performance_data == {}
    
    def test_prompt_variant_with_performance_data(self):
        """Test PromptVariant with performance data."""
        variant = PromptVariant(
            name="test_variant",
            template="Template",
            test_cases=["test"],
            performance_data={"avg_score": 0.85, "avg_time": 1.2}
        )
        
        assert variant.performance_data["avg_score"] == 0.85
        assert variant.performance_data["avg_time"] == 1.2