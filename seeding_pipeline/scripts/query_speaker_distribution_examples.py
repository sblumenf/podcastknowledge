#!/usr/bin/env python3
"""Example queries for analyzing speaker distribution in MeaningfulUnits."""

import os
import sys
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.graph_storage import GraphStorageService
from src.core.config import Config


def run_speaker_distribution_queries():
    """Run example queries using speaker_distribution data."""
    
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
        
        # Query 1: Find units where a specific speaker dominates
        print("=== Query 1: Units dominated by primary speaker (>80% speaking time) ===")
        query1 = """
        MATCH (m:MeaningfulUnit)
        WHERE m.speaker_distribution IS NOT NULL
        WITH m, m.speaker_distribution AS dist_json
        // This would require parsing JSON in Cypher or using a custom function
        RETURN m.id AS unit_id, 
               m.primary_speaker AS primary_speaker,
               m.speaker_distribution AS distribution
        LIMIT 5
        """
        
        results = graph_storage.query(query1)
        if results:
            for result in results:
                unit_id = result['unit_id']
                primary = result['primary_speaker']
                dist_str = result['distribution']
                
                if dist_str:
                    try:
                        dist = json.loads(dist_str)
                        # Check if primary speaker has >80%
                        if primary in dist and dist[primary] > 80:
                            print(f"Unit {unit_id}: {primary} speaks {dist[primary]}% of the time")
                    except:
                        pass
        else:
            print("No units with speaker_distribution found")
        
        # Query 2: Find units with balanced conversation
        print("\n=== Query 2: Units with balanced conversation (no speaker >60%) ===")
        query2 = """
        MATCH (m:MeaningfulUnit)-[:PART_OF]->(e:Episode)
        WHERE m.speaker_distribution IS NOT NULL
        RETURN m.id AS unit_id,
               m.speaker_distribution AS distribution,
               e.title AS episode_title
        LIMIT 10
        """
        
        results = graph_storage.query(query2)
        balanced_count = 0
        if results:
            for result in results:
                unit_id = result['unit_id']
                dist_str = result['distribution']
                episode = result['episode_title']
                
                if dist_str:
                    try:
                        dist = json.loads(dist_str)
                        # Check if conversation is balanced (no speaker >60%)
                        if all(percentage <= 60 for percentage in dist.values()):
                            balanced_count += 1
                            print(f"Unit {unit_id} from '{episode[:50]}...':")
                            for speaker, pct in dist.items():
                                print(f"  - {speaker}: {pct}%")
                    except:
                        pass
        
        if balanced_count == 0 and results:
            print("No balanced conversations found in current data")
            
        # Query 3: Speaker statistics across all units
        print("\n=== Query 3: Overall speaker participation ===")
        query3 = """
        MATCH (m:MeaningfulUnit)
        WHERE m.primary_speaker IS NOT NULL
        RETURN m.primary_speaker AS speaker, 
               count(m) AS unit_count,
               avg(m.end_time - m.start_time) AS avg_duration
        ORDER BY unit_count DESC
        """
        
        results = graph_storage.query(query3)
        if results:
            print(f"{'Speaker':<40} {'Units':<10} {'Avg Duration (s)':<15}")
            print("-" * 65)
            for result in results:
                speaker = result['speaker'][:38]  # Truncate long names
                count = result['unit_count']
                avg_dur = result['avg_duration']
                print(f"{speaker:<40} {count:<10} {avg_dur:>10.1f}")
        
        # Query 4: Multi-speaker units
        print("\n=== Query 4: Units with multiple speakers ===")
        query4 = """
        MATCH (m:MeaningfulUnit)
        WHERE m.speaker_distribution IS NOT NULL
        RETURN m.id AS unit_id,
               m.speaker_distribution AS distribution,
               m.unit_type AS type
        LIMIT 20
        """
        
        results = graph_storage.query(query4)
        multi_speaker_count = 0
        if results:
            for result in results:
                dist_str = result['distribution']
                if dist_str:
                    try:
                        dist = json.loads(dist_str)
                        if len(dist) > 1:
                            multi_speaker_count += 1
                            if multi_speaker_count <= 5:  # Show first 5
                                print(f"\nUnit {result['unit_id']} ({result['type']}):")
                                for speaker, pct in sorted(dist.items(), key=lambda x: x[1], reverse=True):
                                    print(f"  - {speaker}: {pct}%")
                    except:
                        pass
            
            print(f"\nTotal multi-speaker units found: {multi_speaker_count}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        graph_storage.disconnect()


if __name__ == "__main__":
    run_speaker_distribution_queries()