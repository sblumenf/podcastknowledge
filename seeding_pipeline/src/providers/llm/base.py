"""Base LLM provider implementation."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from src.core.interfaces import LLMProvider, HealthCheckable


@dataclass
class LLMResponse:
    """Standard response from LLM providers."""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseLLMProvider(LLMProvider, HealthCheckable, ABC):
    """Base implementation for LLM providers with common functionality."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the LLM provider with configuration."""
        self.config = config
        self.model_name = config.get('model_name', 'unknown')
        self.temperature = config.get('temperature', 0.7)
        self.max_tokens = config.get('max_tokens', 4096)
        self._initialized = False
        
    @abstractmethod
    def _initialize_client(self) -> None:
        """Initialize the underlying LLM client."""
        pass
        
    def _ensure_initialized(self) -> None:
        """Ensure the provider is initialized."""
        if not self._initialized:
            self._initialize_client()
            self._initialized = True
            
    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> str:
        """Generate completion for the given prompt."""
        pass
        
    @abstractmethod
    def complete_with_options(self, prompt: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Generate completion with additional options."""
        pass
        
    def batch_complete(self, prompts: List[str], **kwargs) -> List[str]:
        """Process multiple prompts (default implementation processes sequentially)."""
        self._ensure_initialized()
        return [self.complete(prompt, **kwargs) for prompt in prompts]
        
    @abstractmethod
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        pass
        
    def health_check(self) -> Dict[str, Any]:
        """Check provider health."""
        try:
            self._ensure_initialized()
            # Try a simple completion
            test_response = self.complete("Hello, please respond with 'OK'")
            
            return {
                'healthy': True,
                'provider': self.__class__.__name__,
                'model': self.model_name,
                'test_response': test_response[:50] if test_response else None,
                'initialized': self._initialized
            }
        except Exception as e:
            return {
                'healthy': False,
                'provider': self.__class__.__name__,
                'model': self.model_name,
                'error': str(e),
                'initialized': self._initialized
            }