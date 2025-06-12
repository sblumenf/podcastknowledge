"""Speaker database for caching known speakers across episodes."""

import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import hashlib

logger = logging.getLogger(__name__)


class SpeakerDatabase:
    """Database for caching and retrieving known speaker identifications."""
    
    def __init__(self, cache_dir: Optional[Path] = None, ttl_days: int = 30):
        """
        Initialize speaker database.
        
        Args:
            cache_dir: Directory for persistent cache (None for memory-only)
            ttl_days: Time-to-live for cached speakers in days
        """
        self.cache_dir = cache_dir
        self.ttl_days = ttl_days
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        
        # Load persistent cache if available
        if self.cache_dir:
            self.cache_dir = Path(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_cache()
    
    def _get_podcast_key(self, podcast_name: str) -> str:
        """Generate normalized key for podcast."""
        # Normalize podcast name for consistent matching
        normalized = podcast_name.lower().strip()
        # Remove common variations
        normalized = normalized.replace("podcast", "").replace("show", "").strip()
        # Create hash for consistent key
        return hashlib.md5(normalized.encode()).hexdigest()[:12]
    
    def get_known_speakers(self, podcast_name: str) -> Optional[Dict[str, Any]]:
        """
        Get known speakers for a podcast.
        
        Args:
            podcast_name: Name of the podcast
            
        Returns:
            Dict with speaker information or None if not found
        """
        key = self._get_podcast_key(podcast_name)
        
        # Check memory cache first
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if self._is_valid_entry(entry):
                logger.debug(f"Found speakers in memory cache for '{podcast_name}'")
                return entry['speakers']
            else:
                # Remove expired entry
                del self.memory_cache[key]
        
        # Check persistent cache
        if self.cache_dir:
            cache_file = self.cache_dir / f"{key}.json"
            if cache_file.exists():
                try:
                    with open(cache_file, 'r') as f:
                        entry = json.load(f)
                    
                    if self._is_valid_entry(entry):
                        # Load into memory cache
                        self.memory_cache[key] = entry
                        logger.debug(f"Found speakers in persistent cache for '{podcast_name}'")
                        return entry['speakers']
                    else:
                        # Remove expired file
                        cache_file.unlink()
                        
                except Exception as e:
                    logger.warning(f"Failed to load cache file {cache_file}: {e}")
        
        return None
    
    def store_speakers(self, 
                      podcast_name: str, 
                      speakers: Dict[str, str],
                      confidence_scores: Dict[str, float],
                      episode_count: int = 1) -> None:
        """
        Store speaker information for a podcast.
        
        Args:
            podcast_name: Name of the podcast
            speakers: Dict mapping generic IDs to identified names
            confidence_scores: Confidence scores for each identification
            episode_count: Number of episodes this is based on
        """
        key = self._get_podcast_key(podcast_name)
        
        # Create or update entry
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            # Update with new information
            entry['speakers'].update(speakers)
            entry['confidence_scores'].update(confidence_scores)
            entry['episode_count'] += episode_count
            entry['last_updated'] = datetime.now().isoformat()
            
            # Recalculate average confidence
            all_scores = list(entry['confidence_scores'].values())
            entry['avg_confidence'] = sum(all_scores) / len(all_scores) if all_scores else 0
        else:
            # Create new entry
            entry = {
                'podcast_name': podcast_name,
                'speakers': speakers,
                'confidence_scores': confidence_scores,
                'episode_count': episode_count,
                'avg_confidence': sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else 0,
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            }
        
        # Store in memory
        self.memory_cache[key] = entry
        
        # Persist if configured
        if self.cache_dir:
            cache_file = self.cache_dir / f"{key}.json"
            try:
                with open(cache_file, 'w') as f:
                    json.dump(entry, f, indent=2)
                logger.debug(f"Persisted speakers for '{podcast_name}' to {cache_file}")
            except Exception as e:
                logger.error(f"Failed to persist speaker cache: {e}")
    
    def match_speakers(self,
                      podcast_name: str,
                      current_stats: Dict[str, Any],
                      threshold: float = 0.7) -> Tuple[Dict[str, str], Dict[str, float]]:
        """
        Match current speakers with known speakers based on statistics.
        
        Args:
            podcast_name: Name of the podcast
            current_stats: Current speaker statistics
            threshold: Minimum similarity threshold for matching
            
        Returns:
            Tuple of (speaker_mappings, confidence_scores)
        """
        known_speakers = self.get_known_speakers(podcast_name)
        if not known_speakers:
            return {}, {}
        
        mappings = {}
        confidence_scores = {}
        
        # Sort current speakers by speaking percentage
        sorted_current = sorted(
            current_stats.items(),
            key=lambda x: x[1].get('speaking_percentage', 0),
            reverse=True
        )
        
        # Try to match based on speaking patterns
        for i, (speaker_id, stats) in enumerate(sorted_current):
            speaking_pct = stats.get('speaking_percentage', 0)
            
            # Common patterns for known roles
            if i == 0 and speaking_pct > 40:
                # Likely the host
                for generic_id, name in known_speakers.items():
                    if 'host' in name.lower():
                        mappings[speaker_id] = name
                        confidence_scores[speaker_id] = 0.8
                        break
            elif i == 1 and speaking_pct > 20:
                # Likely co-host or main guest
                for generic_id, name in known_speakers.items():
                    if 'co-host' in name.lower() or 'guest' in name.lower():
                        if speaker_id not in mappings:
                            mappings[speaker_id] = name
                            confidence_scores[speaker_id] = 0.7
                            break
        
        return mappings, confidence_scores
    
    def _is_valid_entry(self, entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid."""
        try:
            last_updated = datetime.fromisoformat(entry['last_updated'])
            age = datetime.now() - last_updated
            return age.days < self.ttl_days
        except:
            return False
    
    def _load_cache(self) -> None:
        """Load all cache files into memory."""
        if not self.cache_dir or not self.cache_dir.exists():
            return
        
        loaded = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r') as f:
                    entry = json.load(f)
                
                if self._is_valid_entry(entry):
                    key = cache_file.stem
                    self.memory_cache[key] = entry
                    loaded += 1
                else:
                    # Remove expired file
                    cache_file.unlink()
                    
            except Exception as e:
                logger.warning(f"Failed to load cache file {cache_file}: {e}")
        
        if loaded > 0:
            logger.info(f"Loaded {loaded} speaker cache entries")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        total_speakers = sum(
            len(entry.get('speakers', {})) 
            for entry in self.memory_cache.values()
        )
        
        avg_confidence = 0
        if self.memory_cache:
            confidences = [
                entry.get('avg_confidence', 0) 
                for entry in self.memory_cache.values()
            ]
            avg_confidence = sum(confidences) / len(confidences)
        
        return {
            'podcasts_cached': len(self.memory_cache),
            'total_speakers': total_speakers,
            'average_confidence': round(avg_confidence, 3),
            'cache_size_mb': self._get_cache_size_mb()
        }
    
    def _get_cache_size_mb(self) -> float:
        """Calculate approximate cache size in MB."""
        # Estimate memory usage
        json_str = json.dumps(self.memory_cache)
        size_bytes = len(json_str.encode('utf-8'))
        return round(size_bytes / (1024 * 1024), 2)
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.memory_cache.clear()
        
        if self.cache_dir and self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
        
        logger.info("Speaker cache cleared")