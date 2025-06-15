"""API v1 for VTT Knowledge Graph Pipeline."""

# API version information
API_VERSION = "1.0.0"
API_VERSION_INFO = (1, 0, 0)

# Version functions
def get_api_version() -> str:
    """Get the current API version."""
    return API_VERSION

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == 'VTTKnowledgeExtractor':
        # Import directly from core orchestrator
        from ...seeding.orchestrator import VTTKnowledgeExtractor
        globals()[name] = VTTKnowledgeExtractor
        return VTTKnowledgeExtractor
    raise AttributeError(f"module {__name__} has no attribute {name}")

__all__ = [
    'API_VERSION',
    'API_VERSION_INFO',
    'VTTKnowledgeExtractor',
    'get_api_version'
]