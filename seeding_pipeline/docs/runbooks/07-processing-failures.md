# Runbook: Processing Failures

## Description
Diagnose and resolve failures in podcast processing pipeline, including transcription, extraction, and graph population errors.

## Symptoms
- [ ] Processing job stuck or not progressing
- [ ] Error messages in logs: "Processing failed for episode"
- [ ] Checkpoints not updating
- [ ] Episodes missing from Neo4j
- [ ] Alert: "Processing failure rate high"

## Impact
- **Severity**: High
- **Affected Components**: Audio processing, LLM extraction, Graph updates
- **User Impact**: Missing or incomplete podcast data

## Prerequisites
- Access to application logs
- Neo4j query access
- Provider API credentials
- Checkpoint directory access

## Resolution Steps

### 1. Identify Failed Episodes
```bash
# Check recent logs for failures
kubectl logs deployment/podcast-kg-pipeline -n podcast-kg --since=1h | grep -i "error\|failed\|exception"

# List stuck checkpoints
kubectl exec -it deployment/podcast-kg-pipeline -n podcast-kg -- \
  ls -la /app/data/checkpoints/ | grep -v complete

# Query Neo4j for incomplete episodes
kubectl port-forward service/neo4j 7687:7687 -n podcast-kg
cypher-shell -u neo4j -p $NEO4J_PASSWORD \
  "MATCH (e:Episode) WHERE NOT EXISTS(e.processed_at) RETURN e.title, e.podcast_name LIMIT 10"
```

### 2. Check Provider Health
```bash
# Test provider connectivity
kubectl exec -it deployment/podcast-kg-pipeline -n podcast-kg -- \
  python -c "from src.api.health import health_check; print(health_check())"

# Check API rate limits
kubectl logs deployment/podcast-kg-pipeline -n podcast-kg | grep -i "rate limit"

# Verify API keys
kubectl get secret podcast-kg-secrets -n podcast-kg -o yaml | grep -E "GOOGLE_API_KEY|OPENAI_API_KEY"
```

### 3. Resume from Checkpoint

#### Option A: Retry Failed Episode
```bash
# Get episode ID from logs
EPISODE_ID="episode_12345"

# Clear failed checkpoint
kubectl exec -it deployment/podcast-kg-pipeline -n podcast-kg -- \
  rm -f /app/data/checkpoints/episode_${EPISODE_ID}_*.pkl

# Retry processing
kubectl exec -it deployment/podcast-kg-pipeline -n podcast-kg -- \
  python -m cli retry-episode --episode-id ${EPISODE_ID}
```

#### Option B: Skip Problematic Episode
```bash
# Mark episode as skipped
kubectl exec -it deployment/podcast-kg-pipeline -n podcast-kg -- \
  python -c "
from src.seeding.checkpoint import mark_episode_skipped
mark_episode_skipped('${EPISODE_ID}', reason='Manual skip - processing error')
"
```

### 4. Fix Common Issues

#### Audio File Issues
```bash
# Check if audio file is accessible
kubectl exec -it deployment/podcast-kg-pipeline -n podcast-kg -- \
  curl -I "https://example.com/episode.mp3"

# Test audio processing directly
kubectl exec -it deployment/podcast-kg-pipeline -n podcast-kg -- \
  python -c "
from src.providers.audio.whisper import WhisperAudioProvider
provider = WhisperAudioProvider({})
result = provider.transcribe('/app/test_audio.mp3')
print(f'Success: {len(result['text'])} characters')
"
```

#### LLM Extraction Issues
```bash
# Test LLM connectivity
kubectl exec -it deployment/podcast-kg-pipeline -n podcast-kg -- \
  python -c "
from src.providers.llm.gemini import GeminiProvider
provider = GeminiProvider({'api_key': '${GOOGLE_API_KEY}'})
response = provider.generate('Test prompt')
print(f'LLM responsive: {len(response) > 0}')
"

# Check for malformed responses
kubectl logs deployment/podcast-kg-pipeline -n podcast-kg | grep -A 10 "JSON parsing error"
```

#### Neo4j Connection Issues
```bash
# Test Neo4j connection
kubectl exec -it deployment/podcast-kg-pipeline -n podcast-kg -- \
  python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j', '${NEO4J_PASSWORD}'))
with driver.session() as session:
    result = session.run('RETURN 1')
    print('Neo4j connected successfully')
"

# Check Neo4j logs
kubectl logs statefulset/neo4j -n podcast-kg --tail=50
```

### 5. Manual Recovery
```bash
# Process single episode manually
kubectl exec -it deployment/podcast-kg-pipeline -n podcast-kg -- \
  python scripts/manual_process.py \
    --episode-url "https://example.com/episode.mp3" \
    --episode-title "Episode Title" \
    --podcast-name "Podcast Name"

# Bulk retry failed episodes
kubectl exec -it deployment/podcast-kg-pipeline -n podcast-kg -- \
  python scripts/retry_failed.py --since "2024-01-01" --max-retries 3
```

## Prevention

### 1. Implement Retry Logic
```python
# In config.yml
processing:
  max_retries: 3
  retry_delay: 60  # seconds
  retry_backoff: 2.0
```

### 2. Add Circuit Breakers
```python
# Provider configuration
providers:
  llm:
    circuit_breaker:
      failure_threshold: 5
      recovery_timeout: 300
      half_open_calls: 3
```

### 3. Monitoring Improvements
- Set up alerts for processing lag
- Monitor checkpoint age
- Track provider error rates
- Alert on stuck episodes

### 4. Data Validation
- Validate RSS feeds before processing
- Check audio file sizes and formats
- Implement transcript length limits
- Validate LLM responses

## Root Cause Analysis

Common causes:
1. **Network Issues**: Timeout downloading large audio files
2. **API Limits**: Rate limiting from LLM providers
3. **Memory Issues**: OOM during audio processing
4. **Data Issues**: Corrupted audio files or invalid metadata
5. **Provider Outages**: External service unavailability

## Recovery Metrics
- Time to detect: _____ minutes
- Time to resolve: _____ minutes
- Episodes affected: _____
- Data loss: None / Partial / Complete

## Related Runbooks
- [08-database-issues.md](08-database-issues.md)
- [09-api-errors.md](09-api-errors.md)
- [14-checkpoint-recovery.md](14-checkpoint-recovery.md)
- [06-high-memory-usage.md](06-high-memory-usage.md)