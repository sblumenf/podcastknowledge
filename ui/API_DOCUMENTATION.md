# API Documentation

## Base URL
```
http://localhost:8000
```

## Endpoints

### 1. Get All Podcasts
Retrieves a list of all available podcasts.

**Endpoint**: `GET /api/podcasts`

**Response**: `200 OK`
```json
[
  {
    "id": "lex-fridman",
    "name": "Lex Fridman Podcast",
    "host": "Lex Fridman",
    "category": "Technology",
    "description": "Conversations about the nature of intelligence, consciousness, love, and power.",
    "tags": ["AI", "Science", "Philosophy"],
    "enabled": true,
    "database_port": 7688,
    "database_name": "lex_fridman"
  }
]
```

**Error Responses**:
- `500 Internal Server Error` - Server error

**Notes**:
- Data source: `seeding_pipeline/config/podcasts.yaml`
- Returns all podcasts regardless of enabled status

---

### 2. Get Podcast Episodes
Retrieves all episodes (MeaningfulUnits) for a specific podcast.

**Endpoint**: `GET /api/podcasts/{podcast_id}/episodes`

**Parameters**:
- `podcast_id` (path) - The podcast identifier

**Response**: `200 OK`
```json
[
  {
    "id": "mu_001",
    "title": "Episode 1: Introduction to AI Safety"
  },
  {
    "id": "mu_002", 
    "title": "Episode 2: The Future of Machine Learning"
  }
]
```

**Error Responses**:
- `404 Not Found` - Podcast not found
- `500 Internal Server Error` - Server or database error

**Notes**:
- Queries Neo4j database for MeaningfulUnit nodes
- Episodes are sorted by name
- Returns only id and title fields

---

### 3. Chat with Podcast
Sends a query to the podcast-specific knowledge graph and receives an AI-generated response.

**Endpoint**: `POST /api/chat/{podcast_id}`

**Parameters**:
- `podcast_id` (path) - The podcast identifier

**Request Body**:
```json
{
  "query": "What did they discuss about AGI?"
}
```

**Response**: `200 OK`
```json
{
  "answer": "Based on the podcast episodes, AGI (Artificial General Intelligence) was discussed in several contexts...",
  "context": ["Episode references and relevant information"]
}
```

**Error Responses**:
- `404 Not Found` - Podcast not found or chat not available
- `503 Service Unavailable` - Neo4j GraphRAG service unavailable
- `500 Internal Server Error` - Server error

**Notes**:
- Uses neo4j-graphrag for knowledge retrieval
- Each podcast has its own database connection
- Responses include markdown formatting
- May include source episode references

---

## Error Response Format

All error responses follow this format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

## CORS Configuration

The API supports CORS with the following configuration:
- Allowed Origins: `*` (all origins)
- Allowed Methods: `GET, POST`
- Allowed Headers: `*`

## Database Architecture

Each podcast has its own Neo4j database instance:
- Connection determined by podcast configuration
- Host: `localhost`
- Port: Specified in podcast config (e.g., 7688)
- Database name: Specified in podcast config

## Rate Limiting

Currently no rate limiting is implemented. In production, consider adding:
- Request throttling per IP
- Token-based authentication
- Usage quotas per user

## WebSocket Support

Not currently implemented. Future versions may include:
- Real-time chat responses
- Live graph updates
- Streaming episode data