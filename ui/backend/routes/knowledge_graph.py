from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import yaml
from pathlib import Path
from neo4j import GraphDatabase
import math

router = APIRouter()

@router.get("/podcasts/{podcast_id}/clusters/{cluster_id}/meaningful-units")
async def get_cluster_meaningful_units(
    podcast_id: str, 
    cluster_id: str,
    k: int = 10
) -> Dict[str, Any]:
    """
    Get top K MeaningfulUnits for a cluster ranked by centroid distance.
    Includes sentiment data for each unit.
    """
    try:
        # Load podcast configuration
        config_path = Path(__file__).parent.parent.parent.parent / "seeding_pipeline" / "config" / "podcasts.yaml"
        
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Find the podcast configuration
        podcast_config = None
        for podcast in config.get('podcasts', []):
            if podcast.get('id') == podcast_id:
                podcast_config = podcast
                break
        
        if not podcast_config:
            raise HTTPException(status_code=404, detail=f"Podcast {podcast_id} not found")
        
        # Get database connection details
        neo4j_uri = f"bolt://localhost:{podcast_config['database']['neo4j_port']}"
        neo4j_user = "neo4j"
        neo4j_password = podcast_config['database']['neo4j_password']
        
        # Connect to Neo4j
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
        meaningful_units = []
        
        with driver.session() as session:
            # Query for meaningful units with sentiment data
            result = session.run("""
                MATCH (c:Cluster {id: $cluster_id})
                MATCH (c)<-[:IN_CLUSTER]-(mu:MeaningfulUnit)
                OPTIONAL MATCH (mu)-[:HAS_SENTIMENT]->(s:Sentiment)
                WITH c, mu, s,
                     gds.similarity.cosine(mu.embedding, c.centroid) as similarity
                RETURN mu.id as id,
                       mu.text as text,
                       mu.summary as summary,
                       mu.embedding as embedding,
                       mu.start_time as start_time,
                       mu.end_time as end_time,
                       mu.episode_id as episode_id,
                       s.polarity as sentiment_polarity,
                       s.score as sentiment_score,
                       s.energy_level as sentiment_energy_level,
                       s.engagement_level as sentiment_engagement_level,
                       similarity
                ORDER BY similarity DESC
                LIMIT $k
            """, cluster_id=cluster_id, k=k)
            
            for record in result:
                unit = {
                    'id': record['id'],
                    'text': record['text'],
                    'summary': record['summary'],
                    'embedding': record['embedding'],
                    'start_time': record['start_time'],
                    'end_time': record['end_time'],
                    'episode_id': record['episode_id'],
                    'similarity': record['similarity'],
                    'sentiment': {
                        'polarity': record['sentiment_polarity'] or 0,
                        'score': record['sentiment_score'] or 0,
                        'energy_level': record['sentiment_energy_level'] or 0,
                        'engagement_level': record['sentiment_engagement_level'] or 0
                    }
                }
                meaningful_units.append(unit)
        
        driver.close()
        
        return {
            'cluster_id': cluster_id,
            'meaningful_units': meaningful_units,
            'count': len(meaningful_units)
        }
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Podcasts configuration file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving meaningful units: {str(e)}")

@router.get("/podcasts/{podcast_id}/knowledge-graph")
async def get_knowledge_graph(podcast_id: str) -> Dict[str, Any]:
    """
    Get cluster-based knowledge graph data for visualization.
    Returns clusters with their interconnectedness levels and edges between clusters.
    """
    try:
        # Load podcast configuration
        config_path = Path(__file__).parent.parent.parent.parent / "seeding_pipeline" / "config" / "podcasts.yaml"
        
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Find the podcast configuration
        podcast_config = None
        for podcast in config.get('podcasts', []):
            if podcast.get('id') == podcast_id:
                podcast_config = podcast
                break
        
        if not podcast_config:
            raise HTTPException(status_code=404, detail=f"Podcast {podcast_id} not found")
        
        # Get database connection details
        neo4j_uri = f"bolt://localhost:{podcast_config['database']['neo4j_port']}"
        neo4j_user = "neo4j"
        neo4j_password = podcast_config['database']['neo4j_password']
        
        # Connect to Neo4j and query for clusters
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
        clusters = []
        edges = []
        
        with driver.session() as session:
            # Query 1: Get clusters with connection counts and centroid
            cluster_result = session.run("""
                MATCH (c:Cluster)
                WITH c
                OPTIONAL MATCH (c)<-[:IN_CLUSTER]-(m1:MeaningfulUnit)-[:PART_OF]->(e:Episode)
                OPTIONAL MATCH (e)<-[:PART_OF]-(m2:MeaningfulUnit)-[:IN_CLUSTER]->(c2:Cluster)
                WHERE c.id <> c2.id
                WITH c, count(DISTINCT c2) as connections
                RETURN c.id as id, 
                       c.label as label, 
                       c.member_count as member_count,
                       c.centroid as centroid,
                       connections
                ORDER BY c.member_count DESC
            """)
            
            for record in cluster_result:
                clusters.append({
                    'id': record['id'],
                    'label': record['label'],
                    'size': record['member_count'],
                    'centroid': record['centroid'],
                    'connections': record['connections']
                })
            
            # Query 2: Get edges between clusters based on shared episodes
            edge_result = session.run("""
                MATCH (c1:Cluster)<-[:IN_CLUSTER]-(m1:MeaningfulUnit)-[:PART_OF]->(e:Episode)
                MATCH (e)<-[:PART_OF]-(m2:MeaningfulUnit)-[:IN_CLUSTER]->(c2:Cluster)
                WHERE c1.id < c2.id
                WITH c1.id as source, c2.id as target, count(DISTINCT e) as shared_count
                WHERE shared_count > 0
                RETURN source, target, shared_count
                ORDER BY shared_count DESC
                LIMIT 100
            """)
            
            # Find max shared count for normalization
            edge_records = list(edge_result)
            max_shared = max([record['shared_count'] for record in edge_records]) if edge_records else 1
            
            for record in edge_records:
                # Apply logarithmic scaling: weight = log10(shared_count + 1) / log10(max_shared + 1)
                shared_count = record['shared_count']
                normalized_weight = math.log10(shared_count + 1) / math.log10(max_shared + 1)
                
                edges.append({
                    'source': record['source'],
                    'target': record['target'],
                    'weight': normalized_weight,
                    'shared_count': shared_count  # Keep raw count for reference
                })
        
        driver.close()
        
        return {
            'clusters': clusters,
            'edges': edges
        }
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Podcasts configuration file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving knowledge graph: {str(e)}")