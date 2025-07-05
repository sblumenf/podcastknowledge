#!/usr/bin/env python3
"""Comprehensive check of both databases with correct relationship patterns."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.storage.graph_storage import GraphStorageService

def check_database(name, port):
    """Check a specific database with correct schema queries."""
    print(f"\n{'='*60}")
    print(f"CHECKING {name.upper()} DATABASE (port {port})")
    print(f"{'='*60}")
    
    storage = GraphStorageService(
        uri=f"neo4j://localhost:{port}",
        username="neo4j",
        password="password"
    )
    
    try:
        storage.connect()
        print(f"✅ Connected to {name} database")
        
        with storage.session() as session:
            # First, let's see what node types exist
            print(f"\n--- NODE TYPES IN {name.upper()} ---")
            result = session.run("CALL db.labels()")
            labels = [record['label'] for record in result]
            print(f"Available labels: {labels}")
            
            # Let's see what relationship types exist
            print(f"\n--- RELATIONSHIP TYPES IN {name.upper()} ---")
            result = session.run("CALL db.relationshipTypes()")
            rel_types = [record['relationshipType'] for record in result]
            print(f"Available relationships: {rel_types}")
            
            # Count episodes
            result = session.run("MATCH (e:Episode) RETURN count(e) as episode_count")
            episode_count = result.single()['episode_count']
            print(f"\n--- EPISODE COUNT ---")
            print(f"Total episodes: {episode_count}")
            
            if episode_count == 0:
                print("No episodes found!")
                return
            
            # Get sample episode to understand schema
            print(f"\n--- SAMPLE EPISODE SCHEMA ---")
            result = session.run("MATCH (e:Episode) RETURN e LIMIT 1")
            sample = result.single()
            if sample:
                episode = sample['e']
                print(f"Sample episode properties: {list(episode.keys())}")
            
            # Count meaningful units using the correct relationship
            print(f"\n--- MEANINGFUL UNIT ANALYSIS ---")
            
            # Try different relationship patterns to find the correct one
            relationship_patterns = [
                "CONTAINS",
                "HAS_UNIT", 
                "HAS_MEANINGFUL_UNIT",
                "INCLUDES"
            ]
            
            units_found = False
            for rel_pattern in relationship_patterns:
                try:
                    result = session.run(f"""
                        MATCH (e:Episode)-[:{rel_pattern}]->(u:MeaningfulUnit)
                        RETURN count(u) as unit_count, count(DISTINCT e) as episodes_with_units
                    """)
                    record = result.single()
                    if record and record['unit_count'] > 0:
                        print(f"✅ Found {record['unit_count']} meaningful units using relationship '{rel_pattern}'")
                        print(f"   Episodes with units: {record['episodes_with_units']}")
                        units_found = True
                        
                        # Get distribution
                        result = session.run(f"""
                            MATCH (e:Episode)-[:{rel_pattern}]->(u:MeaningfulUnit)
                            WITH e, count(u) as unit_count
                            RETURN unit_count, count(e) as episode_count
                            ORDER BY unit_count
                        """)
                        
                        print(f"   Unit distribution:")
                        for record in result:
                            print(f"     {record['unit_count']} units: {record['episode_count']} episodes")
                        break
                except Exception as e:
                    continue
            
            if not units_found:
                # Check if MeaningfulUnit nodes exist at all
                result = session.run("MATCH (u:MeaningfulUnit) RETURN count(u) as total_units")
                total_units = result.single()['total_units']
                print(f"Total MeaningfulUnit nodes (unconnected): {total_units}")
                
                if total_units > 0:
                    print("⚠️  MeaningfulUnit nodes exist but aren't connected to episodes!")
                else:
                    print("❌ No MeaningfulUnit nodes found")
            
            # Check for entities and other knowledge components
            print(f"\n--- KNOWLEDGE COMPONENTS ---")
            knowledge_types = ['Entity', 'Quote', 'Insight']
            for k_type in knowledge_types:
                try:
                    result = session.run(f"MATCH (n:{k_type}) RETURN count(n) as count")
                    count = result.single()['count']
                    print(f"{k_type} nodes: {count}")
                except:
                    print(f"{k_type} nodes: 0 (or label doesn't exist)")
            
            # List some episode titles to verify content
            print(f"\n--- SAMPLE EPISODES ---")
            result = session.run("""
                MATCH (e:Episode) 
                RETURN e.title as title, e.episode_id as episode_id
                ORDER BY e.title 
                LIMIT 5
            """)
            
            for i, record in enumerate(result, 1):
                title = record['title'] or 'No title'
                episode_id = record['episode_id'] or 'No ID'
                print(f"{i}. {title[:60]}..." if len(title) > 60 else f"{i}. {title}")
                print(f"   ID: {episode_id}")
    
    except Exception as e:
        print(f"❌ Error checking {name} database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            storage.disconnect()
        except:
            pass

def main():
    """Check both databases comprehensively."""
    print("COMPREHENSIVE DATABASE ANALYSIS")
    print("Checking both Mel Robbins and MFM databases...")
    
    # Check Mel Robbins database (port 7687)
    check_database("Mel Robbins", 7687)
    
    # Check MFM database (port 7688)  
    check_database("MFM", 7688)
    
    print(f"\n{'='*60}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()