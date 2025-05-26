"""
Tests for metrics calculation functionality
"""
import pytest
from typing import List
from datetime import datetime

from src.core.models import (
    Entity, Insight, Quote, Episode, Segment,
    EntityType, InsightType, QuoteType, ComplexityLevel
)
from src.processing.metrics import (
    MetricsCalculator, ComplexityMetrics, 
    InformationDensityMetrics, AccessibilityMetrics
)


class TestMetricsCalculator:
    """Test suite for MetricsCalculator class"""
    
    @pytest.fixture
    def calculator(self):
        """Create a MetricsCalculator instance"""
        return MetricsCalculator()
    
    @pytest.fixture
    def sample_text(self):
        """Sample text for testing"""
        return """
        Artificial intelligence and machine learning are transforming 
        industries at an unprecedented pace. Complex algorithms analyze 
        vast datasets to extract meaningful patterns. These sophisticated 
        systems require substantial computational resources and expertise.
        """
    
    @pytest.fixture
    def simple_text(self):
        """Simple text for testing"""
        return "The cat sat on the mat. It was a sunny day. The bird sang a song."
    
    @pytest.fixture
    def sample_entities(self):
        """Sample entities for testing"""
        return [
            Entity(
                name="Artificial Intelligence",
                type=EntityType.CONCEPT,
                confidence=0.9,
                description="Advanced computational technology",
                wikipedia_url="https://en.wikipedia.org/wiki/Artificial_intelligence"
            ),
            Entity(
                name="Machine Learning",
                type=EntityType.TECHNOLOGY,
                confidence=0.85,
                description="Subset of AI",
                wikipedia_url="https://en.wikipedia.org/wiki/Machine_learning"
            )
        ]
    
    @pytest.fixture
    def sample_insights(self):
        """Sample insights for testing"""
        return [
            Insight(
                content="AI is revolutionizing multiple industries",
                type=InsightType.TREND,
                confidence=0.8,
                context="Technology adoption",
                segment_indices=[0, 1]
            ),
            Insight(
                content="Complex algorithms require significant resources",
                type=InsightType.TECHNICAL_DETAIL,
                confidence=0.7,
                context="Infrastructure requirements",
                segment_indices=[2]
            )
        ]
    
    @pytest.fixture
    def sample_quotes(self):
        """Sample quotes for testing"""
        return [
            Quote(
                text="transforming industries at an unprecedented pace",
                speaker="Host",
                timestamp="00:01:30",
                context="AI impact discussion",
                type=QuoteType.INSIGHT
            )
        ]
    
    def test_calculate_complexity_simple_text(self, calculator, simple_text):
        """Test complexity calculation with simple text"""
        metrics = calculator.calculate_complexity(simple_text)
        
        assert isinstance(metrics, ComplexityMetrics)
        assert metrics.level == ComplexityLevel.SIMPLE
        assert metrics.avg_sentence_length < 10
        assert metrics.vocabulary_richness < 0.8
        assert metrics.technical_term_density == 0.0
        assert metrics.readability_score > 80
    
    def test_calculate_complexity_complex_text(self, calculator, sample_text, sample_entities):
        """Test complexity calculation with complex text"""
        metrics = calculator.calculate_complexity(sample_text, sample_entities)
        
        assert isinstance(metrics, ComplexityMetrics)
        assert metrics.level in [ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX]
        assert metrics.avg_sentence_length > 10
        assert metrics.vocabulary_richness > 0.5
        assert metrics.technical_term_density > 0
        assert metrics.entity_complexity_score > 0
    
    def test_calculate_complexity_empty_text(self, calculator):
        """Test complexity calculation with empty text"""
        metrics = calculator.calculate_complexity("")
        
        assert metrics.level == ComplexityLevel.SIMPLE
        assert metrics.avg_sentence_length == 0
        assert metrics.vocabulary_richness == 0
        assert metrics.readability_score == 100
    
    def test_calculate_information_density(
        self, calculator, sample_text, sample_insights, 
        sample_entities, sample_quotes
    ):
        """Test information density calculation"""
        word_count = len(sample_text.split())
        metrics = calculator.calculate_information_density(
            word_count, sample_insights, sample_entities, sample_quotes
        )
        
        assert isinstance(metrics, InformationDensityMetrics)
        assert metrics.insights_per_1000_words > 0
        assert metrics.entities_per_1000_words > 0
        assert metrics.quotes_per_1000_words > 0
        assert metrics.fact_density > 0
        assert metrics.unique_concepts_ratio > 0
        assert 0 <= metrics.overall_density <= 1
    
    def test_calculate_information_density_empty_lists(self, calculator):
        """Test information density with empty lists"""
        metrics = calculator.calculate_information_density(1000, [], [], [])
        
        assert metrics.insights_per_1000_words == 0
        assert metrics.entities_per_1000_words == 0
        assert metrics.quotes_per_1000_words == 0
        assert metrics.fact_density == 0
        assert metrics.unique_concepts_ratio == 0
        assert metrics.overall_density == 0
    
    def test_calculate_information_density_zero_words(self, calculator, sample_insights):
        """Test information density with zero word count"""
        metrics = calculator.calculate_information_density(0, sample_insights, [], [])
        
        assert metrics.insights_per_1000_words == 0
        assert metrics.overall_density == 0
    
    def test_calculate_accessibility(
        self, calculator, sample_text, sample_insights, sample_quotes
    ):
        """Test accessibility calculation"""
        metrics = calculator.calculate_accessibility(
            sample_text, sample_insights, sample_quotes
        )
        
        assert isinstance(metrics, AccessibilityMetrics)
        assert 0 <= metrics.explanation_coverage <= 1
        assert metrics.context_availability > 0
        assert metrics.quote_accessibility > 0
        assert 0 <= metrics.overall_accessibility <= 1
    
    def test_calculate_accessibility_empty_inputs(self, calculator, sample_text):
        """Test accessibility with empty insights and quotes"""
        metrics = calculator.calculate_accessibility(sample_text, [], [])
        
        assert metrics.explanation_coverage == 0
        assert metrics.context_availability == 0
        assert metrics.quote_accessibility == 0
        assert metrics.overall_accessibility > 0  # Still based on text readability
    
    def test_calculate_episode_metrics(self, calculator, sample_entities, sample_insights, sample_quotes):
        """Test episode-level metrics calculation"""
        # Create sample segments
        segments = [
            Segment(
                start_time=0.0,
                end_time=60.0,
                speaker="Host",
                text="First segment about AI and ML.",
                entities=sample_entities[:1],
                insights=sample_insights[:1],
                quotes=[]
            ),
            Segment(
                start_time=60.0,
                end_time=120.0,
                speaker="Guest",
                text="Second segment discussing applications.",
                entities=sample_entities[1:],
                insights=sample_insights[1:],
                quotes=sample_quotes
            )
        ]
        
        # Create episode
        episode = Episode(
            title="AI Discussion",
            description="A deep dive into AI",
            audio_url="http://example.com/audio.mp3",
            publication_date=datetime.now(),
            duration=120,
            segments=segments,
            entities=sample_entities,
            insights=sample_insights,
            quotes=sample_quotes,
            key_topics=["AI", "Machine Learning"],
            episode_number=1,
            transcript="Full transcript here"
        )
        
        # Calculate metrics
        complexity, density, accessibility = calculator.calculate_episode_metrics(episode)
        
        # Verify all metrics are calculated
        assert isinstance(complexity, ComplexityMetrics)
        assert isinstance(density, InformationDensityMetrics)
        assert isinstance(accessibility, AccessibilityMetrics)
        
        # Verify metrics have reasonable values
        assert complexity.level in ComplexityLevel
        assert density.overall_density >= 0
        assert 0 <= accessibility.overall_accessibility <= 1
    
    def test_technical_term_detection(self, calculator):
        """Test technical term detection in complexity calculation"""
        technical_text = """
        The convolutional neural network uses backpropagation 
        with stochastic gradient descent optimization. The 
        algorithm implements dropout regularization and batch 
        normalization techniques.
        """
        
        metrics = calculator.calculate_complexity(technical_text)
        
        assert metrics.technical_term_density > 0.2
        assert metrics.level in [ComplexityLevel.COMPLEX, ComplexityLevel.VERY_COMPLEX]
    
    def test_readability_score_calculation(self, calculator):
        """Test readability score calculation"""
        # Very simple text should have high readability
        simple = "I like dogs. Dogs are fun. Cats are nice too."
        simple_metrics = calculator.calculate_complexity(simple)
        assert simple_metrics.readability_score > 90
        
        # Complex text should have lower readability
        complex_text = """
        The epistemological ramifications of quantum mechanical 
        interpretations necessitate a paradigmatic reconsideration 
        of ontological commitments within contemporary philosophical 
        discourse.
        """
        complex_metrics = calculator.calculate_complexity(complex_text)
        assert complex_metrics.readability_score < 30
    
    def test_entity_complexity_scoring(self, calculator, sample_text):
        """Test entity complexity scoring"""
        # Simple entities
        simple_entities = [
            Entity(name="Dog", type=EntityType.CONCEPT, confidence=0.9),
            Entity(name="Cat", type=EntityType.CONCEPT, confidence=0.8)
        ]
        
        # Complex entities
        complex_entities = [
            Entity(
                name="Quantum Entanglement",
                type=EntityType.CONCEPT,
                confidence=0.9,
                description="Complex quantum phenomenon"
            ),
            Entity(
                name="CRISPR-Cas9",
                type=EntityType.TECHNOLOGY,
                confidence=0.85,
                description="Gene editing technology"
            )
        ]
        
        simple_metrics = calculator.calculate_complexity(sample_text, simple_entities)
        complex_metrics = calculator.calculate_complexity(sample_text, complex_entities)
        
        assert complex_metrics.entity_complexity_score > simple_metrics.entity_complexity_score
    
    def test_insight_type_density(self, calculator):
        """Test that different insight types contribute to density"""
        insights_technical = [
            Insight(
                content="Technical detail",
                type=InsightType.TECHNICAL_DETAIL,
                confidence=0.8
            )
        ]
        
        insights_trend = [
            Insight(
                content="Industry trend",
                type=InsightType.TREND,
                confidence=0.9
            )
        ]
        
        density_technical = calculator.calculate_information_density(
            1000, insights_technical, [], []
        )
        density_trend = calculator.calculate_information_density(
            1000, insights_trend, [], []
        )
        
        # Both should contribute to density
        assert density_technical.fact_density > 0
        assert density_trend.fact_density > 0
    
    def test_vocabulary_richness_edge_cases(self, calculator):
        """Test vocabulary richness calculation edge cases"""
        # Repeated words should have low richness
        repeated = "test test test test test"
        metrics_repeated = calculator.calculate_complexity(repeated)
        assert metrics_repeated.vocabulary_richness < 0.3
        
        # Unique words should have high richness
        unique = "apple banana cherry date elderberry"
        metrics_unique = calculator.calculate_complexity(unique)
        assert metrics_unique.vocabulary_richness == 1.0
    
    def test_metrics_with_special_characters(self, calculator):
        """Test metrics calculation with special characters"""
        text_with_special = """
        The @AI system uses #MachineLearning! 
        Check out https://example.com for more info :)
        Email: test@example.com
        """
        
        metrics = calculator.calculate_complexity(text_with_special)
        
        # Should handle special characters gracefully
        assert metrics.avg_sentence_length > 0
        assert metrics.vocabulary_richness > 0
        assert isinstance(metrics.level, ComplexityLevel)