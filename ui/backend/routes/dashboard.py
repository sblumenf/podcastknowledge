from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import yaml
from pathlib import Path

router = APIRouter()

@router.get("/podcasts")
async def get_podcasts() -> List[Dict[str, Any]]:
    """
    Get all podcasts from the configuration file.
    Returns a list of podcast information for the dashboard.
    """
    try:
        # Path to the podcasts.yaml file
        config_path = Path(__file__).parent.parent.parent.parent / "seeding_pipeline" / "config" / "podcasts.yaml"
        
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Extract podcast information
        podcasts = []
        for podcast in config.get('podcasts', []):
            podcast_info = {
                'id': podcast.get('id'),
                'name': podcast.get('name'),
                'host': podcast.get('metadata', {}).get('host', 'Unknown Host'),
                'category': podcast.get('metadata', {}).get('category', 'Uncategorized'),
                'description': podcast.get('metadata', {}).get('description', ''),
                'tags': podcast.get('metadata', {}).get('tags', []),
                'enabled': podcast.get('enabled', False),
                'database_port': podcast.get('database', {}).get('neo4j_port', 'N/A'),
                'database_name': podcast.get('database', {}).get('database_name', 'Unknown')
            }
            podcasts.append(podcast_info)
        
        return podcasts
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Podcasts configuration file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading podcasts configuration: {str(e)}")