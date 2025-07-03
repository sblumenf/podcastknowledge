from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import yaml
from pathlib import Path
from neo4j import GraphDatabase

router = APIRouter()

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
            # Query 1: Get clusters with connection counts
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
                       connections
                ORDER BY c.member_count DESC
            """)
            
            for record in cluster_result:
                clusters.append({
                    'id': record['id'],
                    'label': record['label'],
                    'size': record['member_count'],
                    'connections': record['connections']
                })
            
            # Query 2: Get edges between clusters based on shared episodes
            edge_result = session.run("""
                MATCH (c1:Cluster)<-[:IN_CLUSTER]-(m1:MeaningfulUnit)-[:PART_OF]->(e:Episode)
                MATCH (e)<-[:PART_OF]-(m2:MeaningfulUnit)-[:IN_CLUSTER]->(c2:Cluster)
                WHERE c1.id < c2.id
                WITH c1.id as source, c2.id as target, count(DISTINCT e) as weight
                WHERE weight > 0
                RETURN source, target, weight
                ORDER BY weight DESC
                LIMIT 100
            """)
            
            for record in edge_result:
                edges.append({
                    'source': record['source'],
                    'target': record['target'],
                    'weight': record['weight']
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