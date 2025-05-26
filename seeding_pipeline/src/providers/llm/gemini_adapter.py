"""
Gemini LLM Adapter for Neo4j GraphRAG SimpleKGPipeline.

This adapter allows the existing GeminiProvider to work with neo4j-graphrag's
LLMInterface which expects an `invoke` method.
"""

import logging
from typing import Dict, Any, Optional, List, Union
import json

from src.providers.llm.gemini import GeminiProvider

logger = logging.getLogger(__name__)


class GeminiGraphRAGAdapter:
    """
    Adapter class that makes GeminiProvider compatible with neo4j-graphrag's LLMInterface.
    
    The neo4j-graphrag library expects LLM objects to have an `invoke` method that
    accepts a prompt string and returns a response. This adapter bridges our existing
    GeminiProvider with that interface.
    """
    
    def __init__(self, gemini_provider: Optional[GeminiProvider] = None, **kwargs):
        """
        Initialize the adapter with a GeminiProvider instance or config.
        
        Args:
            gemini_provider: Existing GeminiProvider instance
            **kwargs: Configuration parameters if creating new provider
        """
        if gemini_provider:
            self.provider = gemini_provider
        else:
            # Create new provider with provided config
            self.provider = GeminiProvider(kwargs)
        
        # Store model parameters that SimpleKGPipeline might expect
        self.model_name = self.provider.model_name
        self.model_params = {
            "temperature": self.provider.temperature,
            "max_tokens": self.provider.max_tokens,
        }
        
        # Handle response format for JSON extraction
        if kwargs.get('model_params', {}).get('response_format', {}).get('type') == 'json_object':
            self.json_mode = True
        else:
            self.json_mode = False
    
    def invoke(self, prompt: Union[str, List[Dict[str, str]]]) -> Any:
        """
        Invoke the LLM with a prompt, compatible with neo4j-graphrag interface.
        
        Args:
            prompt: Either a string prompt or a list of message dicts
            
        Returns:
            Response object with 'content' attribute or string response
        """
        try:
            # Handle different prompt formats
            if isinstance(prompt, list):
                # Convert message list to single prompt
                prompt_str = self._messages_to_prompt(prompt)
            else:
                prompt_str = str(prompt)
            
            # Add JSON instruction if in JSON mode
            if self.json_mode:
                prompt_str = self._add_json_instruction(prompt_str)
            
            # Get response from Gemini
            response = self.provider.complete(prompt_str)
            
            # Create response object similar to OpenAI's response format
            class Response:
                def __init__(self, content):
                    self.content = content
            
            return Response(response)
            
        except Exception as e:
            logger.error(f"Error invoking Gemini through adapter: {e}")
            raise
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert a list of message dicts to a single prompt string."""
        prompt_parts = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'system':
                prompt_parts.append(f"System: {content}")
            elif role == 'user':
                prompt_parts.append(f"User: {content}")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")
        
        return "\n\n".join(prompt_parts)
    
    def _add_json_instruction(self, prompt: str) -> str:
        """Add JSON formatting instruction to prompt."""
        json_instruction = "\n\nIMPORTANT: Respond only with valid JSON. Do not include any text before or after the JSON object."
        return prompt + json_instruction
    
    # Additional methods that neo4j-graphrag might expect
    
    def get_num_tokens(self, text: str) -> int:
        """Estimate token count for rate limiting compatibility."""
        # Rough estimation similar to what GeminiProvider does
        return int(len(text.split()) * 1.3)
    
    async def ainvoke(self, prompt: Union[str, List[Dict[str, str]]]) -> Any:
        """Async version of invoke for compatibility."""
        # For now, just wrap the sync version
        # In future, could implement true async support
        return self.invoke(prompt)
    
    @property
    def supports_async(self) -> bool:
        """Indicate async support."""
        return True
    
    @property 
    def supports_json_mode(self) -> bool:
        """Indicate JSON mode support."""
        return True
    
    def __repr__(self) -> str:
        """String representation."""
        return f"GeminiGraphRAGAdapter(model={self.model_name})"


# Convenience function to create adapter from config
def create_gemini_adapter(config: Dict[str, Any]) -> GeminiGraphRAGAdapter:
    """
    Create a GeminiGraphRAGAdapter from configuration.
    
    Args:
        config: Configuration dict with Gemini settings
        
    Returns:
        Configured GeminiGraphRAGAdapter instance
    """
    # Ensure required parameters
    if 'api_key' not in config:
        raise ValueError("Gemini API key is required in config")
    
    # Set defaults for GraphRAG compatibility
    config.setdefault('model_name', 'gemini-2.0-flash')
    config.setdefault('temperature', 0)  # Low temperature for structured extraction
    config.setdefault('max_tokens', 2000)
    
    return GeminiGraphRAGAdapter(**config)