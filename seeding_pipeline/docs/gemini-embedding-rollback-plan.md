# Gemini Embedding Rollback Plan

## Overview

This document provides step-by-step instructions to rollback from Gemini text-embedding-004 to the original sentence-transformers implementation if needed.

## When to Rollback

Consider rollback if:
- API costs exceed budget
- Network connectivity issues affect production
- Latency requirements cannot be met
- Critical bugs discovered in Gemini implementation

## Rollback Procedure

### Step 1: Restore Original Embeddings Service

```bash
# Navigate to project directory
cd /path/to/seeding_pipeline

# Restore the original embeddings.py from backup
cp src/services/embeddings_backup.py src/services/embeddings.py

# Remove the Gemini implementation (optional)
rm src/services/embeddings_gemini.py
```

### Step 2: Update Requirements Files

#### requirements.txt
Add back sentence-transformers:
```diff
# Embeddings
+ sentence-transformers==2.2.2
- # Embeddings are now handled via Gemini API (google-generativeai)
```

#### setup.py
Update install_requires:
```diff
-        "google-generativeai>=0.3.2",
+        "sentence-transformers>=2.2.2",
```

### Step 3: Update Configuration

#### src/core/config.py
Revert embedding settings:
```python
# Embedding Settings
embedding_dimensions: int = 384  # Revert from 768
embedding_similarity: str = "cosine"
embedding_model: str = "all-MiniLM-L6-v2"  # Revert from models/text-embedding-004
```

#### src/core/constants.py
Update batch size:
```python
EMBEDDING_BATCH_SIZE = 50  # Revert from 100
```

### Step 4: Update Provider Coordinator

#### src/seeding/components/provider_coordinator.py
Revert the embedding service initialization:
```python
# Initialize embeddings service
self.embedding_service = EmbeddingsService(
    model_name=getattr(self.config, 'embedding_model', 'all-MiniLM-L6-v2'),
    device=getattr(self.config, 'device', 'cpu'),
    batch_size=getattr(self.config, 'embedding_batch_size', 32),
    normalize_embeddings=getattr(self.config, 'normalize_embeddings', True)
)
```

### Step 5: Update Test Mocks

#### tests/utils/external_service_mocks.py
Revert mock dimensions:
```python
def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
    self.model_name = model_name
    self.embedding_size = 384  # Standard size for MiniLM
```

#### tests/unit/test_interfaces_full.py
Update all test assertions from 768 back to 384.

### Step 6: Reinstall Dependencies

```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Reinstall with sentence-transformers
pip install -r requirements.txt
```

### Step 7: Run Tests

```bash
# Run embedding service tests
pytest tests/services/test_embeddings_service.py -v

# Run interface tests
pytest tests/unit/test_interfaces_full.py::TestEmbeddingProvider -v

# Run integration tests
pytest tests/integration/test_e2e_critical_path.py -v
```

## Data Migration

### Handling Different Embedding Dimensions

If you have data stored with 768-dimensional embeddings, you'll need to:

1. **Option A: Re-embed all data** (Recommended)
   ```python
   # Script to re-embed existing data
   from src.services.embeddings import EmbeddingsService
   
   service = EmbeddingsService()  # Now using 384-dim model
   
   # Re-process all entities/segments
   for entity in get_all_entities():
       new_embedding = service.generate_embedding(entity.text)
       update_entity_embedding(entity.id, new_embedding)
   ```

2. **Option B: Dimension reduction** (Not recommended)
   - Use PCA or similar to reduce 768 → 384 dimensions
   - Will result in information loss

### Neo4j Schema Updates

If embedding dimension was stored in schema:
```cypher
// Update embedding dimension constraints
MATCH (n:Entity)
WHERE size(n.embedding) = 768
SET n.embedding_dimension = 384
```

## Verification Checklist

- [ ] Original embeddings.py restored
- [ ] Requirements files updated
- [ ] Configuration reverted to 384 dimensions
- [ ] Tests updated and passing
- [ ] Dependencies reinstalled
- [ ] No imports of GeminiEmbeddingsService remain
- [ ] Provider coordinator using correct initialization
- [ ] Environment variables updated (remove GEMINI_API_KEY if not needed)

## Quick Rollback Script

Create `rollback_embeddings.sh`:
```bash
#!/bin/bash
echo "Rolling back to sentence-transformers..."

# Restore files
cp src/services/embeddings_backup.py src/services/embeddings.py

# Update requirements
sed -i 's/# Embeddings are now handled via Gemini API.*/sentence-transformers==2.2.2/' requirements.txt

# Reinstall
pip install sentence-transformers==2.2.2

echo "Rollback complete. Run tests to verify."
```

## Post-Rollback Considerations

1. **Performance**: Local embeddings will be faster but lower quality
2. **Storage**: Virtual environment will grow to ~5.7GB again
3. **Cost**: No API costs but higher compute requirements
4. **Features**: All functionality remains the same

## Emergency Contacts

If issues arise during rollback:
1. Check git history: `git log --oneline | grep embedding`
2. Restore from git: `git checkout <commit> -- src/services/embeddings.py`
3. Review original PR for context