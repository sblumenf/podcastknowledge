"""Minimal RAG service for Neo4j GraphRAG integration."""

import os
import logging
from typing import Optional, Dict, Any, List
from neo4j import GraphDatabase
import google.generativeai as genai
import numpy as np

logger = logging.getLogger(__name__)


class RAGService:
    """Minimal service for Neo4j GraphRAG functionality."""
    
    def __init__(self, uri: str, database_name: str, username: str = "neo4j", password: str = None):
        """Initialize RAG service with Neo4j connection parameters."""
        # Get Neo4j connection details from parameters
        self.neo4j_uri = uri
        self.neo4j_username = username
        self.neo4j_password = password or os.getenv("NEO4J_PASSWORD", "password")
        self.neo4j_database = database_name
        
        # Driver will be created on demand
        self._driver = None
        
        # Initialize API keys
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        # Initialize Gemini for embeddings
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
            self.embed_model = genai.GenerativeModel('models/text-embedding-004')
        else:
            logger.warning("GEMINI_API_KEY not found in environment")
            self.embed_model = None
        
        # Validate connection on initialization
        self.validate_connection()
        
    def validate_connection(self) -> None:
        """Validate database connection immediately upon creation."""
        try:
            driver = self._get_driver()
            # Test the connection with a simple query
            with driver.session(database=self.neo4j_database) as session:
                result = session.run("RETURN 1 as test")
                record = result.single()
                if not record:
                    raise ConnectionError("Failed to execute test query")
        except Exception as e:
            raise ConnectionError(f"Cannot connect to database '{self.neo4j_database}' at {self.neo4j_uri}: {str(e)}")
        
    def _get_driver(self):
        """Get or create Neo4j driver."""
        if self._driver is None:
            if not self.neo4j_password:
                raise ValueError("NEO4J_PASSWORD environment variable is required")
                
            self._driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_username, self.neo4j_password)
            )
            logger.info(f"Connected to Neo4j at {self.neo4j_uri}")
        return self._driver
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Neo4j connection and return basic info."""
        try:
            driver = self._get_driver()
            
            # Run a simple query to test connection
            with driver.session(database=self.neo4j_database) as session:
                result = session.run("MATCH (n) RETURN count(n) as node_count LIMIT 1")
                record = result.single()
                node_count = record["node_count"] if record else 0
                
            return {
                "status": "connected",
                "uri": self.neo4j_uri,
                "database": self.neo4j_database,
                "node_count": node_count,
                "graphrag_ready": True
            }
            
        except Exception as e:
            logger.error(f"Neo4j connection test failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "graphrag_ready": False
            }
    
    
    
    
    def search(self, query: str, database_name: str = None, top_k: int = 5) -> Dict[str, Any]:
        """
        Perform RAG search: embed query, search vectors, generate response.
        
        Args:
            query: The search query
            database_name: The database to search in (defaults to self.neo4j_database)
            top_k: Number of results to return
            
        Returns:
            Search results dict with generated response
        """
        # Use provided database or default
        database = database_name or self.neo4j_database
        
        try:
            # Step 1: Embed the query
            logger.info(f"Embedding query for database '{database}': {query}")
            embedding = self._embed_query(query)
            
            # Step 2: Perform vector search
            logger.info(f"Performing vector search in database '{database}'")
            search_results = self._vector_search(embedding, database, top_k)
            
            # Step 3: Generate response if we have results
            if search_results:
                logger.info(f"Generating response based on {len(search_results)} results")
                response = self._generate_response(query, search_results)
                
                return {
                    "query": query,
                    "database": database,
                    "response": response,
                    "sources": search_results,
                    "status": "success"
                }
            else:
                return {
                    "query": query,
                    "database": database,
                    "response": "I couldn't find any relevant information in the podcast episodes to answer your question.",
                    "sources": [],
                    "status": "no_results"
                }
                
        except ValueError as e:
            # Handle missing API keys or initialization errors
            logger.error(f"Configuration error: {e}")
            return {
                "query": query,
                "database": database,
                "error": str(e),
                "status": "configuration_error"
            }
        except Exception as e:
            # Handle other errors
            logger.error(f"Search failed: {e}")
            return {
                "query": query,
                "database": database,
                "error": f"An error occurred during search: {str(e)}",
                "status": "error"
            }
    
    def close(self):
        """Close Neo4j driver connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j driver closed")


# Connection cache for podcast-specific RAG services
_rag_service_cache = {}


def get_or_create_rag_service(podcast_id: str, uri: str, database_name: str, username: str = "neo4j") -> RAGService:
    """Get or create a RAG service instance for a specific podcast."""
    if podcast_id not in _rag_service_cache:
        _rag_service_cache[podcast_id] = RAGService(uri=uri, database_name=database_name, username=username)
    return _rag_service_cache[podcast_id]


def get_rag_service():
    """Deprecated - use get_or_create_rag_service with podcast-specific config."""
    raise NotImplementedError("RAG service now requires podcast-specific configuration. Use the chat endpoint for podcast-specific queries.")