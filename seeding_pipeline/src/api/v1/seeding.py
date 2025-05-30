"""API v1 seeding functionality with versioning and deprecation support."""

import functools
import warnings
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

from ...core.config import Config
from ...seeding import PodcastKnowledgePipeline as _PipelineImpl
from ...__version__ import __api_version__


# Deprecation helpers
def deprecated(version: str, alternative: Optional[str] = None) -> Callable:
    """Mark a function as deprecated.
    
    Args:
        version: Version when this will be removed
        alternative: Alternative function/method to use
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            message = f"{func.__name__} is deprecated and will be removed in v{version}."
            if alternative:
                message += f" Use {alternative} instead."
            warnings.warn(message, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def api_version_check(min_version: str, max_version: Optional[str] = None) -> Callable:
    """Check API version compatibility."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current = tuple(int(x) for x in __api_version__.split('.'))
            min_ver = tuple(int(x) for x in min_version.split('.'))
            
            if current < min_ver:
                raise RuntimeError(
                    f"API version {__api_version__} is too old. "
                    f"Minimum required: {min_version}"
                )
            
            if max_version:
                max_ver = tuple(int(x) for x in max_version.split('.'))
                if current > max_ver:
                    warnings.warn(
                        f"API version {__api_version__} is newer than tested version {max_version}. "
                        "Some features may not work as expected.",
                        FutureWarning
                    )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


class PodcastKnowledgePipeline(_PipelineImpl):
    """Versioned wrapper for PodcastKnowledgePipeline with API stability guarantees.
    
    This class provides:
    - Stable API interface
    - Version checking
    - Deprecation warnings
    - Backward compatibility layer
    """
    
    def __init__(self, config: Optional[Config] = None, api_version: str = "1.0"):
        """Initialize pipeline with version checking.
        
        Args:
            config: Pipeline configuration
            api_version: API version to use (for future compatibility)
        """
        super().__init__(config)
        self._api_version = api_version
        self._created_at = datetime.now()
    
    @api_version_check("1.0")
    def seed_podcast(self, 
                    podcast_config: Dict[str, Any],
                    max_episodes: int = 1,
                    use_large_context: bool = True,
                    extraction_mode: str = "fixed",
                    **kwargs: Any) -> Dict[str, Any]:
        """Seed knowledge graph with a single podcast (v1 API).
        
        Args:
            podcast_config: Podcast configuration
            max_episodes: Maximum episodes to process
            use_large_context: Whether to use large context models
            extraction_mode: "fixed" or "schemaless" (default: "fixed")
            **kwargs: Additional arguments for forward compatibility
            
        Returns:
            Processing summary with v1 schema guarantee
        """
        # Apply extraction mode to config
        if extraction_mode == "schemaless":
            self.config.use_schemaless_extraction = True
        else:
            self.config.use_schemaless_extraction = False
            
        # Handle any v1-specific transformations
        result = super().seed_podcast(
            podcast_config=podcast_config,
            max_episodes=max_episodes,
            use_large_context=use_large_context
        )
        
        # Ensure v1 response schema
        return self._ensure_v1_response(result)
    
    @api_version_check("1.0")
    def seed_podcasts(self,
                     podcast_configs: Union[Dict[str, Any], List[Dict[str, Any]]],
                     max_episodes_each: int = 10,
                     use_large_context: bool = True,
                     extraction_mode: str = "fixed",
                     **kwargs: Any) -> Dict[str, Any]:
        """Seed knowledge graph with multiple podcasts (v1 API).
        
        Args:
            podcast_configs: List of podcast configurations
            max_episodes_each: Episodes to process per podcast
            use_large_context: Whether to use large context models
            extraction_mode: "fixed" or "schemaless" (default: "fixed")
            **kwargs: Additional arguments for forward compatibility
            
        Returns:
            Summary dict with v1 schema guarantee
        """
        # Apply extraction mode to config
        if extraction_mode == "schemaless":
            self.config.use_schemaless_extraction = True
        else:
            self.config.use_schemaless_extraction = False
            
        # Handle any v1-specific transformations
        result = super().seed_podcasts(
            podcast_configs=podcast_configs,
            max_episodes_each=max_episodes_each,
            use_large_context=use_large_context
        )
        
        # Ensure v1 response schema
        return self._ensure_v1_response(result)
    
    def _ensure_v1_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure response conforms to v1 schema.
        
        This provides backward compatibility if internal schema changes.
        """
        # Calculate processing time if not provided
        processing_time = result.get('processing_time_seconds', 0.0)
        if processing_time == 0.0 and result.get('start_time') and result.get('end_time'):
            from datetime import datetime
            start = datetime.fromisoformat(result['start_time'])
            end = datetime.fromisoformat(result['end_time'])
            processing_time = (end - start).total_seconds()
        
        # v1 guaranteed fields
        v1_result = {
            'start_time': result.get('start_time'),
            'end_time': result.get('end_time'),
            'podcasts_processed': result.get('podcasts_processed', 0),
            'episodes_processed': result.get('episodes_processed', 0),
            'episodes_failed': result.get('episodes_failed', 0),
            'processing_time_seconds': processing_time,
            'api_version': '1.0',
            'extraction_mode': result.get('extraction_mode', 'fixed'),
        }
        
        # Include schemaless-specific fields if present
        if result.get('extraction_mode') == 'schemaless':
            v1_result['total_entities'] = result.get('total_entities', 0)
            v1_result['total_relationships'] = result.get('total_relationships', 0)
            v1_result['discovered_types'] = result.get('discovered_types', [])
        
        # Include any additional fields that exist
        for key, value in result.items():
            if key not in v1_result:
                v1_result[key] = value
        
        return v1_result
    
    @api_version_check("1.0")
    def get_schema_evolution(self, 
                           checkpoint_dir: Optional[str] = None,
                           **kwargs: Any) -> Dict[str, Any]:
        """Get schema evolution statistics from schemaless extraction.
        
        Args:
            checkpoint_dir: Directory containing checkpoint files
            **kwargs: Additional arguments for forward compatibility
            
        Returns:
            Schema evolution statistics
        """
        from ...seeding.checkpoint import ProgressCheckpoint
        
        # Use checkpoint dir from config if not provided
        if checkpoint_dir is None:
            checkpoint_dir = getattr(self.config, 'checkpoint_dir', 'checkpoints')
        
        # Initialize checkpoint reader
        checkpoint = ProgressCheckpoint(
            checkpoint_dir=checkpoint_dir,
            extraction_mode='schemaless'
        )
        
        # Get schema statistics
        stats = checkpoint.get_schema_statistics()
        
        # Ensure v1 response format
        return {
            'api_version': '1.0',
            'checkpoint_dir': checkpoint_dir,
            'schema_stats': stats,
            'timestamp': datetime.now().isoformat()
        }
    
    # Deprecated methods for demonstration (not actually deprecated yet)
    @deprecated("2.0", "seed_podcast")
    def process_podcast(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Legacy method name - use seed_podcast instead."""
        return self.seed_podcast(*args, **kwargs)


