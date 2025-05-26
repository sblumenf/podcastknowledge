# Distributed Tracing Guide

This guide covers the distributed tracing implementation for the Podcast Knowledge Pipeline using OpenTelemetry and Jaeger.

## Overview

Distributed tracing provides end-to-end visibility into request flows through the system, helping to:
- Debug performance issues
- Understand system behavior
- Monitor service dependencies
- Track error propagation
- Measure operation latencies

## Architecture

### Components

1. **OpenTelemetry SDK**: Core tracing library
2. **Jaeger**: Backend for trace storage and visualization
3. **Instrumentation**: Automatic and manual trace collection
4. **Context Propagation**: Trace context across service boundaries

### Trace Flow

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│   Client    │────▶│     API      │────▶│  Pipeline  │
└─────────────┘     └──────────────┘     └────────────┘
       │                    │                    │
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────┐
│                    Jaeger Collector                  │
└─────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│                    Jaeger Storage                    │
└─────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│                     Jaeger UI                        │
└─────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

```bash
# Jaeger Configuration
JAEGER_HOST=localhost          # Jaeger agent host
JAEGER_PORT=6831              # Jaeger agent port
JAEGER_ENABLED=true           # Enable/disable tracing

# Service Configuration
TRACING_SERVICE_NAME=podcast-kg-pipeline
TRACING_SERVICE_VERSION=1.0.0
ENVIRONMENT=development

# Sampling Configuration
TRACING_SAMPLING_RATE=1.0     # 1.0 = 100% sampling

# Export Configuration
TRACING_CONSOLE_EXPORT=false  # Export to console
TRACING_BATCH_PROCESSOR=true  # Use batch processor

# Instrumentation Flags
INSTRUMENT_NEO4J=true
INSTRUMENT_REDIS=true
INSTRUMENT_REQUESTS=true
INSTRUMENT_LOGGING=true
INSTRUMENT_LANGCHAIN=true
INSTRUMENT_WHISPER=true
```

### Python Configuration

```python
from src.tracing import init_tracing
from src.tracing.config import TracingConfig

# Initialize tracing
config = TracingConfig(
    service_name="podcast-kg-pipeline",
    jaeger_host="localhost",
    jaeger_port=6831,
    sampling_rate=1.0,
)

init_tracing(
    service_name=config.service_name,
    jaeger_host=config.jaeger_host,
    jaeger_port=config.jaeger_port,
)
```

## Usage

### Basic Tracing

#### Using Decorators

```python
from src.tracing import trace_method, trace_async

@trace_method(name="my_operation")
def process_data(data):
    # Your code here
    return result

@trace_async(name="async_operation")
async def async_process(data):
    # Your async code here
    return result
```

#### Using Context Manager

```python
from src.tracing import create_span

with create_span("custom_operation") as span:
    # Your code here
    span.set_attribute("data.size", len(data))
    span.set_attribute("operation.type", "processing")
```

#### Adding Attributes

```python
from src.tracing import add_span_attributes

# Add attributes to current span
add_span_attributes({
    "episode.id": episode_id,
    "episode.title": title,
    "processing.stage": "transcription",
})
```

### Advanced Tracing

#### Business Logic Tracing

```python
from src.tracing.middleware import trace_business_operation

with trace_business_operation(
    "episode_processing",
    "knowledge_extraction",
    episode_id=episode_id
):
    # Complex business logic
    entities = extract_entities(text)
    insights = generate_insights(entities)
```

#### Database Operations

```python
from src.tracing import trace_database

@trace_database("query", "neo4j", query="MATCH (n) RETURN n")
def get_all_nodes():
    return graph.query("MATCH (n) RETURN n")
```

#### Provider Calls

```python
from src.tracing import trace_provider_call

@trace_provider_call("llm", "generate", model="gemini-pro")
def generate_summary(text):
    return llm_provider.generate(text)
```

### Context Propagation

#### Injecting Context

```python
from src.tracing import inject_context

# Prepare headers for HTTP request
headers = {}
inject_context(headers)

# Make request with trace context
response = requests.post(url, headers=headers)
```

#### Extracting Context

