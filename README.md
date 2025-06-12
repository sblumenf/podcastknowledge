# Podcast Knowledge System

A system for extracting and building knowledge graphs from podcast transcripts.

## Documentation

- **[Overview and Setup](docs/README.md)** - Project overview and quick start guide
- **[API Reference](docs/API.md)** - REST API endpoints and usage
- **[Operations Guide](docs/OPERATIONS.md)** - Deployment, configuration, and maintenance

## Components

- **transcriber/**: Podcast transcription service using Gemini API
- **seeding_pipeline/**: VTT to knowledge graph extraction pipeline
- **data/**: Data storage for transcripts and checkpoints

## Quick Start

### Docker Setup (Recommended)

```bash
# Build and start all services
docker-compose up -d

# Run transcriber
docker-compose run transcriber python cli.py transcribe --feed-url "podcast-rss-url"

# Run seeding pipeline
docker-compose run seeding python cli.py process-vtt --folder /app/data/transcripts
```

### Manual Setup

See [docs/README.md](docs/README.md) for manual setup and usage instructions.