# Module-level convenience functions with version checking
@api_version_check("1.0")
def seed_podcast(podcast_config: Dict[str, Any],
                max_episodes: int = 1,
                use_large_context: bool = True,
                extraction_mode: str = "fixed",
                config: Optional[Config] = None,
                **kwargs: Any) -> Dict[str, Any]:
    """Seed knowledge graph with a single podcast (v1 API).
    
    This is a convenience function that handles pipeline lifecycle.
    
    Args:
        podcast_config: Podcast configuration with RSS URL
        max_episodes: Maximum episodes to process
        use_large_context: Whether to use large context models
        extraction_mode: "fixed" or "schemaless" (default: "fixed")
        config: Optional configuration object
        **kwargs: Additional arguments for forward compatibility
    
    Returns:
        Processing summary dict with v1 schema
    """
    if config is None:
        config = Config()
    
    pipeline = PodcastKnowledgePipeline(config)
    try:
        return pipeline.seed_podcast(
            podcast_config=podcast_config,
            max_episodes=max_episodes,
            use_large_context=use_large_context,
            extraction_mode=extraction_mode,
            **kwargs
        )
    finally:
        pipeline.cleanup()


@api_version_check("1.0")
def seed_podcasts(podcast_configs: Union[Dict[str, Any], List[Dict[str, Any]]],
                 max_episodes_each: int = 10,
                 use_large_context: bool = True,
                 extraction_mode: str = "fixed",
                 config: Optional[Config] = None,
                 **kwargs: Any) -> Dict[str, Any]:
    """Seed knowledge graph with multiple podcasts (v1 API).
    
    This is a convenience function that handles pipeline lifecycle.
    
    Args:
        podcast_configs: List of podcast configurations
        max_episodes_each: Episodes to process per podcast
        use_large_context: Whether to use large context models
        extraction_mode: "fixed" or "schemaless" (default: "fixed")
        config: Optional configuration object
        **kwargs: Additional arguments for forward compatibility
    
    Returns:
        Summary dict with v1 schema
    """
    if config is None:
        config = Config()
    
    pipeline = PodcastKnowledgePipeline(config)
    try:
        return pipeline.seed_podcasts(
            podcast_configs=podcast_configs,
            max_episodes_each=max_episodes_each,
            use_large_context=use_large_context,
            extraction_mode=extraction_mode,
            **kwargs
        )
    finally:
        pipeline.cleanup()


def get_api_version() -> str:
    """Get the current API version."""
    return "1.0.0"


def check_api_compatibility(required_version: str) -> bool:
    """Check if current API version is compatible with required version.
    
    Args:
        required_version: Required API version (e.g., "1.0")
        
    Returns:
        True if compatible, False otherwise
    """
    current = tuple(int(x) for x in get_api_version().split('.'))
    required = tuple(int(x) for x in required_version.split('.'))
    
    # Major version must match, minor/patch can be higher
    return current[0] == required[0] and current >= required


# Changelog tracking
API_CHANGELOG = {
    "1.0.0": {
        "date": "2024-01-01",
        "changes": [
            "Initial stable API release",
            "seed_podcast and seed_podcasts functions",
            "PodcastKnowledgePipeline class",
            "Version checking and deprecation support",
        ]
    }
}