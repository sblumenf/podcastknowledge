#!/usr/bin/env python3
"""Test script to verify speaker identification improvements."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import os
from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig

def test_speaker_improvements():
    """Display current speaker identification results to verify improvements."""
    config = PipelineConfig()
    
    print(f"\n=== Speaker Identification Test ===")
    print(f"Configuration:")
    print(f"  - Speaker confidence threshold: {config.speaker_confidence_threshold}")
    print(f"  - Speaker mapping enabled: True (hardcoded in main.py)")
    print(f"  - Environment SPEAKER_CONFIDENCE_THRESHOLD: {os.environ.get('SPEAKER_CONFIDENCE_THRESHOLD', 'Not set')}")
    
    storage = GraphStorageService(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password,
        database=config.neo4j_database
    )
    
    try:
        # Query for all speakers
        query = """
        MATCH (e:Episode)
        OPTIONAL MATCH (mu:MeaningfulUnit)-[:PART_OF]->(e)
        WHERE mu.speaker_distribution IS NOT NULL
        WITH e, collect(DISTINCT mu.speaker_distribution) as speaker_patterns
        RETURN e.title as title,
               speaker_patterns,
               size(speaker_patterns) as pattern_count
        ORDER BY e.title
        """
        
        results = storage.query(query)
        
        print(f"\n=== Current Speaker Identification Results ===\n")
        
        import json
        
        for r in results:
            print(f"Episode: {r['title']}")
            
            # Extract unique speakers
            speakers_set = set()
            for pattern in r['speaker_patterns']:
                if pattern:
                    try:
                        if isinstance(pattern, str) and pattern.startswith('{'):
                            speaker_dict = json.loads(pattern.replace("'", '"'))
                            speakers_set.update(speaker_dict.keys())
                        else:
                            speakers_set.add(pattern)
                    except:
                        speakers_set.add(str(pattern))
            
            speakers_list = sorted(list(speakers_set))
            
            print(f"Speakers found ({len(speakers_list)}):")
            for speaker in speakers_list:
                # Check if it's a generic speaker
                is_generic = any([
                    "Guest Expert -" in speaker,
                    "Primary Speaker" in speaker,
                    "Brief Contributor" in speaker,
                    "Guest/Contributor" in speaker,
                    "Co-host/Major Guest" in speaker,
                    "(Speaker" in speaker,
                ])
                
                marker = " [GENERIC - needs improvement]" if is_generic else " [IDENTIFIED]"
                print(f"  - {speaker}{marker}")
            
            print()
        
        # Summary statistics
        print("\n=== Summary ===")
        print("Next steps to improve speaker identification:")
        print("1. Set SPEAKER_CONFIDENCE_THRESHOLD=0.5 in your .env file")
        print("2. Re-run the pipeline with: python main.py <vtt_file>")
        print("3. The improvements should:")
        print("   - Accept more LLM identifications (lower confidence threshold)")
        print("   - Better recognize generic patterns for post-processing")
        print("   - Try harder to find actual names before using generic roles")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        storage.close()

if __name__ == "__main__":
    test_speaker_improvements()