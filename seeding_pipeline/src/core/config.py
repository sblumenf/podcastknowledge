"""
Configuration management for the podcast knowledge pipeline.

This module implements a hybrid configuration system that loads:
- Secrets from environment variables (.env file)
- Settings from YAML configuration files
- Defaults from code
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import json
import os
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If dotenv not available, just use environment variables directly
    pass

from .exceptions import ConfigurationError


@dataclass
class PipelineConfig:
    """Base configuration for the podcast processing pipeline."""
    
    # Processing Settings
    min_segment_tokens: int = 150
    max_segment_tokens: int = 800
    min_speakers: int = 1
    max_speakers: int = 10
    
    # Neo4j Database Settings (from environment)
    neo4j_uri: str = field(default_factory=lambda: os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    neo4j_username: str = field(default_factory=lambda: os.environ.get("NEO4J_USERNAME", "neo4j"))
    neo4j_password: Optional[str] = field(default_factory=lambda: os.environ.get("NEO4J_PASSWORD"))
    neo4j_database: str = field(default_factory=lambda: os.environ.get("NEO4J_DATABASE", "neo4j"))
    
    # API Keys (from environment)
    google_api_key: Optional[str] = field(default_factory=lambda: os.environ.get("GOOGLE_API_KEY"))
    openai_api_key: Optional[str] = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY"))
    hf_token: Optional[str] = field(default_factory=lambda: os.environ.get("HF_TOKEN"))
    
    # Embedding Settings
    embedding_dimensions: int = 768  # Gemini text-embedding-004 dimensions
    embedding_similarity: str = "cosine"
    embedding_model: str = "models/text-embedding-004"  # Gemini embedding model
    gemini_embedding_batch_size: int = 100  # Optimal batch size for Gemini API
    
    # File Paths
    base_dir: Path = field(default_factory=lambda: Path("."))
    output_dir: Path = field(default_factory=lambda: Path("./processed_podcasts"))
    checkpoint_dir: Path = field(default_factory=lambda: Path("./checkpoints"))
    
    # Processing Settings
    use_large_context: bool = True
    enable_graph_enhancements: bool = True
    
    # GPU and Memory Settings
    use_gpu: bool = True
    enable_ad_detection: bool = True
    use_semantic_boundaries: bool = True
    gpu_memory_fraction: float = 0.8
    
    # Progress and Monitoring
    checkpoint_interval: int = 1  # Save after N episodes
    memory_cleanup_interval: int = 1  # Cleanup after N episodes
    
    # Logging
    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))
    
    # Schemaless Extraction Settings
    use_schemaless_extraction: bool = field(default_factory=lambda: os.environ.get("USE_SCHEMALESS_EXTRACTION", "false").lower() == "true")
    schemaless_confidence_threshold: float = field(default_factory=lambda: float(os.environ.get("SCHEMALESS_CONFIDENCE_THRESHOLD", "0.7")))
    entity_resolution_threshold: float = field(default_factory=lambda: float(os.environ.get("ENTITY_RESOLUTION_THRESHOLD", "0.85")))
    max_properties_per_node: int = field(default_factory=lambda: int(os.environ.get("MAX_PROPERTIES_PER_NODE", "50")))
    relationship_normalization: bool = field(default_factory=lambda: os.environ.get("RELATIONSHIP_NORMALIZATION", "true").lower() == "true")
    
    def __post_init__(self):
        """Convert string paths to Path objects and validate configuration."""
        # Convert paths
        self.base_dir = Path(self.base_dir)
        self.output_dir = Path(self.output_dir)
        self.checkpoint_dir = Path(self.checkpoint_dir)
        
        # Make paths absolute if they're relative
        if not self.output_dir.is_absolute():
            self.output_dir = self.base_dir / self.output_dir
        if not self.checkpoint_dir.is_absolute():
            self.checkpoint_dir = self.base_dir / self.checkpoint_dir
            
        # Validate
        self.validate()
    
    def validate(self) -> None:
        """Validate configuration values."""
        errors = []
        
        # Check required environment variables
        if not self.neo4j_password:
            errors.append("NEO4J_PASSWORD environment variable is required")
        if not self.google_api_key and not self.openai_api_key:
            errors.append("At least one of GOOGLE_API_KEY or OPENAI_API_KEY is required")
            
        # Validate numeric ranges
        if self.min_segment_tokens >= self.max_segment_tokens:
            errors.append("min_segment_tokens must be less than max_segment_tokens")
        if self.min_speakers > self.max_speakers:
            errors.append("min_speakers must be less than or equal to max_speakers")
        if not 0 < self.gpu_memory_fraction <= 1:
            errors.append("gpu_memory_fraction must be between 0 and 1")
            
        # Validate schemaless settings
        if not 0 <= self.schemaless_confidence_threshold <= 1:
            errors.append("schemaless_confidence_threshold must be between 0 and 1")
        if not 0 <= self.entity_resolution_threshold <= 1:
            errors.append("entity_resolution_threshold must be between 0 and 1")
        if self.max_properties_per_node < 1:
            errors.append("max_properties_per_node must be at least 1")
            
        # Validate paths exist or can be created
        for path_name, path_value in [
            ("output_dir", self.output_dir),
            ("checkpoint_dir", self.checkpoint_dir)
        ]:
            try:
                path_value.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create {path_name} at {path_value}: {e}")
                
        if errors:
            raise ConfigurationError(
                f"Configuration validation failed: {'; '.join(errors)}",
                details={"errors": errors}
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (excluding secrets)."""
        config_dict = {}
        for key, value in self.__dict__.items():
            # Skip sensitive fields
            if key in ["neo4j_password", "google_api_key", "openai_api_key", "hf_token"]:
                config_dict[key] = "***" if value else None
            elif isinstance(value, Path):
                config_dict[key] = str(value)
            else:
                config_dict[key] = value
        return config_dict
    
    @classmethod
    def from_file(cls, config_path: Path) -> "PipelineConfig":
        """Load configuration from YAML file."""
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")
            
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_path.suffix in ['.yaml', '.yml']:
                if not YAML_AVAILABLE:
                    raise ConfigurationError("YAML support not available. Install PyYAML: pip install pyyaml")
                config_data = yaml.safe_load(f)
            elif config_path.suffix == '.json':
                config_data = json.load(f)
            else:
                raise ConfigurationError(f"Unsupported config format: {config_path.suffix}")
                
        # Create instance with file data, environment variables override
        return cls(**config_data)


