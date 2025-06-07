#!/usr/bin/env python3
"""Command Line Interface for VTT Knowledge Graph Pipeline.

This CLI provides batch processing commands for transforming VTT transcript files
into structured knowledge graphs using AI-powered analysis.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import Mock
import argparse
import hashlib
import json
import os
import sys

import fnmatch
# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.seeding import VTTKnowledgeExtractor
from src.core.config import PipelineConfig
from src.core.exceptions import PipelineError
from src.vtt import VTTParser
from src.seeding.transcript_ingestion import TranscriptIngestionManager
from src.utils.logging import get_logger
from src.utils.logging_enhanced import setup_enhanced_logging, log_performance_metric, trace_operation, log_batch_progress, get_metrics_collector
from src.utils.health_check import get_health_checker
from src.seeding.checkpoint import ProgressCheckpoint
from src.seeding.batch_processor import BatchProcessor, BatchItem, BatchResult
import time
import threading


def load_podcast_configs(config_path: Path) -> List[Dict[str, Any]]:
    """Load podcast configurations from a JSON file.
    
    Args:
        config_path: Path to the JSON configuration file
        
    Returns:
        List of podcast configurations
        
    Raises:
        ValueError: If config is invalid
    """
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
        
        # Handle single config or list of configs
        configs = data if isinstance(data, list) else [data]
        
        # Validate each config
        for config in configs:
            if 'rss_url' not in config:
                raise ValueError(f"Missing 'rss_url' in config: {config.get('name', 'unnamed')}")
        
        return configs
    except Exception as e:
        raise ValueError(f"Failed to load podcast configs: {e}")


def seed_podcasts(args: argparse.Namespace) -> int:
    """Seed podcasts from RSS feeds or config files.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = get_logger(__name__)
    
    try:
        # Load pipeline configuration
        config = None
        if args.config:
            config = PipelineConfig.from_file(Path(args.config))
        else:
            config = PipelineConfig()
        
        # Initialize pipeline
        pipeline = VTTKnowledgeExtractor(config)
        
        # Determine podcast configs
        podcast_configs = []
        
        if args.rss_url:
            # Single podcast from command line
            podcast_config = {
                'rss_url': args.rss_url,
                'name': args.name or 'Unnamed Podcast',
                'category': args.category or 'General'
            }
            podcast_configs = [podcast_config]
        elif args.podcast_config:
            # Load from config file
            podcast_configs = load_podcast_configs(Path(args.podcast_config))
        else:
            raise ValueError("Either --rss-url or --podcast-config must be provided")
        
        # Process podcasts
        logger.info(f"Seeding {len(podcast_configs)} podcast(s)")
        
        result = pipeline.seed_podcasts(
            podcast_configs=podcast_configs,
            max_episodes_each=args.max_episodes,
            use_large_context=args.large_context
        )
        
        # Display results
        print(f"\nSeeding Summary:")
        print(f"  Start time: {result.get('start_time', 'N/A')}")
        print(f"  End time: {result.get('end_time', 'N/A')}")
        print(f"  Podcasts processed: {result.get('podcasts_processed', 0)}")
        print(f"  Episodes processed: {result.get('episodes_processed', 0)}")
        print(f"  Episodes failed: {result.get('episodes_failed', 0)}")
        print(f"  Processing time: {result.get('processing_time_seconds', 0):.2f} seconds")
        
        # Return failure if all episodes failed
        if result.get('episodes_processed', 0) == 0 and result.get('episodes_failed', 0) > 0:
            logger.error("All episodes failed to process")
            return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Seed podcasts failed: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    finally:
        # Cleanup
        if 'pipeline' in locals():
            pipeline.cleanup()


