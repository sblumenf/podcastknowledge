# Operations Guide

## Deployment

### Docker Deployment

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f
```

### Manual Deployment

1. Install system dependencies:
```bash
# Ubuntu/Debian
apt-get update
apt-get install python3.9 python3-pip neo4j

# macOS
brew install python@3.9 neo4j
```

2. Set up Python environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

### Required Environment Variables

```bash
# Neo4j Connection
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-secure-password

# LLM API Keys (at least one required)
GOOGLE_API_KEY=your-gemini-api-key
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Transcription (if using transcriber)
GEMINI_API_KEY_1=your-gemini-key-1
GEMINI_API_KEY_2=your-gemini-key-2  # Optional for rotation
```

### Configuration Files

#### Seeding Pipeline (`seeding_pipeline/config/config.yml`)
```yaml
# Processing
batch_size: 10
max_workers: 4

# Checkpoints
checkpoint_enabled: true
checkpoint_dir: "checkpoints/"

# Knowledge Extraction
model_name: "gemini-1.5-pro"
embedding_model: "models/text-embedding-004"
```

#### Transcriber (`transcriber/config/default.yaml`)
```yaml
# Output
output:
  default_dir: "data/transcripts"
  file_pattern: "{date}_{title}.vtt"

# API
api:
  timeout: 300
  requests_per_minute: 15
```

## Command Line Usage

### Transcriber

```bash
# Transcribe single episode
python cli.py transcribe --url "episode-url"

# Transcribe from RSS feed
python cli.py transcribe --feed-url "rss-url" --limit 10

# List episodes without transcribing
python cli.py list --feed-url "rss-url"
```

### Seeding Pipeline

```bash
# Process single file
python cli.py process-vtt --file transcript.vtt

# Batch process folder
python cli.py process-vtt --folder transcripts/ --pattern "*.vtt"

# Check checkpoint status
python cli.py checkpoint-status

# Run with dry-run
python cli.py process-vtt --folder transcripts/ --dry-run
```

## Monitoring

### Logs

- Transcriber logs: `transcriber/logs/`
- Seeding pipeline logs: `seeding_pipeline/logs/`
- Log rotation enabled at 10MB

### Health Checks

```bash
# Check API health
curl http://localhost:8000/health

# Check Neo4j connection
python -c "from src.storage.graph_storage import GraphStorage; GraphStorage().verify_connection()"
```

### Performance Metrics

- Processing speed: ~10-20 segments/second
- Memory usage: ~50MB per 100 segments
- Typical batch: 100 files in <10 minutes

## Maintenance

### Database

```bash
# Backup Neo4j
neo4j-admin database dump neo4j --to=backup.dump

# Clear checkpoints
rm -rf checkpoints/*

# Optimize Neo4j
MATCH (n) CALL db.index.fulltext.queryNodes('node_text_index', n.name) YIELD node RETURN count(node)
```

### Storage

- Transcripts: `data/transcripts/`
- Checkpoints: `checkpoints/`
- Logs: `*/logs/`

### Troubleshooting

1. **API Rate Limits**: Use multiple API keys with rotation
2. **Memory Issues**: Reduce batch_size in config
3. **Neo4j Connection**: Check firewall and connection string
4. **Checkpoint Recovery**: Use `checkpoint-clean` if corrupted

## Security

1. **API Keys**: Use environment variables, never commit
2. **Neo4j**: Change default password, use SSL in production
3. **Logs**: Automatic redaction of sensitive data
4. **Network**: Use firewall rules to restrict access