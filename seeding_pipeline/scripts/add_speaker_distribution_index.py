#!/usr/bin/env python3
"""Add index for speaker_distribution field in MeaningfulUnit nodes."""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.graph_storage import GraphStorageService
from src.core.config import Config


def add_speaker_distribution_index():
    """Add index for speaker_distribution field."""
    
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
        print("Connected to Neo4j")
        
        # Add index for speaker_distribution
        with graph_storage.session() as session:
            try:
                index_query = "CREATE INDEX IF NOT EXISTS FOR (m:MeaningfulUnit) ON (m.speaker_distribution)"
                session.run(index_query)
                print("✓ Added index for MeaningfulUnit.speaker_distribution")
            except Exception as e:
                print(f"Note: Could not create index for speaker_distribution: {e}")
                print("This is normal if the field doesn't exist yet or if Neo4j doesn't support indexing this field type")
        
        # Verify indexes
        with graph_storage.session() as session:
            show_indexes = "SHOW INDEXES"
            results = session.run(show_indexes)
            
            print("\nCurrent indexes on MeaningfulUnit:")
            for record in results:
                if 'MeaningfulUnit' in str(record.get('labelsOrTypes', [])):
                    print(f"  - {record.get('name', 'unnamed')}: {record.get('properties', [])} ({record.get('state', 'unknown')})")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        graph_storage.disconnect()


if __name__ == "__main__":
    add_speaker_distribution_index()