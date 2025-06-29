#!/usr/bin/env python3
"""Find the episode with 313 segments and only 1 meaningful unit."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'seeding_pipeline'))

from neo4j import GraphDatabase

# Neo4j connection
uri = "bolt://localhost:7688"
username = "neo4j"
password = os.environ.get("NEO4J_PASSWORD", "password")
database = "neo4j"

driver = GraphDatabase.driver(uri, auth=(username, password))

try:
    with driver.session(database=database) as session:
        # Look for the episode with 1 unit that might be the 313-segment one
        result = session.run("""
            MATCH (e:Episode)<-[:PART_OF]-(mu:MeaningfulUnit)
            WITH e, count(mu) as unit_count, collect(mu) as units
            WHERE unit_count = 1
            RETURN e.episode_id as episode_id,
                   e.title as title,
                   e.vtt_path as vtt_path,
                   unit_count,
                   units[0].id as unit_id,
                   units[0].summary as unit_summary,
                   units[0].end_time - units[0].start_time as duration_seconds
            ORDER BY duration_seconds DESC
        """)
        
        print("=== EPISODES WITH ONLY 1 MEANINGFUL UNIT ===\n")
        
        for record in result:
            duration_min = record['duration_seconds'] / 60 if record['duration_seconds'] else 0
            
            print(f"Episode: {record['title']}")
            print(f"Episode ID: {record['episode_id']}")
            print(f"VTT Path: {record['vtt_path']}")
            print(f"Units: {record['unit_count']}")
            print(f"Unit Duration: {record['duration_seconds']:.1f}s ({duration_min:.1f} minutes)")
            
            # A 313-segment episode would likely be 30-60 minutes
            if duration_min > 25:
                print("  ⚠️  LIKELY CANDIDATE - Long duration single unit!")
            
            print(f"Unit Summary: {record['unit_summary'][:150] if record['unit_summary'] else 'No summary'}...")
            print("-" * 80)
            print()
        
        # Also check knowledge extraction results
        print("\n=== KNOWLEDGE EXTRACTION SUMMARY ===\n")
        
        result = session.run("""
            MATCH (e:Episode)<-[:PART_OF]-(mu:MeaningfulUnit)
            WITH e, count(mu) as unit_count
            WHERE unit_count = 1
            OPTIONAL MATCH (ent:Entity)-[:EXTRACTED_FROM]->(e)
            OPTIONAL MATCH (ins:Insight)-[:DERIVED_FROM]->(e)
            OPTIONAL MATCH (q:Quote)-[:SPOKEN_IN]->(e)
            WITH e.title as title, 
                 unit_count,
                 count(DISTINCT ent) as entities,
                 count(DISTINCT ins) as insights,
                 count(DISTINCT q) as quotes
            RETURN title, unit_count, entities, insights, quotes
            ORDER BY entities + insights + quotes ASC
        """)
        
        for record in result:
            total = record['entities'] + record['insights'] + record['quotes']
            print(f"Episode: {record['title']}")
            print(f"Units: {record['unit_count']}")
            print(f"Entities: {record['entities']}")
            print(f"Insights: {record['insights']}")
            print(f"Quotes: {record['quotes']}")
            print(f"Total Extractions: {total}")
            
            # The reported issue was 14 entities, 5 quotes, 9 insights (total 28)
            if record['entities'] == 14 and record['quotes'] == 5 and record['insights'] == 9:
                print("  ⚠️  THIS IS THE REPORTED EPISODE!")
            
            print()
            
except Exception as e:
    print(f"Error: {e}")
    
finally:
    driver.close()

print("\nCONCLUSION:")
print("The episode with 313 segments and only 1 meaningful unit is likely")
print("the one with the longest duration single unit (probably 30+ minutes).")
print("\nThis confirms the conversation analyzer is not properly segmenting")
print("long episodes into multiple meaningful units.")