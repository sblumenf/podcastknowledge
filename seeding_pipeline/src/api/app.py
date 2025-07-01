"""FastAPI application for VTT Knowledge Pipeline."""

from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
import asyncio
import os

from ..core.config import SeedingConfig as PipelineConfig
from ..seeding import VTTKnowledgeExtractor as PodcastKnowledgePipeline
from ..utils.logging import get_logger
from .health import create_health_endpoints
from ..monitoring import setup_metrics
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
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


@app.get("/api/v1/vtt/status", tags=["vtt"])
async def get_vtt_processing_status(request: Request):
    """Get VTT processing status and statistics."""
    try:
        # Get checkpoint information
        checkpoint_dir = getattr(request.app.state.config, 'checkpoint_dir', 'checkpoints')
        
        # Count processed VTT files
        from pathlib import Path
        import json
        
        checkpoint_path = Path(checkpoint_dir)
        processed_files = []
        
        if checkpoint_path.exists():
            for checkpoint_file in checkpoint_path.glob("*.json"):
                try:
                    with open(checkpoint_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if 'vtt_file' in data:
                            processed_files.append({
                                "file": data['vtt_file'],
                                "processed_at": data.get('timestamp', 'unknown'),
                                "segments": data.get('segment_count', 0)
                            })
                except Exception:
                    pass
        
        return {
            "status": "success",
            "processed_files_count": len(processed_files),
            "processed_files": processed_files,
            "checkpoint_directory": str(checkpoint_path)
        }
    except Exception as e:
        logger.error(f"Failed to get VTT status: {e}")
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
        graph_provider = pipeline.graph_service
        
        stats = {}
        
        # Get node counts by type
        node_types = ["Podcast", "Episode", "Person", "Insight"]
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