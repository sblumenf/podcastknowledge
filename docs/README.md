# Podcast Knowledge System

A system for extracting and building knowledge graphs from podcast transcripts using AI-powered analysis.

## Overview

This project transforms podcast transcripts (VTT format) into structured knowledge graphs stored in Neo4j, optimized for RAG (Retrieval-Augmented Generation) applications.

## Components

### 1. Transcriber (`/transcriber`)
- Transcribes podcast episodes from RSS feeds using Google Gemini API
- Generates WebVTT format with speaker identification
- Features checkpoint recovery and API key rotation

### 2. Seeding Pipeline (`/seeding_pipeline`)
- Processes VTT transcripts into knowledge graphs
- Extracts insights, entities, and relationships using LLMs
- Batch processing with checkpoint recovery
- Neo4j graph storage optimized for RAG

## Quick Start

### Prerequisites
- Python 3.9+
- Neo4j 5.14+
- API keys for LLM services (Gemini/OpenAI/Anthropic)

### Basic Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/podcast-knowledge.git
cd podcast-knowledge
```

2. Set up environment variables:
```bash
# For transcription
export GEMINI_API_KEY_1="your-gemini-key"

# For knowledge extraction
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password"
export GOOGLE_API_KEY="your-llm-key"
```

### Usage

1. Transcribe podcasts:
```bash
cd transcriber
python cli.py transcribe --feed-url "podcast-rss-url" --output-dir ../data/transcripts
```

2. Process transcripts into knowledge graph:
```bash
cd ../seeding_pipeline
python cli.py process-vtt --folder ../data/transcripts --pattern "*.vtt"
```

## Project Structure

```
podcast-knowledge/
├── transcriber/        # Podcast transcription service
├── seeding_pipeline/   # VTT to knowledge graph pipeline
├── data/              # Data storage (transcripts, checkpoints)
└── docs/              # Essential documentation
    ├── README.md      # This file
    ├── API.md         # API endpoints documentation
    └── OPERATIONS.md  # Deployment and configuration
```

## License

MIT License - see LICENSE file for details.