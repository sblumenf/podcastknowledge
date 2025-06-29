#!/usr/bin/env python3
"""Check meaningful units in the MFM database."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'seeding_pipeline'))

from neo4j import GraphDatabase
import json

# Neo4j connection
uri = "bolt://localhost:7688"
username = "neo4j"
password = os.environ.get("NEO4J_PASSWORD", "password")
database = "neo4j"

driver = GraphDatabase.driver(uri, auth=(username, password))

try:
    with driver.session(database=database) as session:
        # First, check if we have any MeaningfulUnits
        result = session.run("""
            MATCH (mu:MeaningfulUnit)
            RETURN count(mu) as total_units,
                   count(DISTINCT mu.episode_id) as episode_count
        """)
        
        record = result.single()
        print(f"=== DATABASE SUMMARY ===")
        print(f"Total MeaningfulUnits: {record['total_units']}")
        print(f"Total Episodes: {record['episode_count']}")
        print()
        
        # Look for episodes with very few units
        result = session.run("""
            MATCH (e:Episode)
            OPTIONAL MATCH (mu:MeaningfulUnit)-[:PART_OF]->(e)
            WITH e, count(mu) as unit_count
            WHERE unit_count > 0
            RETURN e.episode_id as episode_id,
                   e.title as title,
                   unit_count
            ORDER BY unit_count ASC
            LIMIT 10
        """)
        
        print("=== EPISODES WITH FEWEST UNITS ===")
        for record in result:
            print(f"\nEpisode: {record['episode_id']}")
            print(f"Title: {record['title']}")
            print(f"Units: {record['unit_count']}")
            if record['unit_count'] == 1:
                print("  ⚠️  WARNING: Only 1 unit created!")
        
        # Check unit sizes
        print("\n\n=== MEANINGFUL UNIT SIZES ===")
        result = session.run("""
            MATCH (mu:MeaningfulUnit)
            RETURN mu.id as unit_id,
                   mu.episode_id as episode_id,
                   mu.unit_type as type,
                   mu.segment_count as segments,
                   mu.summary as summary,
                   mu.end_time - mu.start_time as duration
            ORDER BY segments DESC
            LIMIT 10
        """)
        
        for record in result:
            segments = record['segments'] or 'unknown'
            duration = record['duration'] or 0
            
            print(f"\nUnit: {record['unit_id']}")
            print(f"Episode: {record['episode_id']}")
            print(f"Type: {record['type']}")
            print(f"Segments: {segments}")
            print(f"Duration: {duration:.1f}s ({duration/60:.1f} minutes)")
            
            if isinstance(segments, int) and segments > 100:
                print(f"  ⚠️  WARNING: Excessive segments in single unit!")
            
            print(f"Summary: {record['summary'][:100] if record['summary'] else 'No summary'}...")
            
except Exception as e:
    print(f"Error: {e}")
    
finally:
    driver.close()

print("\n\nANALYSIS:")
print("If you see units with 300+ segments, this confirms the issue.")
print("The conversation analyzer is not properly segmenting content into multiple units.")