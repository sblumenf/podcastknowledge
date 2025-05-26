Quick Start Guide
=================

This guide will help you get started with the Podcast Knowledge Graph Pipeline in minutes.

Prerequisites
-------------

Before starting, ensure you have:

1. Python 3.9+ installed
2. Neo4j database running
3. Google Gemini API key
4. Completed the :doc:`installation` steps

Basic Usage
-----------

Processing Your First Podcast
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The simplest way to process a podcast is using the Python API:

.. code-block:: python

   from src.api.v1 import seed_podcast

   # Process a single podcast
   result = seed_podcast({
       'name': 'The Daily',
       'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
       'category': 'News'
   }, max_episodes=3)

   print(f"Successfully processed {result['episodes_processed']} episodes!")

Using the CLI
~~~~~~~~~~~~~

You can also use the command-line interface:

.. code-block:: bash

   # Process a single podcast
   python cli.py seed \
     --rss-url https://feeds.simplecast.com/54nAGcIl \
     --max-episodes 3

   # Process multiple podcasts from a config file
   python cli.py seed \
     --podcast-config podcasts.json \
     --max-episodes 5

Processing Multiple Podcasts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To process multiple podcasts in batch:

.. code-block:: python

   from src.api.v1 import seed_podcasts

   podcasts = [
       {
           'name': 'Tech Podcast',
           'rss_url': 'https://example.com/tech/feed.xml',
           'category': 'Technology'
       },
       {
           'name': 'Science Weekly',
           'rss_url': 'https://example.com/science/feed.xml',
           'category': 'Science'
       }
   ]

   result = seed_podcasts(podcasts, max_episodes_each=5)
   print(f"Processed {result['podcasts_processed']} podcasts")

Configuration Options
---------------------

Basic Configuration
~~~~~~~~~~~~~~~~~~~

Create a custom configuration:

.. code-block:: python

   from src.core.config import Config
   from src.api.v1 import seed_podcast

   # Create custom config
   config = Config()
   config.batch_size = 10
   config.max_workers = 4
   config.checkpoint_enabled = True

   # Use with API
   result = seed_podcast(
       {'name': 'My Podcast', 'rss_url': 'https://...'},
       config=config
   )

Configuration File
~~~~~~~~~~~~~~~~~~

For persistent configuration, create `config/my_config.yml`:

.. code-block:: yaml

   # Processing settings
   batch_size: 10
   max_workers: 4
   
   # Model settings
   model_name: "gemini-1.5-pro"
   temperature: 0.7
   
   # Neo4j settings
   neo4j_uri: "bolt://localhost:7687"
   
   # Features
   checkpoint_enabled: true
   checkpoint_dir: "./checkpoints"

Then use it:

.. code-block:: python

   config = Config.from_file('config/my_config.yml')

Viewing Results
---------------

Querying the Knowledge Graph
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

After processing, query your Neo4j database:

.. code-block:: cypher

   // Find all podcasts
   MATCH (p:Podcast)
   RETURN p.name, p.category, p.episode_count

   // Find insights from a specific podcast
   MATCH (p:Podcast {name: 'The Daily'})-[:HAS_EPISODE]->()
         -[:HAS_SEGMENT]->()-[:HAS_INSIGHT]->(i:Insight)
   RETURN i.text, i.confidence
   ORDER BY i.confidence DESC
   LIMIT 10

   // Find entities mentioned across podcasts
   MATCH (e:Entity)<-[:MENTIONS_ENTITY]-()
   RETURN e.name, count(*) as mentions
   ORDER BY mentions DESC
   LIMIT 20

Using Neo4j Browser
~~~~~~~~~~~~~~~~~~~

1. Open http://localhost:7474 in your browser
2. Login with your Neo4j credentials
3. Run queries to explore the knowledge graph
4. Visualize relationships between podcasts, episodes, and insights

Error Handling
--------------

The pipeline handles errors gracefully:

.. code-block:: python

   result = seed_podcast({
       'name': 'My Podcast',
       'rss_url': 'https://invalid-url.com/feed.xml'
   })

   if result['episodes_failed'] > 0:
       print(f"Warning: {result['episodes_failed']} episodes failed")
   
   # Processing continues even with some failures
   print(f"Still processed {result['episodes_processed']} episodes")

Checkpoint Recovery
-------------------

If processing is interrupted, it automatically resumes:

.. code-block:: python

   # First run - interrupted after 5 episodes
   result1 = seed_podcast(podcast_config, max_episodes=10)

   # Second run - automatically resumes from episode 6
   result2 = seed_podcast(podcast_config, max_episodes=10)

Performance Tips
----------------

1. **Use Batch Processing**: Process multiple episodes together
2. **Enable Checkpoints**: Allows resuming after interruptions
3. **Adjust Worker Count**: Based on your CPU cores
4. **Monitor Memory**: Use smaller batches for limited RAM

.. code-block:: python

   # Optimized configuration
   config = Config()
   config.batch_size = 20
   config.max_workers = 8
   config.checkpoint_enabled = True
   config.use_gpu = True  # If available

Common Patterns
---------------

Processing New Episodes Only
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # The system automatically skips already-processed episodes
   # Just run with the same podcast config
   result = seed_podcast(podcast_config, max_episodes=100)

Filtering Episodes
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Process only recent episodes
   from datetime import datetime, timedelta

   podcast_config = {
       'name': 'Tech News',
       'rss_url': 'https://...',
       'start_date': (datetime.now() - timedelta(days=30)).isoformat()
   }

Next Steps
----------

* Explore :doc:`guides/advanced_features` for more capabilities
* Read about :doc:`guides/plugin_development` to extend the system
* Check :doc:`api/v1` for complete API reference
* See :doc:`examples/index` for more code examples