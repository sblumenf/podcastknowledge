from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import yaml
from pathlib import Path
from datetime import datetime
import logging
from neo4j import GraphDatabase

router = APIRouter(prefix="/api/v1/podcasts", tags=["podcasts"])
logger = logging.getLogger(__name__)

class PodcastService:
    def __init__(self):
        self.config_path = Path(__file__).parent.parent.parent.parent.parent / "seeding_pipeline" / "config" / "podcasts.yaml"
        self._podcasts = None
        self._last_loaded = None
        self.drivers = {}
        
    def load_podcasts(self) -> List[Dict[str, Any]]:
        """Load podcast configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            podcasts = []
            for podcast_config in config.get('podcasts', []):
                if not podcast_config.get('enabled', True):
                    continue
                    
                podcast = {
                    'id': podcast_config['id'],
                    'name': podcast_config['name'],
                    'host': podcast_config.get('metadata', {}).get('host', 'Unknown'),
                    'description': podcast_config.get('metadata', {}).get('description', ''),
                    'category': podcast_config.get('metadata', {}).get('category', 'General'),
                    'tags': podcast_config.get('metadata', {}).get('tags', []),
                    'database': {
                        'uri': podcast_config['database']['uri'],
                        'port': podcast_config['database']['neo4j_port']
                    },
                    'theme_color': self._get_theme_color(podcast_config),
                    'icon_type': self._get_icon_type(podcast_config),
                    'episode_count': 0,
                    'last_updated': None
                }
                podcasts.append(podcast)
                
            self._podcasts = podcasts
            self._last_loaded = datetime.now()
            return podcasts
            
        except Exception as e:
            logger.error(f"Failed to load podcast configuration: {e}")
            raise HTTPException(status_code=500, detail="Failed to load podcast configuration")
    
    def _get_theme_color(self, podcast_config: Dict) -> str:
        """Assign theme color based on podcast ID."""
        colors = {
            'mel_robbins_podcast': 'from-pink-500 to-purple-600',
            'my_first_million': 'from-blue-500 to-indigo-600'
        }
        return colors.get(podcast_config['id'], 'from-gray-500 to-gray-600')
    
    def _get_icon_type(self, podcast_config: Dict) -> str:
        """Determine icon type based on podcast category."""
        category = podcast_config.get('metadata', {}).get('category', '').lower()
        icon_map = {
            'self-improvement': 'sparkles',
            'business': 'briefcase',
            'technology': 'chip',
            'education': 'academic-cap',
            'comedy': 'emoji-happy',
            'news': 'newspaper'
        }
        return icon_map.get(category, 'microphone')
    
    async def get_podcast_stats(self, podcast_id: str, port: int) -> Dict[str, Any]:
        """Query Neo4j to get episode count and last update date."""
        uri = f"bolt://localhost:{port}"
        
        try:
            # Get or create driver
            if uri not in self.drivers:
                self.drivers[uri] = GraphDatabase.driver(uri, auth=("neo4j", "password"))
            
            driver = self.drivers[uri]
            
            with driver.session() as session:
                # Count episodes
                episode_count = session.run("MATCH (e:Episode) RETURN count(e) as count").single()["count"]
                
                # Get last update
                result = session.run("""
                    MATCH (e:Episode)
                    RETURN e.created_at as created_at
                    ORDER BY e.created_at DESC
                    LIMIT 1
                """).single()
                
                last_updated = result["created_at"] if result else datetime.now().isoformat()
                
                return {
                    'episode_count': episode_count,
                    'last_updated': last_updated
                }
        except Exception as e:
            logger.warning(f"Failed to get stats for {podcast_id}: {e}")
            # Return defaults if database is not available
            return {
                'episode_count': 0,
                'last_updated': datetime.now().isoformat()
            }

podcast_service = PodcastService()

@router.get("/", response_model=Dict[str, List[Dict[str, Any]]])
async def get_podcasts():
    """Get all configured podcasts with their metadata."""
    podcasts = podcast_service.load_podcasts()
    
    for podcast in podcasts:
        stats = await podcast_service.get_podcast_stats(
            podcast['id'], 
            podcast['database']['port']
        )
        podcast.update(stats)
    
    return {"podcasts": podcasts}

@router.get("/{podcast_id}")
async def get_podcast(podcast_id: str):
    """Get details for a specific podcast."""
    podcasts = podcast_service.load_podcasts()
    podcast = next((p for p in podcasts if p['id'] == podcast_id), None)
    
    if not podcast:
        raise HTTPException(status_code=404, detail="Podcast not found")
    
    stats = await podcast_service.get_podcast_stats(
        podcast['id'],
        podcast['database']['port']
    )
    podcast.update(stats)
    
    return podcast