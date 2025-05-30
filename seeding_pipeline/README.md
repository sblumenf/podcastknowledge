# Podcast Knowledge Graph Pipeline

A modular, production-ready system for transforming podcast audio into structured knowledge graphs using AI-powered analysis.

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![Neo4j Version](https://img.shields.io/badge/neo4j-5.14%2B-green)](https://neo4j.com/)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)
[![codecov](https://codecov.io/gh/yourusername/podcast-kg-pipeline/branch/main/graph/badge.svg)](https://codecov.io/gh/yourusername/podcast-kg-pipeline)
[![CI](https://github.com/yourusername/podcast-kg-pipeline/workflows/CI/badge.svg)](https://github.com/yourusername/podcast-kg-pipeline/actions)
[![Coverage Status](https://img.shields.io/badge/coverage-8.43%25-red.svg)](htmlcov/index.html)

## Overview

The Podcast Knowledge Graph Pipeline automatically:
- 🎙️ **Transcribes** podcast audio using OpenAI Whisper
- 🔍 **Segments** content into meaningful chunks with speaker diarization
- 🧠 **Extracts** insights, entities, and relationships using LLMs (Gemini)
- 🕸️ **Builds** a Neo4j knowledge graph connecting ideas across episodes
- 📊 **Provides** APIs for batch processing and integration

## Key Features

- **🔌 Modular Architecture**: Plug-in different providers for audio, LLM, and graph processing
- **📈 Scalable Processing**: Handle single episodes or entire podcast catalogs
- **💾 Checkpoint Recovery**: Automatically resume processing after interruptions
- **🛡️ Production Ready**: Comprehensive error handling and resource management
- **🔄 API Versioning**: Stable v1 API with backward compatibility guarantees
- **🔍 Comprehensive Testing**: Unit, integration, and end-to-end test coverage

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/podcast-kg-pipeline.git
cd podcast-kg-pipeline

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

```python
from src.api.v1 import seed_podcast

# Process a single podcast
result = seed_podcast({
    'name': 'My Favorite Podcast',
    'rss_url': 'https://example.com/podcast/feed.xml'
}, max_episodes=5)

print(f"Processed {result['episodes_processed']} episodes")
print(f"Created {result['insights_created']} insights")
```

### CLI Usage

```bash
# Process a single podcast
python cli.py seed --rss-url https://example.com/feed.xml --max-episodes 5

# Process multiple podcasts from config
python cli.py seed --podcast-config podcasts.json --max-episodes 10

# Check system health
python cli.py health
```

## Architecture

```
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
```

## Requirements

- Python 3.9+
- Neo4j 5.14+
- FFmpeg (for audio processing)
- Google Gemini API key
- 4GB+ RAM (8GB recommended)
- GPU with CUDA support (optional, for faster transcription)

## Configuration

1. Create a `.env` file:
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
GOOGLE_API_KEY=your-gemini-api-key
```

2. Optional: Create a custom configuration file:
```yaml
# config/my_config.yml
batch_size: 20
max_workers: 4
model_name: "gemini-1.5-pro"
checkpoint_enabled: true
```

## Project Structure

```
podcast_kg_pipeline/
├── src/
│   ├── api/             # Versioned API interfaces
│   ├── core/            # Core models and configuration
│   ├── providers/       # Pluggable provider implementations
│   ├── processing/      # Knowledge extraction logic
│   ├── seeding/         # Pipeline orchestration
│   └── utils/           # Utility functions
├── tests/               # Comprehensive test suite
├── docs/                # Sphinx documentation
├── scripts/             # Utility scripts
└── cli.py               # Command-line interface
```

## Advanced Features

### Schemaless Mode (Experimental)

The pipeline supports a schemaless knowledge graph extraction mode using Neo4j GraphRAG's SimpleKGPipeline. This mode automatically discovers entities and relationships without predefined schemas:

```yaml
# config/config.yml
use_schemaless_extraction: true
schemaless_confidence_threshold: 0.7
entity_resolution_threshold: 0.85
max_properties_per_node: 50
relationship_normalization: true
```

Features:
- **Automatic Discovery**: Entities and relationships are discovered from content
- **Confidence Filtering**: Filter out low-confidence extractions
- **Entity Resolution**: Automatically merge duplicate entities
- **Property Limits**: Control the number of properties per node
- **Relationship Normalization**: Standardize relationship types

See [docs/migration/to_schemaless.md](docs/migration/to_schemaless.md) for migration guide.

### Custom Providers

Extend the system with your own providers:

```python
from src.providers.llm.base import LLMProvider

class MyCustomLLM(LLMProvider):
    def generate(self, prompt: str, **kwargs) -> str:
        # Your implementation
        pass
```

### Batch Processing

Process multiple podcasts efficiently:

```python
podcasts = [
    {'name': 'Tech Talk', 'rss_url': '...'},
    {'name': 'Science Weekly', 'rss_url': '...'}
]

result = seed_podcasts(podcasts, max_episodes_each=10)
```

### Performance Optimization

```python
config = Config()
config.batch_size = 50      # Larger batches
config.max_workers = 8      # More parallel workers
config.use_gpu = True       # GPU acceleration
```

### Distributed Tracing

Monitor and debug your pipeline with distributed tracing:

```python
# Tracing is automatically enabled
# View traces at http://localhost:16686 (Jaeger UI)

# Custom spans for detailed monitoring
from src.tracing import create_span

with create_span("custom_operation") as span:
    span.set_attribute("episode.id", episode_id)
    # Your processing code
```

See [docs/DISTRIBUTED_TRACING.md](docs/DISTRIBUTED_TRACING.md) for detailed tracing guide.

## Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit
pytest tests/integration
pytest tests/e2e

# Run with coverage
pytest --cov=src --cov-report=html
```

## Documentation

Full documentation is available at [docs/index.rst](docs/index.rst) or can be built with:

```bash
cd docs
make html
```

## Performance

- Processes ~10-20 episodes per hour (depending on length and hardware)
- Handles podcasts with 1000+ episodes
- Memory usage: ~2-4GB for typical podcasts
- Supports concurrent processing of multiple podcasts

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- OpenAI Whisper for transcription
- Google Gemini for LLM capabilities
- Neo4j for graph database
- The podcast community for inspiration

## Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/yourusername/podcast-kg-pipeline/issues)
- 💬 [Discussions](https://github.com/yourusername/podcast-kg-pipeline/discussions)

## Roadmap

- [ ] Support for additional LLM providers (OpenAI, Anthropic)
- [ ] Real-time processing capabilities
- [ ] GraphQL API endpoint
- [ ] Web UI for visualization
- [ ] Kubernetes deployment manifests
- [ ] Multi-language support