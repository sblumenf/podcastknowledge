"""
Feature flag management for the podcast knowledge pipeline.

This module provides a centralized feature flag system for controlling
experimental features and gradual rollouts.
"""

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Dict, Any, Optional
import os

from ..utils.logging import get_logger
logger = get_logger(__name__)


class FeatureFlag(Enum):
    """Available feature flags for the pipeline."""
    
    # Core extraction flags
    LOG_SCHEMA_DISCOVERY = "LOG_SCHEMA_DISCOVERY"
    ENABLE_ENTITY_RESOLUTION_V2 = "ENABLE_ENTITY_RESOLUTION_V2"
    
    # Component enhancement flags (for Phase 9.5)
    ENABLE_TIMESTAMP_INJECTION = "ENABLE_TIMESTAMP_INJECTION"
    ENABLE_SPEAKER_INJECTION = "ENABLE_SPEAKER_INJECTION"
    ENABLE_QUOTE_POSTPROCESSING = "ENABLE_QUOTE_POSTPROCESSING"
    ENABLE_METADATA_ENRICHMENT = "ENABLE_METADATA_ENRICHMENT"
    ENABLE_ENTITY_RESOLUTION_POSTPROCESS = "ENABLE_ENTITY_RESOLUTION_POSTPROCESS"
    
    # Speaker identification flags
    ENABLE_SPEAKER_IDENTIFICATION = "ENABLE_SPEAKER_IDENTIFICATION"


@dataclass
class FlagConfig:
    """Configuration for a single feature flag."""
    name: str
    default_value: bool
    description: str
    env_var: Optional[str] = None
    
    def get_env_var(self) -> str:
        """Get the environment variable name for this flag."""
        return self.env_var or f"FF_{self.name}"


class FeatureFlagManager:
    """Manages feature flags for the application."""
    
    def __init__(self):
        """Initialize the feature flag manager."""
        self._flags: Dict[FeatureFlag, FlagConfig] = {
            FeatureFlag.LOG_SCHEMA_DISCOVERY: FlagConfig(
                name="LOG_SCHEMA_DISCOVERY",
                default_value=True,
                description="Log discovered schema types during schemaless extraction"
            ),
            FeatureFlag.ENABLE_ENTITY_RESOLUTION_V2: FlagConfig(
                name="ENABLE_ENTITY_RESOLUTION_V2",
                default_value=False,
                description="Use improved entity resolution algorithm"
            ),
            FeatureFlag.ENABLE_TIMESTAMP_INJECTION: FlagConfig(
                name="ENABLE_TIMESTAMP_INJECTION",
                default_value=True,
                description="Inject timestamps into extracted entities"
            ),
            FeatureFlag.ENABLE_SPEAKER_INJECTION: FlagConfig(
                name="ENABLE_SPEAKER_INJECTION",
                default_value=True,
                description="Inject speaker information into extracted entities"
            ),
            FeatureFlag.ENABLE_QUOTE_POSTPROCESSING: FlagConfig(
                name="ENABLE_QUOTE_POSTPROCESSING",
                default_value=True,
                description="Enable quote extraction post-processing"
            ),
            FeatureFlag.ENABLE_METADATA_ENRICHMENT: FlagConfig(
                name="ENABLE_METADATA_ENRICHMENT",
                default_value=True,
                description="Enrich extracted entities with metadata"
            ),
            FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS: FlagConfig(
                name="ENABLE_ENTITY_RESOLUTION_POSTPROCESS",
                default_value=True,
                description="Enable entity resolution post-processing"
            ),
            FeatureFlag.ENABLE_SPEAKER_IDENTIFICATION: FlagConfig(
                name="ENABLE_SPEAKER_IDENTIFICATION",
                default_value=True,
                description="Enable LLM-based speaker identification for VTT transcripts"
            ),
        }
        
        # Cache for flag values
        self._cache: Dict[FeatureFlag, bool] = {}
        
    def is_enabled(self, flag: FeatureFlag) -> bool:
        """
        Check if a feature flag is enabled.
        
        Args:
            flag: The feature flag to check
            
        Returns:
            True if the flag is enabled, False otherwise
        """
        if flag in self._cache:
            return self._cache[flag]
            
        config = self._flags.get(flag)
        if not config:
            logger.warning(f"Unknown feature flag: {flag}")
            return False
            
        # Check environment variable first
        env_var = config.get_env_var()
        env_value = os.environ.get(env_var)
        
        if env_value is not None:
            # Parse boolean from string
            value = env_value.lower() in ("true", "1", "yes", "on")
            logger.debug(f"Feature flag {flag.value} set to {value} from environment")
        else:
            value = config.default_value
            logger.debug(f"Feature flag {flag.value} using default value: {value}")
            
        self._cache[flag] = value
        return value
    
    def set_flag(self, flag: FeatureFlag, value: bool) -> None:
        """
        Set a feature flag value programmatically.
        
        Args:
            flag: The feature flag to set
            value: The value to set
        """
        if flag not in self._flags:
            raise ValueError(f"Unknown feature flag: {flag}")
            
        self._cache[flag] = value
        logger.info(f"Feature flag {flag.value} set to {value}")
        
    def get_all_flags(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all feature flags and their current values.
        
        Returns:
            Dictionary mapping flag names to their configuration and current value
        """
        result = {}
        for flag, config in self._flags.items():
            result[flag.value] = {
                "description": config.description,
                "default": config.default_value,
                "current": self.is_enabled(flag),
                "env_var": config.get_env_var()
            }
        return result
    
    def clear_cache(self) -> None:
        """Clear the internal cache of flag values."""
        self._cache.clear()
        logger.debug("Feature flag cache cleared")


# Global instance
_manager: Optional[FeatureFlagManager] = None


def get_feature_flag_manager() -> FeatureFlagManager:
    """Get the global feature flag manager instance."""
    global _manager
    if _manager is None:
        _manager = FeatureFlagManager()
    return _manager


def is_enabled(flag: FeatureFlag) -> bool:
    """
    Check if a feature flag is enabled.
    
    Args:
        flag: The feature flag to check
        
    Returns:
        True if the flag is enabled, False otherwise
    """
    return get_feature_flag_manager().is_enabled(flag)


def set_flag(flag: FeatureFlag, value: bool) -> None:
    """
    Set a feature flag value programmatically.
    
    Args:
        flag: The feature flag to set
        value: The value to set
    """
    get_feature_flag_manager().set_flag(flag, value)


def get_all_flags() -> Dict[str, Dict[str, Any]]:
    """
    Get all feature flags and their current values.
    
    Returns:
        Dictionary mapping flag names to their configuration and current value
    """
    return get_feature_flag_manager().get_all_flags()


@lru_cache(maxsize=None)
def requires_flag(flag: FeatureFlag):
    """
    Decorator to conditionally execute a function based on a feature flag.
    
    Args:
        flag: The feature flag that must be enabled
        
    Example:
        @requires_flag(FeatureFlag.ENABLE_SPEAKER_IDENTIFICATION)
        def speaker_extraction():
            # This will only run if the flag is enabled
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if is_enabled(flag):
                return func(*args, **kwargs)
            else:
                logger.debug(f"Skipping {func.__name__} - feature flag {flag.value} is disabled")
                return None
        return wrapper
    return decorator