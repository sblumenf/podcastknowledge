"""
Sentiment analysis for MeaningfulUnits in podcast transcripts.

This module provides multi-dimensional sentiment analysis including:
- Polarity detection (positive/negative/neutral/mixed)
- Emotion recognition (joy, sadness, anger, fear, etc.)
- Speaker sentiment tracking
- Interaction dynamics analysis
- Temporal sentiment flow
- Schema-less sentiment discovery
"""

import logging
import json
import re
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import statistics

logger = logging.getLogger(__name__)


@dataclass
class SentimentScore:
    """Multi-dimensional sentiment score."""
    polarity: str  # positive, negative, neutral, mixed
    score: float  # -1.0 to 1.0
    emotions: Dict[str, float] = field(default_factory=dict)  # emotion -> intensity (0-1)
    attitudes: Dict[str, float] = field(default_factory=dict)  # attitude -> intensity (0-1)
    energy_level: float = 0.5  # 0.0 (low) to 1.0 (high)
    engagement_level: float = 0.5  # 0.0 (disengaged) to 1.0 (highly engaged)
    confidence: float = 0.0  # 0.0 to 1.0


@dataclass
class SpeakerSentiment:
    """Sentiment analysis for a specific speaker."""
    speaker_name: str
    overall_sentiment: SentimentScore
    emotional_range: float  # 0.0 (consistent) to 1.0 (highly variable)
    dominant_emotion: str
    sentiment_segments: List[Dict[str, Any]] = field(default_factory=list)
    speaking_proportion: float = 0.0


@dataclass
class EmotionalMoment:
    """A significant emotional moment in the conversation."""
    text: str
    speaker: str
    emotion: str
    intensity: float
    timestamp: float
    context: str
    trigger: Optional[str] = None


@dataclass
class SentimentFlow:
    """Temporal sentiment progression."""
    trajectory: str  # ascending, descending, stable, volatile
    shifts: List[Dict[str, Any]] = field(default_factory=list)
    peak_moment: Optional[EmotionalMoment] = None
    valley_moment: Optional[EmotionalMoment] = None
    variability: float = 0.0  # 0.0 to 1.0


@dataclass
class InteractionDynamics:
    """Sentiment dynamics between speakers."""
    harmony_score: float  # 0.0 (conflicting) to 1.0 (harmonious)
    emotional_contagion: float  # 0.0 to 1.0
    dominant_interaction_type: str  # supportive, challenging, neutral, mixed
    speaker_pairs: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class DiscoveredSentiment:
    """Schema-less discovered sentiment type."""
    sentiment_type: str
    description: str
    examples: List[str]
    frequency: int
    confidence: float


@dataclass
class SentimentResult:
    """Complete sentiment analysis result for a MeaningfulUnit."""
    unit_id: str
    overall_sentiment: SentimentScore
    speaker_sentiments: Dict[str, SpeakerSentiment]
    emotional_moments: List[EmotionalMoment]
    sentiment_flow: SentimentFlow
    interaction_dynamics: InteractionDynamics
    discovered_sentiments: List[DiscoveredSentiment]
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SentimentConfig:
    """Configuration for sentiment analysis."""
    # Analysis settings
    min_confidence_threshold: float = 0.6
    emotion_detection_threshold: float = 0.3
    moment_intensity_threshold: float = 0.7
    
    # Schema-less discovery
    enable_sentiment_discovery: bool = True
    max_discovered_types: int = 10
    
    # Performance settings
    use_caching: bool = True
    max_text_length: Optional[int] = None
    
    # Analysis features
    analyze_speaker_sentiment: bool = True
    analyze_interactions: bool = True
    analyze_temporal_flow: bool = True
    detect_emotional_moments: bool = True


