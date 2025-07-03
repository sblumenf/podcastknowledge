"""Main FastAPI application for Podcast Knowledge UI."""

from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from routes.welcome import router as welcome_router
from routes.rag import router as rag_router
from routes.dashboard import router as dashboard_router
from routes.chat import router as chat_router
from routes.admin import router as admin_router
from routes.episodes import router as episodes_router
from routes.knowledge_graph import router as knowledge_graph_router
from routes.knowledge_graph_enhanced import router as knowledge_graph_enhanced_router

# Create FastAPI app instance
app = FastAPI(
    title="Podcast Knowledge UI API",
    version="0.1.0",
    description="API for serving podcast knowledge graph data to the React frontend"
)

# Configure CORS for development (frontend on different port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176"],  # Vite default port and alternatives
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint for health check
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Podcast Knowledge UI API",
        "version": "0.1.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

# Include routers
app.include_router(welcome_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(episodes_router, prefix="/api")
app.include_router(knowledge_graph_router, prefix="/api")
app.include_router(knowledge_graph_enhanced_router, prefix="/api")

# Run with uvicorn when executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8001,
        reload=True,
        log_level="info"
    )