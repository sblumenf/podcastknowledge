# Script Instruction Manual

This comprehensive manual documents all scripts in the Podcast Knowledge project, providing detailed information about their purpose, functionality, and usage.

## Table of Contents

1. [Root Directory Scripts](#root-directory-scripts)
   - [run_pipeline.sh](#run_pipelinesh)
   - [add_podcast.sh](#add_podcastsh)
   - [list_podcasts.sh](#list_podcastssh)
   - [run_clustering.sh](#run_clusteringsh)
   - [update_youtube_url.sh](#update_youtube_urlsh)

2. [Seeding Pipeline Scripts](#seeding-pipeline-scripts)
   - [Setup Scripts](#setup-scripts)
   - [Database Scripts](#database-scripts)
   - [Analysis Scripts](#analysis-scripts)
   - [Testing Scripts](#testing-scripts)
   - [Monitoring Scripts](#monitoring-scripts)
   - [Maintenance Scripts](#maintenance-scripts)
   - [Validation Scripts](#validation-scripts)

3. [Transcriber Scripts](#transcriber-scripts)
   - [Setup Scripts](#transcriber-setup-scripts)
   - [Maintenance Scripts](#transcriber-maintenance-scripts)
   - [Utility Scripts](#transcriber-utility-scripts)

4. [UI Scripts](#ui-scripts)
   - [Setup Scripts](#ui-setup-scripts)

5. [Shared Scripts](#shared-scripts)

---

## Root Directory Scripts

### run_pipeline.sh

**Purpose:**
The run_pipeline.sh script serves as the main orchestrator for the entire podcast knowledge pipeline system. It coordinates the execution of both the transcriber module (which downloads and transcribes podcast episodes) and the seeding pipeline module (which extracts knowledge and populates the Neo4j database). This script provides flexible execution modes, allowing users to run either module independently or both in sequence. It handles environment setup, parameter validation, and provides comprehensive error handling and progress reporting throughout the pipeline execution.

**Process:**
When executed, the script first validates all provided parameters and checks system prerequisites such as Python availability and Neo4j connectivity. It then determines the execution mode based on user input and configures the appropriate environment variables for cross-module communication. If running the transcriber, it activates the transcriber's virtual environment, sets up output directories, and invokes the transcriber CLI with the specified RSS feed URL and episode limits. For the seeding pipeline, it switches to the seeding environment, locates VTT files produced by the transcriber, and processes them through the knowledge extraction pipeline. The script maintains proper error propagation between modules and provides detailed logging when verbose mode is enabled. Throughout execution, it manages virtual environments properly and ensures clean state transitions between modules.

**Usage:**
```bash
# Run from project root directory
./run_pipeline.sh [OPTIONS]

# Parameters:
-t, --transcriber     # Run transcriber module only
-s, --seeding         # Run seeding pipeline only  
-b, --both            # Run both modules (default)
-p, --podcast NAME    # Podcast name (uses RSS URL from config)
-f, --feed-url URL    # RSS feed URL (overrides config)
-e, --max-episodes N  # Maximum episodes to process (default: 1)
-d, --data-dir DIR    # Set data directory (default: /home/sergeblumenfeld/podcastknowledge/data)
-v, --verbose         # Enable verbose output
-h, --help            # Show help message

# Examples:
./run_pipeline.sh --both --podcast "The Mel Robbins Podcast" --max-episodes 3 --verbose
./run_pipeline.sh --transcriber --feed-url "https://feeds.example.com/podcast.rss" --max-episodes 5
./run_pipeline.sh --seeding --podcast "Tech Talk"  # Process existing VTT files only
./run_pipeline.sh -v -b -p "The Mel Robbins Podcast" -e 2  # Short form with verbose
```

### add_podcast.sh

**Purpose:**
The add_podcast.sh script automates the complete setup process for adding a new podcast to the knowledge system. It performs all necessary configuration steps including creating a dedicated Neo4j Docker container for the podcast, setting up the database schema, creating required directory structures for transcripts and processed data, and updating the system configuration files. This script ensures each podcast has isolated resources and proper configuration, preventing conflicts between different podcasts in the system. It validates that podcasts aren't duplicated and automatically assigns appropriate ports and identifiers for new podcasts.

**Process:**
The script begins by validating the provided podcast name and RSS feed URL, then generates a unique podcast ID by normalizing the name. It checks the existing configuration to ensure the podcast doesn't already exist, preventing accidental duplicates. Next, it scans for available Neo4j ports starting from 7687, finding the next unused port for the new podcast's database. It then creates a new Neo4j Docker container with the assigned port, configures authentication, and waits for the database to become healthy. Once Neo4j is running, the script creates a dedicated database for the podcast (or uses the default in Community Edition). It updates the podcasts.yaml configuration file with all necessary settings including database connection details, processing parameters, and clustering configurations. Finally, it creates the required directory structure under the data folder for storing transcripts and processed data with appropriate permissions.

**Usage:**
```bash
# Run from project root directory
./add_podcast.sh --name "Podcast Name" --feed "RSS Feed URL"

# Parameters:
-n, --name NAME    # Name of the podcast (required)
-f, --feed URL     # RSS feed URL for the podcast (required)
-h, --help         # Show help message

# Example:
./add_podcast.sh --name "Tech Talk Show" --feed "https://feeds.example.com/techtalk"
./add_podcast.sh -n "The Daily Brief" -f "https://example.com/daily-brief.rss"

# After successful addition, the script provides:
# - Podcast ID (normalized name)
# - Neo4j port assignment
# - Container name
# - Commands to process episodes
# - Neo4j browser URL
```

### list_podcasts.sh

**Purpose:**
The list_podcasts.sh script provides a comprehensive overview of all podcasts configured in the knowledge system. It reads the podcast configuration file and displays detailed information about each podcast including their operational status, database configuration, and processing settings. This script is essential for system administrators and users to quickly understand which podcasts are available, their current configuration, and how to connect to their respective databases. It also helps in troubleshooting by showing enabled/disabled status and connection details for each podcast.

**Process:**
The script reads the podcasts.yaml configuration file and parses it to extract information about all configured podcasts. For each podcast found, it displays the podcast name, ID, enabled status, RSS feed URL, and Neo4j database connection details including the port number and database name. The script formats this information in a clear, tabular layout that's easy to read and understand. If no podcasts are configured, it displays an appropriate message. The script handles YAML parsing errors gracefully and provides clear error messages if the configuration file is missing or malformed. It also shows the total count of configured podcasts at the end of the listing.

**Usage:**
```bash
# Run from project root directory
./list_podcasts.sh

# No parameters required
# The script will display:
# - Podcast name and ID
# - Enabled/disabled status
# - RSS feed URL
# - Neo4j connection details
# - Database name
# - Total podcast count

# Example output:
# === Configured Podcasts ===
# 
# 1. The Mel Robbins Podcast
#    ID: the_mel_robbins_podcast
#    Enabled: true
#    RSS Feed: https://feeds.example.com/melrobbins
#    Neo4j URI: neo4j://localhost:7687
#    Database: the_mel_robbins_podcast
```

### run_clustering.sh

**Purpose:**
The run_clustering.sh script executes the semantic clustering process on existing knowledge units in the Neo4j database. This clustering process groups semantically similar meaningful units together, creating a higher-level organization of knowledge that helps in discovering themes, topics, and patterns across podcast episodes. The script runs the clustering algorithm which uses vector embeddings to calculate similarities between units and forms clusters based on configurable similarity thresholds. This is particularly useful for identifying recurring themes across episodes and creating topic-based navigation through the knowledge graph.

**Process:**
The script navigates to the seeding pipeline directory and activates the appropriate Python virtual environment if available. It then executes the clustering module which connects to the Neo4j database and retrieves all meaningful units with their embeddings. The clustering algorithm calculates pairwise similarities between unit embeddings using cosine similarity, then applies hierarchical clustering to group similar units together. Clusters are formed based on the configured minimum cluster size and similarity threshold parameters defined in the podcast configuration. The script creates cluster nodes in the database and establishes relationships between meaningful units and their assigned clusters. Progress is reported throughout the process, showing the number of units processed and clusters created. Upon completion, it provides statistics about the clustering results including the number of clusters formed and the distribution of units across clusters.

**Usage:**
```bash
# Run from project root directory
./run_clustering.sh [podcast_name]

# Parameters:
# podcast_name (optional) - Name of specific podcast to cluster
#                          If omitted, clusters all podcasts

# Examples:
./run_clustering.sh                           # Cluster all podcasts
./run_clustering.sh "The Mel Robbins Podcast" # Cluster specific podcast

# The script will:
# - Connect to the appropriate Neo4j database
# - Retrieve meaningful units with embeddings
# - Calculate similarities and form clusters
# - Create cluster nodes and relationships
# - Display clustering statistics
```

### update_youtube_url.sh

**Purpose:**
The update_youtube_url.sh script provides functionality to update or correct YouTube URLs for podcast episodes in the database. This is useful when YouTube URLs change, when initial URL detection failed, or when manually correcting mismatched URLs. The script allows updating URLs for individual episodes or batch updating multiple episodes, ensuring that the podcast player and transcript alignment features continue to work correctly. It maintains data integrity by validating URLs before updating and preserving all other episode metadata.

**Process:**
The script connects to the specified podcast's Neo4j database and locates the episode by ID or title. It validates the provided YouTube URL format to ensure it's a valid YouTube video URL. Before updating, it displays the current episode information including the existing URL (if any) and asks for confirmation. Upon confirmation, it updates the episode node with the new YouTube URL while preserving all other properties. The script can operate in batch mode, reading episode-URL pairs from a file for bulk updates. It maintains a log of all updates performed and can optionally create a backup of original URLs. After updating, it verifies the change was successful and reports the results.

**Usage:**
```bash
# Run from project root directory
./update_youtube_url.sh --podcast "Podcast Name" --episode "Episode ID" --url "YouTube URL"

# Parameters:
--podcast NAME     # Name of the podcast (required)
--episode ID       # Episode ID or title (required)
--url URL          # New YouTube URL (required)
--batch FILE       # Batch update from file
--backup           # Create backup of original URLs
--force            # Skip confirmation prompts

# Examples:
./update_youtube_url.sh --podcast "Tech Talk" --episode "tech_talk_ep_001" --url "https://youtube.com/watch?v=abc123"
./update_youtube_url.sh --podcast "The Daily Brief" --episode "AI Revolution" --url "https://youtu.be/xyz789"
./update_youtube_url.sh --podcast "Tech Talk" --batch urls.txt --backup

# Batch file format (urls.txt):
# episode_id_1,https://youtube.com/watch?v=video1
# episode_id_2,https://youtube.com/watch?v=video2
```

### analyze_podcast_nodes.sh

**Purpose:**
The analyze_podcast_nodes.sh script provides a convenient wrapper for analyzing Neo4j node types across any configured podcast database. It serves as a root-level entry point that forwards commands to the underlying Python analysis script while providing consistent command-line interface conventions. The script helps developers and data scientists quickly explore the structure of podcast knowledge graphs, understand node types and their properties, and identify patterns in the data model. It's particularly useful for database schema documentation, debugging data issues, and planning new features that require understanding existing graph structures.

**Process:**
The script validates command-line arguments and ensures the required podcast parameter is provided. It then changes to the seeding_pipeline directory where the Python analysis script resides and forwards all arguments to it. The underlying Python script connects to the specified podcast's Neo4j database, discovers all node types, analyzes their properties and relationships, and generates either a detailed JSON report or a human-readable summary. The wrapper script maintains consistent error handling and provides helpful usage information when called incorrectly.

**Usage:**
```bash
# Run from project root directory
./analyze_podcast_nodes.sh --podcast PODCAST_NAME [OPTIONS]

# Parameters:
-p, --podcast NAME    # Name or ID of the podcast to analyze (required)
-o, --output FILE     # Output file path (default: neo4j_node_analysis_<podcast>.json)
-f, --format FORMAT   # Output format: json or summary (default: json)
-v, --verbose         # Verbose output during analysis
-h, --help            # Show help message

# Examples:
./analyze_podcast_nodes.sh --podcast "The Mel Robbins Podcast"
./analyze_podcast_nodes.sh -p mel_robbins_podcast -v
./analyze_podcast_nodes.sh --podcast "My First Million" --format summary
./analyze_podcast_nodes.sh -p "Tech Talk" -o tech_talk_analysis.json -v

# The script provides:
# - Complete inventory of node types
# - Property analysis per node type
# - Categorical value extraction
# - Relationship mapping
# - Sample data examination
# - Summary statistics
```

---

## Seeding Pipeline Scripts

### Setup Scripts

#### seeding_pipeline/scripts/setup/install.sh

**Purpose:**
The install.sh script manages the installation of all dependencies required for the seeding pipeline module. It ensures that the Python virtual environment is properly configured, all required Python packages are installed at their correct versions, and system dependencies are verified. The script performs compatibility checks between package versions and provides clear error messages if installation issues occur. It also handles platform-specific installation requirements and can recover from partial installation failures by cleaning up and retrying the installation process.

**Process:**
The script first checks if a virtual environment exists and creates one if necessary using Python 3.8 or higher. It activates the virtual environment and upgrades pip to the latest version to ensure compatibility with modern package formats. Next, it installs all Python dependencies from the requirements.txt file, monitoring for any installation errors or version conflicts. The script verifies that critical packages like neo4j, numpy, and sentence-transformers are correctly installed and accessible. It also checks for system-level dependencies such as build tools required for compiling certain Python packages. If any installation fails, it provides detailed error information and suggestions for resolution. Finally, it runs a verification step to ensure all imports work correctly and displays a summary of installed packages.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
./scripts/setup/install.sh [OPTIONS]

# Parameters:
--clean            # Clean install (remove existing venv)
--upgrade          # Upgrade all packages to latest compatible versions
--dev              # Install development dependencies
--no-cache         # Don't use pip cache
-h, --help         # Show help message

# Examples:
./scripts/setup/install.sh                    # Standard installation
./scripts/setup/install.sh --clean           # Fresh installation
./scripts/setup/install.sh --dev             # Include dev dependencies
./scripts/setup/install.sh --upgrade --no-cache  # Upgrade without cache
```

#### seeding_pipeline/scripts/setup/setup_venv.sh

**Purpose:**
The setup_venv.sh script creates and configures a Python virtual environment specifically for the seeding pipeline module. It ensures isolation from system Python packages and other project environments, preventing version conflicts and maintaining reproducible deployments. The script configures the virtual environment with optimal settings for the seeding pipeline's requirements, including proper paths for model caching and data directories. It also sets up environment activation scripts with necessary environment variables and path configurations.

**Process:**
The script begins by checking the system Python version to ensure it meets the minimum requirement of Python 3.8. It creates a new virtual environment in the seeding_pipeline/venv directory using the venv module. The script then generates custom activation scripts that set required environment variables such as PYTHONPATH, model cache directories, and data paths. It configures the virtual environment to use the correct Python interpreter and ensures pip is updated to a compatible version. The script also creates convenience aliases for common operations and sets up proper permissions for the virtual environment directories. It handles platform-specific differences between Linux, macOS, and Windows environments.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
./scripts/setup/setup_venv.sh [OPTIONS]

# Parameters:
--python PATH      # Path to specific Python interpreter
--name NAME        # Custom venv directory name (default: venv)
--global-packages  # Allow access to system site-packages
-h, --help         # Show help message

# Examples:
./scripts/setup/setup_venv.sh                           # Create standard venv
./scripts/setup/setup_venv.sh --python /usr/bin/python3.9  # Use specific Python
./scripts/setup/setup_venv.sh --name venv-test        # Custom venv name
./scripts/setup/setup_venv.sh --global-packages       # Include system packages

# After creation:
source venv/bin/activate  # Activate the environment
```

### Database Scripts

#### seeding_pipeline/scripts/database/clear_database.py

**Purpose:**
The clear_database.py script provides a controlled method to completely remove all data from a Neo4j database. This includes all nodes, relationships, and their properties, effectively resetting the database to an empty state. The script is useful for testing scenarios, clearing corrupted data, or preparing for a fresh import of podcast data. It includes safety confirmations and provides detailed feedback about what will be deleted, preventing accidental data loss in production environments.

**Process:**
The script establishes a connection to the Neo4j database using credentials from the pipeline configuration. It first queries the database to count all existing nodes and relationships, displaying these counts to the user for confirmation. Before proceeding with deletion, it shows exactly what will be removed and requires explicit confirmation in non-force mode. The deletion process follows Neo4j best practices by first removing all relationships (which cannot exist without nodes) and then removing all nodes. This two-step process prevents constraint violations and ensures clean deletion. Throughout the process, the script provides progress updates and handles any errors gracefully. After deletion, it verifies that the database is empty and reports the final state.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/database/clear_database.py [OPTIONS]

# Parameters:
--podcast NAME     # Specific podcast database to clear
--force           # Skip confirmation prompt
--dry-run         # Show what would be deleted without deleting
-v, --verbose     # Verbose output

# Examples:
python scripts/database/clear_database.py                    # Clear default database
python scripts/database/clear_database.py --podcast "Tech Talk"  # Clear specific podcast
python scripts/database/clear_database.py --dry-run         # Preview deletion
python scripts/database/clear_database.py --force --verbose # Force clear with details

# Safety features:
# - Shows count of nodes/relationships before deletion
# - Requires confirmation unless --force is used
# - Provides detailed logging of deletion process
```

#### seeding_pipeline/scripts/database/comprehensive_database_check.py

**Purpose:**
The comprehensive_database_check.py script performs an extensive analysis of the Neo4j database contents, validating data integrity, checking relationships, and generating detailed statistics about the knowledge graph. It serves as a diagnostic tool for understanding the current state of the database, identifying potential issues, and verifying that the knowledge extraction pipeline has processed data correctly. The script examines all node types, relationship patterns, and data consistency rules, providing a complete health assessment of the podcast knowledge graph.

**Process:**
The script connects to the Neo4j database and systematically examines each component of the knowledge graph. It starts by counting all node types (Episodes, Segments, MeaningfulUnits, Entities, Speakers, Clusters) and their relationships. For each node type, it validates required properties, checks for missing data, and identifies any orphaned nodes. The script analyzes relationship patterns to ensure bidirectional connections are properly maintained and that hierarchical relationships follow expected patterns. It generates statistical summaries including average metrics like segments per episode, meaningful units per segment, and entities per episode. The script also performs specific validation checks such as ensuring all episodes have transcripts, all meaningful units have embeddings, and all timestamps are properly formatted. Any anomalies or potential issues are flagged with detailed descriptions and suggestions for resolution.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/database/comprehensive_database_check.py [OPTIONS]

# Parameters:
--podcast NAME         # Check specific podcast database
--output FILE         # Save report to file
--format FORMAT       # Output format: text, json, html (default: text)
--check-embeddings    # Include embedding validation
--check-content       # Validate content fields
--fix-issues          # Attempt to fix found issues
-v, --verbose         # Detailed output

# Examples:
python scripts/database/comprehensive_database_check.py              # Basic check
python scripts/database/comprehensive_database_check.py --podcast "Tech Talk" --verbose
python scripts/database/comprehensive_database_check.py --output report.json --format json
python scripts/database/comprehensive_database_check.py --check-embeddings --check-content
python scripts/database/comprehensive_database_check.py --fix-issues  # Auto-fix problems

# Report includes:
# - Node counts by type
# - Relationship counts by type
# - Data integrity issues
# - Missing required properties
# - Orphaned nodes
# - Statistical summaries
```

#### seeding_pipeline/scripts/database/delete_single_episode.py

**Purpose:**
The delete_single_episode.py script safely removes a specific podcast episode and all its associated data from the Neo4j database. This includes the episode node itself, all related segments, meaningful units, speaker mappings, and any relationships connecting these elements. The script is designed for surgical removal of problematic episodes, test data, or incorrectly processed content while maintaining database integrity. It ensures that no orphaned nodes or dangling relationships remain after deletion.

**Process:**
The script begins by connecting to the appropriate podcast database and locating the episode using the provided identifier (ID or title). It then performs a comprehensive query to identify all nodes and relationships that would be affected by the deletion, including segments, meaningful units, entities, quotes, and cluster associations. Before deletion, it displays a detailed summary of what will be removed, including counts of each node type and relationship type. If not in force mode, it requires explicit confirmation from the user. The deletion process follows a specific order to maintain referential integrity: first removing relationships, then child nodes (meaningful units, entities), then parent nodes (segments), and finally the episode node itself. The script logs each deletion step and can optionally create a backup of the deleted data in JSON format for recovery purposes.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/database/delete_single_episode.py --episode "EPISODE_ID" [OPTIONS]

# Parameters:
--episode ID          # Episode ID or title to delete (required)
--podcast NAME        # Podcast name (required if multiple podcasts)
--force              # Skip confirmation prompt
--backup FILE        # Backup deleted data to file
--dry-run            # Show what would be deleted without deleting
-v, --verbose        # Show detailed deletion progress

# Examples:
python scripts/database/delete_single_episode.py --episode "tech_talk_ep_001" --podcast "Tech Talk"
python scripts/database/delete_single_episode.py --episode "AI and Future" --force
python scripts/database/delete_single_episode.py --episode "test_episode" --backup deleted_ep.json
python scripts/database/delete_single_episode.py --episode "broken_ep_123" --dry-run --verbose

# Deletes:
# - Episode node
# - All segments of the episode
# - All meaningful units
# - All entity relationships
# - All speaker occurrences
# - All cluster associations
```

### Analysis Scripts

#### seeding_pipeline/scripts/analysis/analyze_episode_units.py

**Purpose:**
The analyze_episode_units.py script provides detailed analysis of meaningful unit distribution across episodes in the podcast database. It helps identify patterns in knowledge extraction, find episodes that may need reprocessing, and understand the overall quality of the extraction pipeline. The script generates statistics about unit counts, types, and distribution patterns, making it valuable for quality assurance and pipeline optimization. It can identify outlier episodes with unusually high or low unit counts, which often indicates processing issues or particularly content-rich episodes.

**Process:**
The script queries the Neo4j database to retrieve all episodes and their associated meaningful units, including unit types and metadata. It calculates comprehensive statistics including average units per episode, standard deviation, and percentile distributions. For each episode, it analyzes the breakdown of unit types (entities, quotes, topics, insights, arguments) and identifies patterns in the distribution. The script groups episodes by unit count ranges and highlights outliers that fall beyond expected thresholds. It examines temporal patterns to see if unit extraction quality has changed over time. For episodes with unusual unit counts, it provides detailed breakdowns including segment counts and extraction metadata. The analysis results are presented in both summary and detailed formats, with optional CSV export for further analysis.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/analysis/analyze_episode_units.py [OPTIONS]

# Parameters:
--podcast NAME        # Analyze specific podcast
--min-units N        # Show episodes with at least N units
--max-units N        # Show episodes with at most N units
--unit-type TYPE     # Focus on specific unit type
--output FILE        # Export results to CSV
--detailed           # Show detailed unit breakdowns
-v, --verbose        # Verbose output

# Examples:
python scripts/analysis/analyze_episode_units.py                    # Basic analysis
python scripts/analysis/analyze_episode_units.py --podcast "Tech Talk" --detailed
python scripts/analysis/analyze_episode_units.py --min-units 0 --max-units 10  # Find low-extraction episodes
python scripts/analysis/analyze_episode_units.py --unit-type entity --output entities.csv
python scripts/analysis/analyze_episode_units.py --verbose          # Full statistical analysis

# Analysis includes:
# - Unit count distribution
# - Episodes with zero or few units
# - Statistical measures (mean, median, std dev)
# - Unit type breakdowns
# - Temporal patterns
# - Outlier identification
```

#### seeding_pipeline/scripts/analysis/analyze_neo4j_nodes.py

**Purpose:**
The analyze_neo4j_nodes.py script performs comprehensive analysis of Neo4j node types and their properties for any configured podcast database. It discovers all node labels in the graph, analyzes their properties, extracts categorical values, and maps relationship patterns between different node types. The script is essential for understanding the knowledge graph structure, validating data integrity, and documenting the database schema. It helps developers and data scientists explore the graph model, identify data patterns, and discover opportunities for new queries or visualizations. The script can analyze any podcast database configured in the system, making it a versatile tool for multi-podcast deployments.

**Process:**
The script begins by loading the podcast configuration from the podcasts.yaml file to determine the correct database connection parameters for the specified podcast. It establishes a connection to the appropriate Neo4j database instance using the podcast-specific URI and credentials. The script then discovers all node labels present in the database using the db.labels() procedure. For each node type, it performs a comprehensive analysis including counting total nodes, identifying all properties used across nodes of that type, and retrieving sample nodes to understand typical data patterns. The script analyzes each property to determine if it contains categorical data by counting distinct values - properties with 20 or fewer distinct values are classified as categorical and all values are extracted with their frequencies. It maps all relationships connected to each node type, both incoming and outgoing, including the labels of connected nodes. The analysis results can be output in JSON format for programmatic use or as a summary for human reading. The script handles large databases efficiently by using sampling techniques and limiting expensive queries.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/analysis/analyze_neo4j_nodes.py --podcast "PODCAST_NAME" [OPTIONS]

# Parameters:
--podcast NAME, -p NAME    # Podcast name or ID (required)
--output FILE, -o FILE     # Output file path (default: neo4j_node_analysis_<podcast>.json)
--verbose, -v              # Verbose output during analysis
--format FORMAT            # Output format: json or summary (default: json)

# Examples:
python scripts/analysis/analyze_neo4j_nodes.py --podcast "The Mel Robbins Podcast"
python scripts/analysis/analyze_neo4j_nodes.py -p mel_robbins_podcast -v
python scripts/analysis/analyze_neo4j_nodes.py --podcast "My First Million" --output mfm_analysis.json
python scripts/analysis/analyze_neo4j_nodes.py --podcast "Tech Talk" --format summary
python scripts/analysis/analyze_neo4j_nodes.py -p "Interview Show" -o analysis.json -v

# Output includes:
# - Complete list of node types
# - Node counts for each type
# - Property schemas per node type
# - Sample data from each node type
# - Categorical property values
# - Relationship mappings
# - Summary statistics
```

#### seeding_pipeline/scripts/analysis/cluster_existing.py

**Purpose:**
The cluster_existing.py script allows manual triggering of the semantic clustering process for existing meaningful units in a podcast's Neo4j database. It provides a way to run or re-run clustering on already processed episodes without needing to reprocess the entire pipeline. The script uses the same HDBSCAN clustering algorithm as the main pipeline but can be executed independently. This is particularly useful after adjusting clustering parameters, when new episodes have been added, or when initial clustering needs to be refined. The script includes validation checks to ensure sufficient data exists for meaningful clustering results.

**Process:**
The script loads the podcast-specific configuration including database connection details and clustering parameters from the podcasts.yaml file. It connects to the specified podcast's Neo4j database and validates that sufficient meaningful units with embeddings exist for clustering. The script then initializes the SemanticClusteringSystem with the appropriate language model service for generating cluster labels. During execution, it retrieves all meaningful units with their 768-dimensional embeddings from the database and runs HDBSCAN clustering with the configured parameters (minimum cluster size, epsilon distance threshold). The clustering process groups semantically similar units together, calculates cluster centroids, and generates human-readable labels for each cluster using the language model. Results are written back to Neo4j, creating Cluster nodes with labels and relationships linking meaningful units to their assigned clusters. The script provides detailed statistics about clustering results including number of clusters created, outlier ratio, and cluster size distribution.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/analysis/cluster_existing.py --podcast "PODCAST_NAME" [OPTIONS]

# Parameters:
--podcast NAME, -p NAME    # Podcast name (required, must match name in podcasts.yaml)
--verbose, -v              # Enable verbose output
--force, -f                # Force clustering even with insufficient data

# Examples:
python scripts/analysis/cluster_existing.py --podcast "The Mel Robbins Podcast"
python scripts/analysis/cluster_existing.py -p "Tech Talk" --verbose
python scripts/analysis/cluster_existing.py --podcast "My First Million" --force
python scripts/analysis/cluster_existing.py -p "Interview Show" -v

# Output includes:
# - Validation results (units found, existing clusters)
# - Clustering progress updates
# - Results summary:
#   - Clusters created
#   - Units clustered
#   - Outliers identified
#   - Execution time
#   - Cluster details (if verbose)
```

#### seeding_pipeline/scripts/analysis/detect_semantic_gaps.py

**Purpose:**
The detect_semantic_gaps.py script analyzes existing clusters in a podcast's knowledge graph to identify semantic gaps - pairs of clusters that are moderately distant and could benefit from exploration of connecting concepts. Based on the InfraNodus gap detection concept but using semantic embeddings, this script helps discover unexplored connections between topics, identify knowledge silos, and suggest areas for future content exploration. It's particularly valuable for content creators looking to find novel connections between existing topics or researchers identifying underexplored areas in their podcast domain.

**Process:**
The script begins by loading the podcast configuration and connecting to the appropriate Neo4j database instance. It validates that sufficient clusters with centroid embeddings exist for meaningful gap analysis (requiring at least 2 clusters). The gap detection algorithm retrieves all active clusters with their 768-dimensional centroid embeddings and calculates pairwise cosine similarities between all cluster pairs. It identifies gaps by finding cluster pairs with moderate semantic distance (default 0.3-0.7 range) - not too similar (would be redundant) and not too different (would be unrelated). For each identified gap, the script calculates a gap score based on how close the distance is to the optimal range center. It then searches for potential bridge concepts by finding meaningful units or entities that appear in episodes containing both clusters. The script creates SEMANTIC_GAP relationships in Neo4j between cluster pairs that meet the gap criteria, storing similarity scores, gap scores, and potential bridge concepts. Results are presented in a ranked list showing the most promising gaps for exploration.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/analysis/detect_semantic_gaps.py --podcast "PODCAST_NAME" [OPTIONS]

# Parameters:
--podcast NAME, -p NAME    # Podcast name (required, must match name in podcasts.yaml)
--verbose, -v              # Enable verbose output

# Examples:
python scripts/analysis/detect_semantic_gaps.py --podcast "The Mel Robbins Podcast"
python scripts/analysis/detect_semantic_gaps.py -p "Tech Talk" --verbose
python scripts/analysis/detect_semantic_gaps.py --podcast "My First Million"
python scripts/analysis/detect_semantic_gaps.py -p "Interview Show" -v

# Output includes:
# - Validation results (clusters found with centroids)
# - Gap detection progress
# - Results summary:
#   - Clusters analyzed
#   - Semantic gaps found
#   - Gap relationships created
#   - Execution time
# - Top semantic gaps:
#   - Cluster pairs
#   - Similarity scores
#   - Gap scores
#   - Bridge concepts (if found)

# Neo4j Queries to explore results:
# Find all gaps:
MATCH (c1:Cluster)-[gap:SEMANTIC_GAP]->(c2:Cluster)
RETURN c1.label, c2.label, gap.similarity, gap.gap_score
ORDER BY gap.gap_score DESC

# Find gaps for specific cluster:
MATCH (c:Cluster {label: "AI Technology"})-[gap:SEMANTIC_GAP]-(other:Cluster)
RETURN other.label, gap.similarity, gap.potential_bridges
```

#### seeding_pipeline/scripts/analysis/speaker_summary_report.py

**Purpose:**
The speaker_summary_report.py script generates comprehensive analytics about speaker participation across podcast episodes. It analyzes speaker identification accuracy, speaking time distribution, and conversation patterns to provide insights into podcast dynamics. The script helps podcast creators understand conversation balance, identify dominant speakers, and track guest appearances across episodes. It's particularly useful for interview-style podcasts where understanding speaker dynamics and ensuring balanced conversations is important.

**Process:**
The script queries the database for all speaker nodes and their relationships to segments and episodes. It calculates speaking time for each speaker by aggregating segment durations, handling overlapping segments appropriately. For each episode, it determines speaker talk-time percentages, conversation turn-taking patterns, and interruption frequencies. The script identifies speaker roles (host, guest, interviewer) based on appearance patterns and speaking characteristics. It generates summary statistics including total speaking time per speaker, average turn length, and participation rates across episodes. The analysis includes speaker network graphs showing which speakers appear together frequently. For podcasts with consistent hosts, it tracks how host speaking time varies with different guests. The script can also identify episodes where speaker detection may have failed based on unusual patterns.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/analysis/speaker_summary_report.py [OPTIONS]

# Parameters:
--podcast NAME        # Analyze specific podcast
--speaker NAME        # Focus on specific speaker
--episode ID          # Analyze single episode
--format FORMAT       # Output format: text, json, html
--output FILE         # Save report to file
--min-episodes N      # Only show speakers in N+ episodes
-v, --verbose         # Detailed analysis

# Examples:
python scripts/analysis/speaker_summary_report.py                    # All speakers summary
python scripts/analysis/speaker_summary_report.py --podcast "Interview Show" --format html
python scripts/analysis/speaker_summary_report.py --speaker "John Doe" --verbose
python scripts/analysis/speaker_summary_report.py --episode "tech_talk_ep_050"
python scripts/analysis/speaker_summary_report.py --min-episodes 5 --output regular_speakers.json

# Report includes:
# - Speaker identification statistics
# - Speaking time distribution
# - Episode participation
# - Conversation dynamics
# - Turn-taking patterns
# - Co-appearance networks
```

### Testing Scripts

#### seeding_pipeline/scripts/testing/run_tests.py

**Purpose:**
The run_tests.py script serves as the main test runner for the seeding pipeline module, orchestrating the execution of all test suites including unit tests, integration tests, and end-to-end tests. It provides flexible test selection, parallel execution capabilities, and comprehensive reporting of test results. The script ensures code quality by validating all components of the pipeline before deployment and can be integrated into continuous integration workflows. It supports various testing configurations and can run specific test subsets for focused testing during development.

**Process:**
The script discovers all test files in the tests directory following Python testing conventions (test_*.py or *_test.py patterns). It configures the test environment by setting appropriate environment variables and ensuring test databases are available. The script can run tests in parallel using multiple processes to speed up execution on multi-core systems. It captures test output, timing information, and coverage data when requested. For each test suite, it manages test fixtures, handles setup and teardown operations, and ensures proper isolation between tests. The script aggregates results from all test runs and generates comprehensive reports showing passed, failed, and skipped tests. It can also run tests in different modes such as quick smoke tests, full regression tests, or specific component tests. Failed tests are reported with detailed stack traces and diagnostic information.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/testing/run_tests.py [OPTIONS]

# Parameters:
--suite SUITE         # Run specific test suite
--pattern PATTERN     # Run tests matching pattern
--parallel N          # Run tests in N parallel processes
--coverage           # Generate coverage report
--verbose            # Verbose test output
--failfast           # Stop on first failure
--markers MARKERS    # Run tests with specific markers
--output FILE        # Save results to file

# Examples:
python scripts/testing/run_tests.py                      # Run all tests
python scripts/testing/run_tests.py --suite unit        # Unit tests only
python scripts/testing/run_tests.py --pattern "*storage*" # Storage-related tests
python scripts/testing/run_tests.py --parallel 4 --coverage  # Parallel with coverage
python scripts/testing/run_tests.py --markers "not slow"  # Skip slow tests
python scripts/testing/run_tests.py --failfast --verbose  # Debug mode

# Test suites:
# - unit: Fast unit tests
# - integration: Integration tests
# - e2e: End-to-end tests
# - performance: Performance tests
```

#### seeding_pipeline/scripts/testing/run_smoke_tests.py

**Purpose:**
The run_smoke_tests.py script executes a minimal set of critical tests designed to quickly verify that the seeding pipeline's core functionality is working correctly. These smoke tests cover the essential paths through the system including VTT parsing, knowledge extraction, and database storage. The script is ideal for rapid validation after deployments, configuration changes, or as a pre-commit check. It provides fast feedback (typically under 30 seconds) about system health without running the full test suite.

**Process:**
The script runs a carefully selected subset of tests that cover critical functionality without requiring extensive setup or processing time. It begins by verifying basic connectivity to required services like Neo4j and model APIs. It then tests core components including VTT file parsing with a small sample file, basic knowledge extraction on a short text segment, and database write/read operations. The script validates that embeddings can be generated and that the pipeline configuration is valid. Each test is designed to complete quickly while still exercising the essential code paths. If any smoke test fails, the script provides immediate feedback about which component is malfunctioning. The tests use minimal test data and mock external services where possible to ensure consistent and fast execution.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/testing/run_smoke_tests.py [OPTIONS]

# Parameters:
--timeout SECONDS    # Maximum time for smoke tests (default: 30)
--skip-external      # Skip external service checks
--config FILE        # Use specific config file
-v, --verbose        # Show detailed test output

# Examples:
python scripts/testing/run_smoke_tests.py                    # Quick validation
python scripts/testing/run_smoke_tests.py --timeout 60      # Allow more time
python scripts/testing/run_smoke_tests.py --skip-external   # Offline mode
python scripts/testing/run_smoke_tests.py -v               # Debug failures

# Smoke tests cover:
# - Configuration loading
# - Database connectivity
# - VTT parsing basics
# - Simple extraction
# - Embedding generation
# - Basic storage operations
```

### Monitoring Scripts

#### seeding_pipeline/scripts/monitoring/monitor_caching.py

**Purpose:**
The monitor_caching.py script provides real-time monitoring and analysis of the caching system used in the seeding pipeline. It tracks cache performance metrics including hit rates, miss rates, memory usage, and eviction patterns for various caches like the Gemini prompt cache and embedding cache. The script helps optimize cache configurations by identifying inefficient cache usage patterns and memory bottlenecks. It's essential for maintaining pipeline performance and managing memory resources effectively, especially when processing large podcast libraries.

**Process:**
The script connects to the running seeding pipeline process and attaches monitoring hooks to all cache instances. It continuously collects metrics including cache hits, misses, evictions, and memory usage for each cache type. The script calculates rolling averages for hit rates and identifies patterns in cache usage across different pipeline stages. It monitors memory pressure and can alert when caches are consuming excessive memory or when hit rates drop below configured thresholds. The monitoring data is displayed in real-time with optional logging to files for historical analysis. The script can also generate cache performance reports showing which cached items are most valuable and which cache configurations might need adjustment. It tracks cache effectiveness over time and can identify when caches should be cleared or resized.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/monitoring/monitor_caching.py [OPTIONS]

# Parameters:
--duration MINUTES    # Monitor for N minutes (default: continuous)
--interval SECONDS    # Sampling interval (default: 5)
--cache TYPE          # Monitor specific cache type
--output FILE         # Log metrics to file
--alert-threshold N   # Alert if hit rate < N%
--memory-limit MB     # Alert if cache > MB
-v, --verbose         # Detailed metrics

# Examples:
python scripts/monitoring/monitor_caching.py                    # Continuous monitoring
python scripts/monitoring/monitor_caching.py --duration 30     # Monitor for 30 minutes
python scripts/monitoring/monitor_caching.py --cache prompt --alert-threshold 80
python scripts/monitoring/monitor_caching.py --output cache_metrics.log --interval 10
python scripts/monitoring/monitor_caching.py --memory-limit 1024 -v

# Monitors:
# - Cache hit/miss rates
# - Memory usage per cache
# - Eviction frequencies
# - Access patterns
# - Performance impact
# - Memory pressure
```

#### seeding_pipeline/scripts/monitoring/metrics_dashboard.py

**Purpose:**
The metrics_dashboard.py script provides a comprehensive real-time dashboard displaying key performance indicators and system metrics for the seeding pipeline. It aggregates data from multiple sources including processing statistics, database metrics, API usage, and system resources to give operators a complete view of pipeline health and performance. The dashboard helps identify bottlenecks, track processing progress, and ensure the system is operating within expected parameters. It's particularly useful during large processing runs or when troubleshooting performance issues.

**Process:**
The script creates a terminal-based dashboard that updates in real-time with current system metrics. It connects to various monitoring endpoints including the Neo4j database for graph statistics, the pipeline process for processing metrics, and system APIs for resource usage. The dashboard displays information in organized sections including processing progress (episodes completed, segments processed, units extracted), performance metrics (processing rate, API latencies, cache hit rates), resource usage (CPU, memory, disk I/O), and error statistics (failed episodes, retry counts, validation errors). The script calculates trending information to show whether metrics are improving or degrading over time. It can also trigger alerts when metrics exceed defined thresholds. The dashboard supports different view modes including summary view, detailed view, and historical trends.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/monitoring/metrics_dashboard.py [OPTIONS]

# Parameters:
--refresh SECONDS     # Dashboard refresh rate (default: 2)
--view MODE          # Display mode: summary, detailed, trends
--podcast NAME       # Show metrics for specific podcast
--export FILE        # Export metrics snapshots
--alert-config FILE  # Load alert thresholds
--history MINUTES    # Show historical data
-v, --verbose        # Show debug metrics

# Examples:
python scripts/monitoring/metrics_dashboard.py                    # Standard dashboard
python scripts/monitoring/metrics_dashboard.py --view detailed   # Detailed metrics
python scripts/monitoring/metrics_dashboard.py --podcast "Tech Talk" --history 60
python scripts/monitoring/metrics_dashboard.py --export metrics.json --refresh 5
python scripts/monitoring/metrics_dashboard.py --alert-config alerts.yaml

# Dashboard sections:
# - Processing Progress
# - Performance Metrics  
# - Resource Usage
# - API Statistics
# - Error Summary
# - Cache Performance
# - Database Statistics
```

### Maintenance Scripts

#### seeding_pipeline/scripts/maintenance/cleanup_imports.py

**Purpose:**
The cleanup_imports.py script automatically organizes and optimizes import statements across all Python files in the seeding pipeline codebase. It removes unused imports, groups imports according to PEP 8 conventions (standard library, third-party, local imports), and sorts them alphabetically within each group. The script helps maintain code cleanliness, reduces file sizes, and prevents import-related conflicts. It's particularly useful after refactoring sessions or when integrating code from different sources.

**Process:**
The script scans all Python files in the seeding pipeline directory, parsing each file's abstract syntax tree (AST) to identify import statements and their usage. It tracks which imported names are actually referenced in the code and marks unused imports for removal. The script then reorganizes the remaining imports into three groups: standard library imports (like os, sys), third-party package imports (like numpy, neo4j), and local application imports. Within each group, imports are sorted alphabetically for consistency. The script handles various import styles including regular imports, from imports, and aliased imports. It preserves important comments associated with imports and maintains any import-time side effects. Before making changes, it can create backups of modified files and provide a dry-run mode to preview changes.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/maintenance/cleanup_imports.py [OPTIONS]

# Parameters:
--path PATH          # Specific file or directory to clean
--dry-run           # Show changes without applying them
--backup            # Create backup files
--skip-tests        # Don't clean test files
--aggressive        # Remove all unused imports (careful!)
--fix-style         # Also fix import style issues
-v, --verbose       # Show detailed changes

# Examples:
python scripts/maintenance/cleanup_imports.py                    # Clean all files
python scripts/maintenance/cleanup_imports.py --dry-run        # Preview changes
python scripts/maintenance/cleanup_imports.py --path src/extraction/ --backup
python scripts/maintenance/cleanup_imports.py --skip-tests --fix-style
python scripts/maintenance/cleanup_imports.py --aggressive -v  # Full cleanup

# Performs:
# - Remove unused imports
# - Group imports by type
# - Sort imports alphabetically
# - Fix import formatting
# - Maintain code functionality
```

#### seeding_pipeline/scripts/maintenance/reset_to_virgin_state.py

**Purpose:**
The reset_to_virgin_state.py script performs a complete system reset, returning the seeding pipeline to its initial state as if it had never processed any data. This comprehensive reset includes clearing all databases, removing processed data files, resetting configuration to defaults, and cleaning up any temporary or cached data. The script is useful for testing scenarios, recovering from corrupted states, or preparing the system for a fresh deployment. It ensures that no residual data or configuration from previous runs affects future processing.

**Process:**
The script performs a systematic cleanup of all system components in a specific order to ensure complete reset. It begins by stopping any running pipeline processes and closing database connections. Next, it clears all Neo4j databases by removing all nodes and relationships, then drops and recreates database schemas. The script removes all processed data directories including transcripts, checkpoints, and logs while preserving the directory structure itself. It resets configuration files to their default states, clearing any custom settings or podcast-specific configurations. Cache directories for models and embeddings are cleared to ensure fresh downloads. The script also removes any temporary files, lock files, or process markers. Throughout the reset process, it provides detailed feedback and can create a backup archive of the current state before resetting. Safety confirmations prevent accidental execution in production environments.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/maintenance/reset_to_virgin_state.py [OPTIONS]

# Parameters:
--force              # Skip all confirmation prompts
--backup DIR         # Backup current state to directory
--keep-config        # Preserve configuration files
--keep-models        # Don't clear model cache
--dry-run           # Show what would be reset
--components LIST    # Reset specific components only
-v, --verbose       # Detailed reset progress

# Examples:
python scripts/maintenance/reset_to_virgin_state.py           # Interactive reset
python scripts/maintenance/reset_to_virgin_state.py --force   # Automatic reset
python scripts/maintenance/reset_to_virgin_state.py --backup /tmp/backup --force
python scripts/maintenance/reset_to_virgin_state.py --keep-config --keep-models
python scripts/maintenance/reset_to_virgin_state.py --components "database,cache"

# Resets:
# - All Neo4j databases
# - Processed data directories
# - Configuration files
# - Cache directories
# - Temporary files
# - Log files
# - Checkpoint data
```

### Validation Scripts

#### seeding_pipeline/scripts/validation/validate_deployment.py

**Purpose:**
The validate_deployment.py script performs comprehensive validation of a seeding pipeline deployment to ensure all components are correctly installed, configured, and operational. It runs through a checklist of system requirements, service availability, configuration validity, and basic functionality tests. The script is designed to be run after new deployments, system updates, or configuration changes to verify that the pipeline is ready for production use. It provides clear pass/fail results for each validation check and actionable recommendations for resolving any issues found.

**Process:**
The script executes a series of validation checks organized into categories including environment validation, dependency checks, service connectivity, and functional tests. It begins by verifying the Python version and ensuring all required packages are installed with compatible versions. Next, it tests connectivity to external services including Neo4j databases, API endpoints for language models, and file system permissions for data directories. The script validates configuration files for syntax errors and required fields, ensuring all podcast configurations are properly formed. It performs functional tests by running minimal pipeline operations like parsing a sample VTT file and executing a simple knowledge extraction. Performance benchmarks ensure the system meets minimum speed requirements. The script generates a detailed report showing the status of each check, with green checkmarks for passed items and red X marks for failures, along with specific remediation steps for any issues discovered.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/validation/validate_deployment.py [OPTIONS]

# Parameters:
--config FILE        # Validate specific config file
--podcast NAME       # Validate specific podcast setup
--quick             # Skip time-consuming checks
--fix               # Attempt to fix issues
--output FILE       # Save validation report
--checklist FILE    # Use custom validation checklist
-v, --verbose       # Detailed validation output

# Examples:
python scripts/validation/validate_deployment.py              # Full validation
python scripts/validation/validate_deployment.py --quick      # Fast validation
python scripts/validation/validate_deployment.py --podcast "Tech Talk" --fix
python scripts/validation/validate_deployment.py --output validation_report.txt
python scripts/validation/validate_deployment.py --verbose    # Debug mode

# Validates:
# - Python environment
# - Package dependencies
# - Service connectivity
# - Configuration files
# - File permissions
# - Database access
# - API credentials
# - Basic functionality
```

#### seeding_pipeline/scripts/validation/security_audit.py

**Purpose:**
The security_audit.py script performs a comprehensive security analysis of the seeding pipeline deployment, checking for vulnerabilities, insecure configurations, and compliance with security best practices. It examines credential management, API key storage, database security settings, and file permissions to identify potential security risks. The script helps maintain security standards by providing regular audits that can be integrated into deployment pipelines or run periodically. It generates detailed reports suitable for security reviews and compliance documentation.

**Process:**
The script systematically examines all security-relevant aspects of the deployment starting with credential management. It checks that API keys and passwords are not hardcoded in source files and are properly stored in environment variables or secure configuration files. File permissions are audited to ensure sensitive files like configuration and credentials have appropriate access restrictions. Database connections are tested for secure protocols and proper authentication. The script scans for common vulnerabilities such as SQL injection risks in query construction, unsafe deserialization of data, and exposure of sensitive information in logs. It validates that all external API communications use HTTPS and that certificate validation is enabled. The audit includes checking for outdated dependencies with known security vulnerabilities using vulnerability databases. Results are categorized by severity (critical, high, medium, low) with specific remediation guidance for each finding.

**Usage:**
```bash
# Run from seeding_pipeline directory
cd seeding_pipeline
python scripts/validation/security_audit.py [OPTIONS]

# Parameters:
--scope SCOPE        # Audit scope: full, config, code, dependencies
--output FILE        # Save audit report
--format FORMAT      # Report format: text, json, html
--fix-permissions    # Auto-fix file permissions
--update-deps       # Update vulnerable dependencies
--strict            # Fail on any finding
-v, --verbose       # Detailed findings

# Examples:
python scripts/validation/security_audit.py                    # Full security audit
python scripts/validation/security_audit.py --scope config    # Configuration only
python scripts/validation/security_audit.py --output security_report.html --format html
python scripts/validation/security_audit.py --fix-permissions --update-deps
python scripts/validation/security_audit.py --strict -v       # CI/CD mode

# Audits:
# - Credential storage
# - File permissions  
# - API security
# - Database security
# - Dependency vulnerabilities
# - Code security patterns
# - Log exposure
# - Network security
```

---

## Transcriber Scripts

### Transcriber Setup Scripts

#### transcriber/scripts/setup/setup_test_env.sh

**Purpose:**
The setup_test_env.sh script creates a complete test environment for the transcriber module, including mock services, test data, and configuration suitable for testing transcription functionality without consuming API credits or requiring real podcast feeds. It sets up mock Deepgram responses, sample RSS feeds, and test audio files that allow comprehensive testing of the transcriber's functionality. The script is essential for development, testing, and CI/CD pipelines where real API access may not be available or desirable.

**Process:**
The script begins by creating a dedicated test directory structure that mirrors the production environment but uses test-specific paths. It generates mock RSS feed files with various podcast structures including different episode formats, metadata variations, and edge cases like missing fields or special characters. Sample audio files are created or downloaded for testing transcription accuracy. The script configures environment variables to point to mock API endpoints that return predetermined responses, allowing predictable testing scenarios. It sets up a mock Deepgram service that returns realistic transcription responses with proper timing and speaker information. Database connections are configured to use test-specific Neo4j instances to avoid affecting production data. The script also creates test configuration files with various podcast settings to ensure the transcriber handles different configuration scenarios correctly.

**Usage:**
```bash
# Run from transcriber directory
cd transcriber
./scripts/setup/setup_test_env.sh [OPTIONS]

# Parameters:
--clean              # Start with fresh test environment
--mock-api PORT      # Port for mock API server (default: 8888)
--test-data DIR      # Custom test data directory
--skip-audio         # Don't download test audio files
--docker             # Use Docker for mock services
-v, --verbose        # Verbose setup output

# Examples:
./scripts/setup/setup_test_env.sh                    # Standard test setup
./scripts/setup/setup_test_env.sh --clean           # Fresh test environment
./scripts/setup/setup_test_env.sh --mock-api 9999   # Custom API port
./scripts/setup/setup_test_env.sh --docker -v       # Docker-based mocks

# Creates:
# - Mock RSS feeds
# - Test audio files
# - Mock API endpoints
# - Test configurations
# - Sample VTT outputs
# - Test databases
```

### Transcriber Maintenance Scripts

#### transcriber/scripts/maintenance/audit_imports.py

**Purpose:**
The audit_imports.py script analyzes import statements across the transcriber module to identify issues such as circular dependencies, missing imports, or imports from incorrect locations. It helps maintain clean code architecture by ensuring imports follow the module's design patterns and don't create unwanted dependencies between components. The script is particularly useful after refactoring or when integrating new features to ensure the module's structure remains clean and maintainable.

**Process:**
The script builds a complete import graph of the transcriber module by parsing all Python files and tracking import relationships. It identifies several types of import issues including circular imports where module A imports from module B which imports from module A, creating potential runtime errors. The script detects imports from internal implementation details that should not be exposed, helping maintain proper encapsulation. It finds unused imports that can be removed and missing imports that might cause runtime errors. The analysis includes checking that imports follow the module's layered architecture, ensuring that lower layers don't import from higher layers. The script generates visual dependency graphs showing the import relationships and highlights problematic patterns. It can also suggest refactoring approaches to resolve circular dependencies.

**Usage:**
```bash
# Run from transcriber directory
cd transcriber
python scripts/maintenance/audit_imports.py [OPTIONS]

# Parameters:
--path PATH          # Audit specific directory
--output FILE        # Save audit report
--graph FILE         # Generate dependency graph
--fix               # Attempt to fix issues
--strict            # Fail on any issues
-v, --verbose       # Detailed analysis

# Examples:
python scripts/maintenance/audit_imports.py                    # Full audit
python scripts/maintenance/audit_imports.py --path src/      # Source only
python scripts/maintenance/audit_imports.py --graph deps.png  # Visual graph
python scripts/maintenance/audit_imports.py --fix            # Auto-fix issues
python scripts/maintenance/audit_imports.py --strict -v      # CI mode

# Detects:
# - Circular dependencies
# - Architectural violations
# - Unused imports
# - Missing imports
# - Internal API usage
# - Import style issues
```

#### transcriber/scripts/maintenance/migrate_existing_transcriptions.py

**Purpose:**
The migrate_existing_transcriptions.py script handles the migration of transcription data between different formats, storage locations, or schema versions. It ensures that existing transcriptions remain accessible and properly formatted when the system is updated or when moving data between environments. The script can handle various migration scenarios including format conversions (e.g., SRT to VTT), directory restructuring, metadata updates, and database schema changes. It's essential for maintaining data continuity during system upgrades or when consolidating transcriptions from multiple sources.

**Process:**
The script begins by scanning the source location for existing transcription files, identifying their format and structure. It creates a migration plan that details what changes will be applied to each file, including format conversions, metadata updates, and new storage locations. For each transcription, the script validates the source data to ensure it's not corrupted before migration. It then applies the necessary transformations such as converting timestamp formats, updating speaker labels, or adding missing metadata fields. The script maintains data integrity by creating backups before modification and validating the migrated data. It handles special cases like split transcriptions that need to be merged or large transcriptions that need to be segmented. Progress is tracked in a migration log that allows resuming interrupted migrations. The script can also update database references to point to the new transcription locations.

**Usage:**
```bash
# Run from transcriber directory
cd transcriber
python scripts/maintenance/migrate_existing_transcriptions.py [OPTIONS]

# Parameters:
--source DIR         # Source directory with transcriptions
--dest DIR           # Destination directory
--format FORMAT      # Convert to format: vtt, srt, json
--mode MODE          # Migration mode: copy, move, convert
--podcast NAME       # Migrate specific podcast only
--backup DIR         # Backup location
--dry-run           # Preview migration plan
-v, --verbose       # Detailed progress

# Examples:
python scripts/maintenance/migrate_existing_transcriptions.py --source /old/path --dest /new/path
python scripts/maintenance/migrate_existing_transcriptions.py --format vtt --mode convert
python scripts/maintenance/migrate_existing_transcriptions.py --podcast "Tech Talk" --backup /backup
python scripts/maintenance/migrate_existing_transcriptions.py --dry-run -v

# Handles:
# - Format conversions
# - Directory restructuring
# - Metadata updates
# - Schema migrations
# - Filename normalization
# - Deduplication
```

### Transcriber Utility Scripts

#### transcriber/scripts/utilities/check_transcribed.py

**Purpose:**
The check_transcribed.py script provides a quick way to verify which podcast episodes have been successfully transcribed and which are still pending. It compares episodes available in RSS feeds against completed transcriptions, helping identify gaps in transcription coverage. The script is useful for monitoring transcription progress, planning batch processing runs, and ensuring complete podcast coverage. It can generate reports showing transcription statistics and identify episodes that may have failed during previous transcription attempts.

**Process:**
The script connects to both the RSS feed parser and the transcription storage system to build complete lists of available and transcribed episodes. For each configured podcast, it fetches the current RSS feed and extracts episode information including titles, publication dates, and URLs. It then scans the transcription directory and database to identify which episodes have completed transcriptions. The script performs fuzzy matching on episode titles to handle minor variations in naming between RSS feeds and transcription files. It calculates coverage statistics showing the percentage of episodes transcribed and identifies patterns such as missing date ranges or specific episode types. The script can also check transcription quality by validating that transcription files meet minimum size requirements and contain expected fields. For missing episodes, it provides direct commands that can be used to transcribe them.

**Usage:**
```bash
# Run from transcriber directory
cd transcriber
python scripts/utilities/check_transcribed.py [OPTIONS]

# Parameters:
--podcast NAME       # Check specific podcast
--feed-url URL       # Check against specific feed
--output FILE        # Save report to file
--format FORMAT      # Output format: text, json, csv
--missing-only       # Show only missing episodes
--validate           # Validate transcription quality
-v, --verbose        # Detailed information

# Examples:
python scripts/utilities/check_transcribed.py                    # Check all podcasts
python scripts/utilities/check_transcribed.py --podcast "Tech Talk"
python scripts/utilities/check_transcribed.py --missing-only --output missing.txt
python scripts/utilities/check_transcribed.py --validate -v     # Quality check
python scripts/utilities/check_transcribed.py --format json     # Machine-readable

# Shows:
# - Transcription coverage
# - Missing episodes
# - Failed transcriptions
# - Quality issues
# - Transcription commands
# - Statistics summary
```

#### transcriber/scripts/utilities/find_next_episodes.py

**Purpose:**
The find_next_episodes.py script intelligently identifies which podcast episodes should be transcribed next based on various prioritization strategies. It considers factors such as episode age, popularity indicators, gaps in coverage, and user-defined priorities to recommend the most valuable episodes to process. The script helps optimize transcription resource usage by focusing on episodes that provide the most value. It's particularly useful for podcasts with large back catalogs where transcribing everything isn't feasible or immediately necessary.

**Process:**
The script analyzes multiple data sources to score and rank untranscribed episodes for each podcast. It starts by identifying all untranscribed episodes from RSS feeds and categorizes them by age, type, and metadata. The script applies configurable scoring algorithms that consider factors like episode recency (newer episodes often more relevant), episode length (avoiding very short or very long episodes), title keywords (prioritizing episodes matching interest keywords), and gaps in temporal coverage. It can integrate with analytics APIs to consider episode popularity or download counts. The script also respects processing constraints such as maximum episode duration or specific date ranges. It groups recommendations by podcast and provides rationale for each recommendation. The output includes ready-to-run transcription commands ordered by priority.

**Usage:**
```bash
# Run from transcriber directory
cd transcriber
python scripts/utilities/find_next_episodes.py [OPTIONS]

# Parameters:
--podcast NAME       # Find episodes for specific podcast
--count N            # Number of episodes to recommend (default: 5)
--strategy STRAT     # Priority strategy: recent, popular, gaps, balanced
--max-duration MIN   # Maximum episode duration in minutes
--keywords WORDS     # Prioritize titles containing keywords
--date-range RANGE   # Consider episodes in date range
--output FILE        # Save recommendations
-v, --verbose        # Show scoring details

# Examples:
python scripts/utilities/find_next_episodes.py --count 10    # Top 10 recommendations
python scripts/utilities/find_next_episodes.py --podcast "Tech Talk" --strategy recent
python scripts/utilities/find_next_episodes.py --keywords "AI,machine learning" --count 5
python scripts/utilities/find_next_episodes.py --max-duration 60 --strategy balanced
python scripts/utilities/find_next_episodes.py --date-range "2024-01-01:2024-12-31"

# Provides:
# - Prioritized episode list
# - Scoring rationale
# - Transcription commands
# - Coverage analysis
# - Resource estimates
```

---

## UI Scripts

### UI Setup Scripts

#### ui/scripts/setup/manage_ui_servers.sh

**Purpose:**
The manage_ui_servers.sh script provides automated management of the UI application's frontend and backend servers. It intelligently checks if servers are already running on their designated ports (frontend on 5173, backend on 8000) and either restarts them if running or starts them fresh if not running. The script handles all necessary setup including virtual environment activation for the backend, dependency installation, and proper server startup sequences. It provides comprehensive status reporting and error handling, making it the primary tool for UI development server management. The script is essential for developers working on the UI components as it eliminates the manual steps of checking server status, killing processes, and starting servers in the correct order.

**Process:**
The script begins by checking system prerequisites and creating necessary directories including a logs directory for server output. It uses multiple fallback methods (lsof, ss, netstat) to detect processes running on the target ports, ensuring compatibility across different systems. For each server that's already running, it identifies the process ID and gracefully terminates it before starting a new instance. For the backend, the script first checks if a Python virtual environment exists and creates one if needed, then activates it and ensures all dependencies from requirements.txt are installed. The frontend setup involves checking for node_modules and running npm install if needed. Both servers are started as background processes with output redirected to separate log files. The script monitors startup progress and validates that servers are accessible on their expected ports before declaring success. Throughout execution, it provides colored status messages and maintains comprehensive logging for troubleshooting.

**Usage:**
```bash
# Run from ui directory
cd ui
./scripts/setup/manage_ui_servers.sh

# Or run from project root
./ui/scripts/setup/manage_ui_servers.sh

# The script requires no parameters and performs these actions:
# 1. Checks for existing servers on ports 5173 and 8000
# 2. Stops any existing servers
# 3. Starts backend server (FastAPI on port 8000)
# 4. Starts frontend server (Vite on port 5173)
# 5. Provides status and access URLs

# Example output:
# === UI Server Management Script ===
# Checking for existing Frontend on port 5173...
# No Frontend running on port 5173
# Checking for existing Backend on port 8000...  
# Found Backend running (PID: 12345). Stopping...
# Backend stopped successfully
#
# Starting Backend Server...
# Starting FastAPI server on port 8000...
# Backend server started successfully (PID: 54321)
# Backend URL: http://localhost:8000
#
# Starting Frontend Server...
# Starting Vite dev server on port 5173...
# Frontend server started successfully (PID: 65432)
# Frontend URL: http://localhost:5173
#
# ✓ Both servers are now running!
# 
# Server Status:
# - Frontend: http://localhost:5173
# - Backend:  http://localhost:8000
# - API Docs: http://localhost:8000/docs
#
# Logs:
# - Frontend: ui/logs/frontend.log
# - Backend:  ui/logs/backend.log
```

**Features:**
- **Automatic Process Detection**: Uses multiple methods to detect running servers
- **Graceful Restart**: Properly stops existing servers before starting new ones
- **Environment Management**: Handles Python virtual environment creation and activation
- **Dependency Management**: Automatically installs missing dependencies
- **Background Execution**: Starts servers as background processes for continued development
- **Comprehensive Logging**: Separate log files for frontend and backend with timestamps
- **Status Validation**: Confirms servers are responding before declaring success
- **Cross-Platform Compatibility**: Works on Linux, macOS, and Windows (with WSL)
- **Error Handling**: Provides clear error messages and troubleshooting guidance
- **Resource Information**: Shows URLs, PIDs, and log file locations

**Troubleshooting:**
```bash
# If servers fail to start, check the logs:
cat ui/logs/backend.log
cat ui/logs/frontend.log

# To manually stop servers:
kill -9 $(lsof -ti:5173)  # Frontend
kill -9 $(lsof -ti:8000)  # Backend

# To check server status manually:
curl http://localhost:8000/docs  # Backend health
curl http://localhost:5173       # Frontend health

# Common issues:
# - Port already in use: Script will handle this automatically
# - Missing dependencies: Script installs them automatically  
# - Python version issues: Ensure Python 3.8+ is available
# - Node.js not installed: Install Node.js 16+ for frontend
```

---

## Shared Scripts

### shared/scripts/test_simple_tracking.sh

**Purpose:**
The test_simple_tracking.sh script validates the basic tracking functionality that prevents duplicate processing of podcast episodes across the transcriber and seeding pipeline modules. It tests the tracking bridge component that allows the transcriber to check if an episode has already been processed before creating a new transcription. The script ensures that the cross-module communication is working correctly and that episodes are properly marked as processed in the database. This is crucial for efficient pipeline operation and preventing wasted computational resources on reprocessing.

**Process:**
The script sets up a controlled test environment with known test episodes and runs through various tracking scenarios. It first creates test episode entries in the Neo4j database with different processing statuses (complete, in-progress, failed). Then it simulates the transcriber checking these episodes through the tracking bridge API. The script verifies that completed episodes are correctly identified and skipped, in-progress episodes are handled appropriately, and failed episodes can be retried. It tests edge cases such as database connection failures, where the system should fall back to safe behavior. The script also validates that the tracking updates work correctly when episodes complete processing. Performance tests ensure that tracking checks don't significantly slow down the transcription process.

**Usage:**
```bash
# Run from project root directory
./shared/scripts/test_simple_tracking.sh [OPTIONS]

# Parameters:
--podcast NAME       # Test with specific podcast
--episodes N         # Number of test episodes (default: 10)
--neo4j-uri URI      # Custom Neo4j connection
--cleanup            # Remove test data after
-v, --verbose        # Verbose test output

# Examples:
./shared/scripts/test_simple_tracking.sh                    # Basic tracking test
./shared/scripts/test_simple_tracking.sh --episodes 50     # Larger test set
./shared/scripts/test_simple_tracking.sh --podcast "Test Podcast" --cleanup
./shared/scripts/test_simple_tracking.sh -v               # Debug mode

# Tests:
# - Episode detection
# - Status checking
# - Update operations
# - Error handling
# - Performance impact
# - Fallback behavior
```

### shared/scripts/test_tracking_sync.sh

**Purpose:**
The test_tracking_sync.sh script performs comprehensive testing of the synchronization between the transcriber and seeding pipeline tracking systems. It simulates concurrent processing scenarios where both modules might be accessing or updating episode tracking information simultaneously. The script ensures data consistency and prevents race conditions that could lead to duplicate processing or missed episodes. It validates that the distributed tracking system maintains accuracy even under high load conditions with multiple podcasts being processed in parallel.

**Process:**
The script creates a complex test scenario with multiple podcasts and episodes in various states of processing. It spawns multiple processes that simulate the transcriber and seeding pipeline running concurrently, each trying to claim and process episodes. The script monitors for race conditions where two processes might try to process the same episode simultaneously. It validates that the locking mechanisms work correctly and that episode status transitions follow the expected state machine (pending → processing → complete). The script tests failure scenarios such as processes crashing mid-operation and ensures that episodes can be recovered and reprocessed. It also measures synchronization overhead and ensures that the tracking system doesn't become a performance bottleneck. Stress tests push the system with rapid status updates to verify it maintains consistency under load.

**Usage:**
```bash
# Run from project root directory
./shared/scripts/test_tracking_sync.sh [OPTIONS]

# Parameters:
--podcasts N         # Number of test podcasts (default: 3)
--episodes N         # Episodes per podcast (default: 20)
--workers N          # Concurrent workers (default: 4)
--duration SEC       # Test duration in seconds
--failure-rate P     # Simulate P% failure rate
--neo4j-uri URI      # Custom Neo4j connection
-v, --verbose        # Detailed test output

# Examples:
./shared/scripts/test_tracking_sync.sh                      # Standard sync test
./shared/scripts/test_tracking_sync.sh --workers 8         # High concurrency
./shared/scripts/test_tracking_sync.sh --failure-rate 10   # With failures
./shared/scripts/test_tracking_sync.sh --podcasts 5 --episodes 50 --duration 300
./shared/scripts/test_tracking_sync.sh -v                  # Debug mode

# Tests:
# - Concurrent access
# - Race conditions
# - State consistency
# - Lock mechanisms
# - Failure recovery
# - Performance scaling
```

### shared/scripts/test_overlap_fix.py

**Purpose:**
The test_overlap_fix.py script validates the fixes implemented for handling overlapping processing scenarios where the same episode might be picked up by multiple pipeline instances. It tests the robustness of the deduplication logic and ensures that even if multiple processes attempt to process the same episode, only one succeeds while others gracefully skip. The script is essential for validating that the pipeline can safely run in distributed environments or when multiple instances are started accidentally.

**Process:**
The script simulates various overlap scenarios that could occur in production environments. It creates test cases where multiple pipeline instances start processing the same podcast feed simultaneously, testing that the first instance to claim an episode locks it successfully while others detect the lock and skip. The script validates the atomic nature of episode claiming operations in the database, ensuring no partial updates occur. It tests timing-sensitive scenarios where processes might check episode status microseconds apart. The script also validates cleanup operations when a process claims an episode but fails before completing, ensuring the episode can be reclaimed after a timeout. Recovery mechanisms are tested by simulating crashed processes and verifying that their claimed episodes become available for reprocessing. The script measures the overhead of overlap detection and ensures it doesn't significantly impact normal processing performance.

**Usage:**
```bash
# Run from project root directory
python shared/scripts/test_overlap_fix.py [OPTIONS]

# Parameters:
--scenario SCENARIO  # Test scenario: basic, concurrent, crash, all
--instances N        # Number of pipeline instances (default: 3)
--episodes N         # Number of test episodes (default: 10)
--timeout SEC        # Lock timeout in seconds (default: 300)
--neo4j-uri URI      # Custom Neo4j connection
--verbose            # Verbose output

# Examples:
python shared/scripts/test_overlap_fix.py                    # All scenarios
python shared/scripts/test_overlap_fix.py --scenario concurrent --instances 5
python shared/scripts/test_overlap_fix.py --scenario crash --timeout 60
python shared/scripts/test_overlap_fix.py --episodes 50 --verbose

# Validates:
# - Lock acquisition
# - Duplicate detection
# - Timeout handling
# - Crash recovery
# - Atomic operations
# - Performance impact
```

---

## Common Workflows

### Adding and Processing a New Podcast

```bash
# 1. Add the podcast to the system
./add_podcast.sh --name "My New Podcast" --feed "https://example.com/feed.rss"

# 2. Process the first 5 episodes
./run_pipeline.sh --both --podcast "My New Podcast" --max-episodes 5

# 3. Check processing status
./list_podcasts.sh
python seeding_pipeline/scripts/database/comprehensive_database_check.py --podcast "My New Podcast"

# 4. Run clustering on the processed episodes
./run_clustering.sh "My New Podcast"
```

### Troubleshooting Failed Episodes

```bash
# 1. Check which episodes are missing
python transcriber/scripts/utilities/check_transcribed.py --podcast "Problem Podcast" --missing-only

# 2. Analyze the database for issues
python seeding_pipeline/scripts/analysis/analyze_episode_units.py --podcast "Problem Podcast" --min-units 0 --max-units 5

# 3. Delete problematic episode
python seeding_pipeline/scripts/database/delete_single_episode.py --episode "problem_episode_id" --podcast "Problem Podcast"

# 4. Reprocess the episode
./run_pipeline.sh --both --podcast "Problem Podcast" --max-episodes 1 --force
```

### Performance Monitoring

```bash
# 1. Start the metrics dashboard
python seeding_pipeline/scripts/monitoring/metrics_dashboard.py --podcast "Active Podcast"

# 2. In another terminal, monitor caching
python seeding_pipeline/scripts/monitoring/monitor_caching.py --duration 30

# 3. Run performance analysis after processing
python seeding_pipeline/scripts/analysis/speaker_summary_report.py --podcast "Active Podcast" --output performance_report.html --format html
```

### System Maintenance

```bash
# 1. Run security audit
python seeding_pipeline/scripts/validation/security_audit.py --output security_report.txt

# 2. Clean up imports
python seeding_pipeline/scripts/maintenance/cleanup_imports.py --dry-run

# 3. Validate deployment
python seeding_pipeline/scripts/validation/validate_deployment.py --fix

# 4. Run comprehensive tests
python seeding_pipeline/scripts/testing/run_tests.py --coverage
```

---

## Best Practices

1. **Always check transcription status before running the pipeline** to avoid reprocessing
2. **Use --verbose flag** when troubleshooting to get detailed output
3. **Run validation scripts** after configuration changes
4. **Monitor resource usage** during large processing runs
5. **Create backups** before running maintenance scripts
6. **Use --dry-run** options to preview changes before applying them
7. **Check logs** in the data/logs directory for detailed error information
8. **Run smoke tests** after system updates to ensure basic functionality

---

## Troubleshooting

### Common Issues

1. **Neo4j Connection Failures**
   - Check if Neo4j container is running: `docker ps`
   - Verify port availability: `nc -z localhost 7687`
   - Check credentials in .env file

2. **Missing Episodes**
   - Run `check_transcribed.py` to identify gaps
   - Check RSS feed URL is correct and accessible
   - Verify YouTube URL detection worked correctly

3. **Low Extraction Quality**
   - Run `analyze_episode_units.py` to identify problematic episodes
   - Check if episode audio quality is sufficient
   - Verify API keys are valid and have sufficient credits

4. **Performance Issues**
   - Use monitoring scripts to identify bottlenecks
   - Check cache hit rates with `monitor_caching.py`
   - Consider adjusting batch sizes in configuration

---

This manual provides comprehensive documentation for all scripts in the Podcast Knowledge project. For additional help or specific use cases not covered here, consult the individual script help messages using the --help flag.