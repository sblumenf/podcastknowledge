from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase
import logging

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])
logger = logging.getLogger(__name__)

class GraphService:
    def __init__(self):
        self.drivers = {}
    
    def get_driver(self, uri: str, username: str = "neo4j", password: str = "password"):
        """Get or create a Neo4j driver for the given URI."""
        if uri not in self.drivers:
            self.drivers[uri] = GraphDatabase.driver(uri, auth=(username, password))
        return self.drivers[uri]
    
    async def get_clusters(self, uri: str, database: str = "neo4j") -> List[Dict[str, Any]]:
        """Get clusters from the database."""
        driver = self.get_driver(uri)
        
        query = """
        MATCH (c:Cluster)
        RETURN c.id as id, c.label as label, c.member_count as member_count
        ORDER BY c.member_count DESC
        """
        
        try:
            with driver.session(database=database) as session:
                result = session.run(query)
                clusters = [dict(record) for record in result]
                return clusters
        except Exception as e:
            logger.error(f"Failed to fetch clusters: {e}")
            # Return empty list if clusters don't exist (fallback to topics)
            return []
    
    async def get_topics(self, uri: str, database: str = "neo4j") -> List[Dict[str, Any]]:
        """Get topics from the database."""
        driver = self.get_driver(uri)
        
        query = """
        MATCH (t:Topic)
        RETURN t.name as name
        ORDER BY t.name
        """
        
        try:
            with driver.session(database=database) as session:
                result = session.run(query)
                topics = [dict(record) for record in result]
                return topics
        except Exception as e:
            logger.error(f"Failed to fetch topics: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch topics")
    
    async def get_initial_graph(self, uri: str, database: str = "neo4j") -> Dict[str, Any]:
        """Get initial graph data (clusters or topics as fallback)."""
        # Try to get clusters first
        clusters = await self.get_clusters(uri, database)
        
        if clusters:
            # Return clusters with their relationships
            driver = self.get_driver(uri)
            query = """
            MATCH (c:Cluster)
            OPTIONAL MATCH (c)-[r:CONTAINS]->(t:Topic)
            RETURN c, collect({topic: t, relationship: r}) as topics
            """
            
            with driver.session(database=database) as session:
                result = session.run(query)
                nodes = []
                edges = []
                
                for record in result:
                    cluster = record["c"]
                    cluster_data = {
                        "id": cluster["id"],
                        "label": cluster["label"],
                        "type": "cluster",
                        "size": 30,
                        "color": "#3498db"
                    }
                    nodes.append(cluster_data)
                    
                    # Add topic relationships if they exist
                    for topic_rel in record["topics"]:
                        if topic_rel["topic"]:
                            topic = topic_rel["topic"]
                            topic_data = {
                                "id": f"topic_{topic['name']}",
                                "label": topic["name"],
                                "type": "topic",
                                "size": 20,
                                "color": "#2ecc71",
                                "hidden": True  # Initially hidden
                            }
                            if topic_data not in nodes:
                                nodes.append(topic_data)
                            
                            edges.append({
                                "id": f"{cluster['id']}_to_{topic['name']}",
                                "source": cluster["id"],
                                "target": f"topic_{topic['name']}",
                                "size": 2
                            })
                
                return {"nodes": nodes, "edges": edges}
        else:
            # Fallback to topics if no clusters exist
            topics = await self.get_topics(uri, database)
            nodes = [
                {
                    "id": f"topic_{topic['name']}",
                    "label": topic["name"],
                    "type": "topic",
                    "size": 25,
                    "color": "#2ecc71"
                }
                for topic in topics
            ]
            return {"nodes": nodes, "edges": []}

graph_service = GraphService()

@router.get("/{podcast_id}/initial")
async def get_initial_graph_data(
    podcast_id: str,
    uri: str = Query(..., description="Neo4j URI"),
    database: str = Query("neo4j", description="Database name")
):
    """Get initial graph data for a podcast."""
    try:
        graph_data = await graph_service.get_initial_graph(uri, database)
        return graph_data
    except Exception as e:
        logger.error(f"Failed to get initial graph data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{podcast_id}/expand/{node_id}")
async def expand_node(
    podcast_id: str,
    node_id: str,
    uri: str = Query(..., description="Neo4j URI"),
    database: str = Query("neo4j", description="Database name")
):
    """Expand a node to show its children."""
    driver = graph_service.get_driver(uri)
    
    try:
        # Determine node type and fetch children accordingly
        if node_id.startswith("topic_"):
            # Fetch meaningful units for a topic
            topic_name = node_id.replace("topic_", "")
            query = """
            MATCH (t:Topic {name: $topic_name})-[r:HAS_MEANINGFUL_UNIT]->(mu:MeaningfulUnit)
            RETURN mu
            LIMIT 20
            """
            params = {"topic_name": topic_name}
        else:
            # Assume it's a cluster, fetch topics
            query = """
            MATCH (c:Cluster {id: $cluster_id})-[r:CONTAINS]->(t:Topic)
            RETURN t
            """
            params = {"cluster_id": node_id}
        
        with driver.session(database=database) as session:
            result = session.run(query, params)
            nodes = []
            edges = []
            
            for record in result:
                if "mu" in record:
                    mu = record["mu"]
                    nodes.append({
                        "id": mu["id"],
                        "label": mu.get("summary", mu["id"])[:50] + "...",
                        "type": "meaningful_unit",
                        "size": 15,
                        "color": "#e74c3c"
                    })
                    edges.append({
                        "id": f"{node_id}_to_{mu['id']}",
                        "source": node_id,
                        "target": mu["id"],
                        "size": 1
                    })
                elif "t" in record:
                    topic = record["t"]
                    topic_id = f"topic_{topic['name']}"
                    nodes.append({
                        "id": topic_id,
                        "label": topic["name"],
                        "type": "topic",
                        "size": 20,
                        "color": "#2ecc71"
                    })
                    edges.append({
                        "id": f"{node_id}_to_{topic_id}",
                        "source": node_id,
                        "target": topic_id,
                        "size": 2
                    })
            
            return {"nodes": nodes, "edges": edges}
            
    except Exception as e:
        logger.error(f"Failed to expand node: {e}")
        raise HTTPException(status_code=500, detail=str(e))