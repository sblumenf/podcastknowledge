"""Mock LLM provider for testing."""

from typing import Dict, Any, List
import json
import hashlib

from src.providers.llm.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider that returns predefined responses for testing."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize mock provider with configuration."""
        super().__init__(config)
        
        # Predefined responses for different prompt patterns
        self.responses = config.get('responses', {})
        self.default_response = config.get('default_response', 'Mock response')
        self.response_mode = config.get('response_mode', 'fixed')  # fixed, hash, echo
        
        # For testing rate limits
        self.call_count = 0
        self.last_prompts = []
        
    def _initialize_client(self) -> None:
        """No client initialization needed for mock provider."""
        pass
        
    def complete(self, prompt: str, **kwargs) -> str:
        """Generate mock completion for the given prompt."""
        self._ensure_initialized()
        
        self.call_count += 1
        self.last_prompts.append(prompt)
        
        # Different response modes for testing
        if self.response_mode == 'echo':
            return f"Echo: {prompt}"
            
        elif self.response_mode == 'hash':
            # Deterministic response based on prompt hash
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
            return f"Response-{prompt_hash}"
            
        elif self.response_mode == 'json':
            # Return valid JSON for parsing tests
            return json.dumps({
                'entities': ['Entity1', 'Entity2'],
                'insights': ['Insight about the topic'],
                'quotes': [{'text': 'Sample quote', 'speaker': 'Speaker1'}]
            })
            
        else:  # fixed mode
            # Check if we have a specific response for this prompt pattern
            for pattern, response in self.responses.items():
                if pattern.lower() in prompt.lower():
                    return response
                    
            return self.default_response
            
    def complete_with_options(self, prompt: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock completion with additional options."""
        self._ensure_initialized()
        
        content = self.complete(prompt)
        
        return {
            'content': content,
            'model': self.model_name,
            'temperature': options.get('temperature', self.temperature),
            'max_tokens': options.get('max_tokens', self.max_tokens),
            'usage': {
                'prompt_tokens': len(prompt.split()),
                'completion_tokens': len(content.split()),
                'total_tokens': len(prompt.split()) + len(content.split())
            },
            'mock': True
        }
        
    def batch_complete(self, prompts: List[str], **kwargs) -> List[str]:
        """Process multiple prompts."""
        return [self.complete(prompt, **kwargs) for prompt in prompts]
        
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get mock rate limit status."""
        return {
            'mock_provider': {
                'calls_made': self.call_count,
                'rate_limited': False,
                'limits': {'rpm': 1000, 'tpm': 1000000, 'rpd': 10000}
            }
        }
        
    def health_check(self) -> Dict[str, Any]:
        """Check mock provider health (always healthy)."""
        return {
            'healthy': True,
            'provider': 'MockLLMProvider',
            'model': self.model_name,
            'call_count': self.call_count,
            'response_mode': self.response_mode,
            'initialized': True
        }
        
    # Additional methods for testing
    def reset_stats(self) -> None:
        """Reset call statistics."""
        self.call_count = 0
        self.last_prompts = []
        
    def get_last_prompts(self) -> List[str]:
        """Get list of prompts received."""
        return self.last_prompts.copy()
        
    def set_response(self, pattern: str, response: str) -> None:
        """Set a specific response for a prompt pattern."""
        self.responses[pattern] = response
        
    def set_response_mode(self, mode: str) -> None:
        """Change response mode."""
        if mode in ['fixed', 'hash', 'echo', 'json']:
            self.response_mode = mode
        else:
            raise ValueError(f"Invalid response mode: {mode}")