from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import podcasts, graph

app = FastAPI(title="Podcast Knowledge Graph API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(podcasts.router)
app.include_router(graph.router)

@app.get("/")
async def root():
    return {"message": "Podcast Knowledge Graph API"}