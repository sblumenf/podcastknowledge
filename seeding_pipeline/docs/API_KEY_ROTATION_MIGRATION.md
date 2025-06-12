# API Key Simplification - Rotation System Removal

This guide describes the simplification of the API key system from a complex rotation-based approach to a single paid tier API key.

## Overview

The seeding pipeline has been simplified to use a single paid tier API key instead of the complex rotation system. This change provides:
- Simplified architecture with fewer moving parts
- Easier debugging and maintenance  
- No state management or persistence complexity
- Direct API key usage without abstraction layers

## Migration from Rotation System

### Environment Variable Changes

**OLD (Multiple Keys with Rotation):**
```bash
# Old system supported multiple keys
export GEMINI_API_KEY_1=first_api_key
export GEMINI_API_KEY_2=second_api_key  
export GEMINI_API_KEY_3=third_api_key
```

**NEW (Single Paid Tier Key):**
```bash
# New system uses a single paid tier API key
export GEMINI_API_KEY=your_paid_tier_api_key

# Backward compatibility maintained
export GOOGLE_API_KEY=your_paid_tier_api_key  # Also supported
```

### Code Changes

#### Service Initialization

```python
# OLD: Required KeyRotationManager
from src.utils.key_rotation_manager import create_key_rotation_manager
from src.services import LLMService, GeminiEmbeddingsService

key_manager = create_key_rotation_manager()
llm_service = LLMService(key_rotation_manager=key_manager)
embeddings_service = GeminiEmbeddingsService(key_rotation_manager=key_manager)
```

```python
# NEW: Direct API key usage
from src.services import LLMService, GeminiEmbeddingsService

llm_service = LLMService()  # Uses GEMINI_API_KEY from environment
embeddings_service = GeminiEmbeddingsService()  # Uses same key

# Or pass explicitly
llm_service = LLMService(api_key="your_api_key")
embeddings_service = GeminiEmbeddingsService(api_key="your_api_key")
```

#### Factory Functions (Recommended)

```python
# OLD: Factory with rotation manager
from src.services import create_gemini_services

llm_service, embeddings_service = create_gemini_services(
    state_dir="/path/to/state"  # Required for rotation state
)
```

```python
# NEW: Simplified factory
from src.services import create_gemini_services

llm_service, embeddings_service = create_gemini_services()
# Or with explicit API key
llm_service, embeddings_service = create_gemini_services(
    api_key="your_api_key"
)
```

## Removed Components

The following files and functionality have been removed:

### Files Deleted
- `src/utils/key_rotation_manager.py`
- `src/utils/rotation_state_manager.py` 
- `src/seeding/components/rotation_checkpoint_integration.py`
- `tests/unit/test_key_rotation_manager.py`
- `tests/unit/test_rotation_state_manager.py`
- `tests/unit/test_services_rotation_integration.py`

### Features Removed
- Round-robin key rotation
- Per-key quota tracking
- Rotation state persistence
- Multiple API key support
- Rate limit coordination between keys
- Checkpoint integration with rotation state

### Methods Removed
- `llm_service.get_rate_limit_status()`
- `KeyRotationManager` class
- `RotationStateManager` class
- `RotationCheckpointIntegration` class

## Benefits of Simplification

### Reduced Complexity
- **Before**: 1000+ lines of rotation logic, state management, and coordination
- **After**: Simple environment variable lookup

### Easier Debugging
- **Before**: Complex error scenarios with multiple keys and state files
- **After**: Direct API calls with clear error messages

### No State Management
- **Before**: Persistent state files, daily resets, quota tracking
- **After**: Stateless service initialization

### Faster Performance
- **Before**: Key selection overhead, state persistence, coordination delays
- **After**: Direct API initialization

## Error Handling Changes

### Rate Limiting
```python
# OLD: Complex rotation on rate limits
try:
    response = llm_service.complete(prompt)
except RateLimitError as e:
    # System would try next key automatically
    pass
```

```python
# NEW: Direct rate limit handling
try:
    response = llm_service.complete(prompt)
except RateLimitError as e:
    # Handle rate limit with paid tier limits
    # Much higher limits with paid tier
    pass
```

### Error Messages
- **OLD**: "All API keys have exceeded their quotas"
- **NEW**: "Gemini rate limit error: [specific error]"

## Configuration Updates

### Environment Variables
Only one environment variable needed:
```bash
export GEMINI_API_KEY=your_paid_tier_api_key
```

### No State Directory Needed
Remove these configurations:
```bash
# No longer needed
unset STATE_DIR
unset CHECKPOINT_DIR  # Only used for checkpoints now
```

## Testing the New System

```python
# Test API key configuration
from src.utils.api_key import get_gemini_api_key

try:
    api_key = get_gemini_api_key()
    print("✓ API key configured correctly")
except ValueError as e:
    print(f"✗ API key missing: {e}")

# Test service creation
from src.services import create_gemini_services

try:
    llm_service, embeddings_service = create_gemini_services()
    print("✓ Services created successfully")
except Exception as e:
    print(f"✗ Service creation failed: {e}")
```

## Paid Tier Benefits

With a paid tier API key, you get:
- **Higher Rate Limits**: No need for rotation
- **Better Performance**: Direct API access
- **Simplified Billing**: Single key tracking
- **Reliable Service**: Production-grade SLA

## Troubleshooting

### API Key Not Found
```
ValueError: No API key found. Please set GEMINI_API_KEY or GOOGLE_API_KEY environment variable with your paid tier API key.
```
**Solution**: Set the environment variable with your paid tier API key

### Import Errors
```
ImportError: No module named 'src.utils.key_rotation_manager'
```
**Solution**: Update imports to use new simplified services

### Old Rate Limit Methods
```
AttributeError: 'LLMService' object has no attribute 'get_rate_limit_status'
```
**Solution**: Remove calls to rotation-specific methods

## Migration Checklist

- [ ] Update environment variables to use single GEMINI_API_KEY
- [ ] Remove multiple API key environment variables  
- [ ] Update service initialization code
- [ ] Remove rotation-specific method calls
- [ ] Test with paid tier API key
- [ ] Remove state directory configurations
- [ ] Update deployment scripts
- [ ] Verify error handling works correctly

## Support

For issues:
- Ensure paid tier API key is properly set
- Check API key has sufficient quota
- Verify environment variable name is correct (GEMINI_API_KEY)
- Enable debug logging: `export LOG_LEVEL=DEBUG`