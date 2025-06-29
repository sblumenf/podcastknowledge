#!/usr/bin/env python3
"""Discover the actual relationships connecting episodes to meaningful units."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.storage.graph_storage import GraphStorageService

def discover_relationships(name, port):
    """Discover actual relationships in use."""
    print(f"\n{'='*50}")
    print(f"DISCOVERING {name.upper()} RELATIONSHIPS")
    print(f"{'='*50}")
    
    storage = GraphStorageService(
        uri=f"neo4j://localhost:{port}",
        username="neo4j",
        password="password"
    )
    
    try:
        storage.connect()
        print(f"✅ Connected to {name} database")
        
        with storage.session() as session:
            # Find ANY relationships between Episodes and MeaningfulUnits
            print(f"\n--- FINDING EPISODE-TO-MEANINGFULUNIT RELATIONSHIPS ---")
            result = session.run("""
                MATCH (e:Episode)-[r]->(u:MeaningfulUnit)
                RETURN type(r) as relationship_type, count(*) as count
                ORDER BY count DESC
            """)
            
            episode_to_unit_rels = list(result)
            
            if episode_to_unit_rels:
                print("✅ Found direct Episode → MeaningfulUnit relationships:")
                for record in episode_to_unit_rels:
                    print(f"  {record['relationship_type']}: {record['count']} connections")
            else:
                print("❌ No direct Episode → MeaningfulUnit relationships found")
                
                # Try reverse direction
                print("\n--- CHECKING REVERSE DIRECTION ---")
                result = session.run("""
                    MATCH (u:MeaningfulUnit)-[r]->(e:Episode)
                    RETURN type(r) as relationship_type, count(*) as count
                    ORDER BY count DESC
                """)
                
                reverse_rels = list(result)
                if reverse_rels:
                    print("✅ Found MeaningfulUnit → Episode relationships:")
                    for record in reverse_rels:
                        print(f"  {record['relationship_type']}: {record['count']} connections")
                else:
                    print("❌ No MeaningfulUnit → Episode relationships either")
            
            # Check what MeaningfulUnits ARE connected to
            print(f"\n--- WHAT ARE MEANINGFULUNITS CONNECTED TO? ---")
            result = session.run("""
                MATCH (u:MeaningfulUnit)-[r]->(n)
                RETURN labels(n) as target_labels, type(r) as relationship_type, count(*) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            
            unit_connections = list(result)
            if unit_connections:
                print("MeaningfulUnits are connected to:")
                for record in unit_connections:
                    labels = record['target_labels']
                    rel_type = record['relationship_type']
                    count = record['count']
                    print(f"  → {labels} via '{rel_type}': {count} times")
            
            # Check what's connected TO MeaningfulUnits
            print(f"\n--- WHAT'S CONNECTED TO MEANINGFULUNITS? ---")
            result = session.run("""
                MATCH (n)-[r]->(u:MeaningfulUnit)
                RETURN labels(n) as source_labels, type(r) as relationship_type, count(*) as count
                ORDER BY count DESC
                LIMIT 10
            """)
            
            to_unit_connections = list(result)
            if to_unit_connections:
                print("Connected TO MeaningfulUnits:")
                for record in to_unit_connections:
                    labels = record['source_labels']
                    rel_type = record['relationship_type']
                    count = record['count']
                    print(f"  {labels} → via '{rel_type}': {count} times")
            
            # Sample a few MeaningfulUnits to see their properties
            print(f"\n--- SAMPLE MEANINGFULUNIT PROPERTIES ---")
            result = session.run("""
                MATCH (u:MeaningfulUnit)
                RETURN u.id as id, u.description as description, u.episode_id as episode_id
                LIMIT 3
            """)
            
            for i, record in enumerate(result, 1):
                unit_id = record['id'] or 'No ID'
                description = record['description'] or 'No description'
                episode_id = record['episode_id'] or 'No episode_id'
                print(f"{i}. Unit ID: {unit_id}")
                print(f"   Description: {description[:100]}...")
                print(f"   Episode ID: {episode_id}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            storage.disconnect()
        except:
            pass

def main():
    """Discover relationships in both databases."""
    discover_relationships("Mel Robbins", 7687)
    discover_relationships("MFM", 7688)

if __name__ == "__main__":
    main()