# Timeout Adjustments for Resource-Constrained Environments

## Summary

All timeout settings have been tripled to better accommodate resource-constrained environments where processing may be slower due to limited CPU, memory, or network resources.

## Updated Timeout Values

| Component | Previous | New | Rationale |
|-----------|----------|-----|-----------|
| **Speaker Identification** | 120s (2 min) | **360s (6 min)** | Allows for slower LLM responses on constrained systems |
| **Conversation Analysis** | 300s (5 min) | **900s (15 min)** | Complex analysis may take longer with limited resources |
| **Knowledge Extraction** | 600s (10 min) | **1800s (30 min)** | Per-unit extraction needs generous timeout for reliability |
| **Graph Storage** | 300s (5 min) | **900s (15 min)** | Database operations may be slower on limited hardware |
| **Pipeline Overall** | 7200s (2 hours) | **7200s (2 hours)** | Left unchanged as requested |

## Environment Variables

Users can still customize these values based on their specific environment:

```bash
# Resource-constrained environment (new defaults)
export SPEAKER_IDENTIFICATION_TIMEOUT=360
export CONVERSATION_ANALYSIS_TIMEOUT=900
export KNOWLEDGE_EXTRACTION_TIMEOUT=1800
export GRAPH_STORAGE_TIMEOUT=900

# Even more constrained (double the new defaults)
export SPEAKER_IDENTIFICATION_TIMEOUT=720
export CONVERSATION_ANALYSIS_TIMEOUT=1800
export KNOWLEDGE_EXTRACTION_TIMEOUT=3600
export GRAPH_STORAGE_TIMEOUT=1800

# Faster environment (halve the new defaults)
export SPEAKER_IDENTIFICATION_TIMEOUT=180
export CONVERSATION_ANALYSIS_TIMEOUT=450
export KNOWLEDGE_EXTRACTION_TIMEOUT=900
export GRAPH_STORAGE_TIMEOUT=450
```

## Impact

- **Better reliability** in resource-constrained environments
- **Fewer timeout errors** during heavy load or slow network conditions
- **More forgiving** for hobby/development setups with limited resources
- **No performance impact** - timeouts only trigger when operations are genuinely slow

## Considerations

1. **Total Processing Time**: With 30 units and 30-minute timeout each, theoretical max is 15 hours (but parallel processing reduces this significantly)

2. **Memory Usage**: Longer timeouts mean processes stay in memory longer, but this is acceptable for reliability

3. **User Experience**: Better to complete slowly than fail with timeouts

These generous timeouts ensure the pipeline completes successfully even in challenging environments, following the principle that reliability is more important than speed for a hobby application.