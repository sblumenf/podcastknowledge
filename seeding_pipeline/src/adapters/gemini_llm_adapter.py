"""Gemini LLM adapter for SimpleKGPipeline integration.

This adapter bridges the existing Gemini LLM service with the SimpleKGPipeline's
LLMInterface requirements, enabling the use of our configured Gemini setup
within the neo4j-graphrag pipeline.
"""

import logging
from typing import Optional

from neo4j_graphrag.llm import LLMInterface, LLMResponse

from src.services.llm import LLMService

logger = logging.getLogger(__name__)


class GeminiLLMAdapter(LLMInterface):
    """Adapter to make LLMService compatible with SimpleKGPipeline.
    
    This adapter wraps the existing LLMService to provide the
    LLMInterface methods required by neo4j-graphrag's SimpleKGPipeline.
    """
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 model_name: str = 'gemini-2.5-flash',
                 temperature: float = 0.7,
                 max_tokens: int = 4096,
                 enable_cache: bool = True,
                 cache_ttl: int = 3600):
        """Initialize the Gemini LLM adapter.
        
        Args:
            api_key: Gemini API key (uses environment if not provided)
            model_name: Model to use (default: gemini-2.5-flash)
            temperature: Generation temperature (default: 0.7)
            max_tokens: Maximum output tokens (default: 4096)
            enable_cache: Enable response caching (default: True)
            cache_ttl: Cache time-to-live in seconds (default: 3600)
        """
        self.gemini_service = LLMService(
            api_key=api_key,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            enable_cache=enable_cache,
            cache_ttl=cache_ttl
        )
        
        # Store configuration for debugging
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        logger.info(f"Initialized GeminiLLMAdapter with model: {model_name}")
    
    def invoke(self, input: str) -> LLMResponse:
        """Synchronously invoke the Gemini LLM.
        
        Args:
            input: The prompt text to send to the LLM
            
        Returns:
            LLMResponse: Response object containing the generated content
            
        Raises:
            Exception: If the API call fails
        """
        try:
            logger.debug(f"Invoking Gemini LLM with prompt length: {len(input)}")
            
            # Use the existing Gemini service to generate completion
            content = self.gemini_service.complete(input)
            
            # Wrap response in LLMResponse object
            response = LLMResponse(content=content)
            
            logger.debug(f"Gemini LLM response length: {len(content)}")
            return response
            
        except Exception as e:
            logger.error(f"Gemini LLM adapter invoke failed: {e}")
            raise
    
    async def ainvoke(self, input: str) -> LLMResponse:
        """Asynchronously invoke the Gemini LLM.
        
        For now, this delegates to the synchronous invoke method since
        the underlying GeminiDirectService doesn't have async support yet.
        
        Args:
            input: The prompt text to send to the LLM
            
        Returns:
            LLMResponse: Response object containing the generated content
            
        Raises:
            Exception: If the API call fails
        """
        try:
            logger.debug(f"Async invoking Gemini LLM with prompt length: {len(input)}")
            
            # For now, delegate to sync method
            # TODO: Implement true async support in GeminiDirectService
            response = self.invoke(input)
            
            return response
            
        except Exception as e:
            logger.error(f"Gemini LLM adapter async invoke failed: {e}")
            raise
    
    def get_model_name(self) -> str:
        """Get the model name being used.
        
        Returns:
            str: The model name
        """
        return self.model_name
    
    def get_service(self) -> LLMService:
        """Get the underlying Gemini service instance.
        
        Returns:
            LLMService: The wrapped service instance
        """
        return self.gemini_service