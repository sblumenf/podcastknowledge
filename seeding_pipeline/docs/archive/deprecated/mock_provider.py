"""Mock LLM provider for testing and validation."""

from typing import Dict, Any, List, Optional
import json
import re

from src.core.interfaces import LLMProvider


class MockLLMProvider(LLMProvider):
    """Mock LLM provider that returns predefined responses for testing."""
    
    def __init__(self):
        """Initialize mock provider with response patterns."""
        self.responses = {
            'entity': self._get_entity_response,
            'insight': self._get_insight_response,
            'quote': self._get_quote_response,
            'topic': self._get_topic_response
        }
    
    def complete(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Generate mock completion based on prompt content.
        
        Args:
            prompt: The prompt to complete
            max_tokens: Maximum tokens (ignored in mock)
            temperature: Temperature (ignored in mock)
            **kwargs: Additional arguments (ignored)
            
        Returns:
            Mock response based on prompt type
        """
        # Determine response type from prompt
        prompt_lower = prompt.lower()
        
        if 'extract named entities' in prompt_lower or 'entity' in prompt_lower:
            return self._get_entity_response(prompt)
        elif 'extract key insights' in prompt_lower or 'insight' in prompt_lower:
            return self._get_insight_response(prompt)
        elif 'extract notable quotes' in prompt_lower or 'quote' in prompt_lower:
            return self._get_quote_response(prompt)
        elif 'identify the main topics' in prompt_lower or 'topic' in prompt_lower:
            return self._get_topic_response(prompt)
        else:
            return "Mock response for: " + prompt[:100]
    
    def embed(self, text: str) -> List[float]:
        """
        Generate mock embedding.
        
        Args:
            text: Text to embed
            
        Returns:
            Mock embedding vector
        """
        # Simple mock: generate consistent embedding based on text hash
        import hashlib
        
        # Generate deterministic values based on text
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        # Convert to float values between -1 and 1
        embedding = []
        for i in range(0, min(len(text_hash), 32), 2):
            value = int(text_hash[i:i+2], 16) / 128.0 - 1.0
            embedding.append(value)
        
        # Pad to standard size (e.g., 1536 for text-embedding-ada-002)
        while len(embedding) < 1536:
            embedding.append(0.0)
        
        return embedding[:1536]
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Generate mock chat completion.
        
        Args:
            messages: Chat messages
            max_tokens: Maximum tokens (ignored)
            temperature: Temperature (ignored)
            **kwargs: Additional arguments (ignored)
            
        Returns:
            Mock chat response
        """
        # Use the last user message for response
        user_messages = [m for m in messages if m.get('role') == 'user']
        if user_messages:
            return self.complete(user_messages[-1].get('content', ''))
        return "Mock chat response"
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check provider health.
        
        Returns:
            Health status dictionary
        """
        return {
            'status': 'healthy',
            'provider': 'mock',
            'version': '1.0',
            'features': ['completion', 'embedding', 'chat']
        }
    
    def _get_entity_response(self, prompt: str) -> str:
        """Generate mock entity extraction response."""
        # Extract some keywords from the prompt to make it contextual
        entities = []
        
        # Look for common patterns
        if 'artificial intelligence' in prompt.lower() or 'ai' in prompt.lower():
            entities.append({
                'name': 'Artificial Intelligence',
                'type': 'TECHNOLOGY',
                'description': 'Advanced computational technology',
                'frequency': 3,
                'confidence': 0.9
            })
        
        if 'machine learning' in prompt.lower() or 'ml' in prompt.lower():
            entities.append({
                'name': 'Machine Learning',
                'type': 'TECHNOLOGY',
                'description': 'Subset of AI for pattern recognition',
                'frequency': 2,
                'confidence': 0.85
            })
        
        if 'healthcare' in prompt.lower() or 'medical' in prompt.lower():
            entities.append({
                'name': 'Healthcare',
                'type': 'CONCEPT',
                'description': 'Medical and health services industry',
                'frequency': 2,
                'confidence': 0.8
            })
        
        # Look for person names (simple pattern)
        person_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b'
        for match in re.finditer(person_pattern, prompt):
            name = match.group(1)
            if name not in ['Extract Named', 'Entity Types']:  # Filter out prompt text
                entities.append({
                    'name': name,
                    'type': 'PERSON',
                    'description': 'Person mentioned in discussion',
                    'frequency': 1,
                    'confidence': 0.7
                })
        
        # Default entities if none found
        if not entities:
            entities = [
                {
                    'name': 'Technology',
                    'type': 'CONCEPT',
                    'description': 'General technology discussion',
                    'frequency': 1,
                    'confidence': 0.6
                }
            ]
        
        return json.dumps(entities, indent=2)
    
    def _get_insight_response(self, prompt: str) -> str:
        """Generate mock insight extraction response."""
        insights = []
        
        # Generate insights based on prompt content
        if 'ai' in prompt.lower() or 'artificial intelligence' in prompt.lower():
            insights.append({
                'content': 'AI is transforming healthcare through advanced diagnostics',
                'type': 'TREND',
                'confidence': 0.8,
                'supporting_evidence': 'Multiple mentions of AI applications'
            })
        
        if 'machine learning' in prompt.lower():
            insights.append({
                'content': 'ML algorithms improve diagnosis accuracy to 95%',
                'type': 'FACT',
                'confidence': 0.9,
                'supporting_evidence': 'Specific accuracy metrics mentioned'
            })
        
        if 'revolutionary' in prompt.lower() or 'transform' in prompt.lower():
            insights.append({
                'content': 'The technology represents a paradigm shift in the field',
                'type': 'OPINION',
                'confidence': 0.7,
                'supporting_evidence': 'Strong language indicating major change'
            })
        
        # Default insight
        if not insights:
            insights.append({
                'content': 'The discussion covers important technological advances',
                'type': 'OBSERVATION',
                'confidence': 0.6
            })
        
        return json.dumps(insights, indent=2)
    
    def _get_quote_response(self, prompt: str) -> str:
        """Generate mock quote extraction response."""
        quotes = []
        
        # Simple quote pattern matching
        quote_pattern = r'"([^"]+)"'
        for match in re.finditer(quote_pattern, prompt):
            quote_text = match.group(1)
            if len(quote_text) > 10:  # Filter out short strings
                quotes.append({
                    'text': quote_text,
                    'speaker': 'Expert',
                    'context': 'Key point in discussion',
                    'type': 'STATEMENT',
                    'timestamp': '00:01:00'
                })
        
        # Add specific quotes based on content
        if 'revolutionary' in prompt.lower():
            quotes.append({
                'text': 'This is revolutionary',
                'speaker': 'Host',
                'context': 'Reacting to new information',
                'type': 'OPINION',
                'timestamp': '00:02:30'
            })
        
        # Default quote if none found
        if not quotes:
            quotes.append({
                'text': 'This technology will change everything',
                'speaker': 'Expert',
                'context': 'Main thesis statement',
                'type': 'PREDICTION',
                'timestamp': '00:00:30'
            })
        
        # Format as expected by parser
        formatted_quotes = []
        for q in quotes:
            formatted_quotes.append(
                f'"{q["text"]}" - {q["speaker"]}\n'
                f'Context: {q["context"]}\n'
                f'Type: {q["type"]}\n'
            )
        
        return '\n'.join(formatted_quotes)
    
    def _get_topic_response(self, prompt: str) -> str:
        """Generate mock topic identification response."""
        topics = []
        
        # Identify topics based on entities mentioned
        if 'ai' in prompt.lower() and 'healthcare' in prompt.lower():
            topics.append({
                'name': 'AI in Healthcare',
                'description': 'Application of artificial intelligence in medical field'
            })
        
        if 'machine learning' in prompt.lower():
            topics.append({
                'name': 'Machine Learning Applications',
                'description': 'Practical uses of ML algorithms'
            })
        
        if 'future' in prompt.lower() or 'transform' in prompt.lower():
            topics.append({
                'name': 'Future of Medicine',
                'description': 'Predictions about technological impact on healthcare'
            })
        
        # Default topics
        if not topics:
            topics.append({
                'name': 'Technology Discussion',
                'description': 'General discussion about technology'
            })
        
        # Format as numbered list
        formatted_topics = []
        for i, topic in enumerate(topics, 1):
            formatted_topics.append(
                f"{i}. {topic['name']} - {topic['description']}"
            )
        
        return '\n'.join(formatted_topics)