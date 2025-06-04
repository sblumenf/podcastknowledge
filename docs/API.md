# API Documentation

## Overview

The Podcast Knowledge System provides REST APIs for transcription and knowledge extraction services.

## Base URLs

- Development: `http://localhost:8000/api/v1`
- Production: Configure as needed

## Endpoints

### Health Check

```
GET /health
```

Returns service health status and version information.

### Seeding Pipeline API

#### Process VTT File

```
POST /api/v1/process
```

Process a single VTT transcript file.

**Request Body:**
```json
{
  "file_path": "/path/to/transcript.vtt",
  "metadata": {
    "source": "podcast_name",
    "date": "2024-01-15"
  }
}
```

**Response:**
```json
{
  "status": "completed",
  "segments_processed": 150,
  "entities_extracted": 45,
  "processing_time": 123.5
}
```

#### Batch Process VTT Files

```
POST /api/v1/seed
```

Process multiple VTT files from a directory.

**Request Body:**
```json
{
  "folder_path": "/path/to/transcripts",
  "pattern": "*.vtt",
  "recursive": true,
  "extraction_config": {
    "use_schemaless_extraction": true,
    "entity_resolution_threshold": 0.85
  }
}
```

### Transcriber API

The transcriber service operates via CLI rather than REST API. See OPERATIONS.md for CLI usage.

## Common Headers

- `Content-Type: application/json`
- `Accept: application/json`

## Error Responses

All endpoints return standard error responses:

```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {}
}
```

## Rate Limiting

- Default: 100 requests per minute
- Configurable via environment variables

## Authentication

Currently no authentication required for local deployment. Production deployments should implement appropriate security measures.

## Service Dependencies

### Embeddings Service
- Uses Google Gemini text-embedding-004 model
- Generates 768-dimensional vectors
- Batch size: 100 texts per request

### LLM Service
- Supports: Gemini, OpenAI, Anthropic
- Configurable via environment variables
- Automatic retry with exponential backoff

### Graph Storage
- Neo4j 5.14+ required
- Connection pooling enabled
- Batch operations for performance