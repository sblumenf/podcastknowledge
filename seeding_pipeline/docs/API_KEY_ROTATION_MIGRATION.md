# API Key Rotation Migration Guide

This guide describes how to migrate from the previous fallback-based API key system to the new rotation-based system in the seeding pipeline.

## Overview

The seeding pipeline now uses the same sophisticated API key rotation system as the transcriber module, providing:
- Round-robin key rotation
- Per-key quota tracking
- Model-specific rate limits
- Coordinated usage between LLM and embeddings services
- State persistence for recovery

## Migration Steps

### 1. Environment Variable Setup

The new system supports multiple API keys through environment variables:

```bash
# Option 1: Single key (backward compatible)
export GOOGLE_API_KEY=your_api_key

# Option 2: Multiple keys for rotation
export GEMINI_API_KEY_1=first_api_key
export GEMINI_API_KEY_2=second_api_key
export GEMINI_API_KEY_3=third_api_key
# ... up to GEMINI_API_KEY_9

# Option 3: Mix of both (GOOGLE_API_KEY is used first)
export GOOGLE_API_KEY=primary_key
export GEMINI_API_KEY_1=backup_key_1
export GEMINI_API_KEY_2=backup_key_2
```

### 2. Configuration Updates

No changes required to existing configuration files. The system automatically detects and uses available keys.

### 3. State Directory Configuration

The rotation state is stored in a persistent file. Configure the location:

```bash
# Option 1: Dedicated state directory
export STATE_DIR=/path/to/state/directory

# Option 2: Co-locate with checkpoints (recommended)
export CHECKPOINT_DIR=/path/to/checkpoints
# State will be stored in CHECKPOINT_DIR/rotation_state/

# Option 3: Default (uses ./data directory)
# No configuration needed
```

### 4. Code Changes

#### Direct Service Initialization (Old Way)

```python
# OLD: Direct initialization with single API key
from src.services import LLMService, EmbeddingsService

llm_service = LLMService(
    api_key=api_key,
    model_name="gemini-2.5-flash"
)

embeddings_service = EmbeddingsService(
    api_key=api_key,
    model_name="models/text-embedding-004"
)
```

#### Factory Function Initialization (New Way)

```python
# NEW: Use factory functions for automatic rotation
from src.services import create_gemini_services

# Both services share the same rotation manager
llm_service, embeddings_service = create_gemini_services(
    llm_model="gemini-2.5-flash",
    embeddings_model="models/text-embedding-004"
)

# Or create services individually
from src.services import create_llm_service_only, create_embeddings_service_only

llm_service = create_llm_service_only(model_name="gemini-2.5-flash")
embeddings_service = create_embeddings_service_only(model_name="models/text-embedding-004")
```

### 5. Rate Limit Status

Check the status of your API keys:

```python
# Get rotation status
status = llm_service.get_rate_limit_status()
print(f"Total keys: {status['total_keys']}")
print(f"Available keys: {status['available_keys']}")

# Detailed key states
for key_state in status['key_states']:
    print(f"{key_state['name']}: {key_state['status']}")
```

## Behavior Changes

### Rate Limiting
- **Old**: Single API key with circuit breaker pattern
- **New**: Round-robin rotation across multiple keys

### Quota Exhaustion
- **Old**: Fallback to different API keys when primary fails
- **New**: Automatic rotation to next available key

### Error Handling
- **Old**: RateLimitError when single key exhausted
- **New**: RateLimitError only when ALL keys exhausted

### State Persistence
- **Old**: No state persistence
- **New**: Rotation state saved to disk, survives restarts

## Rollback Plan

If you need to rollback to the old system:

1. Set only `GOOGLE_API_KEY` environment variable
2. The rotation system will work with a single key
3. Behavior will be similar to the old system

## Monitoring

Monitor the rotation system:

```python
# Check rotation metrics
from src.utils.rotation_state_manager import RotationStateManager

metrics = RotationStateManager.get_rotation_metrics()
print(f"State directory: {metrics['state_directory']}")
print(f"State file exists: {metrics['state_file_exists']}")
```

## Troubleshooting

### No API Keys Found
```
ValueError: No API keys found in environment. Please set one of: GOOGLE_API_KEY, GEMINI_API_KEY, or GEMINI_API_KEY_1 through GEMINI_API_KEY_9
```
**Solution**: Set at least one API key environment variable

### State Directory Not Writable
```
WARNING: Failed to ensure state persistence for API key rotation
```
**Solution**: Ensure STATE_DIR or CHECKPOINT_DIR is writable

### All Keys Exhausted
```
RateLimitError: All API keys have exceeded their quotas
```
**Solution**: Wait for quota reset or add more API keys

## Best Practices

1. **Use Multiple Keys**: Distribute load across 3-5 API keys
2. **Monitor Usage**: Check key status regularly
3. **Set State Directory**: Use persistent storage for state files
4. **Coordinate Services**: Use factory functions to share rotation
5. **Handle Errors**: Catch RateLimitError when all keys exhausted

## Testing

Run the rotation tests:

```bash
# Unit tests
pytest tests/unit/test_key_rotation_manager.py
pytest tests/unit/test_services_rotation_integration.py

# Integration tests
pytest tests/integration -k rotation
```

## Support

For issues or questions:
- Check logs for rotation status messages
- Review state file at `STATE_DIR/.key_rotation_state.json`
- Enable debug logging: `export LOG_LEVEL=DEBUG`