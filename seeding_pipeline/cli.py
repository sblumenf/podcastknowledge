#!/usr/bin/env python3
"""Command Line Interface for VTT Knowledge Graph Pipeline.

This CLI provides batch processing commands for transforming VTT transcript files
into structured knowledge graphs using AI-powered analysis.
"""

import argparse
import json
import sys
import os
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import fnmatch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.seeding import PodcastKnowledgePipeline as VTTKnowledgePipeline
from src.core.config import PipelineConfig
from src.core.exceptions import PipelineError
from src.processing.vtt_parser import VTTParser
from src.seeding.transcript_ingestion import TranscriptIngestionManager
from src.utils.logging import setup_logging as setup_structured_logging, get_logger
from src.seeding.checkpoint import ProgressCheckpoint


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """Set up structured logging configuration."""
    level = "DEBUG" if verbose else os.environ.get("PODCAST_KG_LOG_LEVEL", "INFO")
    
    # Create logs directory if needed
    if log_file:
        log_dir = Path(log_file).parent
        log_dir.mkdir(exist_ok=True, parents=True)
    
    setup_structured_logging(
        level=level,
        log_file=log_file,
        json_format=os.environ.get("PODCAST_KG_LOG_FORMAT", "json").lower() == "json",
        add_context=True,
        add_performance=verbose
    )


def get_file_hash(file_path: Path) -> str:
    """Calculate MD5 hash of a file for change detection."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def find_vtt_files(folder: Path, pattern: str = "*.vtt", recursive: bool = False) -> List[Path]:
    """Find VTT files in a folder matching the given pattern.
    
    Args:
        folder: Directory to search
        pattern: Glob pattern for file matching (default: *.vtt)
        recursive: Whether to search subdirectories
        
    Returns:
        List of VTT file paths
    """
    vtt_files = []
    
    if recursive:
        # Use rglob for recursive search
        for file_path in folder.rglob(pattern):
            if file_path.is_file():
                vtt_files.append(file_path)
    else:
        # Use glob for non-recursive search
        for file_path in folder.glob(pattern):
            if file_path.is_file():
                vtt_files.append(file_path)
    
    return sorted(vtt_files)  # Sort for consistent ordering


def validate_vtt_file(file_path: Path) -> Tuple[bool, Optional[str]]:
    """Validate a VTT file.
    
    Args:
        file_path: Path to VTT file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Check if file exists
        if not file_path.exists():
            return False, f"File does not exist: {file_path}"
        
        # Check if file is readable
        if not file_path.is_file():
            return False, f"Not a file: {file_path}"
        
        # Check file extension
        if file_path.suffix.lower() != '.vtt':
            return False, f"Not a VTT file: {file_path}"
        
        # Try to read first few lines to check format
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            # VTT files should start with WEBVTT
            if not first_line.startswith('WEBVTT'):
                return False, f"Invalid VTT format (missing WEBVTT header): {file_path}"
        
        return True, None
        
    except Exception as e:
        return False, f"Error validating file {file_path}: {str(e)}"


