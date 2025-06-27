"""Minimal RAG service for Neo4j GraphRAG integration."""

import os
import logging
from typing import Optional, Dict, Any, List
from neo4j import GraphDatabase
import google.generativeai as genai
from groq import Groq
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
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        
        # Initialize Gemini for embeddings
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
            self.embed_model = genai.GenerativeModel('models/text-embedding-004')
        else:
            logger.warning("GEMINI_API_KEY not found in environment")
            self.embed_model = None
        
        # Initialize Groq client for LLM responses
        if self.groq_api_key:
            # Create a custom httpx client to avoid the proxies parameter issue
            import httpx
            custom_http_client = httpx.Client(
                timeout=httpx.Timeout(timeout=120.0, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                follow_redirects=True
            )
            self.groq_client = Groq(api_key=self.groq_api_key, http_client=custom_http_client)
        else:
            logger.warning("GROQ_API_KEY not found in environment")
            self.groq_client = None
        
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
    
    def _embed_query(self, query: str) -> List[float]:
        """
        Convert a text query into a 768-dimensional embedding vector using Gemini.
        
        Args:
            query: The text query to embed
            
        Returns:
            List of 768 floats representing the embedding
        """
        try:
            if not self.embed_model:
                raise ValueError("Gemini embedding model not initialized")
                
            # Use Gemini to generate embeddings
            result = genai.embed_content(
                model='models/text-embedding-004',
                content=query
            )
            
            embedding = result['embedding']
            logger.debug(f"Generated embedding of dimension: {len(embedding)}")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            raise
    
    def _vector_search(self, embedding: List[float], database: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search in Neo4j using the embedding.
        
        Args:
            embedding: The query embedding vector
            database: The database name to search in
            top_k: Number of results to return
            
        Returns:
            List of results with node data and similarity scores
        """
        try:
            driver = self._get_driver()
            
            # Cypher query for vector similarity search
            query = """
            CALL db.index.vector.queryNodes('meaningfulUnitEmbeddings', $top_k, $embedding) 
            YIELD node, score 
            RETURN node.text AS text, 
                   node.speaker AS speaker, 
                   node.episodeTitle AS episodeTitle,
                   node.episodeId AS episodeId,
                   node.timestamp AS timestamp,
                   score
            ORDER BY score DESC
            """
            
            results = []
            with driver.session(database=database) as session:
                result = session.run(query, embedding=embedding, top_k=top_k)
                
                for record in result:
                    results.append({
                        "text": record["text"],
                        "speaker": record.get("speaker", "Unknown"),
                        "episodeTitle": record.get("episodeTitle", "Unknown Episode"),
                        "episodeId": record.get("episodeId"),
                        "timestamp": record.get("timestamp"),
                        "score": record["score"]
                    })
            
            logger.info(f"Vector search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise
    
    def _generate_response(self, query: str, context: List[Dict[str, Any]]) -> str:
        """
        Generate a response using Groq's Llama3 model based on the retrieved context.
        
        Args:
            query: The user's query
            context: List of relevant context from vector search
            
        Returns:
            Generated response text
        """
        try:
            if not self.groq_client:
                raise ValueError("Groq client not initialized")
            
            # Build context string with citations
            context_parts = []
            for i, item in enumerate(context, 1):
                episode_info = f"[{item['episodeTitle']}]" if item.get('episodeTitle') else "[Unknown Episode]"
                speaker_info = f"{item.get('speaker', 'Unknown')}: " if item.get('speaker') else ""
                context_parts.append(f"{i}. {episode_info} {speaker_info}{item['text']}")
            
            context_str = "\n\n".join(context_parts)
            
            # Create the prompt
            system_prompt = """You are a helpful assistant answering questions about podcast content. 
            Use the provided context to answer the user's question. When referencing information, 
            cite the episode by including [Episode Title] in your response. If the context doesn't 
            contain relevant information to answer the question, say so."""
            
            user_prompt = f"""Context from podcast episodes:
{context_str}

Question: {query}

Please provide a comprehensive answer based on the context above, citing specific episodes when referencing information."""
            
            # Generate response using Groq
            response = self.groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1024
            )
            
            generated_text = response.choices[0].message.content
            logger.info("Successfully generated response")
            return generated_text
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            raise
    
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