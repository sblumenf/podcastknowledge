#!/usr/bin/env python3
"""Analyze Neo4j database contents to understand the current state."""

from neo4j import GraphDatabase
import os
from collections import defaultdict

# Database connection
uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
auth = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))

driver = GraphDatabase.driver(uri, auth=auth)

def analyze_database():
    with driver.session() as session:
        # Get node counts by label
        print("=== NODE COUNTS BY LABEL ===")
        result = session.run("""
            MATCH (n)
            RETURN labels(n) as labels, count(n) as count
            ORDER BY count DESC
        """)
        for record in result:
            print(f"{record['labels']}: {record['count']}")
        
        # Get relationship counts
        print("\n=== RELATIONSHIP COUNTS BY TYPE ===")
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as type, count(r) as count
            ORDER BY count DESC
        """)
        for record in result:
            print(f"{record['type']}: {record['count']}")
        
        # Check for disconnected nodes
        print("\n=== DISCONNECTED NODES ===")
        result = session.run("""
            MATCH (n)
            WHERE NOT (n)-[]-()
            RETURN labels(n) as labels, count(n) as count
            ORDER BY count DESC
        """)
        total_disconnected = 0
        for record in result:
            print(f"{record['labels']}: {record['count']}")
            total_disconnected += record['count']
        print(f"Total disconnected nodes: {total_disconnected}")
        
        # Sample some nodes
        print("\n=== SAMPLE NODES (first 5 of each type) ===")
        result = session.run("""
            MATCH (n)
            RETURN DISTINCT labels(n) as labels
        """)
        labels = [record['labels'] for record in result]
        
        for label_list in labels:
            if label_list:
                label = label_list[0]
                print(f"\n{label} nodes:")
                result = session.run(f"""
                    MATCH (n:{label})
                    RETURN n
                    LIMIT 5
                """)
                for record in result:
                    node = record['n']
                    print(f"  - {dict(node)}")
        
        # Check for Episodes
        print("\n=== EPISODE ANALYSIS ===")
        result = session.run("""
            MATCH (e:Episode)
            RETURN count(e) as count
        """)
        episode_count = result.single()['count']
        print(f"Total episodes: {episode_count}")
        
        if episode_count > 0:
            # Check episode connections
            result = session.run("""
                MATCH (e:Episode)
                OPTIONAL MATCH (e)-[r]-(connected)
                WITH e, count(r) as connection_count
                RETURN 
                    CASE WHEN connection_count = 0 THEN 'disconnected' 
                         ELSE 'connected' END as status,
                    count(e) as count
            """)
            for record in result:
                print(f"Episodes {record['status']}: {record['count']}")
        
        # Check for entities and concepts
        print("\n=== KNOWLEDGE GRAPH ANALYSIS ===")
        for node_type in ['Entity', 'Concept', 'Topic', 'Person', 'Organization']:
            result = session.run(f"""
                MATCH (n:{node_type})
                RETURN count(n) as count
            """)
            count = result.single()['count']
            if count > 0:
                print(f"{node_type}: {count}")

if __name__ == "__main__":
    try:
        analyze_database()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.close()