def process_vtt(args: argparse.Namespace) -> int:
    """Process VTT transcript files into knowledge graph.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = get_logger(__name__)
    
    try:
        # Load configuration
        config = None
        if args.config:
            config = PipelineConfig.from_file(args.config)
        else:
            config = PipelineConfig.from_env()
        
        # Initialize pipeline
        pipeline = VTTKnowledgePipeline(config)
        
        # Find VTT files
        folder = Path(args.folder)
        if not folder.exists():
            print(f"Error: Folder does not exist: {folder}", file=sys.stderr)
            return 1
        
        if not folder.is_dir():
            print(f"Error: Not a directory: {folder}", file=sys.stderr)
            return 1
        
        print(f"Scanning for VTT files in: {folder}")
        print(f"  Pattern: {args.pattern}")
        print(f"  Recursive: {args.recursive}")
        
        vtt_files = find_vtt_files(folder, args.pattern, args.recursive)
        
        if not vtt_files:
            print(f"No VTT files found matching pattern '{args.pattern}'")
            return 0
        
        print(f"\nFound {len(vtt_files)} VTT file(s)")
        
        # Dry run - just show what would be processed
        if args.dry_run:
            print("\nDRY RUN - Files that would be processed:")
            for i, file_path in enumerate(vtt_files, 1):
                is_valid, error = validate_vtt_file(file_path)
                status = "✓ Valid" if is_valid else f"✗ Invalid: {error}"
                print(f"  {i}. {file_path.relative_to(folder)} - {status}")
            return 0
        
        # Initialize checkpoint if enabled
        checkpoint = None
        if not args.no_checkpoint:
            checkpoint_dir = Path(args.checkpoint_dir)
            checkpoint_dir.mkdir(exist_ok=True, parents=True)
            checkpoint = ProgressCheckpoint(
                checkpoint_dir=str(checkpoint_dir),
                extraction_mode='vtt'
            )
        
        # Process files
        processed = 0
        failed = 0
        skipped = 0
        
        print("\nProcessing VTT files...")
        for i, file_path in enumerate(vtt_files, 1):
            print(f"\n[{i}/{len(vtt_files)}] Processing: {file_path.name}")
            
            # Validate file
            is_valid, error = validate_vtt_file(file_path)
            if not is_valid:
                print(f"  ✗ Skipping invalid file: {error}")
                logger.error(f"Invalid VTT file: {file_path} - {error}")
                failed += 1
                continue
            
            # Check if already processed (via checkpoint)
            if checkpoint:
                file_hash = get_file_hash(file_path)
                if checkpoint.is_vtt_processed(str(file_path), file_hash):
                    print(f"  ✓ Already processed (same content)")
                    skipped += 1
                    continue
            
            try:
                # Create ingestion manager
                ingestion_manager = TranscriptIngestionManager(
                    pipeline=pipeline,
                    checkpoint=checkpoint
                )
                
                # Process the VTT file
                result = ingestion_manager.process_vtt_file(
                    vtt_file=str(file_path),
                    metadata={
                        'source': 'cli',
                        'file_name': file_path.name,
                        'file_path': str(file_path),
                        'processed_at': datetime.now().isoformat()
                    }
                )
                
                if result['success']:
                    print(f"  ✓ Success - {result['segments_processed']} segments processed")
                    processed += 1
                    
                    # Save checkpoint
                    if checkpoint:
                        checkpoint.mark_vtt_processed(
                            str(file_path),
                            file_hash,
                            result['segments_processed']
                        )
                else:
                    print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
                    failed += 1
                    
            except Exception as e:
                print(f"  ✗ Error: {str(e)}")
                logger.error(f"Failed to process {file_path}: {str(e)}", exc_info=True)
                failed += 1
                
                if not args.skip_errors:
                    print("\nAborting due to error. Use --skip-errors to continue on errors.")
                    break
        
        # Print summary
        print("\n" + "="*50)
        print("Processing Summary:")
        print(f"  Total files found: {len(vtt_files)}")
        print(f"  Successfully processed: {processed}")
        print(f"  Failed: {failed}")
        print(f"  Skipped (already processed): {skipped}")
        
        if failed > 0:
            print("\nSome files failed to process. Check logs for details.")
            return 1 if processed == 0 else 0
        
        print("\nVTT processing completed successfully!")
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    finally:
        # Cleanup
        if 'pipeline' in locals():
            pipeline.cleanup()


def checkpoint_status(args: argparse.Namespace) -> int:
    """Show checkpoint status and processing history.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        checkpoint_dir = Path(args.checkpoint_dir)
        if not checkpoint_dir.exists():
            print(f"Checkpoint directory does not exist: {checkpoint_dir}")
            return 0
        
        # Initialize checkpoint reader
        checkpoint = ProgressCheckpoint(
            checkpoint_dir=str(checkpoint_dir),
            extraction_mode='vtt'
        )
        
        # Get processed files
        processed_files = checkpoint.get_processed_vtt_files()
        
        if not processed_files:
            print("No VTT files have been processed yet.")
            return 0
        
        print(f"Checkpoint Status ({checkpoint_dir}):")
        print(f"  Total files processed: {len(processed_files)}")
        print("\nProcessed Files:")
        
        for file_info in sorted(processed_files, key=lambda x: x.get('processed_at', '')):
            print(f"\n  File: {file_info['file']}")
            print(f"    Hash: {file_info['hash'][:16]}...")
            print(f"    Segments: {file_info.get('segments', 'unknown')}")
            print(f"    Processed at: {file_info.get('processed_at', 'unknown')}")
        
        return 0
        
    except Exception as e:
        print(f"Failed to get checkpoint status: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def checkpoint_clean(args: argparse.Namespace) -> int:
    """Clean checkpoint data.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        checkpoint_dir = Path(args.checkpoint_dir)
        if not checkpoint_dir.exists():
            print(f"Checkpoint directory does not exist: {checkpoint_dir}")
            return 0
        
        # Confirm before cleaning
        if not args.force:
            response = input(f"Are you sure you want to clean all checkpoints in {checkpoint_dir}? [y/N] ")
            if response.lower() != 'y':
                print("Cancelled.")
                return 0
        
        # Clean checkpoint files
        checkpoint_files = list(checkpoint_dir.glob("*.json"))
        
        if args.pattern:
            # Filter by pattern if provided
            checkpoint_files = [f for f in checkpoint_files if fnmatch.fnmatch(f.name, args.pattern)]
        
        if not checkpoint_files:
            print("No checkpoint files found to clean.")
            return 0
        
        print(f"Cleaning {len(checkpoint_files)} checkpoint file(s)...")
        
        for checkpoint_file in checkpoint_files:
            try:
                checkpoint_file.unlink()
                print(f"  ✓ Removed: {checkpoint_file.name}")
            except Exception as e:
                print(f"  ✗ Failed to remove {checkpoint_file.name}: {e}")
        
        print("\nCheckpoint cleanup completed.")
        return 0
        
    except Exception as e:
        print(f"Failed to clean checkpoints: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='VTT Knowledge Graph Pipeline - Transform transcripts into structured knowledge',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all VTT files in a folder
  %(prog)s process-vtt --folder /path/to/vtt/files
  
  # Process with specific pattern
  %(prog)s process-vtt --folder /path/to/vtt --pattern "episode_*.vtt"
  
  # Recursive processing
  %(prog)s process-vtt --folder /path/to/vtt --recursive
  
  # Dry run to see what would be processed
  %(prog)s process-vtt --folder /path/to/vtt --dry-run
  
  # Continue on errors
  %(prog)s process-vtt --folder /path/to/vtt --skip-errors
  
  # View checkpoint status
  %(prog)s checkpoint-status
  
  # Clean checkpoints
  %(prog)s checkpoint-clean --force
        """
    )
    
    # Global options
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '-c', '--config',
        type=str,
        help='Path to configuration file (YAML)'
    )
    
    parser.add_argument(
        '--log-file',
        type=str,
        help='Path to log file'
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands'
    )
    
    # Process VTT command (main command)
    vtt_parser = subparsers.add_parser(
        'process-vtt',
        help='Process VTT transcript files into knowledge graph'
    )
    
    vtt_parser.add_argument(
        '--folder',
        type=str,
        required=True,
        help='Folder containing VTT files'
    )
    
    vtt_parser.add_argument(
        '--pattern',
        type=str,
        default='*.vtt',
        help='File pattern to match (default: *.vtt)'
    )
    
    vtt_parser.add_argument(
        '--recursive',
        action='store_true',
        help='Search for VTT files recursively in subdirectories'
    )
    
    vtt_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without actually processing'
    )
    
    vtt_parser.add_argument(
        '--skip-errors',
        action='store_true',
        help='Continue processing even if some files fail'
    )
    
    vtt_parser.add_argument(
        '--no-checkpoint',
        action='store_true',
        help='Disable checkpoint tracking'
    )
    
    vtt_parser.add_argument(
        '--checkpoint-dir',
        type=str,
        default='checkpoints',
        help='Directory for checkpoint files (default: checkpoints)'
    )
    
    # Checkpoint status command
    status_parser = subparsers.add_parser(
        'checkpoint-status',
        help='Show checkpoint status and processing history'
    )
    
    status_parser.add_argument(
        '--checkpoint-dir',
        type=str,
        default='checkpoints',
        help='Directory containing checkpoint files (default: checkpoints)'
    )
    
    # Checkpoint clean command
    clean_parser = subparsers.add_parser(
        'checkpoint-clean',
        help='Clean checkpoint data'
    )
    
    clean_parser.add_argument(
        '--checkpoint-dir',
        type=str,
        default='checkpoints',
        help='Directory containing checkpoint files (default: checkpoints)'
    )
    
    clean_parser.add_argument(
        '--pattern',
        type=str,
        help='Pattern for checkpoint files to clean (e.g., "vtt_*.json")'
    )
    
    clean_parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.verbose, args.log_file if hasattr(args, 'log_file') else None)
    
    # Execute command
    if args.command == 'process-vtt':
        return process_vtt(args)
    elif args.command == 'checkpoint-status':
        return checkpoint_status(args)
    elif args.command == 'checkpoint-clean':
        return checkpoint_clean(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())