#!/usr/bin/env python3
"""Fix database duplicates by setting up constraints and cleaning existing data."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig

def fix_database_duplicates():
    """Fix database duplicates and set up proper constraints."""
    config = PipelineConfig()
    storage = GraphStorageService(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password,
        database=config.neo4j_database
    )
    
    try:
        print("=== Database Duplicate Fix ===\n")
        
        # 1. Setup constraints and indexes (this should have been done initially)
        print("1. Setting up database constraints and indexes...")
        storage.setup_schema()
        print("   ✅ Constraints and indexes created")
        
        # 2. Check what constraints exist now
        print("\n2. Verifying constraints...")
        try:
            constraints = storage.query("SHOW CONSTRAINTS")
            print(f"   Found {len(constraints)} constraints:")
            for c in constraints:
                print(f"     - {c.get('name', 'unnamed')}: {c.get('labelsOrTypes', [])} {c.get('properties', [])}")
        except Exception as e:
            print(f"   Could not list constraints: {e}")
        
        # 3. Handle MeaningfulUnit duplicates (this will fail due to constraint)
        print("\n3. Analyzing MeaningfulUnit duplicates...")
        duplicate_units = storage.query("""
        MATCH (mu:MeaningfulUnit)
        WITH mu.id as unit_id, collect(mu) as units
        WHERE size(units) > 1
        RETURN unit_id, size(units) as count, [u in units | id(u)] as node_ids
        ORDER BY count DESC
        """)
        
        if duplicate_units:
            print(f"   Found {len(duplicate_units)} duplicate unit IDs")
            
            # For each duplicate, keep the first one and delete others
            for dup in duplicate_units:
                unit_id = dup['unit_id']
                node_ids = dup['node_ids']
                count = dup['count']
                
                print(f"   Cleaning unit_id '{unit_id}' ({count} duplicates)")
                
                # Keep the first node, delete the rest
                nodes_to_delete = node_ids[1:]  # Skip first one
                
                for node_id in nodes_to_delete:
                    # Delete the duplicate node
                    storage.query("""
                    MATCH (mu:MeaningfulUnit)
                    WHERE id(mu) = $node_id
                    DETACH DELETE mu
                    """, {"node_id": node_id})
                    print(f"     Deleted node {node_id}")
        else:
            print("   No MeaningfulUnit duplicates found")
        
        # 4. Handle Episode duplicates
        print("\n4. Analyzing Episode duplicates...")
        duplicate_episodes = storage.query("""
        MATCH (e:Episode)
        WITH e.title as title, collect(e) as episodes
        WHERE size(episodes) > 1 AND title IS NOT NULL
        RETURN title, size(episodes) as count, [ep in episodes | {id: ep.id, node_id: id(ep)}] as episodes_info
        ORDER BY count DESC
        """)
        
        if duplicate_episodes:
            print(f"   Found {len(duplicate_episodes)} episodes with duplicate titles")
            
            for dup in duplicate_episodes:
                title = dup['title']
                episodes_info = dup['episodes_info']
                count = dup['count']
                
                print(f"   Episode '{title}' has {count} duplicates:")
                for ep in episodes_info:
                    print(f"     - ID: {ep['id']}")
                
                # Keep the first episode, merge/delete others
                keep_episode = episodes_info[0]
                duplicate_episodes_to_handle = episodes_info[1:]
                
                print(f"   Keeping episode: {keep_episode['id']}")
                
                for dup_ep in duplicate_episodes_to_handle:
                    print(f"   Moving MeaningfulUnits from {dup_ep['id']} to {keep_episode['id']}")
                    
                    # Move all MeaningfulUnits to the kept episode
                    storage.query("""
                    MATCH (mu:MeaningfulUnit)-[r:PART_OF]->(e:Episode)
                    WHERE id(e) = $dup_node_id
                    MATCH (keep_episode:Episode)
                    WHERE id(keep_episode) = $keep_node_id
                    DELETE r
                    CREATE (mu)-[:PART_OF]->(keep_episode)
                    """, {
                        "dup_node_id": dup_ep['node_id'],
                        "keep_node_id": keep_episode['node_id']
                    })
                    
                    # Delete the duplicate episode
                    storage.query("""
                    MATCH (e:Episode)
                    WHERE id(e) = $node_id
                    DETACH DELETE e
                    """, {"node_id": dup_ep['node_id']})
                    
                    print(f"     Deleted duplicate episode {dup_ep['id']}")
        else:
            print("   No duplicate episode titles found")
        
        # 5. Final verification
        print("\n5. Final verification...")
        
        # Count final state
        summary = storage.query("""
        MATCH (e:Episode)
        OPTIONAL MATCH (mu:MeaningfulUnit)-[:PART_OF]->(e)
        RETURN count(DISTINCT e) as episodes, count(mu) as units
        """)
        
        if summary:
            result = summary[0]
            print(f"   Final state: {result['episodes']} episodes, {result['units']} meaningful units")
        
        # Check for remaining duplicates
        remaining_dups = storage.query("""
        MATCH (mu:MeaningfulUnit)
        WITH mu.id as unit_id, count(*) as count
        WHERE count > 1
        RETURN count(*) as duplicate_count
        """)
        
        dup_count = remaining_dups[0]['duplicate_count'] if remaining_dups else 0
        if dup_count == 0:
            print("   ✅ No remaining duplicates")
        else:
            print(f"   ❌ Still {dup_count} duplicate unit IDs")
        
        print("\n=== Fix Complete ===")
        print("Next steps:")
        print("1. The database now has proper constraints")
        print("2. Duplicates have been cleaned up")
        print("3. Future processing should prevent duplicates")
        print("4. Consider modifying create_meaningful_unit() to use MERGE instead of CREATE")
        
    except Exception as e:
        print(f"Error fixing duplicates: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        storage.close()

if __name__ == "__main__":
    fix_database_duplicates()