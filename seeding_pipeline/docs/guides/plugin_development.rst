Plugin Development Guide
========================

This guide explains how to extend the Podcast Knowledge Graph Pipeline with custom providers and plugins.

Overview
--------

The pipeline uses a plugin architecture that allows you to:

- Add new audio transcription services
- Integrate different LLM providers
- Support alternative graph databases
- Implement custom embedding models
- Extend processing capabilities

Plugin Architecture
-------------------

.. code-block:: text

   ┌─────────────────────┐
   │   Your Plugin       │
   ├─────────────────────┤
   │ Implements Provider │
   │    Interface        │
   └──────────┬──────────┘
              │
   ┌──────────▼──────────┐
   │  Provider Factory   │
   │  (Registration)     │
   └──────────┬──────────┘
              │
   ┌──────────▼──────────┐
   │      Pipeline       │
   │   (Uses Provider)   │
   └─────────────────────┘

Creating a Custom Provider
--------------------------

Step 1: Choose Provider Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Decide which provider interface to implement:

- ``AudioProvider`` - For transcription/diarization
- ``LLMProvider`` - For language models
- ``GraphProvider`` - For graph databases
- ``EmbeddingProvider`` - For vector embeddings

Step 2: Implement the Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Example: Custom LLM Provider
''''''''''''''''''''''''''''

.. code-block:: python

   # my_plugin/providers/custom_llm.py
   
   from typing import Optional, Dict, Any, List
   import httpx
   from src.providers.llm.base import LLMProvider
   from src.core.exceptions import ProviderError
   
   
   class CustomLLMProvider(LLMProvider):
       """Custom LLM provider using proprietary API."""
       
       def __init__(self, 
                    api_key: str,
                    api_url: str = "https://api.custom-llm.com/v1",
                    model_name: str = "custom-large",
                    timeout: int = 60,
                    **kwargs):
           """Initialize custom LLM provider.
           
           Args:
               api_key: API authentication key
               api_url: Base URL for API
               model_name: Model identifier
               timeout: Request timeout in seconds
           """
           self.api_key = api_key
           self.api_url = api_url
           self.model_name = model_name
           self.timeout = timeout
           self.client = httpx.Client(
               headers={"Authorization": f"Bearer {api_key}"},
               timeout=timeout
           )
       
       def generate(self,
                   prompt: str,
                   max_tokens: Optional[int] = None,
                   temperature: Optional[float] = None,
                   stop_sequences: Optional[List[str]] = None,
                   **kwargs) -> str:
           """Generate text completion.
           
           Args:
               prompt: Input prompt
               max_tokens: Maximum tokens to generate
               temperature: Sampling temperature (0-1)
               stop_sequences: Stop generation at these sequences
               
           Returns:
               Generated text
               
           Raises:
               ProviderError: If generation fails
           """
           try:
               response = self.client.post(
                   f"{self.api_url}/completions",
                   json={
                       "model": self.model_name,
                       "prompt": prompt,
                       "max_tokens": max_tokens or 1000,
                       "temperature": temperature or 0.7,
                       "stop": stop_sequences
                   }
               )
               response.raise_for_status()
               
               return response.json()["choices"][0]["text"]
               
           except httpx.HTTPError as e:
               raise ProviderError(f"API request failed: {e}")
           except KeyError as e:
               raise ProviderError(f"Unexpected API response: {e}")
       
       def generate_structured(self,
                             prompt: str,
                             schema: Dict[str, Any],
                             **kwargs) -> Dict[str, Any]:
           """Generate structured output matching schema.
           
           Args:
               prompt: Input prompt
               schema: Expected output schema
               
           Returns:
               Structured data matching schema
           """
           import json
           
           # Add schema to prompt
           enhanced_prompt = f"""
           {prompt}
           
           Return your response as valid JSON matching this schema:
           {json.dumps(schema, indent=2)}
           """
           
           response = self.generate(enhanced_prompt, **kwargs)
           
           try:
               return json.loads(response)
           except json.JSONDecodeError:
               # Fallback: extract JSON from response
               import re
               json_match = re.search(r'\{.*\}', response, re.DOTALL)
               if json_match:
                   return json.loads(json_match.group())
               raise ProviderError("Failed to parse structured response")
       
       def count_tokens(self, text: str) -> int:
           """Count tokens in text.
           
           Args:
               text: Input text
               
           Returns:
               Token count
           """
           # Simple approximation - override with actual tokenizer
           return len(text.split()) * 1.3
       
       def health_check(self) -> Dict[str, Any]:
           """Check provider health.
           
           Returns:
               Health status dictionary
           """
           try:
               response = self.client.get(f"{self.api_url}/health")
               response.raise_for_status()
               
               return {
                   "status": "healthy",
                   "provider": "custom_llm",
                   "model": self.model_name,
                   "api_status": response.json()
               }
           except Exception as e:
               return {
                   "status": "unhealthy",
                   "provider": "custom_llm",
                   "error": str(e)
               }
       
       def __del__(self):
           """Clean up resources."""
           if hasattr(self, 'client'):
               self.client.close()

Step 3: Add Configuration Support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # my_plugin/config.py
   
   from dataclasses import dataclass
   from typing import Optional
   
   @dataclass
   class CustomLLMConfig:
       """Configuration for custom LLM provider."""
       api_key: str
       api_url: str = "https://api.custom-llm.com/v1"
       model_name: str = "custom-large"
       timeout: int = 60
       max_retries: int = 3
       
       @classmethod
       def from_dict(cls, data: dict) -> 'CustomLLMConfig':
           """Create config from dictionary."""
           return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

Step 4: Register the Provider
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # my_plugin/__init__.py
   
   from src.factories.provider_factory import ProviderFactory
   from .providers.custom_llm import CustomLLMProvider
   from .config import CustomLLMConfig
   
   def register_plugin():
       """Register custom providers with factory."""
       factory = ProviderFactory()
       
       # Register LLM provider
       factory.register_provider(
           provider_type="llm",
           provider_name="custom",
           provider_class=CustomLLMProvider
       )
       
       # Register configuration loader
       factory.register_config(
           provider_name="custom",
           config_class=CustomLLMConfig
       )
   
   # Auto-register on import
   register_plugin()

Step 5: Use Your Plugin
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Use in configuration file
   # config/custom.yml
   llm_provider: custom
   custom_api_key: ${CUSTOM_API_KEY}
   custom_model_name: custom-large-v2
   
   # Use in code
   from src.core.config import Config
   from src.api.v1 import seed_podcast
   import my_plugin  # This registers the provider
   
   config = Config.from_file('config/custom.yml')
   result = seed_podcast(podcast_config, config=config)

Advanced Plugin Features
------------------------

Adding Processing Extensions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create custom processing modules:

.. code-block:: python

   # my_plugin/processing/sentiment.py
   
   from typing import Dict, Any, List
   from src.processing.base import ProcessingModule
   
   class SentimentAnalyzer(ProcessingModule):
       """Add sentiment analysis to insights."""
       
       def process(self, text: str) -> Dict[str, Any]:
           """Analyze sentiment of text."""
           # Your sentiment analysis logic
           sentiment_score = self._analyze_sentiment(text)
           
           return {
               "sentiment": sentiment_score,
               "sentiment_label": self._score_to_label(sentiment_score)
           }
       
       def enhance_insights(self, insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
           """Add sentiment to existing insights."""
           for insight in insights:
               sentiment_data = self.process(insight['text'])
               insight.update(sentiment_data)
           return insights

Hooking into the Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # my_plugin/hooks.py
   
   from src.seeding.orchestrator import PodcastKnowledgePipeline
   
   def add_sentiment_processing(pipeline: PodcastKnowledgePipeline):
       """Add sentiment analysis to pipeline."""
       from .processing.sentiment import SentimentAnalyzer
       
       # Monkey-patch or use event system
       original_extract = pipeline.knowledge_extractor.extract
       sentiment_analyzer = SentimentAnalyzer()
       
       def extract_with_sentiment(*args, **kwargs):
           results = original_extract(*args, **kwargs)
           results['insights'] = sentiment_analyzer.enhance_insights(
               results.get('insights', [])
           )
           return results
       
       pipeline.knowledge_extractor.extract = extract_with_sentiment

Testing Your Plugin
-------------------

Unit Tests
~~~~~~~~~~

.. code-block:: python

   # tests/test_custom_llm.py
   
   import pytest
   from unittest.mock import Mock, patch
   from my_plugin.providers.custom_llm import CustomLLMProvider
   
   class TestCustomLLMProvider:
       
       @pytest.fixture
       def provider(self):
           return CustomLLMProvider(
               api_key="test-key",
               api_url="https://test.com"
           )
       
       def test_generate(self, provider):
           with patch.object(provider.client, 'post') as mock_post:
               mock_post.return_value.json.return_value = {
                   "choices": [{"text": "Generated text"}]
               }
               
               result = provider.generate("Test prompt")
               assert result == "Generated text"
       
       def test_health_check(self, provider):
           with patch.object(provider.client, 'get') as mock_get:
               mock_get.return_value.json.return_value = {"status": "ok"}
               
               health = provider.health_check()
               assert health["status"] == "healthy"

Integration Tests
~~~~~~~~~~~~~~~~~

.. code-block:: python

   # tests/test_integration.py
   
   def test_plugin_with_pipeline():
       """Test plugin works with full pipeline."""
       import my_plugin  # Register provider
       
       config = Config()
       config.llm_provider = "custom"
       config.custom_api_key = "test-key"
       
       # Mock the API calls
       with patch('httpx.Client.post') as mock_post:
           mock_post.return_value.json.return_value = {
               "choices": [{"text": '{"insights": []}'}]
           }
           
           result = seed_podcast(
               {"name": "Test", "rss_url": "https://..."},
               config=config,
               max_episodes=1
           )
           
           assert result['episodes_processed'] >= 0

Best Practices
--------------

1. **Follow the Interface Contract**
   
   - Implement all required methods
   - Return expected types
   - Handle errors gracefully

2. **Add Comprehensive Logging**

   .. code-block:: python

      import logging
      
      logger = logging.getLogger(__name__)
      
      class MyProvider:
          def generate(self, prompt):
              logger.debug(f"Generating with prompt length: {len(prompt)}")
              # ... implementation ...
              logger.info("Generation completed successfully")

3. **Handle Rate Limiting**

   .. code-block:: python

      from src.utils.rate_limiting import RateLimiter
      
      class MyProvider:
          def __init__(self):
              self.rate_limiter = RateLimiter(
                  calls_per_minute=60,
                  tokens_per_minute=100000
              )
          
          def generate(self, prompt):
              with self.rate_limiter:
                  # API call here
                  pass

4. **Validate Configuration**

   .. code-block:: python

      def __init__(self, **config):
          # Validate required fields
          if not config.get('api_key'):
              raise ConfigurationError("API key is required")
          
          # Validate values
          if config.get('timeout', 60) < 1:
              raise ConfigurationError("Timeout must be positive")

5. **Clean Up Resources**

   .. code-block:: python

      def __del__(self):
          if hasattr(self, 'client'):
              self.client.close()
          if hasattr(self, 'connection'):
              self.connection.disconnect()

Distribution
------------

Package your plugin:

.. code-block:: python

   # setup.py
   from setuptools import setup, find_packages
   
   setup(
       name="podcast-kg-custom-llm",
       version="0.1.0",
       packages=find_packages(),
       install_requires=[
           "podcast-kg-pipeline>=0.1.0",
           "httpx>=0.24.0",
       ],
       entry_points={
           "podcast_kg.plugins": [
               "custom_llm = my_plugin:register_plugin",
           ]
       }
   )

Users can then install:

.. code-block:: bash

   pip install podcast-kg-custom-llm

The plugin auto-registers on import!

See Also
--------

- :doc:`/api/providers` - Provider interface reference
- :doc:`/examples/custom_provider` - Complete example
- :doc:`/guides/architecture` - System architecture