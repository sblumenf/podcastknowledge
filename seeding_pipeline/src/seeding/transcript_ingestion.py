"""Transcript ingestion module for processing VTT files."""

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Set, Tuple
import hashlib
import json
import logging

from src.core.config import PipelineConfig
from src.core.exceptions import ValidationError, PipelineError
from src.core.interfaces import TranscriptSegment
from src.core.models import Podcast, Episode
from src.utils.log_utils import get_logger
from src.vtt import VTTParser
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
            # Parse VTT file
            segments = self.vtt_parser.parse_file(vtt_file.path)
            
            # Optionally merge short segments
            if getattr(self.config, 'merge_short_segments', True):
                min_duration = getattr(self.config, 'min_segment_duration', 2.0)
                segments = self.vtt_parser.merge_short_segments(segments, min_duration)
            
            # Create episode data
            episode_data = self._create_episode_data(vtt_file, segments)
            
            # Mark as processed
            self._processed_files.add(vtt_file.file_hash)
            
            return {
                'status': 'success',
                'file': vtt_file.to_dict(),
                'episode': episode_data,
                'segments': segments,
                'segment_count': len(segments)
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
                           segments: List[TranscriptSegment]) -> Dict[str, Any]:
        """Create episode data from VTT file and segments.
        
        Args:
            vtt_file: VTT file being processed
            segments: Parsed transcript segments
            
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
        
        return {
            'id': vtt_file.file_hash[:12],  # Use first 12 chars of hash as ID
            'title': vtt_file.episode_title,
            'podcast_name': vtt_file.podcast_name,
            'duration_seconds': duration,
            'speaker_count': len(speakers),
            'speakers': speakers,
            'segment_count': len(segments),
            'file_path': str(vtt_file.path),
            'processed_at': datetime.utcnow().isoformat()
        }
    
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

