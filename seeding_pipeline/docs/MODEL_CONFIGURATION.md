# Model Configuration Guide

This document explains how to configure Gemini models for the podcast knowledge extraction pipeline.

## Overview

The pipeline uses three types of models:
- **Flash Model**: For fast processing tasks (speaker identification, conversation analysis)
- **Pro Model**: For complex reasoning tasks (knowledge extraction)
- **Embedding Model**: For vector operations and semantic search

## Environment Variables

Configure models using these environment variables in your `.env` file:

```bash
# Gemini Flash model for fast processing
GEMINI_FLASH_MODEL=gemini-2.5-flash-001

# Gemini Pro model for complex reasoning
GEMINI_PRO_MODEL=gemini-2.5-pro-001

# Gemini embedding model for vector operations
GEMINI_EMBEDDING_MODEL=text-embedding-004
```

## Valid Model Names

### Text Generation Models
- `gemini-2.0-flash-001`
- `gemini-2.5-flash-001` 
- `gemini-2.5-pro-001`

**Backward Compatibility:**
- `gemini-2.5-flash-preview-05-20` (legacy)
- `gemini-2.5-pro-preview-06-05` (legacy)

### Embedding Models
- `text-embedding-004`
- `models/text-embedding-004`

## Default Configuration

If environment variables are not set, the system uses these defaults:

| Variable | Default Value |
|----------|---------------|
| `GEMINI_FLASH_MODEL` | `gemini-2.5-flash-001` |
| `GEMINI_PRO_MODEL` | `gemini-2.5-pro-001` |
| `GEMINI_EMBEDDING_MODEL` | `text-embedding-004` |

## Model Usage by Component

### Flash Model Components (Speed Priority)
- **VTT Segmenter**: Speaker identification
- **Conversation Analyzer**: Conversation structure analysis
- **Sentiment Analyzer**: Sentiment analysis

### Pro Model Components (Accuracy Priority)
- **Knowledge Extractor**: Entity and insight extraction
- **Complex Reasoning**: Advanced analysis tasks

### Embedding Model Components
- **Vector Operations**: Semantic similarity search
- **Content Embeddings**: Text vectorization

## Configuration Examples

### Development Configuration
```bash
# Use faster, cheaper models for development
GEMINI_FLASH_MODEL=gemini-2.5-flash-001
GEMINI_PRO_MODEL=gemini-2.5-flash-001  # Use flash for everything
GEMINI_EMBEDDING_MODEL=text-embedding-004
```

### Production Configuration
```bash
# Use optimal models for production
GEMINI_FLASH_MODEL=gemini-2.5-flash-001
GEMINI_PRO_MODEL=gemini-2.5-pro-001
GEMINI_EMBEDDING_MODEL=text-embedding-004
```

### Legacy Configuration
```bash
# Support for existing preview models
GEMINI_FLASH_MODEL=gemini-2.5-flash-preview-05-20
GEMINI_PRO_MODEL=gemini-2.5-pro-preview-06-05
GEMINI_EMBEDDING_MODEL=text-embedding-004
```

## Validation

The system automatically validates model configurations at startup:

```
✓ Model configuration validated:
  - Flash model: gemini-2.5-flash-001
  - Pro model: gemini-2.5-pro-001
  - Embedding model: text-embedding-004
```

Invalid configurations will show helpful error messages:

```
Invalid model configuration:
  - GEMINI_FLASH_MODEL 'invalid-model' is not a valid model name
```

## Testing Configuration

Use the test script to verify your configuration:

```bash
python3 test_model_configuration.py
```

## Migration from Hardcoded Models

The previous system used hardcoded model names throughout the codebase. The new system:

1. ✅ Centralizes model configuration in environment variables
2. ✅ Provides validation with helpful error messages
3. ✅ Maintains backward compatibility with existing models
4. ✅ Enables easy model switching without code changes

## Troubleshooting

### Common Issues

**Issue**: `Invalid model configuration` error
**Solution**: Check that your model names match the valid options listed above

**Issue**: Models not loading from environment
**Solution**: Ensure your `.env` file is in the correct location and variables are set

**Issue**: Using wrong model for task
**Solution**: Check the model usage guide above to ensure appropriate model assignment

### Getting Help

If you encounter issues:
1. Check your `.env` file syntax
2. Verify model names against the valid options
3. Run the test configuration script
4. Check the startup logs for validation messages

## API Key Configuration

Don't forget to also configure your Gemini API key:

```bash
GOOGLE_API_KEY=your_gemini_api_key_here
# or
GEMINI_API_KEY=your_gemini_api_key_here
```