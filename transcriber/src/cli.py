"""Command Line Interface for Podcast Transcription Pipeline.

This module provides a user-friendly CLI for transcribing podcast episodes
from RSS feeds using Gemini 2.5 Pro.
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path
from typing import Optional, List
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator import TranscriptionOrchestrator
from src.utils.logging import setup_logging, get_logger
from src.utils.progress import ProgressBar
from src.metadata_index import get_metadata_index

logger = get_logger('cli')


def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments.
    
    Args:
        args: Optional list of arguments (for testing). If None, uses sys.argv
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        prog='podcast-transcriber',
        description='Transcribe podcast episodes from RSS feeds using Gemini AI',
        epilog='Example: podcast-transcriber transcribe --feed-url https://example.com/feed.xml'
    )
    
    # Add subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Transcribe command
    transcribe_parser = subparsers.add_parser(
        'transcribe',
        help='Transcribe episodes from a podcast RSS feed'
    )
    
    # Required arguments
    transcribe_parser.add_argument(
        '--feed-url',
        type=str,
        required=True,
        help='URL of the podcast RSS feed'
    )
    
    # Optional arguments
    transcribe_parser.add_argument(
        '--output-dir',
        type=str,
        default='data/transcripts',
        help='Directory for output VTT files (default: data/transcripts)'
    )
    
    transcribe_parser.add_argument(
        '--max-episodes',
        type=int,
        default=12,
        choices=range(1, 13),
        metavar='N',
        help='Maximum number of episodes to process (1-12, default: 12)'
    )
    
    transcribe_parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from checkpoint if available'
    )
    
    transcribe_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without actually transcribing'
    )
    
    transcribe_parser.add_argument(
        '--reset-state',
        action='store_true',
        help='Reset all state files before starting (with backup)'
    )
    
    # Query command
    query_parser = subparsers.add_parser(
        'query',
        help='Search and query processed episodes'
    )
    
    query_parser.add_argument(
        '--speaker',
        type=str,
        help='Search by speaker name'
    )
    
    query_parser.add_argument(
        '--podcast',
        type=str,
        help='Search by podcast name'
    )
    
    query_parser.add_argument(
        '--date',
        type=str,
        help='Search by date (YYYY-MM-DD or YYYY-MM)'
    )
    
    query_parser.add_argument(
        '--date-range',
        nargs=2,
        metavar=('START', 'END'),
        help='Search by date range (START_DATE END_DATE)'
    )
    
    query_parser.add_argument(
        '--keywords',
        type=str,
        help='Search by keywords in title/description'
    )
    
    query_parser.add_argument(
        '--all',
        type=str,
        help='Search across all fields'
    )
    
    query_parser.add_argument(
        '--export-csv',
        type=str,
        help='Export results to CSV file'
    )
    
    query_parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Maximum number of results to show (default: 20)'
    )
    
    query_parser.add_argument(
        '--stats',
        action='store_true',
        help='Show index statistics'
    )
    
    # State management command
    state_parser = subparsers.add_parser(
        'state',
        help='Manage application state files'
    )
    
    state_subparsers = state_parser.add_subparsers(dest='state_command', help='State management commands')
    
    # Show state
    state_show_parser = state_subparsers.add_parser('show', help='Show state file status')
    
    # Reset state
    state_reset_parser = state_subparsers.add_parser('reset', help='Reset all state files')
    state_reset_parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip creating backup before reset'
    )
    state_reset_parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    # Export state
    state_export_parser = state_subparsers.add_parser('export', help='Export state files')
    state_export_parser.add_argument(
        '--output',
        type=str,
        help='Output file path (default: state_export_TIMESTAMP.tar.gz)'
    )
    
    # Import state
    state_import_parser = state_subparsers.add_parser('import', help='Import state files')
    state_import_parser.add_argument(
        'file',
        type=str,
        help='State export file to import'
    )
    state_import_parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip creating backup before import'
    )
    
    # Add global arguments
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--no-progress',
        action='store_true',
        help='Disable progress bar'
    )
    
    # Parse arguments
    parsed_args = parser.parse_args(args)
    
    # Show help if no command provided
    if not parsed_args.command:
        parser.print_help()
        sys.exit(1)
    
    return parsed_args


async def transcribe_command(args: argparse.Namespace) -> int:
    """Execute the transcribe command.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Reset state if requested
        if args.reset_state:
            from src.utils.state_management import reset_state
            print("\nResetting state files before starting...")
            if not reset_state(create_backup=True):
                logger.error("Failed to reset state files")
                return 1
            print("State reset completed.\n")
        
        # Validate output directory
        output_dir = Path(args.output_dir)
        if not output_dir.exists():
            logger.info(f"Creating output directory: {output_dir}")
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # Dry run mode
        if args.dry_run:
            logger.info("DRY RUN MODE - No actual transcription will be performed")
            logger.info(f"Would process up to {args.max_episodes} episodes from: {args.feed_url}")
            logger.info(f"Output directory: {output_dir}")
            if args.resume:
                logger.info("Would check for resumable checkpoints")
            return 0
        
        # Create orchestrator
        orchestrator = TranscriptionOrchestrator(
            output_dir=output_dir,
            enable_checkpoint=True,
            resume=args.resume
        )
        
        # Show progress bar unless disabled
        show_progress = not args.no_progress
        
        if show_progress:
            # Create simple progress callback
            def progress_callback(current: int, total: int, message: str):
                """Update progress display."""
                progress = ProgressBar(total, prefix="Processing")
                progress.update(current, message)
        else:
            progress_callback = None
        
        # Process feed
        logger.info(f"Starting transcription of {args.feed_url}")
        if args.resume:
            logger.info("Checking for resumable checkpoints...")
        
        results = await orchestrator.process_feed(
            args.feed_url,
            max_episodes=args.max_episodes
        )
        
        # Check if results is None or missing required fields
        if not results or not isinstance(results, dict):
            logger.error("No valid results returned from orchestrator")
            return 1
        
        # Display results
        print("\n" + "="*60)
        print("TRANSCRIPTION SUMMARY")
        print("="*60)
        print(f"Status: {results.get('status', 'unknown')}")
        print(f"Episodes processed: {results.get('processed', 0)}")
        print(f"Episodes failed: {results.get('failed', 0)}")
        print(f"Episodes skipped: {results.get('skipped', 0)}")
        
        if results.get('processed', 0) > 0:
            print("\nProcessed Episodes:")
            for episode in results.get('episodes', []):
                if episode.get('status') == 'completed':
                    print(f"  ✓ {episode.get('title', 'Unknown')}")
                    print(f"    Output: {episode.get('output_file', 'N/A')}")
                    if episode.get('speakers'):
                        print(f"    Speakers: {', '.join(episode['speakers'])}")
        
        if results.get('failed', 0) > 0:
            print("\nFailed Episodes:")
            for episode in results.get('episodes', []):
                if episode.get('status') == 'failed':
                    print(f"  ✗ {episode.get('title', 'Unknown')}")
                    print(f"    Error: {episode.get('error', 'Unknown error')}")
        
        # Check API usage
        usage = orchestrator.gemini_client.get_usage_summary()
        print("\nAPI Usage:")
        for key, data in usage.items():
            print(f"  {key}:")
            print(f"    Requests: {data['requests_today']}/{data['requests_today'] + data['requests_remaining']}")
            print(f"    Tokens: {data['tokens_today']:,}/{data['tokens_today'] + data['tokens_remaining']:,}")
        
        print("="*60)
        
        # Return appropriate exit code
        if results.get('status') == 'completed' and results.get('failed', 0) == 0:
            return 0
        elif results.get('status') == 'quota_reached':
            logger.warning("Daily API quota reached. Resume tomorrow to continue.")
            return 2
        else:
            return 1
            
    except KeyboardInterrupt:
        logger.warning("\nTranscription interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def query_command(args: argparse.Namespace) -> int:
    """Execute the query command.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Get metadata index
        index = get_metadata_index()
        
        # Show statistics if requested
        if args.stats:
            stats = index.get_statistics()
            print("\n" + "="*60)
            print("INDEX STATISTICS")
            print("="*60)
            for key, value in stats.items():
                formatted_key = key.replace('_', ' ').title()
                print(f"{formatted_key}: {value}")
            print("="*60)
            return 0
        
        # Determine search type and execute
        search_result = None
        
        if args.speaker:
            search_result = index.search_by_speaker(args.speaker)
        elif args.podcast:
            search_result = index.search_by_podcast(args.podcast)
        elif args.date:
            search_result = index.search_by_date_range(args.date)
        elif args.date_range:
            start_date, end_date = args.date_range
            search_result = index.search_by_date_range(start_date, end_date)
        elif args.keywords:
            search_result = index.search_by_keywords(args.keywords)
        elif args.all:
            search_result = index.search_all(args.all)
        else:
            # No search criteria provided, show all episodes
            episodes = index.get_all_episodes()
            from src.metadata_index import SearchResult
            search_result = SearchResult(
                query="all_episodes",
                total_results=len(episodes),
                episodes=episodes,
                search_time_ms=0.0
            )
        
        # Export to CSV if requested
        if args.export_csv:
            try:
                output_file = index.export_to_csv(args.export_csv)
                print(f"Exported {search_result.total_results} episodes to: {output_file}")
                return 0
            except Exception as e:
                logger.error(f"CSV export failed: {e}")
                return 1
        
        # Display search results
        print("\n" + "="*60)
        print(f"SEARCH RESULTS: {search_result.query}")
        print("="*60)
        print(f"Found {search_result.total_results} episodes (search took {search_result.search_time_ms}ms)")
        
        if search_result.total_results == 0:
            print("No episodes found matching your criteria.")
            return 0
        
        # Limit results if specified
        episodes_to_show = search_result.episodes[:args.limit]
        if len(episodes_to_show) < search_result.total_results:
            print(f"Showing first {len(episodes_to_show)} of {search_result.total_results} results")
        
        print()
        
        # Display episodes
        for i, episode in enumerate(episodes_to_show, 1):
            print(f"{i:3d}. {episode.title}")
            print(f"     Podcast: {episode.podcast_name}")
            print(f"     Date: {episode.publication_date}")
            print(f"     File: {episode.file_path}")
            
            if episode.speakers:
                speakers_str = ', '.join(episode.speakers)
                print(f"     Speakers: {speakers_str}")
            
            if episode.duration:
                duration_min = episode.duration // 60
                duration_sec = episode.duration % 60
                print(f"     Duration: {duration_min}m {duration_sec}s")
            
            if episode.episode_number:
                print(f"     Episode: #{episode.episode_number}")
            
            print()
        
        if search_result.total_results > args.limit:
            print(f"... and {search_result.total_results - args.limit} more episodes")
            print(f"Use --limit {search_result.total_results} to see all results")
        
        print("="*60)
        return 0
        
    except Exception as e:
        logger.error(f"Query failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def state_command(args: argparse.Namespace) -> int:
    """Execute the state management command.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    from src.utils.state_management import (
        show_state_status, reset_state, export_state, import_state, get_state_directory
    )
    
    try:
        if args.state_command == 'show':
            # Show state status
            status = show_state_status()
            
            print("\n" + "="*60)
            print("STATE FILE STATUS")
            print("="*60)
            print(f"State Directory: {status['state_directory']}")
            print("\nState Files:")
            
            for file_path, info in status['state_files'].items():
                print(f"\n  {file_path}:")
                if info['exists']:
                    print(f"    Size: {info['size_bytes']:,} bytes")
                    print(f"    Modified: {info['modified']}")
                    if 'entries' in info:
                        print(f"    Entries: {info['entries']}")
                    if 'episodes' in info:
                        print(f"    Episodes: {info['episodes']}")
                else:
                    print("    Status: NOT FOUND")
            
            print("\n" + "="*60)
            return 0
            
        elif args.state_command == 'reset':
            # Reset state with confirmation
            if not args.force:
                state_dir = get_state_directory()
                response = input(f"\nAre you sure you want to reset all state files in {state_dir}? (yes/no): ")
                if response.lower() not in ['yes', 'y']:
                    print("Reset cancelled.")
                    return 0
            
            print("\nResetting state files...")
            success = reset_state(create_backup=not args.no_backup)
            
            if success:
                print("State reset completed successfully.")
                return 0
            else:
                print("State reset failed. Check logs for details.")
                return 1
                
        elif args.state_command == 'export':
            # Export state
            export_path = export_state(export_path=Path(args.output) if args.output else None)
            print(f"\nState exported to: {export_path}")
            return 0
            
        elif args.state_command == 'import':
            # Import state
            import_path = Path(args.file)
            if not import_path.exists():
                print(f"Error: Import file not found: {import_path}")
                return 1
            
            print(f"\nImporting state from: {import_path}")
            success = import_state(import_path, create_backup=not args.no_backup)
            
            if success:
                print("State import completed successfully.")
                return 0
            else:
                print("State import failed. Check logs for details.")
                return 1
                
        else:
            print("Error: No state subcommand specified. Use --help for usage.")
            return 1
            
    except Exception as e:
        logger.error(f"State command failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def main():
    """Main entry point for the CLI."""
    # Parse arguments
    args = parse_arguments()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(log_level)
    
    # Handle commands
    if args.command == 'transcribe':
        # Run async transcribe command
        exit_code = asyncio.run(transcribe_command(args))
    elif args.command == 'query':
        # Run query command
        exit_code = query_command(args)
    elif args.command == 'state':
        # Run state management command
        exit_code = state_command(args)
    else:
        logger.error(f"Unknown command: {args.command}")
        exit_code = 1
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()