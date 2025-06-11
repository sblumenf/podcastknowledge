#!/usr/bin/env python3
"""Find the next episodes to transcribe based on what's already done."""

import json
from pathlib import Path
from datetime import datetime
from src.feed_parser import parse_feed
from src.utils.logging import setup_logging
from src.progress_tracker import ProgressTracker

def get_transcribed_episodes():
    """Get list of already transcribed episode titles."""
    # First check the progress tracker
    progress_tracker = ProgressTracker()
    transcribed = set()
    
    # Get all episodes from progress tracker
    for podcast_name in progress_tracker.get_all_podcasts():
        episodes = progress_tracker.get_transcribed_episodes(podcast_name)
        transcribed.update(episodes)
    
    # Also check filesystem as backup (for VTT files not in tracker)
    output_dir = Path("output/transcripts")
    if output_dir.exists():
        for podcast_dir in output_dir.iterdir():
            if podcast_dir.is_dir():
                # Check for VTT files
                for vtt_file in podcast_dir.glob("*.vtt"):
                    # Extract title from filename (format: YYYY-MM-DD_Title.vtt)
                    filename = vtt_file.stem
                    if '_' in filename:
                        # Split on first underscore to separate date from title
                        parts = filename.split('_', 1)
                        if len(parts) == 2:
                            title = parts[1].replace('_', ' ').replace('&amp;', '&')
                            transcribed.add(title)
    
    return transcribed

def find_next_episodes_to_transcribe(feed_url, count=3):
    """Find the next N episodes to transcribe."""
    # Get already transcribed episodes
    transcribed = get_transcribed_episodes()
    print(f"Already transcribed episodes: {len(transcribed)}")
    for title in transcribed:
        print(f"  - {title}")
    
    # Parse feed
    print(f"\nParsing feed: {feed_url}")
    podcast_metadata, episodes = parse_feed(feed_url)
    print(f"Total episodes in feed: {len(episodes)}")
    
    # Filter out trailers and already transcribed
    non_trailer_episodes = []
    for ep in episodes:
        if 'trailer' not in ep.title.lower() and ep.title not in transcribed:
            non_trailer_episodes.append(ep)
    
    print(f"Non-trailer, not-yet-transcribed episodes: {len(non_trailer_episodes)}")
    
    # Sort by date (oldest first)
    sorted_episodes = sorted(non_trailer_episodes, key=lambda x: x.published_date)
    
    # Get the next N episodes
    next_episodes = sorted_episodes[:count]
    
    print(f"\nNext {count} episodes to transcribe (oldest first):")
    print("=" * 80)
    
    for i, ep in enumerate(next_episodes, 1):
        print(f"\n{i}. {ep.title}")
        print(f"   Published: {ep.published_date}")
        print(f"   Duration: {ep.duration}")
        print(f"   Audio URL: {ep.audio_url[:100]}...")
    
    return next_episodes

def main():
    setup_logging()
    feed_url = "https://feeds.simplecast.com/UCwaTX1J"
    
    # Find next 3 episodes
    next_episodes = find_next_episodes_to_transcribe(feed_url, count=3)
    
    print(f"\n\nTo transcribe these episodes, you could run:")
    print("python3 -m src.cli transcribe --feed-url https://feeds.simplecast.com/UCwaTX1J --max-episodes 4")
    print("(This would process 4 episodes starting from the newest, but skip the already transcribed one)")

if __name__ == "__main__":
    main()