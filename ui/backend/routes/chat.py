from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import yaml
from pathlib import Path
import logging
from services.rag_service import get_rag_service

router = APIRouter()
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    """Request model for chat."""
    query: str

class ChatResponse(BaseModel):
    """Response model for chat."""
    response: str
    podcast_name: str

@router.post("/chat/{podcast_id}")
async def chat_with_podcast(podcast_id: str, request: ChatRequest) -> ChatResponse:
    """
    Chat with a specific podcast's knowledge graph.
    
    Args:
        podcast_id: The ID of the podcast to query
        request: Chat request with the user's query
        
    Returns:
        Response from the podcast's knowledge graph
    """
    try:
        # Read podcast configuration
        config_path = Path(__file__).parent.parent.parent.parent / "seeding_pipeline" / "config" / "podcasts.yaml"
        
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Find the specific podcast
        podcast = None
        for p in config.get('podcasts', []):
            if p.get('id') == podcast_id:
                podcast = p
                break
        
        if not podcast:
            raise HTTPException(status_code=404, detail=f"Podcast '{podcast_id}' not found")
        
        # Get database connection details
        db_name = podcast.get('database', {}).get('database_name', 'neo4j')
        podcast_name = podcast.get('name', 'Unknown Podcast')
        
        # Get RAG service instance
        rag_service = get_rag_service()
        
        try:
            # Perform RAG search with database name
            logger.info(f"Searching in database '{db_name}' for podcast '{podcast_name}'")
            result = rag_service.search(
                query=request.query,
                database_name=db_name
            )
            
            # Check if we need to fallback to default database name
            # This handles the case where MFM uses 'neo4j' instead of 'my_first_million'
            if result.get("status") == "error" and "database does not exist" in result.get("error", "").lower():
                logger.info(f"Database '{db_name}' not found, trying default 'neo4j'")
                result = rag_service.search(
                    query=request.query,
                    database_name="neo4j"
                )
            
            # Handle different response statuses
            if result.get("status") == "success":
                return ChatResponse(
                    response=result["response"],
                    podcast_name=podcast_name
                )
            elif result.get("status") == "no_results":
                return ChatResponse(
                    response=result["response"],
                    podcast_name=podcast_name
                )
            elif result.get("status") == "configuration_error":
                # Handle missing API keys or configuration issues
                error_msg = result.get("error", "Configuration error")
                raise HTTPException(status_code=500, detail=f"Configuration error: {error_msg}")
            else:
                # Handle other errors
                error_msg = result.get("error", "Unknown error occurred")
                raise HTTPException(status_code=500, detail=f"Search error: {error_msg}")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in RAG search: {e}")
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
                
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Podcasts configuration file not found")
    except Exception as e:
        logger.error(f"Chat error for podcast {podcast_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")