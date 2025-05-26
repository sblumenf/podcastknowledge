Examples
========

This section contains practical examples demonstrating how to use the Podcast Knowledge Graph Pipeline.

.. toctree::
   :maxdepth: 2
   :caption: Example Categories

   basic_usage
   provider_examples
   processing_examples
   advanced_examples
   custom_provider

Overview
--------

The examples are organized into several categories:

Basic Usage
~~~~~~~~~~~

Start here if you're new to the pipeline:

- Processing a single podcast
- Batch processing multiple podcasts
- Using custom configuration
- Error handling basics
- Checkpoint recovery

See :doc:`basic_usage` for complete examples.

Provider Examples
~~~~~~~~~~~~~~~~~

Learn how to work with different providers:

- Audio transcription with Whisper
- LLM integration with Gemini
- Graph operations with Neo4j
- Embedding generation
- Provider composition

See :doc:`provider_examples` for detailed provider usage.

Processing Examples
~~~~~~~~~~~~~~~~~~~

Understand the processing modules:

- Transcript segmentation
- Knowledge extraction
- Entity resolution
- Metrics calculation
- Graph analysis
- Complexity analysis

See :doc:`processing_examples` for processing workflows.

Advanced Examples
~~~~~~~~~~~~~~~~~

Explore advanced features:

- Performance optimization
- Concurrent processing
- Custom pipelines
- Plugin development
- Monitoring and debugging

See :doc:`advanced_examples` for advanced patterns.

Quick Examples
--------------

Process a Single Podcast
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from src.api.v1 import seed_podcast

   result = seed_podcast({
       'name': 'Tech Talk',
       'rss_url': 'https://example.com/feed.xml'
   }, max_episodes=5)

Process Multiple Podcasts
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from src.api.v1 import seed_podcasts

   podcasts = [
       {'name': 'AI Weekly', 'rss_url': 'https://...'},
       {'name': 'Data Science', 'rss_url': 'https://...'}
   ]
   
   result = seed_podcasts(podcasts, max_episodes_each=10)

Custom Configuration
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from src.core.config import Config
   from src.api.v1 import seed_podcast

   config = Config()
   config.batch_size = 50
   config.model_name = 'gemini-1.5-flash'
   
   result = seed_podcast(podcast_config, config=config)

Running the Examples
--------------------

1. **Setup Environment**:

   .. code-block:: bash

      # Clone repository
      git clone https://github.com/yourusername/podcast-kg-pipeline.git
      cd podcast-kg-pipeline
      
      # Install dependencies
      pip install -r requirements.txt

2. **Configure Services**:

   .. code-block:: bash

      # Set environment variables
      export NEO4J_PASSWORD=your-password
      export GOOGLE_API_KEY=your-api-key

3. **Run Examples**:

   .. code-block:: bash

      # Run basic examples
      python docs/examples/basic_usage.py
      
      # Run provider examples
      python docs/examples/provider_examples.py

Example Data
------------

The examples use various data sources:

- **Test RSS Feeds**: Public podcast feeds for testing
- **Sample Transcripts**: Located in `tests/fixtures/`
- **Mock Providers**: For testing without external services

Contributing Examples
---------------------

We welcome new examples! To contribute:

1. Create a new example file in `docs/examples/`
2. Follow the existing pattern with clear comments
3. Test your example works with mock providers
4. Submit a pull request

Tips for Learning
-----------------

1. **Start Simple**: Begin with basic_usage.py
2. **Use Mock Providers**: Test without external services
3. **Read the Logs**: Enable debug logging for insights
4. **Experiment**: Modify examples to learn
5. **Ask Questions**: Use GitHub discussions

Common Patterns
---------------

Error Handling
~~~~~~~~~~~~~~

.. code-block:: python

   try:
       result = seed_podcast(config)
   except Exception as e:
       logger.error(f"Processing failed: {e}")
       # Handle error appropriately

Performance Optimization
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   config = Config()
   config.batch_size = 100  # Larger batches
   config.max_workers = 8   # More parallelism
   config.use_gpu = True    # GPU acceleration

Resource Management
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   pipeline = PodcastKnowledgePipeline(config)
   try:
       result = pipeline.seed_podcast(config)
   finally:
       pipeline.cleanup()  # Always cleanup

Next Steps
----------

After exploring these examples:

1. Check the :doc:`/api/v1` for complete API reference
2. Read :doc:`/guides/plugin_development` to extend the system
3. See :doc:`/guides/troubleshooting` for common issues
4. Explore :doc:`/guides/architecture` for system design