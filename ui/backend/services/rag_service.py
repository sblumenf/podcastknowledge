"""Minimal RAG service for Neo4j GraphRAG integration."""

import os
import logging
from typing import Optional, Dict, Any, List
from neo4j import GraphDatabase
import google.generativeai as genai
import numpy as np
from neo4j_graphrag.llm.base import LLMInterface
from neo4j_graphrag.llm.types import LLMResponse
from neo4j_graphrag.embeddings.base import Embedder
# Importing specific classes to avoid loading OpenAI dependencies
from neo4j_graphrag.retrievers.vector import VectorRetriever
from neo4j_graphrag.generation.graphrag import GraphRAG

logger = logging.getLogger(__name__)

# Import configuration
from config import GEMINI_CONFIG


# Custom Google Generative AI LLM implementation
class GoogleGenerativeAILLM(LLMInterface):
    """Custom LLM implementation for Google Generative AI."""
    
    def __init__(self, model_name: str = None, model_params: Optional[Dict[str, Any]] = None, api_key: str = None):
        """Initialize Google Generative AI LLM."""
        model_name = model_name or GEMINI_CONFIG["model_name"]
        model_params = model_params or {
            "temperature": GEMINI_CONFIG["temperature"],
            "max_output_tokens": GEMINI_CONFIG["max_tokens"]
        }
        super().__init__(model_name, model_params)
        
        # Configure API key
        if api_key:
            genai.configure(api_key=api_key)
        else:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            
        # Initialize the model
        self.model = genai.GenerativeModel(model_name)
        logger.info(f"Initialized GoogleGenerativeAILLM with model: {model_name}")
    
    def invoke(self, input: str, message_history=None, system_instruction=None) -> LLMResponse:
        """Synchronous invocation of the LLM."""
        try:
            # Build the prompt with system instruction if provided
            if system_instruction:
                full_prompt = f"{system_instruction}\n\n{input}"
            else:
                full_prompt = input
                
            # Generate response
            response = self.model.generate_content(full_prompt)
            return LLMResponse(content=response.text)
            
        except Exception as e:
            logger.error(f"Error invoking Google Generative AI: {e}")
            raise
    
    async def ainvoke(self, input: str, message_history=None, system_instruction=None) -> LLMResponse:
        """Asynchronous invocation - currently using sync implementation."""
        # TODO: Implement proper async support
        return self.invoke(input, message_history, system_instruction)


# Custom Google Generative AI Embeddings implementation
class GoogleGenerativeAIEmbeddings(Embedder):
    """Custom embeddings implementation for Google Generative AI."""
    
    def __init__(self, model: str = "models/text-embedding-004", api_key: str = None):
        """Initialize Google Generative AI Embeddings."""
        self.model_name = model
        
        # Configure API key
        if api_key:
            genai.configure(api_key=api_key)
        else:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            
        logger.info(f"Initialized GoogleGenerativeAIEmbeddings with model: {model}")
    
    def embed_query(self, text: str) -> List[float]:
        """Generate embeddings for a single text query."""
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=text
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = []
        for text in texts:
            embeddings.append(self.embed_query(text))
        return embeddings


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
        
        # Initialize neo4j-graphrag components
        self.embedder = None
        self.llm = None
        self.retriever = None
        self.rag = None
        
        if self.gemini_api_key:
            # Initialize embeddings
            self.embedder = GoogleGenerativeAIEmbeddings(
                model="models/text-embedding-004",
                api_key=self.gemini_api_key
            )
            
            # Initialize LLM
            self.llm = GoogleGenerativeAILLM(
                api_key=self.gemini_api_key
            )
            
            # Retriever and RAG will be initialized on demand with database
            logger.info("Initialized Google Generative AI components")
        else:
            logger.warning("GEMINI_API_KEY not found in environment")
        
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
    
    def _initialize_rag_components(self, database: str):
        """Initialize or get RAG components for the specific database."""
        # Only initialize if not already done or if database changed
        if self.retriever is None or getattr(self.retriever, '_database', None) != database:
            if not self.embedder or not self.llm:
                raise ValueError("Embedder and LLM must be initialized first")
                
            driver = self._get_driver()
            
            # Initialize retriever with the meaningful unit embeddings index
            self.retriever = VectorRetriever(
                driver=driver,
                index_name="meaningfulUnitEmbeddings",
                embedder=self.embedder,
                neo4j_database=database
            )
            # Store the database for reference
            self.retriever._database = database
            
            # Initialize GraphRAG pipeline
            self.rag = GraphRAG(
                retriever=self.retriever,
                llm=self.llm
            )
            
            logger.info(f"Initialized RAG components for database: {database}")
    
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
    
    
    
    
    def search(self, query: str, database_name: str = None, top_k: int = 5, system_instruction: str = None) -> Dict[str, Any]:
        """
        Perform RAG search using neo4j-graphrag.
        
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
            if not self.embedder or not self.llm:
                raise ValueError("Gemini API key not configured")
                
            # Initialize RAG components for the specific database
            self._initialize_rag_components(database)
            
            # Perform search using neo4j-graphrag
            logger.info(f"Performing GraphRAG search for database '{database}': {query}")
            
            # Configure retriever to return context
            retriever_config = {"top_k": top_k}
            
            # Use GraphRAG to search and generate response
            result = self.rag.search(
                query_text=query,
                retriever_config=retriever_config,
                return_context=True,  # Get the source context
                system_instruction=system_instruction
            )
            
            # Extract sources from the context
            sources = []
            if hasattr(result, 'retriever_result') and result.retriever_result:
                for item in result.retriever_result.items:
                    # Extract relevant metadata from the retriever result
                    source_data = {
                        "text": item.content,
                        "score": getattr(item, 'score', 0.0)
                    }
                    # Add any additional metadata
                    if hasattr(item, 'metadata'):
                        source_data.update(item.metadata)
                    sources.append(source_data)
            
            return {
                "query": query,
                "database": database,
                "response": result.answer,
                "sources": sources,
                "status": "success"
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