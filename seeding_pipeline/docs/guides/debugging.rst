Debugging Guide
===============

This guide provides techniques and tools for debugging issues in the Podcast Knowledge Graph Pipeline.

Debugging Tools
---------------

Built-in Debug Mode
~~~~~~~~~~~~~~~~~~~

Enable debug mode for detailed logging:

.. code-block:: python

   import logging
   
   # Enable debug logging globally
   logging.basicConfig(
       level=logging.DEBUG,
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
   )
   
   # Or for specific modules
   logging.getLogger('src.processing.extraction').setLevel(logging.DEBUG)
   logging.getLogger('src.providers.llm').setLevel(logging.DEBUG)

Debug Context Manager
~~~~~~~~~~~~~~~~~~~~~

Use the debug context for detailed execution tracking:

.. code-block:: python

   from src.utils.debugging import debug_context, DebugMode
   
   # Basic usage
   with debug_context("processing_episode"):
       result = seed_podcast(podcast_config)
   
   # With options
   with DebugMode(
       save_intermediates=True,
       profile_memory=True,
       trace_calls=True
   ):
       result = process_complex_podcast()

Performance Profiling
~~~~~~~~~~~~~~~~~~~~~

Profile code execution to find bottlenecks:

.. code-block:: python

   from src.utils.debugging import profile_performance
   
   @profile_performance
   def slow_function():
       # Your code here
       pass
   
   # Or manually
   import cProfile
   import pstats
   
   profiler = cProfile.Profile()
   profiler.enable()
   
   # Code to profile
   result = seed_podcast(podcast_config)
   
   profiler.disable()
   stats = pstats.Stats(profiler)
   stats.sort_stats('cumulative')
   stats.print_stats(20)  # Top 20 functions

Memory Debugging
----------------

Track Memory Usage
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from src.utils.debugging import MemoryTracker
   
   tracker = MemoryTracker()
   tracker.start()
   
   # Your processing
   result = seed_podcast(podcast_config)
   
   report = tracker.stop()
   print(f"Peak memory: {report['peak_mb']:.1f} MB")
   print(f"Memory growth: {report['growth_mb']:.1f} MB")
   
   # Show top memory consumers
   for item in report['top_consumers']:
       print(f"{item['object']}: {item['size_mb']:.1f} MB")

Find Memory Leaks
~~~~~~~~~~~~~~~~~

.. code-block:: python

   import tracemalloc
   import gc
   
   # Start tracing
   tracemalloc.start()
   
   # Take snapshot before
   snapshot1 = tracemalloc.take_snapshot()
   
   # Run your code
   for i in range(10):
       result = seed_podcast(podcast_config, max_episodes=1)
       gc.collect()
   
   # Take snapshot after
   snapshot2 = tracemalloc.take_snapshot()
   
   # Compare snapshots
   top_stats = snapshot2.compare_to(snapshot1, 'lineno')
   
   print("[ Top 10 memory increases ]")
   for stat in top_stats[:10]:
       print(stat)

Debugging Specific Components
-----------------------------

Audio Processing Issues
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from src.providers.audio.whisper import WhisperAudioProvider
   
   # Enable debug mode
   provider = WhisperAudioProvider(debug=True)
   
   # Test transcription
   try:
       transcript = provider.transcribe("test.mp3")
       print(f"Transcript length: {len(transcript)}")
   except Exception as e:
       print(f"Error: {e}")
       
       # Check audio file
       import librosa
       audio, sr = librosa.load("test.mp3")
       print(f"Audio shape: {audio.shape}, Sample rate: {sr}")

LLM Provider Issues
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from src.providers.llm.gemini import GeminiProvider
   
   # Debug LLM calls
   class DebugLLMProvider(GeminiProvider):
       def generate(self, prompt, **kwargs):
           print(f"Prompt ({len(prompt)} chars):")
           print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
           
           response = super().generate(prompt, **kwargs)
           
           print(f"Response ({len(response)} chars):")
           print(response[:500] + "..." if len(response) > 500 else response)
           
           return response
   
   # Use debug provider
   provider = DebugLLMProvider(api_key="your-key")

Graph Database Issues
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from src.providers.graph.neo4j import Neo4jGraphProvider
   
   # Enable query logging
   provider = Neo4jGraphProvider(
       uri="bolt://localhost:7687",
       auth=("neo4j", "password"),
       debug=True
   )
   
   # Log all queries
   class QueryLogger:
       def __init__(self, session):
           self.session = session
           
       def run(self, query, **params):
           print(f"Query: {query}")
           print(f"Params: {params}")
           result = self.session.run(query, **params)
           print(f"Result summary: {result.consume().counters}")
           return result

Processing Pipeline Issues
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from src.processing.extraction import KnowledgeExtractor
   
   # Debug extraction process
   class DebugExtractor(KnowledgeExtractor):
       def extract_insights(self, text, **kwargs):
           print(f"Extracting from {len(text)} chars of text")
           
           # Save intermediate results
           with open('debug_input.txt', 'w') as f:
               f.write(text)
           
           insights = super().extract_insights(text, **kwargs)
           
           with open('debug_insights.json', 'w') as f:
               json.dump(insights, f, indent=2)
           
           print(f"Extracted {len(insights)} insights")
           return insights

Debugging Techniques
--------------------

Binary Search for Errors
~~~~~~~~~~~~~~~~~~~~~~~~

When processing fails on large inputs:

