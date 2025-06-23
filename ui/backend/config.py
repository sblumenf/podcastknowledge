"""Configuration reader for accessing podcast information from seeding pipeline."""

import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def read_podcast_config() -> List[Dict[str, Any]]:
    """
    Read podcast configuration from the seeding pipeline config file.
    
    Returns:
        List of podcast configurations with simplified structure for UI needs.
        Each dict contains: id, name, description, neo4j_port
    """
    # Construct path to podcasts.yaml relative to this file
    config_path = Path(__file__).resolve().parent.parent.parent / "seeding_pipeline" / "config" / "podcasts.yaml"
    
    try:
        # Check if file exists
        if not config_path.exists():
            logger.error(f"Podcast configuration file not found at: {config_path}")
            return []
        
        # Read and parse YAML
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Extract podcast information
        podcasts = []
        if config_data and 'podcasts' in config_data:
            # Handle list format
            if isinstance(config_data['podcasts'], list):
                for podcast_info in config_data['podcasts']:
                    # Extract only what the UI needs
                    simplified_podcast = {
                        'id': podcast_info.get('id', ''),
                        'name': podcast_info.get('name', ''),
                        'description': podcast_info.get('metadata', {}).get('description', ''),
                        'neo4j_port': podcast_info.get('database', {}).get('neo4j_port', 7687)
                    }
                    podcasts.append(simplified_podcast)
            # Handle dict format (legacy)
            elif isinstance(config_data['podcasts'], dict):
                for podcast_id, podcast_info in config_data['podcasts'].items():
                    simplified_podcast = {
                        'id': podcast_id,
                        'name': podcast_info.get('name', podcast_id),
                        'description': podcast_info.get('description', ''),
                        'neo4j_port': podcast_info.get('neo4j_port', 7687)
                    }
                    podcasts.append(simplified_podcast)
        
        logger.info(f"Successfully loaded {len(podcasts)} podcast configurations")
        return podcasts
        
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        return []
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error reading configuration: {e}")
        return []


def get_podcast_by_id(podcast_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific podcast configuration by ID.
    
    Args:
        podcast_id: The podcast identifier
        
    Returns:
        Podcast configuration dict or None if not found
    """
    podcasts = read_podcast_config()
    for podcast in podcasts:
        if podcast['id'] == podcast_id:
            return podcast
    return None