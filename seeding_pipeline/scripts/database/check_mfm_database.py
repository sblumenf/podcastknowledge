#!/usr/bin/env python3
"""Check the MFM database for the AI episode and overall statistics."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig

def check_mfm_database():
    """Check MFM database contents and AI episode specifically."""
    
    # Use MFM database connection (port 7688)
    storage = GraphStorageService(
        uri="neo4j://localhost:7688",
        username="neo4j",  # Assuming standard credentials
        password="password"  # This might need to be adjusted
    )
    
    try:
        # Connect to database
        storage.connect()
        print("Connected to MFM Neo4j database (port 7688)")
        
        # Get all episodes
        print("\n=== ALL MFM EPISODES IN DATABASE ===")
        
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
                print("No episodes found in MFM database!")
                return
            
            print(f"Found {len(episodes)} MFM episodes:")
            
            ai_episode = None
            for record in episodes:
                duration_min = record['duration'] / 60 if record['duration'] else 0
                print(f"\nEpisode: {record['episode_id']}")
                print(f"  Title: {record['title']}")
                print(f"  Duration: {duration_min:.1f} minutes")
                print(f"  Units: {record['units']}")
                print(f"  Entities: {record['entities']}")
                print(f"  Quotes: {record['quotes']}")
                print(f"  Insights: {record['insights']}")
                
                # Check if this is the AI episode
                if record['title'] and "AI" in record['title'] and "Smartest Founders" in record['title']:
                    ai_episode = record
                
                # Flag potential issues
                if record['units'] == 1:
                    print("  ⚠️  WARNING: Only 1 meaningful unit (potential fallback)")
                elif record['units'] == 0:
                    print("  ⚠️  WARNING: No meaningful units")
        
        # Detailed analysis of AI episode if found
        if ai_episode:
            print(f"\n=== DETAILED AI EPISODE ANALYSIS ===")
            print(f"Episode: {ai_episode['title']}")
            print(f"Duration: {ai_episode['duration']/60:.1f} minutes")
            print(f"Meaningful Units: {ai_episode['units']}")
            
            if ai_episode['units'] == 1:
                print("⚠️  This episode has only 1 meaningful unit - likely a fallback structure!")
                print("This suggests the conversation analyzer failed for this episode too.")
            elif ai_episode['units'] == 0:
                print("⚠️  This episode has no meaningful units - processing failed!")
            else:
                print(f"✅ This episode appears to have been processed normally with {ai_episode['units']} units")
        else:
            print(f"\n❌ AI episode not found in database")
            print("This means it failed to process and wasn't stored")
        
        # Summary statistics
        print(f"\n=== MFM DATABASE SUMMARY ===")
        total_episodes = len(episodes)
        
        if episodes:
            unit_counts = [e['units'] for e in episodes]
            avg_units = sum(unit_counts) / len(unit_counts)
            max_units = max(unit_counts)
            min_units = min(unit_counts)
            
            print(f"Total episodes: {total_episodes}")
            print(f"Average meaningful units per episode: {avg_units:.1f}")
            print(f"Range: {min_units} - {max_units} units")
            
            # Count problematic episodes
            fallback_count = sum(1 for count in unit_counts if count == 1)
            no_units_count = sum(1 for count in unit_counts if count == 0)
            normal_count = sum(1 for count in unit_counts if count > 1)
            
            print(f"Normal episodes (>1 unit): {normal_count}")
            if fallback_count > 0:
                print(f"⚠️  Fallback episodes (1 unit): {fallback_count}")
            if no_units_count > 0:
                print(f"⚠️  Failed episodes (0 units): {no_units_count}")
            
            # Show distribution
            print(f"\nMeaningful unit distribution:")
            from collections import Counter
            distribution = Counter(unit_counts)
            for count, freq in sorted(distribution.items()):
                print(f"  {count} units: {freq} episodes")
        
    except Exception as e:
        print(f"Error checking MFM database: {e}")
        print("This might be a connection issue - checking if MFM database is running...")
        import traceback
        traceback.print_exc()
    finally:
        try:
            storage.disconnect()
        except:
            pass

if __name__ == "__main__":
    check_mfm_database()