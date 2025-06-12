"""Simplified Command Line Interface for Podcast Transcription with Deepgram.

This module provides a streamlined CLI for transcribing podcast episodes
from RSS feeds using Deepgram's transcription service.
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Optional, List
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from src.simple_orchestrator import SimpleOrchestrator
from src.feed_parser import parse_feed, validate_feed_url
from src.utils.logging import setup_logging, get_logger
from src.progress_tracker import ProgressTracker

logger = get_logger('cli')


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog='podcast-transcriber',
        description='Transcribe podcast episodes using Deepgram',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s transcribe --feed-url https://example.com/podcast.rss
  %(prog)s transcribe --feed-url https://example.com/podcast.rss --max-episodes 5
  %(prog)s validate-feed --feed-url https://example.com/podcast.rss
        """
    )
    
    # Global arguments
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    # Create subcommands
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
        required=True
    )
    
    # Transcribe command
    transcribe_parser = subparsers.add_parser(
        'transcribe',
        help='Transcribe podcast episodes from RSS feed'
    )
    transcribe_parser.add_argument(
        '--feed-url',
        required=True,
        help='URL of the podcast RSS feed'
    )
    transcribe_parser.add_argument(
        '--output-dir',
        help='Directory for output VTT files (overrides TRANSCRIPT_OUTPUT_DIR)'
    )
    transcribe_parser.add_argument(
        '--max-episodes',
        type=int,
        metavar='N',
        help='Maximum number of episodes to process'
    )
    transcribe_parser.add_argument(
        '--mock',
        action='store_true',
        help='Use mock Deepgram responses for testing'
    )
    transcribe_parser.add_argument(
        '--first-non-trailer',
        action='store_true',
        help='Transcribe only the first non-trailer episode'
    )
    transcribe_parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-transcription of episodes even if already transcribed'
    )
    
    # Transcribe-single command (alias for common use case)
    transcribe_single_parser = subparsers.add_parser(
        'transcribe-single',
        help='Transcribe a single episode from RSS feed'
    )
    transcribe_single_parser.add_argument(
        'feed_url',
        help='URL of the podcast RSS feed'
    )
    transcribe_single_parser.add_argument(
        '--first-non-trailer',
        action='store_true',
        help='Skip trailer episodes and transcribe the first regular episode'
    )
    transcribe_single_parser.add_argument(
        '--output-dir',
        help='Directory for output VTT files (overrides TRANSCRIPT_OUTPUT_DIR)'
    )
    transcribe_single_parser.add_argument(
        '--mock',
        action='store_true',
        help='Use mock Deepgram responses for testing'
    )
    transcribe_single_parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-transcription of episodes even if already transcribed'
    )
    
    # Validate feed command
    validate_parser = subparsers.add_parser(
        'validate-feed',
        help='Validate RSS feed and show episode list'
    )
    validate_parser.add_argument(
        '--feed-url',
        required=True,
        help='URL of the podcast RSS feed to validate'
    )
    
    # Status command
    status_parser = subparsers.add_parser(
        'status',
        help='Show transcription progress status'
    )
    status_parser.add_argument(
        '--podcast',
        help='Show status for specific podcast only'
    )
    
    return parser.parse_args()


