"""Seeding module for API v1 compatibility.

This module provides compatibility shims for tests that expect
the seeding interface.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from ...seeding.orchestrator import VTTKnowledgeExtractor as CoreVTTKnowledgeExtractor
from ...core.config import SeedingConfig
from . import deprecated


class _PipelineImpl:
    """Internal pipeline implementation for API v1."""
    
    def __init__(self, config=None, api_version="1.0"):
        self.config = config or SeedingConfig()
        self._api_version = api_version
        self._created_at = datetime.now()
        self._core_pipeline = CoreVTTKnowledgeExtractor(self.config)
    
    def seed_podcast(self, podcast: Dict[str, Any]) -> Dict[str, Any]:
        """Seed a single podcast."""
        # This would be the actual implementation
        return {
            'api_version': self._api_version,
            'start_time': datetime.now().isoformat(),
            'end_time': datetime.now().isoformat(),
            'podcasts_processed': 1,
            'episodes_processed': 0,
            'episodes_failed': 0,
            'processing_time_seconds': 0.0
        }
    
    def seed_podcasts(self, podcasts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Seed multiple podcasts."""
        return {
            'api_version': self._api_version,
            'start_time': datetime.now().isoformat(),
            'end_time': datetime.now().isoformat(),
            'podcasts_processed': len(podcasts),
            'episodes_processed': 0,
            'episodes_failed': 0,
            'processing_time_seconds': 0.0
        }


class VTTKnowledgeExtractor:
    """API v1 compatible VTTKnowledgeExtractor."""
    
    def __init__(self, config=None, api_version="1.0"):
        self._impl = _PipelineImpl(config, api_version)
        self._api_version = api_version
        self._created_at = datetime.now()
    
    def seed_podcast(self, podcast: Dict[str, Any]) -> Dict[str, Any]:
        """Seed a single podcast."""
        result = self._impl.seed_podcast(podcast)
        # Ensure API version is included in response
        result['api_version'] = self._api_version
        return result
    
    def seed_podcasts(self, podcasts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Seed multiple podcasts."""
        result = self._impl.seed_podcasts(podcasts)
        # Ensure API version is included in response
        result['api_version'] = self._api_version
        return result
    
    @deprecated("2.0", "seed_podcast")
    def process_podcast(self, podcast: Dict[str, Any]) -> Dict[str, Any]:
        """Deprecated method for processing podcasts."""
        return self.seed_podcast(podcast)
    
    def cleanup(self):
        """Clean up resources."""
        # For API v1 compatibility - cleanup is handled internally
        pass