"""Podcast configuration models using Pydantic for validation."""

from typing import Dict, List, Optional, Any
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, ConfigDict
import re


class DatabaseConfig(BaseModel):
    """Database configuration for a podcast."""
    
    uri: str = Field(description="Neo4j database URI")
    database_name: Optional[str] = Field(None, description="Specific database name (defaults to podcast ID)")
    username: Optional[str] = Field(None, description="Database username (defaults to env NEO4J_USERNAME)")
    password: Optional[str] = Field(None, description="Database password (defaults to env NEO4J_PASSWORD)")
    
    @field_validator('uri')
    @classmethod
    def validate_uri(cls, v: str) -> str:
        """Validate Neo4j URI format."""
        if not v.startswith(('neo4j://', 'neo4j+s://', 'bolt://', 'bolt+s://')):
            raise ValueError("Database URI must start with neo4j://, neo4j+s://, bolt://, or bolt+s://")
        return v


class ProcessingConfig(BaseModel):
    """Processing configuration for a podcast."""
    
    model_config = ConfigDict(extra='allow')
    
    batch_size: int = Field(10, ge=1, le=100, description="Number of episodes to process in parallel")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum retries for failed episodes")
    enable_flow_analysis: bool = Field(True, description="Enable episode flow analysis")
    enable_graph_enhancement: bool = Field(True, description="Enable graph enhancement")
    use_large_context: bool = Field(True, description="Use large context models")
    custom_prompts: Optional[Dict[str, str]] = Field(None, description="Custom prompts for this podcast")


class PodcastMetadata(BaseModel):
    """Podcast metadata."""
    
    description: Optional[str] = Field(None, description="Podcast description")
    language: str = Field("en", description="Primary language code")
    category: Optional[str] = Field(None, description="Podcast category")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    host: Optional[str] = Field(None, description="Podcast host(s)")
    website: Optional[str] = Field(None, description="Podcast website URL")
    
    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate language code format."""
        if not re.match(r'^[a-z]{2}(-[A-Z]{2})?$', v):
            raise ValueError("Language must be ISO 639-1 code (e.g., 'en' or 'en-US')")
        return v


class PodcastConfig(BaseModel):
    """Complete configuration for a single podcast."""
    
    id: str = Field(description="Unique podcast identifier")
    name: str = Field(description="Human-readable podcast name")
    enabled: bool = Field(True, description="Whether this podcast is enabled for processing")
    
    database: Optional[DatabaseConfig] = Field(None, description="Database configuration")
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig, description="Processing settings")
    metadata: PodcastMetadata = Field(default_factory=PodcastMetadata, description="Podcast metadata")
    
    # Directory paths (relative to data root)
    transcript_dir: Optional[str] = Field(None, description="Custom transcript directory")
    processed_dir: Optional[str] = Field(None, description="Custom processed directory")
    checkpoint_dir: Optional[str] = Field(None, description="Custom checkpoint directory")
    
    @field_validator('id')
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate podcast ID format."""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Podcast ID must contain only letters, numbers, underscores, and hyphens")
        return v.lower()
    
    def get_database_name(self) -> str:
        """Get the database name for this podcast."""
        if self.database and self.database.database_name:
            return self.database.database_name
        return self.id
    
    def get_transcript_path(self, base_path: Path) -> Path:
        """Get the transcript directory path."""
        if self.transcript_dir:
            return base_path / self.transcript_dir
        return base_path / "podcasts" / self.id / "transcripts"
    
    def get_processed_path(self, base_path: Path) -> Path:
        """Get the processed directory path."""
        if self.processed_dir:
            return base_path / self.processed_dir
        return base_path / "podcasts" / self.id / "processed"
    
    def get_checkpoint_path(self, base_path: Path) -> Path:
        """Get the checkpoint directory path."""
        if self.checkpoint_dir:
            return base_path / self.checkpoint_dir
        return base_path / "podcasts" / self.id / "checkpoints"


class PodcastRegistry(BaseModel):
    """Registry of all podcast configurations."""
    
    version: str = Field("1.0", description="Configuration version")
    podcasts: List[PodcastConfig] = Field(description="List of podcast configurations")
    defaults: Optional[ProcessingConfig] = Field(None, description="Default processing configuration")
    
    @field_validator('podcasts')
    @classmethod
    def validate_unique_ids(cls, v: List[PodcastConfig]) -> List[PodcastConfig]:
        """Ensure all podcast IDs are unique."""
        ids = [p.id for p in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate podcast IDs found")
        return v
    
    def get_podcast(self, podcast_id: str) -> Optional[PodcastConfig]:
        """Get a podcast configuration by ID."""
        for podcast in self.podcasts:
            if podcast.id == podcast_id.lower():
                return podcast
        return None
    
    def get_enabled_podcasts(self) -> List[PodcastConfig]:
        """Get all enabled podcasts."""
        return [p for p in self.podcasts if p.enabled]
    
    def apply_defaults(self) -> None:
        """Apply default processing config to all podcasts."""
        if not self.defaults:
            return
        
        defaults_dict = self.defaults.model_dump()
        for podcast in self.podcasts:
            # Merge defaults with podcast-specific config
            current_dict = podcast.processing.model_dump()
            for key, value in defaults_dict.items():
                if key not in current_dict or current_dict[key] is None:
                    setattr(podcast.processing, key, value)