"""Welcome endpoint for the UI API."""

from datetime import datetime
from fastapi import APIRouter
from typing import Dict, Any

from ..config import read_podcast_config

router = APIRouter()


@router.get("/welcome")
async def get_welcome() -> Dict[str, Any]:
    """
    Get welcome information including system status and podcast count.
    
    Returns:
        Welcome message with system information
    """
    # Get podcast configurations
    podcasts = read_podcast_config()
    
    return {
        "message": "Welcome to Podcast Knowledge Explorer",
        "system_status": {
            "podcast_count": len(podcasts),
            "status": "operational",
            "timestamp": datetime.now().isoformat()
        },
        "description": "Explore knowledge graphs from your favorite podcasts"
    }