# Unified Pipeline Configuration

This document describes the simplified configuration for the unified knowledge pipeline.

## Required Environment Variables

The unified pipeline requires these environment variables:

```bash
# Neo4j Database (Required)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j  
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j

# LLM Service (At least one required)
GOOGLE_API_KEY=your_google_api_key
OPENAI_API_KEY=your_openai_api_key

# Optional
HF_TOKEN=your_huggingface_token
YOUTUBE_API_KEY=your_youtube_api_key
LOG_LEVEL=INFO
```

## Configuration Philosophy

The unified pipeline follows these principles:

- **Single Approach Only**: No alternative pipeline configurations
- **No Feature Toggles**: All features are always enabled
- **Fixed Processing**: Semantic boundaries and full feature set always used
- **Simplified Settings**: Only essential configuration options

## Processing Behavior

The unified pipeline always:
- Uses semantic grouping (MeaningfulUnits)
- Enables all knowledge extraction features
- Generates YouTube URLs with timestamp adjustment
- Performs schema-less knowledge discovery
- Applies complete error handling with episode rejection

## Removed Complexity

These configuration options were removed to enforce single approach:
- `use_large_context` (always true)
- `enable_graph_enhancements` (always true)  
- `use_semantic_boundaries` (always true)
- `youtube_search_*` settings (fixed defaults)
- `enable_knowledge_discovery` (always true)
- Alternative feature flags

## Usage

```python
from src.core.config import PipelineConfig

# Simple initialization - defaults handle everything
config = PipelineConfig()

# Only override paths if needed
config = PipelineConfig(
    output_dir=Path("./my_output"),
    checkpoint_dir=Path("./my_checkpoints")
)
```

The unified pipeline requires no configuration choices - it uses the optimal settings for all processing.