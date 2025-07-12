from fastapi import APIRouter, HTTPException
from neo4j import GraphDatabase
import os
import yaml
from pathlib import Path
from typing import Dict, List, Any

router = APIRouter()

# Load podcast configuration
def get_podcast_config():
    config_path = os.environ.get('PODCASTS_CONFIG_PATH', 
        '/home/sergeblumenfeld/podcastknowledge/seeding_pipeline/config/podcasts.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def get_driver_for_podcast(podcast_id: str):
    config = get_podcast_config()
    
    # Find the podcast configuration
    podcast_config = None
    for podcast in config['podcasts']:
        if podcast['id'] == podcast_id:
            podcast_config = podcast
            break
    
    if not podcast_config:
        raise HTTPException(status_code=404, detail=f"Podcast {podcast_id} not found in configuration")
    
    # Get database configuration
    db_config = podcast_config['database']
    uri = f"bolt://localhost:{db_config['neo4j_port']}"
    password = db_config.get('neo4j_password', 'password')
    
    return GraphDatabase.driver(uri, auth=("neo4j", password))

@router.get("/podcasts/{podcast_id}/meaningful-units")
async def get_podcast_meaningful_units(podcast_id: str) -> Dict[str, Any]:
    """Get all meaningful units for a specific podcast with cluster relationships."""
    
    driver = get_driver_for_podcast(podcast_id)
    
    try:
        with driver.session() as session:
            # Query without podcast filter since each podcast has its own database
            query = """
            MATCH (e:Episode)
            MATCH (m:MeaningfulUnit)-[:PART_OF]->(e)
            OPTIONAL MATCH (m)-[:IN_CLUSTER]->(c:Cluster)
            WITH m, c.id as cluster_id
            ORDER BY cluster_id, m.id
            WITH cluster_id, collect({
                id: m.id,
                summary: m.summary,
                themes: m.themes,
                cluster_id: cluster_id
            }) as units
            RETURN collect({
                cluster_id: cluster_id,
                units: units
            }) as clusters
            """
            
            result = session.run(query)
            record = result.single()
            
            if not record:
                raise HTTPException(status_code=404, detail="No data found")
            
            clusters_data = record["clusters"]
            
            # Build nodes and links
            nodes = []
            links = []
            seen_units = set()
            
            for cluster_group in clusters_data:
                cluster_units = cluster_group["units"]
                cluster_id = cluster_group["cluster_id"]
                
                # Add nodes
                for unit in cluster_units:
                    if unit["id"] not in seen_units:
                        nodes.append({
                            "id": unit["id"],
                            "name": unit["summary"][:100] + "..." if unit["summary"] and len(unit["summary"]) > 100 else unit["summary"] or "No summary",
                            "cluster": cluster_id or 0,  # Use 0 for unclustered units
                            "themes": unit["themes"]
                        })
                        seen_units.add(unit["id"])
                
                # Create links between units in the same cluster
                if cluster_id is not None and len(cluster_units) > 1:
                    for i in range(len(cluster_units)):
                        for j in range(i + 1, len(cluster_units)):
                            links.append({
                                "source": cluster_units[i]["id"],
                                "target": cluster_units[j]["id"]
                            })
            
            return {
                "nodes": nodes,
                "links": links
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        driver.close()