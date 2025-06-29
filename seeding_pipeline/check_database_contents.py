#!/usr/bin/env python3
"""Check what episodes are actually in the Neo4j database."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig

def check_database_contents():
    """Check what's actually in the database."""
    
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
        
        # Get all episodes
        print("\n=== ALL EPISODES IN DATABASE ===")
        
        with storage.session() as session:
            result = session.run("""
                MATCH (e:Episode)
                OPTIONAL MATCH (e)-[:CONTAINS]->(u:MeaningfulUnit)
                OPTIONAL MATCH (u)-[:MENTIONED_IN]-(ent:Entity)
                OPTIONAL MATCH (u)-[:CONTAINS_QUOTE]->(q:Quote)
                OPTIONAL MATCH (u)-[:CONTAINS_INSIGHT]->(i:Insight)
                WITH e, 
                     count(DISTINCT u) as units,
                     count(DISTINCT ent) as entities, 
                     count(DISTINCT q) as quotes,
                     count(DISTINCT i) as insights
                RETURN e.episode_id as episode_id, e.title as title, 
                       e.duration_seconds as duration, e.podcast_title as podcast,
                       units, entities, quotes, insights
                ORDER BY e.episode_id
            """)
            
            episodes = list(result)
            
            if not episodes:
                print("No episodes found in database!")
                return
            
            print(f"Found {len(episodes)} episodes:")
            
            for record in episodes:
                duration_min = record['duration'] / 60 if record['duration'] else 0
                print(f"\nEpisode: {record['episode_id']}")
                print(f"  Title: {record['title']}")
                print(f"  Podcast: {record['podcast']}")
                print(f"  Duration: {duration_min:.1f} minutes")
                print(f"  Units: {record['units']}")
                print(f"  Entities: {record['entities']}")
                print(f"  Quotes: {record['quotes']}")
                print(f"  Insights: {record['insights']}")
                
                # Flag potential issues
                if record['units'] == 1:
                    print("  ⚠️  WARNING: Only 1 meaningful unit (potential fallback)")
                elif record['units'] == 0:
                    print("  ⚠️  WARNING: No meaningful units")
        
        # Summary statistics
        print(f"\n=== SUMMARY STATISTICS ===")
        total_episodes = len(episodes)
        
        unit_counts = [e['units'] for e in episodes]
        
        if unit_counts:
            avg_units = sum(unit_counts) / len(unit_counts)
            max_units = max(unit_counts)
            min_units = min(unit_counts)
            
            print(f"Total episodes: {total_episodes}")
            print(f"Average meaningful units per episode: {avg_units:.1f}")
            print(f"Range: {min_units} - {max_units} units")
            
            # Count problematic episodes
            fallback_count = sum(1 for count in unit_counts if count == 1)
            no_units_count = sum(1 for count in unit_counts if count == 0)
            
            if fallback_count > 0:
                print(f"⚠️  Episodes with only 1 unit (potential fallbacks): {fallback_count}")
            if no_units_count > 0:
                print(f"⚠️  Episodes with no units: {no_units_count}")
            
            # Show distribution
            print(f"\nMeaningful unit distribution:")
            from collections import Counter
            distribution = Counter(unit_counts)
            for count, freq in sorted(distribution.items()):
                print(f"  {count} units: {freq} episodes")
        
    except Exception as e:
        print(f"Error checking database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        storage.disconnect()

if __name__ == "__main__":
    check_database_contents()