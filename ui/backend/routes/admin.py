from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from neo4j import GraphDatabase
import logging
import yaml
from pathlib import Path
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/podcasts")
async def get_podcasts() -> List[Dict[str, str]]:
    """Get list of all podcasts from configuration"""
    try:
        # Path to the podcasts.yaml file
        config_path = Path(__file__).parent.parent.parent.parent / "seeding_pipeline" / "config" / "podcasts.yaml"
        
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Extract podcast information
        podcasts = []
        for podcast in config.get('podcasts', []):
            podcasts.append({
                "id": podcast.get('id'),
                "name": podcast.get('name'),
                "enabled": str(podcast.get('enabled', True))
            })
        
        return podcasts
    except Exception as e:
        logger.error(f"Error getting podcasts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get podcasts")

@router.get("/podcasts/{podcast_id}/youtube-urls")
async def get_youtube_urls(podcast_id: str) -> List[Dict[str, Any]]:
    """Get episodes with YouTube URLs for a specific podcast"""
    try:
        # Load config to get database details
        config_path = Path(__file__).parent.parent.parent.parent / "seeding_pipeline" / "config" / "podcasts.yaml"
        
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Find the podcast
        podcast = None
        for p in config.get('podcasts', []):
            if p.get('id') == podcast_id:
                podcast = p
                break
        
        if not podcast:
            raise HTTPException(status_code=404, detail=f"Podcast '{podcast_id}' not found")
        
        # Get database connection details
        db_config = podcast.get('database', {})
        db_uri = db_config.get('uri', 'bolt://localhost:7687')
        db_username = db_config.get('username', 'neo4j')
        db_password = os.getenv('NEO4J_PASSWORD', 'password')
        db_name = db_config.get('database_name', 'neo4j')
        
        # Connect to database
        driver = GraphDatabase.driver(db_uri, auth=(db_username, db_password))
        
        with driver.session(database=db_name) as session:
            query = """
            MATCH (e:Episode)
            RETURN e.title as title, 
                   e.published_date as episode_date,
                   e.youtube_url as youtube_url
            ORDER BY e.published_date DESC
            """
            
            result = session.run(query)
            episodes = []
            
            for record in result:
                episodes.append({
                    "title": record["title"] or "",
                    "episode_date": record["episode_date"] or "",
                    "youtube_url": record["youtube_url"] or ""
                })
            
            return episodes
            
    except Exception as e:
        logger.error(f"Error getting YouTube URLs for podcast {podcast_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get YouTube URLs: {str(e)}")