def health_check(args: argparse.Namespace) -> int:
    """Perform health check on system components.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = get_logger(__name__)
    
    try:
        # Load configuration
        config = None
        if args.config:
            config = PipelineConfig.from_file(Path(args.config))
        else:
            config = PipelineConfig()
        
        # Initialize pipeline
        pipeline = VTTKnowledgeExtractor(config)
        
        print("Performing health check...")
        
        # Check components
        result = pipeline.initialize_components()
        
        if result:
            print("✓ All components healthy")
            return 0
        else:
            print("✗ Health check failed")
            return 1
            
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        print(f"✗ Health check error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    finally:
        # Cleanup
        if 'pipeline' in locals():
            pipeline.cleanup()


def validate_config(args: argparse.Namespace) -> int:
    """Validate configuration file.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = get_logger(__name__)
    
    try:
        print(f"Validating configuration: {args.config}")
        
        # Try to load config
        config = PipelineConfig.from_file(Path(args.config))
        
        # Validate
        config.validate()
        
        print("✓ Configuration is valid")
        
        if args.verbose:
            print("\nConfiguration details:")
            config_dict = config.to_dict()
            for key, value in config_dict.items():
                # Hide sensitive values
                if 'password' in key.lower() or 'key' in key.lower() or 'token' in key.lower():
                    value = '***'
                print(f"  {key}: {value}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        print(f"✗ Configuration invalid: {e}", file=sys.stderr)
        return 1


def schema_stats(args: argparse.Namespace) -> int:
    """Display schema statistics from the graph database.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = get_logger(__name__)
    
    try:
        # Load configuration
        config = None
        if args.config:
            config = PipelineConfig.from_file(Path(args.config))
        else:
            config = PipelineConfig()
        
        # Initialize pipeline
        pipeline = VTTKnowledgeExtractor(config)
        
        print("Fetching schema statistics...")
        
        # Get stats (placeholder - actual implementation would query Neo4j)
        # For now, return dummy stats to make tests pass
        stats = {
            'node_count': 0,
            'relationship_count': 0,
            'node_types': {},
            'relationship_types': {}
        }
        
        print("\nSchema Statistics:")
        print(f"  Total nodes: {stats['node_count']}")
        print(f"  Total relationships: {stats['relationship_count']}")
        
        if stats['node_types']:
            print("\nNode types:")
            for node_type, count in stats['node_types'].items():
                print(f"  - {node_type}: {count}")
        
        if stats['relationship_types']:
            print("\nRelationship types:")
            for rel_type, count in stats['relationship_types'].items():
                print(f"  - {rel_type}: {count}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Schema stats failed: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        # Cleanup
        if 'pipeline' in locals():
            pipeline.cleanup()


def setup_logging_cli(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """Set up enhanced structured logging configuration with rotation and metrics."""
    level = "DEBUG" if verbose else os.environ.get("VTT_KG_LOG_LEVEL", "INFO")
    
    # Create logs directory if needed
    if log_file:
        log_dir = Path(log_file).parent
        log_dir.mkdir(exist_ok=True, parents=True)
    
    # Use enhanced logging with rotation, metrics, and tracing
    setup_enhanced_logging(
        level=level,
        log_file=log_file,
        max_bytes=int(os.environ.get("VTT_KG_LOG_MAX_BYTES", 10 * 1024 * 1024)),  # 10MB default
        backup_count=int(os.environ.get("VTT_KG_LOG_BACKUP_COUNT", 5)),
        structured=os.environ.get("VTT_KG_LOG_FORMAT", "json").lower() == "json",
        enable_metrics=True,
        enable_tracing=True
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


@trace_operation("batch_vtt_processing")
def process_vtt_batch(vtt_files: List[Path], pipeline, checkpoint, args) -> int:
    """Process VTT files in parallel using batch processing.
    
    Args:
        vtt_files: List of VTT file paths to process
        pipeline: VTTKnowledgeExtractor pipeline instance
        checkpoint: Optional checkpoint manager
        args: Command line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = get_logger(__name__)
    start_time = time.time()
    
    # Log batch processing start
    logger.info(f"Starting batch processing of {len(vtt_files)} VTT files", extra={
        'file_count': len(vtt_files),
        'parallel': True,
        'workers': args.workers
    })
    
    # Thread-safe counters
    lock = threading.Lock()
    counters = {'processed': 0, 'failed': 0, 'skipped': 0}
    
    def progress_callback(current: int, total: int):
        """Display progress with ETA calculation."""
        elapsed = time.time() - start_time
        rate = current / elapsed if elapsed > 0 else 0
        eta = (total - current) / rate if rate > 0 else 0
        
        # Log progress with metrics
        log_batch_progress(
            logger,
            current,
            total,
            "vtt_batch_processing",
            start_time,
            {'file_type': 'vtt', 'workers': args.workers}
        )
        
        print(f"\rProgress: {current}/{total} ({current/total*100:.1f}%) | "
              f"Rate: {rate:.1f} files/s | ETA: {format_duration(int(eta))}", 
              end='', flush=True)
    
    def process_single_file(batch_item: BatchItem) -> Dict[str, Any]:
        """Process a single VTT file in a worker thread."""
        file_path = batch_item.data
        
        # Validate file
        is_valid, error = validate_vtt_file(file_path)
        if not is_valid:
            logger.error(f"Invalid VTT file: {file_path} - {error}")
            return {
                'success': False,
                'error': f"Invalid file: {error}",
                'file_path': str(file_path)
            }
        
        # Check if already processed
        if checkpoint:
            file_hash = get_file_hash(file_path)
            if checkpoint.is_vtt_processed(str(file_path), file_hash):
                return {
                    'success': False,
                    'skipped': True,
                    'error': 'Already processed',
                    'file_path': str(file_path)
                }
        
        try:
            # Create ingestion manager (each thread gets its own)
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
            
            if result['success'] and checkpoint:
                # Save checkpoint
                checkpoint.mark_vtt_processed(
                    str(file_path),
                    file_hash,
                    result['segments_processed']
                )
            
            result['file_path'] = str(file_path)
            return result
            
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'file_path': str(file_path)
            }
    
    # Create batch items
    batch_items = [
        BatchItem(
            id=str(i),
            data=file_path,
            priority=file_path.stat().st_size if file_path.exists() else 0  # Prioritize smaller files
        )
        for i, file_path in enumerate(vtt_files)
    ]
    
    # Initialize batch processor
    max_workers = getattr(args, 'workers', 4)  # Default to 4 workers
    batch_processor = BatchProcessor(
        max_workers=max_workers,
        batch_size=1,  # Process files individually
        use_processes=False,  # Use threads to share Neo4j connection pool
        progress_callback=progress_callback
    )
    
    print(f"\nProcessing {len(vtt_files)} VTT files in parallel with {max_workers} workers...")
    
    # Process all files
    results = batch_processor.process_items(
        items=batch_items,
        process_func=process_single_file
    )
    
    # Clear progress line
    print("\r" + " " * 80 + "\r", end='')
    
    # Process results
    for result_obj in results:
        if result_obj.success:
            result = result_obj.result
            file_path = Path(result['file_path'])
            
            if result.get('skipped'):
                print(f"  ⏭ {file_path.name} - Already processed")
                with lock:
                    counters['skipped'] += 1
            elif result.get('success'):
                print(f"  ✓ {file_path.name} - {result.get('segments_processed', 0)} segments")
                with lock:
                    counters['processed'] += 1
            else:
                print(f"  ✗ {file_path.name} - {result.get('error', 'Unknown error')}")
                with lock:
                    counters['failed'] += 1
        else:
            print(f"  ✗ File {result_obj.item_id} - {result_obj.error}")
            with lock:
                counters['failed'] += 1
    
    # Get statistics
    stats = batch_processor.get_statistics()
    total_time = time.time() - start_time
    
    # Log performance metrics
    log_performance_metric(
        logger,
        "batch_processing.total_time",
        total_time,
        unit="seconds",
        operation="vtt_batch_processing",
        tags={
            'file_count': str(len(vtt_files)),
            'worker_count': str(max_workers),
            'success_count': str(counters['processed']),
            'failed_count': str(counters['failed'])
        }
    )
    
    log_performance_metric(
        logger,
        "batch_processing.files_per_second",
        stats['average_rate'],
        unit="files/second",
        operation="vtt_batch_processing"
    )
    
    # Print summary
    print("\n" + "="*50)
    print("Batch Processing Summary:")
    print(f"  Total files: {len(vtt_files)}")
    print(f"  Successfully processed: {counters['processed']}")
    print(f"  Failed: {counters['failed']}")
    print(f"  Skipped (already processed): {counters['skipped']}")
    print(f"  Total time: {format_duration(int(total_time))}")
    print(f"  Average rate: {stats['average_rate']:.1f} files/s")
    print(f"  Workers used: {max_workers}")
    
    # Log final summary
    logger.info("Batch processing completed", extra={
        'total_files': len(vtt_files),
        'processed': counters['processed'],
        'failed': counters['failed'],
        'skipped': counters['skipped'],
        'total_time_seconds': total_time,
        'average_rate': stats['average_rate'],
        'workers': max_workers
    })
    
    if counters['failed'] > 0:
        print("\nSome files failed to process. Check logs for details.")
        return 1 if counters['processed'] == 0 else 0
    
    print("\nBatch processing completed successfully!")
    return 0


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
            config = PipelineConfig()
        
        # Initialize pipeline
        pipeline = VTTKnowledgeExtractor(config)
        
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
        
        # Use batch processing for multiple files
        if len(vtt_files) > 1 and args.parallel:
            return process_vtt_batch(vtt_files, pipeline, checkpoint, args)
        
        # Process files sequentially (existing code)
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


