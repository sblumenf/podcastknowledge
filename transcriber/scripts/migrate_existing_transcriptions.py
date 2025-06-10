#!/usr/bin/env python3
"""Migration script to build progress tracking from existing transcriptions.

This script scans the output directory for existing VTT files and
creates an initial progress tracking file based on what's already been
transcribed.
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.progress_tracker import ProgressTracker
from src.utils.logging import setup_logging, get_logger

logger = get_logger(__name__)


def extract_episode_info(vtt_path: Path) -> tuple[str, str]:
    """Extract episode title and date from VTT filename.
    
    Expected format: YYYY-MM-DD_Episode_Title.vtt
    
    Args:
        vtt_path: Path to VTT file
        
    Returns:
        Tuple of (episode_title, date_string)
    """
    filename = vtt_path.stem  # Remove .vtt extension
    
    # Try to extract date from beginning of filename
    date_pattern = r'^(\d{4}-\d{2}-\d{2})_(.+)$'
    match = re.match(date_pattern, filename)
    
    if match:
        date_str = match.group(1)
        episode_title = match.group(2).replace('_', ' ')
    else:
        # No date in filename, use file modification time
        date_str = datetime.fromtimestamp(vtt_path.stat().st_mtime).strftime('%Y-%m-%d')
        episode_title = filename.replace('_', ' ')
    
    return episode_title, date_str


def scan_output_directory(output_dir: Path) -> dict[str, list[tuple[str, str]]]:
    """Scan output directory for existing VTT files.
    
    Args:
        output_dir: Base output directory containing podcast folders
        
    Returns:
        Dictionary mapping podcast names to list of (episode_title, date) tuples
    """
    transcriptions = {}
    
    if not output_dir.exists():
        logger.warning(f"Output directory does not exist: {output_dir}")
        return transcriptions
    
    # Look for VTT files in subdirectories
    for podcast_dir in output_dir.iterdir():
        if not podcast_dir.is_dir():
            continue
            
        podcast_name = podcast_dir.name.replace('_', ' ')
        vtt_files = list(podcast_dir.glob('*.vtt'))
        
        if vtt_files:
            logger.info(f"Found {len(vtt_files)} VTT files for podcast: {podcast_name}")
            episodes = []
            
            for vtt_file in vtt_files:
                try:
                    episode_title, date_str = extract_episode_info(vtt_file)
                    episodes.append((episode_title, date_str))
                    logger.debug(f"  - {episode_title} ({date_str})")
                except Exception as e:
                    logger.warning(f"Error processing {vtt_file}: {e}")
            
            if episodes:
                transcriptions[podcast_name] = episodes
    
    return transcriptions


def migrate_to_progress_tracker(transcriptions: dict[str, list[tuple[str, str]]], 
                               progress_file: str) -> None:
    """Migrate existing transcriptions to progress tracker format.
    
    Args:
        transcriptions: Dictionary of podcast -> episode info
        progress_file: Path to progress tracking file
    """
    # Initialize progress tracker
    tracker = ProgressTracker(progress_file)
    
    # Clear any existing data (in case of re-run)
    existing_podcasts = tracker.get_all_podcasts()
    for podcast in existing_podcasts:
        tracker.clear_podcast(podcast)
    
    # Add all transcriptions
    total_episodes = 0
    for podcast_name, episodes in transcriptions.items():
        logger.info(f"Migrating {len(episodes)} episodes for {podcast_name}")
        
        for episode_title, date_str in episodes:
            tracker.mark_episode_transcribed(podcast_name, episode_title, date_str)
            total_episodes += 1
    
    logger.info(f"Migration complete: {total_episodes} episodes across {len(transcriptions)} podcasts")


def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(
        description='Migrate existing transcriptions to progress tracking system'
    )
    parser.add_argument(
        '--output-dir',
        default=os.getenv('TRANSCRIPT_OUTPUT_DIR', 'output/transcripts'),
        help='Directory containing existing VTT files'
    )
    parser.add_argument(
        '--progress-file',
        default='data/transcribed_episodes.json',
        help='Path to progress tracking file'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without making changes'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    import logging
    setup_logging(log_level=logging.DEBUG if args.verbose else logging.INFO)
    
    # Scan for existing transcriptions
    output_dir = Path(args.output_dir)
    logger.info(f"Scanning output directory: {output_dir}")
    
    transcriptions = scan_output_directory(output_dir)
    
    if not transcriptions:
        logger.info("No existing transcriptions found")
        return 0
    
    # Display summary
    total_episodes = sum(len(episodes) for episodes in transcriptions.values())
    print(f"\nFound existing transcriptions:")
    print(f"  Podcasts: {len(transcriptions)}")
    print(f"  Total episodes: {total_episodes}")
    print()
    
    for podcast_name in sorted(transcriptions.keys()):
        episodes = transcriptions[podcast_name]
        print(f"  {podcast_name}: {len(episodes)} episodes")
    
    if args.dry_run:
        print("\nDry run mode - no changes made")
        return 0
    
    # Perform migration
    print(f"\nMigrating to progress file: {args.progress_file}")
    migrate_to_progress_tracker(transcriptions, args.progress_file)
    
    print("\nMigration complete!")
    print(f"Progress tracking file created: {args.progress_file}")
    print("\nYou can now use the transcription system and it will skip these episodes.")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())