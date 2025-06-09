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


async def _retry_failed_episodes(orchestrator: TranscriptionOrchestrator, args: argparse.Namespace) -> int:
    """Retry failed episodes from previous runs.
    
    Args:
        orchestrator: TranscriptionOrchestrator instance
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    logger.info("Checking for failed episodes to retry...")
    
    # Get failed episodes from progress tracker
    failed_episodes = orchestrator.progress_tracker.get_failed(max_attempts=3)
    
    if not failed_episodes:
        print("No failed episodes found to retry.")
        return 0
    
    print(f"\nFound {len(failed_episodes)} failed episodes to retry:")
    for i, episode in enumerate(failed_episodes, 1):
        print(f"  {i}. {episode.title}")
        print(f"     Last error: {episode.error}")
        print(f"     Attempts: {episode.attempt_count}")
    
    # Confirm retry
    response = input("\nDo you want to retry these episodes? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Retry cancelled.")
        return 0
    
    print("\nRetrying failed episodes...")
    
    # Reset failure status for retry
    from src.progress_tracker import EpisodeStatus
    for episode in failed_episodes:
        # Reset episode status to pending and clear error
        episode.status = EpisodeStatus.PENDING
        orchestrator.progress_tracker.state.episodes[episode.guid].status = EpisodeStatus.PENDING
        episode.error = None
        episode.error_type = None
    
    # Save updated state
    orchestrator.progress_tracker._save_state()
    
    # Create list of episodes for processing
    from src.feed_parser import Episode
    retry_episodes = []
    
    for episode_progress in failed_episodes:
        # Reconstruct Episode object from progress data
        episode = Episode(
            guid=episode_progress.guid,
            title=episode_progress.title,
            audio_url=episode_progress.audio_url,
            publication_date=episode_progress.publication_date,
            description="",  # Not stored in progress
            duration="",     # Not stored in progress
            author=""        # Not stored in progress
        )
        retry_episodes.append(episode)
    
    # Process the retry episodes using orchestrator's internal logic
    from src.utils.batch_progress import BatchProgressTracker
    
    # Initialize batch progress tracker for retry
    batch_tracker = BatchProgressTracker(orchestrator.progress_tracker, len(retry_episodes))
    batch_tracker.start_batch()
    
    results = {
        'status': 'completed',
        'processed': 0,
        'failed': 0,
        'skipped': 0,
        'episodes': []
    }
    
    # Create fake podcast metadata for processing
    from src.feed_parser import PodcastMetadata
    podcast_metadata = PodcastMetadata(
        title="Retry Session",
        description="Retrying failed episodes",
        link="",
        language="en",
        author=""
    )
    
    for i, episode in enumerate(retry_episodes):
        batch_tracker.update_current_episode(episode.title)
        
        try:
            # Process episode using orchestrator's private method
            episode_result = await orchestrator._process_episode(episode, podcast_metadata)
            results['episodes'].append(episode_result)
            
            if episode_result['status'] == 'completed':
                results['processed'] += 1
                processing_time = episode_result.get('duration', 300.0)
                batch_tracker.episode_completed(processing_time)
            elif episode_result['status'] == 'failed':
                results['failed'] += 1
                error_msg = episode_result.get('error', 'Unknown error')
                batch_tracker.episode_failed(error_msg)
            elif episode_result['status'] == 'skipped':
                results['skipped'] += 1
                reason = episode_result.get('reason', 'Unknown reason')
                batch_tracker.episode_skipped(reason)
        
        except Exception as e:
            logger.error(f"Failed to retry episode {episode.title}: {e}")
            results['failed'] += 1
            batch_tracker.episode_failed(str(e))
    
    # Finish batch tracking
    if results['status'] == 'completed':
        batch_tracker.finish_batch("Retry completed successfully")
    else:
        batch_tracker.finish_batch("Retry completed with errors")
    
    # Display retry results
    print("\n" + "="*60)
    print("RETRY SUMMARY")
    print("="*60)
    print(f"Status: {results.get('status', 'unknown')}")
    print(f"Episodes processed: {results.get('processed', 0)}")
    print(f"Episodes failed again: {results.get('failed', 0)}")
    print(f"Episodes skipped: {results.get('skipped', 0)}")
    
    if results.get('processed', 0) > 0:
        print("\nSuccessfully Retried Episodes:")
        for episode in results.get('episodes', []):
            if episode.get('status') == 'completed':
                print(f"  ✓ {episode.get('title', 'Unknown')}")
                print(f"    Output: {episode.get('output_file', 'N/A')}")
    
    if results.get('failed', 0) > 0:
        print("\nStill Failed Episodes:")
        for episode in results.get('episodes', []):
            if episode.get('status') == 'failed':
                print(f"  ✗ {episode.get('title', 'Unknown')}")
                print(f"    Error: {episode.get('error', 'Unknown error')}")
    
    print("="*60)
    
    # Return appropriate exit code
    if results.get('failed', 0) == 0:
        return 0
    else:
        return 1


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
    
    transcribe_parser.add_argument(
        '--retry-failed',
        action='store_true',
        help='Retry only failed episodes from previous runs'
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
    
    # Operational commands
    validate_parser = subparsers.add_parser(
        'validate-feed',
        help='Validate a podcast RSS feed'
    )
    validate_parser.add_argument(
        'feed_url',
        type=str,
        help='URL of the podcast RSS feed to validate'
    )
    validate_parser.add_argument(
        '--detailed',
        action='store_true',
        help='Show detailed validation information'
    )
    
    # Test API command
    test_api_parser = subparsers.add_parser(
        'test-api',
        help='Test API connectivity and quota status'
    )
    test_api_parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick test without making actual API calls'
    )
    
    # Show quota command
    quota_parser = subparsers.add_parser(
        'show-quota',
        help='Show current API quota usage across all keys'
    )
    quota_parser.add_argument(
        '--export-csv',
        type=str,
        help='Export quota data to CSV file'
    )
    quota_parser.add_argument(
        '--reset-usage',
        action='store_true',
        help='Reset usage counters (for testing only)'
    )
    
    # Health check command
    health_parser = subparsers.add_parser(
        'health',
        help='Run health check server for monitoring'
    )
    health_parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='Port for health check server (default: 8080)'
    )
    health_parser.add_argument(
        '--host',
        type=str,
        default='localhost',
        help='Host for health check server (default: localhost)'
    )
    health_parser.add_argument(
        '--daemon',
        action='store_true',
        help='Run as daemon process'
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
        
        # Handle retry failed episodes
        if args.retry_failed:
            return await _retry_failed_episodes(orchestrator, args)
        
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
            
            # Check for batch-level resume capability
            completed_episodes = len([
                ep for ep in orchestrator.progress_tracker.state.episodes.values()
                if ep.status.value == 'completed'
            ])
            failed_episodes = len([
                ep for ep in orchestrator.progress_tracker.state.episodes.values() 
                if ep.status.value == 'failed'
            ])
            
            if completed_episodes > 0 or failed_episodes > 0:
                logger.info(f"Found existing progress: {completed_episodes} completed, {failed_episodes} failed episodes")
                logger.info("Will skip already completed episodes and continue batch processing")
        
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


async def validate_feed_command(args: argparse.Namespace) -> int:
    """Execute the validate-feed command.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        from src.feed_parser import parse_feed
        
        print(f"\nValidating RSS feed: {args.feed_url}")
        print("=" * 60)
        
        # Parse the feed
        try:
            podcast_metadata, episodes = parse_feed(args.feed_url)
        except Exception as e:
            print(f"❌ Feed validation FAILED: {e}")
            return 1
        
        # Basic validation results
        print(f"✅ Feed parsed successfully")
        print(f"📝 Podcast: {podcast_metadata.title}")
        print(f"👤 Author: {podcast_metadata.author}")
        print(f"📅 Episodes found: {len(episodes)}")
        
        if not episodes:
            print("⚠️  Warning: No episodes found in feed")
            return 1
        
        # Detailed validation if requested
        if args.detailed:
            print("\n📊 DETAILED VALIDATION")
            print("-" * 40)
            
            # Metadata validation
            print(f"Description: {'✅' if podcast_metadata.description else '❌'} {len(podcast_metadata.description or '')} chars")
            print(f"Language: {'✅' if podcast_metadata.language else '❌'} {podcast_metadata.language or 'Not specified'}")
            print(f"Link: {'✅' if podcast_metadata.link else '❌'} {podcast_metadata.link or 'Not specified'}")
            
            # Episode validation
            valid_episodes = 0
            invalid_episodes = 0
            
            print(f"\n📋 Episode Analysis (showing first 10):")
            for i, episode in enumerate(episodes[:10]):
                status = "✅"
                issues = []
                
                if not episode.audio_url:
                    issues.append("no audio URL")
                    status = "❌"
                if not episode.title:
                    issues.append("no title")
                    status = "❌"
                if not episode.guid:
                    issues.append("no GUID")
                    status = "⚠️"
                
                if issues:
                    invalid_episodes += 1
                    print(f"  {i+1:2d}. {status} {episode.title[:50]}{'...' if len(episode.title) > 50 else ''}")
                    print(f"      Issues: {', '.join(issues)}")
                else:
                    valid_episodes += 1
                    print(f"  {i+1:2d}. {status} {episode.title[:50]}{'...' if len(episode.title) > 50 else ''}")
            
            if len(episodes) > 10:
                print(f"      ... and {len(episodes) - 10} more episodes")
            
            print(f"\n📈 Summary:")
            print(f"  Valid episodes: {len(episodes) - invalid_episodes}")
            print(f"  Episodes with issues: {invalid_episodes}")
            print(f"  Success rate: {((len(episodes) - invalid_episodes) / len(episodes) * 100):.1f}%")
        
        print("\n" + "=" * 60)
        
        if args.detailed and invalid_episodes > 0:
            print("⚠️  Some episodes have validation issues")
            return 1
        else:
            print("✅ Feed validation completed successfully")
            return 0
            
    except Exception as e:
        logger.error(f"Feed validation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


async def test_api_command(args: argparse.Namespace) -> int:
    """Execute the test-api command.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        from src.config import Config
        from src.gemini_client import create_gemini_client
        from src.key_rotation_manager import create_key_rotation_manager
        
        print("\n🔧 Testing API connectivity and quota status")
        print("=" * 60)
        
        # Initialize configuration
        config = Config()
        
        # Get available API keys
        api_keys = config.get_api_keys()
        if not api_keys:
            print("❌ No API keys found in environment")
            print("Please set GEMINI_API_KEY_1, GEMINI_API_KEY_2, etc.")
            return 1
        
        print(f"🔑 Found {len(api_keys)} API keys")
        
        # Test each key
        key_manager = create_key_rotation_manager()
        gemini_client = create_gemini_client(key_manager)
        
        print(f"📊 Quota status:")
        usage_summary = gemini_client.get_usage_summary()
        
        all_keys_healthy = True
        total_requests_available = 0
        total_tokens_available = 0
        
        for i, (key_name, usage_data) in enumerate(usage_summary.items(), 1):
            requests_used = usage_data['requests_today']
            tokens_used = usage_data['tokens_today']
            requests_remaining = usage_data.get('requests_remaining', 25 - requests_used)
            tokens_remaining = usage_data.get('tokens_remaining', 1000000 - tokens_used)
            
            status = "✅" if requests_remaining > 0 and tokens_remaining > 0 else "❌"
            if requests_remaining <= 0 or tokens_remaining <= 0:
                all_keys_healthy = False
            
            print(f"  Key {i}: {status}")
            print(f"    Requests: {requests_used}/25 used ({requests_remaining} remaining)")
            print(f"    Tokens: {tokens_used:,}/1,000,000 used ({tokens_remaining:,} remaining)")
            
            total_requests_available += max(0, requests_remaining)
            total_tokens_available += max(0, tokens_remaining)
        
        print(f"\n📈 Total capacity available:")
        print(f"  Requests: {total_requests_available}")
        print(f"  Tokens: {total_tokens_available:,}")
        
        # Quick test mode - skip actual API calls
        if args.quick:
            print("\n⚡ Quick test mode - skipping actual API calls")
            if all_keys_healthy:
                print("✅ All API keys appear healthy")
                return 0
            else:
                print("⚠️  Some API keys are at quota limits")
                return 1
        
        # Full test - make a simple API call
        print("\n🧪 Testing actual API connectivity...")
        
        try:
            # Make a simple test call with minimal token usage
            test_prompt = "Respond with just the word 'OK' if you can understand this message."
            
            import google.generativeai as genai
            genai.configure(api_key=api_keys[0])
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            response = await model.generate_content_async(test_prompt)
            
            if response and response.text:
                print("✅ API connectivity test successful")
                print(f"   Response: {response.text.strip()}")
            else:
                print("❌ API connectivity test failed - no response")
                return 1
                
        except Exception as e:
            print(f"❌ API connectivity test failed: {e}")
            return 1
        
        print("\n" + "=" * 60)
        
        if all_keys_healthy:
            print("✅ API test completed successfully - all systems operational")
            return 0
        else:
            print("⚠️  API test completed with warnings - some keys at quota limits")
            return 1
            
    except Exception as e:
        logger.error(f"API test failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def show_quota_command(args: argparse.Namespace) -> int:
    """Execute the show-quota command.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        from src.config import Config
        from src.gemini_client import create_gemini_client
        from src.key_rotation_manager import create_key_rotation_manager
        import csv
        from datetime import datetime
        
        print("\n📊 API Quota Usage Report")
        print("=" * 60)
        
        # Initialize components
        config = Config()
        key_manager = create_key_rotation_manager()
        gemini_client = create_gemini_client(key_manager)
        
        # Get usage data
        usage_summary = gemini_client.get_usage_summary()
        
        if not usage_summary:
            print("❌ No quota data available")
            return 1
        
        # Reset usage if requested (testing only)
        if args.reset_usage:
            print("⚠️  Resetting usage counters (TESTING ONLY)")
            for tracker in gemini_client.usage_trackers:
                tracker.reset_daily_usage()
            gemini_client._save_usage_state()
            print("✅ Usage counters reset")
            return 0
        
        # Display quota information
        quota_data = []
        total_requests_used = 0
        total_tokens_used = 0
        total_requests_available = 0
        total_tokens_available = 0
        
        print("Key Status                Requests         Tokens")
        print("-" * 60)
        
        for i, (key_name, usage_data) in enumerate(usage_summary.items(), 1):
            requests_used = usage_data['requests_today']
            tokens_used = usage_data['tokens_today']
            requests_remaining = usage_data.get('requests_remaining', 25 - requests_used)
            tokens_remaining = usage_data.get('tokens_remaining', 1000000 - tokens_used)
            
            # Determine status
            if requests_remaining <= 0 or tokens_remaining <= 0:
                status = "❌ QUOTA EXCEEDED"
            elif requests_used > 20 or tokens_used > 800000:
                status = "⚠️  NEAR LIMIT"
            else:
                status = "✅ HEALTHY"
            
            print(f"#{i:<2} {status:<15} {requests_used:>3}/{requests_remaining + requests_used:<3} ({requests_remaining:>2} left) {tokens_used:>7,}/{tokens_remaining + tokens_used:>7,} ({tokens_remaining:>7,} left)")
            
            # Track totals
            total_requests_used += requests_used
            total_tokens_used += tokens_used
            total_requests_available += requests_remaining
            total_tokens_available += tokens_remaining
            
            # Store for CSV export
            quota_data.append({
                'key_index': i,
                'status': status.replace('✅', 'HEALTHY').replace('⚠️', 'NEAR_LIMIT').replace('❌', 'QUOTA_EXCEEDED'),
                'requests_used': requests_used,
                'requests_total': requests_remaining + requests_used,
                'requests_remaining': requests_remaining,
                'tokens_used': tokens_used,
                'tokens_total': tokens_remaining + tokens_used,
                'tokens_remaining': tokens_remaining,
                'timestamp': datetime.now().isoformat()
            })
        
        print("-" * 60)
        print(f"TOTAL                    {total_requests_used:>3}/{total_requests_used + total_requests_available:<3} ({total_requests_available:>2} left) {total_tokens_used:>7,}/{total_tokens_used + total_tokens_available:>7,} ({total_tokens_available:>7,} left)")
        
        # Calculate estimated processing capacity
        print(f"\n📈 Estimated Processing Capacity:")
        # Rough estimate: 1 episode = 2 requests (transcribe + speakers), ~40k tokens for 30min episode
        estimated_episodes = min(
            total_requests_available // 2,
            total_tokens_available // 40000
        )
        print(f"   Episodes processable with current quota: ~{estimated_episodes}")
        
        if estimated_episodes == 0:
            print("   ⚠️  No episodes can be processed with current quota")
        elif estimated_episodes < 5:
            print("   ⚠️  Limited processing capacity remaining")
        
        # Export to CSV if requested
        if args.export_csv:
            try:
                with open(args.export_csv, 'w', newline='') as csvfile:
                    fieldnames = ['key_index', 'status', 'requests_used', 'requests_total', 'requests_remaining',
                                'tokens_used', 'tokens_total', 'tokens_remaining', 'timestamp']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    for row in quota_data:
                        writer.writerow(row)
                
                print(f"\n💾 Quota data exported to: {args.export_csv}")
            except Exception as e:
                print(f"❌ Failed to export CSV: {e}")
                return 1
        
        print("\n" + "=" * 60)
        
        if total_requests_available > 0 and total_tokens_available > 0:
            print("✅ Quota status: Ready for processing")
            return 0
        else:
            print("❌ Quota status: All keys exhausted")
            return 1
            
    except Exception as e:
        logger.error(f"Quota command failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def health_command(args: argparse.Namespace) -> int:
    """Execute the health check server command.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import json
        import threading
        import signal
        from src.config import Config
        from src.gemini_client import create_gemini_client
        from src.key_rotation_manager import create_key_rotation_manager
        
        # Global health check data
        health_data = {'status': 'unknown'}
        
        class HealthCheckHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/health' or self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    try:
                        # Get current health status
                        config = Config()
                        key_manager = create_key_rotation_manager()
                        gemini_client = create_gemini_client(key_manager)
                        
                        # Check API quota
                        usage_summary = gemini_client.get_usage_summary()
                        healthy_keys = 0
                        total_keys = len(usage_summary)
                        
                        for usage_data in usage_summary.values():
                            requests_remaining = usage_data.get('requests_remaining', 0)
                            tokens_remaining = usage_data.get('tokens_remaining', 0)
                            if requests_remaining > 0 and tokens_remaining > 0:
                                healthy_keys += 1
                        
                        # Determine overall health
                        if healthy_keys == 0:
                            status = "unhealthy"
                            message = "All API keys exhausted"
                        elif healthy_keys < total_keys:
                            status = "degraded" 
                            message = f"Only {healthy_keys}/{total_keys} API keys available"
                        else:
                            status = "healthy"
                            message = "All systems operational"
                        
                        response_data = {
                            'status': status,
                            'message': message,
                            'timestamp': datetime.now().isoformat(),
                            'api_keys': {
                                'total': total_keys,
                                'healthy': healthy_keys,
                                'exhausted': total_keys - healthy_keys
                            },
                            'quota': usage_summary
                        }
                        
                    except Exception as e:
                        response_data = {
                            'status': 'error',
                            'message': str(e),
                            'timestamp': datetime.now().isoformat()
                        }
                    
                    self.wfile.write(json.dumps(response_data, indent=2).encode())
                    
                elif self.path == '/metrics':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    
                    # Prometheus-style metrics
                    try:
                        config = Config()
                        key_manager = create_key_rotation_manager()
                        gemini_client = create_gemini_client(key_manager)
                        usage_summary = gemini_client.get_usage_summary()
                        
                        metrics = []
                        metrics.append("# HELP podcast_transcriber_api_requests_used API requests used today")
                        metrics.append("# TYPE podcast_transcriber_api_requests_used gauge")
                        
                        for i, usage_data in enumerate(usage_summary.values(), 1):
                            metrics.append(f'podcast_transcriber_api_requests_used{{key="{i}"}} {usage_data["requests_today"]}')
                        
                        metrics.append("# HELP podcast_transcriber_api_tokens_used API tokens used today")
                        metrics.append("# TYPE podcast_transcriber_api_tokens_used gauge")
                        
                        for i, usage_data in enumerate(usage_summary.values(), 1):
                            metrics.append(f'podcast_transcriber_api_tokens_used{{key="{i}"}} {usage_data["tokens_today"]}')
                        
                        self.wfile.write('\n'.join(metrics).encode())
                        
                    except Exception as e:
                        self.wfile.write(f"# Error generating metrics: {e}".encode())
                
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'Not Found')
            
            def log_message(self, format, *args):
                # Suppress default logging unless verbose
                if args.verbose:
                    super().log_message(format, *args)
        
        # Create and start server
        server = HTTPServer((args.host, args.port), HealthCheckHandler)
        
        print(f"\n🏥 Starting health check server on {args.host}:{args.port}")
        print("Available endpoints:")
        print(f"  http://{args.host}:{args.port}/health - JSON health status")
        print(f"  http://{args.host}:{args.port}/metrics - Prometheus metrics")
        print("\nPress Ctrl+C to stop the server")
        
        if args.daemon:
            print("Running in daemon mode...")
            # Simple daemon mode - run in background
            def signal_handler(sig, frame):
                print("\nShutting down health check server...")
                server.shutdown()
                sys.exit(0)
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down health check server...")
            server.shutdown()
        
        return 0
        
    except Exception as e:
        logger.error(f"Health check server failed: {e}")
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
    elif args.command == 'validate-feed':
        # Run feed validation command
        exit_code = asyncio.run(validate_feed_command(args))
    elif args.command == 'test-api':
        # Run API test command
        exit_code = asyncio.run(test_api_command(args))
    elif args.command == 'show-quota':
        # Run quota display command
        exit_code = show_quota_command(args)
    elif args.command == 'health':
        # Run health check server
        exit_code = health_command(args)
    else:
        logger.error(f"Unknown command: {args.command}")
        exit_code = 1
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()