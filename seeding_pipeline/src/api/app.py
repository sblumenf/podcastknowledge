"""FastAPI application with distributed tracing support."""

import os
import asyncio
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from ..core.config import PipelineConfig
from ..seeding import PodcastKnowledgePipeline
from .health import create_health_endpoints
from .metrics import setup_metrics
from ..utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Podcast Knowledge Pipeline API...")
    
    # Initialize pipeline
    config = PipelineConfig.from_env()
    pipeline = PodcastKnowledgePipeline(config)
    pipeline.initialize_components()
    
    # Store in app state
    app.state.pipeline = pipeline
    app.state.config = config
    
    yield
    
    # Shutdown
    logger.info("Shutting down Podcast Knowledge Pipeline API...")
    pipeline.cleanup()


# Create FastAPI app
app = FastAPI(
    title="Podcast Knowledge Pipeline API",
    description="API for extracting and managing podcast knowledge graphs",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add health endpoints
create_health_endpoints(app)

# Setup metrics
setup_metrics(app)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint."""
    return {
        "message": "Podcast Knowledge Pipeline API",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/api/v1/seed/podcast", tags=["seeding"])
async def seed_podcast(request: Request, podcast_config: Dict[str, Any]):
    """
    Seed a single podcast into the knowledge graph.
    
    Args:
        podcast_config: Configuration containing:
            - id: Unique podcast identifier
            - rss_url: RSS feed URL
            - name: Podcast name (optional)
            - max_episodes: Maximum episodes to process (default: 1)
    """
    pipeline = request.app.state.pipeline
    
    try:
        # Run seeding in background task
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            pipeline.seed_podcast,
            podcast_config,
            podcast_config.get("max_episodes", 1)
        )
        
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        logger.error(f"Failed to seed podcast: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/v1/seed/podcasts", tags=["seeding"])
async def seed_podcasts(request: Request, podcast_configs: List[Dict[str, Any]]):
    """
    Seed multiple podcasts into the knowledge graph.
    
    Args:
        podcast_configs: List of podcast configurations
    """
    pipeline = request.app.state.pipeline
    
    try:
        # Run seeding in background task
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            pipeline.seed_podcasts,
            podcast_configs
        )
        
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        logger.error(f"Failed to seed podcasts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/v1/status/{podcast_id}", tags=["status"])
async def get_podcast_status(request: Request, podcast_id: str):
    """Get processing status for a podcast."""
    pipeline = request.app.state.pipeline
    
    try:
        # Get checkpoint status
        checkpoint = pipeline.checkpoint
        completed_episodes = checkpoint.get_completed_episodes()
        
        # Filter for this podcast
        podcast_episodes = [
            ep for ep in completed_episodes 
            if ep.startswith(f"{podcast_id}_")
        ]
        
        return {
            "podcast_id": podcast_id,
            "episodes_completed": len(podcast_episodes),
            "episode_ids": podcast_episodes
        }
    except Exception as e:
        logger.error(f"Failed to get podcast status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/v1/graph/stats", tags=["graph"])
async def get_graph_stats(request: Request):
    """Get knowledge graph statistics."""
    pipeline = request.app.state.pipeline
    
    try:
        # Query graph for statistics
        graph_provider = pipeline.graph_provider
        
        stats = {}
        
        # Get node counts by type
        node_types = ["Podcast", "Episode", "Person", "Topic", "Insight"]
        for node_type in node_types:
            query = f"MATCH (n:{node_type}) RETURN count(n) as count"
            result = graph_provider.query(query)
            stats[f"{node_type.lower()}_count"] = result[0]["count"] if result else 0
        
        # Get relationship counts
        rel_query = "MATCH ()-->() RETURN count(*) as count"
        result = graph_provider.query(rel_query)
        stats["relationship_count"] = result[0]["count"] if result else 0
        
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get graph stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Exception handlers
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    # Run with uvicorn for development
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": "INFO",
                "handlers": ["default"],
            },
        }
    )