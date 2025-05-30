# Feature Preservation Matrix

## Overview
This matrix documents all current features and capabilities in the codebase, marking each as KEEP, REMOVE, or MODIFY for the VTT transcript processing refactor.

## Core Processing Pipeline

| Feature | Status | Reasoning | Dependencies |
|---------|--------|-----------|--------------|
| **RSS Feed Processing** | REMOVE | Not needed for VTT input | feedparser |
| **Audio Download** | REMOVE | Starting with VTT files | urllib, requests |
| **Whisper Transcription** | REMOVE | Using external service | whisper, torch, pyannote |
| **Speaker Diarization** | REMOVE | VTT includes speakers | pyannote.audio |
| **Segment Processing** | KEEP | Still need to parse segments | Core Python |
| **Knowledge Extraction** | KEEP | Core functionality | LLM providers |
| **Entity Resolution** | KEEP | Critical for quality | numpy, scipy |
| **Quote Extraction** | KEEP | Valuable for RAG | Core processing |
| **Importance Scoring** | KEEP | Helps RAG prioritization | networkx |
| **Discourse Flow Analysis** | KEEP | Conversation tracking | Core processing |
| **Emergent Theme Detection** | KEEP | Implicit topic discovery | Core processing |
| **Graph Construction** | KEEP | Core output | neo4j |
| **Checkpoint/Recovery** | KEEP | Reliability for batches | Core Python |

## Provider System

| Feature | Status | Reasoning | Dependencies |
|---------|--------|-----------|--------------|
| **Audio Providers** | REMOVE | No audio processing | whisper, torch |
| **LLM Providers** | KEEP | Core extraction | openai, langchain |
| **Graph Providers** | KEEP | Neo4j storage | neo4j |
| **Embedding Providers** | KEEP | RAG retrieval | sentence-transformers, openai |
| **Provider Factory** | MODIFY | Remove audio registration | Core Python |
| **Mock Providers** | KEEP | Testing support | Core Python |

## API Layer

| Feature | Status | Reasoning | Dependencies |
|---------|--------|-----------|--------------|
| **FastAPI Application** | MODIFY | Keep minimal endpoints | fastapi |
| **Seeding Endpoints** | REMOVE | Replace with VTT endpoints | - |
| **Health Checks** | KEEP | Basic monitoring | - |
| **Metrics Endpoints** | REMOVE | Over-engineered | - |
| **SLO Tracking** | REMOVE | Not needed for seeding | - |
| **API Documentation** | MODIFY | Update for VTT | - |

## Monitoring & Observability

| Feature | Status | Reasoning | Dependencies |
|---------|--------|-----------|--------------|
| **Distributed Tracing** | REMOVE | Overkill for batch | opentelemetry |
| **Jaeger Integration** | REMOVE | External dependency | opentelemetry |
| **Prometheus Metrics** | REMOVE | Over-engineered | - |
| **Grafana Dashboards** | REMOVE | Not needed | - |
| **Basic Logging** | KEEP | Essential debugging | logging |
| **Performance Timing** | KEEP | Simple measurements | time |

## Configuration System

| Feature | Status | Reasoning | Dependencies |
|---------|--------|-----------|--------------|
| **YAML Configuration** | KEEP | Standard approach | PyYAML |
| **Environment Variables** | KEEP | Credentials/keys | python-dotenv |
| **Config Validation** | KEEP | Prevent errors | pydantic |
| **Audio Settings** | REMOVE | No audio processing | - |
| **RSS Settings** | REMOVE | No feed processing | - |
| **VTT Settings** | ADD | New functionality | - |

## Data Models

| Feature | Status | Reasoning | Dependencies |
|---------|--------|-----------|--------------|
| **Podcast Model** | MODIFY | Simplify for VTT | pydantic |
| **Episode Model** | MODIFY | Adapt for VTT files | pydantic |
| **Segment Model** | KEEP | Core data structure | pydantic |
| **Entity Models** | KEEP | Knowledge representation | pydantic |
| **TranscriptSegment** | KEEP | Segment structure | dataclasses |

## Infrastructure

| Feature | Status | Reasoning | Dependencies |
|---------|--------|-----------|--------------|
| **Docker Support** | MODIFY | Simplify for VTT | - |
| **Kubernetes Manifests** | REMOVE | Over-engineered | - |
| **Docker Compose** | MODIFY | Keep Neo4j + app | - |
| **CI/CD Configs** | MODIFY | Update for new flow | - |

## Testing Infrastructure

| Feature | Status | Reasoning | Dependencies |
|---------|--------|-----------|--------------|
| **Unit Tests** | MODIFY | Adapt for VTT | pytest |
| **Integration Tests** | MODIFY | New VTT scenarios | pytest |
| **E2E Tests** | MODIFY | VTT pipeline tests | pytest |
| **Performance Tests** | KEEP | Ensure efficiency | pytest |
| **Test Fixtures** | MODIFY | Add VTT samples | - |
| **Mock Providers** | KEEP | Testing isolation | - |

## Utilities

| Feature | Status | Reasoning | Dependencies |
|---------|--------|-----------|--------------|
| **Memory Monitoring** | KEEP | Resource management | psutil |
| **Retry Logic** | KEEP | API reliability | Core Python |
| **Rate Limiting** | KEEP | API quotas | Core Python |
| **Text Processing** | KEEP | Content cleaning | Core Python |
| **Pattern Matching** | KEEP | Entity extraction | re |
| **Component Tracking** | REMOVE | Over-engineered | - |
| **Feature Flags** | REMOVE | Not needed | - |

## Database & Storage

| Feature | Status | Reasoning | Dependencies |
|---------|--------|-----------|--------------|
| **Neo4j Connection** | KEEP | Core storage | neo4j |
| **Connection Pooling** | KEEP | Performance | neo4j |
| **Index Management** | KEEP | Query performance | neo4j |
| **Schema Evolution** | REMOVE | Start fresh | - |
| **Migration Tools** | REMOVE | No legacy data | - |

## New Features (To Add)

| Feature | Purpose | Dependencies |
|---------|---------|--------------|
| **VTT Parser** | Parse WebVTT format | webvtt-py (TBD) |
| **VTT Folder Scanner** | Batch processing | pathlib |
| **VTT Validation** | Input validation | Core Python |
| **Transcript Ingestion** | New entry point | Core Python |

## Summary Statistics

- **Total Features**: 74
- **KEEP**: 32 (43%)
- **REMOVE**: 29 (39%)
- **MODIFY**: 13 (18%)
- **ADD**: 4

## Impact Analysis

### High Impact Removals
1. Audio processing pipeline - Removes torch, whisper dependencies
2. RSS feed system - Simplifies entry point
3. Monitoring stack - Reduces operational complexity

### Critical Preservations
1. Knowledge extraction pipeline - Core value
2. Entity resolution - Data quality
3. Graph construction - Output format
4. Embeddings - RAG support

### Key Modifications
1. CLI interface - VTT-focused commands
2. Configuration - Remove audio/RSS, add VTT
3. Docker setup - Simplified deployment