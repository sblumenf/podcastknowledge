# Multi-Podcast Support Guide

This guide explains how to use the podcast knowledge system with multiple podcasts.

## Overview

The system now supports multiple podcasts, each with:
- Its own Neo4j database in a separate Docker container
- Isolated processing and storage
- Automatic RSS feed lookup
- Simple management commands

## Adding a New Podcast

To add a new podcast to the system:

```bash
./add_podcast.sh --name "Podcast Name" --feed "https://rss-feed-url.com"
```

This command will:
1. Generate a unique podcast ID
2. Start a new Neo4j Docker container on the next available port
3. Create the database
4. Set up directory structure
5. Update the configuration file
6. Display connection information

### Example

```bash
./add_podcast.sh --name "Tech Talk Show" --feed "https://feeds.example.com/techtalk"
```

## Processing Episodes

### Process episodes for a specific podcast

```bash
# Process 5 new episodes
./run_pipeline.sh --both --podcast "Podcast Name" --max-episodes 5

# Process with verbose output
./run_pipeline.sh --both --podcast "Podcast Name" --max-episodes 5 --verbose

# Just run transcriber
./run_pipeline.sh --transcriber --podcast "Podcast Name" --max-episodes 3

# Just run seeding pipeline (process existing VTT files)
./run_pipeline.sh --seeding
```

### Key Features

- **No RSS URL needed**: The system automatically looks up the RSS feed from configuration
- **Smart episode counting**: `--max-episodes 5` always means "5 NEW episodes" regardless of how many you already have
- **Automatic port routing**: Each podcast's data goes to its own Neo4j database

## Listing Podcasts

To see all configured podcasts and their status:

```bash
./list_podcasts.sh
```

This shows:
- Podcast ID and name
- Neo4j port assignment
- Container status (Running/Stopped/Not Found)
- Number of transcribed episodes
- RSS feed URLs

## Configuration

All podcast configurations are stored in `seeding_pipeline/config/podcasts.yaml`. Each podcast has:

```yaml
- id: podcast_id
  name: Podcast Name
  rss_feed_url: https://feeds.example.com/podcast
  enabled: true
  database:
    uri: neo4j://localhost:7687
    neo4j_port: 7687
    database_name: podcast_id
```

## Directory Structure

Each podcast has its own directories:
- Transcripts: `data/transcripts/Podcast_Name/`
- Processed: `data/processed/Podcast_Name/`

## Neo4j Access

Each podcast runs in its own container:
- Container name: `neo4j-podcast_id`
- Bolt URL: `neo4j://localhost:[port]`
- Browser: `http://localhost:[port-200]`
- Default credentials: neo4j/password (or from environment variables)

## Troubleshooting

### Container not starting
- Check if the port is already in use
- Verify Docker is running
- Check container logs: `docker logs neo4j-podcast_id`

### RSS feed not found
- Verify the podcast name matches exactly (case-sensitive)
- Check `podcasts.yaml` has the `rss_feed_url` field
- Use `./list_podcasts.sh` to see configured podcasts

### Episodes not processing
- Ensure the podcast container is running: `docker ps`
- Check VTT files exist in the correct directory
- Verify Neo4j connection with browser interface

### Duplicate podcast error
- The system prevents adding the same podcast twice
- Use `./list_podcasts.sh` to see existing podcasts
- Remove from `podcasts.yaml` if needed

## Environment Variables

- `NEO4J_USER`: Neo4j username (default: neo4j)
- `NEO4J_PASSWORD`: Neo4j password (default: password)
- `GEMINI_API_KEY`: Required for knowledge extraction

## Best Practices

1. **Start small**: Process a few episodes first to verify setup
2. **Monitor resources**: Each Neo4j container uses memory
3. **Regular backups**: Back up Neo4j data directories
4. **Consistent naming**: Use clear, consistent podcast names
5. **Check logs**: Both pipeline and Neo4j logs for troubleshooting