# Configuration Documentation

## Overview

The Podcast Knowledge Graph Pipeline uses a hybrid configuration system that combines:
- Environment variables for secrets and deployment-specific settings
- YAML/JSON configuration files for application settings
- Code constants for fixed values and limits

## Environment Variables

All environment variables can be set in a `.env` file in the project root or exported in your shell.

### Required Variables

#### Database Configuration
- **NEO4J_PASSWORD** (required in production)
  - Description: Password for Neo4j database authentication
  - Example: `export NEO4J_PASSWORD=your_secure_password`

### Optional Variables

#### Database Configuration
- **NEO4J_URI**
  - Description: Neo4j database connection URI
  - Default: `bolt://localhost:7687`
  - Example: `export NEO4J_URI=bolt://neo4j.example.com:7687`

- **NEO4J_USERNAME**
  - Description: Neo4j username
  - Default: `neo4j`
  - Example: `export NEO4J_USERNAME=neo4j`

- **NEO4J_DATABASE**
  - Description: Neo4j database name
  - Default: `neo4j`
  - Example: `export NEO4J_DATABASE=podcast_kg`

#### API Keys
- **GOOGLE_API_KEY**
  - Description: Google API key for Gemini models
  - Default: None
  - Example: `export GOOGLE_API_KEY=your_google_api_key`

- **OPENAI_API_KEY**
  - Description: OpenAI API key for GPT models
  - Default: None
  - Example: `export OPENAI_API_KEY=your_openai_api_key`

- **HF_TOKEN**
  - Description: Hugging Face token for model access
  - Default: None
  - Example: `export HF_TOKEN=your_huggingface_token`

#### Feature Flags
- **USE_SCHEMALESS_EXTRACTION**
  - Description: Enable schemaless entity extraction
  - Default: `false`
  - Values: `true`, `false`
  - Example: `export USE_SCHEMALESS_EXTRACTION=true`

- **ENABLE_TRACING**
  - Description: Enable distributed tracing with Jaeger
  - Default: `false`
  - Values: `true`, `false`
  - Example: `export ENABLE_TRACING=true`

- **ENABLE_METRICS**
  - Description: Enable Prometheus metrics collection
  - Default: `false`
  - Values: `true`, `false`
  - Example: `export ENABLE_METRICS=true`

#### Performance Settings
- **SCHEMALESS_CONFIDENCE_THRESHOLD**
  - Description: Confidence threshold for schemaless extraction
  - Default: `0.7`
  - Range: 0.0 - 1.0
  - Example: `export SCHEMALESS_CONFIDENCE_THRESHOLD=0.8`

- **ENTITY_RESOLUTION_THRESHOLD**
  - Description: Similarity threshold for entity resolution
  - Default: `0.85`
  - Range: 0.0 - 1.0
  - Example: `export ENTITY_RESOLUTION_THRESHOLD=0.9`

- **MAX_PROPERTIES_PER_NODE**
  - Description: Maximum properties allowed per graph node
  - Default: `50`
  - Example: `export MAX_PROPERTIES_PER_NODE=100`

#### Logging and Monitoring
- **LOG_LEVEL**
  - Description: Logging level
  - Default: `INFO`
  - Values: `DEBUG`, `INFO`, `WARNING`, `ERROR`
  - Example: `export LOG_LEVEL=DEBUG`

- **LOG_FORMAT**
  - Description: Log output format
  - Default: `json`
  - Values: `json`, `text`
  - Example: `export LOG_FORMAT=text`

#### Resource Limits
- **MAX_WORKERS**
  - Description: Maximum number of worker threads
  - Default: `4`
  - Example: `export MAX_WORKERS=8`

- **MAX_MEMORY_GB**
  - Description: Maximum memory usage in GB
  - Default: `4.0`
  - Example: `export MAX_MEMORY_GB=8.0`

#### Tracing Configuration (if ENABLE_TRACING=true)
- **JAEGER_AGENT_HOST**
  - Description: Jaeger agent hostname
  - Default: `localhost`
  - Example: `export JAEGER_AGENT_HOST=jaeger.example.com`

- **JAEGER_AGENT_PORT**
  - Description: Jaeger agent port
  - Default: `6831`
  - Example: `export JAEGER_AGENT_PORT=6831`

- **SERVICE_NAME**
  - Description: Service name for tracing
  - Default: `podcast-kg-pipeline`
  - Example: `export SERVICE_NAME=podcast-kg-prod`

## Configuration Files

### YAML Configuration Example

Create a `config.yml` file:

```yaml
# Audio Processing
min_segment_tokens: 150
max_segment_tokens: 800
whisper_model_size: "large-v3"
use_faster_whisper: true

# Speaker Diarization
min_speakers: 1
max_speakers: 10

# Processing Settings
batch_size: 10
embedding_batch_size: 50
max_episodes: 5
use_large_context: true
enable_graph_enhancements: true

# GPU and Memory
use_gpu: true
enable_ad_detection: true
use_semantic_boundaries: true
gpu_memory_fraction: 0.8

# Rate Limiting
llm_requests_per_minute: 60
llm_tokens_per_minute: 150000
embedding_requests_per_minute: 500

# Retry Settings
max_retries: 3
retry_delay: 1.0
exponential_backoff: true
```

### Loading Configuration

```python
from src.core.config import Config

# Load from file
config = Config.from_file("config.yml")

# Or use defaults with environment variables
config = Config()
```

## Example .env File

```bash
# Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_secure_password
NEO4J_DATABASE=podcast_kg

# API Keys
GOOGLE_API_KEY=your_google_api_key
# OPENAI_API_KEY=your_openai_api_key  # Optional if using Gemini

# Feature Flags
USE_SCHEMALESS_EXTRACTION=false
ENABLE_TRACING=false
ENABLE_METRICS=false

# Performance
SCHEMALESS_CONFIDENCE_THRESHOLD=0.7
ENTITY_RESOLUTION_THRESHOLD=0.85
MAX_PROPERTIES_PER_NODE=50

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Resources
MAX_WORKERS=4
MAX_MEMORY_GB=4.0
```

## Configuration Precedence

1. Environment variables (highest priority)
2. Configuration file values
3. Default values in code (lowest priority)

## Constants

Fixed values are defined in `src/core/constants.py`:

- Timeout values (request, connection, retry)
- Batch sizes for different operations
- Confidence thresholds
- Model parameters
- Resource limits
- Performance thresholds

See `src/core/constants.py` for the complete list of constants.

## Validation

The configuration system automatically validates:
- Required environment variables are set
- Numeric values are within valid ranges
- Paths exist or can be created
- Dependencies are available

## Best Practices

1. **Never commit secrets** - Use `.env` files and add them to `.gitignore`
2. **Use environment variables** for deployment-specific settings
3. **Use config files** for application behavior settings
4. **Use constants** for fixed limits and thresholds
5. **Document changes** - Update this file when adding new configuration options