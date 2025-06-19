"""Speaker mapping post-processing module.

This module identifies and updates generic speaker names in the Neo4j database
using a 3-step approach: pattern matching, YouTube API, and LLM as fallback.
"""

import re
from typing import Dict, List, Optional, Tuple, Any
import json
from datetime import datetime
from pathlib import Path

from src.utils.logging import get_logger
from src.storage.graph_storage import GraphStorageService
from src.services.llm import LLMService
from src.core.config import PipelineConfig
from src.services.youtube_description_fetcher import YouTubeDescriptionFetcher

logger = get_logger(__name__)


class SpeakerMapper:
    """Maps generic speaker names to real names using multiple identification methods."""
    
    def __init__(self, storage: GraphStorageService, llm_service: LLMService, config: PipelineConfig):
        """Initialize the speaker mapper.
        
        Args:
            storage: Neo4j storage instance
            llm_service: LLM service for fallback identification
            config: Configuration object
        """
        self.storage = storage
        self.llm_service = llm_service
        self.config = config
        self.youtube_client = None  # Will be initialized lazily
        self._cache = {}  # Cache for API responses
        
        logger.info("Initialized SpeakerMapper")
    
    def process_episode(self, episode_id: str) -> Dict[str, str]:
        """Process a single episode to identify generic speakers.
        
        Args:
            episode_id: The episode ID to process
            
        Returns:
            Dict mapping generic names to identified names
        """
        logger.info(f"Processing episode {episode_id} for speaker identification")
        
        # Get episode details and speakers
        episode_data = self._get_episode_data(episode_id)
        if not episode_data:
            logger.warning(f"Episode {episode_id} not found")
            return {}
        
        generic_speakers = self._identify_generic_speakers(episode_data)
        if not generic_speakers:
            logger.info(f"No generic speakers found in episode {episode_id}")
            return {}
        
        logger.info(f"Found {len(generic_speakers)} generic speakers to identify")
        
        # Try identification methods in order
        mappings = {}
        
        # Step 1: Pattern matching from episode description
        mappings.update(self._match_from_episode_description(episode_data, generic_speakers))
        remaining = [s for s in generic_speakers if s not in mappings]
        
        if remaining:
            # Step 2: Pattern matching from transcript introductions
            mappings.update(self._match_from_introductions(episode_data, remaining))
            remaining = [s for s in remaining if s not in mappings]
        
        if remaining:
            # Step 3: Pattern matching from closing credits
            mappings.update(self._match_from_closing_credits(episode_data, remaining))
            remaining = [s for s in remaining if s not in mappings]
        
        if remaining and episode_data.get('youtube_url'):
            # Step 4: YouTube API
            mappings.update(self._match_from_youtube(episode_data, remaining))
            remaining = [s for s in remaining if s not in mappings]
        
        if remaining:
            # Step 5: LLM as last resort
            mappings.update(self._match_from_llm(episode_data, remaining))
        
        # NEW: Apply sanity checks before database updates
        if mappings:
            logger.info(f"Applying sanity checks to {len(mappings)} identified speakers")
            
            # 1. Filter out non-names
            valid_mappings = {
                k: v for k, v in mappings.items() 
                if self._is_valid_speaker_name(v)
            }
            
            filtered_count = len(mappings) - len(valid_mappings)
            if filtered_count > 0:
                logger.info(f"Filtered out {filtered_count} non-name speakers")
                for k, v in mappings.items():
                    if k not in valid_mappings:
                        logger.info(f"  Filtered: '{k}' -> '{v}'")
            
            mappings = valid_mappings
        
        # Check for duplicates across ALL speakers (including already identified ones)
        all_speakers = self._get_all_episode_speakers(episode_id)
        
        if all_speakers:
            logger.info(f"Checking for duplicates among {len(all_speakers)} total speakers")
            
            # 2. Check for duplicates and create merge mappings
            duplicates = self._find_duplicate_speakers(all_speakers)
            
            if duplicates:
                logger.info(f"Found {len(duplicates)} duplicate speakers to merge")
                
                # Apply duplicate resolution to new mappings
                for old_name, new_name in mappings.items():
                    if new_name in duplicates:
                        # This newly identified name is a duplicate of another
                        mappings[old_name] = duplicates[new_name]
                        logger.info(f"Redirected mapping: '{old_name}' -> '{new_name}' -> '{duplicates[new_name]}'")
                
                # Also need to merge existing duplicates in database
                self._merge_duplicate_speakers(episode_id, duplicates)
            
            # 3. Check value contributions for all speakers (log warnings only)
            for speaker in all_speakers:
                if not self._has_meaningful_contribution(episode_id, speaker):
                    logger.warning(
                        f"Speaker '{speaker}' has minimal contributions in episode {episode_id[:50]}..."
                    )
        
        # Apply final mappings to database
        if mappings:
            logger.info(f"Applying {len(mappings)} validated speaker updates")
            self._update_speakers_in_database(episode_id, mappings)
            self._log_speaker_changes(episode_id, mappings)
        else:
            logger.info("No valid speaker mappings to apply after sanity checks")
        
        return mappings
    
    def _get_episode_data(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve episode data including metadata and units."""
        query = """
        MATCH (e:Episode {id: $episode_id})
        OPTIONAL MATCH (mu:MeaningfulUnit)-[:PART_OF]->(e)
        WITH e, mu
        ORDER BY mu.start_time
        RETURN e, collect(mu) as units
        """
        result = self.storage.query(query, {"episode_id": episode_id})
        
        if not result:
            return None
        
        episode = result[0]['e']
        units = result[0]['units']
        
        return {
            'episode': episode,
            'units': units,
            'description': episode.get('description', ''),
            'title': episode.get('title', ''),
            'youtube_url': episode.get('youtube_url', ''),
            'podcast': episode.get('podcast', '')
        }
    
    def _identify_generic_speakers(self, episode_data: Dict[str, Any]) -> List[str]:
        """Identify speakers with generic names that need mapping."""
        generic_speakers = set()
        
        for unit in episode_data['units']:
            speaker_dist = unit.get('speaker_distribution', '')
            if speaker_dist:
                # Parse speaker distribution JSON
                try:
                    if isinstance(speaker_dist, str):
                        speaker_dict = json.loads(speaker_dist)
                    else:
                        speaker_dict = speaker_dist
                    
                    for speaker_name in speaker_dict.keys():
                        # Check if this is a generic name
                        if self._is_generic_speaker(speaker_name):
                            generic_speakers.add(speaker_name)
                except Exception as e:
                    logger.debug(f"Could not parse speaker_distribution: {e}")
        
        return list(generic_speakers)
    
    def _is_generic_speaker(self, name: str) -> bool:
        """Check if a speaker name is generic and needs identification."""
        if not name:
            return False
        
        # First check if it already contains a real name
        # Pattern: "FirstName LastName (Role)" - this is already identified
        if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+.*\(', name):
            # Has a real name followed by role in parentheses
            return False
        
        # Truly generic patterns that need identification
        generic_patterns = [
            r'^Guest Expert$',  # Just "Guest Expert" without a name
            r'^Guest/Contributor',  # Generic contributor
            r'^Co-host/Producer$',  # Just the role
            r'^Producer$',  # Just "Producer"
            r'^Co-host$',  # Just "Co-host"
            r'^Brief Family Member$',
            r'^Guest \(Speaker \d+\)$',  # "Guest (Speaker 2)"
            r'^Host$',  # Just "Host" without name
            r'^Guest$',  # Just "Guest" without name
        ]
        
        # Check if matches any truly generic pattern
        return any(re.match(pattern, name) for pattern in generic_patterns)
    
    def _is_valid_speaker_name(self, name: str) -> bool:
        """Check if a string is a valid speaker name.
        
        Uses simple blacklist approach following KISS principle.
        
        Args:
            name: The speaker name to validate
            
        Returns:
            True if valid speaker name, False otherwise
        """
        # Simple blacklist approach - KISS principle
        invalid_patterns = [
            'you know what',
            'um', 'uh', 'ah',
            'yeah', 'okay', 'alright',
            'oh', 'hmm', 'huh',
            'yes', 'no', 'maybe',
            'well', 'so', 'and',
            'like', 'just', 'really',
            'actually', 'basically',
            'literally', 'right',
            'i mean', 'you know',
        ]
        
        name_lower = name.lower().strip()
        
        # Check blacklist
        if name_lower in invalid_patterns:
            logger.debug(f"Filtering out non-name: '{name}' (blacklisted)")
            return False
        
        # Basic sanity: must have at least configured minimum characters
        if len(name) < self.config.speaker_min_name_length:
            logger.debug(f"Filtering out non-name: '{name}' (too short, < {self.config.speaker_min_name_length} chars)")
            return False
        
        # Must contain at least one letter
        if not any(c.isalpha() for c in name):
            logger.debug(f"Filtering out non-name: '{name}' (no letters)")
            return False
        
        # Check for common transcription errors (all lowercase phrases)
        if name.islower() and len(name.split()) > 1:
            logger.debug(f"Filtering out non-name: '{name}' (multi-word lowercase)")
            return False
        
        return True
    
    def _extract_name_and_role(self, speaker_name: str) -> Tuple[str, str]:
        """Extract base name and role from a speaker string.
        
        Args:
            speaker_name: Full speaker name possibly with role
            
        Returns:
            Tuple of (base_name, role) or (speaker_name, '') if no role
        """
        # Pattern to extract name and role
        match = re.match(r'^(.+?)\s*\((.+?)\)$', speaker_name)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return speaker_name.strip(), ''
    
    def _are_likely_same_person(self, name1: str, name2: str) -> bool:
        """Simple heuristic to detect if two names refer to the same person.
        
        Args:
            name1: First speaker name
            name2: Second speaker name
            
        Returns:
            True if likely the same person
        """
        # Extract base names and roles
        base1, role1 = self._extract_name_and_role(name1)
        base2, role2 = self._extract_name_and_role(name2)
        
        # Normalize for comparison
        name1_lower = name1.lower()
        name2_lower = name2.lower()
        base1_lower = base1.lower()
        base2_lower = base2.lower()
        
        # If one contains "Family" and other contains "Son/Daughter/Child"
        family_keywords = ['family', 'son', 'daughter', 'child', 'relative', 'brother', 'sister', 'parent', 'mother', 'father']
        name1_has_family = any(kw in name1_lower for kw in family_keywords)
        name2_has_family = any(kw in name2_lower for kw in family_keywords)
        
        if name1_has_family and name2_has_family:
            # Both refer to family members - likely same if in same episode
            # Check for more specific match (e.g., "son" in both)
            specific_family = ['son', 'daughter', 'brother', 'sister', 'mother', 'father']
            for kw in specific_family:
                if kw in name1_lower and kw in name2_lower:
                    logger.debug(f"Likely same person (family): '{name1}' and '{name2}'")
                    return True
        
        # If base names are similar (simple character overlap check)
        if base1_lower and base2_lower and base1_lower != base2_lower:
            # Calculate simple similarity
            shorter = min(len(base1_lower), len(base2_lower))
            longer = max(len(base1_lower), len(base2_lower))
            
            # Check if one name contains the other
            if base1_lower in base2_lower or base2_lower in base1_lower:
                logger.debug(f"Likely same person (contains): '{name1}' and '{name2}'")
                return True
            
            # Character overlap check
            overlap = len(set(base1_lower) & set(base2_lower))
            if shorter >= 4 and overlap > shorter * 0.7:
                logger.debug(f"Likely same person (overlap): '{name1}' and '{name2}'")
                return True
        
        # Check for obvious role variations
        if base1_lower == base2_lower and role1 != role2:
            # Same base name, different roles
            logger.debug(f"Likely same person (role variation): '{name1}' and '{name2}'")
            return True
        
        return False
    
    def _find_duplicate_speakers(self, speakers: List[str]) -> Dict[str, str]:
        """Find likely duplicate speakers in the same episode.
        
        Args:
            speakers: List of all speaker names in episode
            
        Returns:
            Dict mapping duplicate names to canonical names
        """
        duplicates = {}
        
        # Simple rule-based approach
        for i, speaker1 in enumerate(speakers):
            if speaker1 in duplicates:
                continue
                
            for speaker2 in speakers[i+1:]:
                if speaker2 in duplicates:
                    continue
                    
                # Case 1: Role variations of same person
                if self._are_likely_same_person(speaker1, speaker2):
                    # Keep the more specific/longer name as canonical
                    if len(speaker2) > len(speaker1):
                        duplicates[speaker1] = speaker2
                        logger.info(f"Duplicate detected: '{speaker1}' -> '{speaker2}'")
                    else:
                        duplicates[speaker2] = speaker1
                        logger.info(f"Duplicate detected: '{speaker2}' -> '{speaker1}'")
        
        return duplicates
    
    def _get_all_episode_speakers(self, episode_id: str) -> List[str]:
        """Get all unique speakers in an episode.
        
        Args:
            episode_id: Episode ID
            
        Returns:
            List of all unique speaker names
        """
        query = """
        MATCH (mu:MeaningfulUnit)-[:PART_OF]->(e:Episode {id: $episode_id})
        WHERE mu.speaker_distribution IS NOT NULL
        WITH mu.speaker_distribution as dist
        RETURN collect(DISTINCT dist) as distributions
        """
        
        result = self.storage.query(query, {"episode_id": episode_id})
        
        all_speakers = set()
        if result and result[0]['distributions']:
            for dist in result[0]['distributions']:
                try:
                    if isinstance(dist, str):
                        speaker_dict = json.loads(dist)
                    else:
                        speaker_dict = dist
                    all_speakers.update(speaker_dict.keys())
                except Exception as e:
                    logger.debug(f"Could not parse speaker_distribution: {e}")
        
        return sorted(list(all_speakers))
    
    def _has_meaningful_contribution(self, episode_id: str, speaker: str) -> bool:
        """Check if speaker has meaningful knowledge contributions.
        
        Args:
            episode_id: Episode ID
            speaker: Speaker name to check
            
        Returns:
            True if speaker has meaningful contributions
        """
        # Query for units attributed to this speaker
        query = """
        MATCH (mu:MeaningfulUnit)-[:PART_OF]->(e:Episode {id: $episode_id})
        WHERE mu.speaker_distribution IS NOT NULL
        AND mu.speaker_distribution CONTAINS $speaker
        RETURN COUNT(mu) as unit_count, 
               AVG(SIZE(mu.text)) as avg_text_length,
               COLLECT(mu.text)[..3] as sample_texts
        """
        
        try:
            result = self.storage.query(
                query, 
                {"episode_id": episode_id, "speaker": f'"{speaker}"'}
            )
            
            if result:
                record = result[0]
                unit_count = record['unit_count']
                avg_length = record['avg_text_length'] or 0
                sample_texts = record.get('sample_texts', [])
                
                logger.debug(f"Speaker '{speaker}' has {unit_count} units, avg length: {avg_length}")
                
                # Use configuration thresholds
                if unit_count < self.config.speaker_min_units:
                    logger.warning(
                        f"Speaker '{speaker}' has only {unit_count} units (threshold: {self.config.speaker_min_units})"
                    )
                    return False
                    
                if avg_length < self.config.speaker_min_avg_text_length:
                    logger.warning(
                        f"Speaker '{speaker}' has short average text length: {avg_length} "
                        f"(threshold: {self.config.speaker_min_avg_text_length})"
                    )
                    # Check if any samples are meaningful despite short average
                    meaningful_samples = 0
                    for text in sample_texts:
                        if text and len(text) > self.config.speaker_min_avg_text_length:
                            meaningful_samples += 1
                    
                    if meaningful_samples == 0:
                        return False
                
                return True
                
        except Exception as e:
            logger.error(f"Error checking contribution for speaker '{speaker}': {e}")
            # Default to keeping speaker on error
            return True
        
        return True
    
    def _merge_duplicate_speakers(self, episode_id: str, duplicates: Dict[str, str]) -> None:
        """Merge duplicate speakers in database.
        
        Updates all MeaningfulUnits to replace duplicate speaker names with canonical names.
        
        Args:
            episode_id: Episode ID
            duplicates: Dict mapping duplicate names to canonical names
        """
        if not duplicates:
            return
        
        logger.info(f"Merging {len(duplicates)} duplicate speakers in episode {episode_id}")
        
        # Use the existing storage service for database operations
        for old_name, new_name in duplicates.items():
            try:
                # Need to properly escape the names for JSON replacement
                # The speaker_distribution field contains JSON like {"Speaker Name": 0.5}
                # We need to replace the key in the JSON
                
                query = """
                MATCH (mu:MeaningfulUnit)-[:PART_OF]->(e:Episode {id: $episode_id})
                WHERE mu.speaker_distribution CONTAINS $old_name_pattern
                SET mu.speaker_distribution = REPLACE(
                    mu.speaker_distribution, 
                    $old_name_pattern, 
                    $new_name_pattern
                )
                RETURN COUNT(mu) as updated_count
                """
                
                # Create the patterns for JSON key replacement
                old_name_pattern = f'"{old_name}"'
                new_name_pattern = f'"{new_name}"'
                
                result = self.storage.query(
                    query,
                    {
                        "episode_id": episode_id,
                        "old_name_pattern": old_name_pattern,
                        "new_name_pattern": new_name_pattern
                    }
                )
                
                if result:
                    count = result[0].get('updated_count', 0)
                    logger.info(f"Merged '{old_name}' -> '{new_name}' in {count} units")
                    
            except Exception as e:
                logger.error(f"Failed to merge duplicate speaker '{old_name}' -> '{new_name}': {e}")
                # Continue with other merges even if one fails
    
    def _match_from_episode_description(self, episode_data: Dict[str, Any], 
                                      generic_speakers: List[str]) -> Dict[str, str]:
        """Extract speaker names from episode description."""
        mappings = {}
        description = episode_data.get('description', '')
        
        if not description:
            return mappings
        
        # Common patterns for guest names in descriptions
        guest_patterns = [
            r'with\s+(?:guest\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',  # "with [guest] Name Name"
            r'featuring\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',  # "featuring Name Name"
            r'(?:guest|joined\s+by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',  # "guest Name" or "joined by Name"
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+(?:joins|is\s+here)',  # "Name joins/is here"
            r'(?:Dr\.|Professor|Prof\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})',  # Academic titles
        ]
        
        # Extract potential guest names
        potential_names = []
        for pattern in guest_patterns:
            matches = re.findall(pattern, description)
            potential_names.extend(matches)
        
        # Remove duplicates and filter out common words
        common_words = {'The', 'This', 'Today', 'In', 'On', 'With', 'And', 'But', 'For'}
        unique_names = []
        seen = set()
        
        for name in potential_names:
            # Clean up the name
            name = name.strip()
            first_word = name.split()[0] if name else ''
            
            # Skip if starts with common word or already seen
            if first_word not in common_words and name not in seen:
                unique_names.append(name)
                seen.add(name)
        
        logger.debug(f"Found potential names in description: {unique_names}")
        
        # Try to match generic speakers with found names
        for generic in generic_speakers:
            generic_lower = generic.lower()
            
            # Match experts/doctors with academic titles
            if 'expert' in generic_lower or 'psychiatrist' in generic_lower:
                for name in unique_names:
                    if any(title in description for title in ['Dr.', 'Doctor', 'Ph.D.', 'MD']):
                        if name in description:
                            # Verify this name appears near academic context
                            context_window = 50
                            name_index = description.find(name)
                            if name_index != -1:
                                context = description[max(0, name_index-context_window):name_index+context_window+len(name)]
                                if any(word in context.lower() for word in ['psychiatrist', 'psychologist', 'professor', 'doctor', 'expert', 'researcher']):
                                    mappings[generic] = f"Dr. {name}" if not name.startswith('Dr.') else name
                                    unique_names.remove(name)
                                    break
            
            # Match generic guest with remaining names
            elif 'guest' in generic_lower and unique_names:
                # Take the first unmatched name
                mappings[generic] = unique_names[0]
                unique_names.pop(0)
            
            # Match co-host/producer
            elif 'co-host' in generic_lower or 'producer' in generic_lower:
                # Look for producer-specific patterns
                producer_patterns = [
                    r'produced\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                    r'producer\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
                ]
                for pattern in producer_patterns:
                    match = re.search(pattern, description)
                    if match:
                        mappings[generic] = match.group(1)
                        break
        
        logger.info(f"Description matching found {len(mappings)} mappings")
        return mappings
    
    def _match_from_introductions(self, episode_data: Dict[str, Any], 
                                generic_speakers: List[str]) -> Dict[str, str]:
        """Find speaker names from introduction patterns in early transcript segments.
        
        Searches the first segments of the transcript for common introduction patterns
        where speakers identify themselves or each other.
        
        Args:
            episode_data: Episode data including units
            generic_speakers: List of generic speaker names to identify
            
        Returns:
            Dict mapping generic names to identified real names
        """
        mappings = {}
        units = episode_data.get('units', [])
        
        if not units:
            return mappings
        
        # Get first 10 units (typically covers introductions)
        intro_units = units[:10]
        
        # Common introduction patterns
        intro_patterns = [
            # Self-introductions
            r"I'm\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\.|,|\s|$)",  # "I'm Name Name" - require at least 2 parts
            r"My\s+name\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})(?:\.|,|\s|$)",  # "My name is Name"
            r"This\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s+speaking|,|\.|$)",  # "This is Name" (self-referential)
            r"I\s+am\s+(?:Dr\.|Doctor\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\.|,|\s|$)",  # "I am [Dr.] Name"
            
            # Host welcoming guest
            r"Welcome\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",  # "Welcome Name"
            r"Joining\s+(?:me|us)\s+(?:today|now)\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",  # "Joining me today is Name"
            r"(?:Today|Now)\s+I'm\s+(?:talking|speaking)\s+with\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",  # "Today I'm talking with Name"
            r"(?:glad|happy|pleased)\s+to\s+have\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",  # "glad to have Name"
            
            # Guest acknowledging host  
            r"Thanks\s+for\s+having\s+me,\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",  # "Thanks for having me, Name"
            r"Thank\s+you,\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",  # "Thank you, Name"
            r"Great\s+to\s+be\s+here,\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",  # "Great to be here, Name"
            
            # Academic/professional titles
            r"(?:Dr\.|Doctor|Professor|Prof\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",  # Academic titles
        ]
        
        # Track which speakers appear in which order
        speaker_appearances = {}  # speaker -> first appearance index
        name_discoveries = []  # [(name, unit_index, pattern_type)]
        
        # Analyze each intro unit
        for unit_idx, unit in enumerate(intro_units):
            content = unit.get('text', '')  # Use 'text' field
            speaker_dist = unit.get('speaker_distribution', '')
            
            # Parse speakers for this unit
            current_speakers = []
            try:
                if isinstance(speaker_dist, str):
                    speaker_dict = json.loads(speaker_dist)
                else:
                    speaker_dict = speaker_dist
                current_speakers = list(speaker_dict.keys())
            except:
                logger.debug(f"Could not parse speaker_distribution in intro unit {unit_idx}")
            
            # Track first appearance of each speaker
            for speaker in current_speakers:
                if speaker not in speaker_appearances:
                    speaker_appearances[speaker] = unit_idx
            
            # Look for name patterns in content
            for pattern in intro_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Clean up the match
                    name = match.strip()
                    
                    # Skip common false positives and non-name phrases
                    if name.lower() in ['i', 'me', 'you', 'we', 'they', 'here', 'there', 'today', 'now']:
                        continue
                    
                    # Skip if it starts with a lowercase word or contains only one word
                    if not name[0].isupper() or (len(name.split()) == 1 and pattern_type == 'self_intro'):
                        continue
                    
                    # Skip common verbs that might be captured
                    first_word = name.split()[0].lower()
                    if first_word in ['excited', 'happy', 'pleased', 'glad', 'ready', 'going', 'trying']:
                        continue
                    
                    # Determine pattern type for context
                    pattern_type = 'self_intro' if any(p in pattern for p in ["I'm", "My name", "I am"]) else 'other_intro'
                    
                    name_discoveries.append((name, unit_idx, pattern_type, current_speakers))
                    logger.debug(f"Found potential name '{name}' in unit {unit_idx} via {pattern_type}")
        
        # Now try to match discovered names with generic speakers
        # Strategy: Match based on order of appearance and context
        
        # Sort generic speakers by their first appearance
        generic_by_appearance = sorted(
            [(s, speaker_appearances.get(s, float('inf'))) for s in generic_speakers],
            key=lambda x: x[1]
        )
        
        # Process self-introductions first (most reliable)
        for name, unit_idx, pattern_type, speakers_in_unit in name_discoveries:
            if pattern_type == 'self_intro' and name not in mappings.values():
                # The speaker introducing themselves is likely the one speaking in this unit
                for speaker in speakers_in_unit:
                    if speaker in generic_speakers and speaker not in mappings:
                        mappings[speaker] = name
                        logger.info(f"Matched '{speaker}' to '{name}' via self-introduction")
                        break
        
        # Process other introductions (host introducing guest)
        remaining_generic = [g for g in generic_speakers if g not in mappings]
        remaining_names = [n for n, _, pt, _ in name_discoveries 
                          if pt == 'other_intro' and n not in mappings.values()]
        
        for generic in remaining_generic:
            # Prefer matching guests with introduced names
            if 'guest' in generic.lower() and remaining_names:
                # Guest is likely the first name introduced by host
                mappings[generic] = remaining_names[0]
                remaining_names.pop(0)
                logger.info(f"Matched '{generic}' to '{mappings[generic]}' via host introduction")
            elif 'host' in generic.lower():
                # Host might be the one doing the introducing
                # Look for "Thank you, [Name]" patterns where guest thanks host
                for name, _, pattern_type, speakers in name_discoveries:
                    if 'Thank' in str(pattern_type) and name not in mappings.values():
                        mappings[generic] = name
                        logger.info(f"Matched '{generic}' to '{name}' via guest acknowledgment")
                        break
        
        logger.info(f"Introduction matching found {len(mappings)} mappings")
        return mappings
    
    def _match_from_closing_credits(self, episode_data: Dict[str, Any], 
                                   generic_speakers: List[str]) -> Dict[str, str]:
        """Extract speaker names from closing credits at the end of episodes.
        
        Searches the final segments of the transcript for credits patterns
        where speakers are thanked or credited.
        
        Args:
            episode_data: Episode data including units  
            generic_speakers: List of generic speaker names to identify
            
        Returns:
            Dict mapping generic names to identified real names
        """
        mappings = {}
        units = episode_data.get('units', [])
        
        if not units or len(units) < 5:
            return mappings
        
        # Get last 5 units (typically covers closing/credits)
        closing_units = units[-5:]
        
        # Common closing credit patterns
        credit_patterns = [
            # Thanks and credits - capture full names after titles, stop at common words
            r"Special\s+thanks\s+to\s+(?:our\s+guest\s+)?Dr\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s+(?:for|who|,|\.))",  # "Special thanks to Dr. Name for/who/,/."
            r"Special\s+thanks\s+to\s+(?:our\s+guest\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s+(?:for|who|,|\.))",  # "Special thanks to Name for/who/,/."
            r"Thanks\s+to\s+(?:our\s+guest\s+)?Dr\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s+(?:for|who|,|\.))",  # "Thanks to Dr. Name for/who/,/."
            r"Thanks\s+to\s+(?:our\s+guest\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s+(?:for|who|,|\.))",  # "Thanks to Name for/who/,/."
            r"Our\s+guest\s+(?:today\s+)?(?:was|has\s+been)\s+Dr\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s+|,|\.|$)",  # "Our guest was Dr. Name"
            r"Our\s+guest\s+(?:today\s+)?(?:was|has\s+been)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s+|,|\.|$)",  # "Our guest was Name"
            r"(?:Today's|This)\s+guest\s+(?:was|is)\s+Dr\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s+|,|\.|$)",  # "Today's guest was Dr. Name"
            r"(?:Today's|This)\s+guest\s+(?:was|is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?:\s+|,|\.|$)",  # "Today's guest was Name"
            # Fallback patterns for names with titles (less specific)
            r"Special\s+thanks\s+to\s+(?:our\s+guest\s+)?Dr\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",  # "Special thanks to Dr. Name"
            r"Special\s+thanks\s+to\s+(?:our\s+guest\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",  # "Special thanks to Name"
            r"Thanks\s+to\s+(?:our\s+guest\s+)?Dr\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",  # "Thanks to Dr. Name"
            r"Thanks\s+to\s+(?:our\s+guest\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",  # "Thanks to Name"
            
            # Production credits - stop at common words
            r"Produced\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})(?:\s+(?:who|and|with|,|\.|$))",  # "Produced by Name who/and/,/."
            r"Executive\s+producer\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})(?:\s+(?:who|and|with|,|\.|$))",  # "Executive producer Name"
            r"(?:This\s+)?(?:episode|podcast)\s+(?:is|was)\s+produced\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})(?:\s+(?:who|and|with|,|\.|$))",
            # Fallback patterns for production credits
            r"Produced\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",  # "Produced by Name"
            r"Executive\s+producer\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",  # "Executive producer Name"
            r"(?:This\s+)?(?:episode|podcast)\s+(?:is|was)\s+produced\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
            
            # Host sign-offs
            r"I'm\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+(?:and|,)\s+(?:thanks|thank\s+you)",  # "I'm Name and thanks"
            r"This\s+(?:is|was)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",  # "This is/was Name" (sign-off)
            r"Until\s+next\s+time,\s+(?:I'm\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",  # "Until next time, I'm Name"
            
            # Expert/guest credits with titles - capture names after titles
            r"(?:Dr\.|Doctor|Professor|Prof\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",  # Academic titles - require full name
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}),\s+(?:author|expert|specialist|researcher)",  # "Name, author/expert" - require full name
        ]
        
        # Collect all potential names from closing credits
        discovered_names = {}
        
        for unit in closing_units:
            content = unit.get('text', '')  # Use 'text' field
            
            for pattern in credit_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    name = match.strip()
                    
                    # Skip common false positives
                    if name.lower() in ['the', 'this', 'that', 'here', 'there', 'everyone', 'folks']:
                        continue
                    
                    # Skip single word names unless they're preceded by a title
                    if len(name.split()) == 1 and not any(title in content for title in ['Dr.', 'Doctor', 'Professor']):
                        continue
                    
                    # Categorize by pattern type
                    if any(word in pattern.lower() for word in ['guest', 'thanks']):
                        discovered_names.setdefault('guest', []).append(name)
                    elif any(word in pattern.lower() for word in ['produced', 'producer']):
                        discovered_names.setdefault('producer', []).append(name)
                    elif any(word in pattern.lower() for word in ["i'm", 'this is', 'until']):
                        discovered_names.setdefault('host', []).append(name)
                    else:
                        discovered_names.setdefault('other', []).append(name)
                    
                    logger.debug(f"Found credit name '{name}' via pattern: {pattern}")
        
        # Match discovered names with generic speakers
        for generic in generic_speakers:
            if generic in mappings:
                continue
                
            generic_lower = generic.lower()
            
            # Match based on role
            if 'guest' in generic_lower and 'guest' in discovered_names:
                # Take the most frequently mentioned guest name
                guest_names = discovered_names['guest']
                if guest_names:
                    # Count occurrences
                    name_counts = {}
                    for name in guest_names:
                        name_counts[name] = name_counts.get(name, 0) + 1
                    
                    # Get most frequent
                    most_frequent = max(name_counts.items(), key=lambda x: x[1])[0]
                    if most_frequent not in mappings.values():
                        mappings[generic] = most_frequent
                        logger.info(f"Matched '{generic}' to '{most_frequent}' via closing credits")
            
            elif ('producer' in generic_lower or 'co-host' in generic_lower) and 'producer' in discovered_names:
                producer_names = discovered_names['producer']
                if producer_names and producer_names[0] not in mappings.values():
                    mappings[generic] = producer_names[0]
                    logger.info(f"Matched '{generic}' to '{producer_names[0]}' via production credits")
            
            elif 'host' in generic_lower and 'host' in discovered_names:
                host_names = discovered_names['host']
                if host_names and host_names[0] not in mappings.values():
                    mappings[generic] = host_names[0]
                    logger.info(f"Matched '{generic}' to '{host_names[0]}' via host sign-off")
            
            # Try to match experts/doctors with any academic titles found
            elif 'expert' in generic_lower or 'psychiatrist' in generic_lower:
                # Look for names with academic titles
                all_names = discovered_names.get('other', []) + discovered_names.get('guest', [])
                for name in all_names:
                    if name not in mappings.values():
                        # Check if this might be an expert based on context
                        mappings[generic] = name
                        logger.info(f"Matched '{generic}' to '{name}' via closing credits context")
                        break
        
        logger.info(f"Closing credits matching found {len(mappings)} mappings")
        return mappings
    
    def _match_from_youtube(self, episode_data: Dict[str, Any], 
                           generic_speakers: List[str]) -> Dict[str, str]:
        """Extract speaker names from YouTube video description.
        
        Uses the YouTube API to fetch the full video description and extract
        speaker names from structured information often found there.
        
        Args:
            episode_data: Episode data including YouTube URL
            generic_speakers: List of generic speaker names to identify
            
        Returns:
            Dict mapping generic names to identified real names
        """
        mappings = {}
        youtube_url = episode_data.get('youtube_url', '')
        
        if not youtube_url:
            logger.debug("No YouTube URL available for this episode")
            return mappings
        
        # Initialize YouTube client if not already done
        if not self.youtube_client:
            self.youtube_client = YouTubeDescriptionFetcher()
            if not self.youtube_client.is_available():
                logger.warning("YouTube API not available, skipping YouTube description matching")
                return mappings
        
        # Get video description
        description = self.youtube_client.get_video_description(youtube_url)
        if not description:
            logger.debug("Could not retrieve YouTube description")
            return mappings
        
        logger.debug(f"Retrieved YouTube description ({len(description)} chars)")
        
        # Patterns for extracting guest information from YouTube descriptions
        guest_patterns = [
            # Common YouTube description formats
            r"(?:Guest|Today's guest):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})",  # "Guest: Name Name"
            r"(?:Featuring|With)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})",  # "Featuring Name"
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:joins|is our guest)",  # "Name joins/is our guest"
            
            # Structured guest lists
            r"(?:GUEST|Guest)\s*[:\|\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})",  # "GUEST: Name" or "Guest - Name"
            r"\n([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s*[-–—]\s*(?:[A-Z][a-z]+ )*(?:Expert|Author|Founder|CEO|Doctor|Dr\.|Professor)",  # "Name - Title/Role"
            
            # Social media handles often with real names
            r"(?:Instagram|Twitter|TikTok):\s*@?([A-Z][a-z]+(?:[_.]?[A-Z][a-z]+)?)",  # Social media with real names
            
            # Timestamps with guest names
            r"\d{1,2}:\d{2}\s*[-–—]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+(?:intro|joins|arrives)",  # "0:45 - John Smith intro"
            
            # Book/work mentions
            r"(?:author of|wrote|created)\s+[\"'].*?[\"']\s*[-–—]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",  # "author of 'Book' - Name"
            
            # Academic/professional titles
            r"(?:Dr\.|Doctor|Professor|Prof\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
        ]
        
        # Production credits patterns
        producer_patterns = [
            r"(?:Produced by|Producer):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
            r"(?:Executive Producer|EP):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
            r"\n([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s*[-–—]\s*Producer",
        ]
        
        # Host patterns
        host_patterns = [
            r"(?:Host|Hosted by):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
            r"\n([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s*[-–—]\s*Host",
        ]
        
        # Extract names based on patterns
        discovered_names = {'guest': [], 'producer': [], 'host': []}
        
        # Search for guest names
        for pattern in guest_patterns:
            matches = re.findall(pattern, description)
            for match in matches:
                name = match.strip()
                # Filter out common false positives
                if name and len(name) > 2 and name not in ['The', 'This', 'Our', 'Today']:
                    discovered_names['guest'].append(name)
                    logger.debug(f"Found potential guest name in YouTube description: {name}")
        
        # Search for producer names
        for pattern in producer_patterns:
            matches = re.findall(pattern, description)
            for match in matches:
                name = match.strip()
                if name and len(name) > 2:
                    discovered_names['producer'].append(name)
        
        # Search for host names
        for pattern in host_patterns:
            matches = re.findall(pattern, description)
            for match in matches:
                name = match.strip()
                if name and len(name) > 2:
                    discovered_names['host'].append(name)
        
        # Match discovered names with generic speakers
        for generic in generic_speakers:
            if generic in mappings:
                continue
            
            generic_lower = generic.lower()
            
            # Match guests
            if 'guest' in generic_lower and discovered_names['guest']:
                # Take the first guest name (most likely the main guest)
                guest_name = discovered_names['guest'][0]
                if guest_name not in mappings.values():
                    mappings[generic] = guest_name
                    discovered_names['guest'].pop(0)
                    logger.info(f"Matched '{generic}' to '{guest_name}' via YouTube description")
            
            # Match experts (often same as guests)
            elif 'expert' in generic_lower and discovered_names['guest']:
                # Look for names with titles
                for idx, name in enumerate(discovered_names['guest']):
                    if any(title in description for title in ['Dr.', 'Doctor', 'Ph.D.', 'MD', 'Professor']):
                        if name not in mappings.values():
                            mappings[generic] = name
                            discovered_names['guest'].pop(idx)
                            logger.info(f"Matched '{generic}' to '{name}' via YouTube description (expert)")
                            break
            
            # Match producers
            elif ('producer' in generic_lower or 'co-host' in generic_lower) and discovered_names['producer']:
                producer_name = discovered_names['producer'][0]
                if producer_name not in mappings.values():
                    mappings[generic] = producer_name
                    discovered_names['producer'].pop(0)
                    logger.info(f"Matched '{generic}' to '{producer_name}' via YouTube description")
            
            # Match hosts
            elif 'host' in generic_lower and discovered_names['host']:
                host_name = discovered_names['host'][0]
                if host_name not in mappings.values():
                    mappings[generic] = host_name
                    discovered_names['host'].pop(0)
                    logger.info(f"Matched '{generic}' to '{host_name}' via YouTube description")
        
        logger.info(f"YouTube description matching found {len(mappings)} mappings")
        return mappings
    
    def _generate_speaker_prompt(self, episode_data: Dict[str, Any], 
                                generic_speaker: str, 
                                speaker_segments: List[str]) -> str:
        """Generate an effective prompt for speaker identification.
        
        Args:
            episode_data: Episode metadata
            generic_speaker: The generic speaker label to identify
            speaker_segments: Sample segments where this speaker appears
            
        Returns:
            Formatted prompt for the LLM
        """
        podcast_name = episode_data.get('podcast', '')
        episode_title = episode_data.get('title', '')
        description = episode_data.get('description', '')[:500]  # First 500 chars
        
        # Build context from speaker segments
        segment_context = "\n".join([
            f"- \"{seg[:200]}...\"" if len(seg) > 200 else f"- \"{seg}\""
            for seg in speaker_segments[:5]  # First 5 segments
        ])
        
        prompt = f"""You are analyzing a podcast transcript to identify a speaker's real name.

Podcast: {podcast_name}
Episode: {episode_title}
Episode Description: {description}

The transcript identifies a speaker as "{generic_speaker}".

Here are some things this speaker said:
{segment_context}

Based on the context, episode information, and what the speaker says, what is most likely this person's real name?

Consider:
1. Any self-introductions or mentions of their name
2. References to their work, books, or affiliations
3. How others address them
4. Their role (guest, expert, host, etc.)

Provide ONLY the most likely full name (first and last name if available). If you cannot determine the name with reasonable confidence, respond with "UNKNOWN".

Name:"""
        
        return prompt
    
    def _match_from_llm(self, episode_data: Dict[str, Any], 
                       generic_speakers: List[str]) -> Dict[str, str]:
        """Use LLM to identify speakers based on context.
        
        This is the last resort method when pattern matching and APIs fail.
        Uses the Gemini Flash model for speed.
        
        Args:
            episode_data: Episode data including units
            generic_speakers: List of generic speaker names to identify
            
        Returns:
            Dict mapping generic names to identified real names
        """
        mappings = {}
        units = episode_data.get('units', [])
        
        if not units or not self.llm_service:
            logger.debug("No units or LLM service available for LLM-based identification")
            return mappings
        
        # Group segments by speaker
        speaker_segments = {}
        for unit in units:
            content = unit.get('text', '')  # Use 'text' field from MeaningfulUnit
            speaker_dist = unit.get('speaker_distribution', '')
            
            # Parse speaker distribution
            try:
                if isinstance(speaker_dist, str):
                    speaker_dict = json.loads(speaker_dist)
                else:
                    speaker_dict = speaker_dist
                    
                for speaker_name in speaker_dict.keys():
                    if speaker_name in generic_speakers:
                        if speaker_name not in speaker_segments:
                            speaker_segments[speaker_name] = []
                        speaker_segments[speaker_name].append(content)
            except Exception as e:
                logger.debug(f"Could not parse speaker_distribution in LLM method: {e}")
        
        # Process each generic speaker
        for generic_speaker in generic_speakers:
            if generic_speaker in mappings:
                continue
                
            segments = speaker_segments.get(generic_speaker, [])
            if not segments:
                logger.debug(f"No segments found for speaker: {generic_speaker}")
                continue
            
            try:
                # Generate prompt
                prompt = self._generate_speaker_prompt(
                    episode_data, 
                    generic_speaker, 
                    segments
                )
                
                # Call LLM
                logger.info(f"Using LLM to identify speaker: {generic_speaker}")
                response = self.llm_service.complete(prompt)
                
                # Parse response
                name = response.strip()
                
                # Validate response
                if name and name != "UNKNOWN" and len(name) > 2:
                    # Basic validation - should look like a name
                    if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', name):
                        mappings[generic_speaker] = name
                        logger.info(f"LLM identified '{generic_speaker}' as '{name}'")
                    else:
                        logger.warning(f"LLM returned invalid name format: {name}")
                else:
                    logger.info(f"LLM could not identify speaker: {generic_speaker}")
                    
            except Exception as e:
                logger.error(f"LLM identification failed for {generic_speaker}: {e}")
                continue
        
        logger.info(f"LLM-based matching found {len(mappings)} mappings")
        return mappings
    
    def _update_speakers_in_database(self, episode_id: str, mappings: Dict[str, str]) -> None:
        """Apply speaker mappings to all affected MeaningfulUnits.
        
        Updates the speaker field and speaker_distribution JSON for all units
        that contain the generic speaker names.
        
        Args:
            episode_id: Episode ID to update
            mappings: Dict mapping generic names to real names
        """
        if not mappings:
            return
        
        logger.info(f"Updating {len(mappings)} speaker mappings in database for episode {episode_id}")
        
        # Start a transaction
        session = self.storage.driver.session()
        tx = session.begin_transaction()
        
        try:
            # For each mapping, update all affected MeaningfulUnits
            for generic_name, real_name in mappings.items():
                # Update units where this speaker appears in the speaker_distribution field
                update_query = """
                MATCH (e:Episode {id: $episode_id})<-[:PART_OF]-(mu:MeaningfulUnit)
                WHERE mu.speaker_distribution CONTAINS $generic_name
                SET mu.speaker_distribution = REPLACE(mu.speaker_distribution, $generic_name, $real_name)
                RETURN count(mu) as updated_count
                """
                
                result = tx.run(update_query, {
                    'episode_id': episode_id,
                    'generic_name': generic_name,
                    'real_name': real_name
                })
                
                try:
                    record = result.single()
                    if record:
                        count = record['updated_count']
                        logger.debug(f"Updated {count} units for speaker '{generic_name}' -> '{real_name}'")
                except Exception as e:
                    logger.debug(f"Could not retrieve update count: {e}")
                
                # Skip secondary update - speaker_distribution is the only field
                
                # No secondary update needed - speaker_distribution is the primary field
            
            # Update the episode node with a timestamp of when speakers were mapped
            episode_update_query = """
            MATCH (e:Episode {id: $episode_id})
            SET e.speakersMapped = true,
                e.speakerMappingTimestamp = $timestamp,
                e.speakerMappingMethod = 'post_processing'
            RETURN e
            """
            
            tx.run(episode_update_query, {
                'episode_id': episode_id,
                'timestamp': datetime.now().isoformat()
            })
            
            # Commit the transaction
            tx.commit()
            logger.info(f"Successfully applied speaker mappings for episode {episode_id}")
            
        except Exception as e:
            # Rollback on error
            tx.rollback()
            logger.error(f"Failed to update speakers in database: {e}")
            raise
        finally:
            tx.close()
            session.close()
    
    def _log_speaker_changes(self, episode_id: str, mappings: Dict[str, str]) -> None:
        """Log all speaker changes for audit trail.
        
        Creates a log entry with details about the speaker mappings applied.
        
        Args:
            episode_id: Episode ID
            mappings: Applied mappings
        """
        if not mappings:
            return
        
        timestamp = datetime.now().isoformat()
        
        # Create audit log entry
        audit_entry = {
            'timestamp': timestamp,
            'episode_id': episode_id,
            'mappings': mappings,
            'method': 'automated_post_processing',
            'mapping_count': len(mappings)
        }
        
        # Log to file (create logs directory if needed)
        log_dir = Path('logs/speaker_mappings')
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"speaker_mappings_{datetime.now().strftime('%Y%m%d')}.json"
        
        # Append to log file
        try:
            # Read existing logs if file exists
            if log_file.exists():
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            else:
                logs = []
            
            # Add new entry
            logs.append(audit_entry)
            
            # Write back
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2)
            
            logger.info(f"Logged speaker changes to {log_file}")
            
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
        
        # Also store in Neo4j for persistence
        try:
            audit_query = """
            MATCH (e:Episode {id: $episode_id})
            CREATE (e)-[:HAS_SPEAKER_MAPPING_AUDIT]->(audit:SpeakerMappingAudit {
                timestamp: $timestamp,
                mappings: $mappings_json,
                method: $method,
                mappingCount: $mapping_count
            })
            RETURN audit
            """
            
            self.storage.query(audit_query, {
                'episode_id': episode_id,
                'timestamp': timestamp,
                'mappings_json': json.dumps(mappings),
                'method': 'automated_post_processing',
                'mapping_count': len(mappings)
            })
            
            logger.debug("Created audit node in Neo4j")
            
        except Exception as e:
            logger.error(f"Failed to create audit node in Neo4j: {e}")