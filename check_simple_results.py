#!/usr/bin/env python3
"""Simple check of episode processing results."""

import os
from neo4j import GraphDatabase

def check_results():
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    username = os.getenv('NEO4J_USERNAME', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'password')
    
    driver = GraphDatabase.driver(uri, auth=(username, password))
    
    try:
        with driver.session() as session:
            # Check for episodes
            result = session.run("""
                MATCH (e:Episode)
                WHERE e.id CONTAINS 'Mel_Robbins'
                RETURN e.id, e.created_at
                ORDER BY e.created_at DESC
                LIMIT 5
            """)
            
            episodes = list(result)
            if episodes:
                print(f"Found {len(episodes)} episodes:")
                for record in episodes:
                    print(f"  - {record['e.id']}")
                    print(f"    Created: {record['e.created_at']}")
                    
                # Get stats for most recent
                most_recent_id = episodes[0]['e.id']
                stats = session.run("""
                    MATCH (e:Episode {id: $episode_id})
                    OPTIONAL MATCH (e)-[:HAS_UNIT]->(u:MeaningfulUnit)
                    OPTIONAL MATCH (u)-[:CONTAINS_ENTITY]->(ent:Entity)
                    OPTIONAL MATCH (u)-[:CONTAINS_QUOTE]->(q:Quote)
                    OPTIONAL MATCH (u)-[:CONTAINS_INSIGHT]->(ins:Insight)
                    RETURN COUNT(DISTINCT u) as units,
                           COUNT(DISTINCT ent) as entities,
                           COUNT(DISTINCT q) as quotes,
                           COUNT(DISTINCT ins) as insights
                """, episode_id=most_recent_id)
                
                stats_record = stats.single()
                print(f"\nStats for most recent episode:")
                print(f"  - Meaningful Units: {stats_record['units']}")
                print(f"  - Entities: {stats_record['entities']}")
                print(f"  - Quotes: {stats_record['quotes']}")
                print(f"  - Insights: {stats_record['insights']}")
            else:
                print("No Mel Robbins episodes found")
                
                # Check what episodes exist
                all_episodes = session.run("MATCH (e:Episode) RETURN e.id LIMIT 10")
                episode_list = list(all_episodes)
                if episode_list:
                    print("\nFound these episodes instead:")
                    for record in episode_list:
                        print(f"  - {record['e.id']}")
                else:
                    print("\nNo episodes found in database")
                    
    finally:
        driver.close()

if __name__ == "__main__":
    check_results()