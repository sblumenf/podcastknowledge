"""Content analysis metrics for text complexity, density, and accessibility.

This module preserves the content analysis functionality from the original
processing/metrics.py, maintaining all algorithms and calculations.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import logging
import re
from statistics import mean, stdev

from src.core.models import Entity, Insight, ComplexityLevel

logger = logging.getLogger(__name__)


@dataclass
class ComplexityMetrics:
    """Metrics for text complexity analysis."""
    classification: ComplexityLevel
    complexity_score: float
    technical_density: float
    avg_word_length: float
    avg_sentence_length: float
    syllable_complexity: float
    unique_ratio: float
    technical_entity_count: int


@dataclass
class InformationDensityMetrics:
    """Metrics for information density analysis."""
    information_score: float
    insight_density: float
    entity_density: float
    fact_density: float
    word_count: int
    duration_minutes: float
    insights_per_minute: float
    entities_per_minute: float


@dataclass
class AccessibilityMetrics:
    """Metrics for content accessibility analysis."""
    accessibility_score: float
    avg_sentence_length: float
    jargon_percentage: float
    explanation_quality: float
    readability_score: float


class ContentMetricsCalculator:
    """Calculator for various content metrics.
    
    This class preserves all the original algorithms from MetricsCalculator
    in processing/metrics.py.
    """
    
    def __init__(self):
        """Initialize metrics calculator."""
        # Technical term patterns
        self.technical_patterns = [
            r'\b[A-Z]{2,}[A-Z0-9]*\b',  # Acronyms (at least 2 uppercase letters)
            r'\b\w+(?:ology|itis|osis|ase|ine|cyte|plasm)\b',  # Medical/scientific suffixes
            r'\b(?:neuro|cardio|hypo|hyper|anti|meta|poly|mono)\w+\b',  # Technical prefixes
            r'\b(?:bi|tri)(?:lateral|modal|polar|nary|cycle|weekly|monthly|annual)\b',  # bi/tri compounds
            r'\b(?:algorithm|protocol|methodology|hypothesis|synthesis)\b',
            r'\b(?:receptor|enzyme|pathway|mechanism|substrate)\b',
        ]
        
        # Explanation patterns
        self.explanation_patterns = [
            r'\b(?:which means|in other words|that is|i\.e\.|for example|such as)\b',
            r'\b(?:basically|simply put|essentially|in simple terms)\b',
            r'\b(?:imagine|think of it as|like a?|similar to)\b',  # Analogies
            r'\([^)]+\)',  # Parenthetical explanations
        ]
        
        # Fact patterns
        self.fact_patterns = [
            r'\b\d+\s*(?:percent|%)',  # Percentages
            r'\b(?:study|research|experiment|trial)\s+(?:found|showed|demonstrated)',
            r'\b(?:according to|based on|research from)',
            r'\b(?:statistically|significantly|correlation)',
            r'\b\d{4}\b',  # Years (potential citations)
        ]
    
    def calculate_complexity(
        self,
        text: str,
        entities: Optional[List[Entity]] = None
    ) -> ComplexityMetrics:
        """Calculate text complexity metrics."""
        # Get vocabulary metrics
        vocab_metrics = self._analyze_vocabulary_complexity(text)
        
        # Count technical entities
        technical_entity_count = 0
        if entities:
            technical_types = {
                'Study', 'Institution', 'Researcher', 'Journal', 'Theory',
                'Research_Method', 'Medication', 'Condition', 'Treatment',
                'Symptom', 'Biological_Process', 'Medical_Device', 'Chemical',
                'Scientific_Theory', 'Laboratory', 'Experiment', 'Discovery'
            }
            
            technical_entity_count = sum(
                1 for entity in entities
                if str(entity.entity_type).split('.')[-1] in technical_types
            )
        
        # Calculate composite complexity score
        complexity_score = (
            vocab_metrics['avg_word_length'] * 0.2 +
            (1 - vocab_metrics['unique_ratio']) * 0.2 +
            vocab_metrics['syllable_complexity'] * 0.3 +
            vocab_metrics['technical_density'] * 100 * 0.3
        )
        
        # Add entity contribution
        if entities and len(entities) > 0:
            entity_ratio = technical_entity_count / len(entities)
            complexity_score += entity_ratio * 2
        
        # Classify based on score
        if complexity_score < 3:
            classification = ComplexityLevel.LAYPERSON
        elif complexity_score < 5:
            classification = ComplexityLevel.INTERMEDIATE
        else:
            classification = ComplexityLevel.EXPERT
        
        # Override based on technical density
        if vocab_metrics['technical_density'] > 0.1:
            classification = ComplexityLevel.EXPERT
        elif vocab_metrics['technical_density'] > 0.05 and classification == ComplexityLevel.LAYPERSON:
            classification = ComplexityLevel.INTERMEDIATE
        
        return ComplexityMetrics(
            classification=classification,
            complexity_score=complexity_score,
            technical_density=vocab_metrics['technical_density'],
            avg_word_length=vocab_metrics['avg_word_length'],
            avg_sentence_length=vocab_metrics['avg_sentence_length'],
            syllable_complexity=vocab_metrics['syllable_complexity'],
            unique_ratio=vocab_metrics['unique_ratio'],
            technical_entity_count=technical_entity_count
        )
    
    def calculate_information_density(
        self,
        text: str,
        insights: Optional[List[Insight]] = None,
        entities: Optional[List[Entity]] = None
    ) -> InformationDensityMetrics:
        """Calculate information density metrics."""
        # Basic text metrics
        words = text.split()
        word_count = len(words)
        
        if word_count == 0:
            return InformationDensityMetrics(
                information_score=0,
                insight_density=0,
                entity_density=0,
                fact_density=0,
                word_count=0,
                duration_minutes=0,
                insights_per_minute=0,
                entities_per_minute=0
            )
        
        # Calculate densities
        insight_count = len(insights) if insights else 0
        entity_count = len(entities) if entities else 0
        
        insight_density = (insight_count / word_count) * 100
        entity_density = (entity_count / word_count) * 100
        
        # Count facts
        fact_count = self._count_facts(text)
        fact_density = (fact_count / word_count) * 100
        
        # Calculate composite information score
        information_score = (
            insight_density * 0.4 +
            entity_density * 0.3 +
            fact_density * 0.3
        )
        
        # Estimate duration (average speaking rate: 150 wpm)
        avg_wpm = 150
        duration_minutes = word_count / avg_wpm
        
        # Calculate per-minute metrics
        insights_per_minute = insight_count / duration_minutes if duration_minutes > 0 else 0
        entities_per_minute = entity_count / duration_minutes if duration_minutes > 0 else 0
        
        return InformationDensityMetrics(
            information_score=information_score,
            insight_density=insight_density,
            entity_density=entity_density,
            fact_density=fact_density,
            word_count=word_count,
            duration_minutes=duration_minutes,
            insights_per_minute=insights_per_minute,
            entities_per_minute=entities_per_minute
        )
    
    def calculate_accessibility(
        self,
        text: str,
        complexity_score: float
    ) -> AccessibilityMetrics:
        """Calculate accessibility metrics."""
        # Split into sentences and words
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        words = text.split()
        
        if not sentences or not words:
            return AccessibilityMetrics(
                accessibility_score=0,
                avg_sentence_length=0,
                jargon_percentage=0,
                explanation_quality=0,
                readability_score=0
            )
        
        # Average sentence length
        avg_sentence_length = len(words) / len(sentences)
        
        # Count jargon and explanations
        jargon_count = 0
        for i, pattern in enumerate(self.technical_patterns):
            # First pattern (acronyms) should be case sensitive
            if i == 0:
                matches = re.findall(pattern, text)
            else:
                matches = re.findall(pattern, text, re.IGNORECASE)
            jargon_count += len(matches)
        
        explanation_count = sum(
            len(re.findall(pattern, text, re.IGNORECASE))
            for pattern in self.explanation_patterns
        )
        
        # Calculate percentages
        jargon_percentage = (jargon_count / len(words)) * 100
        
        # Explanation quality: ratio of explanations to jargon
        explanation_quality = (
            explanation_count / jargon_count * 100
            if jargon_count > 0
            else 100.0
        )
        
        # Calculate readability score (simplified Flesch Reading Ease)
        avg_syllables_per_word = self._estimate_syllables(text) / len(words)
        readability_score = max(0, min(100,
            206.835 - 1.015 * avg_sentence_length - 84.6 * avg_syllables_per_word
        ))
        
        # Calculate composite accessibility score
        accessibility_score = (
            (100 - complexity_score * 10) * 0.3 +
            readability_score * 0.3 +
            min(100, explanation_quality) * 0.2 +
            (100 - min(100, jargon_percentage * 10)) * 0.2
        )
        
        return AccessibilityMetrics(
            accessibility_score=accessibility_score / 100,  # Normalize to 0-1
            avg_sentence_length=avg_sentence_length,
            jargon_percentage=jargon_percentage,
            explanation_quality=explanation_quality / 100,  # Normalize to 0-1
            readability_score=readability_score / 100  # Normalize to 0-1
        )
    
    def aggregate_episode_metrics(
        self,
        segment_complexities: List[ComplexityMetrics],
        segment_densities: List[InformationDensityMetrics],
        segment_accessibilities: List[AccessibilityMetrics]
    ) -> Dict[str, Any]:
        """Aggregate segment metrics to episode level."""
        if not segment_complexities:
            return self._empty_episode_metrics()
        
        # Complexity aggregation
        complexity_scores = [m.complexity_score for m in segment_complexities]
        avg_complexity = mean(complexity_scores)
        complexity_variance = stdev(complexity_scores) if len(complexity_scores) > 1 else 0
        
        # Count complexity level distribution
        level_counts = Counter(m.classification for m in segment_complexities)
        total_segments = len(segment_complexities)
        
        complexity_distribution = {
            level.value: count / total_segments
            for level, count in level_counts.items()
        }
        
        # Determine dominant complexity level
        dominant_level = max(level_counts.items(), key=lambda x: x[1])[0]
        
        # Information density aggregation
        if segment_densities:
            avg_info_score = mean(m.information_score for m in segment_densities)
            total_insights = sum(
                m.word_count * m.insight_density / 100
                for m in segment_densities
            )
            total_entities = sum(
                m.word_count * m.entity_density / 100
                for m in segment_densities
            )
            info_variance = stdev(
                m.information_score for m in segment_densities
            ) if len(segment_densities) > 1 else 0
        else:
            avg_info_score = 0
            total_insights = 0
            total_entities = 0
            info_variance = 0
        
        # Accessibility aggregation
        if segment_accessibilities:
            avg_accessibility = mean(m.accessibility_score for m in segment_accessibilities)
        else:
            avg_accessibility = 0
        
        # Technical characteristics
        avg_technical_density = mean(m.technical_density for m in segment_complexities)
        is_technical = avg_technical_density > 0.05
        is_mixed_complexity = complexity_variance > 1.5
        has_consistent_density = info_variance < 2.0
        
        return {
            # Complexity metrics
            'avg_complexity': avg_complexity,
            'dominant_complexity_level': dominant_level,
            'technical_density': avg_technical_density,
            'complexity_variance': complexity_variance,
            'is_mixed_complexity': is_mixed_complexity,
            'is_technical': is_technical,
            'layperson_percentage': complexity_distribution.get(ComplexityLevel.LAYPERSON.value, 0),
            'intermediate_percentage': complexity_distribution.get(ComplexityLevel.INTERMEDIATE.value, 0),
            'expert_percentage': complexity_distribution.get(ComplexityLevel.EXPERT.value, 0),
            
            # Information density metrics
            'avg_information_score': avg_info_score,
            'total_insights': int(total_insights),
            'total_entities': int(total_entities),
            'information_variance': info_variance,
            'has_consistent_density': has_consistent_density,
            
            # Accessibility metrics
            'avg_accessibility': avg_accessibility,
            
            # Counts
            'segment_count': total_segments
        }
    
    # Helper methods
    
    def _analyze_vocabulary_complexity(self, text: str) -> Dict[str, float]:
        """Analyze vocabulary complexity of text."""
        words = text.split()
        
        if not words:
            return {
                'avg_word_length': 0,
                'unique_ratio': 0,
                'technical_density': 0,
                'syllable_complexity': 0,
                'avg_sentence_length': 0
            }
        
        # Average word length
        avg_word_length = mean(len(word) for word in words)
        
        # Unique word ratio
        unique_words = set(word.lower() for word in words)
        unique_ratio = len(unique_words) / len(words)
        
        # Technical term density
        technical_count = 0
        for i, pattern in enumerate(self.technical_patterns):
            # First pattern (acronyms) should be case sensitive
            if i == 0:
                matches = re.findall(pattern, text)
            else:
                matches = re.findall(pattern, text, re.IGNORECASE)
            technical_count += len(matches)
        technical_density = technical_count / len(words)
        
        # Syllable complexity
        total_syllables = self._estimate_syllables(text)
        syllable_complexity = total_syllables / len(words)
        
        # Average sentence length
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        avg_sentence_length = len(words) / len(sentences) if sentences else len(words)
        
        return {
            'avg_word_length': avg_word_length,
            'unique_ratio': unique_ratio,
            'technical_density': technical_density,
            'syllable_complexity': syllable_complexity,
            'avg_sentence_length': avg_sentence_length
        }
    
    def _estimate_syllables(self, text: str) -> int:
        """Estimate syllable count in text."""
        # Simple syllable estimation
        vowels = 'aeiouAEIOU'
        syllable_count = 0
        
        words = text.split()
        for word in words:
            word = word.strip('.,!?;:"')
            if len(word) <= 3:
                syllable_count += 1
            else:
                # Count vowel groups
                prev_was_vowel = False
                word_syllables = 0
                
                for char in word:
                    is_vowel = char in vowels
                    if is_vowel and not prev_was_vowel:
                        word_syllables += 1
                    prev_was_vowel = is_vowel
                
                # Adjust for silent e
                if word.endswith('e') and word_syllables > 1:
                    word_syllables -= 1
                
                syllable_count += max(1, word_syllables)
        
        return syllable_count
    
    def _count_facts(self, text: str) -> int:
        """Count fact-like statements in text."""
        fact_count = sum(
            len(re.findall(pattern, text, re.IGNORECASE))
            for pattern in self.fact_patterns
        )
        
        # Also count sentences with numbers (often factual)
        sentences = re.split(r'[.!?]+', text)
        for sentence in sentences:
            if re.search(r'\d+', sentence):
                fact_count += 0.5  # Half weight for general numeric content
        
        return int(fact_count)
    
    def _empty_episode_metrics(self) -> Dict[str, Any]:
        """Return empty episode metrics structure."""
        return {
            'avg_complexity': 0,
            'dominant_complexity_level': ComplexityLevel.UNKNOWN,
            'technical_density': 0,
            'complexity_variance': 0,
            'is_mixed_complexity': False,
            'is_technical': False,
            'layperson_percentage': 0,
            'intermediate_percentage': 0,
            'expert_percentage': 0,
            'avg_information_score': 0,
            'total_insights': 0,
            'total_entities': 0,
            'information_variance': 0,
            'has_consistent_density': False,
            'avg_accessibility': 0,
            'segment_count': 0
        }