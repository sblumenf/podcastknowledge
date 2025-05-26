"""
Advanced complexity analysis functionality
"""
import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass
from statistics import mean, stdev
from collections import Counter
import math

from src.core.models import Entity, Insight, Quote, ComplexityLevel, EntityType


logger = logging.getLogger(__name__)


@dataclass
class VocabularyMetrics:
    """Metrics for vocabulary analysis"""
    unique_word_count: int
    total_word_count: int
    vocabulary_richness: float
    avg_word_length: float
    technical_term_count: int
    technical_density: float
    syllable_complexity: float
    lexical_diversity: float


@dataclass 
class SegmentComplexity:
    """Complexity analysis for a text segment"""
    segment_id: str
    complexity_level: ComplexityLevel
    complexity_score: float
    vocabulary_metrics: VocabularyMetrics
    readability_score: float
    technical_entity_count: int
    sentence_count: int
    avg_sentence_length: float


@dataclass
class EpisodeComplexity:
    """Episode-level complexity analysis"""
    average_complexity: float
    dominant_level: ComplexityLevel
    complexity_distribution: Dict[ComplexityLevel, int]
    technical_density: float
    complexity_variance: float
    segment_complexities: List[SegmentComplexity]


class ComplexityAnalyzer:
    """Advanced complexity analysis for podcast content"""
    
    def __init__(self):
        """Initialize complexity analyzer"""
        # Common technical terms in various domains
        self.technical_terms = {
            'medical': {
                'diagnosis', 'symptom', 'treatment', 'pathology', 'etiology',
                'prognosis', 'therapeutic', 'clinical', 'pharmaceutical',
                'metabolism', 'syndrome', 'chronic', 'acute', 'inflammation'
            },
            'technology': {
                'algorithm', 'framework', 'architecture', 'infrastructure',
                'optimization', 'implementation', 'protocol', 'interface',
                'scalability', 'latency', 'throughput', 'deployment',
                'microservice', 'containerization', 'orchestration'
            },
            'science': {
                'hypothesis', 'methodology', 'correlation', 'causation',
                'empirical', 'theoretical', 'quantum', 'molecular',
                'statistical', 'systematic', 'phenomenon', 'paradigm'
            },
            'business': {
                'revenue', 'margin', 'equity', 'valuation', 'acquisition',
                'synergy', 'leverage', 'optimization', 'monetization',
                'scalability', 'disruption', 'stakeholder', 'portfolio'
            }
        }
        
        # Flatten all technical terms
        self.all_technical_terms = set()
        for domain_terms in self.technical_terms.values():
            self.all_technical_terms.update(domain_terms)
    
    def analyze_vocabulary_complexity(
        self, 
        text: str,
        domain_hints: Optional[List[str]] = None
    ) -> VocabularyMetrics:
        """
        Analyze vocabulary complexity of text
        
        Args:
            text: Text to analyze
            domain_hints: Optional domain hints for technical term detection
            
        Returns:
            VocabularyMetrics with detailed analysis
        """
        if not text:
            return VocabularyMetrics(
                unique_word_count=0,
                total_word_count=0,
                vocabulary_richness=0.0,
                avg_word_length=0.0,
                technical_term_count=0,
                technical_density=0.0,
                syllable_complexity=0.0,
                lexical_diversity=0.0
            )
        
        # Tokenize and clean text
        words = re.findall(r'\b[a-z]+\b', text.lower())
        if not words:
            return VocabularyMetrics(
                unique_word_count=0,
                total_word_count=0,
                vocabulary_richness=0.0,
                avg_word_length=0.0,
                technical_term_count=0,
                technical_density=0.0,
                syllable_complexity=0.0,
                lexical_diversity=0.0
            )
        
        # Basic metrics
        total_words = len(words)
        unique_words = set(words)
        unique_count = len(unique_words)
        
        # Vocabulary richness (unique/total ratio)
        vocabulary_richness = unique_count / total_words if total_words > 0 else 0
        
        # Average word length
        avg_word_length = mean(len(word) for word in words) if words else 0
        
        # Technical term detection
        technical_terms_to_check = self.all_technical_terms.copy()
        
        # Add domain-specific terms if hints provided
        if domain_hints:
            for domain in domain_hints:
                if domain.lower() in self.technical_terms:
                    technical_terms_to_check.update(self.technical_terms[domain.lower()])
        
        # Count technical terms
        technical_count = sum(1 for word in words if word in technical_terms_to_check)
        technical_density = technical_count / total_words if total_words > 0 else 0
        
        # Syllable complexity (approximation)
        total_syllables = sum(self._count_syllables(word) for word in words)
        avg_syllables = total_syllables / total_words if total_words > 0 else 0
        syllable_complexity = avg_syllables / 3.0  # Normalize to 0-1 range
        
        # Lexical diversity (Type-Token Ratio with adjustment for text length)
        # Using Moving Average Type-Token Ratio (MATTR) approximation
        if total_words > 50:
            # Sample windows for diversity calculation
            window_size = 50
            diversities = []
            for i in range(0, total_words - window_size + 1, 10):
                window = words[i:i + window_size]
                diversities.append(len(set(window)) / window_size)
            lexical_diversity = mean(diversities) if diversities else vocabulary_richness
        else:
            lexical_diversity = vocabulary_richness
        
        return VocabularyMetrics(
            unique_word_count=unique_count,
            total_word_count=total_words,
            vocabulary_richness=vocabulary_richness,
            avg_word_length=avg_word_length,
            technical_term_count=technical_count,
            technical_density=technical_density,
            syllable_complexity=min(syllable_complexity, 1.0),
            lexical_diversity=lexical_diversity
        )
    
    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word (approximation)"""
        word = word.lower()
        syllables = 0
        vowels = "aeiouy"
        
        # Count vowel groups
        prev_was_vowel = False
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                syllables += 1
            prev_was_vowel = is_vowel
        
        # Adjust for silent e
        if word.endswith("e") and syllables > 1:
            syllables -= 1
        
        # Minimum of 1 syllable
        return max(1, syllables)
    
    def classify_segment_complexity(
        self,
        text: str,
        entities: Optional[List[Entity]] = None,
        vocab_metrics: Optional[VocabularyMetrics] = None
    ) -> SegmentComplexity:
        """
        Classify complexity level of a text segment
        
        Args:
            text: Segment text
            entities: Optional entities found in segment
            vocab_metrics: Optional pre-calculated vocabulary metrics
            
        Returns:
            SegmentComplexity with classification and metrics
        """
        # Calculate vocabulary metrics if not provided
        if vocab_metrics is None:
            vocab_metrics = self.analyze_vocabulary_complexity(text)
        
        # Count sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        sentence_count = len(sentences)
        
        # Average sentence length
        words_per_sentence = []
        for sentence in sentences:
            words = re.findall(r'\b\w+\b', sentence)
            if words:
                words_per_sentence.append(len(words))
        
        avg_sentence_length = mean(words_per_sentence) if words_per_sentence else 0
        
        # Count technical entities
        technical_entity_count = 0
        if entities:
            technical_types = {EntityType.TECHNOLOGY, EntityType.SCIENTIFIC_THEORY, 
                             EntityType.MEDICAL_TERM, EntityType.RESEARCH_METHOD}
            technical_entity_count = sum(1 for e in entities if e.type in technical_types)
        
        # Calculate readability score (simplified Flesch Reading Ease)
        # Score = 206.835 - 1.015 * (total words / total sentences) - 84.6 * (total syllables / total words)
        if sentence_count > 0 and vocab_metrics.total_word_count > 0:
            avg_words_per_sentence = vocab_metrics.total_word_count / sentence_count
            avg_syllables_per_word = vocab_metrics.syllable_complexity * 3  # Denormalize
            
            readability = 206.835 - (1.015 * avg_words_per_sentence) - (84.6 * avg_syllables_per_word)
            readability = max(0, min(100, readability))  # Clamp to 0-100
        else:
            readability = 50  # Default middle value
        
        # Calculate complexity score (0-100)
        complexity_score = self._calculate_complexity_score(
            vocab_metrics,
            avg_sentence_length,
            technical_entity_count,
            readability
        )
        
        # Classify complexity level
        if complexity_score < 30:
            complexity_level = ComplexityLevel.SIMPLE
        elif complexity_score < 50:
            complexity_level = ComplexityLevel.MODERATE
        elif complexity_score < 70:
            complexity_level = ComplexityLevel.COMPLEX
        else:
            complexity_level = ComplexityLevel.VERY_COMPLEX
        
        return SegmentComplexity(
            segment_id="",  # To be set by caller
            complexity_level=complexity_level,
            complexity_score=complexity_score,
            vocabulary_metrics=vocab_metrics,
            readability_score=readability,
            technical_entity_count=technical_entity_count,
            sentence_count=sentence_count,
            avg_sentence_length=avg_sentence_length
        )
    
    def _calculate_complexity_score(
        self,
        vocab_metrics: VocabularyMetrics,
        avg_sentence_length: float,
        technical_entity_count: int,
        readability: float
    ) -> float:
        """Calculate overall complexity score (0-100)"""
        # Weight different factors
        weights = {
            'technical_density': 0.25,
            'sentence_complexity': 0.20,
            'vocabulary_richness': 0.15,
            'readability': 0.20,
            'syllable_complexity': 0.10,
            'entity_complexity': 0.10
        }
        
        # Normalize factors to 0-100 scale
        factors = {
            'technical_density': vocab_metrics.technical_density * 100,
            'sentence_complexity': min(avg_sentence_length / 30 * 100, 100),
            'vocabulary_richness': vocab_metrics.lexical_diversity * 100,
            'readability': 100 - readability,  # Invert so higher = more complex
            'syllable_complexity': vocab_metrics.syllable_complexity * 100,
            'entity_complexity': min(technical_entity_count * 10, 100)
        }
        
        # Calculate weighted score
        score = sum(factors[key] * weights[key] for key in weights)
        
        return min(100, max(0, score))
    
    def calculate_episode_complexity(
        self,
        segment_complexities: List[SegmentComplexity]
    ) -> EpisodeComplexity:
        """
        Calculate episode-level complexity from segment complexities
        
        Args:
            segment_complexities: List of segment complexity analyses
            
        Returns:
            EpisodeComplexity with aggregated metrics
        """
        if not segment_complexities:
            return EpisodeComplexity(
                average_complexity=0.0,
                dominant_level=ComplexityLevel.SIMPLE,
                complexity_distribution={},
                technical_density=0.0,
                complexity_variance=0.0,
                segment_complexities=[]
            )
        
        # Calculate average complexity score
        scores = [seg.complexity_score for seg in segment_complexities]
        avg_complexity = mean(scores)
        
        # Calculate variance
        if len(scores) > 1:
            variance = stdev(scores) ** 2
        else:
            variance = 0.0
        
        # Count distribution of complexity levels
        level_counts = Counter(seg.complexity_level for seg in segment_complexities)
        distribution = {level: level_counts.get(level, 0) for level in ComplexityLevel}
        
        # Find dominant level
        if level_counts:
            dominant_level = level_counts.most_common(1)[0][0]
        else:
            dominant_level = ComplexityLevel.MODERATE
        
        # Average technical density
        tech_densities = [seg.vocabulary_metrics.technical_density 
                         for seg in segment_complexities]
        avg_technical_density = mean(tech_densities) if tech_densities else 0.0
        
        return EpisodeComplexity(
            average_complexity=avg_complexity,
            dominant_level=dominant_level,
            complexity_distribution=distribution,
            technical_density=avg_technical_density,
            complexity_variance=variance,
            segment_complexities=segment_complexities
        )
    
    def calculate_information_density(
        self,
        text: str,
        insights: Optional[List[Insight]] = None,
        entities: Optional[List[Entity]] = None,
        quotes: Optional[List[Quote]] = None
    ) -> Dict[str, float]:
        """
        Calculate information density metrics
        
        Args:
            text: Text to analyze
            insights: Optional insights extracted
            entities: Optional entities found
            quotes: Optional quotes identified
            
        Returns:
            Dictionary of density metrics
        """
        # Word count
        words = re.findall(r'\b\w+\b', text)
        word_count = len(words)
        
        if word_count == 0:
            return {
                'word_count': 0,
                'insight_density': 0.0,
                'entity_density': 0.0,
                'quote_density': 0.0,
                'information_density': 0.0,
                'fact_density': 0.0
            }
        
        # Calculate densities (per 1000 words)
        words_in_thousands = word_count / 1000
        
        insight_count = len(insights) if insights else 0
        entity_count = len(entities) if entities else 0
        quote_count = len(quotes) if quotes else 0
        
        insight_density = insight_count / words_in_thousands if words_in_thousands > 0 else 0
        entity_density = entity_count / words_in_thousands if words_in_thousands > 0 else 0
        quote_density = quote_count / words_in_thousands if words_in_thousands > 0 else 0
        
        # Fact density (insights that are facts or data)
        fact_count = 0
        if insights:
            from src.core.models import InsightType
            fact_types = {InsightType.FACT, InsightType.STATISTIC, InsightType.RESEARCH_FINDING}
            fact_count = sum(1 for i in insights if i.type in fact_types)
        
        fact_density = fact_count / words_in_thousands if words_in_thousands > 0 else 0
        
        # Overall information density (weighted sum)
        information_density = (
            insight_density * 0.4 +
            entity_density * 0.3 +
            fact_density * 0.2 +
            quote_density * 0.1
        )
        
        return {
            'word_count': word_count,
            'insight_density': insight_density,
            'entity_density': entity_density,
            'quote_density': quote_density,
            'information_density': information_density,
            'fact_density': fact_density
        }
    
    def analyze_segment_transitions(
        self,
        segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Analyze complexity transitions between segments
        
        Args:
            segments: List of segments with complexity data
            
        Returns:
            List of transition analyses
        """
        transitions = []
        
        for i in range(1, len(segments)):
            prev_segment = segments[i-1]
            curr_segment = segments[i]
            
            # Get complexity scores
            prev_score = prev_segment.get('complexity_score', 50)
            curr_score = curr_segment.get('complexity_score', 50)
            
            # Calculate transition
            score_change = curr_score - prev_score
            change_magnitude = abs(score_change)
            
            # Classify transition
            if change_magnitude < 10:
                transition_type = "smooth"
            elif change_magnitude < 20:
                transition_type = "moderate"
            else:
                transition_type = "abrupt"
            
            # Determine direction
            if score_change > 0:
                direction = "increasing"
            elif score_change < 0:
                direction = "decreasing"
            else:
                direction = "stable"
            
            transitions.append({
                'from_segment': i-1,
                'to_segment': i,
                'score_change': score_change,
                'change_magnitude': change_magnitude,
                'transition_type': transition_type,
                'direction': direction,
                'from_speaker': prev_segment.get('speaker', 'Unknown'),
                'to_speaker': curr_segment.get('speaker', 'Unknown')
            })
        
        return transitions
    
    def identify_complexity_patterns(
        self,
        episode_complexity: EpisodeComplexity
    ) -> Dict[str, Any]:
        """
        Identify patterns in complexity throughout episode
        
        Args:
            episode_complexity: Episode complexity analysis
            
        Returns:
            Dictionary of identified patterns
        """
        if not episode_complexity.segment_complexities:
            return {
                'trend': 'unknown',
                'consistency': 'unknown',
                'peaks': [],
                'valleys': []
            }
        
        scores = [seg.complexity_score for seg in episode_complexity.segment_complexities]
        
        # Identify trend
        if len(scores) >= 3:
            # Simple linear trend
            first_third = mean(scores[:len(scores)//3])
            last_third = mean(scores[-len(scores)//3:])
            
            if last_third > first_third + 5:
                trend = "increasing"
            elif last_third < first_third - 5:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        # Measure consistency
        if episode_complexity.complexity_variance < 50:
            consistency = "high"
        elif episode_complexity.complexity_variance < 150:
            consistency = "moderate"
        else:
            consistency = "low"
        
        # Find peaks and valleys
        peaks = []
        valleys = []
        
        if len(scores) >= 3:
            for i in range(1, len(scores) - 1):
                # Peak: higher than neighbors
                if scores[i] > scores[i-1] and scores[i] > scores[i+1]:
                    peaks.append({
                        'segment_index': i,
                        'score': scores[i],
                        'prominence': scores[i] - mean([scores[i-1], scores[i+1]])
                    })
                # Valley: lower than neighbors
                elif scores[i] < scores[i-1] and scores[i] < scores[i+1]:
                    valleys.append({
                        'segment_index': i,
                        'score': scores[i],
                        'prominence': mean([scores[i-1], scores[i+1]]) - scores[i]
                    })
        
        return {
            'trend': trend,
            'consistency': consistency,
            'peaks': sorted(peaks, key=lambda x: x['prominence'], reverse=True)[:3],
            'valleys': sorted(valleys, key=lambda x: x['prominence'], reverse=True)[:3],
            'average_complexity': episode_complexity.average_complexity,
            'dominant_level': episode_complexity.dominant_level.value
        }
    
    def calculate_accessibility_score(
        self,
        text: str,
        insights: Optional[List[Insight]] = None,
        quotes: Optional[List[Quote]] = None,
        complexity_metrics: Optional[SegmentComplexity] = None
    ) -> Dict[str, float]:
        """
        Calculate accessibility score for content
        
        Args:
            text: Text to analyze
            insights: Optional insights for context
            quotes: Optional quotes for explanation quality
            complexity_metrics: Optional pre-calculated complexity
            
        Returns:
            Dictionary of accessibility metrics
        """
        # Calculate complexity if not provided
        if complexity_metrics is None:
            complexity_metrics = self.classify_segment_complexity(text)
        
        # Base accessibility from readability
        readability_factor = complexity_metrics.readability_score / 100
        
        # Explanation quality factor
        explanation_factor = 0.5  # Default neutral
        if insights:
            # Check for explanatory insights
            from src.core.models import InsightType
            explanatory_types = {InsightType.EXPLANATION, InsightType.CLARIFICATION, 
                               InsightType.EXAMPLE, InsightType.SUMMARY}
            explanatory_count = sum(1 for i in insights if i.type in explanatory_types)
            if len(insights) > 0:
                explanation_factor = min(1.0, 0.5 + (explanatory_count / len(insights)) * 0.5)
        
        # Context availability from quotes
        context_factor = 0.5  # Default neutral
        if quotes:
            # Quotes with context improve accessibility
            contextualized = sum(1 for q in quotes if q.context and len(q.context) > 20)
            if len(quotes) > 0:
                context_factor = min(1.0, 0.5 + (contextualized / len(quotes)) * 0.5)
        
        # Jargon usage penalty
        jargon_penalty = 1.0 - complexity_metrics.vocabulary_metrics.technical_density
        
        # Sentence complexity penalty
        sentence_penalty = 1.0
        if complexity_metrics.avg_sentence_length > 20:
            # Penalize very long sentences
            sentence_penalty = max(0.3, 1.0 - (complexity_metrics.avg_sentence_length - 20) / 30)
        
        # Calculate overall accessibility score
        accessibility_score = (
            readability_factor * 0.3 +
            explanation_factor * 0.25 +
            context_factor * 0.15 +
            jargon_penalty * 0.2 +
            sentence_penalty * 0.1
        )
        
        # Additional metrics
        metrics = {
            'accessibility_score': min(1.0, max(0.0, accessibility_score)),
            'readability_factor': readability_factor,
            'explanation_quality': explanation_factor,
            'context_availability': context_factor,
            'jargon_usage': complexity_metrics.vocabulary_metrics.technical_density,
            'sentence_complexity': 1.0 - sentence_penalty,
            'avg_sentence_length': complexity_metrics.avg_sentence_length,
            'technical_term_percentage': complexity_metrics.vocabulary_metrics.technical_density * 100
        }
        
        return metrics
    
    def analyze_content_structure(
        self,
        segments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze overall content structure and flow
        
        Args:
            segments: List of segments with text and metadata
            
        Returns:
            Dictionary of structural analysis
        """
        if not segments:
            return {
                'total_segments': 0,
                'speaker_distribution': {},
                'topic_transitions': 0,
                'structure_type': 'unknown'
            }
        
        # Speaker distribution
        speaker_counts = Counter(seg.get('speaker', 'Unknown') for seg in segments)
        total_segments = len(segments)
        speaker_distribution = {
            speaker: count / total_segments 
            for speaker, count in speaker_counts.items()
        }
        
        # Analyze topic transitions (simplified)
        topic_transitions = 0
        for i in range(1, len(segments)):
            # Simple heuristic: different speakers often indicate topic transitions
            if segments[i].get('speaker') != segments[i-1].get('speaker'):
                topic_transitions += 1
        
        # Determine structure type
        num_speakers = len(speaker_counts)
        if num_speakers == 1:
            structure_type = 'monologue'
        elif num_speakers == 2:
            if abs(speaker_distribution.get(list(speaker_counts.keys())[0], 0) - 0.5) < 0.1:
                structure_type = 'balanced_dialogue'
            else:
                structure_type = 'interview'
        else:
            structure_type = 'multi_party_discussion'
        
        return {
            'total_segments': total_segments,
            'speaker_distribution': speaker_distribution,
            'topic_transitions': topic_transitions,
            'structure_type': structure_type,
            'num_speakers': num_speakers,
            'avg_segment_length': mean(len(seg.get('text', '').split()) 
                                      for seg in segments) if segments else 0
        }