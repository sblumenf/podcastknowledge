Troubleshooting Guide
=====================

This guide helps you resolve common issues with the Podcast Knowledge Graph Pipeline.

Common Issues
-------------

Neo4j Connection Problems
~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptom**: ``ConnectionRefusedError`` or ``ServiceUnavailable``

**Solutions**:

1. **Check Neo4j is running**:

   .. code-block:: bash

      # Check if Neo4j is running
      systemctl status neo4j  # Linux
      brew services list      # macOS
      
      # Or check with Docker
      docker ps | grep neo4j

2. **Verify connection details**:

   .. code-block:: python

      # Test connection manually
      from neo4j import GraphDatabase
      
      driver = GraphDatabase.driver(
          "bolt://localhost:7687",
          auth=("neo4j", "your-password")
      )
      
      with driver.session() as session:
          result = session.run("RETURN 1")
          print(result.single()[0])

3. **Check firewall/ports**:

   .. code-block:: bash

      # Check if port 7687 is open
      netstat -an | grep 7687
      
      # Test connection
      telnet localhost 7687

Memory Issues
~~~~~~~~~~~~~

**Symptom**: ``MemoryError`` or system becoming unresponsive

**Solutions**:

1. **Reduce batch size**:

   .. code-block:: python

      config = Config()
      config.batch_size = 5  # Smaller batches
      config.max_workers = 2  # Fewer parallel workers

2. **Process fewer episodes**:

   .. code-block:: python

      # Process in smaller chunks
      for i in range(0, 100, 10):
          result = seed_podcast(
              podcast_config,
              max_episodes=10,
              start_index=i
          )

3. **Enable memory cleanup**:

   .. code-block:: python

      # Force garbage collection
      import gc
      gc.collect()
      
      # Monitor memory usage
      import psutil
      process = psutil.Process()
      print(f"Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")

API Rate Limiting
~~~~~~~~~~~~~~~~~

**Symptom**: ``429 Too Many Requests`` or ``RateLimitError``

**Solutions**:

1. **Adjust rate limiting settings**:

   .. code-block:: python

      config = Config()
      config.rate_limit_calls = 10  # Calls per minute
      config.rate_limit_tokens = 100000  # Tokens per minute

2. **Add delays between requests**:

   .. code-block:: python

      import time
      
      for podcast in podcasts:
          result = seed_podcast(podcast)
          time.sleep(2)  # 2 second delay

3. **Use exponential backoff**:

   .. code-block:: python

      from src.utils.retry import with_retry
      
      @with_retry(max_attempts=3, backoff_factor=2)
      def process_with_retry(config):
          return seed_podcast(config)

Audio Processing Errors
~~~~~~~~~~~~~~~~~~~~~~~

**Symptom**: ``FFmpeg not found`` or ``Audio format not supported``

**Solutions**:

1. **Install FFmpeg**:

   .. code-block:: bash

      # Ubuntu/Debian
      sudo apt update && sudo apt install ffmpeg
      
      # macOS
      brew install ffmpeg
      
      # Verify installation
      ffmpeg -version

2. **Convert audio format**:

   .. code-block:: bash

      # Convert to supported format
      ffmpeg -i podcast.m4a -acodec mp3 podcast.mp3

3. **Check audio file**:

   .. code-block:: python

      # Validate audio file
      import os
      
      if not os.path.exists(audio_path):
          print(f"File not found: {audio_path}")
      
      # Check file size
      size_mb = os.path.getsize(audio_path) / (1024 * 1024)
      if size_mb > 500:
          print(f"File too large: {size_mb:.1f} MB")

LLM Provider Errors
~~~~~~~~~~~~~~~~~~~

**Symptom**: ``Invalid API key`` or ``Model not found``

**Solutions**:

1. **Verify API credentials**:

   .. code-block:: bash

      # Check environment variable
      echo $GOOGLE_API_KEY
      
      # Test API key
      curl -H "x-goog-api-key: $GOOGLE_API_KEY" \
        https://generativelanguage.googleapis.com/v1/models

2. **Check model availability**:

   .. code-block:: python

      from src.providers.llm.gemini import GeminiProvider
      
      provider = GeminiProvider(api_key="your-key")
      models = provider.list_models()
      print("Available models:", models)

3. **Use fallback model**:

   .. code-block:: python

      config = Config()
      config.model_name = "gemini-1.5-flash"  # Use if pro unavailable

