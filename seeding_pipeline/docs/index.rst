Podcast Knowledge Graph Pipeline Documentation
==============================================

Welcome to the Podcast Knowledge Graph Pipeline documentation! This system transforms podcast audio into structured knowledge graphs using AI-powered analysis.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart
   configuration

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   guides/basic_usage
   guides/advanced_features
   guides/troubleshooting
   guides/migration

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/v1
   api/providers
   api/processing
   api/utilities

.. toctree::
   :maxdepth: 2
   :caption: Developer Guide

   guides/plugin_development
   guides/contributing
   guides/architecture
   guides/debugging

.. toctree::
   :maxdepth: 1
   :caption: Additional Resources

   examples/index
   changelog
   license

Overview
--------

The Podcast Knowledge Graph Pipeline is a modular system for extracting structured knowledge from podcast audio. It:

* **Transcribes** podcast audio using Whisper
* **Segments** content into meaningful chunks
* **Extracts** insights, entities, and relationships using LLMs
* **Builds** a Neo4j knowledge graph
* **Provides** APIs for batch processing and integration

Key Features
------------

* **Modular Architecture**: Plug-in different providers for audio, LLM, and graph processing
* **Scalable Processing**: Handle single episodes or entire podcast catalogs
* **Checkpoint Recovery**: Resume processing after interruptions
* **Production Ready**: Comprehensive error handling and resource management
* **API Versioning**: Stable v1 API with backward compatibility guarantees

Quick Example
-------------

.. code-block:: python

   from src.api.v1 import seed_podcast

   # Process a single podcast
   result = seed_podcast({
       'name': 'My Favorite Podcast',
       'rss_url': 'https://example.com/podcast/feed.xml'
   }, max_episodes=5)

   print(f"Processed {result['episodes_processed']} episodes")
   print(f"Created {result['insights_created']} insights")

Architecture Overview
--------------------

.. code-block:: text

   ┌─────────────────────────────────────────────────────────────────┐
   │                          CLI / API                                │
   ├─────────────────────────────────────────────────────────────────┤
   │                    Pipeline Orchestrator                          │
   ├─────────────────────────────────────────────────────────────────┤
   │   Audio      │   Knowledge    │    Graph       │   Utility       │
   │ Processing   │  Extraction    │  Operations    │  Functions      │
   ├─────────────────────────────────────────────────────────────────┤
   │                     Provider Interfaces                           │
   │   AudioProvider  │  LLMProvider  │  GraphProvider  │  Embeddings │
   ├─────────────────────────────────────────────────────────────────┤
   │                    Core Models & Config                           │
   └─────────────────────────────────────────────────────────────────┘

Getting Help
------------

* **GitHub Issues**: https://github.com/yourusername/podcast-kg-pipeline/issues
* **Documentation**: You're here!
* **Examples**: See the :doc:`examples/index` section

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`