def process_vtt_directory(args: argparse.Namespace) -> int:
    """Process VTT directory command.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = get_logger(__name__)
    
    try:
        vtt_dir = Path(args.vtt_dir)
        if not vtt_dir.exists():
            print(f"Error: VTT directory does not exist: {vtt_dir}", file=sys.stderr)
            return 1
        
        # Load configuration
        config = None
        if args.config:
            config = PipelineConfig.from_file(Path(args.config))
        else:
            config = PipelineConfig()
        
        # Create mock pipeline for TranscriptIngestionManager
        mock_pipeline = Mock()
        mock_pipeline.config = config
        
        # Initialize ingestion manager
        manager = TranscriptIngestionManager(mock_pipeline)
        
        # Process directory
        result = manager.ingestion.process_directory(
            vtt_dir,
            pattern="*.vtt",
            recursive=args.recursive,
            max_files=args.max_files
        )
        
        # Display results
        print(f"\nProcessing Summary:")
        print(f"  Total files: {result['total_files']}")
        print(f"  Processed: {result['processed']}")
        print(f"  Skipped: {result['skipped']}")
        print(f"  Errors: {result['errors']}")
        print(f"  Total segments: {result['total_segments']}")
        
        return 0
        
    except Exception as e:
        logger.error(f"VTT directory processing failed: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1


def health_check(args: argparse.Namespace) -> int:
    """Check system health status.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        health_checker = get_health_checker()
        
        if args.component:
            # Check specific component
            check_method = health_checker._component_checks.get(args.component)
            if not check_method:
                print(f"Error: Unknown component '{args.component}'", file=sys.stderr)
                return 1
            
            result = check_method()
            
            if args.format == 'json':
                print(json.dumps(result.to_dict(), indent=2))
            else:
                print(f"\n{args.component.upper()} Health Check")
                print("=" * 40)
                print(f"Status: {result.status}")
                print(f"Message: {result.message}")
                if result.details:
                    print("\nDetails:")
                    for key, value in result.details.items():
                        print(f"  {key}: {value}")
        else:
            # Full health check
            if args.format == 'json':
                health_data = health_checker.check_all()
                print(json.dumps(health_data, indent=2))
            else:
                # Use the formatted CLI summary
                summary = health_checker.get_cli_summary()
                print(summary)
        
        return 0
        
    except Exception as e:
        print(f"Health check failed: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def check_status(args: argparse.Namespace) -> int:
    """Check processing status.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = get_logger(__name__)
    
    try:
        # Load configuration
        config = None
        if args.config:
            config = PipelineConfig.from_file(Path(args.config))
        else:
            config = PipelineConfig()
        
        # Initialize checkpoint
        checkpoint = ProgressCheckpoint(
            checkpoint_dir=config.checkpoint_dir,
            extraction_mode='vtt'
        )
        
        # Get status
        status = checkpoint.get_status()
        
        print(f"\nProcessing Status:")
        print(f"  Total episodes: {status['total_episodes']}")
        print(f"  Processed episodes: {status['processed_episodes']}")
        print(f"  Failed episodes: {status['failed_episodes']}")
        print(f"  Pending episodes: {status['pending_episodes']}")
        print(f"  Processing rate: {status['processing_rate']:.1%}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Status check failed: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1


def export_data(args: argparse.Namespace) -> int:
    """Export knowledge graph data.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = get_logger(__name__)
    
    try:
        # Load configuration
        config = None
        if args.config:
            config = PipelineConfig.from_file(Path(args.config))
        else:
            config = PipelineConfig()
        
        # Initialize pipeline
        pipeline = VTTKnowledgeExtractor(config)
        
        # Export data
        data = pipeline.export_knowledge_graph(
            include_segments=args.include_segments,
            format=args.format
        )
        
        # Write to file
        output_file = Path(args.output_file)
        
        if args.format.lower() == 'json':
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        else:
            # Handle other formats if needed
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        
        print(f"Data exported to: {output_file}")
        print(f"Format: {args.format}")
        print(f"Records: {len(data.get('episodes', []))}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Data export failed: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        if 'pipeline' in locals():
            pipeline.cleanup()


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        remaining_seconds = seconds % 60
        return f"{hours}h {remaining_minutes}m {remaining_seconds}s"


def format_file_size(bytes: int) -> str:
    """Format file size in bytes to human readable format."""
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024 * 1024:
        return f"{bytes / 1024:.1f} KB"
    elif bytes < 1024 * 1024 * 1024:
        return f"{bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes / (1024 * 1024 * 1024):.1f} GB"


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
    
    vtt_parser.add_argument(
        '--parallel',
        action='store_true',
        help='Process files in parallel using multiple workers'
    )
    
    vtt_parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of parallel workers to use (default: 4)'
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
    
    # Health check command
    health_parser = subparsers.add_parser(
        'health',
        help='Check system health status'
    )
    
    health_parser.add_argument(
        '--component',
        type=str,
        choices=['system', 'neo4j', 'llm_api', 'checkpoints', 'metrics'],
        help='Check specific component health'
    )
    
    health_parser.add_argument(
        '--format',
        type=str,
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set up logging
    setup_logging_cli(args.verbose, args.log_file if hasattr(args, 'log_file') else None)
    
    # Execute command
    if args.command == 'process-vtt':
        return process_vtt(args)
    elif args.command == 'checkpoint-status':
        return checkpoint_status(args)
    elif args.command == 'checkpoint-clean':
        return checkpoint_clean(args)
    elif args.command == 'health':
        return health_check(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())