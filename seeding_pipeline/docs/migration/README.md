# Migration Guide: Podcast Pipeline to VTT Pipeline

This guide helps users transition from the original podcast/RSS processing pipeline to the new VTT-focused pipeline.

## Overview of Changes

The pipeline has been refactored to focus exclusively on processing VTT (WebVTT) transcript files. This change removes audio processing overhead and creates a more streamlined tool for knowledge graph construction from transcripts.

### What's Been Removed

- **Audio Processing**: All Whisper/audio transcription functionality
- **RSS Feed Processing**: Podcast feed parsing and episode downloading
- **Audio Dependencies**: PyTorch, Whisper, faster-whisper, pyannote
- **Distributed Monitoring**: Jaeger, OpenTelemetry, Prometheus, Grafana
- **Complex Deployment**: Kubernetes manifests, multi-service architecture

### What's Been Added

- **VTT Parser**: Native WebVTT file parsing with full format support
- **Batch Processing**: Efficient folder-based transcript processing
- **File-based Checkpoints**: Resume processing with content hash tracking
- **Simplified CLI**: Focused commands for VTT processing

### What's Preserved

- **Knowledge Extraction**: LLM-based entity and insight extraction
- **Neo4j Integration**: Full graph database functionality
- **Entity Resolution**: Advanced deduplication and merging
- **Embeddings**: Vector representations for RAG applications
- **API Access**: REST endpoints for integration

## Migration Steps

### 1. Export Existing Data

If you have an existing knowledge graph from the podcast pipeline:

```bash
# Export your Neo4j data
neo4j-admin dump --database=neo4j --to=backup.dump

# Or export as CSV
MATCH (n) 
RETURN n 
INTO CSV URL 'file:///export/nodes.csv'
```

### 2. Convert Audio to VTT

If you have audio files that need processing:

#### Option A: Use External Transcription Services
- [Rev.com](https://www.rev.com) - Professional transcription with VTT export
- [AssemblyAI](https://www.assemblyai.com) - API-based transcription
- [Whisper Web](https://huggingface.co/spaces/openai/whisper) - Free online tool

#### Option B: Use Whisper Locally (Separate Tool)
```bash
# Install whisper separately
pip install openai-whisper

# Transcribe to VTT
whisper audio.mp3 --output_format vtt --language en
```

#### Option C: Convert Existing Transcripts
If you have transcripts in other formats:

```python
# Convert SRT to VTT
def srt_to_vtt(srt_file, vtt_file):
    with open(srt_file, 'r') as f:
        content = f.read()
    
    # Replace commas with dots in timestamps
    content = re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})', r'\1.\2', content)
    
    # Add WEBVTT header
    vtt_content = "WEBVTT\n\n" + content
    
    with open(vtt_file, 'w') as f:
        f.write(vtt_content)
```

### 3. Update Configuration

#### Old Configuration (config.yml)
```yaml
# Old podcast-focused config
audio_provider: whisper
whisper_model: medium
diarization_enabled: true
rss_feeds:
  - url: https://example.com/feed.xml
    max_episodes: 10
```

#### New Configuration (config.yml)
```yaml
# New VTT-focused config
merge_short_segments: true
min_segment_duration: 2.0
batch_size: 10
max_workers: 4
checkpoint_enabled: true
```

### 4. Update CLI Commands

#### Old Commands
```bash
# Old: Process podcast from RSS
python cli.py seed --rss-url https://example.com/feed.xml

# Old: Process multiple podcasts
python cli.py seed --podcast-config podcasts.json
```

#### New Commands
```bash
# New: Process VTT file
python cli.py process-vtt --file transcript.vtt

# New: Process folder of VTT files
python cli.py process-vtt --folder transcripts/

# New: Batch processing with options
python cli.py process-vtt --folder transcripts/ --recursive --skip-errors
```

### 5. Update API Integration

#### Old API Calls
```python
# Old: Seed podcast endpoint
response = requests.post('/api/v1/seed_podcast', json={
    'rss_url': 'https://example.com/feed.xml',
    'max_episodes': 5
})
```

#### New API Calls
```python
# New: Process VTT endpoint
response = requests.post('/api/v1/process', json={
    'file_path': '/path/to/transcript.vtt',
    'metadata': {'source': 'meeting'}
})
```

## Common Migration Scenarios

### Scenario 1: Existing Podcast Processing Workflow

**Before**: Download podcast → Transcribe with Whisper → Extract knowledge → Build graph

**After**: Export existing transcripts as VTT → Process with new pipeline

**Steps**:
1. Use the old pipeline one last time to export transcripts
2. Convert transcripts to VTT format
3. Process VTT files with new pipeline

### Scenario 2: New Transcript Sources

**Before**: Limited to podcast RSS feeds

**After**: Process any VTT transcript (meetings, interviews, videos)

**Benefits**:
- Process YouTube transcripts directly
- Handle Zoom meeting transcripts
- Work with any captioned content

### Scenario 3: Production Deployment

**Before**: Complex multi-service deployment with monitoring

**After**: Simple Docker container with Neo4j

**Migration**:
```bash
# Old: Complex docker-compose
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up

# New: Simple deployment
docker-compose up  # Just app + Neo4j
```

## Troubleshooting

### Issue: "Module 'audio' not found"
**Solution**: Remove any custom code that imports audio modules. These have been removed.

### Issue: "No RSS feed configuration found"
**Solution**: RSS processing is removed. Convert to VTT files and use `--folder` option.

### Issue: "Checkpoint format incompatible"
**Solution**: Clear old checkpoints and start fresh:
```bash
python cli.py checkpoint-clean --all
```

### Issue: "Memory usage higher than before"
**Solution**: Adjust batch size in config:
```yaml
batch_size: 5  # Reduce from default 10
```

## Feature Comparison

| Feature | Podcast Pipeline | VTT Pipeline |
|---------|-----------------|--------------|
| Input Format | RSS/Audio | VTT Files |
| Transcription | Built-in Whisper | External/Pre-processed |
| Batch Processing | Episode-based | File-based |
| Checkpoints | Episode tracking | File hash tracking |
| Deployment | Complex (8+ services) | Simple (2 services) |
| Memory Usage | 4-8GB | 2-4GB |
| Dependencies | 50+ packages | 30+ packages |
| Setup Time | 30+ minutes | <5 minutes |

## Best Practices

1. **Organize VTT Files**: Use folder structure to organize transcripts by source/date
2. **Add Metadata**: Include metadata.json files in folders for additional context
3. **Use Checkpoints**: Enable checkpoints for large batch processing
4. **Monitor Progress**: Use `--dry-run` first to verify what will be processed
5. **Incremental Processing**: Process new files regularly rather than huge batches

## Support

If you encounter issues during migration:

1. Check the [troubleshooting section](#troubleshooting)
2. Review the [example VTT files](../examples/vtt/)
3. Open an issue on GitHub with:
   - Your migration scenario
   - Error messages
   - Sample VTT file (if applicable)

## Future Considerations

The VTT pipeline is designed for:
- **RAG Applications**: Optimized metadata and embeddings
- **Transcript Sources**: Any captioned content, not just podcasts
- **Scalability**: Handle thousands of transcript files
- **Simplicity**: Minimal dependencies and deployment complexity

The removal of audio processing allows focus on knowledge extraction quality and graph optimization for retrieval tasks.