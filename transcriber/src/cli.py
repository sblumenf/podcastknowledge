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

logger = get_logger('cli')


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.
    
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
    args = parser.parse_args()
    
    # Show help if no command provided
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    return args


async def transcribe_command(args: argparse.Namespace) -> int:
    """Execute the transcribe command.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
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
        
        # Display results
        print("\n" + "="*60)
        print("TRANSCRIPTION SUMMARY")
        print("="*60)
        print(f"Status: {results['status']}")
        print(f"Episodes processed: {results['processed']}")
        print(f"Episodes failed: {results['failed']}")
        print(f"Episodes skipped: {results['skipped']}")
        
        if results['processed'] > 0:
            print("\nProcessed Episodes:")
            for episode in results['episodes']:
                if episode['status'] == 'completed':
                    print(f"  ✓ {episode['title']}")
                    print(f"    Output: {episode['output_file']}")
                    if episode.get('speakers'):
                        print(f"    Speakers: {', '.join(episode['speakers'])}")
        
        if results['failed'] > 0:
            print("\nFailed Episodes:")
            for episode in results['episodes']:
                if episode['status'] == 'failed':
                    print(f"  ✗ {episode['title']}")
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
        if results['status'] == 'completed' and results['failed'] == 0:
            return 0
        elif results['status'] == 'quota_reached':
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
    else:
        logger.error(f"Unknown command: {args.command}")
        exit_code = 1
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()