"""API v1 for VTT Knowledge Graph Pipeline.

This is the first stable API version. Future versions will maintain
backward compatibility or provide clear migration paths.
"""

# API version information
API_VERSION = "1.0.0"
API_VERSION_INFO = (1, 0, 0)

# Version functions
def get_api_version() -> str:
    """Get the current API version."""
    return API_VERSION

def check_api_compatibility(required_version: str) -> bool:
    """Check if the API is compatible with a required version."""
    # Parse version parts
    required_parts = required_version.split('.')
    required_major = int(required_parts[0])
    current_major = API_VERSION_INFO[0]
    
    # Only compatible if same major version
    return current_major == required_major

def deprecated(version=None, replacement=None):
    """Decorator to mark functions as deprecated.
    
    Args:
        version: Version when the function will be removed
        replacement: Name of the replacement function
    """
    def decorator(func):
        import functools
        import warnings
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            message = f"{func.__name__} is deprecated"
            if version:
                message += f" and will be removed in version {version}"
            if replacement:
                message += f". Use {replacement} instead"
            warnings.warn(
                message,
                DeprecationWarning,
                stacklevel=2
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator

def api_version_check(required_version: str):
    """Decorator to check API version compatibility."""
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not check_api_compatibility(required_version):
                raise RuntimeError(f"API version {required_version} required, but {API_VERSION} is installed")
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name in ['seed_podcast', 'seed_podcasts', 'PodcastKnowledgePipeline', 'VTTKnowledgeExtractor']:
        from .podcast_api import seed_podcast, seed_podcasts, PodcastKnowledgePipeline
        # VTTKnowledgeExtractor is an alias for PodcastKnowledgePipeline
        if name == 'VTTKnowledgeExtractor':
            VTTKnowledgeExtractor = PodcastKnowledgePipeline
            globals()[name] = VTTKnowledgeExtractor
            return VTTKnowledgeExtractor
        globals()[name] = locals()[name]
        return locals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")

__all__ = [
    'API_VERSION',
    'API_VERSION_INFO',
    'seed_podcast',
    'seed_podcasts',
    'PodcastKnowledgePipeline',
    'VTTKnowledgeExtractor',  # Alias for PodcastKnowledgePipeline
    'get_api_version',
    'check_api_compatibility',
    'deprecated',
    'api_version_check'
]