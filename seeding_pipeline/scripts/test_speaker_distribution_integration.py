#!/usr/bin/env python3
"""Integration test for speaker_distribution storage in MeaningfulUnits."""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.graph_storage import GraphStorageService
from src.core.config import Config
from src.services.segment_regrouper import MeaningfulUnit
from src.core.interfaces import TranscriptSegment


def create_test_meaningful_unit():
    """Create a test MeaningfulUnit with speaker_distribution."""
    
    # Create test segments with different speakers
    segments = [
        TranscriptSegment(
            id="seg_001",
            text="Hello everyone, welcome to the show.",
            start_time=0.0,
            end_time=3.0,
            speaker="Host"
        ),
        TranscriptSegment(
            id="seg_002",
            text="Thanks for having me on the show.",
            start_time=3.0,
            end_time=5.0,
            speaker="Guest"
        ),
        TranscriptSegment(
            id="seg_003",
            text="Let's talk about the topic today.",
            start_time=5.0,
            end_time=8.0,
            speaker="Host"
        ),
        TranscriptSegment(
            id="seg_004",
            text="I'm excited to share my insights.",
            start_time=8.0,
            end_time=10.0,
            speaker="Guest"
        )
    ]
    
    # Create MeaningfulUnit with speaker_distribution
    unit = MeaningfulUnit(
        id=f"test_unit_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        segments=segments,
        unit_type="topic_discussion",
        summary="Test unit for speaker distribution verification",
        themes=["testing", "verification"],
        start_time=0.0,
        end_time=10.0,
        primary_speaker="Host",
        speaker_distribution={
            "Host": 60.0,  # 6 seconds out of 10
            "Guest": 40.0  # 4 seconds out of 10
        },
        is_complete=True,
        metadata={"test": True}
    )
    
    return unit


def test_speaker_distribution_storage():
    """Test that speaker_distribution is correctly stored and retrieved."""
    
    # Initialize configuration
    config = Config()
    
    # Initialize graph storage
    graph_storage = GraphStorageService(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password,
        database=config.neo4j_database
    )
    
    try:
        # Connect to Neo4j
        graph_storage.connect()
        print("✓ Connected to Neo4j")
        
        # Create test episode
        test_episode_id = f"test_episode_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        episode_metadata = {
            'episode_id': test_episode_id,
            'title': 'Test Episode for Speaker Distribution',
            'description': 'Testing speaker distribution storage',
            'published_date': datetime.now().isoformat(),
            'youtube_url': 'https://youtube.com/test',
            'vtt_path': '/test/path.vtt'
        }
        
        # Create episode
        episode_id = graph_storage.create_episode(episode_metadata)
        print(f"✓ Created test episode: {episode_id}")
        
        # Create test MeaningfulUnit
        unit = create_test_meaningful_unit()
        
        # Prepare unit data for storage (mimicking unified_pipeline.py)
        unit_data = {
            'id': unit.id,
            'text': unit.text,
            'start_time': unit.start_time,
            'end_time': unit.end_time,
            'summary': unit.summary,
            'primary_speaker': unit.primary_speaker,
            'speaker_distribution': unit.speaker_distribution,  # This should now be included
            'unit_type': unit.unit_type,
            'themes': unit.themes,
            'segment_indices': [seg.start_time for seg in unit.segments],
            'is_complete': unit.is_complete,
            'metadata': unit.metadata or {}
        }
        
        # Store the unit
        unit_id = graph_storage.create_meaningful_unit(
            unit_data=unit_data,
            episode_id=episode_id
        )
        print(f"✓ Created MeaningfulUnit: {unit_id}")
        
        # Query to retrieve and verify
        query = """
        MATCH (m:MeaningfulUnit {id: $unit_id})
        RETURN m.id AS id, 
               m.primary_speaker AS primary_speaker,
               m.speaker_distribution AS speaker_distribution,
               m.summary AS summary
        """
        
        results = graph_storage.query(query, parameters={'unit_id': unit_id})
        
        if results:
            result = results[0]
            print("\n✓ Successfully retrieved MeaningfulUnit:")
            print(f"  ID: {result['id']}")
            print(f"  Summary: {result['summary']}")
            print(f"  Primary Speaker: {result['primary_speaker']}")
            
            if result['speaker_distribution']:
                try:
                    speaker_dist = json.loads(result['speaker_distribution'])
                    print("  Speaker Distribution:")
                    for speaker, percentage in speaker_dist.items():
                        print(f"    - {speaker}: {percentage}%")
                    
                    # Verify the values match what we stored
                    if speaker_dist == unit.speaker_distribution:
                        print("\n✅ Speaker distribution stored and retrieved correctly!")
                    else:
                        print("\n❌ Speaker distribution mismatch!")
                        print(f"   Expected: {unit.speaker_distribution}")
                        print(f"   Got: {speaker_dist}")
                        
                except json.JSONDecodeError as e:
                    print(f"\n❌ Failed to parse speaker_distribution JSON: {e}")
                    print(f"   Raw value: {result['speaker_distribution']}")
            else:
                print("\n❌ Speaker distribution not found in retrieved data!")
        else:
            print("\n❌ Failed to retrieve the created MeaningfulUnit!")
            
        # Clean up test data
        cleanup_query = """
        MATCH (e:Episode {id: $episode_id})
        OPTIONAL MATCH (e)<-[:PART_OF]-(m:MeaningfulUnit)
        DETACH DELETE e, m
        """
        graph_storage.query(cleanup_query, parameters={'episode_id': episode_id})
        print("\n✓ Cleaned up test data")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        graph_storage.disconnect()


if __name__ == "__main__":
    test_speaker_distribution_storage()