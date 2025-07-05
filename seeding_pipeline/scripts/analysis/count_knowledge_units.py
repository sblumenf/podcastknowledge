#!/usr/bin/env python3
"""Count all knowledge units in the Neo4j database."""

import os
from neo4j import GraphDatabase

def count_knowledge_units():
    # Get database connection details from environment variables
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    username = os.getenv('NEO4J_USERNAME', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'password')
    
    driver = GraphDatabase.driver(uri, auth=(username, password))
    
    try:
        with driver.session() as session:
            print("=== KNOWLEDGE UNIT COUNTS ===\n")
            
            # Count Episodes
            result = session.run("MATCH (e:Episode) RETURN COUNT(e) as count")
            episode_count = result.single()['count']
            print(f"Episodes: {episode_count}")
            
            # Count Topics
            result = session.run("MATCH (t:Topic) RETURN COUNT(t) as count")
            topic_count = result.single()['count']
            print(f"Topics: {topic_count}")
            
            # Count MeaningfulUnits
            result = session.run("MATCH (u:MeaningfulUnit) RETURN COUNT(u) as count")
            unit_count = result.single()['count']
            print(f"MeaningfulUnits: {unit_count}")
            
            # Count total knowledge units
            total = episode_count + topic_count + unit_count
            print(f"\nTotal knowledge units: {total}")
            
            # Additional counts for other node types if they exist
            print("\n=== OTHER NODE TYPES ===\n")
            
            # Get all node labels in the database
            result = session.run("""
                MATCH (n)
                RETURN DISTINCT labels(n) as labels
            """)
            
            all_labels = set()
            for record in result:
                if record['labels']:
                    all_labels.update(record['labels'])
            
            # Check for other node types that exist
            other_types = ['Speaker', 'Entity', 'Quote', 'Insight']
            found_other = False
            
            for node_type in other_types:
                if node_type in all_labels:
                    result = session.run(f"MATCH (n:{node_type}) RETURN COUNT(n) as count")
                    count = result.single()['count']
                    if count > 0:
                        if not found_other:
                            found_other = True
                        print(f"{node_type}s: {count}")
            
            # Show breakdown by MeaningfulUnit types if available
            if unit_count > 0:
                print("\n=== MEANINGFUL UNIT TYPES ===\n")
                result = session.run("""
                    MATCH (u:MeaningfulUnit)
                    RETURN u.unit_type as type, COUNT(u) as count
                    ORDER BY count DESC
                """)
                
                for record in result:
                    if record['type']:
                        print(f"{record['type']}: {record['count']}")
                        
    finally:
        driver.close()

if __name__ == "__main__":
    count_knowledge_units()