"""
Tests for complexity analysis functionality
"""
from typing import List

import pytest

from src.core.extraction_interface import Entity, Insight, Quote, EntityType, InsightType, QuoteType, ComplexityLevel
from src.extraction.complexity_analysis import (
    ComplexityAnalyzer, VocabularyMetrics, SegmentComplexity, 
    EpisodeComplexity
)


class TestComplexityAnalyzer:
    """Test suite for ComplexityAnalyzer class"""
    
    @pytest.fixture
    def analyzer(self):
        """Create a ComplexityAnalyzer instance"""
        return ComplexityAnalyzer()
    
    @pytest.fixture
    def simple_text(self):
        """Simple text sample"""
        return "The cat sat on the mat. The dog ran fast. It was a nice day."
    
    @pytest.fixture
    def complex_text(self):
        """Complex technical text sample"""
        return """
        The implementation of quantum computing algorithms necessitates a 
        comprehensive understanding of superposition and entanglement phenomena. 
        These fundamental quantum mechanical principles enable exponential 
        computational advantages for specific problem domains, particularly 
        in cryptographic applications and optimization scenarios.
        """
    
    @pytest.fixture
    def medical_text(self):
        """Medical domain text"""
        return """
        The patient presented with acute myocardial infarction characterized 
        by elevated troponin levels and ST-segment elevation on the 
        electrocardiogram. Immediate percutaneous coronary intervention was 
        indicated for revascularization of the occluded vessel.
        """
    
    @pytest.fixture
    def sample_entities(self):
        """Sample entities for testing"""
        return [
            Entity(name="quantum computing", type=EntityType.CONCEPT, confidence=0.9),
            Entity(name="superposition", type=EntityType.SCIENTIFIC_THEORY, confidence=0.85),
            Entity(name="entanglement", type=EntityType.SCIENTIFIC_THEORY, confidence=0.85)
        ]
    
    @pytest.fixture
    def sample_insights(self):
        """Sample insights for testing"""
        return [
            Insight(
                content="Quantum computing offers exponential speedup",
                type=InsightType.FACT,
                confidence=0.9
            ),
            Insight(
                content="This is how superposition works",
                type=InsightType.EXPLANATION,
                confidence=0.8
            )
        ]
    
    def test_analyze_vocabulary_complexity_simple(self, analyzer, simple_text):
        """Test vocabulary analysis on simple text"""
        metrics = analyzer.analyze_vocabulary_complexity(simple_text)
        
        assert isinstance(metrics, VocabularyMetrics)
        assert metrics.total_word_count == 15
        assert metrics.vocabulary_richness > 0.5  # Most words are unique
        assert metrics.technical_density == 0.0  # No technical terms
        assert metrics.avg_word_length < 4  # Short words
        assert metrics.syllable_complexity < 0.5  # Simple syllables
    
    def test_analyze_vocabulary_complexity_technical(self, analyzer, complex_text):
        """Test vocabulary analysis on technical text"""
        metrics = analyzer.analyze_vocabulary_complexity(
            complex_text,
            domain_hints=['technology', 'science']
        )
        
        assert metrics.technical_density > 0.1  # Has technical terms
        assert metrics.avg_word_length > 5  # Longer words
        assert metrics.syllable_complexity > 0.5  # More complex syllables
        assert metrics.lexical_diversity > 0.7  # Rich vocabulary
    
    def test_analyze_vocabulary_complexity_medical(self, analyzer, medical_text):
        """Test vocabulary analysis on medical text"""
        metrics = analyzer.analyze_vocabulary_complexity(
            medical_text,
            domain_hints=['medical']
        )
        
        assert metrics.technical_density > 0.2  # High technical content
        assert metrics.technical_term_count >= 5  # Multiple medical terms
    
    def test_syllable_counting(self, analyzer):
        """Test syllable counting accuracy"""
        assert analyzer._count_syllables("cat") == 1
        assert analyzer._count_syllables("hello") == 2
        assert analyzer._count_syllables("beautiful") == 3
        assert analyzer._count_syllables("implementation") >= 4
        assert analyzer._count_syllables("a") == 1  # Minimum 1 syllable
    
    def test_classify_segment_complexity_simple(self, analyzer, simple_text):
        """Test segment complexity classification for simple text"""
        complexity = analyzer.classify_segment_complexity(simple_text)
        
        assert isinstance(complexity, SegmentComplexity)
        assert complexity.complexity_level == ComplexityLevel.SIMPLE
        assert complexity.complexity_score < 30
        assert complexity.readability_score > 70
        assert complexity.avg_sentence_length < 10
    
    def test_classify_segment_complexity_complex(self, analyzer, complex_text, sample_entities):
        """Test segment complexity classification for complex text"""
        complexity = analyzer.classify_segment_complexity(
            complex_text,
            entities=sample_entities
        )
        
        assert complexity.complexity_level in [ComplexityLevel.COMPLEX, ComplexityLevel.VERY_COMPLEX]
        assert complexity.complexity_score > 50
        assert complexity.technical_entity_count > 0
        assert complexity.readability_score < 50
    
    def test_calculate_episode_complexity(self, analyzer):
        """Test episode-level complexity calculation"""
        # Create segment complexities with different levels
        segment_complexities = [
            SegmentComplexity(
                segment_id="1",
                complexity_level=ComplexityLevel.SIMPLE,
                complexity_score=20,
                vocabulary_metrics=VocabularyMetrics(
                    unique_word_count=50, total_word_count=100,
                    vocabulary_richness=0.5, avg_word_length=4,
                    technical_term_count=0, technical_density=0.0,
                    syllable_complexity=0.3, lexical_diversity=0.5
                ),
                readability_score=80,
                technical_entity_count=0,
                sentence_count=5,
                avg_sentence_length=10
            ),
            SegmentComplexity(
                segment_id="2",
                complexity_level=ComplexityLevel.COMPLEX,
                complexity_score=70,
                vocabulary_metrics=VocabularyMetrics(
                    unique_word_count=80, total_word_count=120,
                    vocabulary_richness=0.67, avg_word_length=6,
                    technical_term_count=10, technical_density=0.08,
                    syllable_complexity=0.6, lexical_diversity=0.7
                ),
                readability_score=40,
                technical_entity_count=3,
                sentence_count=4,
                avg_sentence_length=20
            )
        ]
        
        episode_complexity = analyzer.calculate_episode_complexity(segment_complexities)
        
        assert isinstance(episode_complexity, EpisodeComplexity)
        assert episode_complexity.average_complexity == 45  # (20+70)/2
        assert episode_complexity.dominant_level in [ComplexityLevel.SIMPLE, ComplexityLevel.COMPLEX]
        assert episode_complexity.complexity_variance > 0
        assert len(episode_complexity.complexity_distribution) > 0
    
    def test_calculate_information_density(self, analyzer, complex_text, sample_entities, sample_insights):
        """Test information density calculation"""
        quotes = [
            Quote(
                text="Quantum computing is revolutionary",
                speaker="Expert",
                timestamp="00:01:00",
                context="Opening statement",
                type=QuoteType.INSIGHT
            )
        ]
        
        density = analyzer.calculate_information_density(
            complex_text,
            insights=sample_insights,
            entities=sample_entities,
            quotes=quotes
        )
        
        assert isinstance(density, dict)
        assert density['word_count'] > 0
        assert density['entity_density'] > 0
        assert density['insight_density'] > 0
        assert density['quote_density'] > 0
        assert density['information_density'] > 0
    
    def test_analyze_segment_transitions(self, analyzer):
        """Test segment transition analysis"""
        segments = [
            {'speaker': 'Host', 'text': 'Simple intro', 'complexity_score': 20},
            {'speaker': 'Guest', 'text': 'Complex response', 'complexity_score': 60},
            {'speaker': 'Host', 'text': 'Follow up', 'complexity_score': 30}
        ]
        
        transitions = analyzer.analyze_segment_transitions(segments)
        
        assert len(transitions) == 2
        assert transitions[0]['transition_type'] == 'abrupt'  # 20->60 is big jump
        assert transitions[0]['direction'] == 'increasing'
        assert transitions[1]['direction'] == 'decreasing'
    
    def test_identify_complexity_patterns(self, analyzer):
        """Test complexity pattern identification"""
        # Create episode with increasing complexity
        complexities = []
        for i in range(10):
            score = 20 + i * 5  # Gradually increasing
            complexities.append(
                SegmentComplexity(
                    segment_id=str(i),
                    complexity_level=ComplexityLevel.MODERATE,
                    complexity_score=score,
                    vocabulary_metrics=VocabularyMetrics(
                        unique_word_count=50, total_word_count=100,
                        vocabulary_richness=0.5, avg_word_length=5,
                        technical_term_count=i, technical_density=i/100,
                        syllable_complexity=0.5, lexical_diversity=0.5
                    ),
                    readability_score=70-i*2,
                    technical_entity_count=i//2,
                    sentence_count=5,
                    avg_sentence_length=15
                )
            )
        
        episode_complexity = EpisodeComplexity(
            average_complexity=45,
            dominant_level=ComplexityLevel.MODERATE,
            complexity_distribution={ComplexityLevel.MODERATE: 10},
            technical_density=0.05,
            complexity_variance=50,
            segment_complexities=complexities
        )
        
        patterns = analyzer.identify_complexity_patterns(episode_complexity)
        
        assert patterns['trend'] == 'increasing'
        assert patterns['consistency'] == 'moderate'
        assert len(patterns['peaks']) >= 0
        assert len(patterns['valleys']) >= 0
    
    def test_calculate_accessibility_score(self, analyzer, simple_text, sample_insights):
        """Test accessibility score calculation"""
        quotes = [
            Quote(
                text="Let me explain this simply",
                speaker="Host",
                timestamp="00:00:30",
                context="Providing a clear explanation of the concept",
                type=QuoteType.EXPLANATION
            )
        ]
        
        accessibility = analyzer.calculate_accessibility_score(
            simple_text,
            insights=sample_insights,
            quotes=quotes
        )
        
        assert isinstance(accessibility, dict)
        assert 0 <= accessibility['accessibility_score'] <= 1
        assert accessibility['readability_factor'] > 0.7  # Simple text
        assert accessibility['explanation_quality'] > 0.5  # Has explanations
        assert accessibility['context_availability'] > 0.5  # Has context
        assert accessibility['jargon_usage'] < 0.1  # Low jargon
    
    def test_analyze_content_structure(self, analyzer):
        """Test content structure analysis"""
        segments = [
            {'speaker': 'Host', 'text': 'Welcome to the show'},
            {'speaker': 'Guest', 'text': 'Thanks for having me'},
            {'speaker': 'Host', 'text': 'Let us discuss AI'},
            {'speaker': 'Guest', 'text': 'AI is fascinating'},
            {'speaker': 'Host', 'text': 'Indeed it is'}
        ]
        
        structure = analyzer.analyze_content_structure(segments)
        
        assert structure['total_segments'] == 5
        assert structure['num_speakers'] == 2
        assert structure['structure_type'] in ['interview', 'balanced_dialogue']
        assert structure['topic_transitions'] == 4  # Each speaker change
        assert 'Host' in structure['speaker_distribution']
        assert 'Guest' in structure['speaker_distribution']
    
    def test_empty_text_handling(self, analyzer):
        """Test handling of empty text"""
        metrics = analyzer.analyze_vocabulary_complexity("")
        assert metrics.total_word_count == 0
        assert metrics.vocabulary_richness == 0
        
        complexity = analyzer.classify_segment_complexity("")
        assert complexity.complexity_level == ComplexityLevel.SIMPLE
        
        density = analyzer.calculate_information_density("", [], [], [])
        assert density['word_count'] == 0
        assert density['information_density'] == 0
    
    def test_edge_cases(self, analyzer):
        """Test various edge cases"""
        # Single word
        metrics = analyzer.analyze_vocabulary_complexity("Hello")
        assert metrics.total_word_count == 1
        assert metrics.vocabulary_richness == 1.0
        
        # No segments
        episode_complexity = analyzer.calculate_episode_complexity([])
        assert episode_complexity.average_complexity == 0
        
        # Empty segment list
        transitions = analyzer.analyze_segment_transitions([])
        assert len(transitions) == 0
        
        structure = analyzer.analyze_content_structure([])
        assert structure['total_segments'] == 0
        assert structure['structure_type'] == 'unknown'