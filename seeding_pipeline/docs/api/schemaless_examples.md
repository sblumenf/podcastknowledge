# Schemaless API Examples

This document provides example requests and responses for the schemaless extraction API.

## Basic Schemaless Extraction

### Request
```http
POST /api/v1/seed
Content-Type: application/json

{
  "rss_url": "https://example.com/tech-podcast.xml",
  "name": "Tech Talks Daily",
  "extraction_config": {
    "use_schemaless_extraction": true,
    "schemaless_confidence_threshold": 0.7,
    "entity_resolution_threshold": 0.85,
    "max_properties_per_node": 50,
    "relationship_normalization": true
  },
  "processing_options": {
    "max_episodes": 5
  }
}
```

### Response
```json
{
  "start_time": "2024-01-15T10:30:00Z",
  "end_time": "2024-01-15T10:45:23Z",
  "podcasts_processed": 1,
  "episodes_processed": 5,
  "episodes_failed": 0,
  "processing_time_seconds": 923.45,
  "api_version": "1.1",
  "extraction_mode": "schemaless",
  "discovered_entity_types": [
    "Person", "Company", "Technology", "Product", "Event", "Location"
  ],
  "discovered_relationship_types": [
    "WORKS_AT", "CREATED", "USES", "LOCATED_IN", "PARTICIPATED_IN", "MENTIONED"
  ],
  "schema_evolution": {
    "new_types": ["AIConcept", "ProgrammingLanguage"],
    "new_properties": {
      "Person": ["expertise", "twitter_handle"],
      "Company": ["founded_year", "industry"],
      "Technology": ["version", "open_source"]
    }
  },
  "extraction_stats": {
    "entities_extracted": 347,
    "relationships_created": 512,
    "properties_added": 1893,
    "entities_resolved": 23
  }
}
```

## Schema Discovery

### Request
```http
GET /api/v1/schema/discover?include_stats=true&filter_domain=technology
```

### Response
```json
{
  "entity_types": [
    {
      "name": "Person",
      "count": 145,
      "properties": ["name", "role", "company", "expertise", "twitter_handle"],
      "first_seen": "2024-01-10T08:00:00Z",
      "last_seen": "2024-01-15T10:45:00Z"
    },
    {
      "name": "Technology",
      "count": 89,
      "properties": ["name", "type", "version", "creator", "open_source", "language"],
      "first_seen": "2024-01-10T08:05:00Z",
      "last_seen": "2024-01-15T10:43:00Z"
    },
    {
      "name": "Company",
      "count": 67,
      "properties": ["name", "industry", "founded_year", "headquarters", "website"],
      "first_seen": "2024-01-10T08:03:00Z",
      "last_seen": "2024-01-15T10:44:00Z"
    }
  ],
  "relationship_types": [
    {
      "name": "WORKS_AT",
      "count": 134,
      "source_types": ["Person"],
      "target_types": ["Company"]
    },
    {
      "name": "CREATED",
      "count": 78,
      "source_types": ["Person", "Company"],
      "target_types": ["Technology", "Product"]
    },
    {
      "name": "USES",
      "count": 256,
      "source_types": ["Company", "Person"],
      "target_types": ["Technology"]
    }
  ],
  "property_usage": {
    "name": {
      "usage_count": 301,
      "value_types": ["string"]
    },
    "founded_year": {
      "usage_count": 45,
      "value_types": ["number", "string"]
    },
    "expertise": {
      "usage_count": 89,
      "value_types": ["array"]
    }
  }
}
```

## Query Translation

### Request
```http
POST /api/v1/query/translate
Content-Type: application/json

{
  "query": "MATCH (p:Person {role: 'CEO'})-[:WORKS_AT]->(c:Company) WHERE c.industry = 'Technology' RETURN p.name, c.name",
  "target_mode": "schemaless"
}
```

