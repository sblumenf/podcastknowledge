"""
Centralized environment variable management.

This module provides a single place to access all environment variables
with validation, helpful error messages, and defaults.
"""

import os
from typing import Optional, Dict, Any


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
                "Google API key for Gemini models"
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
            
            # Feature Flags
            "USE_SCHEMALESS_EXTRACTION": cls.get_bool(
                "USE_SCHEMALESS_EXTRACTION",
                False,
                "Enable schemaless entity extraction"
            ),
            "ENABLE_TRACING": cls.get_bool(
                "ENABLE_TRACING",
                False,
                "Enable distributed tracing with Jaeger"
            ),
            "ENABLE_METRICS": cls.get_bool(
                "ENABLE_METRICS",
                False,
                "Enable Prometheus metrics collection"
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
            
            # Tracing Configuration
            "JAEGER_AGENT_HOST": cls.get_optional(
                "JAEGER_AGENT_HOST",
                "localhost",
                "Jaeger agent hostname"
            ),
            "JAEGER_AGENT_PORT": cls.get_int(
                "JAEGER_AGENT_PORT",
                6831,
                "Jaeger agent port"
            ),
            "SERVICE_NAME": cls.get_optional(
                "SERVICE_NAME",
                "podcast-kg-pipeline",
                "Service name for tracing"
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