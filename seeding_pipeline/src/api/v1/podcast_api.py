"""API v1 Podcast Functions.

This module provides the API functions expected by the E2E tests,
wrapping the actual VTTKnowledgeExtractor functionality.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import hashlib
import logging

from ...seeding.orchestrator import VTTKnowledgeExtractor
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
    config: Optional[SeedingConfig] = None
) -> Dict[str, Any]:
    """Process a single podcast's VTT files.
    
    Args:
        podcast: Dict with podcast metadata including 'name' and VTT file info
        max_episodes: Maximum number of episodes to process
        config: Pipeline configuration
        
    Returns:
        Summary dict with processing results
    """
    # Initialize pipeline
    pipeline = VTTKnowledgeExtractor(config)
    
    # Create VTTFile objects from podcast data
    vtt_files = []
    
    # Handle different input formats
    if 'vtt_files' in podcast:
        # Direct VTT files provided
        for vtt_data in podcast['vtt_files'][:max_episodes]:
            if isinstance(vtt_data, VTTFile):
                vtt_files.append(vtt_data)
            elif isinstance(vtt_data, dict):
                file_path = Path(vtt_data.get('path', ''))
                file_stat = file_path.stat() if file_path.exists() else None
                vtt_file = VTTFile(
                    path=file_path,
                    podcast_name=podcast.get('name', 'Unknown'),
                    episode_title=vtt_data.get('title', 'Unknown Episode'),
                    file_hash=_compute_file_hash(file_path) if file_path.exists() else '',
                    size_bytes=file_stat.st_size if file_stat else 0,
                    created_at=datetime.fromtimestamp(file_stat.st_ctime) if file_stat else datetime.now(),
                    metadata=vtt_data
                )
                vtt_files.append(vtt_file)
            elif isinstance(vtt_data, (str, Path)):
                file_path = Path(vtt_data)
                file_stat = file_path.stat() if file_path.exists() else None
                vtt_file = VTTFile(
                    path=file_path,
                    podcast_name=podcast.get('name', 'Unknown'),
                    episode_title=f"Episode from {file_path.name}",
                    file_hash=_compute_file_hash(file_path) if file_path.exists() else '',
                    size_bytes=file_stat.st_size if file_stat else 0,
                    created_at=datetime.fromtimestamp(file_stat.st_ctime) if file_stat else datetime.now()
                )
                vtt_files.append(vtt_file)
    elif 'vtt_directory' in podcast:
        # Process directory of VTT files
        result = pipeline.process_vtt_directory(
            Path(podcast['vtt_directory']),
            podcast_name=podcast.get('name', 'Unknown'),
            max_files=max_episodes
        )
        return {
            'podcasts_processed': 1,
            'episodes_processed': result.get('files_processed', 0),
            'episodes_failed': result.get('files_failed', 0),
            'total_insights': result.get('total_insights', 0),
            'total_entities': result.get('total_entities', 0),
            'errors': result.get('errors', [])
        }
    
    # Process the VTT files
    if vtt_files:
        result = pipeline.process_vtt_files(vtt_files)
        return {
            'podcasts_processed': 1,
            'episodes_processed': result.get('files_processed', 0),
            'episodes_failed': result.get('files_failed', 0),
            'total_insights': result.get('total_insights', 0),
            'total_entities': result.get('total_entities', 0),
            'errors': result.get('errors', [])
        }
    
    return {
        'podcasts_processed': 0,
        'episodes_processed': 0,
        'episodes_failed': 0,
        'total_insights': 0,
        'total_entities': 0,
        'errors': ['No VTT files found to process']
    }


def seed_podcasts(
    podcasts: List[Dict[str, Any]],
    max_episodes_per_podcast: Optional[int] = None,
    config: Optional[SeedingConfig] = None
) -> Dict[str, Any]:
    """Process multiple podcasts' VTT files.
    
    Args:
        podcasts: List of podcast dicts with metadata
        max_episodes_per_podcast: Max episodes per podcast
        config: Pipeline configuration
        
    Returns:
        Summary dict with aggregate processing results
    """
    total_result = {
        'podcasts_processed': 0,
        'episodes_processed': 0,
        'episodes_failed': 0,
        'total_insights': 0,
        'total_entities': 0,
        'errors': []
    }
    
    for podcast in podcasts:
        try:
            result = seed_podcast(
                podcast,
                max_episodes=max_episodes_per_podcast,
                config=config
            )
            
            # Aggregate results
            total_result['podcasts_processed'] += result.get('podcasts_processed', 0)
            total_result['episodes_processed'] += result.get('episodes_processed', 0)
            total_result['episodes_failed'] += result.get('episodes_failed', 0)
            total_result['total_insights'] += result.get('total_insights', 0)
            total_result['total_entities'] += result.get('total_entities', 0)
            total_result['errors'].extend(result.get('errors', []))
            
        except Exception as e:
            logger.error(f"Failed to process podcast {podcast.get('name', 'Unknown')}: {e}")
            total_result['errors'].append(f"Podcast {podcast.get('name', 'Unknown')}: {str(e)}")
    
    return total_result