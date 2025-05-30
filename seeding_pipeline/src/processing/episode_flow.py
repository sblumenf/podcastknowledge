"""Within-episode discourse flow analysis."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter
import numpy as np
from scipy.spatial.distance import cosine

from src.core.models import Entity, Segment
# Provider imports removed - using services directly
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EpisodeFlowAnalyzer:
    """
    Tracks how concepts flow within a single episode.
    Maps introduction, development, and resolution of ideas.
    Works entirely within episode boundaries.
    """
    
    def __init__(self, embedding_provider: Optional[Any] = None):
        """
        Initialize the episode flow analyzer.
        
        Args:
            embedding_provider: Provider for calculating semantic similarity
        """
        self.embedding_provider = embedding_provider
    
    def classify_segment_transitions(self, segments: List[Segment]) -> List[Dict]:
        """
        Classify how conversation moves between segments.
        
        Args:
            segments: List of segments in order
            
        Returns:
            List of transition classifications
        """
        transitions = []
        
        for i in range(len(segments) - 1):
            current_segment = segments[i]
            next_segment = segments[i + 1]
            
            # Calculate semantic similarity if embeddings available
            semantic_similarity = self._calculate_semantic_similarity(
                current_segment.text, 
                next_segment.text
            )
            
            # Detect transition type
            transition_type = self._detect_transition_type(
                current_segment, 
                next_segment,
                semantic_similarity
            )
            
            # Look for explicit transition markers
            explicit_marker = self._find_transition_marker(next_segment.text)
            
            # Calculate smoothness score
            smoothness_score = self._calculate_smoothness(
                semantic_similarity,
                transition_type,
                explicit_marker
            )
            
            transitions.append({
                "from_segment": i,
                "to_segment": i + 1,
                "transition_type": transition_type,
                "semantic_similarity": semantic_similarity,
                "explicit_marker": explicit_marker,
                "smoothness_score": smoothness_score
            })
        
        return transitions
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts."""
        if not self.embedding_provider:
            return 0.5  # Default neutral similarity
        
        try:
            emb1 = np.array(self.embedding_provider.embed_text(text1))
            emb2 = np.array(self.embedding_provider.embed_text(text2))
            return 1 - cosine(emb1, emb2)
        except:
            return 0.5
    
    def _detect_transition_type(
        self, 
        current: Segment, 
        next_seg: Segment,
        similarity: float
    ) -> str:
        """Detect the type of transition between segments."""
        # Check for speaker change
        speaker_changed = current.speaker != next_seg.speaker
        
        # High similarity suggests continuation or expansion
        if similarity > 0.8:
            return "continuation"
        elif similarity > 0.6:
            return "expansion"
        elif similarity > 0.4:
            if speaker_changed:
                return "pivot"
            else:
                return "return"
        else:
            return "jump"
    
    def _find_transition_marker(self, text: str) -> Optional[str]:
        """Find explicit transition markers in text."""
        markers = {
            "continuation": ["furthermore", "moreover", "additionally", "also"],
            "expansion": ["speaking of which", "on that note", "similarly"],
            "pivot": ["however", "on the other hand", "but", "alternatively"],
            "jump": ["anyway", "moving on", "let's shift to", "changing topics"],
            "return": ["going back to", "as I was saying", "to return to"]
        }
        
        text_lower = text.lower()
        for marker_type, phrases in markers.items():
            for phrase in phrases:
                if phrase in text_lower[:100]:  # Check first 100 chars
                    return phrase
        
        return None
    
    def _calculate_smoothness(
        self, 
        similarity: float, 
        transition_type: str,
        explicit_marker: Optional[str]
    ) -> float:
        """Calculate how smooth a transition is."""
        base_scores = {
            "continuation": 0.9,
            "expansion": 0.8,
            "return": 0.7,
            "pivot": 0.6,
            "jump": 0.3
        }
        
        score = base_scores.get(transition_type, 0.5)
        
        # Adjust based on similarity
        score = (score + similarity) / 2
        
        # Bonus for explicit markers
        if explicit_marker:
            score = min(score + 0.1, 1.0)
        
        return score
    
    def track_concept_introductions(
        self, 
        segments: List[Segment], 
        entities: List[Entity]
    ) -> Dict[str, Dict]:
        """
        Identify how concepts are introduced.
        
        Args:
            segments: List of segments
            entities: List of entities to track
            
        Returns:
            Dictionary mapping entity IDs to introduction data
        """
        introductions = {}
        
        # Track which segments mention each entity
        entity_mentions = self._find_entity_mentions(segments, entities)
        
        for entity in entities:
            if entity.id not in entity_mentions:
                continue
            
            first_mention = entity_mentions[entity.id][0]
            segment_idx = first_mention["segment_index"]
            segment = segments[segment_idx]
            
            # Detect introduction type
            intro_type = self._detect_introduction_type(
                segment.text,
                entity.name,
                segment_idx,
                segments
            )
            
            # Assess initial depth
            initial_depth = self._assess_initial_depth(
                segment.text,
                entity.name,
                first_mention["context"]
            )
            
            introductions[entity.id] = {
                "introduction_segment": segment_idx,
                "introduction_type": intro_type,
                "introduction_context": first_mention["context"],
                "initial_depth": initial_depth,
                "introducer": segment.speaker
            }
        
        return introductions
    
    def _find_entity_mentions(
        self, 
        segments: List[Segment], 
        entities: List[Entity]
    ) -> Dict[str, List[Dict]]:
        """Find all mentions of entities in segments."""
        mentions = defaultdict(list)
        
        for i, segment in enumerate(segments):
            text_lower = segment.text.lower()
            
            for entity in entities:
                if entity.name.lower() in text_lower:
                    # Find context around mention
                    start_idx = text_lower.find(entity.name.lower())
                    context_start = max(0, start_idx - 50)
                    context_end = min(len(segment.text), start_idx + len(entity.name) + 50)
                    context = segment.text[context_start:context_end]
                    
                    mentions[entity.id].append({
                        "segment_index": i,
                        "position": start_idx,
                        "context": context,
                        "speaker": segment.speaker
                    })
        
        return dict(mentions)
    
    def _detect_introduction_type(
        self, 
        text: str, 
        entity_name: str,
        segment_idx: int,
        all_segments: List[Segment]
    ) -> str:
        """Detect how a concept is introduced."""
        text_lower = text.lower()
        entity_lower = entity_name.lower()
        
        # Check for planned introduction
        planned_phrases = ["today we'll discuss", "let's talk about", "our topic is"]
        for phrase in planned_phrases:
            if phrase in text_lower and entity_lower in text_lower:
                return "planned"
        
        # Check for responsive introduction (question in previous segment)
        if segment_idx > 0:
            prev_text = all_segments[segment_idx - 1].text.lower()
            if "?" in prev_text and entity_lower in text_lower:
                return "responsive"
        
        # Check for tangential (brief mention)
        entity_position = text_lower.find(entity_lower)
        if entity_position > len(text_lower) * 0.7:  # Mentioned late in segment
            return "tangential"
        
        # Default to organic
        return "organic"
    
    def _assess_initial_depth(
        self, 
        text: str, 
        entity_name: str,
        context: str
    ) -> str:
        """Assess the initial depth of discussion."""
        context_lower = context.lower()
        
        # Indicators of deep discussion
        deep_indicators = ["because", "therefore", "specifically", "in detail"]
        # Indicators of moderate discussion
        moderate_indicators = ["for example", "such as", "including"]
        # Indicators of surface discussion
        surface_indicators = ["mention", "briefly", "touch on"]
        
        deep_count = sum(1 for ind in deep_indicators if ind in context_lower)
        moderate_count = sum(1 for ind in moderate_indicators if ind in context_lower)
        surface_count = sum(1 for ind in surface_indicators if ind in context_lower)
        
        if deep_count > 0:
            return "deep"
        elif moderate_count > 0:
            return "moderate"
        else:
            return "surface"
    
    def map_concept_development(
        self, 
        entity: Entity, 
        segments: List[Segment]
    ) -> Dict:
        """
        Track how each concept develops through episode.
        
        Args:
            entity: Entity to track
            segments: List of segments
            
        Returns:
            Development timeline with phase markers
        """
        # Find all mentions
        mentions = []
        for i, segment in enumerate(segments):
            if entity.name.lower() in segment.text.lower():
                mentions.append({
                    "segment_index": i,
                    "segment": segment
                })
        
        if not mentions:
            return {"phases": [], "timeline": []}
        
        # Analyze each mention for development phase
        phases = []
        for i, mention in enumerate(mentions):
            phase = self._identify_development_phase(
                mention["segment"].text,
                entity.name,
                i,
                len(mentions)
            )
            
            phases.append({
                "segment_index": mention["segment_index"],
                "phase": phase,
                "timestamp": mention["segment"].start_time
            })
        
        # Create development summary
        development_summary = {
            "phases": phases,
            "timeline": self._create_development_timeline(phases),
            "total_mentions": len(mentions),
            "development_pattern": self._identify_development_pattern(phases)
        }
        
        return development_summary
    
    def _identify_development_phase(
        self, 
        text: str, 
        entity_name: str,
        mention_index: int,
        total_mentions: int
    ) -> str:
        """Identify which development phase this mention represents."""
        text_lower = text.lower()
        
        # First mention is usually introduction
        if mention_index == 0:
            return "introduction"
        
        # Check for elaboration indicators
        if any(phrase in text_lower for phrase in ["explain", "detail", "describe"]):
            return "elaboration"
        
        # Check for application indicators
        if any(phrase in text_lower for phrase in ["example", "instance", "case"]):
            return "application"
        
        # Check for challenge indicators
        if any(phrase in text_lower for phrase in ["however", "but", "challenge", "question"]):
            return "challenge"
        
        # Check for integration indicators
        if any(phrase in text_lower for phrase in ["connect", "relate", "together with"]):
            return "integration"
        
        # Last mention might be resolution
        if mention_index == total_mentions - 1:
            if any(phrase in text_lower for phrase in ["conclude", "summary", "therefore"]):
                return "resolution"
        
        # Default to elaboration
        return "elaboration"
    
    def _create_development_timeline(self, phases: List[Dict]) -> List[str]:
        """Create a simplified development timeline."""
        if not phases:
            return []
        
        timeline = []
        for phase in phases:
            phase_name = phase["phase"]
            if not timeline or timeline[-1] != phase_name:
                timeline.append(phase_name)
        
        return timeline
    
    def _identify_development_pattern(self, phases: List[Dict]) -> str:
        """Identify the overall development pattern."""
        if not phases:
            return "none"
        
        phase_sequence = [p["phase"] for p in phases]
        
        # Check for complete development
        expected_phases = ["introduction", "elaboration", "application", "resolution"]
        if all(phase in phase_sequence for phase in expected_phases):
            return "complete"
        
        # Check for question-driven
        if phase_sequence.count("challenge") > 2:
            return "question-driven"
        
        # Check for example-heavy
        if phase_sequence.count("application") > len(phase_sequence) / 3:
            return "example-heavy"
        
        # Check for circular
        if len(phase_sequence) > 3 and phase_sequence[0] == phase_sequence[-1]:
            return "circular"
        
        return "standard"
    
    def analyze_conversation_momentum(
        self, 
        segments: List[Segment], 
        window_size: int = 5
    ) -> List[Dict]:
        """
        Track energy and pace of discussion.
        
        Args:
            segments: List of segments
            window_size: Size of sliding window for analysis
            
        Returns:
            Momentum curve with annotations
        """
        momentum_data = []
        
        for i in range(len(segments)):
            # Define window
            window_start = max(0, i - window_size // 2)
            window_end = min(len(segments), i + window_size // 2 + 1)
            window_segments = segments[window_start:window_end]
            
            # Calculate momentum factors
            factors = {
                "new_concepts": self._calculate_new_concept_rate(window_segments, i),
                "speaker_turns": self._calculate_speaker_turn_frequency(window_segments),
                "questions": self._calculate_question_density(window_segments),
                "insights": self._calculate_insight_rate(window_segments),
                "intensity": self._calculate_emotional_intensity(window_segments)
            }
            
            # Calculate overall momentum
            momentum = sum(factors.values()) / len(factors)
            
            momentum_data.append({
                "segment_index": i,
                "momentum": momentum,
                "factors": factors,
                "timestamp": segments[i].start_time,
                "annotation": self._annotate_momentum(momentum, factors)
            })
        
        return momentum_data
    
    def _calculate_new_concept_rate(self, segments: List[Segment], current_idx: int) -> float:
        """Calculate rate of new concept introduction."""
        # Simplified: look for capitalized words as potential concepts
        concepts_seen = set()
        new_concepts = 0
        
        for segment in segments:
            words = segment.text.split()
            for word in words:
                if word[0].isupper() and len(word) > 3:
                    if word not in concepts_seen:
                        new_concepts += 1
                        concepts_seen.add(word)
        
        return min(new_concepts / max(len(segments), 1), 1.0)
    
    def _calculate_speaker_turn_frequency(self, segments: List[Segment]) -> float:
        """Calculate frequency of speaker turns."""
        if len(segments) <= 1:
            return 0.0
        
        turns = 0
        for i in range(1, len(segments)):
            if segments[i].speaker != segments[i-1].speaker:
                turns += 1
        
        return turns / (len(segments) - 1)
    
    def _calculate_question_density(self, segments: List[Segment]) -> float:
        """Calculate density of questions."""
        total_sentences = 0
        questions = 0
        
        for segment in segments:
            sentences = segment.text.split('.')
            total_sentences += len(sentences)
            questions += segment.text.count('?')
        
        return questions / max(total_sentences, 1)
    
    def _calculate_insight_rate(self, segments: List[Segment]) -> float:
        """Calculate rate of insight generation."""
        # Look for insight indicators
        insight_phrases = ["realize", "understand", "insight", "discovered", "learned"]
        
        insight_count = 0
        for segment in segments:
            text_lower = segment.text.lower()
            for phrase in insight_phrases:
                if phrase in text_lower:
                    insight_count += 1
                    break
        
        return insight_count / max(len(segments), 1)
    
    def _calculate_emotional_intensity(self, segments: List[Segment]) -> float:
        """Calculate emotional intensity of discussion."""
        # Look for emotion indicators
        emotion_words = ["amazing", "terrible", "love", "hate", "excited", "worried", 
                        "fantastic", "awful", "brilliant", "stupid"]
        
        emotion_count = 0
        total_words = 0
        
        for segment in segments:
            words = segment.text.lower().split()
            total_words += len(words)
            emotion_count += sum(1 for word in words if word in emotion_words)
        
        return min(emotion_count / max(total_words / 100, 1), 1.0)
    
    def _annotate_momentum(self, momentum: float, factors: Dict[str, float]) -> str:
        """Create annotation for momentum level."""
        if momentum > 0.8:
            return "high_energy"
        elif momentum > 0.6:
            # Find dominant factor
            dominant = max(factors.items(), key=lambda x: x[1])
            return f"elevated_{dominant[0]}"
        elif momentum > 0.4:
            return "steady"
        elif momentum > 0.2:
            return "low_energy"
        else:
            return "minimal_activity"
    
    def track_topic_depth(
        self, 
        segments: List[Segment], 
        entities: List[Entity]
    ) -> Dict[str, float]:
        """
        Measure how deeply each topic is explored.
        
        Args:
            segments: List of segments
            entities: List of entities representing topics
            
        Returns:
            Depth score 0-1 for each major topic
        """
        topic_depths = {}
        
        for entity in entities:
            # Calculate depth indicators
            indicators = {
                "time_spent": self._calculate_time_spent(segments, entity),
                "related_concepts": self._count_related_concepts(segments, entity, entities),
                "detail_level": self._assess_detail_level(segments, entity),
                "examples_provided": self._count_examples(segments, entity),
                "questions_ratio": self._calculate_question_answer_ratio(segments, entity)
            }
            
            # Calculate overall depth score
            depth_score = sum(indicators.values()) / len(indicators)
            topic_depths[entity.name] = depth_score
        
        return topic_depths
    
    def _calculate_time_spent(self, segments: List[Segment], entity: Entity) -> float:
        """Calculate proportion of time spent on topic."""
        total_duration = sum(s.end_time - s.start_time for s in segments)
        topic_duration = 0
        
        for segment in segments:
            if entity.name.lower() in segment.text.lower():
                topic_duration += segment.end_time - segment.start_time
        
        return min(topic_duration / max(total_duration, 1), 1.0)
    
    def _count_related_concepts(
        self, 
        segments: List[Segment], 
        entity: Entity,
        all_entities: List[Entity]
    ) -> float:
        """Count how many related concepts are introduced."""
        related_count = 0
        entity_segments = []
        
        # Find segments mentioning the entity
        for i, segment in enumerate(segments):
            if entity.name.lower() in segment.text.lower():
                entity_segments.append(i)
        
        # Check other entities in same segments
        for other_entity in all_entities:
            if other_entity.id == entity.id:
                continue
            
            for i, segment in enumerate(segments):
                if i in entity_segments and other_entity.name.lower() in segment.text.lower():
                    related_count += 1
                    break
        
        return min(related_count / 10, 1.0)  # Normalize to max 10 related concepts
    
    def _assess_detail_level(self, segments: List[Segment], entity: Entity) -> float:
        """Assess level of detail in explanations."""
        detail_indicators = ["specifically", "in detail", "precisely", "exactly", 
                           "step by step", "broken down", "detailed"]
        
        detail_count = 0
        mention_count = 0
        
        for segment in segments:
            if entity.name.lower() in segment.text.lower():
                mention_count += 1
                text_lower = segment.text.lower()
                for indicator in detail_indicators:
                    if indicator in text_lower:
                        detail_count += 1
                        break
        
        return detail_count / max(mention_count, 1)
    
    def _count_examples(self, segments: List[Segment], entity: Entity) -> float:
        """Count examples and evidence provided."""
        example_indicators = ["for example", "for instance", "such as", "like",
                            "case in point", "consider", "take the case"]
        
        example_count = 0
        
        for segment in segments:
            if entity.name.lower() in segment.text.lower():
                text_lower = segment.text.lower()
                for indicator in example_indicators:
                    if indicator in text_lower:
                        example_count += 1
        
        return min(example_count / 5, 1.0)  # Normalize to max 5 examples
    
    def _calculate_question_answer_ratio(self, segments: List[Segment], entity: Entity) -> float:
        """Calculate ratio of questions answered vs raised."""
        questions_raised = 0
        questions_answered = 0
        
        for i, segment in enumerate(segments):
            if entity.name.lower() in segment.text.lower():
                # Count questions
                questions_raised += segment.text.count('?')
                
                # Look for answer indicators in next segments
                if i < len(segments) - 1:
                    next_text = segments[i + 1].text.lower()
                    if any(phrase in next_text for phrase in ["the answer", "that's because", "this means"]):
                        questions_answered += 1
        
        if questions_raised == 0:
            return 0.5  # Neutral if no questions
        
        return questions_answered / questions_raised
    
    def detect_circular_references(self, concept_timeline: Dict[str, List]) -> List[Dict]:
        """
        Find when conversation returns to earlier concepts.
        
        Args:
            concept_timeline: Timeline of concept appearances
            
        Returns:
            List of circular reference detections
        """
        circular_refs = []
        
        for concept, timeline in concept_timeline.items():
            if len(timeline) < 2:
                continue
            
            # Look for gaps indicating circular return
            for i in range(1, len(timeline)):
                current = timeline[i]
                first = timeline[0]
                
                # Check if there's a significant gap
                segment_gap = current["segment_index"] - timeline[i-1]["segment_index"]
                
                if segment_gap > 5:  # Significant gap before return
                    circular_refs.append({
                        "concept": concept,
                        "first_mention": {
                            "segment": first["segment_index"],
                            "timestamp": first.get("timestamp", 0)
                        },
                        "return_mention": {
                            "segment": current["segment_index"],
                            "timestamp": current.get("timestamp", 0)
                        },
                        "evolution": self._describe_concept_evolution(timeline[:i], timeline[i:]),
                        "closure_achieved": self._check_closure(timeline[i:])
                    })
        
        return circular_refs
    
    def _describe_concept_evolution(self, early_mentions: List, later_mentions: List) -> str:
        """Describe how concept evolved between mentions."""
        # Simplified evolution description
        if len(early_mentions) == 1 and len(later_mentions) == 1:
            return "Initial mention → Brief return"
        elif len(early_mentions) > len(later_mentions):
            return "Initial exploration → Quick revisit"
        elif len(later_mentions) > len(early_mentions):
            return "Initial mention → Deeper exploration"
        else:
            return "Initial discussion → Balanced return"
    
    def _check_closure(self, later_mentions: List) -> bool:
        """Check if concept achieved closure in later mentions."""
        # Simple heuristic: closure if mentioned multiple times
        # and contains resolution language
        if len(later_mentions) < 2:
            return False
        
        # In real implementation, would check for resolution language
        return len(later_mentions) >= 2
    
    def analyze_concept_resolution(
        self, 
        concepts: Dict[str, Dict], 
        final_segments: List[Segment]
    ) -> Dict[str, Dict]:
        """
        Determine if/how concepts are resolved.
        
        Args:
            concepts: Concept tracking data
            final_segments: Last segments of episode
            
        Returns:
            Resolution analysis for each concept
        """
        resolutions = {}
        
        # Define what constitutes "final segments"
        final_segment_indices = [s.segment_index for s in final_segments[-5:]]
        
        for concept_id, concept_data in concepts.items():
            # Check if concept appears in final segments
            final_mentions = self._find_final_mentions(
                concept_id, 
                concept_data,
                final_segment_indices
            )
            
            # Determine resolution type
            resolution_type = self._determine_resolution_type(
                final_mentions,
                final_segments
            )
            
            # Calculate resolution quality
            quality_score = self._calculate_resolution_quality(
                resolution_type,
                final_mentions
            )
            
            resolutions[concept_id] = {
                "resolution_type": resolution_type,
                "quality_score": quality_score,
                "final_state": self._describe_final_state(resolution_type, final_mentions)
            }
        
        return resolutions
    
    def _find_final_mentions(
        self, 
        concept_id: str, 
        concept_data: Dict,
        final_indices: List[int]
    ) -> List[Dict]:
        """Find mentions of concept in final segments."""
        final_mentions = []
        
        # This would need actual mention data
        # For now, return empty list
        return final_mentions
    
    def _determine_resolution_type(
        self, 
        final_mentions: List[Dict],
        final_segments: List[Segment]
    ) -> str:
        """Determine how concept was resolved."""
        if not final_mentions:
            return "abandoned"
        
        # Check final segment text for resolution indicators
        resolution_text = " ".join(s.text for s in final_segments[-2:]).lower()
        
        if "therefore" in resolution_text or "conclude" in resolution_text:
            return "answered"
        elif "future" in resolution_text or "next time" in resolution_text:
            return "deferred"
        elif "partially" in resolution_text or "some aspects" in resolution_text:
            return "partial"
        elif "instead" in resolution_text or "actually" in resolution_text:
            return "transformed"
        
        return "partial"
    
    def _calculate_resolution_quality(self, resolution_type: str, final_mentions: List) -> float:
        """Calculate quality score for resolution."""
        base_scores = {
            "answered": 1.0,
            "partial": 0.7,
            "transformed": 0.6,
            "deferred": 0.5,
            "abandoned": 0.2
        }
        
        score = base_scores.get(resolution_type, 0.5)
        
        # Adjust based on number of final mentions
        if len(final_mentions) > 2:
            score = min(score + 0.1, 1.0)
        
        return score
    
    def _describe_final_state(self, resolution_type: str, final_mentions: List) -> str:
        """Describe the final state of the concept."""
        descriptions = {
            "answered": "Concept fully addressed and concluded",
            "partial": "Some aspects resolved, others remain open",
            "deferred": "Explicitly marked for future discussion",
            "abandoned": "Dropped without explicit resolution",
            "transformed": "Evolved into different question or concept"
        }
        
        return descriptions.get(resolution_type, "Unknown resolution state")
    
    def generate_episode_flow_summary(self, flow_analysis: Dict) -> Dict:
        """
        Create structured summary of episode flow.
        
        Args:
            flow_analysis: Complete flow analysis data
            
        Returns:
            Structured flow summary
        """
        summary = {
            "opening_concepts": self._extract_opening_concepts(flow_analysis),
            "core_developments": self._extract_core_developments(flow_analysis),
            "key_transitions": self._extract_key_transitions(flow_analysis),
            "unresolved_threads": self._extract_unresolved_threads(flow_analysis),
            "circular_themes": self._extract_circular_themes(flow_analysis),
            "flow_pattern": self._determine_flow_pattern(flow_analysis),
            "narrative_coherence": self._calculate_narrative_coherence(flow_analysis)
        }
        
        return summary
    
    def _extract_opening_concepts(self, flow_analysis: Dict) -> List[str]:
        """Extract concepts introduced in opening."""
        introductions = flow_analysis.get("concept_introductions", {})
        opening_concepts = []
        
        for entity_id, intro_data in introductions.items():
            if intro_data.get("introduction_segment", 999) < 3:  # First 3 segments
                opening_concepts.append(entity_id)
        
        return opening_concepts
    
    def _extract_core_developments(self, flow_analysis: Dict) -> List[Dict]:
        """Extract core concept developments."""
        developments = []
        
        # This would analyze development patterns
        # For now, return placeholder
        return developments
    
    def _extract_key_transitions(self, flow_analysis: Dict) -> List[Dict]:
        """Extract most important transitions."""
        transitions = flow_analysis.get("transitions", [])
        
        # Filter for significant transitions
        key_transitions = [
            t for t in transitions 
            if t.get("transition_type") in ["pivot", "jump"] or 
            t.get("smoothness_score", 1) < 0.5
        ]
        
        return key_transitions[:5]  # Top 5 transitions
    
    def _extract_unresolved_threads(self, flow_analysis: Dict) -> List[str]:
        """Extract concepts that weren't resolved."""
        resolutions = flow_analysis.get("resolutions", {})
        
        unresolved = [
            concept_id for concept_id, res_data in resolutions.items()
            if res_data.get("resolution_type") in ["abandoned", "deferred"]
        ]
        
        return unresolved
    
    def _extract_circular_themes(self, flow_analysis: Dict) -> List[Dict]:
        """Extract themes that came full circle."""
        circular_refs = flow_analysis.get("circular_references", [])
        
        # Filter for significant circular themes
        significant = [
            ref for ref in circular_refs
            if ref.get("closure_achieved", False)
        ]
        
        return significant
    
    def _determine_flow_pattern(self, flow_analysis: Dict) -> str:
        """Determine overall flow pattern."""
        transitions = flow_analysis.get("transitions", [])
        
        if not transitions:
            return "unknown"
        
        # Count transition types
        type_counts = Counter(t.get("transition_type") for t in transitions)
        
        # Determine pattern based on dominant transition type
        if type_counts.get("continuation", 0) > len(transitions) * 0.6:
            return "linear_progression"
        elif type_counts.get("return", 0) > len(transitions) * 0.3:
            return "spiral"
        elif type_counts.get("jump", 0) > len(transitions) * 0.3:
            return "branching"
        else:
            return "mixed"
    
    def _calculate_narrative_coherence(self, flow_analysis: Dict) -> float:
        """Calculate overall narrative coherence score."""
        factors = []
        
        # Transition smoothness
        transitions = flow_analysis.get("transitions", [])
        if transitions:
            avg_smoothness = sum(t.get("smoothness_score", 0.5) for t in transitions) / len(transitions)
            factors.append(avg_smoothness)
        
        # Resolution completeness
        resolutions = flow_analysis.get("resolutions", {})
        if resolutions:
            resolved_ratio = sum(
                1 for r in resolutions.values() 
                if r.get("resolution_type") in ["answered", "partial"]
            ) / len(resolutions)
            factors.append(resolved_ratio)
        
        # Circular closure
        circular_refs = flow_analysis.get("circular_references", [])
        if circular_refs:
            closure_ratio = sum(1 for r in circular_refs if r.get("closure_achieved")) / len(circular_refs)
            factors.append(closure_ratio)
        
        return sum(factors) / len(factors) if factors else 0.5
    
    def analyze_speaker_contribution_flow(self, segments: List[Segment]) -> Dict[str, Dict]:
        """
        Track how each speaker contributes to flow.
        
        Args:
            segments: List of segments
            
        Returns:
            Speaker contribution analysis
        """
        speaker_data = defaultdict(lambda: {
            "segments": [],
            "concept_introductions": 0,
            "questions": 0,
            "statements": 0,
            "transitions_initiated": 0,
            "flow_role": "unknown"
        })
        
        # Analyze each segment
        for i, segment in enumerate(segments):
            speaker = segment.speaker
            speaker_data[speaker]["segments"].append(i)
            
            # Count questions vs statements
            questions = segment.text.count('?')
            speaker_data[speaker]["questions"] += questions
            
            # Approximate statement count
            sentences = len([s for s in segment.text.split('.') if s.strip()])
            speaker_data[speaker]["statements"] += max(sentences - questions, 0)
            
            # Check for concept introductions (simplified)
            if i == 0 or (i > 0 and self._introduces_new_concept(segment, segments[:i])):
                speaker_data[speaker]["concept_introductions"] += 1
            
            # Check for transition initiation
            if i > 0 and segments[i-1].speaker != speaker:
                speaker_data[speaker]["transitions_initiated"] += 1
        
        # Determine role for each speaker
        for speaker, data in speaker_data.items():
            data["flow_role"] = self._determine_speaker_role(data)
            
            # Calculate ratios
            total_utterances = data["questions"] + data["statements"]
            if total_utterances > 0:
                data["question_ratio"] = data["questions"] / total_utterances
            else:
                data["question_ratio"] = 0
            
            # Calculate introduction rate
            if len(data["segments"]) > 0:
                data["introduction_rate"] = data["concept_introductions"] / len(data["segments"])
            else:
                data["introduction_rate"] = 0
        
        return dict(speaker_data)
    
    def _introduces_new_concept(self, segment: Segment, previous_segments: List[Segment]) -> bool:
        """Check if segment introduces new concept."""
        # Simplified: look for capitalized words not seen before
        previous_text = " ".join(s.text for s in previous_segments).lower()
        
        words = segment.text.split()
        for word in words:
            if word[0].isupper() and len(word) > 3:
                if word.lower() not in previous_text:
                    return True
        
        return False
    
    def _determine_speaker_role(self, speaker_data: Dict) -> str:
        """Determine speaker's role in conversation flow."""
        question_ratio = speaker_data.get("question_ratio", 0)
        introduction_rate = speaker_data.get("introduction_rate", 0)
        
        if question_ratio > 0.5:
            return "interviewer"
        elif introduction_rate > 0.3:
            return "expert"
        elif speaker_data["transitions_initiated"] > 5:
            return "moderator"
        else:
            return "participant"
    
    def calculate_segment_flow_importance(
        self, 
        segment: Segment, 
        flow_analysis: Dict
    ) -> float:
        """
        Score segment importance based on flow role.
        
        Args:
            segment: Segment to score
            flow_analysis: Complete flow analysis
            
        Returns:
            Importance score 0-1
        """
        importance_factors = []
        
        # Check if segment introduces major concepts
        introductions = flow_analysis.get("concept_introductions", {})
        introduces_major = any(
            intro.get("introduction_segment") == segment.segment_index
            for intro in introductions.values()
        )
        if introduces_major:
            importance_factors.append(1.0)
        
        # Check if segment contains key transitions
        transitions = flow_analysis.get("transitions", [])
        key_transition = any(
            t.get("from_segment") == segment.segment_index and
            t.get("transition_type") in ["pivot", "jump"]
            for t in transitions
        )
        if key_transition:
            importance_factors.append(0.8)
        
        # Check if segment achieves resolutions
        resolutions = flow_analysis.get("resolutions", {})
        has_resolution = any(
            res.get("resolution_segment") == segment.segment_index
            for res in resolutions.values()
        )
        if has_resolution:
            importance_factors.append(0.9)
        
        # Check if segment bridges topics
        if self._is_bridge_segment(segment, flow_analysis):
            importance_factors.append(0.7)
        
        # Check for flow turning points
        momentum = flow_analysis.get("momentum", [])
        is_turning_point = self._is_turning_point(segment.segment_index, momentum)
        if is_turning_point:
            importance_factors.append(0.8)
        
        # Calculate final importance
        if not importance_factors:
            return 0.3  # Base importance
        
        return sum(importance_factors) / len(importance_factors)
    
    def _is_bridge_segment(self, segment: Segment, flow_analysis: Dict) -> bool:
        """Check if segment bridges different topics."""
        # Simplified check: segment mentions multiple concepts
        concept_count = 0
        
        introductions = flow_analysis.get("concept_introductions", {})
        for entity_id in introductions:
            # This would check if entity is mentioned in segment
            # For now, use simplified logic
            concept_count += 1
        
        return concept_count > 2
    
    def _is_turning_point(self, segment_index: int, momentum: List[Dict]) -> bool:
        """Check if segment represents a momentum turning point."""
        if not momentum or segment_index >= len(momentum) - 1:
            return False
        
        current = momentum[segment_index].get("momentum", 0.5)
        next_val = momentum[segment_index + 1].get("momentum", 0.5)
        
        # Check for significant change
        return abs(next_val - current) > 0.3