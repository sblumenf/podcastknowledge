"""Transcript ingestion module for processing VTT files."""

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Set, Tuple
import hashlib
import json
import logging
import os
import shutil

from src.core.config import PipelineConfig
from src.core.exceptions import ValidationError, PipelineError
from src.core.interfaces import TranscriptSegment
from src.core.models import Podcast, Episode
from src.utils.log_utils import get_logger
from src.vtt import VTTParser
try:
    from src.utils.youtube_search import YouTubeSearcher
except ImportError:
    YouTubeSearcher = None
    
logger = get_logger(__name__)


@dataclass
class VTTFile:
    """Represents a VTT file to be processed."""
    path: Path
    podcast_name: str
    episode_title: str
    file_hash: str
    size_bytes: int
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['path'] = str(data['path'])
        data['created_at'] = data['created_at'].isoformat()
        return data


class TranscriptIngestion:
    """Main entry point for VTT transcript ingestion."""
    
    def __init__(self, config: PipelineConfig):
        """Initialize transcript ingestion.
        
        Args:
            config: Pipeline configuration
        """
        self.config = config
        self.vtt_parser = VTTParser()
        self._processed_files: Set[str] = set()
        
        # Initialize YouTube searcher if enabled
        self.youtube_searcher = None
        if getattr(config, 'youtube_search_enabled', False):
            if YouTubeSearcher:
                try:
                    api_key = getattr(config, 'youtube_api_key', None) or os.environ.get('YOUTUBE_API_KEY')
                    if api_key:
                        self.youtube_searcher = YouTubeSearcher(api_key)
                        logger.info("YouTube search enabled for missing URLs")
                    else:
                        logger.warning("YouTube search enabled but no API key found")
                except Exception as e:
                    logger.warning(f"Failed to initialize YouTube searcher: {e}")
            else:
                logger.warning("YouTube search enabled but youtube_search module not available")
    
    def scan_directory(self, 
                      directory: Path, 
                      pattern: str = "*.vtt",
                      recursive: bool = True) -> List[VTTFile]:
        """Scan directory for VTT files.
        
        Args:
            directory: Directory to scan
            pattern: File pattern to match (default: *.vtt)
            recursive: Whether to scan subdirectories
            
        Returns:
            List of VTTFile objects found
        """
        directory = Path(directory)
        if not directory.exists():
            raise ValidationError(f"Directory not found: {directory}")
        
        vtt_files = []
        
        # Use rglob for recursive, glob for non-recursive
        glob_func = directory.rglob if recursive else directory.glob
        
        for file_path in glob_func(pattern):
            if file_path.is_file():
                vtt_file = self._create_vtt_file(file_path)
                if vtt_file:
                    vtt_files.append(vtt_file)
        
        logger.info(f"Found {len(vtt_files)} VTT files in {directory}")
        return vtt_files
    
    def _create_vtt_file(self, file_path: Path) -> Optional[VTTFile]:
        """Create VTTFile object from file path.
        
        Args:
            file_path: Path to VTT file
            
        Returns:
            VTTFile object or None if invalid
        """
        try:
            # Get file stats
            stat = file_path.stat()
            
            # Calculate file hash
            file_hash = self._calculate_file_hash(file_path)
            
            # Infer podcast and episode from path
            podcast_name, episode_title = self._infer_metadata_from_path(file_path)
            
            # Check for metadata file
            metadata = self._load_metadata_file(file_path.parent)
            
            # Override with metadata if available
            if metadata:
                podcast_name = metadata.get('podcast', {}).get('name', podcast_name)
                if 'episode' in metadata:
                    episode_title = metadata['episode'].get('title', episode_title)
            
            return VTTFile(
                path=file_path,
                podcast_name=podcast_name,
                episode_title=episode_title,
                file_hash=file_hash,
                size_bytes=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_mtime),
                metadata=metadata
            )
            
        except Exception as e:
            logger.warning(f"Failed to process file {file_path}: {e}")
            return None
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hex digest of file hash
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _infer_metadata_from_path(self, file_path: Path) -> Tuple[str, str]:
        """Infer podcast and episode names from file path.
        
        Args:
            file_path: Path to VTT file
            
        Returns:
            Tuple of (podcast_name, episode_title)
        """
        # Use parent directory as podcast name
        podcast_name = file_path.parent.name
        
        # Use filename without extension as episode title
        episode_title = file_path.stem
        
        # Clean up common patterns
        episode_title = episode_title.replace('_', ' ').replace('-', ' ')
        
        return podcast_name, episode_title
    
    def _load_metadata_file(self, directory: Path) -> Optional[Dict[str, Any]]:
        """Load metadata.json from directory if it exists.
        
        Args:
            directory: Directory to check
            
        Returns:
            Metadata dictionary or None
        """
        metadata_path = directory / "metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load metadata from {metadata_path}: {e}")
        return None
    
    def process_vtt_file(self, 
                        vtt_file: VTTFile,
                        checkpoint_manager: Optional[Any] = None) -> Dict[str, Any]:
        """Process a single VTT file.
        
        Args:
            vtt_file: VTT file to process
            checkpoint_manager: Optional checkpoint manager
            
        Returns:
            Processing result dictionary
        """
        logger.info(f"Processing VTT file: {vtt_file.path}")
        
        # Check if already processed
        if vtt_file.file_hash in self._processed_files:
            logger.info(f"File already processed: {vtt_file.path}")
            return {'status': 'skipped', 'reason': 'already_processed'}
        
        try:
            # Parse VTT file with metadata extraction
            try:
                parse_result = self.vtt_parser.parse_file_with_metadata(vtt_file.path)
                segments = parse_result['segments']
                vtt_metadata = parse_result['metadata']
            except AttributeError:
                # Fallback for older VTT parser without metadata extraction
                logger.warning("VTT parser doesn't support metadata extraction, using legacy parsing")
                segments = self.vtt_parser.parse_file(vtt_file.path)
                vtt_metadata = {}
            
            # Optionally merge short segments
            if getattr(self.config, 'merge_short_segments', True):
                min_duration = getattr(self.config, 'min_segment_duration', 2.0)
                segments = self.vtt_parser.merge_short_segments(segments, min_duration)
            
            # Create episode data with metadata
            episode_data = self._create_episode_data(vtt_file, segments, vtt_metadata)
            
            # Mark as processed
            self._processed_files.add(vtt_file.file_hash)
            
            return {
                'status': 'success',
                'file': vtt_file.to_dict(),
                'episode': episode_data,
                'segments': segments,
                'segment_count': len(segments),
                'metadata': vtt_metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to process {vtt_file.path}: {e}")
            return {
                'status': 'error',
                'file': vtt_file.to_dict(),
                'error': str(e)
            }
    
    def _create_episode_data(self, 
                           vtt_file: VTTFile, 
                           segments: List[TranscriptSegment],
                           vtt_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create episode data from VTT file, segments, and metadata.
        
        Args:
            vtt_file: VTT file being processed
            segments: Parsed transcript segments
            vtt_metadata: Metadata extracted from VTT file
            
        Returns:
            Episode data dictionary
        """
        # Calculate duration from segments
        if segments:
            duration = segments[-1].end_time
        else:
            duration = 0.0
        
        # Extract speakers
        speakers = list(set(seg.speaker for seg in segments if seg.speaker))
        
        # Extract podcast ID from metadata
        podcast_id = vtt_metadata.get('podcast_id', 'unknown_podcast')
        
        # Use metadata to enhance episode data
        episode_data = {
            'id': vtt_file.file_hash[:12],  # Use first 12 chars of hash as ID
            'title': vtt_metadata.get('episode', vtt_file.episode_title),
            'podcast_name': vtt_metadata.get('podcast', vtt_file.podcast_name),
            'podcast_id': podcast_id,  # Add podcast ID for multi-podcast support
            'description': vtt_metadata.get('description', ''),
            'published_date': vtt_metadata.get('date', ''),
            'youtube_url': vtt_metadata.get('youtube_url'),
            'original_url': vtt_metadata.get('original_url'),
            'duration_seconds': vtt_metadata.get('duration', duration),
            'speaker_count': len(speakers),
            'speakers': speakers,
            'segment_count': len(segments),
            'file_path': str(vtt_file.path),
            'processed_at': datetime.utcnow().isoformat(),
            'transcript_metadata': vtt_metadata  # Store all metadata
        }
        
        # Log if YouTube URL was found
        if episode_data['youtube_url']:
            logger.info(f"YouTube URL found for episode: {episode_data['youtube_url']}")
        else:
            logger.info("No YouTube URL found in VTT metadata")
            
            # Try to find YouTube URL using search if enabled
            if self.youtube_searcher:
                logger.info(f"Searching for YouTube URL for episode: {episode_data['title']}")
                try:
                    youtube_url = self.youtube_searcher.search_youtube_url(
                        podcast_name=episode_data['podcast_name'],
                        episode_title=episode_data['title'],
                        published_date=episode_data.get('published_date')
                    )
                    
                    if youtube_url:
                        episode_data['youtube_url'] = youtube_url
                        logger.info(f"Found YouTube URL via search: {youtube_url}")
                    else:
                        logger.info("YouTube search did not find a suitable match")
                        
                except Exception as e:
                    logger.warning(f"YouTube search failed: {e}")
            
        return episode_data
    
    def process_directory(self,
                         directory: Path,
                         pattern: str = "*.vtt",
                         recursive: bool = True,
                         max_files: Optional[int] = None,
                         checkpoint_manager: Optional[Any] = None) -> Dict[str, Any]:
        """Process all VTT files in a directory.
        
        Args:
            directory: Directory containing VTT files
            pattern: File pattern to match
            recursive: Whether to scan subdirectories
            max_files: Maximum number of files to process
            checkpoint_manager: Optional checkpoint manager
            
        Returns:
            Processing summary
        """
        # Scan for VTT files
        vtt_files = self.scan_directory(directory, pattern, recursive)
        
        if max_files:
            vtt_files = vtt_files[:max_files]
        
        # Process results
        results = {
            'total_files': len(vtt_files),
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'total_segments': 0,
            'files': []
        }
        
        # Process each file
        for vtt_file in vtt_files:
            result = self.process_vtt_file(vtt_file, checkpoint_manager)
            
            if result['status'] == 'success':
                results['processed'] += 1
                results['total_segments'] += result['segment_count']
            elif result['status'] == 'skipped':
                results['skipped'] += 1
            else:
                results['errors'] += 1
            
            results['files'].append(result)
        
        return results
    
    def group_by_podcast(self, vtt_files: List[VTTFile]) -> Dict[str, List[VTTFile]]:
        """Group VTT files by podcast name.
        
        Args:
            vtt_files: List of VTT files
            
        Returns:
            Dictionary mapping podcast names to file lists
        """
        grouped = {}
        for vtt_file in vtt_files:
            podcast = vtt_file.podcast_name
            if podcast not in grouped:
                grouped[podcast] = []
            grouped[podcast].append(vtt_file)
        
        return grouped
    
    def validate_vtt_file(self, file_path: Path) -> bool:
        """Validate that a file is a valid VTT file.
        
        Args:
            file_path: Path to file to validate
            
        Returns:
            True if valid VTT file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                return first_line.startswith('WEBVTT')
        except Exception:
            return False
    
    def process_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Process a single VTT file by path.
        
        Args:
            file_path: Path to VTT file
            
        Returns:
            Processing result dictionary
        """
        file_path = Path(file_path)
        vtt_file = self._create_vtt_file(file_path)
        if not vtt_file:
            return {
                'status': 'error',
                'error': f'Failed to create VTTFile from {file_path}'
            }
        return self.process_vtt_file(vtt_file)
    
    def _compute_file_hash(self, file_path: Union[str, Path]) -> str:
        """Compute SHA256 hash of file (alias for _calculate_file_hash).
        
        Args:
            file_path: Path to file
            
        Returns:
            Hex digest of file hash
        """
        return self._calculate_file_hash(Path(file_path))


class TranscriptIngestionManager:
    """Manager class that bridges between CLI and TranscriptIngestion.
    
    This provides the interface expected by the CLI while using
    TranscriptIngestion internally.
    """
    
    def __init__(self, pipeline: Any, checkpoint: Optional[Any] = None):
        """Initialize ingestion manager.
        
        Args:
            pipeline: Knowledge pipeline instance
            checkpoint: Optional checkpoint manager
        """
        self.pipeline = pipeline
        self.checkpoint = checkpoint
        self.ingestion = TranscriptIngestion(pipeline.config)
        
        # Initialize podcast directory manager if in multi-podcast mode
        self.podcast_mode = os.getenv('PODCAST_MODE', 'single')
        if self.podcast_mode == 'multi':
            from src.utils.podcast_directory_manager import PodcastDirectoryManager
            self.dir_manager = PodcastDirectoryManager()
        else:
            self.dir_manager = None
    
    def process_vtt_file(self, vtt_file: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a VTT file and return results.
        
        Args:
            vtt_file: Path to VTT file
            metadata: Optional metadata
            
        Returns:
            Dictionary with processing results including:
            - success: bool
            - segments_processed: int (if successful)
            - error: str (if failed)
        """
        try:
            vtt_path = Path(vtt_file)
            
            # Check if file exists in processed directory
            processed_dir = Path(os.getenv('PROCESSED_DIR', 'data/processed'))
            
            # In multi-podcast mode, we need to determine the podcast ID first
            if self.podcast_mode == 'multi' and self.dir_manager:
                # Parse file to get podcast ID
                parse_result = self.ingestion.vtt_parser.parse_file_with_metadata(vtt_path)
                podcast_id = parse_result['metadata'].get('podcast_id', 'unknown_podcast')
                
                # Ensure podcast directory structure exists
                podcast_dirs = self.dir_manager.ensure_podcast_structure(podcast_id)
                
                # Use podcast-specific processed directory
                processed_dir = podcast_dirs['processed']
                
                # Calculate relative path for processed file
                relative_path = vtt_path.name
                processed_file_path = processed_dir / relative_path
            else:
                # Single podcast mode - maintain same directory structure
                relative_path = None
                vtt_input_dir = Path(os.getenv('VTT_INPUT_DIR', 'data/transcripts'))
                if vtt_path.is_relative_to(vtt_input_dir):
                    relative_path = vtt_path.relative_to(vtt_input_dir)
                    processed_file_path = processed_dir / relative_path
                else:
                    # Fallback: just use filename
                    processed_file_path = processed_dir / vtt_path.name
            
            # Check if already processed
            if processed_file_path.exists():
                logger.info(f"File already processed (exists in processed directory): {vtt_path}")
                return {
                    'success': False,
                    'skipped': True,
                    'error': 'File already processed'
                }
            
            # Create VTTFile object
            vtt_file_obj = self.ingestion._create_vtt_file(vtt_path)
            if not vtt_file_obj:
                return {
                    'success': False,
                    'error': 'Failed to create VTTFile object'
                }
            
            # Process the file
            result = self.ingestion.process_vtt_file(vtt_file_obj, self.checkpoint)
            
            # Transform result to expected format
            if result['status'] == 'success':
                # Move file to processed directory
                try:
                    # Create subdirectories if needed
                    processed_file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Move the file
                    shutil.move(str(vtt_path), str(processed_file_path))
                    logger.info(f"Moved processed file to: {processed_file_path}")
                    
                    # Update checkpoint with move status
                    if self.checkpoint:
                        self.checkpoint.mark_vtt_moved_to_processed(str(vtt_path), str(processed_file_path))
                    
                except Exception as e:
                    # Log error but don't fail the processing
                    logger.error(f"Failed to move file to processed directory: {e}")
                    # Don't return error - processing was successful
                
                return {
                    'success': True,
                    'segments_processed': result['segment_count'],
                    'segments': result.get('segments', []),
                    'episode': result.get('episode', {})
                }
            elif result['status'] == 'skipped':
                return {
                    'success': False,
                    'skipped': True,
                    'error': f"Skipped: {result.get('reason', 'Unknown reason')}"
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown error')
                }
                
        except Exception as e:
            logger.error(f"Failed to process VTT file {vtt_file}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
