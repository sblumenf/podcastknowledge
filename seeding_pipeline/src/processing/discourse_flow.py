"""
Discourse flow tracking for podcast conversations.

This module tracks the temporal flow of concepts through conversations,
identifying introduction points, development arcs, and resolution patterns.
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict
import numpy as np

from src.core.models import Entity, Insight, Segment

logger = logging.getLogger(__name__)


class DiscourseFlowTracker:
    """
    Tracks the temporal flow of concepts through podcast conversations.
    Identifies introduction, development, peak, and resolution phases.
    Maps concept trajectories and narrative patterns.
    """
    
    def __init__(self):
        """Initialize the discourse flow tracker."""
        self.logger = logger
        
    def build_concept_timeline(
        self,
        segments: List[Segment],
        entities: List[Entity]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Create timeline of when each concept appears.
        
        Args:
            segments: List of conversation segments
            entities: List of entities found in the conversation
            
        Returns:
            Dictionary mapping entity IDs to their timeline data
        """
        timelines = {}
        
        for entity in entities:
            entity_timeline = []
            entity_name_lower = entity.name.lower()
            
            for segment_idx, segment in enumerate(segments):
                segment_text_lower = segment.text.lower()
                
                # Check if entity is mentioned in this segment
                if entity_name_lower in segment_text_lower:
                    # Determine mention type based on position and context
                    mention_type = self._determine_mention_type(
                        segment_idx, len(segments), entity_timeline
                    )
                    
                    # Calculate context density (simplified - count of entity mentions)
                    context_density = segment_text_lower.count(entity_name_lower) / len(segment.text.split())
                    
                    timeline_entry = {
                        "segment_index": segment_idx,
                        "timestamp": segment.start_time,
                        "mention_type": mention_type,
                        "context_density": min(1.0, context_density * 10),  # Normalize to 0-1
                        "speaker": segment.speaker if hasattr(segment, 'speaker') else "Unknown"
                    }
                    
                    entity_timeline.append(timeline_entry)
            
            if entity_timeline:
                timelines[entity.id] = {
                    "entity_id": entity.id,
                    "timeline": entity_timeline
                }
        
        return timelines
    
    def _determine_mention_type(
        self,
        segment_idx: int,
        total_segments: int,
        previous_mentions: List[Dict]
    ) -> str:
        """
        Determine the type of mention based on position and history.
        
        Args:
            segment_idx: Current segment index
            total_segments: Total number of segments
            previous_mentions: Previous mentions of this entity
            
        Returns:
            Mention type string
        """
        position_ratio = segment_idx / total_segments
        
        # First mention
        if not previous_mentions:
            return "introduction"
        
        # Near the end
        if position_ratio > 0.8:
            return "conclusion"
        
        # Long gap since last mention
        if previous_mentions:
            last_segment = previous_mentions[-1]["segment_index"]
            if segment_idx - last_segment > total_segments * 0.2:
                return "callback"
        
        # Default to development
        return "development"
    
    def analyze_concept_lifecycle(
        self,
        concept_timeline: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Identify lifecycle phases of each concept.
        
        Args:
            concept_timeline: Timeline data for a single concept
            
        Returns:
            Dictionary with lifecycle analysis
        """
        timeline = concept_timeline.get("timeline", [])
        
        if not timeline:
            return {
                "lifecycle_pattern": "absent",
                "introduction_segment": None,
                "peak_segment": None,
                "total_duration": 0,
                "development_intensity": 0
            }
        
        # Find introduction (first mention)
        introduction_segment = timeline[0]["segment_index"]
        
        # Find peak (segment with highest context density)
        peak_segment = max(timeline, key=lambda x: x["context_density"])["segment_index"]
        
        # Calculate total duration
        first_timestamp = timeline[0]["timestamp"]
        last_timestamp = timeline[-1]["timestamp"]
        total_duration = last_timestamp - first_timestamp
        
        # Calculate development intensity
        development_mentions = [t for t in timeline if t["mention_type"] == "development"]
        development_intensity = len(development_mentions) / len(timeline) if timeline else 0
        
        # Determine lifecycle pattern
        lifecycle_pattern = self._determine_lifecycle_pattern(timeline)
        
        return {
            "lifecycle_pattern": lifecycle_pattern,
            "introduction_segment": introduction_segment,
            "peak_segment": peak_segment,
            "total_duration": total_duration,
            "development_intensity": development_intensity
        }
    
    def _determine_lifecycle_pattern(self, timeline: List[Dict]) -> str:
        """
        Determine the lifecycle pattern of a concept.
        
        Args:
            timeline: Timeline entries for the concept
            
        Returns:
            Pattern name
        """
        if len(timeline) < 2:
            return "brief-mention"
        
        mention_types = [t["mention_type"] for t in timeline]
        
        # Check for standard patterns
        if mention_types[0] == "introduction" and mention_types[-1] == "conclusion":
            if "development" in mention_types:
                return "introduce-develop-conclude"
            else:
                return "introduce-conclude"
        
        if mention_types.count("callback") > 1:
            return "recurring-theme"
        
        if all(t["mention_type"] == "development" for t in mention_types[1:-1]):
            return "introduce-develop-integrate"
        
        return "fragmented"
    
    def detect_discourse_patterns(
        self,
        concept_timelines: Dict[str, List[Dict]]
    ) -> List[Dict[str, Any]]:
        """
        Identify common discourse patterns.
        
        Args:
            concept_timelines: All concept timelines
            
        Returns:
            List of detected patterns with confidence scores
        """
        patterns = []
        
        # Analyze overall structure
        if not concept_timelines:
            return patterns
        
        # Extract all timeline entries
        all_entries = []
        for entity_id, timeline_data in concept_timelines.items():
            for entry in timeline_data.get("timeline", []):
                entry_with_entity = entry.copy()
                entry_with_entity["entity_id"] = entity_id
                all_entries.append(entry_with_entity)
        
        # Sort by segment index
        all_entries.sort(key=lambda x: x["segment_index"])
        
        # Detect linear progression
        linear_score = self._detect_linear_progression(all_entries)
        if linear_score > 0.6:
            patterns.append({
                "pattern_type": "linear_progression",
                "confidence": linear_score,
                "description": "Concepts introduced sequentially and developed in order"
            })
        
        # Detect circular return
        circular_score = self._detect_circular_pattern(concept_timelines)
        if circular_score > 0.5:
            patterns.append({
                "pattern_type": "circular_return",
                "confidence": circular_score,
                "description": "Discussion returns to initial concepts"
            })
        
        # Detect hub and spoke
        hub_score, hub_entities = self._detect_hub_pattern(concept_timelines)
        if hub_score > 0.6:
            patterns.append({
                "pattern_type": "hub_and_spoke",
                "confidence": hub_score,
                "description": "Central concepts with radiating discussions",
                "hub_entities": hub_entities
            })
        
        # Detect parallel threads
        parallel_score = self._detect_parallel_threads(concept_timelines)
        if parallel_score > 0.5:
            patterns.append({
                "pattern_type": "parallel_threads",
                "confidence": parallel_score,
                "description": "Multiple concepts developed simultaneously"
            })
        
        # Detect convergence
        convergence_score = self._detect_convergence(all_entries)
        if convergence_score > 0.5:
            patterns.append({
                "pattern_type": "convergence",
                "confidence": convergence_score,
                "description": "Multiple concepts merge into unified discussion"
            })
        
        return patterns
    
    def _detect_linear_progression(self, all_entries: List[Dict]) -> float:
        """Detect if concepts are introduced and developed linearly."""
        if len(all_entries) < 3:
            return 0.0
        
        # Check if introductions happen in first half
        introductions = [e for e in all_entries if e["mention_type"] == "introduction"]
        if not introductions:
            return 0.0
        
        first_half_boundary = len(all_entries) // 2
        intro_in_first_half = sum(1 for e in introductions if all_entries.index(e) < first_half_boundary)
        
        return intro_in_first_half / len(introductions)
    
    def _detect_circular_pattern(self, concept_timelines: Dict[str, List[Dict]]) -> float:
        """Detect if discussion returns to initial concepts."""
        circular_concepts = 0
        total_concepts = 0
        
        for timeline_data in concept_timelines.values():
            timeline = timeline_data.get("timeline", [])
            if len(timeline) > 2:
                total_concepts += 1
                # Check if concept appears in both first and last quarters
                total_segments = timeline[-1]["segment_index"] - timeline[0]["segment_index"] + 1
                if total_segments > 4:
                    first_quarter = timeline[0]["segment_index"] + total_segments // 4
                    last_quarter = timeline[0]["segment_index"] + 3 * total_segments // 4
                    
                    has_early = any(t["segment_index"] <= first_quarter for t in timeline)
                    has_late = any(t["segment_index"] >= last_quarter for t in timeline)
                    
                    if has_early and has_late:
                        circular_concepts += 1
        
        return circular_concepts / total_concepts if total_concepts > 0 else 0.0
    
    def _detect_hub_pattern(self, concept_timelines: Dict[str, List[Dict]]) -> Tuple[float, List[str]]:
        """Detect hub and spoke pattern with central concepts."""
        # Count mentions for each entity
        mention_counts = {}
        for entity_id, timeline_data in concept_timelines.items():
            mention_counts[entity_id] = len(timeline_data.get("timeline", []))
        
        if not mention_counts:
            return 0.0, []
        
        # Find potential hubs (top 20% by mention count)
        sorted_entities = sorted(mention_counts.items(), key=lambda x: x[1], reverse=True)
        hub_threshold = sorted_entities[0][1] * 0.7  # 70% of max mentions
        
        hub_entities = [entity_id for entity_id, count in sorted_entities if count >= hub_threshold]
        
        # Calculate hub score based on distribution
        if len(hub_entities) >= 1 and len(hub_entities) <= 3:
            # Good hub pattern: 1-3 central concepts
            hub_score = 0.8
        else:
            hub_score = 0.3
        
        return hub_score, hub_entities[:3]
    
    def _detect_parallel_threads(self, concept_timelines: Dict[str, List[Dict]]) -> float:
        """Detect if multiple concepts are developed in parallel."""
        if len(concept_timelines) < 2:
            return 0.0
        
        # Group timelines by segment ranges
        segment_ranges = []
        for timeline_data in concept_timelines.values():
            timeline = timeline_data.get("timeline", [])
            if timeline:
                min_segment = min(t["segment_index"] for t in timeline)
                max_segment = max(t["segment_index"] for t in timeline)
                segment_ranges.append((min_segment, max_segment))
        
        # Count overlapping ranges
        overlaps = 0
        for i in range(len(segment_ranges)):
            for j in range(i + 1, len(segment_ranges)):
                range1 = segment_ranges[i]
                range2 = segment_ranges[j]
                # Check if ranges overlap
                if range1[0] <= range2[1] and range2[0] <= range1[1]:
                    overlaps += 1
        
        max_overlaps = len(segment_ranges) * (len(segment_ranges) - 1) / 2
        return overlaps / max_overlaps if max_overlaps > 0 else 0.0
    
    def _detect_convergence(self, all_entries: List[Dict]) -> float:
        """Detect if multiple concepts converge."""
        if len(all_entries) < 4:
            return 0.0
        
        # Divide timeline into quarters
        total_entries = len(all_entries)
        quarter_size = total_entries // 4
        
        # Count unique entities in each quarter
        quarters_entities = []
        for q in range(4):
            start_idx = q * quarter_size
            end_idx = (q + 1) * quarter_size if q < 3 else total_entries
            quarter_entries = all_entries[start_idx:end_idx]
            unique_entities = set(e["entity_id"] for e in quarter_entries)
            quarters_entities.append(unique_entities)
        
        # Check if diversity decreases (convergence)
        if len(quarters_entities[0]) > len(quarters_entities[-1]) * 1.5:
            return 0.8
        
        return 0.2
    
    def calculate_concept_momentum(
        self,
        timeline: List[Dict[str, Any]],
        window_size: int = 3
    ) -> List[float]:
        """
        Measure how concept importance changes over time.
        
        Args:
            timeline: Timeline entries for a concept
            window_size: Size of sliding window
            
        Returns:
            List of momentum values for each time point
        """
        if len(timeline) < 2:
            return [0.0] * len(timeline)
        
        momentum_values = []
        
        for i in range(len(timeline)):
            # Get window boundaries
            start = max(0, i - window_size // 2)
            end = min(len(timeline), i + window_size // 2 + 1)
            
            # Calculate mention density in window
            window_entries = timeline[start:end]
            if len(window_entries) > 1:
                # Calculate time span
                time_span = window_entries[-1]["timestamp"] - window_entries[0]["timestamp"]
                if time_span > 0:
                    # Mentions per second
                    density = len(window_entries) / time_span
                else:
                    density = len(window_entries)
                
                # Weight by context density
                avg_context_density = sum(e["context_density"] for e in window_entries) / len(window_entries)
                weighted_density = density * avg_context_density
            else:
                weighted_density = window_entries[0]["context_density"] if window_entries else 0
            
            momentum_values.append(weighted_density)
        
        # Calculate rate of change
        momentum_changes = []
        for i in range(len(momentum_values)):
            if i == 0:
                momentum_changes.append(0.0)
            else:
                change = momentum_values[i] - momentum_values[i-1]
                momentum_changes.append(change)
        
        return momentum_changes
    
    def detect_narrative_arcs(
        self,
        segments: List[Segment],
        concept_timelines: Dict[str, List[Dict]]
    ) -> Dict[str, Any]:
        """
        Identify story-like structures in discussions.
        
        Args:
            segments: List of segments
            concept_timelines: Timeline data for all concepts
            
        Returns:
            Dictionary describing detected narrative arcs
        """
        arcs = {
            "primary_arc": None,
            "arc_confidence": 0.0,
            "turning_points": [],
            "resolution_status": "unknown"
        }
        
        if not concept_timelines or not segments:
            return arcs
        
        # Analyze problem-solution pattern
        problem_solution_score, ps_data = self._detect_problem_solution_arc(segments, concept_timelines)
        
        # Analyze journey pattern
        journey_score, journey_data = self._detect_journey_arc(concept_timelines)
        
        # Analyze debate pattern
        debate_score, debate_data = self._detect_debate_arc(segments)
        
        # Analyze discovery pattern
        discovery_score, discovery_data = self._detect_discovery_arc(concept_timelines)
        
        # Select primary arc
        arc_scores = [
            ("problem_solution", problem_solution_score, ps_data),
            ("journey", journey_score, journey_data),
            ("debate", debate_score, debate_data),
            ("discovery", discovery_score, discovery_data)
        ]
        
        primary_arc = max(arc_scores, key=lambda x: x[1])
        
        if primary_arc[1] > 0.5:  # Confidence threshold
            arcs["primary_arc"] = primary_arc[0]
            arcs["arc_confidence"] = primary_arc[1]
            arcs["turning_points"] = primary_arc[2].get("turning_points", [])
            arcs["resolution_status"] = primary_arc[2].get("resolution_status", "unknown")
        
        return arcs
    
    def _detect_problem_solution_arc(
        self,
        segments: List[Segment],
        concept_timelines: Dict[str, List[Dict]]
    ) -> Tuple[float, Dict]:
        """Detect problem-solution narrative arc."""
        # Simplified detection based on segment progression
        problem_keywords = ["problem", "issue", "challenge", "difficulty", "concern"]
        solution_keywords = ["solution", "solve", "fix", "address", "resolve"]
        
        # Count keywords in different parts
        total_segments = len(segments)
        first_third = total_segments // 3
        last_third = 2 * total_segments // 3
        
        problem_count_early = 0
        solution_count_late = 0
        
        for i, segment in enumerate(segments):
            text_lower = segment.text.lower()
            if i < first_third:
                problem_count_early += sum(1 for kw in problem_keywords if kw in text_lower)
            if i >= last_third:
                solution_count_late += sum(1 for kw in solution_keywords if kw in text_lower)
        
        # Calculate score
        score = min(1.0, (problem_count_early + solution_count_late) / 10)
        
        data = {
            "turning_points": [first_third] if score > 0.5 else [],
            "resolution_status": "resolved" if solution_count_late > 0 else "unresolved"
        }
        
        return score, data
    
    def _detect_journey_arc(self, concept_timelines: Dict[str, List[Dict]]) -> Tuple[float, Dict]:
        """Detect journey/sequential exploration arc."""
        # Check for sequential concept introduction
        introduction_segments = []
        for timeline_data in concept_timelines.values():
            timeline = timeline_data.get("timeline", [])
            introductions = [t for t in timeline if t["mention_type"] == "introduction"]
            if introductions:
                introduction_segments.append(introductions[0]["segment_index"])
        
        if len(introduction_segments) < 3:
            return 0.0, {}
        
        # Check if introductions are sequential
        introduction_segments.sort()
        sequential_score = 0.0
        for i in range(1, len(introduction_segments)):
            if introduction_segments[i] > introduction_segments[i-1]:
                sequential_score += 1
        
        sequential_score = sequential_score / (len(introduction_segments) - 1)
        
        data = {
            "turning_points": introduction_segments[1:-1],  # Middle introductions
            "resolution_status": "journey_complete"
        }
        
        return sequential_score * 0.8, data
    
    def _detect_debate_arc(self, segments: List[Segment]) -> Tuple[float, Dict]:
        """Detect debate/contrasting viewpoints arc."""
        # Look for contrasting language
        contrast_keywords = ["however", "but", "although", "conversely", "on the other hand", "disagree"]
        
        contrast_count = 0
        contrast_segments = []
        
        for i, segment in enumerate(segments):
            text_lower = segment.text.lower()
            segment_contrasts = sum(1 for kw in contrast_keywords if kw in text_lower)
            if segment_contrasts > 0:
                contrast_count += segment_contrasts
                contrast_segments.append(i)
        
        # Normalize score
        score = min(1.0, contrast_count / (len(segments) * 0.2))
        
        data = {
            "turning_points": contrast_segments[:3],  # First few contrasts
            "resolution_status": "perspectives_presented"
        }
        
        return score, data
    
    def _detect_discovery_arc(self, concept_timelines: Dict[str, List[Dict]]) -> Tuple[float, Dict]:
        """Detect discovery/unknown to known arc."""
        # Look for progression in concept development
        development_progression = 0
        total_concepts = 0
        
        for timeline_data in concept_timelines.values():
            timeline = timeline_data.get("timeline", [])
            if len(timeline) > 2:
                total_concepts += 1
                # Check if context density increases
                early_density = sum(t["context_density"] for t in timeline[:len(timeline)//2])
                late_density = sum(t["context_density"] for t in timeline[len(timeline)//2:])
                
                if late_density > early_density * 1.2:  # 20% increase
                    development_progression += 1
        
        score = development_progression / total_concepts if total_concepts > 0 else 0.0
        
        data = {
            "turning_points": [],
            "resolution_status": "discovery_made" if score > 0.5 else "exploring"
        }
        
        return score, data
    
    def track_concept_interactions(
        self,
        timelines: Dict[str, List[Dict]],
        segments: List[Segment]
    ) -> List[Dict[str, Any]]:
        """
        Track when concepts interact or merge.
        
        Args:
            timelines: All concept timelines
            segments: List of segments
            
        Returns:
            List of concept interactions
        """
        interactions = []
        
        # Group timeline entries by segment
        segment_concepts = defaultdict(list)
        for entity_id, timeline_data in timelines.items():
            for entry in timeline_data.get("timeline", []):
                segment_concepts[entry["segment_index"]].append(entity_id)
        
        # Find co-occurrences
        for segment_idx, concepts in segment_concepts.items():
            if len(concepts) > 1:
                # All pairs in this segment interact
                for i in range(len(concepts)):
                    for j in range(i + 1, len(concepts)):
                        interaction = {
                            "segment_index": segment_idx,
                            "timestamp": segments[segment_idx].start_time if segment_idx < len(segments) else 0,
                            "entity_1": concepts[i],
                            "entity_2": concepts[j],
                            "interaction_type": self._determine_interaction_type(
                                concepts[i], concepts[j], segment_idx, timelines
                            )
                        }
                        interactions.append(interaction)
        
        return interactions
    
    def _determine_interaction_type(
        self,
        entity1: str,
        entity2: str,
        segment_idx: int,
        timelines: Dict[str, List[Dict]]
    ) -> str:
        """
        Determine the type of interaction between two concepts.
        
        Args:
            entity1: First entity ID
            entity2: Second entity ID
            segment_idx: Segment where interaction occurs
            timelines: All timelines
            
        Returns:
            Interaction type string
        """
        # Get timelines for both entities
        timeline1 = timelines.get(entity1, {}).get("timeline", [])
        timeline2 = timelines.get(entity2, {}).get("timeline", [])
        
        # Check if both are being introduced
        intro1 = any(t["segment_index"] == segment_idx and t["mention_type"] == "introduction" for t in timeline1)
        intro2 = any(t["segment_index"] == segment_idx and t["mention_type"] == "introduction" for t in timeline2)
        
        if intro1 and intro2:
            return "co_introduction"
        
        # Check if one leads to another
        if intro2 and any(t["segment_index"] < segment_idx for t in timeline1):
            return "causal_link"
        
        # Check if they appear together frequently
        co_occurrences = sum(1 for seg_concepts in timelines.values() 
                           if entity1 in seg_concepts and entity2 in seg_concepts)
        
        if co_occurrences > 3:
            return "synthesis"
        
        return "contrast"
    
    def analyze_transitions(
        self,
        segments: List[Segment],
        concept_timelines: Dict[str, List[Dict]]
    ) -> List[Dict[str, Any]]:
        """
        Identify how conversation moves between topics.
        
        Args:
            segments: List of segments
            concept_timelines: Timeline data for all concepts
            
        Returns:
            List of transition analyses
        """
        transitions = []
        
        # Get concepts by segment
        segment_concepts = defaultdict(set)
        for entity_id, timeline_data in concept_timelines.items():
            for entry in timeline_data.get("timeline", []):
                segment_concepts[entry["segment_index"]].add(entity_id)
        
        # Analyze transitions between adjacent segments
        for i in range(len(segments) - 1):
            current_concepts = segment_concepts.get(i, set())
            next_concepts = segment_concepts.get(i + 1, set())
            
            if current_concepts or next_concepts:
                transition = {
                    "from_segment": i,
                    "to_segment": i + 1,
                    "transition_type": self._classify_transition(
                        current_concepts, next_concepts
                    ),
                    "smoothness_score": self._calculate_transition_smoothness(
                        current_concepts, next_concepts
                    ),
                    "concepts_carried": list(current_concepts & next_concepts),
                    "concepts_dropped": list(current_concepts - next_concepts),
                    "concepts_introduced": list(next_concepts - current_concepts)
                }
                
                # Look for explicit transition markers
                if i + 1 < len(segments):
                    transition["explicit_marker"] = self._find_transition_marker(
                        segments[i + 1].text
                    )
                
                transitions.append(transition)
        
        return transitions
    
    def _classify_transition(self, current: set, next: set) -> str:
        """Classify the type of transition between segments."""
        if not current:
            return "introduction"
        if not next:
            return "conclusion"
        
        overlap = len(current & next)
        
        if overlap == len(current) == len(next):
            return "continuation"
        elif overlap > 0 and len(next - current) > 0:
            return "expansion"
        elif overlap > 0 and len(current - next) > 0:
            return "focus"
        elif overlap == 0:
            return "pivot"
        else:
            return "bridge"
    
    def _calculate_transition_smoothness(self, current: set, next: set) -> float:
        """Calculate how smooth a transition is."""
        if not current or not next:
            return 0.5
        
        overlap = len(current & next)
        total = len(current | next)
        
        return overlap / total if total > 0 else 0.0
    
    def _find_transition_marker(self, text: str) -> Optional[str]:
        """Find explicit transition markers in text."""
        transition_markers = [
            "speaking of which", "on that note", "similarly", "however",
            "moving on", "furthermore", "in addition", "consequently",
            "therefore", "as a result", "in contrast", "meanwhile"
        ]
        
        text_lower = text.lower()
        for marker in transition_markers:
            if marker in text_lower:
                return marker
        
        return None
    
    def generate_flow_visualization_data(
        self,
        flow_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare data for timeline visualization.
        
        Args:
            flow_analysis: Complete flow analysis data
            
        Returns:
            Visualization-ready data structure
        """
        viz_data = {
            "concept_streams": [],
            "interaction_points": [],
            "narrative_phases": [],
            "key_transitions": [],
            "momentum_data": []
        }
        
        # Process concept timelines into streams
        for entity_id, timeline_data in flow_analysis.get("concept_timelines", {}).items():
            stream = {
                "entity_id": entity_id,
                "entity_name": flow_analysis.get("entity_names", {}).get(entity_id, entity_id),
                "timeline": timeline_data.get("timeline", []),
                "lifecycle": flow_analysis.get("concept_lifecycles", {}).get(entity_id, {}),
                "color": self._generate_stream_color(entity_id)
            }
            viz_data["concept_streams"].append(stream)
        
        # Add interaction points
        for interaction in flow_analysis.get("concept_interactions", []):
            viz_data["interaction_points"].append({
                "timestamp": interaction["timestamp"],
                "entities": [interaction["entity_1"], interaction["entity_2"]],
                "type": interaction["interaction_type"]
            })
        
        # Add narrative phases
        narrative_arc = flow_analysis.get("narrative_arc", {})
        if narrative_arc.get("primary_arc"):
            viz_data["narrative_phases"] = [
                {
                    "type": narrative_arc["primary_arc"],
                    "confidence": narrative_arc["arc_confidence"],
                    "turning_points": narrative_arc.get("turning_points", [])
                }
            ]
        
        # Add key transitions
        for transition in flow_analysis.get("transitions", [])[:10]:  # Top 10
            if transition["transition_type"] in ["pivot", "expansion"]:
                viz_data["key_transitions"].append({
                    "from_segment": transition["from_segment"],
                    "to_segment": transition["to_segment"],
                    "type": transition["transition_type"],
                    "marker": transition.get("explicit_marker", "")
                })
        
        # Add momentum data for key concepts
        for entity_id, momentum in flow_analysis.get("concept_momentum", {}).items()[:5]:  # Top 5
            viz_data["momentum_data"].append({
                "entity_id": entity_id,
                "momentum_values": momentum
            })
        
        return viz_data
    
    def _generate_stream_color(self, entity_id: str) -> str:
        """Generate a color for visualization based on entity ID."""
        # Simple hash-based color generation
        hash_value = hash(entity_id)
        hue = (hash_value % 360) / 360
        saturation = 0.6 + (hash_value % 40) / 100
        lightness = 0.5
        
        # Convert HSL to hex (simplified)
        import colorsys
        rgb = colorsys.hls_to_rgb(hue, lightness, saturation)
        hex_color = "#{:02x}{:02x}{:02x}".format(
            int(rgb[0] * 255),
            int(rgb[1] * 255),
            int(rgb[2] * 255)
        )
        
        return hex_color
    
    def enrich_entities_with_flow_data(
        self,
        entities: List[Entity],
        flow_analysis: Dict[str, Any]
    ) -> List[Entity]:
        """
        Add discourse flow information to entities.
        
        Args:
            entities: List of entities to enrich
            flow_analysis: Flow analysis results
            
        Returns:
            Enriched entities
        """
        # Get lifecycles and momentum data
        lifecycles = flow_analysis.get("concept_lifecycles", {})
        momentum_data = flow_analysis.get("concept_momentum", {})
        
        for entity in entities:
            # Add lifecycle data
            if entity.id in lifecycles:
                lifecycle = lifecycles[entity.id]
                entity.discourse_lifecycle = lifecycle.get("lifecycle_pattern", "unknown")
                entity.discourse_intensity = lifecycle.get("development_intensity", 0.0)
                
            # Add momentum data
            if entity.id in momentum_data:
                momentum_values = momentum_data[entity.id]
                if momentum_values:
                    # Average momentum
                    entity.discourse_momentum = sum(momentum_values) / len(momentum_values)
                else:
                    entity.discourse_momentum = 0.0
            
            # Determine discourse role
            entity.discourse_role = self._determine_entity_discourse_role(
                entity.id, flow_analysis
            )
        
        return entities
    
    def _determine_entity_discourse_role(
        self,
        entity_id: str,
        flow_analysis: Dict[str, Any]
    ) -> str:
        """Determine the primary discourse role of an entity."""
        lifecycle = flow_analysis.get("concept_lifecycles", {}).get(entity_id, {})
        pattern = lifecycle.get("lifecycle_pattern", "")
        
        if pattern == "introduce-develop-conclude":
            return "main_theme"
        elif pattern == "recurring-theme":
            return "connecting_thread"
        elif pattern == "brief-mention":
            return "supporting_detail"
        elif "hub" in str(flow_analysis.get("discourse_patterns", [])):
            # Check if this entity is a hub
            for pattern in flow_analysis.get("discourse_patterns", []):
                if pattern.get("pattern_type") == "hub_and_spoke":
                    if entity_id in pattern.get("hub_entities", []):
                        return "central_concept"
        
        return "participant"
    
    def generate_flow_summary(self, flow_analysis: Dict[str, Any]) -> str:
        """
        Create human-readable summary of discourse flow.
        
        Args:
            flow_analysis: Complete flow analysis
            
        Returns:
            Text summary
        """
        summary_parts = []
        
        # Summarize discourse patterns
        patterns = flow_analysis.get("discourse_patterns", [])
        if patterns:
            primary_pattern = max(patterns, key=lambda p: p["confidence"])
            summary_parts.append(
                f"The discussion follows a {primary_pattern['pattern_type'].replace('_', ' ')} "
                f"pattern ({primary_pattern['confidence']:.0%} confidence)."
            )
        
        # Summarize narrative arc
        arc = flow_analysis.get("narrative_arc", {})
        if arc.get("primary_arc"):
            arc_type = arc["primary_arc"].replace("_", " ")
            summary_parts.append(
                f"The narrative structure is primarily a {arc_type} arc, "
                f"with {arc.get('resolution_status', 'unknown')} resolution."
            )
        
        # Summarize key transitions
        transitions = flow_analysis.get("transitions", [])
        pivots = [t for t in transitions if t["transition_type"] == "pivot"]
        if pivots:
            summary_parts.append(
                f"The conversation includes {len(pivots)} major topic shifts."
            )
        
        # Summarize concept development
        lifecycles = flow_analysis.get("concept_lifecycles", {})
        main_themes = [k for k, v in lifecycles.items() 
                      if v.get("lifecycle_pattern") == "introduce-develop-conclude"]
        if main_themes:
            summary_parts.append(
                f"{len(main_themes)} concepts are fully developed from introduction to conclusion."
            )
        
        return " ".join(summary_parts) if summary_parts else "Unable to generate flow summary."
    
    def analyze_episode_flow(
        self,
        segments: List[Segment],
        entities: List[Entity],
        insights: List[Insight]
    ) -> Dict[str, Any]:
        """
        Main method to analyze complete episode flow.
        
        Args:
            segments: List of segments
            entities: List of entities
            insights: List of insights
            
        Returns:
            Complete flow analysis
        """
        logger.info("Starting discourse flow analysis")
        
        # Build concept timelines
        concept_timelines = self.build_concept_timeline(segments, entities)
        logger.info(f"Built timelines for {len(concept_timelines)} concepts")
        
        # Analyze lifecycles
        concept_lifecycles = {}
        concept_momentum = {}
        
        for entity_id, timeline_data in concept_timelines.items():
            # Lifecycle analysis
            lifecycle = self.analyze_concept_lifecycle(timeline_data)
            concept_lifecycles[entity_id] = lifecycle
            
            # Momentum analysis
            timeline = timeline_data.get("timeline", [])
            if timeline:
                momentum = self.calculate_concept_momentum(timeline)
                concept_momentum[entity_id] = momentum
        
        # Detect discourse patterns
        discourse_patterns = self.detect_discourse_patterns(concept_timelines)
        logger.info(f"Detected {len(discourse_patterns)} discourse patterns")
        
        # Detect narrative arcs
        narrative_arc = self.detect_narrative_arcs(segments, concept_timelines)
        
        # Track concept interactions
        concept_interactions = self.track_concept_interactions(concept_timelines, segments)
        logger.info(f"Found {len(concept_interactions)} concept interactions")
        
        # Analyze transitions
        transitions = self.analyze_transitions(segments, concept_timelines)
        
        # Create entity name mapping
        entity_names = {e.id: e.name for e in entities}
        
        # Compile results
        flow_analysis = {
            "concept_timelines": concept_timelines,
            "concept_lifecycles": concept_lifecycles,
            "concept_momentum": concept_momentum,
            "discourse_patterns": discourse_patterns,
            "narrative_arc": narrative_arc,
            "concept_interactions": concept_interactions,
            "transitions": transitions,
            "entity_names": entity_names
        }
        
        logger.info("Discourse flow analysis completed")
        
        return flow_analysis