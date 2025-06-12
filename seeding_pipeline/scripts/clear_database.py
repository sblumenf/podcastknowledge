#!/usr/bin/env python3
"""Clear all data from Neo4j database."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig

def clear_database():
    """Clear all nodes and relationships from the database."""
    
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
        print("Connected to Neo4j database")
        
        # Count before deletion
        print("\n=== BEFORE DELETION ===")
        with storage.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = result.single()['count']
            print(f"Total nodes: {node_count}")
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()['count']
            print(f"Total relationships: {rel_count}")
        
        if node_count == 0 and rel_count == 0:
            print("\nDatabase is already empty!")
            return
        
        # Show what will be deleted
        print(f"\nDeleting {node_count} nodes and {rel_count} relationships...")
        
        # Delete all relationships first
        print("\nDeleting all relationships...")
        with storage.session() as session:
            session.run("MATCH ()-[r]->() DELETE r")
        
        # Delete all nodes
        print("Deleting all nodes...")
        with storage.session() as session:
            session.run("MATCH (n) DELETE n")
        
        # Verify deletion
        print("\n=== AFTER DELETION ===")
        with storage.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = result.single()['count']
            print(f"Total nodes: {node_count}")
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()['count']
            print(f"Total relationships: {rel_count}")
        
        print("\nDatabase cleared successfully!")
        
    except Exception as e:
        print(f"Error clearing database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        storage.disconnect()

if __name__ == "__main__":
    clear_database()