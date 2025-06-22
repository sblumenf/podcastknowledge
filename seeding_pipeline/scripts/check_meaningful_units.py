#!/usr/bin/env python3
"""Check the structure of existing MeaningfulUnits in the database."""

import os
import sys
import json
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.graph_storage import GraphStorageService
from src.core.config import Config


def check_meaningful_units():
    """Check existing MeaningfulUnits and their properties."""
    
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
        print("Connected to Neo4j\n")
        
        # Get all properties of MeaningfulUnits
        query = """
        MATCH (m:MeaningfulUnit)
        RETURN m
        LIMIT 5
        """
        
        results = graph_storage.query(query)
        
        if results:
            print(f"Sample MeaningfulUnit properties (showing first {len(results)} units):\n")
            
            for i, result in enumerate(results, 1):
                unit = result['m']
                print(f"{i}. Unit ID: {unit.get('id', 'N/A')}")
                print(f"   Properties available:")
                for key in sorted(unit.keys()):
                    value = unit[key]
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:97] + "..."
                    print(f"     - {key}: {value}")
                print()
        
        # Check for units by episode
        episode_query = """
        MATCH (e:Episode)<-[:PART_OF]-(m:MeaningfulUnit)
        RETURN e.title AS episode_title, e.id AS episode_id, count(m) AS unit_count
        ORDER BY e.id DESC
        LIMIT 10
        """
        
        episode_results = graph_storage.query(episode_query)
        
        if episode_results:
            print("\nEpisodes with MeaningfulUnits:")
            print("-" * 80)
            for result in episode_results:
                print(f"Episode: {result['episode_title'][:50]}...")
                print(f"  ID: {result['episode_id']}")
                print(f"  Units: {result['unit_count']}")
                print()
        
        # Check if any units have embeddings
        embedding_query = """
        MATCH (m:MeaningfulUnit)
        WHERE m.embedding IS NOT NULL
        RETURN count(m) AS count
        """
        
        embedding_result = graph_storage.query(embedding_query)
        embedding_count = embedding_result[0]['count'] if embedding_result else 0
        
        print(f"\nMeaningfulUnits with embeddings: {embedding_count}")
        
        # Check unique speakers
        speaker_query = """
        MATCH (m:MeaningfulUnit)
        WHERE m.primary_speaker IS NOT NULL
        RETURN DISTINCT m.primary_speaker AS speaker, count(m) AS count
        ORDER BY count DESC
        """
        
        speaker_results = graph_storage.query(speaker_query)
        
        if speaker_results:
            print("\nPrimary speakers in MeaningfulUnits:")
            print("-" * 40)
            for result in speaker_results:
                print(f"{result['speaker']}: {result['count']} units")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        graph_storage.disconnect()


if __name__ == "__main__":
    check_meaningful_units()