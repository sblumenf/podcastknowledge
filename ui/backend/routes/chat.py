from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import yaml
from pathlib import Path
from neo4j import GraphDatabase
import logging

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
        db_uri = podcast.get('database', {}).get('uri', 'bolt://localhost:7687')
        db_name = podcast.get('database', {}).get('database_name', 'neo4j')
        podcast_name = podcast.get('name', 'Unknown Podcast')
        
        # For now, create a simple response
        # In a real implementation, this would connect to Neo4j and query the knowledge graph
        driver = None
        try:
            # Connect to the specific podcast's database
            driver = GraphDatabase.driver(
                db_uri,
                auth=("neo4j", "changeme")  # In production, use environment variables
            )
            
            # Test connection and get some basic info
            with driver.session(database=db_name) as session:
                result = session.run(
                    "MATCH (n) RETURN count(n) as node_count LIMIT 1"
                )
                record = result.single()
                node_count = record["node_count"] if record else 0
            
            # Simple placeholder response for now
            # In a real implementation, this would use RAG to query the knowledge graph
            response_text = f"I'm connected to the {podcast_name} knowledge graph with {node_count} nodes. "
            response_text += f"You asked: '{request.query}'. "
            response_text += "Full RAG implementation coming soon!"
            
            return ChatResponse(
                response=response_text,
                podcast_name=podcast_name
            )
            
        finally:
            if driver:
                driver.close()
                
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Podcasts configuration file not found")
    except Exception as e:
        logger.error(f"Chat error for podcast {podcast_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")