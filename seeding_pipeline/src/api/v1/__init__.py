"""API v1 for VTT Knowledge Graph Pipeline.

This is the first stable API version. Future versions will maintain
backward compatibility or provide clear migration paths.
"""

# API version information
API_VERSION = "1.1.0"
API_VERSION_INFO = (1, 1, 0)

# Temporary: Export basic functionality until API is properly refactored
from ...seeding import VTTKnowledgeExtractor

__all__ = [
    'VTTKnowledgeExtractor',
    'API_VERSION',
    'API_VERSION_INFO'
]