.. code-block:: python

   def find_failing_episode(episodes):
       """Find which episode causes failure using binary search."""
       if len(episodes) == 1:
           return episodes[0]
       
       mid = len(episodes) // 2
       first_half = episodes[:mid]
       second_half = episodes[mid:]
       
       try:
           process_episodes(first_half)
           # First half works, issue in second half
           return find_failing_episode(second_half)
       except:
           # Issue in first half
           return find_failing_episode(first_half)

Checkpoint Debugging
~~~~~~~~~~~~~~~~~~~~

Debug checkpoint save/load:

.. code-block:: python

   from src.seeding.checkpoint import ProgressCheckpoint
   
   checkpoint = ProgressCheckpoint("./checkpoints", debug=True)
   
   # Manually save state
   state = {
       'podcast': 'Test',
       'episode': 5,
       'segment': 10
   }
   checkpoint.save_checkpoint("test_podcast", state)
   
   # Verify saved
   loaded = checkpoint.load_checkpoint("test_podcast")
   assert loaded == state
   
   # List all checkpoints
   import os
   checkpoints = os.listdir("./checkpoints")
   print(f"Found {len(checkpoints)} checkpoint files")

Timeout Debugging
~~~~~~~~~~~~~~~~~

Handle and debug timeouts:

.. code-block:: python

   import signal
   from contextlib import contextmanager
   
   @contextmanager
   def timeout(seconds):
       def signal_handler(signum, frame):
           raise TimeoutError(f"Timed out after {seconds} seconds")
       
       signal.signal(signal.SIGALRM, signal_handler)
       signal.alarm(seconds)
       try:
           yield
       finally:
           signal.alarm(0)
   
   # Use timeout
   try:
       with timeout(30):
           result = process_large_episode()
   except TimeoutError:
       print("Processing took too long!")
       # Debug what was happening
       import traceback
       traceback.print_stack()

Interactive Debugging
---------------------

Using pdb
~~~~~~~~~

.. code-block:: python

   import pdb
   
   def problematic_function(data):
       # Set breakpoint
       pdb.set_trace()
       
       # Or conditionally
       if len(data) > 1000:
           pdb.set_trace()
       
       return process(data)

Using ipdb (Enhanced pdb)
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Install ipdb
   pip install ipdb
   
   # Run with post-mortem debugging
   python -m ipdb -c continue cli.py seed --rss-url ...

Remote Debugging
~~~~~~~~~~~~~~~~

.. code-block:: python

   # For debugging in containers/remote servers
   import debugpy
   
   debugpy.listen(5678)
   print("Waiting for debugger attach...")
   debugpy.wait_for_client()
   
   # Your code here
   result = seed_podcast(podcast_config)

Logging Best Practices
----------------------

Structured Logging
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import structlog
   
   logger = structlog.get_logger()
   
   # Log with context
   logger.info(
       "processing_episode",
       podcast="Tech Talk",
       episode=42,
       duration_seconds=1834
   )
   
   # Bind context for all subsequent logs
   log = logger.bind(request_id="abc123")
   log.info("started_processing")
   log.info("completed_processing", duration=10.5)

Log Aggregation
~~~~~~~~~~~~~~~

.. code-block:: python

   # Configure centralized logging
   import logging.handlers
   
   handler = logging.handlers.SysLogHandler(address=('localhost', 514))
   formatter = logging.Formatter(
       '%(name)s: %(levelname)s %(message)s'
   )
   handler.setFormatter(formatter)
   
   logger = logging.getLogger()
   logger.addHandler(handler)

Common Debug Scenarios
----------------------

"It works locally but not in production"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Check environment differences
   import os
   import sys
   
   print(f"Python version: {sys.version}")
   print(f"Platform: {sys.platform}")
   print(f"Environment variables:")
   for key in ['NEO4J_URI', 'GOOGLE_API_KEY', 'PYTHONPATH']:
       print(f"  {key}: {os.environ.get(key, 'NOT SET')}")
   
   # Check installed packages
   import pkg_resources
   for dist in pkg_resources.working_set:
       print(f"{dist.key}: {dist.version}")

"Random failures"
~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Add retry with detailed logging
   from src.utils.retry import with_retry
   
   @with_retry(
       max_attempts=3,
       backoff_factor=2,
       on_retry=lambda e, attempt: print(f"Retry {attempt}: {e}")
   )
   def flaky_operation():
       # Your code
       pass

"Slow processing"
~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Time each step
   import time
   from contextlib import contextmanager
   
   @contextmanager
   def timer(name):
       start = time.time()
       yield
       duration = time.time() - start
       print(f"{name} took {duration:.2f} seconds")
   
   with timer("Transcription"):
       transcript = audio_provider.transcribe(audio_file)
   
   with timer("Segmentation"):
       segments = segmenter.segment(transcript)
   
   with timer("Extraction"):
       insights = extractor.extract(segments)

Debug Output
------------

Save debug information:

.. code-block:: python

   from src.utils.debugging import DebugOutput
   
   with DebugOutput("debug_session") as debug:
       # Automatically saves all intermediate results
       result = seed_podcast(podcast_config)
   
   # Creates debug_session/
   # ├── config.json
   # ├── transcripts/
   # ├── segments/
   # ├── insights/
   # ├── errors.log
   # └── performance.json

Visualization
~~~~~~~~~~~~~

Visualize processing flow:

.. code-block:: python

   from src.utils.debugging import visualize_pipeline_flow
   
   # Generate flow diagram
   visualize_pipeline_flow(
       podcast_config,
       output_file="pipeline_flow.png"
   )
   
   # Generate timing diagram
   from src.utils.debugging import plot_timing_diagram
   
   plot_timing_diagram(
       debug_output_dir="debug_session",
       output_file="timing.png"
   )