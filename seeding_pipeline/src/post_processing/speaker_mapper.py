"""Speaker mapping post-processing module.

This module identifies and updates generic speaker names in the Neo4j database
using a 3-step approach: pattern matching, YouTube API, and LLM as fallback.
"""

import re
from typing import Dict, List, Optional, Tuple, Any
import json
from datetime import datetime

from src.utils.logging import get_logger
from src.storage.graph_storage import GraphStorageService
from src.services.llm import LLMService
from src.core.config import PipelineConfig

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
        
        # Apply mappings to database
        if mappings:
            logger.info(f"Identified {len(mappings)} speakers, applying updates")
            self._update_speakers_in_database(episode_id, mappings)
            self._log_speaker_changes(episode_id, mappings)
        
        return mappings
    
    def _get_episode_data(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve episode data including metadata and units."""
        query = """
        MATCH (e:Episode {episodeId: $episode_id})
        OPTIONAL MATCH (e)-[:HAS_MEANINGFUL_UNIT]->(mu:MeaningfulUnit)
        RETURN e, collect(mu) as units
        ORDER BY mu.segmentNumbers[0]
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
            'youtube_url': episode.get('episodeUrl', ''),
            'podcast': episode.get('podcast', '')
        }
    
    def _identify_generic_speakers(self, episode_data: Dict[str, Any]) -> List[str]:
        """Identify speakers with generic names that need mapping."""
        generic_speakers = set()
        
        for unit in episode_data['units']:
            speakers = unit.get('speakers', '')
            if speakers:
                # Parse speaker JSON
                try:
                    if isinstance(speakers, str):
                        speaker_dict = json.loads(speakers.replace("'", '"'))
                    else:
                        speaker_dict = speakers
                    
                    for speaker_name in speaker_dict.keys():
                        # Check if this is a generic name
                        if self._is_generic_speaker(speaker_name):
                            generic_speakers.add(speaker_name)
                except:
                    # Handle single speaker format
                    if self._is_generic_speaker(speakers):
                        generic_speakers.add(speakers)
        
        return list(generic_speakers)
    
    def _is_generic_speaker(self, name: str) -> bool:
        """Check if a speaker name is generic and needs identification."""
        if not name:
            return False
        
        # Already has a real name (not just role-based)
        if any(char.isupper() and i > 0 for i, char in enumerate(name.split()[0])):
            # Has capital letters in middle of first word (likely a name)
            if not any(pattern in name for pattern in ['Speaker', 'Guest', 'Host', 'Expert']):
                return False
        
        # Generic patterns to identify
        generic_patterns = [
            r'^Guest Expert',
            r'^Guest\/Contributor',
            r'^Co-host\/Producer$',
            r'^Brief Family Member$',
            r'^Guest \(Speaker \d+\)$',
            r'^\w+ Expert \(',  # Any expert with role description
        ]
        
        return any(re.match(pattern, name) for pattern in generic_patterns)
    
    def _match_from_episode_description(self, episode_data: Dict[str, Any], 
                                      generic_speakers: List[str]) -> Dict[str, str]:
        """Extract speaker names from episode description.
        
        This method will be implemented in Phase 2.
        """
        return {}
    
    def _match_from_introductions(self, episode_data: Dict[str, Any], 
                                generic_speakers: List[str]) -> Dict[str, str]:
        """Find speaker names from introduction patterns.
        
        This method will be implemented in Phase 2.
        """
        return {}
    
    def _match_from_closing_credits(self, episode_data: Dict[str, Any], 
                                   generic_speakers: List[str]) -> Dict[str, str]:
        """Extract speaker names from closing credits.
        
        This method will be implemented in Phase 2.
        """
        return {}
    
    def _match_from_youtube(self, episode_data: Dict[str, Any], 
                           generic_speakers: List[str]) -> Dict[str, str]:
        """Extract speaker names from YouTube video description.
        
        This method will be implemented in Phase 3.
        """
        return {}
    
    def _match_from_llm(self, episode_data: Dict[str, Any], 
                       generic_speakers: List[str]) -> Dict[str, str]:
        """Use LLM to identify speakers based on context.
        
        This method will be implemented in Phase 4.
        """
        return {}
    
    def _update_speakers_in_database(self, episode_id: str, mappings: Dict[str, str]) -> None:
        """Apply speaker mappings to all affected MeaningfulUnits.
        
        This method will be implemented in Phase 5.
        """
        pass
    
    def _log_speaker_changes(self, episode_id: str, mappings: Dict[str, str]) -> None:
        """Log all speaker changes for audit trail.
        
        This method will be implemented in Phase 5.
        """
        pass