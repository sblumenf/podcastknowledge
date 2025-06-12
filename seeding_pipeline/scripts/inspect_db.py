#!/usr/bin/env python3
"""Inspect Neo4j database contents."""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig

def inspect_database():
    """Inspect the current state of the Neo4j database."""
    
    # Initialize connection
    config = PipelineConfig()
    storage = GraphStorageService(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password
    )
    
    try:
        # Connect to database
        storage.connect()
        print("Successfully connected to Neo4j database")
        print("\n" + "="*60)
        
        # Count nodes by label
        print("NODE COUNTS BY LABEL:")
        print("-"*60)
        
        with storage.session() as session:
            # Get all labels
            result = session.run("CALL db.labels()")
            labels = [record[0] for record in result]
            
            for label in labels:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                count = result.single()['count']
                print(f"{label}: {count}")
        
        print("\n" + "="*60)
        print("RELATIONSHIP COUNTS BY TYPE:")
        print("-"*60)
        
        with storage.session() as session:
            # Get all relationship types
            result = session.run("CALL db.relationshipTypes()")
            rel_types = [record[0] for record in result]
            
            for rel_type in rel_types:
                result = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count")
                count = result.single()['count']
                print(f"{rel_type}: {count}")
        
        print("\n" + "="*60)
        print("DISCONNECTED NODES:")
        print("-"*60)
        
        with storage.session() as session:
            for label in labels:
                result = session.run(f"""
                    MATCH (n:{label})
                    WHERE NOT (n)-[]-()
                    RETURN count(n) as count
                """)
                count = result.single()['count']
                if count > 0:
                    print(f"{label}: {count} disconnected nodes")
        
        print("\n" + "="*60)
        print("SAMPLE DATA:")
        print("-"*60)
        
        # Show sample episodes
        with storage.session() as session:
            result = session.run("""
                MATCH (e:Episode)
                RETURN e
                LIMIT 5
            """)
            episodes = list(result)
            if episodes:
                print(f"\nSample Episodes ({len(episodes)}):")
                for record in episodes:
                    episode = dict(record['e'])
                    print(f"  - Title: {episode.get('title', 'N/A')}")
                    print(f"    ID: {episode.get('id', 'N/A')}")
                    
                    # Check connections
                    result2 = session.run("""
                        MATCH (e:Episode {id: $id})-[r]-(connected)
                        RETURN type(r) as rel_type, labels(connected) as node_labels, count(*) as count
                        ORDER BY count DESC
                    """, id=episode.get('id'))
                    connections = list(result2)
                    if connections:
                        print("    Connections:")
                        for conn in connections:
                            print(f"      - {conn['rel_type']} -> {conn['node_labels']}: {conn['count']}")
                    else:
                        print("    Connections: None (disconnected)")
                    print()
        
    except Exception as e:
        print(f"Error inspecting database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        storage.disconnect()

if __name__ == "__main__":
    inspect_database()