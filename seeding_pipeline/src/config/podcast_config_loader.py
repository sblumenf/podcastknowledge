"""Podcast configuration loader for YAML files."""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
import logging
from pydantic import ValidationError

from src.config.podcast_config_models import PodcastRegistry, PodcastConfig
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PodcastConfigLoader:
    """Loads and manages podcast configurations from YAML files."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the configuration loader.
        
        Args:
            config_path: Path to the YAML config file. If not provided,
                        looks for config/podcasts.yaml relative to project root
        """
        self.config_path = config_path or self._get_default_config_path()
        self._registry: Optional[PodcastRegistry] = None
        self._loaded = False
    
    def _get_default_config_path(self) -> Path:
        """Get the default configuration file path."""
        # Try several locations
        possible_paths = [
            Path("config/podcasts.yaml"),
            Path("../config/podcasts.yaml"),
            Path("/home/sergeblumenfeld/podcastknowledge/config/podcasts.yaml"),
            Path.home() / "podcastknowledge/config/podcasts.yaml"
        ]
        
        # Also check environment variable
        env_path = os.getenv("PODCAST_CONFIG_PATH")
        if env_path:
            possible_paths.insert(0, Path(env_path))
        
        for path in possible_paths:
            if path.exists():
                logger.info(f"Found podcast config at: {path}")
                return path
        
        # Default to the first option even if it doesn't exist
        default_path = Path("/home/sergeblumenfeld/podcastknowledge/config/podcasts.yaml")
        logger.warning(f"No podcast config found, using default path: {default_path}")
        return default_path
    
    def load(self, reload: bool = False) -> PodcastRegistry:
        """Load the podcast configuration from YAML file.
        
        Args:
            reload: Force reload even if already loaded
            
        Returns:
            PodcastRegistry containing all podcast configurations
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValidationError: If configuration is invalid
        """
        if self._loaded and not reload and self._registry:
            return self._registry
        
        if not self.config_path.exists():
            raise FileNotFoundError(f"Podcast configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            # Validate and create registry
            self._registry = PodcastRegistry(**config_data)
            
            # Apply defaults if specified
            self._registry.apply_defaults()
            
            # Merge with environment overrides
            self._apply_env_overrides()
            
            self._loaded = True
            logger.info(f"Loaded {len(self._registry.podcasts)} podcast configurations")
            
            return self._registry
            
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML config: {e}")
            raise ValueError(f"Invalid YAML in config file: {e}")
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load podcast configuration: {e}")
            raise
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration."""
        if not self._registry:
            return
        
        # Check for database override
        neo4j_uri = os.getenv("NEO4J_URI")
        neo4j_username = os.getenv("NEO4J_USERNAME")
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        
        for podcast in self._registry.podcasts:
            if not podcast.database:
                # Create default database config from environment
                from src.config.podcast_config_models import DatabaseConfig
                podcast.database = DatabaseConfig(
                    uri=neo4j_uri or "neo4j://localhost:7687",
                    username=neo4j_username,
                    password=neo4j_password
                )
            else:
                # Override with environment values if not set
                if not podcast.database.uri and neo4j_uri:
                    podcast.database.uri = neo4j_uri
                if not podcast.database.username and neo4j_username:
                    podcast.database.username = neo4j_username
                if not podcast.database.password and neo4j_password:
                    podcast.database.password = neo4j_password
    
    def get_registry(self) -> PodcastRegistry:
        """Get the loaded podcast registry.
        
        Returns:
            PodcastRegistry instance
            
        Raises:
            RuntimeError: If configuration hasn't been loaded yet
        """
        if not self._loaded or not self._registry:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self._registry
    
    def get_podcast(self, podcast_id: str) -> Optional[PodcastConfig]:
        """Get a specific podcast configuration.
        
        Args:
            podcast_id: The podcast identifier
            
        Returns:
            PodcastConfig if found, None otherwise
        """
        registry = self.get_registry()
        return registry.get_podcast(podcast_id)
    
    def save(self, registry: Optional[PodcastRegistry] = None, 
             path: Optional[Path] = None) -> None:
        """Save the podcast configuration to YAML file.
        
        Args:
            registry: Registry to save (uses loaded registry if not provided)
            path: Path to save to (uses config_path if not provided)
        """
        registry = registry or self._registry
        if not registry:
            raise RuntimeError("No registry to save")
        
        save_path = path or self.config_path
        
        # Ensure directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict for YAML serialization
        config_dict = registry.model_dump(exclude_none=True)
        
        # Write YAML with nice formatting
        with open(save_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Saved podcast configuration to: {save_path}")
    
    def create_example_config(self, path: Optional[Path] = None) -> None:
        """Create an example podcast configuration file.
        
        Args:
            path: Path to save example config (uses config_path if not provided)
        """
        from src.config.podcast_config_models import (
            PodcastRegistry, PodcastConfig, DatabaseConfig, 
            ProcessingConfig, PodcastMetadata
        )
        
        example_registry = PodcastRegistry(
            version="1.0",
            defaults=ProcessingConfig(
                batch_size=10,
                max_retries=3,
                enable_flow_analysis=True,
                enable_graph_enhancement=True,
                use_large_context=True
            ),
            podcasts=[
                PodcastConfig(
                    id="tech_talk",
                    name="Tech Talk Podcast",
                    enabled=True,
                    database=DatabaseConfig(
                        uri="neo4j://localhost:7687",
                        database_name="tech_talk"
                    ),
                    metadata=PodcastMetadata(
                        description="A podcast about technology trends and innovations",
                        language="en",
                        category="Technology",
                        tags=["tech", "software", "innovation"],
                        host="John Doe",
                        website="https://techtalk.example.com"
                    )
                ),
                PodcastConfig(
                    id="data_science_hour",
                    name="Data Science Hour",
                    enabled=True,
                    database=DatabaseConfig(
                        uri="neo4j://localhost:7687",
                        database_name="data_science"
                    ),
                    processing=ProcessingConfig(
                        batch_size=5,  # Override default
                        custom_prompts={
                            "entity_extraction": "Focus on data science concepts, tools, and methodologies"
                        }
                    ),
                    metadata=PodcastMetadata(
                        description="Weekly discussions on data science and machine learning",
                        language="en",
                        category="Science",
                        tags=["data-science", "machine-learning", "AI"],
                        host="Jane Smith"
                    )
                ),
                PodcastConfig(
                    id="startup_stories",
                    name="Startup Stories",
                    enabled=False,  # Disabled example
                    metadata=PodcastMetadata(
                        description="Interviews with successful startup founders",
                        language="en",
                        category="Business",
                        tags=["startup", "entrepreneurship", "business"]
                    )
                )
            ]
        )
        
        self.save(example_registry, path or self.config_path)
        logger.info("Created example podcast configuration file")


# Singleton instance
_loader_instance: Optional[PodcastConfigLoader] = None


def get_podcast_config_loader(config_path: Optional[Path] = None) -> PodcastConfigLoader:
    """Get the singleton podcast configuration loader.
    
    Args:
        config_path: Path to config file (only used on first call)
        
    Returns:
        PodcastConfigLoader instance
    """
    global _loader_instance
    
    if _loader_instance is None:
        _loader_instance = PodcastConfigLoader(config_path)
    
    return _loader_instance