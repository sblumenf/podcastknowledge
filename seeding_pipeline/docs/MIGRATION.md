# Migration Guide: From Monolith to Modular System

This guide provides a step-by-step approach to migrating from the monolithic `podcast_knowledge_system_enhanced.py` to the new modular architecture.

## Table of Contents

1. [Overview](#overview)
2. [Pre-Migration Checklist](#pre-migration-checklist)
3. [Code Migration](#code-migration)
4. [Data Migration](#data-migration)
5. [Configuration Migration](#configuration-migration)
6. [Testing the Migration](#testing-the-migration)
7. [Rollback Procedures](#rollback-procedures)
8. [Feature Comparison](#feature-comparison)
9. [Troubleshooting](#troubleshooting)

## Overview

The modular system provides the same core functionality as the monolith but with:
- Better maintainability and testability
- Plugin-based provider architecture
- Enhanced error handling and recovery
- Improved resource management
- API versioning for future compatibility

### Key Differences

| Aspect | Monolith | Modular |
|--------|----------|---------|
| Structure | Single 8,179-line file | Multiple focused modules |
| Configuration | Hardcoded values | YAML + environment variables |
| Error Handling | Basic try-catch | Structured with severity levels |
| Testing | Manual testing only | Comprehensive test suite |
| Providers | Tightly coupled | Plugin architecture |
| Checkpointing | Basic | Versioned with compression |

## Pre-Migration Checklist

Before migrating, ensure you have:

- [ ] Backed up your Neo4j database
- [ ] Saved any custom configurations
- [ ] Documented any local modifications to the monolith
- [ ] Tested the new system with sample data
- [ ] Reviewed breaking changes below

### Breaking Changes

1. **Removed Features**:
   - Interactive visualization components
   - Live transcription features
   - Real-time analytics dashboard
   - Interactive Q&A interface

2. **API Changes**:
   - Main entry point is now `seed_podcast()` instead of direct instantiation
   - Configuration via files instead of code changes
   - Provider initialization through factories

## Code Migration

### Step 1: Update Import Statements

Replace monolithic imports:

```python
# Old
from podcast_knowledge_system_enhanced import (
    PodcastKnowledgeExtractor,
    EnhancedPodcastSegmenter,
    AudioProcessor
)

# New
from podcast_kg_pipeline.api.v1 import seed_podcast, seed_podcasts
from podcast_kg_pipeline.core.config import PipelineConfig
```

### Step 2: Update Configuration

Migrate from hardcoded configuration to file-based:

```python
# Old - Hardcoded in script
class Config:
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "password"
    WHISPER_MODEL = "large-v3"
    
# New - config/config.yml
providers:
  graph:
    type: neo4j
    config:
      uri: ${NEO4J_URI}
      user: ${NEO4J_USER}
      password: ${NEO4J_PASSWORD}
      
  audio:
    type: whisper
    config:
      model_size: large-v3
```

### Step 3: Update Usage Patterns

Migrate from class instantiation to API calls:

```python
# Old - Direct instantiation
extractor = PodcastKnowledgeExtractor(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password"
)
extractor.seed_knowledge_base_parallel(
    podcast_configs=[{
        "name": "Lex Fridman Podcast",
        "rss_url": "https://lexfridman.com/feed/podcast/"
    }],
    max_episodes_each=10
)

# New - API-based
from podcast_kg_pipeline.api.v1 import seed_podcasts

result = seed_podcasts(
    podcast_configs=[{
        "name": "Lex Fridman Podcast",
        "rss_url": "https://lexfridman.com/feed/podcast/"
    }],
    max_episodes_each=10,
    config_path="config/config.yml"
)
```

### Step 4: Custom Provider Migration

If you have custom processing logic:

```python
# Old - Modified methods in monolith
def custom_extraction_logic(self, segment_text):
    # Custom logic here
    pass

# New - Create a custom provider
from podcast_kg_pipeline.providers.llm.base import LLMProvider

class CustomLLMProvider(LLMProvider):
    def extract_insights(self, segment_text: str) -> Dict[str, Any]:
        # Your custom logic here
        pass
        
# Register the provider
from podcast_kg_pipeline.factories import provider_factory
provider_factory.register_provider('custom_llm', CustomLLMProvider)
```

## Data Migration

### Neo4j Schema Compatibility

The modular system maintains backward compatibility with the existing Neo4j schema. However, it adds versioning:

```cypher
// Check current schema version
MATCH (m:Metadata {type: 'schema_version'})
RETURN m.version

// The modular system will automatically migrate if needed
```

### Checkpoint Migration

Old checkpoints need conversion to the new format:

```python
# Script to migrate checkpoints
from podcast_kg_pipeline.migration.checkpoint_migrator import migrate_checkpoints

# Migrate old checkpoint files
migrate_checkpoints(
    old_checkpoint_dir="./checkpoints",
    new_checkpoint_dir="./data/checkpoints"
)
```

## Configuration Migration

### Environment Variables

Create a `.env` file with your secrets:

```bash
# .env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
GOOGLE_API_KEY=your_gemini_key
```

### Configuration File

Create `config/config.yml`:

```yaml
pipeline:
  batch_size: 5
  max_workers: 4
  checkpoint_interval: 10
  
providers:
  audio:
    type: whisper
    config:
      model_size: large-v3
      device: cuda
      compute_type: float16
      
  llm:
    type: gemini
    config:
      model: gemini-1.5-pro
      temperature: 0.7
      max_retries: 3
      
  graph:
    type: neo4j
    config:
      uri: ${NEO4J_URI}
      user: ${NEO4J_USER}
      password: ${NEO4J_PASSWORD}
      connection_pool_size: 50
      
processing:
  segment_length: 1500
  overlap: 100
  min_segment_length: 100
  
extraction:
  prompts_version: "1.0"
  cache_enabled: true
  cache_ttl: 3600
```

## Testing the Migration

### 1. Validation Script

Run the migration validation script:

```bash
python scripts/validate_migration.py \
    --monolith-script ../podcast_knowledge_system_enhanced.py \
    --test-podcast "https://example.com/podcast.rss" \
    --max-episodes 2
```

### 2. Compare Outputs

The validation script will:
- Run both systems on the same data
- Compare Neo4j node counts and relationships
- Check for missing or different data
- Generate a comparison report

### 3. Performance Testing

```bash
# Benchmark both systems
python scripts/benchmark_migration.py
```

Expected results:
- Memory usage: Similar or better
- Processing time: Within 2x (due to additional validation)
- Resource cleanup: Improved in modular system

## Rollback Procedures

If issues arise during migration:

### 1. Immediate Rollback

```bash
# Stop the new system
pkill -f podcast_kg_pipeline

# Restore Neo4j backup
neo4j-admin restore --from=backup/neo4j-backup-premigration

# Resume using monolith
python podcast_knowledge_system_enhanced.py
```

### 2. Partial Rollback

You can run both systems in parallel:

```python
# Use feature flag to choose system
if os.getenv("USE_MODULAR_SYSTEM", "false").lower() == "true":
    from podcast_kg_pipeline.api.v1 import seed_podcast
    result = seed_podcast(config)
else:
    from podcast_knowledge_system_enhanced import PodcastKnowledgeExtractor
    extractor = PodcastKnowledgeExtractor()
    result = extractor.seed_knowledge_base(config)
```

## Feature Comparison

### Core Features (Maintained)

- ✅ RSS feed parsing and episode discovery
- ✅ Audio transcription with Whisper
- ✅ Speaker diarization
- ✅ Knowledge extraction with LLMs
- ✅ Entity recognition and resolution
- ✅ Graph database population
- ✅ Embedding generation
- ✅ Checkpoint/resume functionality
- ✅ Batch processing

### Removed Features

- ❌ Interactive visualizations
- ❌ Real-time Q&A interface
- ❌ Live transcription mode
- ❌ Web dashboard

### New Features

- ✅ Provider plugin system
- ✅ Configuration management
- ✅ API versioning
- ✅ Health monitoring
- ✅ Enhanced error recovery
- ✅ Resource management
- ✅ Comprehensive testing

## Troubleshooting

### Common Issues

#### 1. Import Errors

```python
# Error: ModuleNotFoundError: No module named 'podcast_kg_pipeline'

# Solution: Install the package
pip install -e /path/to/podcast_kg_pipeline
```

#### 2. Configuration Issues

```python
# Error: ConfigurationError: Missing required configuration

# Solution: Ensure all required fields in config.yml
# Check against config.schema.json for validation
```

#### 3. Provider Initialization

```python
# Error: ProviderError: Failed to initialize audio provider

# Solution: Check provider configuration and dependencies
# Ensure CUDA is available for GPU-based Whisper
```

#### 4. Neo4j Connection

```python
# Error: GraphDatabaseError: Failed to connect to Neo4j

# Solution: Verify Neo4j is running and credentials are correct
docker-compose up -d neo4j  # If using Docker
```

### Debug Mode

Enable detailed logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or via environment variable
export PODCAST_KG_LOG_LEVEL=DEBUG
```

### Getting Help

1. Check the [documentation](./README.md)
2. Review [examples](./examples/)
3. Search [GitHub issues](https://github.com/your-repo/issues)
4. Enable debug logging and check error details

## Migration Timeline

Recommended migration approach:

1. **Week 1**: Test with sample podcasts
2. **Week 2**: Migrate configuration and providers
3. **Week 3**: Process new podcasts with modular system
4. **Week 4**: Migrate historical data if needed
5. **Week 5**: Decommission monolith

## Conclusion

The migration from monolith to modular system provides:
- Better maintainability and testing
- Improved resource management
- Enhanced error handling
- Future extensibility

While some interactive features are removed, the core knowledge extraction functionality is preserved and enhanced. The modular architecture enables easier customization and scaling for production use cases.