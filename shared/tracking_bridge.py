"""
Shared tracking bridge for cross-module episode tracking.

This module enables the transcriber to check Neo4j without tight coupling to the 
seeding_pipeline. It provides a minimal interface for checking episode status
and handles multi-podcast database routing.
"""

import os
import sys
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


class TranscriptionTracker:
    """Bridge for checking episode status across transcriber and seeding modules."""
    
    def __init__(self):
        """Initialize the tracking bridge."""
        self._neo4j_available = False
        self._episode_tracker = None
        self._podcast_configs = {}
        self._combined_mode = self._detect_combined_mode()
        self._connection_pool = {}  # Connection pool for multi-podcast support
        
        # Try to import seeding_pipeline components
        self._initialize_neo4j_connection()
    
    def _detect_combined_mode(self) -> bool:
        """
        Auto-detect if running in combined mode.
        
        Returns:
            True if running in combined mode, False otherwise
        """
        # Check for environment variable set by run_pipeline.sh
        pipeline_mode = os.environ.get('PODCAST_PIPELINE_MODE')
        if pipeline_mode == 'combined':
            logger.info("Combined mode detected via PODCAST_PIPELINE_MODE environment variable")
            return True
        
        # Check if both modules are accessible
        seeding_available = self._check_seeding_pipeline_available()
        
        if seeding_available:
            logger.info("Combined mode detected: seeding_pipeline available")
            return True
        
        logger.info("Running in independent mode")
        return False
    
    def _check_seeding_pipeline_available(self) -> bool:
        """Check if seeding_pipeline module is available."""
        try:
            # Add seeding_pipeline to path if needed
            repo_root = Path(__file__).parent.parent
            seeding_path = repo_root / 'seeding_pipeline'
            
            if seeding_path.exists() and str(seeding_path) not in sys.path:
                sys.path.insert(0, str(seeding_path))
            
            # Try to import to check availability
            import src.tracking
            return True
        except ImportError:
            return False
    
    def _initialize_neo4j_connection(self):
        """Initialize connection to Neo4j if available."""
        if not self._combined_mode:
            logger.debug("Not in combined mode, skipping Neo4j initialization")
            return
        
        try:
            # Import seeding_pipeline tracking components
            from src.tracking import EpisodeTracker
            from src.storage.graph_storage import GraphStorageService
            
            # Load podcast configurations
            self._load_podcast_configs()
            
            # Create a minimal graph storage for checking
            # We'll initialize specific database connections on demand
            self._neo4j_available = True
            logger.info("Neo4j tracking bridge initialized successfully")
            
        except Exception as e:
            logger.warning(f"Could not initialize Neo4j connection: {e}")
            logger.info("Falling back to file-based tracking only")
            self._neo4j_available = False
    
    def _load_podcast_configs(self):
        """Load podcast configurations for multi-podcast support."""
        try:
            import yaml
            
            # Find podcasts.yaml config
            repo_root = Path(__file__).parent.parent
            config_path = repo_root / 'seeding_pipeline' / 'config' / 'podcasts.yaml'
            
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    
                # Store podcast database configurations
                for podcast in config.get('podcasts', []):
                    podcast_id = podcast['id']
                    self._podcast_configs[podcast_id] = podcast.get('database', {})
                    
                logger.info(f"Loaded configurations for {len(self._podcast_configs)} podcasts")
            else:
                logger.warning(f"Podcast config not found at {config_path}")
                
        except Exception as e:
            logger.error(f"Error loading podcast configs: {e}")
    
    def should_transcribe(self, podcast_id: str, episode_title: str, date: str) -> bool:
        """
        Check if an episode should be transcribed.
        
        Args:
            podcast_id: Identifier for the podcast
            episode_title: Title of the episode
            date: Publication date of the episode
            
        Returns:
            True if episode should be transcribed, False if already in Neo4j
        """
        # Always transcribe if not in combined mode or Neo4j unavailable
        if not self._combined_mode or not self._neo4j_available:
            return True
        
        try:
            # Generate expected VTT filename to create episode ID
            from src.tracking import generate_episode_id
            
            # Normalize title for filename (matching transcriber logic)
            normalized_title = self._normalize_title(episode_title)
            filename = f"{date}_{normalized_title}.vtt"
            
            # Generate episode ID
            episode_id = generate_episode_id(filename, podcast_id)
            
            # Get Neo4j tracker for this podcast
            tracker = self.get_neo4j_tracker(podcast_id)
            
            if tracker:
                is_processed = tracker.is_episode_processed(episode_id)
                if is_processed:
                    logger.info(f"Episode {episode_id} already in knowledge graph, skipping transcription")
                    return False
                else:
                    logger.debug(f"Episode {episode_id} not found in Neo4j, proceeding with transcription")
                    return True
            else:
                # No tracker available, proceed with transcription
                return True
                
        except Exception as e:
            logger.error(f"Error checking Neo4j for episode: {e}")
            # On error, proceed with transcription to be safe
            return True
    
    def get_neo4j_tracker(self, podcast_id: str) -> Optional[Any]:
        """
        Get Neo4j episode tracker for specific podcast.
        
        Args:
            podcast_id: Podcast identifier
            
        Returns:
            EpisodeTracker instance or None if unavailable
        """
        if not self._neo4j_available:
            return None
        
        try:
            from src.tracking import EpisodeTracker
            from src.storage.graph_storage import GraphStorageService
            from src.storage.multi_database_graph_storage import MultiDatabaseGraphStorage
            
            # Check if we have config for this podcast
            if podcast_id not in self._podcast_configs:
                logger.warning(f"No database configuration found for podcast: {podcast_id}")
                return None
            
            # Check if we already have a tracker for this podcast (connection pooling)
            if podcast_id in self._connection_pool:
                return self._connection_pool[podcast_id]
            
            # Create graph storage for this podcast's database
            db_config = self._podcast_configs[podcast_id]
            
            # Check if we're in multi-podcast mode
            if len(self._podcast_configs) > 1:
                # Use multi-database storage for proper routing
                graph_storage = MultiDatabaseGraphStorage()
                graph_storage.set_podcast_context(podcast_id)
            else:
                # Single podcast mode - use regular graph storage
                graph_storage = GraphStorageService()
            
            # Create episode tracker and cache it
            tracker = EpisodeTracker(graph_storage)
            self._connection_pool[podcast_id] = tracker
            
            logger.debug(f"Created and cached Neo4j tracker for podcast: {podcast_id}")
            return tracker
            
        except Exception as e:
            logger.error(f"Error creating Neo4j tracker for podcast {podcast_id}: {e}")
            return None
    
    def _normalize_title(self, title: str) -> str:
        """
        Normalize episode title to match transcriber's filename generation.
        
        Args:
            title: Original episode title
            
        Returns:
            Normalized title for filename
        """
        import re
        
        # This should match the logic in transcriber's file_organizer_simple.py
        # and title_utils.py
        
        # Convert to lowercase
        normalized = title.lower()
        
        # Remove special characters and replace with spaces
        normalized = re.sub(r'[^\w\s-]', ' ', normalized)
        
        # Replace multiple spaces with single space
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Replace spaces with underscores
        normalized = normalized.replace(' ', '_')
        
        # Remove leading/trailing underscores
        normalized = normalized.strip('_')
        
        return normalized
    
    def cleanup(self):
        """Clean up any open connections."""
        if self._connection_pool:
            logger.info("Cleaning up Neo4j connections...")
            for podcast_id, tracker in self._connection_pool.items():
                try:
                    if hasattr(tracker, 'storage') and hasattr(tracker.storage, 'close'):
                        tracker.storage.close()
                        logger.debug(f"Closed connection for podcast: {podcast_id}")
                except Exception as e:
                    logger.error(f"Error closing connection for podcast {podcast_id}: {e}")
            
            self._connection_pool.clear()


# Create a singleton instance
_tracker_instance = None


def get_tracker() -> TranscriptionTracker:
    """Get or create the singleton tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = TranscriptionTracker()
    return _tracker_instance