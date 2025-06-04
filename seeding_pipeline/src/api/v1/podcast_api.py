"""API v1 Podcast Functions.

This module provides the API functions expected by the E2E tests,
wrapping the actual VTTKnowledgeExtractor functionality.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import hashlib
import logging

from .seeding import VTTKnowledgeExtractor
from ...seeding.transcript_ingestion import VTTFile
from ...core.config import SeedingConfig

logger = logging.getLogger(__name__)


def _compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file."""
    if not file_path.exists():
        return ''
    
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


# Alias for backward compatibility
PodcastKnowledgePipeline = VTTKnowledgeExtractor


def seed_podcast(
    podcast: Dict[str, Any],
    max_episodes: Optional[int] = None,
    config: Optional[SeedingConfig] = None,
    **kwargs
) -> Dict[str, Any]:
    """Process a single podcast's VTT files.
    
    Args:
        podcast: Dict with podcast metadata including 'name' and VTT file info
        max_episodes: Maximum number of episodes to process
        config: Pipeline configuration
        **kwargs: Additional arguments for forward compatibility
        
    Returns:
        Summary dict with processing results
    """
    # Initialize pipeline
    pipeline = VTTKnowledgeExtractor(config)
    
    try:
        # Call the pipeline's seed_podcast method
        result = pipeline.seed_podcast(podcast)
        return result
    finally:
        # Ensure cleanup is called
        pipeline.cleanup()


def seed_podcasts(
    podcasts: List[Dict[str, Any]],
    max_episodes_per_podcast: Optional[int] = None,
    config: Optional[SeedingConfig] = None,
    **kwargs
) -> Dict[str, Any]:
    """Process multiple podcasts' VTT files.
    
    Args:
        podcasts: List of podcast dicts with metadata
        max_episodes_per_podcast: Max episodes per podcast
        config: Pipeline configuration
        **kwargs: Additional arguments for forward compatibility
        
    Returns:
        Summary dict with aggregate processing results
    """
    # Initialize pipeline
    pipeline = VTTKnowledgeExtractor(config)
    
    try:
        # Call the pipeline's seed_podcasts method
        result = pipeline.seed_podcasts(podcasts)
        return result
    finally:
        # Ensure cleanup is called
        pipeline.cleanup()