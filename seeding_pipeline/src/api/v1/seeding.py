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
        from pathlib import Path
        from ...seeding.transcript_ingestion import VTTFile
        import hashlib
        import os
        
        start_time = datetime.now()
        
        try:
            # Convert podcast data to VTTFile objects
            vtt_files = []
            if 'vtt_files' in podcast:
                for vtt_data in podcast['vtt_files']:
                    vtt_path = Path(vtt_data['path'])
                    if not vtt_path.exists():
                        continue
                        
                    # Compute file hash
                    file_hash = hashlib.sha256()
                    with open(vtt_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            file_hash.update(chunk)
                    
                    vtt_file = VTTFile(
                        path=vtt_path,
                        podcast_name=podcast.get('name', 'Unknown Podcast'),
                        episode_title=vtt_data.get('title', 'Unknown Episode'),
                        file_hash=file_hash.hexdigest(),
                        size_bytes=os.path.getsize(vtt_path),
                        created_at=datetime.now()
                    )
                    vtt_files.append(vtt_file)
            
            if not vtt_files:
                # No VTT files to process
                return {
                    'api_version': self._api_version,
                    'start_time': start_time.isoformat(),
                    'end_time': datetime.now().isoformat(),
                    'podcasts_processed': 1,
                    'episodes_processed': 0,
                    'episodes_failed': 0,
                    'processing_time_seconds': 0.0
                }
            
            # Process the VTT files using the core pipeline
            result = self._core_pipeline.process_vtt_files(vtt_files)
            
            # Convert the result to expected format
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            return {
                'api_version': self._api_version,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'podcasts_processed': 1,
                'episodes_processed': result.get('files_processed', 0),
                'episodes_failed': result.get('files_failed', 0),
                'processing_time_seconds': processing_time
            }
            
        except Exception as e:
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            return {
                'api_version': self._api_version,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'podcasts_processed': 1,
                'episodes_processed': 0,
                'episodes_failed': len(podcast.get('vtt_files', [])),
                'processing_time_seconds': processing_time,
                'error': str(e)
            }
    
    def seed_podcasts(self, podcasts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Seed multiple podcasts."""
        start_time = datetime.now()
        total_episodes_processed = 0
        total_episodes_failed = 0
        
        for podcast in podcasts:
            try:
                result = self.seed_podcast(podcast)
                total_episodes_processed += result.get('episodes_processed', 0)
                total_episodes_failed += result.get('episodes_failed', 0)
            except Exception:
                # Count all episodes in this podcast as failed
                total_episodes_failed += len(podcast.get('vtt_files', []))
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        return {
            'api_version': self._api_version,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'podcasts_processed': len(podcasts),
            'episodes_processed': total_episodes_processed,
            'episodes_failed': total_episodes_failed,
            'processing_time_seconds': processing_time
        }


class VTTKnowledgeExtractor:
    """API v1 compatible VTTKnowledgeExtractor."""
    
    def __init__(self, config=None, api_version="1.0"):
        self._impl = _PipelineImpl(config, api_version)
        self._api_version = api_version
        self._created_at = datetime.now()
    
    def seed_podcast(self, podcast: Dict[str, Any], max_episodes: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """Seed a single podcast."""
        # For now, ignore max_episodes as this is handled in RSS processing
        # VTT processing uses all provided files
        result = self._impl.seed_podcast(podcast)
        # Ensure API version is included in response
        result['api_version'] = self._api_version
        return result
    
    def seed_podcasts(self, podcasts: List[Dict[str, Any]], max_episodes_per_podcast: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """Seed multiple podcasts."""
        # For now, ignore max_episodes_per_podcast as this is handled in RSS processing
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