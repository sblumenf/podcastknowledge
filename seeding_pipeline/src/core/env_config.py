"""
Centralized environment variable management.

This module provides a single place to access all environment variables
with validation, helpful error messages, and defaults.
"""

from typing import Optional, Dict, Any
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the seeding_pipeline directory
# This ensures it works regardless of where the script is run from
current_file = Path(__file__).resolve()
seeding_pipeline_dir = current_file.parent.parent.parent  # Go up to seeding_pipeline/
env_path = seeding_pipeline_dir / '.env'

if env_path.exists():
    load_dotenv(env_path)
else:
    # Try current working directory as fallback
    fallback_env = Path('.env')
    if fallback_env.exists():
        load_dotenv(fallback_env)
class EnvironmentConfig:
    """Centralized environment variable access with validation."""
    
    @staticmethod
    def get_required(key: str, description: str) -> str:
        """Get a required environment variable with helpful error message."""
        value = os.getenv(key)
        if not value:
            raise ValueError(
                f"Required environment variable {key} is not set.\n"
                f"Description: {description}\n"
                f"Please set it in your .env file or export it:\n"
                f"  export {key}=your_value"
            )
        return value
    
    @staticmethod
    def get_optional(key: str, default: Optional[str] = None, description: str = "") -> Optional[str]:
        """Get an optional environment variable with default."""
        value = os.getenv(key, default)
        if not value and description:
            # Log info about optional variable
            pass
        return value
    
    @staticmethod
    def get_bool(key: str, default: bool = False, description: str = "") -> bool:
        """Get a boolean environment variable."""
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "on", "enabled")
    
    @staticmethod
    def get_int(key: str, default: int = 0, description: str = "") -> int:
        """Get an integer environment variable."""
        value = os.getenv(key, str(default))
        try:
            return int(value)
        except ValueError:
            raise ValueError(
                f"Environment variable {key} must be an integer.\n"
                f"Current value: '{value}'\n"
                f"Description: {description}"
            )
    
    @staticmethod
    def get_float(key: str, default: float = 0.0, description: str = "") -> float:
        """Get a float environment variable."""
        value = os.getenv(key, str(default))
        try:
            return float(value)
        except ValueError:
            raise ValueError(
                f"Environment variable {key} must be a float.\n"
                f"Current value: '{value}'\n"
                f"Description: {description}"
            )
    
    @classmethod
    def get_all_env_vars(cls) -> Dict[str, Any]:
        """Get all environment variables used by the application."""
        return {
            # Database Configuration
            "NEO4J_URI": cls.get_optional(
                "NEO4J_URI", 
                "bolt://localhost:7687",
                "Neo4j database connection URI"
            ),
            "NEO4J_USERNAME": cls.get_optional(
                "NEO4J_USERNAME",
                "neo4j",
                "Neo4j username"
            ),
            "NEO4J_PASSWORD": cls.get_optional(
                "NEO4J_PASSWORD",
                None,
                "Neo4j password (required for production)"
            ),
            "NEO4J_DATABASE": cls.get_optional(
                "NEO4J_DATABASE",
                "neo4j",
                "Neo4j database name"
            ),
            
            # API Keys
            "GOOGLE_API_KEY": cls.get_optional(
                "GOOGLE_API_KEY",
                None,
                "Google API key for Gemini models (backward compatibility)"
            ),
            "GEMINI_API_KEY": cls.get_optional(
                "GEMINI_API_KEY",
                None,
                "Primary Gemini API key (alternative to GOOGLE_API_KEY)"
            ),
            "GEMINI_API_KEY_1": cls.get_optional(
                "GEMINI_API_KEY_1",
                None,
                "First Gemini API key for rotation"
            ),
            "GEMINI_API_KEY_2": cls.get_optional(
                "GEMINI_API_KEY_2",
                None,
                "Second Gemini API key for rotation"
            ),
            "GEMINI_API_KEY_3": cls.get_optional(
                "GEMINI_API_KEY_3",
                None,
                "Third Gemini API key for rotation"
            ),
            "GEMINI_API_KEY_4": cls.get_optional(
                "GEMINI_API_KEY_4",
                None,
                "Fourth Gemini API key for rotation"
            ),
            "GEMINI_API_KEY_5": cls.get_optional(
                "GEMINI_API_KEY_5",
                None,
                "Fifth Gemini API key for rotation"
            ),
            "GEMINI_API_KEY_6": cls.get_optional(
                "GEMINI_API_KEY_6",
                None,
                "Sixth Gemini API key for rotation"
            ),
            "GEMINI_API_KEY_7": cls.get_optional(
                "GEMINI_API_KEY_7",
                None,
                "Seventh Gemini API key for rotation"
            ),
            "GEMINI_API_KEY_8": cls.get_optional(
                "GEMINI_API_KEY_8",
                None,
                "Eighth Gemini API key for rotation"
            ),
            "GEMINI_API_KEY_9": cls.get_optional(
                "GEMINI_API_KEY_9",
                None,
                "Ninth Gemini API key for rotation"
            ),
            "OPENAI_API_KEY": cls.get_optional(
                "OPENAI_API_KEY",
                None,
                "OpenAI API key for GPT models"
            ),
            "HF_TOKEN": cls.get_optional(
                "HF_TOKEN",
                None,
                "Hugging Face token for model access"
            ),
            
            # Model Configuration
            "GEMINI_FLASH_MODEL": cls.get_optional(
                "GEMINI_FLASH_MODEL",
                "gemini-2.5-flash-preview-05-20",
                "Gemini Flash model for fast processing (speaker ID, conversation analysis)"
            ),
            "GEMINI_PRO_MODEL": cls.get_optional(
                "GEMINI_PRO_MODEL", 
                "gemini-2.5-pro-preview-06-05",
                "Gemini Pro model for complex reasoning (knowledge extraction)"
            ),
            "GEMINI_EMBEDDING_MODEL": cls.get_optional(
                "GEMINI_EMBEDDING_MODEL",
                "text-embedding-004", 
                "Gemini embedding model for vector operations"
            ),
            
            # Feature Flags
            "USE_SCHEMALESS_EXTRACTION": cls.get_bool(
                "USE_SCHEMALESS_EXTRACTION",
                False,
                "Enable schemaless entity extraction"
            ),
            
            # Performance Settings
            "SCHEMALESS_CONFIDENCE_THRESHOLD": cls.get_float(
                "SCHEMALESS_CONFIDENCE_THRESHOLD",
                0.7,
                "Confidence threshold for schemaless extraction"
            ),
            "ENTITY_RESOLUTION_THRESHOLD": cls.get_float(
                "ENTITY_RESOLUTION_THRESHOLD",
                0.85,
                "Similarity threshold for entity resolution"
            ),
            "MAX_PROPERTIES_PER_NODE": cls.get_int(
                "MAX_PROPERTIES_PER_NODE",
                50,
                "Maximum properties allowed per graph node"
            ),
            
            # Logging and Monitoring
            "LOG_LEVEL": cls.get_optional(
                "LOG_LEVEL",
                "INFO",
                "Logging level (DEBUG, INFO, WARNING, ERROR)"
            ),
            "LOG_FORMAT": cls.get_optional(
                "LOG_FORMAT",
                "json",
                "Log format (json or text)"
            ),
            
            # Resource Limits
            "MAX_WORKERS": cls.get_int(
                "MAX_WORKERS",
                4,
                "Maximum number of worker threads"
            ),
            "MAX_MEMORY_GB": cls.get_float(
                "MAX_MEMORY_GB",
                4.0,
                "Maximum memory usage in GB"
            ),
            "MAX_MEMORY_MB": cls.get_int(
                "MAX_MEMORY_MB",
                2048,
                "Maximum memory usage in MB"
            ),
            "MAX_CONCURRENT_FILES": cls.get_int(
                "MAX_CONCURRENT_FILES",
                1,
                "Maximum concurrent files to process"
            ),
            "BATCH_SIZE": cls.get_int(
                "BATCH_SIZE",
                10,
                "Processing batch size"
            ),
            
            # Feature Flags
            "ENABLE_ENHANCED_LOGGING": cls.get_bool(
                "ENABLE_ENHANCED_LOGGING",
                False,
                "Enable enhanced logging with rotation and JSON format"
            ),
            "ENABLE_METRICS": cls.get_bool(
                "ENABLE_METRICS",
                False,
                "Enable metrics collection"
            ),
            
            # Development Settings
            "DEBUG_MODE": cls.get_bool(
                "DEBUG_MODE",
                False,
                "Enable debug mode"
            ),
            "CHECKPOINT_DIR": cls.get_optional(
                "CHECKPOINT_DIR",
                "checkpoints",
                "Directory for storing checkpoints"
            ),
            "OUTPUT_DIR": cls.get_optional(
                "OUTPUT_DIR",
                "output",
                "Directory for output files"
            ),
            "STATE_DIR": cls.get_optional(
                "STATE_DIR",
                "data",
                "Directory for storing API key rotation state files"
            ),
        }
    
    @classmethod
    def validate_required_vars(cls, required_vars: list) -> None:
        """Validate that required environment variables are set."""
        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)
        
        if missing:
            raise ValueError(
                f"Missing required environment variables:\n"
                f"{', '.join(missing)}\n\n"
                f"Please set these in your .env file or export them:\n"
                + '\n'.join(f"  export {var}=your_value" for var in missing)
            )
    
    @classmethod
    def get_flash_model(cls) -> str:
        """Get the configured Gemini Flash model name."""
        return cls.get_optional("GEMINI_FLASH_MODEL", "gemini-2.5-flash-preview-05-20", "Gemini Flash model")
    
    @classmethod
    def get_pro_model(cls) -> str:
        """Get the configured Gemini Pro model name."""
        return cls.get_optional("GEMINI_PRO_MODEL", "gemini-2.5-pro-preview-06-05", "Gemini Pro model")
    
    @classmethod
    def get_embedding_model(cls) -> str:
        """Get the configured Gemini embedding model name."""
        return cls.get_optional("GEMINI_EMBEDDING_MODEL", "text-embedding-004", "Gemini embedding model")
    
    @classmethod
    def validate_model_configuration(cls) -> Dict[str, Any]:
        """Validate that configured model names are valid.
        
        Returns:
            Dictionary with validation results:
            {
                'valid': bool,
                'flash_model': {'name': str, 'valid': bool, 'message': str},
                'pro_model': {'name': str, 'valid': bool, 'message': str},
                'embedding_model': {'name': str, 'valid': bool, 'message': str},
                'errors': List[str]
            }
        """
        # Valid model names from Google GenAI documentation
        valid_text_models = {
            'gemini-2.0-flash-001',
            'gemini-2.5-flash-001', 
            'gemini-2.5-pro-001',
            # Include preview models for backward compatibility
            'gemini-2.5-flash-preview-05-20',
            'gemini-2.5-pro-preview-06-05'
        }
        
        valid_embedding_models = {
            'text-embedding-004',
            'models/text-embedding-004'
        }
        
        # Get configured models
        flash_model = cls.get_flash_model()
        pro_model = cls.get_pro_model()
        embedding_model = cls.get_embedding_model()
        
        results = {
            'valid': True,
            'flash_model': {'name': flash_model, 'valid': True, 'message': 'Valid'},
            'pro_model': {'name': pro_model, 'valid': True, 'message': 'Valid'},
            'embedding_model': {'name': embedding_model, 'valid': True, 'message': 'Valid'},
            'errors': []
        }
        
        # Validate flash model
        if flash_model not in valid_text_models:
            results['flash_model']['valid'] = False
            results['flash_model']['message'] = f"Invalid model. Valid options: {', '.join(sorted(valid_text_models))}"
            results['errors'].append(f"GEMINI_FLASH_MODEL '{flash_model}' is not a valid model name")
            results['valid'] = False
        
        # Validate pro model
        if pro_model not in valid_text_models:
            results['pro_model']['valid'] = False
            results['pro_model']['message'] = f"Invalid model. Valid options: {', '.join(sorted(valid_text_models))}"
            results['errors'].append(f"GEMINI_PRO_MODEL '{pro_model}' is not a valid model name")
            results['valid'] = False
        
        # Validate embedding model
        if embedding_model not in valid_embedding_models:
            results['embedding_model']['valid'] = False
            results['embedding_model']['message'] = f"Invalid model. Valid options: {', '.join(sorted(valid_embedding_models))}"
            results['errors'].append(f"GEMINI_EMBEDDING_MODEL '{embedding_model}' is not a valid model name")
            results['valid'] = False
        
        return results
    
    @classmethod
    def get_config_summary(cls) -> str:
        """Get a summary of all configuration values (masking secrets)."""
        config = cls.get_all_env_vars()
        summary = ["Environment Configuration:"]
        
        for key, value in sorted(config.items()):
            if any(secret in key.upper() for secret in ["PASSWORD", "KEY", "TOKEN"]):
                display_value = "***" if value else "Not set"
            else:
                display_value = str(value)
            summary.append(f"  {key}: {display_value}")
        
        return "\n".join(summary)


# Convenience instance
env_config = EnvironmentConfig()