def cmd_transcribe(args: argparse.Namespace) -> int:
    """Handle the transcribe command.
    
    Args:
        args: Parsed command line arguments.
        
    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    # Validate feed URL
    if not validate_feed_url(args.feed_url):
        logger.error(f"Invalid feed URL: {args.feed_url}")
        return 1
    
    # Parse RSS feed
    try:
        logger.info(f"Parsing RSS feed: {args.feed_url}")
        podcast_metadata, episodes = parse_feed(args.feed_url)
        logger.info(f"Found {len(episodes)} episodes in feed: {podcast_metadata.title}")
    except Exception as e:
        logger.error(f"Failed to parse feed: {e}")
        return 1
    
    # Filter out trailers if requested
    if hasattr(args, 'first_non_trailer') and args.first_non_trailer:
        # Filter out episodes with "trailer" in the title (case-insensitive)
        non_trailer_episodes = [ep for ep in episodes if 'trailer' not in ep.title.lower()]
        if non_trailer_episodes:
            episodes = non_trailer_episodes[:1]
            logger.info(f"Selected first non-trailer episode: {episodes[0].title}")
        else:
            logger.warning("No non-trailer episodes found")
            episodes = episodes[:1] if episodes else []
    
    # Limit episodes if requested
    elif args.max_episodes and args.max_episodes > 0:
        episodes = episodes[:args.max_episodes]
        logger.info(f"Processing first {len(episodes)} episodes")
    
    if not episodes:
        logger.warning("No episodes found to process")
        return 0
    
    # Initialize orchestrator
    orchestrator = SimpleOrchestrator(
        output_dir=args.output_dir,
        mock_enabled=args.mock,
        force_reprocess=getattr(args, 'force', False)
    )
    
    # Add podcast name to episodes for file organization
    for episode in episodes:
        episode.podcast_name = podcast_metadata.title
    
    # Process episodes
    print(f"\nTranscribing {len(episodes)} episodes from {podcast_metadata.title}")
    print("=" * 60)
    
    results = orchestrator.process_episodes(episodes)
    
    # Display summary
    summary = orchestrator.generate_summary_report(results)
    print(summary)
    
    # Return non-zero if any episodes failed
    return 1 if results['failed'] > 0 else 0


def cmd_validate_feed(args: argparse.Namespace) -> int:
    """Handle the validate-feed command.
    
    Args:
        args: Parsed command line arguments.
        
    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    # Validate feed URL
    if not validate_feed_url(args.feed_url):
        print(f"Invalid feed URL: {args.feed_url}")
        return 1
    
    # Parse RSS feed
    try:
        podcast_metadata, episodes = parse_feed(args.feed_url)
    except Exception as e:
        print(f"Failed to parse feed: {e}")
        return 1
    
    # Display podcast information
    print(f"\nPodcast: {podcast_metadata.title}")
    print(f"Description: {podcast_metadata.description[:100]}..." if podcast_metadata.description else "No description")
    print(f"Author: {podcast_metadata.author or 'Unknown'}")
    print(f"Language: {podcast_metadata.language or 'Unknown'}")
    print(f"Total episodes: {len(episodes)}")
    
    # Display recent episodes
    print("\nRecent episodes:")
    for i, episode in enumerate(episodes[:10], 1):
        pub_date = episode.published_date.strftime('%Y-%m-%d') if episode.published_date else 'No date'
        duration = episode.duration or 'Unknown duration'
        print(f"{i:2d}. {episode.title}")
        print(f"    Published: {pub_date}, Duration: {duration}")
        if episode.description:
            desc = episode.description[:80].replace('\n', ' ')
            print(f"    {desc}...")
    
    if len(episodes) > 10:
        print(f"\n... and {len(episodes) - 10} more episodes")
    
    return 0


def cmd_transcribe_single(args: argparse.Namespace) -> int:
    """Handle the transcribe-single command.
    
    This is a convenience wrapper around transcribe for single episodes.
    
    Args:
        args: Parsed command line arguments.
        
    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    # Convert to transcribe command format
    args.feed_url = args.feed_url
    args.max_episodes = 1 if not args.first_non_trailer else None
    return cmd_transcribe(args)


def cmd_status(args: argparse.Namespace) -> int:
    """Handle the status command to show transcription progress.
    
    Args:
        args: Parsed command line arguments.
        
    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    # Initialize progress tracker
    progress_tracker = ProgressTracker()
    
    # Get all podcasts or specific one
    if args.podcast:
        podcasts = [args.podcast] if args.podcast in progress_tracker.get_all_podcasts() else []
        if not podcasts:
            print(f"No transcription data found for podcast: {args.podcast}")
            return 1
    else:
        podcasts = progress_tracker.get_all_podcasts()
    
    if not podcasts:
        print("No transcribed episodes found.")
        return 0
    
    # Display progress
    total_transcribed = progress_tracker.get_total_transcribed_count()
    print(f"\nTranscription Progress Status")
    print("=" * 60)
    print(f"Total episodes transcribed: {total_transcribed}")
    print(f"Total podcasts: {len(podcasts)}")
    print()
    
    # Show details for each podcast
    for podcast_name in sorted(podcasts):
        episodes = progress_tracker.get_transcribed_episodes(podcast_name)
        print(f"\n{podcast_name}:")
        print(f"  Episodes transcribed: {len(episodes)}")
        
        # Show first few episodes
        if len(episodes) <= 5:
            for episode in episodes:
                print(f"    - {episode}")
        else:
            # Show first 3 and last 2
            for episode in episodes[:3]:
                print(f"    - {episode}")
            print(f"    ... and {len(episodes) - 5} more episodes ...")
            for episode in episodes[-2:]:
                print(f"    - {episode}")
    
    print("\n" + "=" * 60)
    print(f"Progress file: {progress_tracker.tracking_file_path}")
    
    return 0


def main() -> int:
    """Main entry point for the CLI."""
    # Parse arguments
    args = parse_arguments()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(log_level=log_level)
    
    # Route to appropriate command handler
    if args.command == 'transcribe':
        return cmd_transcribe(args)
    elif args.command == 'transcribe-single':
        return cmd_transcribe_single(args)
    elif args.command == 'validate-feed':
        return cmd_validate_feed(args)
    elif args.command == 'status':
        return cmd_status(args)
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1


if __name__ == '__main__':
    sys.exit(main())