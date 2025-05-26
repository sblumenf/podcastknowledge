Provider Interfaces
===================

This document describes the provider interfaces for extending the pipeline.

Overview
--------

Providers are pluggable components that handle external services:

- **AudioProvider**: Transcription and diarization
- **LLMProvider**: Language model interactions  
- **GraphProvider**: Graph database operations
- **EmbeddingProvider**: Vector embeddings

Base Interfaces
---------------

AudioProvider
~~~~~~~~~~~~~

.. autoclass:: src.providers.audio.base.AudioProvider
   :members:
   :undoc-members:
   :show-inheritance:

LLMProvider
~~~~~~~~~~~

.. autoclass:: src.providers.llm.base.LLMProvider
   :members:
   :undoc-members:
   :show-inheritance:

GraphProvider
~~~~~~~~~~~~~

.. autoclass:: src.providers.graph.base.GraphProvider
   :members:
   :undoc-members:
   :show-inheritance:

EmbeddingProvider
~~~~~~~~~~~~~~~~~

.. autoclass:: src.providers.embeddings.base.EmbeddingProvider
   :members:
   :undoc-members:
   :show-inheritance:

Built-in Providers
------------------

Audio Providers
~~~~~~~~~~~~~~~

**WhisperAudioProvider**

.. autoclass:: src.providers.audio.whisper.WhisperAudioProvider
   :members:
   :show-inheritance:

Example usage:

.. code-block:: python

   from src.providers.audio.whisper import WhisperAudioProvider
   
   provider = WhisperAudioProvider(
       model_size="base",
       device="cuda",
       compute_type="float16"
   )
   
   transcript = provider.transcribe("episode.mp3")
   segments = provider.diarize("episode.mp3")

LLM Providers
~~~~~~~~~~~~~

**GeminiProvider**

.. autoclass:: src.providers.llm.gemini.GeminiProvider
   :members:
   :show-inheritance:

Example usage:

.. code-block:: python

   from src.providers.llm.gemini import GeminiProvider
   
   provider = GeminiProvider(
       api_key="your-api-key",
       model_name="gemini-1.5-pro",
       temperature=0.7
   )
   
   response = provider.generate(
       prompt="Extract key insights from: ...",
       max_tokens=1000
   )

Graph Providers
~~~~~~~~~~~~~~~

**Neo4jProvider**

.. autoclass:: src.providers.graph.neo4j.Neo4jGraphProvider
   :members:
   :show-inheritance:

Example usage:

.. code-block:: python

   from src.providers.graph.neo4j import Neo4jGraphProvider
   
   provider = Neo4jGraphProvider(
       uri="bolt://localhost:7687",
       auth=("neo4j", "password")
   )
   
   # Create nodes and relationships
   provider.create_node("Podcast", {"name": "Tech Talk"})
   provider.create_relationship(
       "MATCH (p:Podcast), (e:Episode) WHERE id(p)=$pid AND id(e)=$eid",
       "HAS_EPISODE",
       {"pid": podcast_id, "eid": episode_id}
   )

Embedding Providers
~~~~~~~~~~~~~~~~~~~

**SentenceTransformerProvider**

.. autoclass:: src.providers.embeddings.sentence_transformer.SentenceTransformerEmbeddingProvider
   :members:
   :show-inheritance:

Creating Custom Providers
-------------------------

To create a custom provider, implement the appropriate interface:

Example: Custom LLM Provider
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from typing import Optional, Dict, Any
   from src.providers.llm.base import LLMProvider
   
   class CustomLLMProvider(LLMProvider):
       """Custom LLM provider implementation."""
       
       def __init__(self, api_key: str, **kwargs):
           self.api_key = api_key
           self.client = CustomAPIClient(api_key)
       
       def generate(self, 
                   prompt: str,
                   max_tokens: Optional[int] = None,
                   temperature: Optional[float] = None,
                   **kwargs) -> str:
           """Generate text from prompt."""
           response = self.client.complete(
               prompt=prompt,
               max_tokens=max_tokens or 1000,
               temperature=temperature or 0.7
           )
           return response.text
       
       def generate_structured(self,
                             prompt: str,
                             schema: Dict[str, Any],
                             **kwargs) -> Dict[str, Any]:
           """Generate structured output."""
           response = self.generate(
               prompt + f"\nReturn JSON matching schema: {schema}"
           )
           return json.loads(response)
       
       def health_check(self) -> Dict[str, Any]:
           """Check provider health."""
           try:
               self.client.ping()
               return {"status": "healthy", "provider": "custom"}
           except Exception as e:
               return {"status": "unhealthy", "error": str(e)}

Registering Custom Providers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Register your provider with the factory:

.. code-block:: python

   from src.factories.provider_factory import ProviderFactory
   
   # Register provider
   factory = ProviderFactory()
   factory.register_provider(
       provider_type="llm",
       provider_name="custom",
       provider_class=CustomLLMProvider
   )
   
   # Use in configuration
   config = Config()
   config.llm_provider = "custom"
   config.custom_api_key = "your-key"

Provider Health Monitoring
--------------------------

All providers implement health checking:

.. code-block:: python

   # Check individual provider
   health = provider.health_check()
   if health["status"] != "healthy":
       print(f"Provider unhealthy: {health.get('error')}")
   
   # Monitor all providers
   from src.providers.health import ProviderHealthMonitor
   
   monitor = ProviderHealthMonitor([
       audio_provider,
       llm_provider,
       graph_provider
   ])
   
   health_report = monitor.check_all()

Provider Configuration
----------------------

Providers can be configured via:

1. **Constructor parameters**:

   .. code-block:: python

      provider = WhisperAudioProvider(model_size="large")

2. **Configuration file**:

   .. code-block:: yaml

      # config.yml
      audio_provider: whisper
      whisper_model_size: large
      whisper_device: cuda

3. **Environment variables**:

   .. code-block:: bash

      export WHISPER_MODEL_SIZE=large
      export GEMINI_API_KEY=your-key

Best Practices
--------------

1. **Always implement health_check()** for monitoring
2. **Handle rate limiting** in API-based providers
3. **Add retry logic** for transient failures
4. **Log important operations** for debugging
5. **Validate inputs** before processing
6. **Clean up resources** in destructors

See Also
--------

- :doc:`/guides/plugin_development` - Full plugin development guide
- :doc:`/api/processing` - Processing modules that use providers
- :doc:`/examples/custom_provider` - Complete custom provider example