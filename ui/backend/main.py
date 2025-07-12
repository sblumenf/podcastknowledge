from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yaml
from pathlib import Path
from datetime import datetime
from neo4j import GraphDatabase
import os

app = FastAPI()

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load podcast configuration
def load_podcast_config():
    config_path = Path(__file__).parent.parent.parent / "seeding_pipeline" / "config" / "podcasts.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

@app.get("/api/v1/podcasts")
async def get_podcasts():
    """Get list of all configured podcasts with basic stats"""
    try:
        config = load_podcast_config()
        podcasts = []
        
        # Handle new YAML structure where podcasts is a list
        for podcast_config in config['podcasts']:
            # Basic podcast info from config
            podcast_info = {
                'id': podcast_config['id'],
                'name': podcast_config['name'],
                'description': podcast_config.get('metadata', {}).get('description', ''),
                'episode_count': 0,
                'last_updated': datetime.now().isoformat()
            }
            
            # Try to get stats from Neo4j
            try:
                db_config = podcast_config['database']
                driver = GraphDatabase.driver(
                    f"bolt://localhost:{db_config['neo4j_port']}", 
                    auth=("neo4j", db_config.get('neo4j_password', 'password'))
                )
                
                with driver.session() as session:
                    # Get episode count
                    result = session.run("MATCH (e:Episode) RETURN count(e) as count")
                    podcast_info['episode_count'] = result.single()['count']
                    
                    # Get last episode date
                    result = session.run(
                        "MATCH (e:Episode) "
                        "RETURN e.published_date as date "
                        "ORDER BY e.published_date DESC LIMIT 1"
                    )
                    record = result.single()
                    if record and record['date']:
                        podcast_info['last_updated'] = record['date']
                
                driver.close()
            except Exception as e:
                # If Neo4j is not available, just use config data
                print(f"Could not connect to Neo4j for {podcast_config['id']}: {e}")
            
            podcasts.append(podcast_info)
        
        return {"podcasts": podcasts}
    
    except Exception as e:
        return {"error": str(e), "podcasts": []}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)