#!/usr/bin/env python3
"""Explore possible connections between clusters"""

from neo4j import GraphDatabase
import yaml
from pathlib import Path

# Load podcast configuration
config_path = Path(__file__).parent / "seeding_pipeline" / "config" / "podcasts.yaml"

with open(config_path, 'r') as file:
    config = yaml.safe_load(file)

# Find the mel robbins podcast configuration  
podcast_config = None
for podcast in config.get('podcasts', []):
    if podcast.get('id') == 'mel_robbins_podcast':
        podcast_config = podcast
        break

if podcast_config:
    neo4j_uri = f"bolt://localhost:{podcast_config['database']['neo4j_port']}"
    neo4j_user = "neo4j"
    neo4j_password = podcast_config['database']['neo4j_password']
    
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    with driver.session() as session:
        # 1. Check temporal proximity - MeaningfulUnits that are close in time
        print("1. Temporal proximity connections:")
        result = session.run("""
            MATCH (c1:Cluster)<-[:IN_CLUSTER]-(m1:MeaningfulUnit)
            MATCH (c2:Cluster)<-[:IN_CLUSTER]-(m2:MeaningfulUnit)
            WHERE c1.id < c2.id 
            AND m1.episode_id = m2.episode_id
            AND abs(m1.start_time - m2.end_time) < 60  // Within 60 seconds
            WITH c1.id as source, c2.id as target, count(*) as connections
            WHERE connections > 0
            RETURN source, target, connections
            ORDER BY connections DESC
            LIMIT 5
        """)
        for record in result:
            print(f"  {record['source']} <-> {record['target']}: {record['connections']} temporal connections")
            
        # 2. Check semantic similarity through embeddings
        print("\n2. Checking for embeddings:")
        result = session.run("""
            MATCH (m:MeaningfulUnit)
            WHERE m.embedding IS NOT NULL
            RETURN count(m) as embedding_count
        """)
        for record in result:
            print(f"  MeaningfulUnits with embeddings: {record['embedding_count']}")
            
        # 3. Check shared quotes
        print("\n3. Shared quotes between clusters:")
        result = session.run("""
            MATCH (c1:Cluster)<-[:IN_CLUSTER]-(m1:MeaningfulUnit)<-[:EXTRACTED_FROM]-(q:Quote)
            MATCH (q)-[:EXTRACTED_FROM]->(m2:MeaningfulUnit)-[:IN_CLUSTER]->(c2:Cluster)
            WHERE c1.id < c2.id
            WITH c1.id as source, c2.id as target, count(DISTINCT q) as shared_quotes
            WHERE shared_quotes > 0
            RETURN source, target, shared_quotes
            ORDER BY shared_quotes DESC
            LIMIT 5
        """)
        for record in result:
            print(f"  {record['source']} <-> {record['target']}: {record['shared_quotes']} shared quotes")
            
        # 4. Check shared insights
        print("\n4. Shared insights between clusters:")
        result = session.run("""
            MATCH (c1:Cluster)<-[:IN_CLUSTER]-(m1:MeaningfulUnit)<-[:EXTRACTED_FROM]-(i:Insight)
            MATCH (i)-[:EXTRACTED_FROM]->(m2:MeaningfulUnit)-[:IN_CLUSTER]->(c2:Cluster)
            WHERE c1.id < c2.id
            WITH c1.id as source, c2.id as target, count(DISTINCT i) as shared_insights
            WHERE shared_insights > 0
            RETURN source, target, shared_insights
            ORDER BY shared_insights DESC
            LIMIT 5
        """)
        for record in result:
            print(f"  {record['source']} <-> {record['target']}: {record['shared_insights']} shared insights")
            
        # 5. Check cluster centroids
        print("\n5. Cluster embeddings (for semantic similarity):")
        result = session.run("""
            MATCH (c:Cluster)
            WHERE c.centroid IS NOT NULL
            RETURN c.id as cluster_id, size(c.centroid) as embedding_size
            ORDER BY cluster_id
            LIMIT 5
        """)
        for record in result:
            print(f"  {record['cluster_id']}: embedding size {record['embedding_size']}")
    
    driver.close()