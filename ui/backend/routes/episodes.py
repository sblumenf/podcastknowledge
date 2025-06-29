from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import yaml
from pathlib import Path
from neo4j import GraphDatabase

router = APIRouter()

@router.get("/podcasts/{podcast_id}/episodes")
async def get_episodes(podcast_id: str) -> List[Dict[str, Any]]:
    """
    Get all episodes from the podcast's Neo4j database.
    Neo4j is the source of truth for episodes.
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
        
        # Connect to Neo4j and query for episodes (meaningful units)
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
        episodes = []
        with driver.session() as session:
            # Query for all MeaningfulUnit nodes
            result = session.run("""
                MATCH (m:MeaningfulUnit)
                RETURN m.id as id, m.name as title
                ORDER BY m.name
            """)
            
            for record in result:
                episodes.append({
                    'id': record['id'],
                    'title': record['title'] or f"Episode {record['id']}"
                })
        
        driver.close()
        return episodes
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Podcasts configuration file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving episodes: {str(e)}")