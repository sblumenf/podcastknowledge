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
    
    # Limit episodes if requested
    if args.max_episodes and args.max_episodes > 0:
        episodes = episodes[:args.max_episodes]
        logger.info(f"Processing first {len(episodes)} episodes")
    
    if not episodes:
        logger.warning("No episodes found to process")
        return 0
    
    # Initialize orchestrator
    orchestrator = SimpleOrchestrator(
        output_dir=args.output_dir,
        mock_enabled=args.mock
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
    elif args.command == 'validate-feed':
        return cmd_validate_feed(args)
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1


if __name__ == '__main__':
    sys.exit(main())