class SentimentAnalyzer:
    """
    Analyzes sentiment in MeaningfulUnits with multi-dimensional approach.
    
    This analyzer provides comprehensive sentiment analysis including:
    - Basic polarity (positive/negative/neutral)
    - Emotion detection (joy, sadness, anger, etc.)
    - Speaker-specific sentiment tracking
    - Interaction dynamics between speakers
    - Temporal sentiment progression
    - Schema-less sentiment discovery
    """
    
    # Base emotion categories (Plutchik's wheel + additions)
    BASE_EMOTIONS = {
        'joy', 'sadness', 'anger', 'fear', 'surprise', 
        'disgust', 'trust', 'anticipation', 'pride', 'shame'
    }
    
    # Base attitude categories
    BASE_ATTITUDES = {
        'skeptical', 'enthusiastic', 'critical', 'supportive',
        'curious', 'defensive', 'confident', 'uncertain',
        'optimistic', 'pessimistic'
    }
    
    # Sentiment indicators for rule-based fallback
    SENTIMENT_INDICATORS = {
        'positive': {
            'words': {'great', 'excellent', 'wonderful', 'amazing', 'fantastic', 'love', 'brilliant', 'perfect', 'beautiful', 'awesome'},
            'phrases': {'really good', 'very nice', 'absolutely right', 'totally agree', 'well done', 'good point'},
            'weight': 1.0
        },
        'negative': {
            'words': {'terrible', 'horrible', 'awful', 'hate', 'dislike', 'wrong', 'bad', 'poor', 'disappointing', 'frustrating'},
            'phrases': {'not good', 'really bad', 'completely wrong', 'totally disagree', 'big problem', 'serious issue'},
            'weight': -1.0
        },
        'uncertainty': {
            'words': {'maybe', 'perhaps', 'possibly', 'unsure', 'unclear', 'confusing', 'complicated'},
            'phrases': {'not sure', 'hard to say', 'difficult to know', 'might be', 'could be'},
            'weight': 0.0
        }
    }
    
    def __init__(self, llm_service: Any, config: Optional[SentimentConfig] = None):
        """
        Initialize sentiment analyzer.
        
        Args:
            llm_service: LLM service for sentiment analysis
            config: Configuration settings
        """
        self.llm_service = llm_service
        self.config = config or SentimentConfig()
        self.logger = logger
        
        # Cache for performance
        self._sentiment_cache = {} if self.config.use_caching else None
        
    def analyze_meaningful_unit(
        self,
        meaningful_unit: Any,
        episode_context: Optional[Dict[str, Any]] = None
    ) -> SentimentResult:
        """
        Perform comprehensive sentiment analysis on a MeaningfulUnit.
        
        Args:
            meaningful_unit: The MeaningfulUnit to analyze
            episode_context: Optional episode metadata for context
            
        Returns:
            SentimentResult with multi-dimensional analysis
        """
        start_time = datetime.now()
        
        # Check cache
        cache_key = f"{meaningful_unit.id}_sentiment"
        if self._sentiment_cache is not None and cache_key in self._sentiment_cache:
            self.logger.debug(f"Using cached sentiment for unit {meaningful_unit.id}")
            return self._sentiment_cache[cache_key]
        
        try:
            # Extract unit properties
            unit_text = meaningful_unit.text
            unit_id = meaningful_unit.id
            primary_speaker = meaningful_unit.primary_speaker or "Unknown"
            themes = meaningful_unit.themes or []
            unit_type = meaningful_unit.unit_type
            
            # Truncate if needed
            if self.config.max_text_length and len(unit_text) > self.config.max_text_length:
                unit_text = unit_text[:self.config.max_text_length]
                self.logger.warning(f"Truncated text for unit {unit_id} to {self.config.max_text_length} chars")
            
            # 1. Analyze overall sentiment
            overall_sentiment = self._analyze_overall_sentiment(unit_text, themes, unit_type)
            
            # 2. Analyze speaker sentiments
            speaker_sentiments = {}
            if self.config.analyze_speaker_sentiment and primary_speaker != "Unknown":
                speaker_sentiments = self._analyze_speaker_sentiments(
                    meaningful_unit, primary_speaker
                )
            
            # 3. Detect emotional moments
            emotional_moments = []
            if self.config.detect_emotional_moments:
                emotional_moments = self._detect_emotional_moments(
                    unit_text, primary_speaker
                )
            
            # 4. Analyze sentiment flow
            sentiment_flow = SentimentFlow(trajectory="stable")
            if self.config.analyze_temporal_flow:
                sentiment_flow = self._analyze_sentiment_flow(
                    meaningful_unit, emotional_moments
                )
            
            # 5. Analyze interaction dynamics
            interaction_dynamics = InteractionDynamics(
                harmony_score=0.5,
                emotional_contagion=0.0,
                dominant_interaction_type="neutral"
            )
            # Skip interaction analysis - we only have primary speaker now
            if False:
                interaction_dynamics = self._analyze_interaction_dynamics(
                    meaningful_unit, speaker_sentiments
                )
            
            # 6. Discover schema-less sentiments
            discovered_sentiments = []
            if self.config.enable_sentiment_discovery:
                discovered_sentiments = self._discover_sentiments(
                    unit_text, overall_sentiment
                )
            
            # Calculate overall confidence
            confidence = self._calculate_confidence(
                overall_sentiment,
                speaker_sentiments,
                len(emotional_moments)
            )
            
            # Build metadata
            metadata = {
                'analysis_time_ms': (datetime.now() - start_time).total_seconds() * 1000,
                'text_length': len(unit_text),
                'speaker_count': 1 if primary_speaker != "Unknown" else 0,
                'theme_count': len(themes),
                'unit_type': unit_type,
                'episode_context': episode_context
            }
            
            # Create result
            result = SentimentResult(
                unit_id=unit_id,
                overall_sentiment=overall_sentiment,
                speaker_sentiments=speaker_sentiments,
                emotional_moments=emotional_moments,
                sentiment_flow=sentiment_flow,
                interaction_dynamics=interaction_dynamics,
                discovered_sentiments=discovered_sentiments,
                confidence=confidence,
                metadata=metadata
            )
            
            # Cache result
            if self._sentiment_cache is not None:
                self._sentiment_cache[cache_key] = result
            
            self.logger.info(
                f"Completed sentiment analysis for unit {unit_id}: "
                f"{overall_sentiment.polarity} ({overall_sentiment.score:.2f})"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error analyzing sentiment for unit {meaningful_unit.id}: {e}")
            # Return neutral result on error
            return self._create_error_result(meaningful_unit.id, str(e))
    
    def _analyze_overall_sentiment(
        self,
        text: str,
        themes: List[str],
        unit_type: str
    ) -> SentimentScore:
        """
        Analyze overall sentiment of the text.
        
        Args:
            text: Text to analyze
            themes: Themes for context
            unit_type: Type of conversation unit
            
        Returns:
            SentimentScore with multi-dimensional analysis
        """
        # Build context
        context = f"Unit type: {unit_type}, Themes: {', '.join(themes)}" if themes else f"Unit type: {unit_type}"
        
        # Create prompt for LLM
        prompt = f"""Analyze the sentiment of this conversation segment.

Context: {context}

Text: {text}

Provide a comprehensive sentiment analysis including:
1. Overall polarity: positive, negative, neutral, or mixed
2. Sentiment score: -1.0 (very negative) to 1.0 (very positive)
3. Emotions present with intensity (0.0 to 1.0): joy, sadness, anger, fear, surprise, disgust, trust, anticipation, pride, shame
4. Attitudes with intensity (0.0 to 1.0): skeptical, enthusiastic, critical, supportive, curious, defensive, confident, uncertain, optimistic, pessimistic
5. Energy level: 0.0 (low energy) to 1.0 (high energy)
6. Engagement level: 0.0 (disengaged) to 1.0 (highly engaged)

Return as JSON:
{{
    "polarity": "positive|negative|neutral|mixed",
    "score": -1.0 to 1.0,
    "emotions": {{"emotion": intensity, ...}},
    "attitudes": {{"attitude": intensity, ...}},
    "energy_level": 0.0 to 1.0,
    "engagement_level": 0.0 to 1.0,
    "reasoning": "brief explanation"
}}"""
        
        try:
            response_data = self.llm_service.complete_with_options(prompt, json_mode=True)
            
            # Defensive check for response_data and content key
            if response_data and isinstance(response_data, dict) and 'content' in response_data:
                if response_data['content'] is not None:
                    result = self._parse_sentiment_response(response_data['content'])
                else:
                    self.logger.debug("LLM returned None content for sentiment analysis")
                    result = None
            else:
                self.logger.warning(f"Invalid response structure from LLM: {type(response_data)}")
                result = None
            
            if result:
                return SentimentScore(
                    polarity=result.get('polarity', 'neutral'),
                    score=float(result.get('score', 0.0)),
                    emotions=result.get('emotions', {}),
                    attitudes=result.get('attitudes', {}),
                    energy_level=float(result.get('energy_level', 0.5)),
                    engagement_level=float(result.get('engagement_level', 0.5)),
                    confidence=0.9  # High confidence for LLM analysis
                )
            else:
                # Fallback to rule-based
                return self._fallback_sentiment_analysis(text)
                
        except Exception as e:
            self.logger.error(f"Error in LLM sentiment analysis: {e}")
            return self._fallback_sentiment_analysis(text)
    
    def _analyze_speaker_sentiments(
        self,
        meaningful_unit: Any,
        primary_speaker: str
    ) -> Dict[str, SpeakerSentiment]:
        """
        Analyze sentiment for the primary speaker in the unit.
        
        Args:
            meaningful_unit: The MeaningfulUnit being analyzed
            primary_speaker: Primary speaker name
            
        Returns:
            Dictionary mapping speaker names to their sentiment analysis
        """
        speaker_sentiments = {}
        
        # Extract speaker segments
        speaker_texts = self._extract_speaker_texts(meaningful_unit)
        
        # Only analyze primary speaker
        if primary_speaker in speaker_texts and speaker_texts[primary_speaker]:
            # Combine speaker's text
            speaker_text = " ".join(speaker_texts[primary_speaker])
            speaker = primary_speaker
            
            # Analyze speaker's sentiment
            sentiment_scores = []
            emotions_found = []
            
            # Analyze each segment
            for text_segment in speaker_texts[speaker]:
                segment_sentiment = self._analyze_text_sentiment(text_segment)
                sentiment_scores.append(segment_sentiment.score)
                emotions_found.extend(list(segment_sentiment.emotions.keys()))
            
            # Calculate overall speaker sentiment
            if sentiment_scores:
                avg_score = statistics.mean(sentiment_scores)
                score_variance = statistics.variance(sentiment_scores) if len(sentiment_scores) > 1 else 0.0
                emotional_range = min(1.0, score_variance * 2)  # Normalize variance to 0-1
                
                # Determine dominant emotion
                emotion_counts = {}
                for emotion in emotions_found:
                    emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
                dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1])[0] if emotion_counts else "neutral"
                
                # Create speaker sentiment
                speaker_sentiment = SpeakerSentiment(
                    speaker_name=speaker,
                    overall_sentiment=SentimentScore(
                        polarity=self._score_to_polarity(avg_score),
                        score=avg_score,
                        confidence=0.8
                    ),
                    emotional_range=emotional_range,
                    dominant_emotion=dominant_emotion,
                    speaking_proportion=1.0  # Primary speaker has 100% proportion
                )
                
                speaker_sentiments[speaker] = speaker_sentiment
        
        return speaker_sentiments
    
    def _detect_emotional_moments(
        self,
        text: str,
        primary_speaker: str
    ) -> List[EmotionalMoment]:
        """
        Detect significant emotional moments in the text.
        
        Args:
            text: Text to analyze
            primary_speaker: Primary speaker for attribution
            
        Returns:
            List of emotional moments
        """
        prompt = f"""Identify the most emotionally significant moments in this conversation.

Text: {text}

For each emotional moment, identify:
1. The exact quote or statement
2. The emotion expressed (joy, sadness, anger, fear, surprise, etc.)
3. The intensity (0.0 to 1.0)
4. Brief context
5. What triggered it (if apparent)

Return as JSON list:
[
    {{
        "text": "exact quote",
        "emotion": "emotion type",
        "intensity": 0.0 to 1.0,
        "context": "brief context",
        "trigger": "what caused it" or null
    }}
]

Focus on moments with intensity > {self.config.moment_intensity_threshold}."""
        
        try:
            response_data = self.llm_service.complete_with_options(prompt, json_mode=True)
            moments_data = self._parse_json_response(response_data['content'])
            
            if not moments_data:
                return []
            
            # Convert to EmotionalMoment objects
            emotional_moments = []
            for moment_data in moments_data:
                if not isinstance(moment_data, dict):
                    continue
                
                # Try to determine speaker (simplified - could be enhanced)
                speaker = self._identify_speaker_for_text(
                    moment_data.get('text', ''),
                    primary_speaker
                )
                
                moment = EmotionalMoment(
                    text=moment_data.get('text', ''),
                    speaker=speaker,
                    emotion=moment_data.get('emotion', 'unknown'),
                    intensity=float(moment_data.get('intensity', 0.7)),
                    timestamp=0.0,  # Would need segment info for accurate timestamp
                    context=moment_data.get('context', ''),
                    trigger=moment_data.get('trigger')
                )
                
                if moment.intensity >= self.config.moment_intensity_threshold:
                    emotional_moments.append(moment)
            
            return emotional_moments
            
        except Exception as e:
            self.logger.error(f"Error detecting emotional moments: {e}")
            return []
    
    def _analyze_sentiment_flow(
        self,
        meaningful_unit: Any,
        emotional_moments: List[EmotionalMoment]
    ) -> SentimentFlow:
        """
        Analyze how sentiment changes throughout the unit.
        
        Args:
            meaningful_unit: The unit being analyzed
            emotional_moments: Detected emotional moments
            
        Returns:
            SentimentFlow describing temporal progression
        """
        # Simplified implementation - could be enhanced with segment-level analysis
        
        # Find peak and valley moments
        peak_moment = None
        valley_moment = None
        
        if emotional_moments:
            # Find most positive moment
            positive_moments = [m for m in emotional_moments if m.emotion in {'joy', 'pride', 'trust'}]
            if positive_moments:
                peak_moment = max(positive_moments, key=lambda m: m.intensity)
            
            # Find most negative moment
            negative_moments = [m for m in emotional_moments if m.emotion in {'sadness', 'anger', 'fear', 'disgust'}]
            if negative_moments:
                valley_moment = max(negative_moments, key=lambda m: m.intensity)
        
        # Determine trajectory
        trajectory = "stable"
        shifts = []
        variability = 0.0
        
        if emotional_moments:
            # Calculate emotional variability
            emotions = [m.emotion for m in emotional_moments]
            unique_emotions = len(set(emotions))
            variability = min(1.0, unique_emotions / 10.0)  # Normalize to 0-1
            
            # Simple trajectory detection
            if peak_moment and valley_moment:
                trajectory = "volatile"
            elif len(emotional_moments) > 3:
                trajectory = "dynamic"
        
        return SentimentFlow(
            trajectory=trajectory,
            shifts=shifts,
            peak_moment=peak_moment,
            valley_moment=valley_moment,
            variability=variability
        )
    
    def _analyze_interaction_dynamics(
        self,
        meaningful_unit: Any,
        speaker_sentiments: Dict[str, SpeakerSentiment]
    ) -> InteractionDynamics:
        """
        Analyze sentiment dynamics between speakers.
        
        Args:
            meaningful_unit: The unit being analyzed
            speaker_sentiments: Individual speaker sentiments
            
        Returns:
            InteractionDynamics describing speaker relationships
        """
        if len(speaker_sentiments) < 2:
            return InteractionDynamics(
                harmony_score=1.0,
                emotional_contagion=0.0,
                dominant_interaction_type="neutral"
            )
        
        # Calculate harmony score based on sentiment alignment
        sentiment_scores = [s.overall_sentiment.score for s in speaker_sentiments.values()]
        
        # Harmony: low variance in sentiment scores
        if len(sentiment_scores) > 1:
            score_variance = statistics.variance(sentiment_scores)
            harmony_score = max(0.0, 1.0 - score_variance)
        else:
            harmony_score = 1.0
        
        # Determine interaction type
        all_positive = all(s > 0.3 for s in sentiment_scores)
        all_negative = all(s < -0.3 for s in sentiment_scores)
        mixed = any(s > 0.3 for s in sentiment_scores) and any(s < -0.3 for s in sentiment_scores)
        
        if all_positive:
            interaction_type = "supportive"
        elif all_negative:
            interaction_type = "critical"
        elif mixed:
            interaction_type = "challenging"
        else:
            interaction_type = "neutral"
        
        # Emotional contagion (simplified - similarity in emotional patterns)
        emotional_contagion = harmony_score * 0.5  # Simplified calculation
        
        return InteractionDynamics(
            harmony_score=harmony_score,
            emotional_contagion=emotional_contagion,
            dominant_interaction_type=interaction_type,
            speaker_pairs={}
        )
    
    def _discover_sentiments(
        self,
        text: str,
        overall_sentiment: SentimentScore
    ) -> List[DiscoveredSentiment]:
        """
        Discover context-specific sentiments not in base categories.
        
        Args:
            text: Text to analyze
            overall_sentiment: Overall sentiment for context
            
        Returns:
            List of discovered sentiment types
        """
        prompt = f"""Analyze this text for unique, context-specific sentiments beyond standard emotions.

Text: {text}

Current sentiment: {overall_sentiment.polarity} (score: {overall_sentiment.score})

Identify any specialized sentiments, moods, or emotional states specific to this conversation that don't fit standard categories like joy, anger, etc. Examples might include:
- Domain-specific sentiments (e.g., "technical frustration", "creative excitement")
- Complex emotional states (e.g., "nostalgic optimism", "cautious enthusiasm")
- Situational sentiments (e.g., "deadline anxiety", "milestone pride")

Return as JSON list (max {self.config.max_discovered_types} items):
[
    {{
        "sentiment_type": "unique sentiment name",
        "description": "what this sentiment represents",
        "examples": ["quote 1", "quote 2"],
        "frequency": estimated occurrences,
        "confidence": 0.0 to 1.0
    }}
]"""
        
        try:
            response_data = self.llm_service.complete_with_options(prompt, json_mode=True)
            discovered_data = self._parse_json_response(response_data['content'])
            
            if not discovered_data:
                return []
            
            # Convert to DiscoveredSentiment objects
            discovered_sentiments = []
            for item in discovered_data[:self.config.max_discovered_types]:
                if not isinstance(item, dict):
                    continue
                
                # Handle frequency field that might be text
                frequency_value = item.get('frequency', 1)
                if isinstance(frequency_value, str):
                    # Map text frequency to numeric values
                    frequency_map = {
                        'very high': 10, 'high': 8, 'medium': 5, 'moderate': 5,
                        'low': 3, 'very low': 1, 'rare': 1, 'common': 7,
                        'frequent': 8, 'occasional': 4, 'sporadic': 2
                    }
                    frequency_text = frequency_value.lower().strip()
                    frequency = frequency_map.get(frequency_text, 5)  # Default to 5 if unknown
                else:
                    try:
                        frequency = int(frequency_value)
                    except (ValueError, TypeError):
                        frequency = 5  # Default value
                
                # Handle confidence field that might be text
                confidence_value = item.get('confidence', 0.5)
                if isinstance(confidence_value, str):
                    # Try to parse as float or use text mapping
                    confidence_text = confidence_value.lower().strip()
                    confidence_map = {
                        'very high': 0.9, 'high': 0.8, 'medium': 0.5,
                        'low': 0.3, 'very low': 0.1
                    }
                    try:
                        confidence = float(confidence_value)
                    except ValueError:
                        confidence = confidence_map.get(confidence_text, 0.5)
                else:
                    try:
                        confidence = float(confidence_value)
                    except (ValueError, TypeError):
                        confidence = 0.5
                
                sentiment = DiscoveredSentiment(
                    sentiment_type=item.get('sentiment_type', 'unknown'),
                    description=item.get('description', ''),
                    examples=item.get('examples', []),
                    frequency=frequency,
                    confidence=confidence
                )
                
                if sentiment.confidence >= self.config.min_confidence_threshold:
                    discovered_sentiments.append(sentiment)
            
            return discovered_sentiments
            
        except Exception as e:
            self.logger.error(f"Error discovering sentiments: {e}")
            return []
    
    # Helper methods
    
    def _parse_sentiment_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM sentiment response with text-to-number conversion."""
        result = self._parse_json_response(response)
        
        if not result:
            return None
            
        # Text-to-number conversion mapping
        TEXT_TO_SCORE = {
            # Common text values
            "very high": 0.9, "high": 0.8, "medium high": 0.7,
            "medium": 0.5, "moderate": 0.5,
            "medium low": 0.3, "low": 0.2, "very low": 0.1,
            # Intensity descriptors
            "extremely": 0.95, "very": 0.85, "quite": 0.75,
            "somewhat": 0.6, "slightly": 0.4, "barely": 0.2,
            # Energy/engagement specific
            "energetic": 0.8, "engaged": 0.8, "neutral": 0.5,
            "passive": 0.3, "disengaged": 0.2,
            # Polarity mappings
            "positive": 0.7, "negative": -0.7, "mixed": 0.0
        }
        
        # Convert text values to numbers for numeric fields
        numeric_fields = ['score', 'energy_level', 'engagement_level']
        for field in numeric_fields:
            if field in result and isinstance(result[field], str):
                # Try direct mapping first
                text_value = result[field].lower().strip()
                if text_value in TEXT_TO_SCORE:
                    result[field] = TEXT_TO_SCORE[text_value]
                else:
                    # Try to extract number from string (e.g., "0.8", "80%", "8/10")
                    import re
                    # Pattern to match various numeric formats
                    number_match = re.search(r'(\d+\.?\d*)\s*[/%]?\s*(\d*)', text_value)
                    if number_match:
                        num = float(number_match.group(1))
                        denom = number_match.group(2)
                        
                        # Handle percentage
                        if '%' in text_value:
                            result[field] = num / 100.0
                        # Handle fraction (e.g., "8/10")
                        elif denom:
                            result[field] = num / float(denom)
                        # Handle decimal directly
                        else:
                            result[field] = num if num <= 1.0 else num / 10.0
                    else:
                        # Default to neutral if can't parse
                        self.logger.warning(f"Could not parse text value '{text_value}' for {field}, defaulting to 0.5")
                        result[field] = 0.5
        
        # Also convert emotion intensities if present
        if 'emotions' in result and isinstance(result['emotions'], dict):
            for emotion, intensity in result['emotions'].items():
                if isinstance(intensity, str):
                    text_intensity = intensity.lower().strip()
                    if text_intensity in TEXT_TO_SCORE:
                        result['emotions'][emotion] = TEXT_TO_SCORE[text_intensity]
                    else:
                        result['emotions'][emotion] = 0.5  # Default
        
        return result
    
    def _parse_json_response(self, response: str) -> Optional[Any]:
        """Parse JSON from LLM response."""
        try:
            # Parse JSON (no cleaning needed with native JSON mode)
            return json.loads(response)
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse JSON response: {e}")
            return None
    
    def _fallback_sentiment_analysis(self, text: str) -> SentimentScore:
        """Rule-based fallback sentiment analysis."""
        text_lower = text.lower()
        
        # Count sentiment indicators
        positive_score = 0.0
        negative_score = 0.0
        
        for sentiment_type, indicators in self.SENTIMENT_INDICATORS.items():
            if sentiment_type == 'uncertainty':
                continue
                
            # Count words
            for word in indicators['words']:
                count = text_lower.count(word)
                if sentiment_type == 'positive':
                    positive_score += count * 0.1
                else:
                    negative_score += count * 0.1
            
            # Count phrases
            for phrase in indicators['phrases']:
                count = text_lower.count(phrase)
                if sentiment_type == 'positive':
                    positive_score += count * 0.2
                else:
                    negative_score += count * 0.2
        
        # Calculate final score
        total_score = positive_score - negative_score
        normalized_score = max(-1.0, min(1.0, total_score / 10.0))
        
        # Determine polarity
        if normalized_score > 0.1:
            polarity = "positive"
        elif normalized_score < -0.1:
            polarity = "negative"
        else:
            polarity = "neutral"
        
        return SentimentScore(
            polarity=polarity,
            score=normalized_score,
            confidence=0.5  # Lower confidence for rule-based
        )
    
    def _extract_speaker_texts(self, meaningful_unit: Any) -> Dict[str, List[str]]:
        """Extract text segments for each speaker."""
        speaker_texts = {}
        
        # This is simplified - in reality, would need to parse segments
        # For now, return full text for each speaker
        # Only extract for primary speaker
        if meaningful_unit.primary_speaker and meaningful_unit.primary_speaker != "Unknown":
            speaker = meaningful_unit.primary_speaker
            speaker_texts[speaker] = [meaningful_unit.text]  # Simplified
        
        return speaker_texts
    
    def _analyze_text_sentiment(self, text: str) -> SentimentScore:
        """Analyze sentiment of a text segment."""
        # Simplified - reuse overall sentiment analysis
        return self._analyze_overall_sentiment(text, [], "segment")
    
    def _score_to_polarity(self, score: float) -> str:
        """Convert numerical score to polarity."""
        if score > 0.1:
            return "positive"
        elif score < -0.1:
            return "negative"
        else:
            return "neutral"
    
    def _identify_speaker_for_text(
        self,
        text: str,
        primary_speaker: str
    ) -> str:
        """Identify likely speaker for a text snippet."""
        # Simplified implementation - just return primary speaker
        return primary_speaker if primary_speaker else "Unknown"
    
    def _calculate_confidence(
        self,
        overall_sentiment: SentimentScore,
        speaker_sentiments: Dict[str, SpeakerSentiment],
        emotional_moment_count: int
    ) -> float:
        """Calculate overall analysis confidence."""
        confidences = [overall_sentiment.confidence]
        
        # Add speaker sentiment confidences
        for speaker_sentiment in speaker_sentiments.values():
            confidences.append(speaker_sentiment.overall_sentiment.confidence)
        
        # Boost confidence if we found emotional moments
        if emotional_moment_count > 0:
            confidences.append(0.9)
        
        # Return average confidence
        return statistics.mean(confidences) if confidences else 0.5
    
    def _create_error_result(self, unit_id: str, error_message: str) -> SentimentResult:
        """Create a neutral result for error cases."""
        return SentimentResult(
            unit_id=unit_id,
            overall_sentiment=SentimentScore(
                polarity="neutral",
                score=0.0,
                confidence=0.0
            ),
            speaker_sentiments={},
            emotional_moments=[],
            sentiment_flow=SentimentFlow(trajectory="unknown"),
            interaction_dynamics=InteractionDynamics(
                harmony_score=0.5,
                emotional_contagion=0.0,
                dominant_interaction_type="unknown"
            ),
            discovered_sentiments=[],
            confidence=0.0,
            metadata={'error': error_message}
        )
    
    def aggregate_episode_sentiment(
        self,
        unit_sentiments: List[SentimentResult]
    ) -> Dict[str, Any]:
        """
        Aggregate sentiment across all MeaningfulUnits in an episode.
        
        Args:
            unit_sentiments: List of sentiment results from all units
            
        Returns:
            Episode-level sentiment summary
        """
        if not unit_sentiments:
            return {
                'overall_polarity': 'neutral',
                'average_score': 0.0,
                'emotional_arc': 'flat',
                'key_emotions': [],
                'speaker_sentiments': {}
            }
        
        # Aggregate scores
        scores = [result.overall_sentiment.score for result in unit_sentiments]
        polarities = [result.overall_sentiment.polarity for result in unit_sentiments]
        
        # Aggregate emotions
        all_emotions = {}
        for result in unit_sentiments:
            for emotion, intensity in result.overall_sentiment.emotions.items():
                if emotion not in all_emotions:
                    all_emotions[emotion] = []
                all_emotions[emotion].append(intensity)
        
        # Calculate averages
        avg_emotions = {
            emotion: statistics.mean(intensities)
            for emotion, intensities in all_emotions.items()
        }
        
        # Find key emotions
        key_emotions = sorted(
            avg_emotions.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Determine emotional arc
        if len(scores) > 1:
            first_third = statistics.mean(scores[:len(scores)//3])
            last_third = statistics.mean(scores[-(len(scores)//3):])
            
            if last_third > first_third + 0.2:
                emotional_arc = "ascending"
            elif last_third < first_third - 0.2:
                emotional_arc = "descending"
            else:
                emotional_arc = "stable"
        else:
            emotional_arc = "single_point"
        
        # Aggregate speaker sentiments
        speaker_sentiments = {}
        for result in unit_sentiments:
            for speaker, sentiment in result.speaker_sentiments.items():
                if speaker not in speaker_sentiments:
                    speaker_sentiments[speaker] = []
                speaker_sentiments[speaker].append(sentiment.overall_sentiment.score)
        
        avg_speaker_sentiments = {
            speaker: statistics.mean(scores)
            for speaker, scores in speaker_sentiments.items()
        }
        
        return {
            'overall_polarity': statistics.mode(polarities) if polarities else 'neutral',
            'average_score': statistics.mean(scores),
            'score_variance': statistics.variance(scores) if len(scores) > 1 else 0.0,
            'emotional_arc': emotional_arc,
            'key_emotions': key_emotions,
            'speaker_sentiments': avg_speaker_sentiments,
            'total_units_analyzed': len(unit_sentiments)
        }