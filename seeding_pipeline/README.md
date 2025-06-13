# VTT Knowledge Graph Pipeline

A streamlined system for transforming VTT (WebVTT) transcript files into structured knowledge graphs using AI-powered analysis. This tool is optimized for building knowledge bases from transcribed content for RAG (Retrieval-Augmented Generation) applications.

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![Neo4j Version](https://img.shields.io/badge/neo4j-5.14%2B-green)](https://neo4j.com/)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

## Overview

The VTT Knowledge Graph Pipeline automatically:
- 📄 **Parses** WebVTT transcript files with speaker identification
- 🔍 **Segments** content into meaningful chunks for processing
- 🧠 **Extracts** insights, entities, and relationships using LLMs
- 🕸️ **Builds** a Neo4j knowledge graph optimized for RAG applications
- 📊 **Provides** batch processing capabilities for large transcript collections

## Key Features

- **📝 VTT Native**: Direct processing of WebVTT files with full format support
- **🚀 Batch Processing**: Efficiently handle folders of transcript files
- **💾 Neo4j-Based Tracking**: Single source of truth for episode processing status
- **🔄 Smart Recovery**: Automatically skip already-processed episodes using Neo4j tracking
- **🎯 RAG Optimized**: Rich metadata and embeddings for retrieval applications
- **🎙️ Multi-Podcast Support**: Process and store multiple podcasts in separate databases
- **🧪 Comprehensive Testing**: Full test coverage for reliability

## Quick Start

### Setting Up Virtual Environment

1. **Create Virtual Environment**:
   ```bash
   ./scripts/setup_venv.sh
   ```

2. **Activate Virtual Environment**:
   - Linux/Mac:
     ```bash
     source venv/bin/activate
     ```
   - Windows Command Prompt:
     ```cmd
     venv\Scripts\activate
     ```
   - Windows PowerShell:
     ```powershell
     venv\Scripts\Activate.ps1
     ```

3. **Deactivate** (when done):
   ```bash
   deactivate
   ```

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/vtt-knowledge-pipeline.git
cd vtt-knowledge-pipeline

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies - Choose based on your needs:

# Option 1: Core functionality only (fastest, ~60 seconds)
pip install -r requirements-core.txt

# Option 2: Core + API server
pip install -r requirements-core.txt
pip install -r requirements-api.txt

# Option 3: Full installation with all features
pip install -r requirements.txt
```

### Basic Usage

#### Process a single VTT file:
```bash
# Put the VTT file in a folder and use the folder pattern
python -m src.cli.cli process-vtt --folder /path/to/folder --pattern "specific_file.vtt"
```

#### Process a folder of VTT files:
```bash
python -m src.cli.cli process-vtt --folder transcripts/ --pattern "*.vtt"
```

#### Process with additional options:
```bash
python -m src.cli.cli process-vtt \
    --folder transcripts/ \
    --pattern "*.vtt" \
    --recursive \
    --skip-errors \
    --no-checkpoint
```

#### Dry run to preview what will be processed:
```bash
python -m src.cli.cli process-vtt --folder transcripts/ --pattern "*.vtt" --dry-run
```

#### Expected Output:
```
Scanning for VTT files in: transcripts/
  Pattern: *.vtt
  Recursive: False

Found 3 VTT file(s)

Processing VTT files...

[1/3] Processing: episode_001.vtt
  ✓ Success: 45 segments, 12 entities, 8 quotes extracted

[2/3] Processing: episode_002.vtt
  ✓ Success: 67 segments, 18 entities, 15 quotes extracted

[3/3] Processing: episode_003.vtt
  ✓ Success: 52 segments, 14 entities, 11 quotes extracted

==================================================
Processing Summary:
  Total files found: 3
  Successfully processed: 3
  Failed: 0
  Skipped (already processed): 0

Knowledge extraction completed successfully!
Total entities: 44
Total quotes: 34
Total segments: 164
```

## Multi-Podcast Support

The pipeline supports processing multiple podcasts with separate database storage for each.

### Single vs Multi-Podcast Mode

The pipeline operates in two modes:

- **Single Mode** (default): All data stored in one Neo4j database
- **Multi Mode**: Each podcast stored in its own database

Set the mode using environment variable:
```bash
export PODCAST_MODE=single  # Default
export PODCAST_MODE=multi   # Multi-podcast mode
```

### Multi-Podcast Usage

#### List configured podcasts:
```bash
python -m src.cli.cli list-podcasts
```

#### Process files for a specific podcast:
```bash
python -m src.cli.cli process-vtt --podcast tech_talk
```

#### Process all enabled podcasts:
```bash
python -m src.cli.cli process-vtt --all-podcasts
```

### Podcast Configuration

Configure podcasts in `config/podcasts.yaml`:
```yaml
version: '1.0'
podcasts:
  - id: tech_talk
    name: Tech Talk Podcast
    enabled: true
    database:
      uri: neo4j://localhost:7687
      database_name: tech_talk
    processing:
      batch_size: 10
      enable_flow_analysis: true
    metadata:
      description: A podcast about technology trends
      host: John Doe
```

### Directory Structure

In multi-podcast mode, each podcast has its own directory:
```
data/
├── podcasts/
│   ├── tech_talk/
│   │   ├── transcripts/    # Input VTT files
│   │   ├── processed/      # Processed VTT files
│   │   └── exports/        # Export outputs
│   └── data_science_hour/
│       ├── transcripts/
│       ├── processed/
│       └── exports/
```

## VTT Format Requirements

The pipeline expects standard WebVTT format files:

```vtt
WEBVTT

00:00:00.000 --> 00:00:05.000
<v Speaker1>Hello, welcome to our discussion about AI.

00:00:05.000 --> 00:00:10.000
<v Speaker2>Thank you for having me. AI is transforming everything.
```

### Supported Features:
- Timestamps in HH:MM:SS.mmm format
- Speaker identification using `<v>` tags
- Multi-line captions
- Cue identifiers and settings
- NOTE blocks and metadata

## Architecture

The pipeline follows a streamlined architecture with direct integration between components:

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLI Interface (process-vtt)                   │
│                    python -m src.cli.cli                         │
└──────────────────────┬────────────────────────────────────────────┘
                       │ Calls directly
┌─────────────────────────────────────────────────────────────────┐
│                  VTTKnowledgeExtractor                           │
│                  (Main Orchestrator)                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │ VTT Parser  │  │ Knowledge   │  │   Entity    │  │   Neo4j   │ │
│  │     &       │→ │ Extraction  │→ │ Resolution  │→ │ Storage   │ │
│  │Segmentation │  │   (LLM)     │  │             │  │ Service   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────────┘

Flow:
1. CLI discovers and validates VTT files
2. VTTKnowledgeExtractor orchestrates the full pipeline:
   - Parses VTT files into segments
   - Calls LLM services for knowledge extraction
   - Resolves entities and relationships
   - Stores results in Neo4j graph database
3. Returns processing summary to CLI
```

## Requirements

- Python 3.9+
- Neo4j 5.14+
- LLM API access (OpenAI/Anthropic/Google)
- 2GB+ RAM (4GB recommended for batch processing)

## Configuration

1. Create a `.env` file:
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
GOOGLE_API_KEY=your-llm-api-key  # Or OPENAI_API_KEY
```

2. Optional: Customize processing in `config/config.yml`:
```yaml
# VTT processing settings
merge_short_segments: true
min_segment_duration: 2.0  # seconds

# Batch processing
batch_size: 10
max_workers: 4

# Knowledge extraction
model_name: "gemini-1.5-pro"
use_large_context: true

# Episode tracking is now handled by Neo4j
# Legacy checkpoint files are deprecated
```

## Project Structure

```
vtt_knowledge_pipeline/
├── src/
│   ├── api/             # REST API endpoints
│   ├── core/            # Core models and configuration
│   ├── extraction/      # Knowledge extraction components
│   ├── processing/      # VTT parsing and segmentation
│   ├── seeding/         # Pipeline orchestration
│   ├── services/        # Direct service implementations
│   ├── storage/         # Graph storage operations
│   └── utils/           # Utility functions
├── tests/               # Comprehensive test suite
├── docs/                # Documentation
├── config/              # Configuration files
└── cli.py               # Command-line interface
```

## Advanced Features

### Checkpoint System

The pipeline uses Neo4j as the single source of truth for tracking processed episodes:

```bash
# View episode processing status
python -m src.cli.cli status episodes                    # List all episodes
python -m src.cli.cli status episodes --podcast podcast1  # List episodes for specific podcast
python -m src.cli.cli status pending --podcast podcast1  # Show unprocessed VTT files
python -m src.cli.cli status stats                       # Show aggregate statistics

# Force reprocessing of already completed episodes
python -m src.cli.cli process-vtt --folder transcripts/ --force

# Note: checkpoint-status and checkpoint-clean commands are deprecated
```

### Parallel Processing

Process multiple files concurrently for better performance:

```yaml
# config/config.yml
max_workers: 4  # Number of parallel workers
batch_size: 10  # Files per batch
```

### Entity Resolution

The pipeline includes advanced entity resolution to merge duplicate entities across transcripts:

```yaml
# config/config.yml
entity_resolution_enabled: true
entity_resolution_threshold: 0.85  # Similarity threshold
```

## API Usage

The pipeline includes a REST API for integration:

```python
import requests

# Check health
response = requests.get("http://localhost:8000/health")

# Process VTT file
response = requests.post(
    "http://localhost:8000/api/v1/process",
    json={
        "file_path": "/path/to/transcript.vtt",
        "metadata": {"source": "meeting", "date": "2024-01-15"}
    }
)
```

## Performance Considerations

- **Memory Usage**: ~50MB per 100 segments
- **Processing Speed**: ~10-20 segments/second (varies by LLM)
- **Batch Processing**: 100 files in <10 minutes typical
- **Graph Size**: Optimized for millions of nodes/relationships

## Troubleshooting

### Common Issues

#### ❌ "No VTT files found"
- **Cause**: Incorrect folder path or pattern
- **Solution**: 
  ```bash
  # Check if folder exists and contains VTT files
  ls -la /path/to/folder/*.vtt
  # Use absolute paths if relative paths fail
  python -m src.cli.cli process-vtt --folder "$(pwd)/transcripts" --pattern "*.vtt"
  ```

#### ❌ "Failed to make LLM call: API_KEY_INVALID"
- **Cause**: Missing or invalid API key
- **Solution**:
  ```bash
  # Set API key environment variable
  export GOOGLE_API_KEY="your_actual_api_key_here"
  # Or create .env file with:
  echo "GOOGLE_API_KEY=your_actual_api_key_here" > .env
  ```

#### ❌ "NoneType object has no attribute 'run'"
- **Cause**: Neo4j connection failed
- **Solution**:
  ```bash
  # Check if Neo4j is running
  docker ps | grep neo4j
  # Start Neo4j if not running
  docker start neo4j
  # Verify connection settings in .env file
  ```

#### ❌ "Invalid timestamp format"
- **Cause**: Malformed VTT file timestamps
- **Solution**: VTT files must use format `HH:MM:SS.mmm` (e.g., `00:01:23.456`)
  ```vtt
  # ✓ Correct format
  00:00:00.000 --> 00:00:05.000
  
  # ❌ Incorrect format  
  00:00.000 --> 00:05.000
  ```

#### ⚠️ Processing runs too fast (no LLM calls)
- **Symptoms**: Processing completes in seconds, no entities extracted
- **Cause**: Pipeline bypassed knowledge extraction
- **Verification**: Look for log entries showing LLM API calls
- **Solution**: This was the original issue fixed in this pipeline

### Debugging Tips

1. **Enable verbose logging**:
   ```bash
   python -m src.cli.cli process-vtt --folder transcripts/ --pattern "*.vtt" --verbose
   ```

2. **Check processing logs**: Look for LLM API call logs to verify extraction is happening

3. **Verify Neo4j data**: Use the queries below to check if data was stored

## Neo4j Query Examples

Once processing completes, you can query the knowledge graph in Neo4j:

### View Processed Episodes
```cypher
// List all episodes
MATCH (e:Episode) 
RETURN e.title, e.entity_count, e.quote_count, e.segment_count
ORDER BY e.title;
```

### Find Entities by Type
```cypher
// Find all person entities
MATCH (p:Person) 
RETURN p.name, p.confidence, p.episode_id
ORDER BY p.confidence DESC;

// Find all concept entities
MATCH (c:Concept) 
RETURN c.name, c.confidence
ORDER BY c.confidence DESC;
```

### Explore Relationships
```cypher
// Find entities mentioned in episodes
MATCH (episode:Episode)-[:MENTIONS]->(entity)
RETURN episode.title, entity.name, entity.type
ORDER BY episode.title;
```

### Search for Specific Topics
```cypher
// Find episodes mentioning "AI" or "artificial intelligence"
MATCH (episode:Episode)-[:MENTIONS]->(entity)
WHERE toLower(entity.name) CONTAINS "ai" 
   OR toLower(entity.name) CONTAINS "artificial intelligence"
RETURN DISTINCT episode.title, entity.name;
```

### Get Episode Statistics
```cypher
// Processing statistics by episode
MATCH (e:Episode)
OPTIONAL MATCH (e)-[:MENTIONS]->(entity)
OPTIONAL MATCH (e)-[:CONTAINS_QUOTE]->(quote:Quote)
RETURN e.title, 
       e.segment_count as segments,
       count(DISTINCT entity) as entities,
       count(DISTINCT quote) as quotes
ORDER BY entities DESC;
```

### Find Related Content
```cypher
// Find episodes that share common entities
MATCH (e1:Episode)-[:MENTIONS]->(entity)<-[:MENTIONS]-(e2:Episode)
WHERE e1 <> e2
RETURN e1.title, e2.title, entity.name as shared_entity
ORDER BY e1.title, e2.title;
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit
pytest tests/integration
pytest tests/performance

# Run with coverage
pytest --cov=src --cov-report=html

# Run tests in parallel for faster execution
pytest -n auto

# Run tests with detailed output
pytest -v --tb=short
```

For comprehensive test patterns and guidelines, see [Test Fix Summary and Patterns](docs/testing/test-fix-summary.md).

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
flake8 src/ tests/

# Type checking
mypy src/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built on the foundation of the original Podcast Knowledge Graph Pipeline
- Optimized for VTT processing and RAG applications
- Uses Neo4j for graph storage and querying
- Powered by modern LLMs for knowledge extraction