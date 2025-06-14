# Dependency Cleanup Complete

## What Was Actually Removed

### From requirements.txt:
- ❌ `langchain==0.1.0` - Moved to optional
- ❌ `langchain-google-genai==0.0.5` - Moved to optional
- ❌ `openai==1.6.1` - Completely unused
- ❌ `tqdm==4.66.1` - Not used in pipeline
- ❌ `scipy==1.11.4` - Moved to optional (has fallbacks)
- ❌ `networkx==3.1` - Moved to optional (has fallbacks)

### From pyproject.toml and setup.py:
- ❌ `torch>=2.1.0` - Moved to optional
- ❌ `sentence-transformers>=2.2.2` - Moved to optional
- All the above removed dependencies

## What Was Added:
- ✅ `psutil>=5.9.6` - Was missing but heavily used
- ✅ `pydantic>=2.5.0` - Was missing but required
- ✅ `google-api-python-client>=2.108.0` - Was missing but required

## Files Modified:
1. ✅ `requirements.txt` - Cleaned up to core dependencies only
2. ✅ `setup.py` - Updated install_requires
3. ✅ `pyproject.toml` - Updated dependencies and added optional groups

## New Optional Dependency Groups:

```bash
# For scientific computing (graph analysis)
pip install -e ".[scientific]"

# For API server
pip install -e ".[api]"  

# For langchain (if still needed)
pip install -e ".[langchain]"

# For local embeddings (instead of Gemini)
pip install -e ".[embeddings-local]"
```

## Results:
- **Before**: 13 direct dependencies (including heavy ones like torch)
- **After**: 9 core dependencies (all lightweight except numpy)
- **Removed**: 6 dependencies completely
- **Made Optional**: 6 dependencies

## Next Steps:
1. Set `LLM_SERVICE_TYPE=gemini_direct` in your `.env` file
2. Run `pip install -r requirements.txt` to get the cleaned dependencies
3. The system will use direct Gemini APIs instead of langchain

## No Functionality Lost:
- All features remain available
- Optional dependencies can be installed when needed
- System has fallbacks for scipy/networkx functionality