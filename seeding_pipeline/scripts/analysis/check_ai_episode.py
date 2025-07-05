#!/usr/bin/env python3
"""Check the AI episode status in Neo4j database."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig

def check_ai_episode():
    """Check status of the AI episode in database."""
    
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
        
        # Search for episodes with "AI" in the title
        print("\n=== SEARCHING FOR AI EPISODES ===")
        
        with storage.session() as session:
            result = session.run("""
                MATCH (e:Episode)
                WHERE e.title CONTAINS "AI" OR e.episode_id CONTAINS "AI"
                RETURN e.episode_id as episode_id, e.title as title
                ORDER BY e.episode_id
            """)
            
            ai_episodes = list(result)
            if not ai_episodes:
                print("No episodes with 'AI' found in database")
                return
            
            for record in ai_episodes:
                print(f"Found: {record['episode_id']}")
                print(f"  Title: {record['title']}")
        
        # Check the specific episode we're looking for
        target_episode = None
        for episode in ai_episodes:
            if "How_the_Smartest_Founders_Are_Quietly_Winning_with_AI" in episode['episode_id']:
                target_episode = episode['episode_id']
                break
        
        if not target_episode:
            print("\nTarget AI episode not found in database!")
            return
        
        print(f"\n=== ANALYZING EPISODE: {target_episode} ===")
        
        # Get detailed stats for this episode
        with storage.session() as session:
            result = session.run("""
                MATCH (e:Episode {episode_id: $episode_id})
                OPTIONAL MATCH (e)-[:CONTAINS]->(u:MeaningfulUnit)
                OPTIONAL MATCH (u)-[:MENTIONED_IN]-(ent:Entity)
                OPTIONAL MATCH (u)-[:CONTAINS_QUOTE]->(q:Quote)
                OPTIONAL MATCH (u)-[:CONTAINS_INSIGHT]->(i:Insight)
                WITH e, 
                     count(DISTINCT u) as units,
                     count(DISTINCT ent) as entities, 
                     count(DISTINCT q) as quotes,
                     count(DISTINCT i) as insights
                RETURN e.title as title, e.duration_seconds as duration,
                       units, entities, quotes, insights
            """, episode_id=target_episode)
            
            record = result.single()
            if record:
                print(f"Title: {record['title']}")
                print(f"Duration: {record['duration']:.1f} seconds ({record['duration']/60:.1f} minutes)")
                print(f"Meaningful Units: {record['units']}")
                print(f"Entities: {record['entities']}")
                print(f"Quotes: {record['quotes']}")
                print(f"Insights: {record['insights']}")
                
                # Check if this looks like a fallback (1 unit)
                if record['units'] == 1:
                    print("\n⚠️  WARNING: Only 1 meaningful unit - this may be a fallback structure!")
                elif record['units'] == 0:
                    print("\n⚠️  WARNING: No meaningful units found!")
                else:
                    print(f"\n✅ Normal episode structure with {record['units']} units")
        
        # Compare with other episodes for context
        print("\n=== COMPARISON WITH OTHER EPISODES ===")
        
        with storage.session() as session:
            result = session.run("""
                MATCH (e:Episode)
                OPTIONAL MATCH (e)-[:CONTAINS]->(u:MeaningfulUnit)
                WITH e, count(DISTINCT u) as units
                WHERE units > 0
                RETURN e.episode_id as episode_id, e.title as title, units, e.duration_seconds as duration
                ORDER BY units DESC
                LIMIT 10
            """)
            
            print("Top 10 episodes by meaningful unit count:")
            for record in result:
                duration_min = record['duration'] / 60 if record['duration'] else 0
                print(f"  {record['units']} units - {record['title'][:50]}... ({duration_min:.1f}min)")
        
        # Show episodes with exactly 1 unit (potential fallbacks)
        with storage.session() as session:
            result = session.run("""
                MATCH (e:Episode)
                OPTIONAL MATCH (e)-[:CONTAINS]->(u:MeaningfulUnit)
                WITH e, count(DISTINCT u) as units
                WHERE units = 1
                RETURN e.episode_id as episode_id, e.title as title, units, e.duration_seconds as duration
                ORDER BY e.title
            """)
            
            fallback_episodes = list(result)
            if fallback_episodes:
                print(f"\n⚠️  Episodes with only 1 meaningful unit (potential fallbacks): {len(fallback_episodes)}")
                for record in fallback_episodes:
                    duration_min = record['duration'] / 60 if record['duration'] else 0
                    print(f"  {record['title'][:50]}... ({duration_min:.1f}min)")
            else:
                print("\n✅ No episodes with only 1 meaningful unit found")
        
    except Exception as e:
        print(f"Error checking episode: {e}")
        import traceback
        traceback.print_exc()
    finally:
        storage.disconnect()

if __name__ == "__main__":
    check_ai_episode()