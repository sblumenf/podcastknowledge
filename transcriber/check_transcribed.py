#!/usr/bin/env python3
"""Check which episodes have been transcribed."""

import json
from pathlib import Path
from datetime import datetime

def check_transcribed_episodes():
    """Check and list all transcribed episodes."""
    output_dir = Path("output/transcripts")
    
    if not output_dir.exists():
        print("No transcripts directory found.")
        return
    
    transcribed = []
    
    # Walk through all podcast directories
    for podcast_dir in output_dir.iterdir():
        if podcast_dir.is_dir():
            podcast_name = podcast_dir.name.replace('_', ' ')
            
            # Find all JSON files (which contain metadata)
            for json_file in podcast_dir.glob("*.json"):
                vtt_file = json_file.with_suffix('.vtt')
                
                # Load metadata from JSON
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                    
                    # Extract episode metadata from the structure
                    episode_data = data.get('episode', {})
                    transcription_data = data.get('transcription', {})
                    
                    episode_info = {
                        'podcast': episode_data.get('podcast_name', podcast_name),
                        'title': episode_data.get('title', json_file.stem),
                        'date': episode_data.get('published_date', 'Unknown'),
                        'duration': episode_data.get('duration', 'Unknown'),
                        'youtube_url': episode_data.get('youtube_url', 'Not found'),
                        'transcribed_at': transcription_data.get('transcribed_at', 'Unknown'),
                        'word_count': transcription_data.get('word_count', 0),
                        'json_path': str(json_file),
                        'vtt_path': str(vtt_file),
                        'vtt_exists': vtt_file.exists()
                    }
                    
                    transcribed.append(episode_info)
                except Exception as e:
                    print(f"Error reading {json_file}: {e}")
    
    # Sort by date
    transcribed.sort(key=lambda x: x['date'])
    
    # Display results
    print(f"\nTotal transcribed episodes: {len(transcribed)}")
    print("=" * 80)
    
    for ep in transcribed:
        print(f"\nPodcast: {ep['podcast']}")
        print(f"Episode: {ep['title']}")
        print(f"Published: {ep['date']}")
        print(f"Duration: {ep['duration']}")
        print(f"Transcribed: {ep['transcribed_at']}")
        print(f"Word Count: {ep['word_count']:,}")
        print(f"YouTube: {ep['youtube_url']}")
        print(f"VTT: {'✓' if ep['vtt_exists'] else '✗'} {ep['vtt_path']}")
        print("-" * 80)

if __name__ == "__main__":
    check_transcribed_episodes()