Checkpoint Recovery Issues
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptom**: Processing restarts from beginning instead of resuming

**Solutions**:

1. **Verify checkpoint directory**:

   .. code-block:: python

      import os
      
      checkpoint_dir = "./checkpoints"
      if not os.path.exists(checkpoint_dir):
          os.makedirs(checkpoint_dir)
      
      # Check for checkpoint files
      checkpoints = os.listdir(checkpoint_dir)
      print(f"Found {len(checkpoints)} checkpoint files")

2. **Clear corrupted checkpoints**:

   .. code-block:: bash

      # Remove old checkpoints
      rm -rf checkpoints/*.json
      
      # Or selectively remove
      find checkpoints -name "*.json" -mtime +7 -delete

3. **Debug checkpoint loading**:

   .. code-block:: python

      from src.utils.resources import ProgressCheckpoint
      
      checkpoint = ProgressCheckpoint("./checkpoints")
      state = checkpoint.load_checkpoint("podcast_name")
      print("Checkpoint state:", state)

Performance Issues
~~~~~~~~~~~~~~~~~~

**Symptom**: Processing is very slow

**Solutions**:

1. **Profile the code**:

   .. code-block:: python

      import cProfile
      import pstats
      
      profiler = cProfile.Profile()
      profiler.enable()
      
      result = seed_podcast(podcast_config)
      
      profiler.disable()
      stats = pstats.Stats(profiler)
      stats.sort_stats('cumulative')
      stats.print_stats(10)  # Top 10 functions

2. **Use GPU acceleration**:

   .. code-block:: python

      config = Config()
      config.whisper_device = "cuda"  # Use GPU
      config.whisper_compute_type = "float16"  # Faster computation

3. **Optimize settings**:

   .. code-block:: python

      # Performance-optimized configuration
      config = Config()
      config.batch_size = 50
      config.max_workers = 8
      config.use_large_context = False
      config.enable_diarization = False

Debugging Techniques
--------------------

Enable Debug Logging
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import logging
   
   # Enable debug logging
   logging.basicConfig(level=logging.DEBUG)
   
   # Or for specific module
   logging.getLogger('src.processing.extraction').setLevel(logging.DEBUG)

Trace Execution
~~~~~~~~~~~~~~~

.. code-block:: python

   # Use debugging context
   from src.utils.debugging import debug_context
   
   with debug_context("processing_episode"):
       result = seed_podcast(podcast_config)

Check System Resources
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from src.utils.debugging import SystemMonitor
   
   monitor = SystemMonitor()
   monitor.start()
   
   # Your processing here
   result = seed_podcast(podcast_config)
   
   report = monitor.stop()
   print(f"Peak memory: {report['peak_memory_mb']:.1f} MB")
   print(f"CPU usage: {report['avg_cpu_percent']:.1f}%")

Getting Help
------------

If you're still experiencing issues:

1. **Check the logs**:

   .. code-block:: bash

      # Look for error patterns
      grep -i error podcast_kg.log
      
      # Check recent logs
      tail -f podcast_kg.log

2. **Run diagnostics**:

   .. code-block:: bash

      # Run health check
      python cli.py health
      
      # Validate configuration
      python cli.py validate-config --config config.yml

3. **Create minimal reproduction**:

   .. code-block:: python

      # Minimal test case
      from src.api.v1 import seed_podcast
      
      result = seed_podcast({
          'name': 'Test',
          'rss_url': 'https://example.com/feed.xml'
      }, max_episodes=1)
      
      print(result)

4. **Report an issue**:
   
   - GitHub Issues: https://github.com/yourusername/podcast-kg-pipeline/issues
   - Include: Error message, stack trace, configuration, steps to reproduce

Common Error Messages
---------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Error Message
     - Solution
   * - ``ConnectionRefusedError: [Errno 111]``
     - Neo4j is not running or wrong URI
   * - ``AuthError: Invalid credentials``
     - Check Neo4j username/password
   * - ``RateLimitError: Quota exceeded``
     - Wait or upgrade API plan
   * - ``FileNotFoundError: ffmpeg``
     - Install FFmpeg
   * - ``torch.cuda.OutOfMemoryError``
     - Reduce batch size or use CPU
   * - ``JSONDecodeError``
     - LLM returned invalid format, retry
   * - ``TimeoutError``
     - Increase timeout or check network