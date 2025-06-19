#!/usr/bin/env python3
"""Test script for speaker sanity check enhancements."""

import sys
sys.path.append('/home/sergeblumenfeld/podcastknowledge/seeding_pipeline')

from src.storage.graph_storage import GraphStorageService
from src.services.llm import LLMService
from src.core.config import PipelineConfig
from src.post_processing.speaker_mapper import SpeakerMapper
from src.utils.logging import setup_logging

def test_speaker_sanity_checks():
    """Test the enhanced speaker mapper with sanity checks."""
    # Setup
    setup_logging()
    config = PipelineConfig()
    
    # Initialize services
    print("Initializing services...")
    storage = GraphStorageService(
        config.neo4j_uri,
        config.neo4j_username,
        config.neo4j_password
    )
    llm_service = LLMService(config)
    speaker_mapper = SpeakerMapper(storage, llm_service, config)
    
    # Select a test episode - one we know has issues
    test_episode_id = "The_Mel_Robbins_Podcast_2_Ways_to_Take_Your_Power_Back_When_You_Feel_Insecure_2025-06-18T23:06:48.626679"
    
    print(f"\nTesting speaker sanity checks on episode:")
    print(f"  {test_episode_id[:80]}...")
    
    # First, let's check current speakers
    print("\nCurrent speakers in episode:")
    query = """
    MATCH (mu:MeaningfulUnit)-[:PART_OF]->(e:Episode {id: $episode_id})
    WHERE mu.speaker_distribution IS NOT NULL
    WITH DISTINCT mu.speaker_distribution as dist
    UNWIND dist as speaker_dist
    RETURN speaker_dist
    LIMIT 20
    """
    
    result = storage.query(query, {"episode_id": test_episode_id})
    
    import json
    all_speakers = set()
    for record in result:
        dist = record['speaker_dist']
        try:
            if isinstance(dist, str):
                speakers = json.loads(dist)
            else:
                speakers = dist
            all_speakers.update(speakers.keys())
        except:
            pass
    
    for i, speaker in enumerate(sorted(all_speakers), 1):
        print(f"  {i}. {speaker}")
    
    # Test individual sanity check functions
    print("\n\nTesting individual sanity check functions:")
    
    # Test non-name filter
    test_names = ["you know what", "Mel Robbins", "um", "Dr. Smith", "yeah", "Brief Family Member"]
    print("\n1. Non-name filter test:")
    for name in test_names:
        is_valid = speaker_mapper._is_valid_speaker_name(name)
        print(f"   '{name}' -> {'VALID' if is_valid else 'INVALID'}")
    
    # Test duplicate detection
    print("\n2. Duplicate detection test:")
    test_speakers = [
        "Brief Family Member",
        "Mel Robbins' Son (Introducer)",
        "Mel Robbins (Host)",
        "Guest/Contributor"
    ]
    duplicates = speaker_mapper._find_duplicate_speakers(test_speakers)
    if duplicates:
        for old, new in duplicates.items():
            print(f"   '{old}' -> '{new}' (DUPLICATE)")
    else:
        print("   No duplicates found")
    
    # Test value contribution check
    print("\n3. Value contribution check test:")
    for speaker in ["Mel Robbins (Host)", "Brief Family Member", "you know what"]:
        if speaker in all_speakers:
            has_value = speaker_mapper._has_meaningful_contribution(test_episode_id, speaker)
            print(f"   '{speaker}' -> {'HAS VALUE' if has_value else 'LOW VALUE'}")
    
    # Now run the full process_episode with sanity checks
    print("\n\nRunning full speaker mapping with sanity checks...")
    print("=" * 60)
    
    try:
        mappings = speaker_mapper.process_episode(test_episode_id)
        
        print(f"\nFinal mappings applied: {len(mappings)}")
        for old_name, new_name in mappings.items():
            print(f"   '{old_name}' -> '{new_name}'")
            
    except Exception as e:
        print(f"Error during processing: {e}")
        import traceback
        traceback.print_exc()
    
    # Check final state
    print("\n\nFinal speakers in episode after sanity checks:")
    result = storage.query(query, {"episode_id": test_episode_id})
    
    final_speakers = set()
    for record in result:
        dist = record['speaker_dist']
        try:
            if isinstance(dist, str):
                speakers = json.loads(dist)
            else:
                speakers = dist
            final_speakers.update(speakers.keys())
        except:
            pass
    
    for i, speaker in enumerate(sorted(final_speakers), 1):
        print(f"  {i}. {speaker}")
    
    # Summary
    print("\n\nSummary:")
    print(f"  Original speakers: {len(all_speakers)}")
    print(f"  Final speakers: {len(final_speakers)}")
    print(f"  Speakers removed/merged: {len(all_speakers) - len(final_speakers)}")
    
    # Close resources
    storage.close()

if __name__ == "__main__":
    test_speaker_sanity_checks()