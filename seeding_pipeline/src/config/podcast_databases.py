"""Podcast database routing configuration using the new YAML config system."""

import os
from pathlib import Path
from typing import Dict, Optional, Any
import logging

from src.config.podcast_config_loader import get_podcast_config_loader
from src.config.podcast_config_models import PodcastConfig, PodcastRegistry

logger = logging.getLogger(__name__)


class PodcastDatabaseConfig:
    """Configuration for podcast-to-database mapping using YAML config."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize podcast database configuration.
        
        Args:
            config_path: Path to configuration file. Uses default if not provided.
        """
        config_path_obj = Path(config_path) if config_path else None
        self._config_loader = get_podcast_config_loader(config_path_obj)
        self._registry: Optional[PodcastRegistry] = None
        self._legacy_mode = False
        self._load_config()
        
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            self._registry = self._config_loader.load()
            logger.info(f"Loaded podcast registry with {len(self._registry.podcasts)} podcasts")
        except FileNotFoundError:
            logger.warning("No podcast configuration file found, using legacy mode")
            self._legacy_mode = True
            self._setup_legacy_config()
        except Exception as e:
            logger.error(f"Failed to load podcast configuration: {e}")
            self._legacy_mode = True
            self._setup_legacy_config()
    
    def _setup_legacy_config(self) -> None:
        """Setup legacy configuration for backward compatibility."""
        # Create a minimal registry for legacy mode
        from src.config.podcast_config_models import PodcastRegistry, PodcastConfig, DatabaseConfig
        
        self._registry = PodcastRegistry(
            version="1.0",
            podcasts=[
                PodcastConfig(
                    id="unknown_podcast",
                    name="Unknown Podcast",
                    database=DatabaseConfig(
                        uri=os.getenv('NEO4J_URI', 'neo4j://localhost:7687'),
                        database_name=os.getenv('NEO4J_DATABASE', 'neo4j')
                    )
                )
            ]
        )
        
    def get_database_for_podcast(self, podcast_id: str) -> str:
        """Get database name for a podcast ID.
        
        Args:
            podcast_id: Podcast identifier
            
        Returns:
            Database name to use
        """
        if not self._registry:
            return os.getenv('NEO4J_DATABASE', 'neo4j')
        
        podcast = self._registry.get_podcast(podcast_id)
        if podcast:
            return podcast.get_database_name()
        
        # Default database for unknown podcasts
        return os.getenv('NEO4J_DATABASE', 'neo4j')
        
    def get_podcast_config(self, podcast_id: str) -> Dict[str, Any]:
        """Get full configuration for a podcast.
        
        Args:
            podcast_id: Podcast identifier
            
        Returns:
            Podcast configuration dictionary
        """
        if not self._registry:
            return {}
        
        podcast = self._registry.get_podcast(podcast_id)
        if podcast:
            return podcast.model_dump(exclude_none=True)
        
        return {}
        
    def add_podcast(self, podcast_id: str, config: Dict[str, Any]) -> None:
        """Add or update podcast configuration.
        
        Args:
            podcast_id: Podcast identifier
            config: Podcast configuration
        """
        if not self._registry:
            return
        
        # This would require modifying the registry and saving
        # For now, log a warning
        logger.warning("Dynamic podcast addition not yet implemented. Please update podcasts.yaml manually.")
        
    def save_config(self) -> None:
        """Save configuration to file."""
        if self._legacy_mode:
            logger.warning("Cannot save config in legacy mode")
            return
        
        try:
            self._config_loader.save(self._registry)
        except Exception as e:
            logger.error(f"Failed to save podcast config: {e}")
            
    def list_podcasts(self) -> Dict[str, str]:
        """List all configured podcasts with their databases.
        
        Returns:
            Dictionary mapping podcast IDs to database names
        """
        result = {}
        
        if not self._registry:
            return {'unknown_podcast': 'neo4j'}
        
        for podcast in self._registry.podcasts:
            result[podcast.id] = podcast.get_database_name()
            
        return result
        
    def create_database_config(self, podcast_id: str, base_uri: str) -> Dict[str, str]:
        """Create database connection config for a podcast.
        
        Args:
            podcast_id: Podcast identifier
            base_uri: Base Neo4j URI (may be overridden by podcast config)
            
        Returns:
            Database connection configuration
        """
        if not self._registry:
            return {
                'uri': base_uri,
                'database': self.get_database_for_podcast(podcast_id)
            }
        
        podcast = self._registry.get_podcast(podcast_id)
        if podcast and podcast.database:
            # Use podcast-specific configuration
            return {
                'uri': podcast.database.uri or base_uri,
                'database': podcast.get_database_name(),
                'username': podcast.database.username,
                'password': podcast.database.password
            }
        
        # Default configuration
        return {
            'uri': base_uri,
            'database': self.get_database_for_podcast(podcast_id)
        }
    
    def get_enabled_podcasts(self) -> list[str]:
        """Get list of enabled podcast IDs.
        
        Returns:
            List of enabled podcast IDs
        """
        if not self._registry:
            return []
        
        return [p.id for p in self._registry.get_enabled_podcasts()]