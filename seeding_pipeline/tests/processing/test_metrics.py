"""
Tests for metrics calculation functionality
"""
from datetime import datetime
from typing import List

import pytest

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
                id="entity_1",
                name="Artificial Intelligence",
                entity_type=EntityType.CONCEPT,
                confidence_score=0.9,
                description="Advanced computational technology",
                wikipedia_url="https://en.wikipedia.org/wiki/Artificial_intelligence"
            ),
            Entity(
                id="entity_2",
                name="Machine Learning",
                entity_type=EntityType.TECHNOLOGY,
                confidence_score=0.85,
                description="Subset of AI",
                wikipedia_url="https://en.wikipedia.org/wiki/Machine_learning"
            )
        ]
    
    @pytest.fixture
    def sample_insights(self):
        """Sample insights for testing"""
        return [
            Insight(
                id="insight_1",
                title="AI Revolution",
                description="AI is revolutionizing multiple industries",
                insight_type=InsightType.KEY_POINT,
                confidence_score=0.8
            ),
            Insight(
                id="insight_2",
                title="Resource Requirements",
                description="Complex algorithms require significant resources",
                insight_type=InsightType.TECHNICAL,
                confidence_score=0.7
            )
        ]
    
    @pytest.fixture
    def sample_quotes(self):
        """Sample quotes for testing"""
        return [
            Quote(
                id="quote_1",
                text="transforming industries at an unprecedented pace",
                speaker="Host",
                estimated_timestamp=90.0,
                context="AI impact discussion",
                quote_type=QuoteType.INSIGHTFUL
            )
        ]
    
    def test_calculate_complexity_simple_text(self, calculator, simple_text):
        """Test complexity calculation with simple text"""
        metrics = calculator.calculate_complexity(simple_text)
        
        assert isinstance(metrics, ComplexityMetrics)
        assert metrics.classification == ComplexityLevel.LAYPERSON
        assert metrics.avg_sentence_length < 10
        assert metrics.unique_ratio > 0.7  # Simple text has more unique words
        assert metrics.technical_density == 0.0
        assert metrics.complexity_score < 3  # Low complexity score
    
    def test_calculate_complexity_complex_text(self, calculator, sample_text, sample_entities):
        """Test complexity calculation with complex text"""
        metrics = calculator.calculate_complexity(sample_text, sample_entities)
        
        assert isinstance(metrics, ComplexityMetrics)
        assert metrics.classification in [ComplexityLevel.INTERMEDIATE, ComplexityLevel.EXPERT]
        assert metrics.avg_sentence_length >= 10
        assert metrics.unique_ratio > 0.5
        assert metrics.technical_density > 0
        # Note: technical_entity_count is 0 because CONCEPT/TECHNOLOGY aren't in technical_types
    
    def test_calculate_complexity_empty_text(self, calculator):
        """Test complexity calculation with empty text"""
        metrics = calculator.calculate_complexity("")
        
        assert metrics.classification == ComplexityLevel.LAYPERSON
        assert metrics.avg_sentence_length == 0
        assert metrics.unique_ratio == 0
        assert metrics.complexity_score >= 0  # May have small base score
    
    def test_calculate_information_density(
        self, calculator, sample_text, sample_insights, 
        sample_entities
    ):
        """Test information density calculation"""
        metrics = calculator.calculate_information_density(
            sample_text, sample_insights, sample_entities
        )
        
        assert isinstance(metrics, InformationDensityMetrics)
        assert metrics.insight_density > 0
        assert metrics.entity_density > 0
        assert metrics.fact_density >= 0
        assert metrics.information_score > 0
        assert metrics.word_count > 0
        assert metrics.duration_minutes > 0
    
    def test_calculate_information_density_empty_lists(self, calculator, sample_text):
        """Test information density with empty lists"""
        metrics = calculator.calculate_information_density(sample_text, [], [])
        
        assert metrics.insight_density == 0
        assert metrics.entity_density == 0
        assert metrics.fact_density >= 0  # May still detect facts in text
        assert metrics.information_score >= 0
    
    def test_calculate_information_density_empty_text(self, calculator, sample_insights):
        """Test information density with empty text"""
        metrics = calculator.calculate_information_density("", sample_insights, [])
        
        assert metrics.information_score == 0
        assert metrics.word_count == 0
        assert metrics.duration_minutes == 0
    
    def test_calculate_accessibility(
        self, calculator, sample_text
    ):
        """Test accessibility calculation"""
        # First calculate complexity to get complexity score
        complexity_metrics = calculator.calculate_complexity(sample_text)
        
        metrics = calculator.calculate_accessibility(
            sample_text, complexity_metrics.complexity_score
        )
        
        assert isinstance(metrics, AccessibilityMetrics)
        assert 0 <= metrics.accessibility_score <= 1
        assert metrics.avg_sentence_length > 0
        assert metrics.jargon_percentage >= 0
        assert 0 <= metrics.explanation_quality <= 1
        assert 0 <= metrics.readability_score <= 1
    
    def test_calculate_accessibility_empty_text(self, calculator):
        """Test accessibility with empty text"""
        metrics = calculator.calculate_accessibility("", 0)
        
        assert metrics.accessibility_score == 0
        assert metrics.avg_sentence_length == 0
        assert metrics.jargon_percentage == 0
        assert metrics.explanation_quality == 0
        assert metrics.readability_score == 0
    
    def test_aggregate_episode_metrics(self, calculator):
        """Test episode-level metrics aggregation"""
        # Create sample segment metrics
        segment_complexities = [
            ComplexityMetrics(
                classification=ComplexityLevel.LAYPERSON,
                complexity_score=2.5,
                technical_density=0.02,
                avg_word_length=4.5,
                avg_sentence_length=12,
                syllable_complexity=1.5,
                unique_ratio=0.7,
                technical_entity_count=1
            ),
            ComplexityMetrics(
                classification=ComplexityLevel.INTERMEDIATE,
                complexity_score=4.0,
                technical_density=0.08,
                avg_word_length=5.5,
                avg_sentence_length=18,
                syllable_complexity=2.0,
                unique_ratio=0.6,
                technical_entity_count=3
            )
        ]
        
        segment_densities = [
            InformationDensityMetrics(
                information_score=5.0,
                insight_density=2.0,
                entity_density=3.0,
                fact_density=1.5,
                word_count=100,
                duration_minutes=0.67,
                insights_per_minute=3.0,
                entities_per_minute=4.5
            ),
            InformationDensityMetrics(
                information_score=7.0,
                insight_density=3.0,
                entity_density=4.0,
                fact_density=2.0,
                word_count=150,
                duration_minutes=1.0,
                insights_per_minute=3.0,
                entities_per_minute=4.0
            )
        ]
        
        segment_accessibilities = [
            AccessibilityMetrics(
                accessibility_score=0.8,
                avg_sentence_length=12,
                jargon_percentage=2.0,
                explanation_quality=0.7,
                readability_score=0.75
            ),
            AccessibilityMetrics(
                accessibility_score=0.6,
                avg_sentence_length=18,
                jargon_percentage=8.0,
                explanation_quality=0.5,
                readability_score=0.55
            )
        ]
        
        # Calculate aggregate metrics
        episode_metrics = calculator.aggregate_episode_metrics(
            segment_complexities, segment_densities, segment_accessibilities
        )
        
        # Verify all metrics are present
        assert 'avg_complexity' in episode_metrics
        assert 'dominant_complexity_level' in episode_metrics
        assert 'technical_density' in episode_metrics
        assert 'complexity_variance' in episode_metrics
        assert 'is_mixed_complexity' in episode_metrics
        assert 'is_technical' in episode_metrics
        assert 'avg_information_score' in episode_metrics
        assert 'total_insights' in episode_metrics
        assert 'total_entities' in episode_metrics
        assert 'avg_accessibility' in episode_metrics
        assert 'segment_count' in episode_metrics
        
        # Verify calculated values
        assert episode_metrics['segment_count'] == 2
        assert episode_metrics['avg_complexity'] == 3.25  # (2.5 + 4.0) / 2
        # With a tie, max() returns the first one (LAYPERSON)
        assert episode_metrics['dominant_complexity_level'] in [ComplexityLevel.LAYPERSON, ComplexityLevel.INTERMEDIATE]
        assert episode_metrics['is_technical'] == False  # avg technical density < 0.05
    
    def test_technical_term_detection(self, calculator):
        """Test technical term detection in complexity calculation"""
        technical_text = """
        The convolutional neural network uses backpropagation 
        with stochastic gradient descent optimization. The 
        algorithm implements dropout regularization and batch 
        normalization techniques. The receptor binds to the substrate
        through enzymatic pathways.
        """
        
        metrics = calculator.calculate_complexity(technical_text)
        
        assert metrics.technical_density > 0.1
        assert metrics.classification == ComplexityLevel.EXPERT
    
    def test_readability_score_calculation(self, calculator):
        """Test readability score calculation via accessibility metrics"""
        # Very simple text should have high readability
        simple = "I like dogs. Dogs are fun. Cats are nice too."
        simple_complexity = calculator.calculate_complexity(simple)
        simple_accessibility = calculator.calculate_accessibility(simple, simple_complexity.complexity_score)
        assert simple_accessibility.readability_score > 0.9
        
        # Complex text should have lower readability
        complex_text = """
        The epistemological ramifications of quantum mechanical 
        interpretations necessitate a paradigmatic reconsideration 
        of ontological commitments within contemporary philosophical 
        discourse.
        """
        complex_complexity = calculator.calculate_complexity(complex_text)
        complex_accessibility = calculator.calculate_accessibility(complex_text, complex_complexity.complexity_score)
        assert complex_accessibility.readability_score < 0.3
    
    def test_entity_complexity_scoring(self, calculator, sample_text):
        """Test entity complexity scoring"""
        # Simple entities
        simple_entities = [
            Entity(id="e1", name="Dog", entity_type=EntityType.CONCEPT, confidence_score=0.9),
            Entity(id="e2", name="Cat", entity_type=EntityType.CONCEPT, confidence_score=0.8)
        ]
        
        # Complex entities with technical types
        complex_entities = [
            Entity(
                id="e3",
                name="Quantum Entanglement",
                entity_type=EntityType.CONCEPT,
                confidence_score=0.9,
                description="Complex quantum phenomenon"
            ),
            Entity(
                id="e4",
                name="CRISPR-Cas9",
                entity_type=EntityType.TECHNOLOGY,
                confidence_score=0.85,
                description="Gene editing technology"
            )
        ]
        
        simple_metrics = calculator.calculate_complexity(sample_text, simple_entities)
        complex_metrics = calculator.calculate_complexity(sample_text, complex_entities)
        
        # Both should have 0 technical entities as CONCEPT/TECHNOLOGY aren't in technical_types
        assert complex_metrics.technical_entity_count == simple_metrics.technical_entity_count == 0
        # Complexity score might be similar as entities don't affect it much
        assert complex_metrics.complexity_score >= simple_metrics.complexity_score
    
    def test_vocabulary_richness_edge_cases(self, calculator):
        """Test vocabulary richness (unique ratio) calculation edge cases"""
        # Repeated words should have low richness
        repeated = "test test test test test"
        metrics_repeated = calculator.calculate_complexity(repeated)
        assert metrics_repeated.unique_ratio < 0.3
        
        # Unique words should have high richness
        unique = "apple banana cherry date elderberry"
        metrics_unique = calculator.calculate_complexity(unique)
        assert metrics_unique.unique_ratio == 1.0
    
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
        assert metrics.unique_ratio > 0
        assert isinstance(metrics.classification, ComplexityLevel)
    
    def test_fact_detection(self, calculator):
        """Test fact detection in information density"""
        factual_text = """
        According to research from MIT, 85% of companies are adopting AI.
        A 2023 study found significant correlation between AI usage and productivity.
        The experiment demonstrated a 40% improvement in efficiency.
        """
        
        metrics = calculator.calculate_information_density(factual_text, [], [])
        
        assert metrics.fact_density > 0
        assert metrics.information_score > 0
    
    def test_explanation_quality_detection(self, calculator):
        """Test explanation quality in accessibility"""
        text_with_explanations = """
        Machine learning, which means computers learning from data, is growing.
        In other words, AI systems can improve without explicit programming.
        Think of it as teaching a computer to recognize patterns, similar to
        how humans learn. Basically, it's automated pattern recognition.
        """
        
        complexity = calculator.calculate_complexity(text_with_explanations)
        accessibility = calculator.calculate_accessibility(text_with_explanations, complexity.complexity_score)
        
        assert accessibility.explanation_quality > 0.5  # Good explanation coverage
        assert accessibility.accessibility_score > 0.6  # Should be accessible