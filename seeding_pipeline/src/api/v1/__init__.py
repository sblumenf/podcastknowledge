"""API v1 for Podcast Knowledge Graph Pipeline.

This is the first stable API version. Future versions will maintain
backward compatibility or provide clear migration paths.
"""

from .seeding import (
    seed_podcast,
    seed_podcasts,
    PodcastKnowledgePipeline,
    get_api_version,
    check_api_compatibility,
    deprecated,
    api_version_check,
)

__all__ = [
    'seed_podcast',
    'seed_podcasts',
    'PodcastKnowledgePipeline',
    'get_api_version',
    'check_api_compatibility',
    'deprecated',
    'api_version_check',
]

# API version information
API_VERSION = "1.1.0"
API_VERSION_INFO = (1, 1, 0)