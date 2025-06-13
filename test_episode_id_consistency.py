#!/usr/bin/env python3
"""Test that episode ID generation is consistent across modules."""

import sys
from pathlib import Path

# Add repository root to path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

# Test imports
print("Testing episode ID consistency...\n")

# Import from shared module
from shared import generate_episode_id as shared_generate_id

# Import from seeding_pipeline
from seeding_pipeline.src.tracking import generate_episode_id as seeding_generate_id

# Test cases
test_cases = [
    ("2024-01-15_Episode_Title_Here.vtt", "test_podcast"),
    ("2024-12-20_The_AI_Revolution.vtt", "tech_talk"),
    ("2024_06_15_Machine_Learning_101.vtt", "data_science"),
    ("20240815_Special_Episode.vtt", "my_show"),
    ("Episode_Without_Date.vtt", "podcast_name"),
    ("Complex Title: Part 1 - The Beginning!.vtt", "show"),
]

print("Testing episode ID generation consistency:")
print("-" * 60)

all_match = True
for filename, podcast_id in test_cases:
    shared_id = shared_generate_id(filename, podcast_id)
    seeding_id = seeding_generate_id(filename, podcast_id)
    
    match = shared_id == seeding_id
    all_match = all_match and match
    
    status = "✓" if match else "✗"
    print(f"{status} {filename}")
    print(f"  Podcast: {podcast_id}")
    print(f"  Shared:  {shared_id}")
    print(f"  Seeding: {seeding_id}")
    if not match:
        print(f"  MISMATCH!")
    print()

# Test that transcriber uses consistent title normalization
print("\nTesting transcriber title normalization:")
print("-" * 60)

from transcriber.src.utils.title_utils import normalize_title, make_filename_safe

test_titles = [
    "Episode: Part 1",
    "The AI Revolution!",
    "Machine Learning & Data Science",
    "Complex / Title / With / Slashes",
]

for title in test_titles:
    normalized = normalize_title(title)
    safe = make_filename_safe(normalized)
    
    # Create a filename
    filename = f"2024-01-01_{safe}.vtt"
    episode_id = shared_generate_id(filename, "test")
    
    print(f"Original:   {title}")
    print(f"Normalized: {normalized}")
    print(f"Safe:       {safe}")
    print(f"Episode ID: {episode_id}")
    print()

# Summary
print("-" * 60)
if all_match:
    print("✓ All episode IDs match! Consistency achieved.")
else:
    print("✗ Episode ID mismatch detected. Need to fix implementation.")

# Cleanup
Path(__file__).unlink()