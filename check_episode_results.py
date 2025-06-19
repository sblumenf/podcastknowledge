#!/usr/bin/env python3
"""Check the results of the processed episode in Neo4j."""

import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent / "seeding_pipeline"))

from src.storage.graph_storage import GraphStorageService

def check_episode_results():
    """Check what was stored for the processed episode."""
    
    # Initialize graph storage
    graph_storage = GraphStorageService(
        uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        username=os.getenv('NEO4J_USERNAME', 'neo4j'),
        password=os.getenv('NEO4J_PASSWORD', 'password')
    )
    
    try:
        graph_storage.connect()
        
        # Query for the episode
        query = """
        MATCH (e:Episode)
        WHERE e.podcast_name = 'The Mel Robbins Podcast' 
        AND e.title CONTAINS 'Feel Good in Your Body'
        RETURN e.episode_id, e.title, e.processing_timestamp
        ORDER BY e.processing_timestamp DESC
        LIMIT 5
        """
        
        results = graph_storage.query(query)
        
        if results:
            print(f"Found {len(results)} episodes:")
            for i, result in enumerate(results):
                print(f"\n{i+1}. Episode ID: {result['e.episode_id']}")
                print(f"   Title: {result['e.title']}")
                print(f"   Processed: {result['e.processing_timestamp']}")
                
                # Get statistics for the most recent episode
                if i == 0:
                    episode_id = result['e.episode_id']
                    
                    # Count nodes and relationships
                    stats_query = """
                    MATCH (e:Episode {episode_id: $episode_id})
                    OPTIONAL MATCH (e)-[:HAS_UNIT]->(u:MeaningfulUnit)
                    OPTIONAL MATCH (u)-[:CONTAINS_ENTITY]->(ent:Entity)
                    OPTIONAL MATCH (u)-[:CONTAINS_QUOTE]->(q:Quote)
                    OPTIONAL MATCH (u)-[:CONTAINS_INSIGHT]->(ins:Insight)
                    OPTIONAL MATCH (e)-[:HAS_TOPIC]->(t:Topic)
                    OPTIONAL MATCH (e)<-[:SPOKEN_IN]-(s:Speaker)
                    WITH e, 
                         COUNT(DISTINCT u) as units,
                         COUNT(DISTINCT ent) as entities,
                         COUNT(DISTINCT q) as quotes,
                         COUNT(DISTINCT ins) as insights,
                         COUNT(DISTINCT t) as topics,
                         COUNT(DISTINCT s) as speakers
                    RETURN units, entities, quotes, insights, topics, speakers
                    """
                    
                    stats = graph_storage.query(stats_query, {"episode_id": episode_id})
                    
                    if stats:
                        print(f"\n   Statistics for most recent processing:")
                        print(f"   - Meaningful Units: {stats[0]['units']}")
                        print(f"   - Entities: {stats[0]['entities']}")
                        print(f"   - Quotes: {stats[0]['quotes']}")
                        print(f"   - Insights: {stats[0]['insights']}")
                        print(f"   - Topics: {stats[0]['topics']}")
                        print(f"   - Speakers: {stats[0]['speakers']}")
        else:
            print("No episodes found for 'The Mel Robbins Podcast' with 'Feel Good in Your Body' in title")
            
    finally:
        graph_storage.close()

if __name__ == "__main__":
    check_episode_results()