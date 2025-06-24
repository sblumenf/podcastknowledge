"""RAG (Retrieval Augmented Generation) endpoints for the UI API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from services.rag_service import get_rag_service

router = APIRouter()


class SearchRequest(BaseModel):
    """Request model for RAG search."""
    query: str
    top_k: Optional[int] = 5


@router.get("/rag/status")
async def get_rag_status() -> Dict[str, Any]:
    """
    Check RAG service status and Neo4j connection.
    
    Returns:
        RAG service status including connection info
    """
    try:
        rag_service = get_rag_service()
        return rag_service.test_connection()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/search")
async def search_knowledge(request: SearchRequest) -> Dict[str, Any]:
    """
    Search the knowledge graph using RAG.
    
    Args:
        request: Search request with query and optional parameters
        
    Returns:
        Search results from the knowledge graph
    """
    try:
        rag_service = get_rag_service()
        results = rag_service.search(
            query=request.query,
            top_k=request.top_k
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))