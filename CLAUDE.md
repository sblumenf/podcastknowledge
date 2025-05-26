# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains the Podcast Knowledge Graph Pipeline - a modular system for transforming podcast audio into structured knowledge graphs using AI-powered analysis. The main project is located in the `seeding_pipeline/` directory.

## Common Development Commands

### Installation and Setup
```bash
cd seeding_pipeline
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"   # Install with development dependencies
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit           # Unit tests only
pytest tests/integration    # Integration tests
pytest tests/e2e           # End-to-end tests
pytest tests/performance   # Performance tests

# Run with coverage
pytest --cov=src --cov-report=html

# Run a specific test
pytest tests/unit/test_config.py::TestConfig::test_specific_method
```

### Code Quality
```bash
# Format code
black src/ tests/ --line-length 100

# Sort imports
isort src/ tests/ --profile black

# Lint code
flake8 src/ tests/

# Type checking
mypy src/ --strict

# Security audit
bandit -r src/

# Run all code quality checks
python scripts/run_code_quality.py
```

### Development and Debugging
```bash
# Main CLI interface
python cli.py seed --rss-url https://example.com/feed.xml --max-episodes 5

# Run API server
python run_api.py

# Console script entries (after installation)
podcast-kg seed --help
podcast-kg-seed --help
```

### Docker and Deployment
```bash
# Start services with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Build documentation
cd docs && make html
```

## Architecture Overview

The system follows a modular, provider-based architecture:

### Core Components
- **Provider Pattern**: All major functionalities (audio, LLM, graph, embeddings) are implemented as pluggable providers with base interfaces in `src/providers/`
- **Pipeline Orchestration**: The `src/seeding/orchestrator.py` manages the entire processing pipeline with checkpoint recovery
- **Processing Logic**: Business logic for extraction, segmentation, and analysis in `src/processing/`
- **API Layer**: Versioned REST APIs in `src/api/` with v1 being the stable interface

### Key Design Patterns
- **Factory Pattern**: `src/factories/provider_factory.py` manages provider instantiation
- **Interface Segregation**: Clear interfaces defined in `src/core/interfaces.py`
- **Dependency Injection**: Providers are injected into processors, allowing easy testing and swapping
- **Checkpoint/Recovery**: Built-in resilience with checkpoint system in `src/seeding/checkpoint.py`

### Configuration and Environment
- Environment variables loaded from `.env` file (Neo4j credentials, API keys)
- YAML configuration in `config/` directory for pipeline settings
- Comprehensive config validation in `src/core/config.py`

### Testing Strategy
- Mock providers for all interfaces enable fast unit testing
- Integration tests use Docker containers for real services
- Golden output validation for consistency
- Performance regression tests to catch slowdowns

### Monitoring and Observability
- Distributed tracing with Jaeger (automatic instrumentation)
- Prometheus metrics and Grafana dashboards
- Health checks and SLO tracking
- Structured logging with correlation IDs

## Important Considerations

### Resource Management
- Memory monitoring utilities in `src/utils/memory.py` - use for large batch processing
- Rate limiting in `src/utils/rate_limiting.py` - respect API quotas
- GPU usage controlled via config for Whisper transcription

### Error Handling
- Comprehensive retry logic with exponential backoff in `src/utils/retry.py`
- All providers implement proper error handling and resource cleanup
- Checkpoint system ensures no data loss on failures

### Performance Optimization
- Batch processing configured via `batch_size` in config
- Concurrent processing with `max_workers` setting
- Caching strategies implemented in providers
- Connection pooling for database operations

### Adding New Features
- New providers should inherit from base classes in `src/providers/*/base.py`
- Follow existing patterns for error handling and logging
- Add corresponding tests in `tests/providers/`
- Update factory classes to support new providers