```python
from src.tracing import extract_context

# Extract from incoming request
trace_context = extract_context(request.headers)

# Continue trace with extracted context
with trace.use_context(trace_context):
    process_request()
```

## Instrumentation

### Automatic Instrumentation

The following libraries are automatically instrumented:

1. **Neo4j**: All queries and transactions
2. **Redis**: All cache operations
3. **Requests**: HTTP client calls
4. **LangChain**: LLM interactions
5. **Whisper**: Audio transcription

Enable with:

```python
from src.tracing.instrumentation import instrument_all
instrument_all()
```

### Manual Instrumentation

For custom operations:

```python
from src.tracing import get_tracer

tracer = get_tracer()

with tracer.start_as_current_span("custom_operation") as span:
    span.set_attribute("custom.attribute", "value")
    # Your code here
```

## Deployment

### Docker Compose

```yaml
services:
  jaeger:
    image: jaegertracing/all-in-one:1.51
    ports:
      - "16686:16686"  # UI
      - "6831:6831/udp"  # Agent
    environment:
      - COLLECTOR_OTLP_ENABLED=true
```

### Kubernetes

Apply the Kubernetes manifests:

```bash
kubectl apply -f k8s/12-jaeger.yaml
```

Access Jaeger UI:

```bash
kubectl port-forward svc/jaeger-query 16686:16686 -n podcast-kg
```

### Production Considerations

1. **Sampling**: Reduce sampling rate in production
   ```bash
   TRACING_SAMPLING_RATE=0.1  # 10% sampling
   ```

2. **Storage**: Use persistent storage for Jaeger
   ```yaml
   - SPAN_STORAGE_TYPE=elasticsearch
   - ES_SERVER_URLS=http://elasticsearch:9200
   ```

3. **Performance**: Use batch span processor
   ```bash
   TRACING_BATCH_PROCESSOR=true
   TRACING_MAX_BATCH_SIZE=512
   ```

## Viewing Traces

### Jaeger UI

1. Open http://localhost:16686
2. Select service from dropdown
3. Set time range and filters
4. Click "Find Traces"

### Trace Analysis

#### Performance Analysis
- Identify slow operations
- Find bottlenecks
- Compare operation durations

#### Error Analysis
- Track error propagation
- Find root causes
- Monitor error rates

#### Dependency Analysis
- Visualize service dependencies
- Track inter-service calls
- Monitor service health

## Best Practices

### Span Naming

Use hierarchical naming:
```
service.component.operation
```

Examples:
- `pipeline.segmentation.process_audio`
- `neo4j.query.create_node`
- `whisper.transcribe.faster_whisper`

### Attributes

Include meaningful attributes:
```python
span.set_attributes({
    # Resource identifiers
    "episode.id": "ep_123",
    "podcast.id": "pod_456",
    
    # Metrics
    "segments.count": 150,
    "processing.duration_ms": 3500,
    
    # Status
    "result.status": "success",
    "error.type": "ValidationError",
})
```

### Error Handling

Always record exceptions:
```python
try:
    process_data()
except Exception as e:
    span.record_exception(e)
    span.set_status(StatusCode.ERROR, str(e))
    raise
```

### Sampling Strategies

1. **Development**: 100% sampling
2. **Staging**: 50% sampling
3. **Production**: 1-10% sampling
4. **Errors**: Always sample errors

## Troubleshooting

### No Traces Appearing

1. Check Jaeger is running:
   ```bash
   curl http://localhost:14269/metrics
   ```

2. Verify configuration:
   ```bash
   echo $JAEGER_HOST
   echo $JAEGER_PORT
   ```

3. Check logs for errors:
   ```bash
   docker logs podcast-kg-jaeger
   ```

### Missing Spans

1. Ensure instrumentation is enabled
2. Check sampling rate
3. Verify context propagation

### Performance Impact

1. Reduce sampling rate
2. Use batch processor
3. Disable console export
4. Limit span attributes

## Examples

See `examples/tracing_example.py` for a complete working example.

## References

- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [Distributed Tracing Best Practices](https://www.jaegertracing.io/docs/latest/best-practices/)