@dataclass
class SeedingConfig(PipelineConfig):
    """Configuration optimized for batch knowledge seeding."""
    
    # Batch processing settings
    batch_size: int = 10
    embedding_batch_size: int = 100  # Increased for Gemini API efficiency
    save_checkpoints: bool = True
    checkpoint_every_n: int = 5  # Episodes
    
    # Progress settings
    enable_progress_bar: bool = True
    show_memory_usage: bool = True
    
    # Disable interactive features for batch mode
    interactive_mode: bool = False
    save_visualizations: bool = False
    generate_reports: bool = False
    verbose_logging: bool = False
    
    # Rate limiting
    llm_requests_per_minute: int = 60
    llm_tokens_per_minute: int = 150000
    embedding_requests_per_minute: int = 500
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    exponential_backoff: bool = True
    
    # Resource limits
    max_concurrent_llm_jobs: int = 4
    max_memory_gb: float = 4.0
    
    def __post_init__(self):
        """Set appropriate defaults for batch mode."""
        # Override parent settings for batch mode
        if not self.verbose_logging:
            self.log_level = "ERROR"
            
        # Call parent post_init
        super().__post_init__()
    
    def get_segmenter_config(self) -> Dict[str, Any]:
        """Get configuration for the podcast segmenter."""
        return {
            'min_segment_tokens': self.min_segment_tokens,
            'max_segment_tokens': self.max_segment_tokens,
            'use_gpu': self.use_gpu,
            'ad_detection_enabled': self.enable_ad_detection,
            'use_semantic_boundaries': self.use_semantic_boundaries,
            'min_speakers': self.min_speakers,
            'max_speakers': self.max_speakers,
            'batch_size': self.batch_size,
        }
    
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get rate limiting configuration."""
        return {
            'llm_rpm': self.llm_requests_per_minute,
            'llm_tpm': self.llm_tokens_per_minute,
            'embedding_rpm': self.embedding_requests_per_minute,
        }
    
    def validate_dependencies(self) -> List[str]:
        """Check which optional dependencies are available."""
        available = []
        missing = []
        
                
        # Check LLM providers
        try:
            import langchain_google_genai
            available.append("langchain-google-genai")
        except ImportError:
            missing.append("langchain-google-genai")
            
        try:
            import openai
            available.append("openai")
        except ImportError:
            if not self.openai_api_key:
                # Only a problem if we need it
                pass
            else:
                missing.append("openai")
                
        # Check other dependencies
                
        return missing


# Configuration loading hierarchy
def load_config(
    config_path: Optional[Path] = None,
    config_type: str = "seeding"
) -> Union[PipelineConfig, SeedingConfig]:
    """
    Load configuration with the following precedence:
    1. Environment variables (highest)
    2. Config file
    3. Defaults (lowest)
    
    Args:
        config_path: Optional path to config file
        config_type: Type of config to load ("pipeline" or "seeding")
        
    Returns:
        Loaded configuration instance
    """
    # Select config class
    config_class = SeedingConfig if config_type == "seeding" else PipelineConfig
    
    # Load from file if provided
    if config_path:
        config = config_class.from_file(config_path)
    else:
        # Check for default config files
        default_paths = [
            Path("config/config.yml"),
            Path("config/config.yaml"),
            Path("config.yml"),
            Path("config.yaml"),
        ]
        
        for path in default_paths:
            if path.exists():
                config = config_class.from_file(path)
                break
        else:
            # Use all defaults
            config = config_class()
            
    return config


# Convenience functions
def get_neo4j_config(config: PipelineConfig) -> Dict[str, Any]:
    """Extract Neo4j configuration."""
    return {
        "uri": config.neo4j_uri,
        "auth": (config.neo4j_username, config.neo4j_password),
        "database": config.neo4j_database,
    }


def get_llm_config(config: PipelineConfig) -> Dict[str, Any]:
    """Extract LLM configuration."""
    return {
        "google_api_key": config.google_api_key,
        "openai_api_key": config.openai_api_key,
    }


# Alias for backward compatibility
Config = PipelineConfig