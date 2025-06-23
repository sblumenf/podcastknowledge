"""Main FastAPI application for Podcast Knowledge UI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Create FastAPI app instance
app = FastAPI(
    title="Podcast Knowledge UI API",
    version="0.1.0",
    description="API for serving podcast knowledge graph data to the React frontend"
)

# Configure CORS for development (frontend on different port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default port
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
        "status": "running"
    }

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