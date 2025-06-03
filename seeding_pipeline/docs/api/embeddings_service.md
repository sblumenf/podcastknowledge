# Embeddings Service API Documentation

## Overview

The Embeddings Service provides text embedding generation using Google's Gemini text-embedding-004 model. This service is used throughout the pipeline to generate semantic embeddings for entities, segments, and other text content.

## Configuration

### Environment Variables
- `GEMINI_API_KEY` (required): Your Google API key with access to Gemini models

### Configuration Options
```yaml
embedding_model: "models/text-embedding-004"  # Default Gemini model
embedding_dimensions: 768                      # Fixed for text-embedding-004
embedding_batch_size: 100                      # Optimal for API efficiency
```

## API Reference

### EmbeddingsService

The main service class for generating embeddings.

#### Initialization

```python
from src.services.embeddings import EmbeddingsService

# Using environment variable for API key
service = EmbeddingsService()

# Or with explicit API key
service = EmbeddingsService(api_key="your-api-key")
```

#### Methods

##### generate_embedding(text: str) -> List[float]

Generate embedding for a single text.

**Parameters:**
- `text` (str): Input text to embed

**Returns:**
- List[float]: 768-dimensional embedding vector

**Example:**
```python
embedding = service.generate_embedding("This is a sample text")
# Returns: [0.123, -0.456, 0.789, ...] (768 values)
```

**Special Cases:**
- Empty or whitespace-only text returns a zero vector of 768 dimensions
- Text longer than 2048 tokens is truncated

##### generate_embeddings(texts: List[str]) -> List[List[float]]

Generate embeddings for multiple texts efficiently using batch processing.

**Parameters:**
- `texts` (List[str]): List of input texts

**Returns:**
- List[List[float]]: List of 768-dimensional embedding vectors

**Example:**
```python
texts = ["First text", "Second text", "Third text"]
embeddings = service.generate_embeddings(texts)
# Returns: [[...], [...], [...]] (3 embeddings of 768 dimensions each)
```

##### compute_similarity(embedding1: List[float], embedding2: List[float]) -> float

Compute cosine similarity between two embeddings.

**Parameters:**
- `embedding1` (List[float]): First embedding vector
- `embedding2` (List[float]): Second embedding vector

**Returns:**
- float: Cosine similarity score between -1 and 1

**Example:**
```python
similarity = service.compute_similarity(emb1, emb2)
# Returns: 0.85 (high similarity)
```

##### find_similar(query_embedding: List[float], embeddings: List[List[float]], top_k: int = 5) -> List[Tuple[int, float]]

Find most similar embeddings to a query.

**Parameters:**
- `query_embedding` (List[float]): Query embedding vector
- `embeddings` (List[List[float]]): List of embeddings to search
- `top_k` (int): Number of top results to return (default: 5)

**Returns:**
- List[Tuple[int, float]]: List of (index, similarity_score) tuples sorted by similarity

**Example:**
```python
results = service.find_similar(query_emb, corpus_embeddings, top_k=3)
# Returns: [(5, 0.92), (2, 0.87), (8, 0.81)]
```

##### get_model_info() -> Dict[str, Any]

Get information about the embedding model.

**Returns:**
- Dict containing model metadata

**Example:**
```python
info = service.get_model_info()
# Returns: {
#     'model_name': 'models/text-embedding-004',
#     'dimension': 768,
#     'api_based': True,
#     'batch_size': 100,
#     'rate_limits': {...}
# }
```

## Rate Limiting

The service includes automatic rate limiting to comply with Gemini API limits:
- 1,500 requests per minute
- 4,000,000 characters per minute
- 1,500,000 requests per day

Rate limit errors are handled automatically with exponential backoff retry.

## Error Handling

### Common Exceptions

- `ValueError`: Raised when API key is missing or invalid
- `RateLimitError`: When API rate limits are exceeded (automatic retry)
- `ProviderError`: For other API-related errors

### Example Error Handling

```python
from src.core.exceptions import RateLimitError, ProviderError

try:
    embedding = service.generate_embedding(text)
except RateLimitError as e:
    # Wait and retry
    logger.warning(f"Rate limit hit: {e}")
    time.sleep(60)
except ProviderError as e:
    # Handle API error
    logger.error(f"API error: {e}")
```

## Migration from Sentence Transformers

### Key Changes

| Feature | Old (sentence-transformers) | New (Gemini) |
|---------|---------------------------|--------------|
| Model | all-MiniLM-L6-v2 | text-embedding-004 |
| Dimensions | 384 | 768 |
| Location | Local | API |
| Cost | Free | Per character |
| Latency | ~1ms | ~50-200ms |

### Code Compatibility

The service maintains the same interface, so existing code works without changes:

```python
# Old code (still works)
from src.services.embeddings import EmbeddingsService
service = EmbeddingsService()  # Now uses Gemini

# Generate embeddings (same interface)
embedding = service.generate_embedding("text")
```

## Performance Considerations

1. **Batch Processing**: Always use `generate_embeddings()` for multiple texts
2. **Caching**: Consider caching embeddings for frequently used texts
3. **Rate Limits**: Monitor usage to avoid hitting daily limits
4. **Network**: Ensure stable internet connection for API calls

## Usage Examples

### Basic Usage
```python
# Initialize service
service = EmbeddingsService()

# Single embedding
text = "The history of artificial intelligence"
embedding = service.generate_embedding(text)
print(f"Embedding dimension: {len(embedding)}")  # 768

# Batch processing
texts = ["AI is transformative", "Machine learning advances", "Neural networks"]
embeddings = service.generate_embeddings(texts)

# Find similar texts
query = "Deep learning technology"
query_emb = service.generate_embedding(query)
similar = service.find_similar(query_emb, embeddings, top_k=2)
for idx, score in similar:
    print(f"Text: {texts[idx]}, Similarity: {score:.3f}")
```

### Integration with Knowledge Graph
```python
# Extract entities and generate embeddings
entities = extract_entities(transcript)
entity_texts = [f"{e.name}: {e.description}" for e in entities]
entity_embeddings = service.generate_embeddings(entity_texts)

# Store in Neo4j with embeddings
for entity, embedding in zip(entities, entity_embeddings):
    graph_service.create_node(
        label="Entity",
        properties={
            "name": entity.name,
            "type": entity.entity_type,
            "embedding": embedding
        }
    )
```