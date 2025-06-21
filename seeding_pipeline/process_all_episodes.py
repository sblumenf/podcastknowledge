#!/usr/bin/env python3
"""Process all Mel Robbins podcast episodes."""

import subprocess
import sys
from pathlib import Path
import re

# Episodes to process
episodes_dir = Path("/home/sergeblumenfeld/podcastknowledge/transcriber/output/transcripts/The_Mel_Robbins_Podcast")
episodes = list(episodes_dir.glob("*.vtt"))

print(f"Found {len(episodes)} episodes to process\n")

for i, episode_path in enumerate(episodes, 1):
    # Extract title from filename (remove date prefix and .vtt extension)
    filename = episode_path.stem
    # Remove date prefix (YYYY-MM-DD_)
    title_match = re.match(r'\d{4}-\d{2}-\d{2}_(.+)', filename)
    if title_match:
        title = title_match.group(1).replace('_', ' ')
    else:
        title = filename.replace('_', ' ')
    
    print(f"\n{'='*60}")
    print(f"Processing episode {i}/{len(episodes)}")
    print(f"File: {episode_path.name}")
    print(f"Title: {title}")
    print(f"{'='*60}\n")
    
    # Run the pipeline
    cmd = [
        "python3", "main.py",
        str(episode_path),
        "--podcast", "The Mel Robbins Podcast",
        "--title", title,
        "--timeout", "3600"  # 1 hour timeout per episode
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Successfully processed: {title}")
        else:
            print(f"✗ Error processing: {title}")
            print(f"Error output: {result.stderr}")
    except Exception as e:
        print(f"✗ Exception processing {title}: {e}")

print(f"\n{'='*60}")
print("Processing complete!")
print(f"{'='*60}")