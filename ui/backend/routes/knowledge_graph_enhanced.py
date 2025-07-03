from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import yaml
from pathlib import Path
from neo4j import GraphDatabase
import numpy as np

router = APIRouter()

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    if not vec1 or not vec2:
        return 0.0
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot_product / (norm1 * norm2))

@router.get("/podcasts/{podcast_id}/knowledge-graph-enhanced")
async def get_enhanced_knowledge_graph(
    podcast_id: str,
    connection_type: Optional[str] = "hybrid"
) -> Dict[str, Any]:
    """
    Get cluster-based knowledge graph with multiple connection types.
    
    connection_type options:
    - episodes: Shared episodes (default)
    - temporal: Temporal proximity within episodes
    - semantic: Semantic similarity based on embeddings
    - hybrid: Combination of all types
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
        
        clusters = []
        edges = []
        
        with driver.session() as session:
            # Get clusters with their embeddings (centroid)
            cluster_result = session.run("""
                MATCH (c:Cluster)
                RETURN c.id as id, 
                       c.label as label, 
                       c.member_count as member_count,
                       c.centroid as embedding
                ORDER BY c.member_count DESC
            """)
            
            cluster_embeddings = {}
            for record in cluster_result:
                cluster_id = record['id']
                clusters.append({
                    'id': cluster_id,
                    'label': record['label'],
                    'size': record['member_count'],
                    'connections': 0  # Will be calculated based on edges
                })
                if record['embedding']:
                    cluster_embeddings[cluster_id] = record['embedding']
            
            # Calculate connections based on type
            if connection_type in ["episodes", "hybrid"]:
                # Episode-based connections
                edge_result = session.run("""
                    MATCH (c1:Cluster)<-[:IN_CLUSTER]-(m1:MeaningfulUnit)-[:PART_OF]->(e:Episode)
                    MATCH (e)<-[:PART_OF]-(m2:MeaningfulUnit)-[:IN_CLUSTER]->(c2:Cluster)
                    WHERE c1.id < c2.id
                    WITH c1.id as source, c2.id as target, count(DISTINCT e) as weight
                    WHERE weight > 0
                    RETURN source, target, weight, 'episode' as type
                    ORDER BY weight DESC
                    LIMIT 50
                """)
                
                for record in edge_result:
                    edges.append({
                        'source': record['source'],
                        'target': record['target'],
                        'weight': record['weight'],
                        'type': record['type']
                    })
            
            if connection_type in ["temporal", "hybrid"]:
                # Temporal proximity connections
                edge_result = session.run("""
                    MATCH (c1:Cluster)<-[:IN_CLUSTER]-(m1:MeaningfulUnit)
                    MATCH (c2:Cluster)<-[:IN_CLUSTER]-(m2:MeaningfulUnit)
                    WHERE c1.id < c2.id 
                    AND m1.episode_id = m2.episode_id
                    AND abs(m1.start_time - m2.end_time) < 30
                    WITH c1.id as source, c2.id as target, count(*) as weight
                    WHERE weight > 0
                    RETURN source, target, weight, 'temporal' as type
                    ORDER BY weight DESC
                    LIMIT 30
                """)
                
                for record in edge_result:
                    # Only add if not already connected by episodes
                    if not any(e['source'] == record['source'] and e['target'] == record['target'] for e in edges):
                        edges.append({
                            'source': record['source'],
                            'target': record['target'],
                            'weight': record['weight'] * 0.5,  # Lower weight for temporal
                            'type': record['type']
                        })
            
            if connection_type in ["semantic", "hybrid"]:
                # Semantic similarity connections
                similarity_threshold = 0.7
                cluster_ids = list(cluster_embeddings.keys())
                
                for i in range(len(cluster_ids)):
                    for j in range(i + 1, len(cluster_ids)):
                        id1, id2 = cluster_ids[i], cluster_ids[j]
                        if id1 in cluster_embeddings and id2 in cluster_embeddings:
                            similarity = cosine_similarity(
                                cluster_embeddings[id1],
                                cluster_embeddings[id2]
                            )
                            if similarity > similarity_threshold:
                                # Only add if not already connected
                                if not any(
                                    (e['source'] == id1 and e['target'] == id2) or 
                                    (e['source'] == id2 and e['target'] == id1) 
                                    for e in edges
                                ):
                                    edges.append({
                                        'source': id1,
                                        'target': id2,
                                        'weight': similarity * 10,  # Scale for visibility
                                        'type': 'semantic'
                                    })
            
            # Update connection counts for clusters
            for cluster in clusters:
                cluster_id = cluster['id']
                connection_count = sum(
                    1 for edge in edges 
                    if edge['source'] == cluster_id or edge['target'] == cluster_id
                )
                cluster['connections'] = connection_count
        
        driver.close()
        
        return {
            'clusters': clusters,
            'edges': edges,
            'connection_type': connection_type
        }
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Podcasts configuration file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving knowledge graph: {str(e)}")