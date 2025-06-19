#!/usr/bin/env python3
"""Comprehensive check of episode processing results."""

import os
from neo4j import GraphDatabase

def check_results():
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    username = os.getenv('NEO4J_USERNAME', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'password')
    
    driver = GraphDatabase.driver(uri, auth=(username, password))
    
    try:
        with driver.session() as session:
            # Get the episode ID
            result = session.run("""
                MATCH (e:Episode)
                WHERE e.id CONTAINS 'Mel_Robbins' AND e.id CONTAINS 'Feel_Good'
                RETURN e.id, e.created_at
                ORDER BY e.created_at DESC
                LIMIT 1
            """)
            
            episode = result.single()
            if not episode:
                print("Episode not found")
                return
                
            episode_id = episode['e.id']
            print(f"Episode: {episode_id}")
            print(f"Created: {episode['e.created_at']}")
            print()
            
            # Check all node types related to this episode
            print("=== NODE COUNTS ===")
            
            # Check MeaningfulUnits
            result = session.run("""
                MATCH (e:Episode {id: $id})-[:CONTAINS]->(u:MeaningfulUnit)
                RETURN COUNT(u) as count
            """, id=episode_id)
            units = result.single()['count']
            print(f"MeaningfulUnits: {units}")
            
            # Check Topics
            result = session.run("""
                MATCH (e:Episode {id: $id})-[:DISCUSSES]->(t:Topic)
                RETURN COUNT(t) as count, COLLECT(t.name) as names
            """, id=episode_id)
            topics = result.single()
            print(f"Topics: {topics['count']}")
            if topics['names']:
                for name in topics['names'][:10]:  # Show first 10
                    print(f"  - {name}")
            
            # Check Speakers
            result = session.run("""
                MATCH (s:Speaker)-[:APPEARS_IN]->(e:Episode {id: $id})
                RETURN COUNT(s) as count, COLLECT(s.name) as names
            """, id=episode_id)
            speakers = result.single()
            print(f"Speakers: {speakers['count']}")
            if speakers['names']:
                for name in speakers['names']:
                    print(f"  - {name}")
            
            # Check for any Entity nodes
            result = session.run("""
                MATCH (n:Entity)
                RETURN COUNT(n) as count
                LIMIT 1
            """)
            entity_count = result.single()['count']
            print(f"\nTotal Entity nodes in database: {entity_count}")
            
            # Check for any Quote nodes
            result = session.run("""
                MATCH (n:Quote)
                RETURN COUNT(n) as count
                LIMIT 1
            """)
            quote_count = result.single()['count']
            print(f"Total Quote nodes in database: {quote_count}")
            
            # Check for any Insight nodes  
            result = session.run("""
                MATCH (n:Insight)
                RETURN COUNT(n) as count
                LIMIT 1
            """)
            insight_count = result.single()['count']
            print(f"Total Insight nodes in database: {insight_count}")
            
            # Show a sample MeaningfulUnit
            print("\n=== SAMPLE MEANINGFUL UNIT ===")
            result = session.run("""
                MATCH (e:Episode {id: $id})-[:CONTAINS]->(u:MeaningfulUnit)
                RETURN u.id, u.unit_type, u.summary, u.start_time, u.end_time
                LIMIT 1
            """, id=episode_id)
            
            unit = result.single()
            if unit:
                print(f"ID: {unit['u.id']}")
                print(f"Type: {unit['u.unit_type']}")
                print(f"Summary: {unit['u.summary']}")
                print(f"Time: {unit['u.start_time']} - {unit['u.end_time']}")
                
    finally:
        driver.close()

if __name__ == "__main__":
    check_results()