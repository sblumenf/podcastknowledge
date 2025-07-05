#!/usr/bin/env python3
"""Analyze episode meaningful unit distribution."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig

def analyze_units():
    """Analyze meaningful unit distribution across episodes."""
    
    config = PipelineConfig()
    storage = GraphStorageService(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password
    )
    
    try:
        storage.connect()
        print("Connected to Neo4j database")
        print("\n" + "="*80)
        
        with storage.session() as session:
            # Get all episodes and their meaningful unit counts
            result = session.run("""
                MATCH (e:Episode)
                OPTIONAL MATCH (e)<-[:BELONGS_TO]-(mu:MeaningfulUnit)
                WITH e, count(mu) as unit_count
                RETURN e.id as episode_id,
                       e.title as title,
                       e.youtube_url as url,
                       unit_count
                ORDER BY unit_count DESC
            """)
            episodes = list(result)
            
            print(f"Total episodes: {len(episodes)}")
            print(f"\nEpisode Unit Distribution:")
            print("-" * 80)
            
            # Group by unit count
            unit_distribution = {}
            for ep in episodes:
                count = ep['unit_count']
                if count not in unit_distribution:
                    unit_distribution[count] = []
                unit_distribution[count].append(ep)
            
            # Print distribution
            for unit_count in sorted(unit_distribution.keys(), reverse=True):
                eps = unit_distribution[unit_count]
                print(f"\n{unit_count} units: {len(eps)} episodes")
                if unit_count <= 1:  # Show episodes with 0-1 units
                    for ep in eps[:10]:  # Show up to 10
                        print(f"  - {ep['title'][:70]}...")
                        
            # Check for the 313-segment episode mentioned
            print("\n\nSearching for episodes that might be the 313-segment episode...")
            print("-" * 80)
            
            # Look for episodes with specific patterns in title
            long_ep_result = session.run("""
                MATCH (e:Episode)
                WHERE e.title CONTAINS 'Billionaire' OR 
                      e.title CONTAINS 'Mohnish' OR
                      e.title CONTAINS '$10,000' OR
                      e.title CONTAINS 'Turn'
                OPTIONAL MATCH (e)<-[:BELONGS_TO]-(mu:MeaningfulUnit)
                WITH e, count(mu) as unit_count
                RETURN e.id as episode_id,
                       e.title as title,
                       unit_count
            """)
            
            long_episodes = list(long_ep_result)
            if long_episodes:
                print("\nPotential matches for the 313-segment episode:")
                for ep in long_episodes:
                    print(f"  - {ep['title']}")
                    print(f"    Units: {ep['unit_count']}")
                    
            # Get overall statistics
            print("\n\nOVERALL STATISTICS:")
            print("=" * 80)
            
            stats_result = session.run("""
                MATCH (e:Episode)
                OPTIONAL MATCH (e)<-[:BELONGS_TO]-(mu:MeaningfulUnit)
                WITH e, count(mu) as unit_count
                RETURN 
                    avg(unit_count) as avg_units,
                    min(unit_count) as min_units,
                    max(unit_count) as max_units,
                    sum(unit_count) as total_units,
                    count(e) as total_episodes,
                    count(CASE WHEN unit_count = 0 THEN 1 END) as episodes_with_no_units,
                    count(CASE WHEN unit_count = 1 THEN 1 END) as episodes_with_one_unit,
                    count(CASE WHEN unit_count > 1 THEN 1 END) as episodes_with_multiple_units
            """)
            
            stats = stats_result.single()
            print(f"Total Episodes: {stats['total_episodes']}")
            print(f"Total Meaningful Units: {stats['total_units']}")
            print(f"Average Units per Episode: {stats['avg_units']:.2f}")
            print(f"Min Units: {stats['min_units']}")
            print(f"Max Units: {stats['max_units']}")
            print(f"\nBreakdown:")
            print(f"  Episodes with 0 units: {stats['episodes_with_no_units']}")
            print(f"  Episodes with 1 unit: {stats['episodes_with_one_unit']}")
            print(f"  Episodes with >1 units: {stats['episodes_with_multiple_units']}")
            
        print("\n" + "="*80)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        storage.disconnect()

if __name__ == "__main__":
    analyze_units()