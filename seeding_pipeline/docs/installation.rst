Installation
============

This guide covers the installation of the Podcast Knowledge Graph Pipeline.

Requirements
------------

System Requirements
~~~~~~~~~~~~~~~~~~~

* Python 3.9 or higher
* 4GB+ RAM (8GB recommended)
* 10GB+ free disk space
* FFmpeg (for audio processing)

External Services
~~~~~~~~~~~~~~~~~

* Neo4j 5.14+ database
* Google Gemini API key (for LLM processing)
* Optional: GPU with CUDA support for faster transcription

Installation Methods
--------------------

From Source (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~

1. Clone the repository:

   .. code-block:: bash

      git clone https://github.com/yourusername/podcast-kg-pipeline.git
      cd podcast-kg-pipeline

2. Create a virtual environment:

   .. code-block:: bash

      python -m venv venv
      source venv/bin/activate  # On Windows: venv\Scripts\activate

3. Install dependencies:

   .. code-block:: bash

      pip install -r requirements.txt
      
      # For development
      pip install -r requirements-dev.txt

Using pip (Future)
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   pip install podcast-kg-pipeline

Docker Installation
~~~~~~~~~~~~~~~~~~~

1. Using Docker Compose:

   .. code-block:: bash

      docker-compose up -d

2. Using pre-built image:

   .. code-block:: bash

      docker run -d \
        -e NEO4J_URI=bolt://neo4j:7687 \
        -e GOOGLE_API_KEY=your-api-key \
        podcast-kg-pipeline

Neo4j Setup
-----------

Local Installation
~~~~~~~~~~~~~~~~~~

1. Download Neo4j from https://neo4j.com/download/
2. Install and start Neo4j
3. Set the password for the `neo4j` user
4. Install required plugins:
   
   * APOC
   * Graph Data Science (optional)

Docker Neo4j
~~~~~~~~~~~~

.. code-block:: bash

   docker run -d \
     --name neo4j \
     -p 7474:7474 -p 7687:7687 \
     -e NEO4J_AUTH=neo4j/your-password \
     -e NEO4J_PLUGINS='["apoc", "graph-data-science"]' \
     neo4j:5.14

Configuration
-------------

1. Create a `.env` file:

   .. code-block:: bash

      cp .env.example .env

2. Edit `.env` with your credentials:

   .. code-block:: bash

      NEO4J_URI=bolt://localhost:7687
      NEO4J_USER=neo4j
      NEO4J_PASSWORD=your-password
      GOOGLE_API_KEY=your-gemini-api-key

3. Optional: Create a configuration file:

   .. code-block:: bash

      cp config/config.example.yml config/config.yml

Verification
------------

Verify the installation:

.. code-block:: bash

   # Check CLI
   python cli.py --help
   
   # Run health check
   python cli.py health

   # Test with a sample podcast
   python cli.py seed --rss-url https://example.com/podcast.xml --max-episodes 1

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**FFmpeg not found**
   Install FFmpeg:
   
   .. code-block:: bash
   
      # Ubuntu/Debian
      sudo apt update && sudo apt install ffmpeg
      
      # macOS
      brew install ffmpeg
      
      # Windows
      # Download from https://ffmpeg.org/download.html

**Neo4j connection refused**
   - Ensure Neo4j is running
   - Check the URI in your `.env` file
   - Verify firewall settings

**Out of memory errors**
   - Increase available RAM
   - Reduce batch size in configuration
   - Process fewer episodes at once

**GPU not detected (for Whisper)**
   - Install CUDA toolkit
   - Install PyTorch with CUDA support:
   
   .. code-block:: bash
   
      pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

Next Steps
----------

* Read the :doc:`quickstart` guide
* Configure the system in :doc:`configuration`
* Check out :doc:`examples/index` for usage examples