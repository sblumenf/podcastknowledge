# Migrating from LangChain to Direct Gemini API

## Why Migrate?

- Removes 2 dependencies: `langchain` and `langchain-google-genai`
- Reduces potential version conflicts and security vulnerabilities
- Direct API implementation already exists and is tested
- No loss of functionality

## Migration Steps

### 1. Set Environment Variable

Add to your `.env` file:
```
LLM_SERVICE_TYPE=gemini_direct
```

Or use the cached version for better performance:
```
LLM_SERVICE_TYPE=gemini_cached
```

### 2. Update Factory Default (Optional)

If you want to make the direct API the default, edit `src/services/llm_factory.py`:

```python
# Line 54 - Change from:
service_type = os.getenv('LLM_SERVICE_TYPE', LLMServiceType.LANGCHAIN)

# To:
service_type = os.getenv('LLM_SERVICE_TYPE', LLMServiceType.GEMINI_DIRECT)
```

### 3. Install Updated Dependencies

```bash
# Remove old dependencies
pip uninstall langchain langchain-google-genai openai tqdm

# Install from cleaned requirements
pip install -r requirements.txt
```

### 4. Verify Everything Works

```bash
# Run tests
pytest tests/services/test_llm*.py -v

# Test the pipeline
python -m src.cli.cli extract --vtt-file path/to/test.vtt
```

## Rollback Plan

If you need to rollback to langchain:

1. Install langchain dependencies:
   ```bash
   pip install langchain==0.1.0 langchain-google-genai==0.0.5
   ```

2. Set environment variable:
   ```bash
   export LLM_SERVICE_TYPE=langchain
   ```

## Feature Comparison

| Feature | LangChain | Direct API |
|---------|-----------|------------|
| Basic completion | ✓ | ✓ |
| Response caching | ✓ | ✓ |
| Rate limiting | ✓ | ✓ |
| Context caching | ✗ | ✓ |
| Dependencies | 2 extra | 0 extra |
| Performance | Standard | Faster |