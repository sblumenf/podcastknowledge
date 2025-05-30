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
- **💾 Checkpoint Recovery**: Resume processing after interruptions with file-based tracking
- **🔄 Change Detection**: Skip already-processed files using content hashing
- **🎯 RAG Optimized**: Rich metadata and embeddings for retrieval applications
- **🧪 Comprehensive Testing**: Full test coverage for reliability

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/vtt-knowledge-pipeline.git
cd vtt-knowledge-pipeline

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"  # Install with development dependencies
```

### Basic Usage

#### Process a single VTT file:
```bash
python cli.py process-vtt --file transcript.vtt
```

#### Process a folder of VTT files:
```bash
python cli.py process-vtt --folder transcripts/ --pattern "*.vtt"
```

#### Process with additional options:
```bash
python cli.py process-vtt \
    --folder transcripts/ \
    --recursive \
    --skip-errors \
    --checkpoint-enabled
```

#### Dry run to preview what will be processed:
```bash
python cli.py process-vtt --folder transcripts/ --dry-run
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

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLI Interface                            │
├─────────────────────────────────────────────────────────────────┤
│                    Pipeline Orchestrator                          │
├─────────────────────────────────────────────────────────────────┤
│   VTT Parser    │   Knowledge    │    Graph       │   Utility    │
│ & Segmentation  │  Extraction    │  Operations    │  Functions   │
├─────────────────────────────────────────────────────────────────┤
│                     Provider Interfaces                           │
│              LLMProvider    │    GraphProvider    │  Embeddings  │
├─────────────────────────────────────────────────────────────────┤
│                    Core Models & Config                           │
└─────────────────────────────────────────────────────────────────┘
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

# Checkpoint settings
checkpoint_enabled: true
checkpoint_dir: "checkpoints/"
```

## Project Structure

```
vtt_knowledge_pipeline/
├── src/
│   ├── api/             # REST API endpoints
│   ├── core/            # Core models and configuration
│   ├── providers/       # LLM and Graph providers
│   ├── processing/      # VTT parsing and knowledge extraction
│   ├── seeding/         # Pipeline orchestration and ingestion
│   └── utils/           # Utility functions
├── tests/               # Comprehensive test suite
├── docs/                # Documentation
├── config/              # Configuration files
└── cli.py               # Command-line interface
```

## Advanced Features

### Checkpoint System

The pipeline tracks processed files to enable resumption after interruptions:

```bash
# View checkpoint status
python cli.py checkpoint-status

# Clean checkpoint data
python cli.py checkpoint-clean

# Clean specific file from checkpoint
python cli.py checkpoint-clean --file transcript.vtt
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
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
flake8 src/ tests/

# Type checking
mypy src/
```

## Migration from Podcast Pipeline

If migrating from the previous podcast-focused version:

1. Export any existing knowledge graphs
2. Convert audio transcripts to VTT format
3. Process VTT files through this pipeline
4. See [Migration Guide](docs/migration/README.md) for details

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