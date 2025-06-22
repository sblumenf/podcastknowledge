#!/usr/bin/env python3
"""Test script to verify speaker_distribution is stored in MeaningfulUnit nodes."""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.graph_storage import GraphStorageService
from src.core.config import Config


def test_speaker_distribution_storage():
    """Test that speaker_distribution is correctly stored in Neo4j."""
    
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
        
        # Query for MeaningfulUnits with speaker_distribution
        query = """
        MATCH (m:MeaningfulUnit)
        WHERE m.speaker_distribution IS NOT NULL
        RETURN m.id AS id, 
               m.primary_speaker AS primary_speaker,
               m.speaker_distribution AS speaker_distribution
        LIMIT 10
        """
        
        results = graph_storage.query(query)
        
        if not results:
            print("\n⚠️  No MeaningfulUnits found with speaker_distribution field")
            print("This could mean:")
            print("1. No episodes have been processed with the updated code")
            print("2. The field is not being stored correctly")
            
            # Check if there are any MeaningfulUnits at all
            count_query = "MATCH (m:MeaningfulUnit) RETURN count(m) AS count"
            count_result = graph_storage.query(count_query)
            total_units = count_result[0]['count'] if count_result else 0
            print(f"\nTotal MeaningfulUnits in database: {total_units}")
            
        else:
            print(f"\n✓ Found {len(results)} MeaningfulUnits with speaker_distribution")
            print("\nSample data:")
            
            for i, result in enumerate(results[:5], 1):
                print(f"\n{i}. Unit ID: {result['id']}")
                print(f"   Primary Speaker: {result['primary_speaker']}")
                
                # Parse the JSON string
                try:
                    speaker_dist = json.loads(result['speaker_distribution'])
                    print("   Speaker Distribution:")
                    for speaker, percentage in speaker_dist.items():
                        print(f"     - {speaker}: {percentage}%")
                except json.JSONDecodeError:
                    print(f"   Speaker Distribution: {result['speaker_distribution']} (invalid JSON)")
        
        # Check a recently created MeaningfulUnit (if any)
        recent_query = """
        MATCH (m:MeaningfulUnit)-[:PART_OF]->(e:Episode)
        RETURN m.id AS id, 
               m.primary_speaker AS primary_speaker,
               m.speaker_distribution AS speaker_distribution,
               e.id AS episode_id,
               e.title AS episode_title
        ORDER BY m.id DESC
        LIMIT 1
        """
        
        recent_results = graph_storage.query(recent_query)
        if recent_results:
            print("\n\nMost recent MeaningfulUnit:")
            result = recent_results[0]
            print(f"Unit ID: {result['id']}")
            print(f"Episode: {result['episode_title']} ({result['episode_id']})")
            print(f"Primary Speaker: {result['primary_speaker']}")
            
            if result['speaker_distribution']:
                try:
                    speaker_dist = json.loads(result['speaker_distribution'])
                    print("Speaker Distribution:")
                    for speaker, percentage in speaker_dist.items():
                        print(f"  - {speaker}: {percentage}%")
                except json.JSONDecodeError:
                    print(f"Speaker Distribution: {result['speaker_distribution']} (invalid JSON)")
            else:
                print("Speaker Distribution: Not set")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        graph_storage.disconnect()


if __name__ == "__main__":
    test_speaker_distribution_storage()