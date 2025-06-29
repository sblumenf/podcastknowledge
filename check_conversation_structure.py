#!/usr/bin/env python3
"""Check what conversation structure was created for episodes."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'seeding_pipeline'))

from neo4j import GraphDatabase
import json

# Neo4j connection
uri = "bolt://localhost:7688"
username = "neo4j"
password = os.environ.get("NEO4J_PASSWORD", "password")
database = "neo4j"  # Use default database

driver = GraphDatabase.driver(uri, auth=(username, password))

try:
    with driver.session(database=database) as session:
        # Query for meaningful units
        result = session.run("""
            MATCH (mu:MeaningfulUnit)
            RETURN mu.episode_id as episode_id,
                   count(mu) as unit_count,
                   collect({
                       id: mu.id,
                       type: mu.unit_type,
                       summary: mu.summary,
                       segment_count: mu.metadata.segment_count,
                       duration: mu.end_time - mu.start_time
                   }) as units
            ORDER BY unit_count ASC
            LIMIT 10
        """)
        
        print("=== MEANINGFUL UNITS PER EPISODE ===\n")
        
        for record in result:
            episode_id = record["episode_id"]
            unit_count = record["unit_count"]
            units = record["units"]
            
            print(f"Episode: {episode_id}")
            print(f"Units: {unit_count}")
            
            if unit_count == 1:
                print("  ⚠️  WARNING: Only 1 unit created!")
                unit = units[0]
                print(f"  - Type: {unit['type']}")
                print(f"  - Segments: {unit.get('segment_count', 'unknown')}")
                print(f"  - Duration: {unit.get('duration', 0):.1f}s")
                print(f"  - Summary: {unit['summary'][:100]}...")
            else:
                total_segments = sum(u.get('segment_count', 0) for u in units)
                print(f"  - Total segments across units: {total_segments}")
                print(f"  - Average segments per unit: {total_segments/unit_count:.1f}")
            
            print()
        
        # Check for episodes with high segment counts in single units
        print("\n=== UNITS WITH EXCESSIVE SEGMENTS ===\n")
        
        result = session.run("""
            MATCH (mu:MeaningfulUnit)
            WHERE mu.metadata.segment_count > 50
            RETURN mu.id as unit_id,
                   mu.episode_id as episode_id,
                   mu.unit_type as type,
                   mu.metadata.segment_count as segments,
                   mu.summary as summary
            ORDER BY segments DESC
            LIMIT 10
        """)
        
        for record in result:
            print(f"Unit: {record['unit_id']}")
            print(f"Episode: {record['episode_id']}")
            print(f"Type: {record['type']}")
            print(f"Segments: {record['segments']} ⚠️")
            print(f"Summary: {record['summary'][:100]}...")
            print()
            
except Exception as e:
    print(f"Error: {e}")
    
finally:
    driver.close()

print("\nANALYSIS:")
print("If you see episodes with only 1 unit containing 300+ segments,")
print("this confirms the conversation analyzer is not properly segmenting the content.")
print("\nThe prompt needs to be more explicit about creating multiple units.")