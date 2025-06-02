"""
Core interfaces and protocols for the podcast knowledge pipeline.

This module defines the abstract interfaces that all providers must implement,
ensuring consistent behavior across different implementations.
"""

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Dict, Any, List, Optional, Tuple, Union
# Base protocol for health checks
class HealthCheckable(Protocol):
    """Protocol for components that support health checks."""
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the component.
        
        Returns:
            Dict containing:
                - status: "healthy", "degraded", or "unhealthy"
                - details: Additional information about the health status
                - timestamp: When the check was performed
        """
        ...


# Transcript Processing Interfaces
@dataclass
class TranscriptSegment:
    """Represents a transcript segment."""
    id: str
    text: str
    start_time: float
    end_time: float
    speaker: Optional[str] = None
    confidence: Optional[float] = None


# Audio Provider Interfaces
class AudioProvider(ABC):
    """Abstract base class for audio providers."""
    
    @abstractmethod
    def download_audio(self, url: str, output_path: str) -> str:
        """Download audio from URL.
        
        Args:
            url: URL of the audio file
            output_path: Path to save the audio file
            
        Returns:
            Path to the downloaded file
        """
        pass
    
    @abstractmethod
    def get_audio_duration(self, file_path: str) -> float:
        """Get duration of an audio file in seconds.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            Duration in seconds
        """
        pass
    
    @abstractmethod
    def validate_audio_format(self, file_path: str) -> bool:
        """Validate if audio format is supported.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            True if format is supported
        """
        pass


# LLM Provider Interfaces
@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    metadata: Optional[Dict[str, Any]] = None


class LLMProvider(HealthCheckable, Protocol):
    """Interface for Large Language Model providers."""
    
    def invoke(self, prompt: str, temperature: float = 0.3) -> LLMResponse:
        """
        Send a prompt to the LLM and get a response.
        
        Args:
            prompt: The prompt to send
            temperature: Sampling temperature (0.0 to 1.0)
            
        Returns:
            LLM response with content and metadata
            
        Raises:
            LLMProcessingError: If the request fails
        """
        ...
    
    def invoke_with_retry(
        self, 
        prompt: str, 
        temperature: float = 0.3,
        max_retries: int = 3
    ) -> LLMResponse:
        """
        Invoke LLM with automatic retry on failure.
        
        Args:
            prompt: The prompt to send
            temperature: Sampling temperature
            max_retries: Maximum number of retry attempts
            
        Returns:
            LLM response with content and metadata
        """
        ...
    
    def check_rate_limits(self) -> Dict[str, Any]:
        """
        Check current rate limit status.
        
        Returns:
            Dict with rate limit information
        """
        ...


# Graph Database Provider Interfaces
class GraphProvider(HealthCheckable, Protocol):
    """Interface for graph database providers."""
    
    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a graph database query.
        
        Args:
            query: The query to execute (e.g., Cypher for Neo4j)
            parameters: Optional query parameters
            
        Returns:
            List of result records as dictionaries
            
        Raises:
            DatabaseConnectionError: If the query fails
        """
        ...
    
    def execute_write(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a write operation on the graph database.
        
        Args:
            query: The write query to execute
            parameters: Optional query parameters
            
        Returns:
            Summary of the write operation
        """
        ...
    
    def setup_schema(self) -> None:
        """
        Set up the database schema, constraints, and indexes.
        
        Raises:
            DatabaseConnectionError: If schema setup fails
        """
        ...
    
    def get_connection_pool_status(self) -> Dict[str, Any]:
        """
        Get the status of the connection pool.
        
        Returns:
            Dict with pool statistics
        """
        ...


# Embedding Provider Interfaces
class EmbeddingProvider(HealthCheckable, Protocol):
    """Interface for embedding generation providers."""
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text.
        
        Args:
            text: Input text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        ...
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        ...
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this provider.
        
        Returns:
            Embedding dimension
        """
        ...


# Knowledge Extraction Interfaces
@dataclass
class ExtractedEntity:
    """Represents an extracted entity."""
    name: str
    entity_type: str
    description: Optional[str] = None
    confidence: float = 1.0


@dataclass
class ExtractedInsight:
    """Represents an extracted insight."""
    content: str
    insight_type: str
    confidence: float = 1.0
    supporting_segments: Optional[List[str]] = None


@dataclass
class ExtractedQuote:
    """Represents an extracted quote."""
    text: str
    speaker: str
    context: Optional[str] = None
    quote_type: str = "general"


class KnowledgeExtractor(Protocol):
    """Interface for knowledge extraction from transcripts."""
    
    def extract_entities(self, transcript: str) -> List[ExtractedEntity]:
        """
        Extract entities from transcript text.
        
        Args:
            transcript: The transcript text
            
        Returns:
            List of extracted entities
        """
        ...
    
    def extract_insights(self, transcript: str) -> List[ExtractedInsight]:
        """
        Extract insights from transcript text.
        
        Args:
            transcript: The transcript text
            
        Returns:
            List of extracted insights
        """
        ...
    
    def extract_quotes(self, transcript: str) -> List[ExtractedQuote]:
        """
        Extract notable quotes from transcript text.
        
        Args:
            transcript: The transcript text
            
        Returns:
            List of extracted quotes
        """
        ...


# Context Manager Interfaces
class Neo4jManager(AbstractContextManager):
    """Context manager interface for Neo4j connections."""
    
    @abstractmethod
    def __enter__(self):
        """
        Enter the context manager and return the driver.
        
        Returns:
            Neo4j driver instance
            
        Raises:
            DatabaseConnectionError: If connection fails
        """
        ...
    
    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context manager and close the connection.
        
        Args:
            exc_type: Exception type if an error occurred
            exc_val: Exception value if an error occurred
            exc_tb: Exception traceback if an error occurred
        """
        ...