### Response
```json
{
  "original_query": "MATCH (p:Person {role: 'CEO'})-[:WORKS_AT]->(c:Company) WHERE c.industry = 'Technology' RETURN p.name, c.name",
  "translated_query": "MATCH (n {_type: 'Person', role: 'CEO'})-[r {_type: 'WORKS_AT'}]->(m {_type: 'Company'}) WHERE m.industry = 'Technology' RETURN n.name, m.name",
  "warnings": [
    "Property 'role' may not exist on all Person entities in schemaless mode",
    "Consider using property existence check: WHERE exists(n.role)"
  ]
}
```

## Extraction Mode Comparison

### Request
```http
POST /api/v1/extraction/compare
Content-Type: application/json

{
  "test_content": {
    "text": "Elon Musk, CEO of Tesla and SpaceX, announced a new AI initiative. The project will use advanced machine learning techniques developed at OpenAI.",
    "speaker": "News Reporter",
    "timestamp": 120.5
  },
  "metrics": ["entity_count", "relationship_count", "property_coverage", "extraction_time"]
}
```

### Response
```json
{
  "fixed_schema_results": {
    "entity_count": 4,
    "relationship_count": 3,
    "extraction_time_ms": 234.5,
    "entities": ["Elon Musk", "Tesla", "SpaceX", "OpenAI"],
    "relationships": ["CEO_OF", "CEO_OF", "DEVELOPED_AT"]
  },
  "schemaless_results": {
    "entity_count": 6,
    "relationship_count": 5,
    "unique_types_discovered": 4,
    "extraction_time_ms": 312.8,
    "entities": ["Elon Musk", "Tesla", "SpaceX", "AI initiative", "machine learning techniques", "OpenAI"],
    "types": ["Person", "Company", "Company", "Project", "Technology", "Organization"],
    "relationships": ["CEO_OF", "CEO_OF", "ANNOUNCED", "WILL_USE", "DEVELOPED_AT"]
  },
  "comparison_metrics": {
    "entity_coverage_ratio": 1.5,
    "relationship_coverage_ratio": 1.67,
    "performance_ratio": 1.33,
    "additional_insights": [
      "Schemaless mode discovered 2 additional entities: 'AI initiative' and 'machine learning techniques'",
      "Schemaless mode created more granular relationship types",
      "Fixed schema mode was 25% faster due to predefined constraints"
    ]
  }
}
```

## Dual Extraction Mode

### Request
```http
POST /api/v1/seed
Content-Type: application/json

{
  "rss_url": "https://example.com/mixed-content-podcast.xml",
  "extraction_config": {
    "use_schemaless_extraction": true,
    "schemaless_confidence_threshold": 0.8
  },
  "processing_options": {
    "dual_extraction_mode": true,
    "max_episodes": 1
  }
}
```

### Response
```json
{
  "start_time": "2024-01-15T11:00:00Z",
  "end_time": "2024-01-15T11:05:45Z",
  "podcasts_processed": 1,
  "episodes_processed": 1,
  "episodes_failed": 0,
  "processing_time_seconds": 345.67,
  "api_version": "1.1",
  "extraction_mode": "dual",
  "fixed_schema_stats": {
    "entities": 45,
    "relationships": 67
  },
  "schemaless_stats": {
    "entities": 62,
    "relationships": 89,
    "new_types": 8
  },
  "comparison": {
    "entity_overlap": 0.73,
    "relationship_overlap": 0.75,
    "unique_to_schemaless": {
      "entities": 17,
      "types": ["Concept", "Method", "Framework"]
    }
  }
}
```

## Error Handling

### Invalid Configuration Request
```http
POST /api/v1/seed
Content-Type: application/json

{
  "rss_url": "https://example.com/podcast.xml",
  "extraction_config": {
    "schemaless_confidence_threshold": 1.5  // Invalid: > 1.0
  }
}
```

### Error Response
```json
{
  "error": "Invalid configuration",
  "details": {
    "field": "schemaless_confidence_threshold",
    "message": "Value must be between 0.0 and 1.0",
    "provided_value": 1.5
  },
  "trace_id": "abc123-def456-ghi789"
}
```