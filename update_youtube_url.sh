#!/bin/bash
# Script to update YouTube URL for an episode in Neo4j

# Check if required parameters are provided
if [ $# -lt 3 ]; then
    echo "Usage: $0 <podcast_name> <episode_title_fragment> <youtube_url>"
    echo "Example: $0 \"My First Million\" \"local side hustles\" \"https://www.youtube.com/watch?v=abc123\""
    exit 1
fi

PODCAST_NAME="$1"
TITLE_FRAGMENT="$2"
YOUTUBE_URL="$3"

# Get Neo4j credentials from environment or use defaults
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"

# Look up the port for this podcast
PORT=$(python3 -c "
import yaml
with open('seeding_pipeline/config/podcasts.yaml', 'r') as f:
    config = yaml.safe_load(f)
for p in config['podcasts']:
    if p['name'] == '$PODCAST_NAME':
        print(p['database']['neo4j_port'])
        break
")

if [ -z "$PORT" ]; then
    echo "Error: Podcast '$PODCAST_NAME' not found in configuration"
    exit 1
fi

echo "Connecting to Neo4j on port $PORT..."

# First, find the episode
echo "Searching for episode containing: $TITLE_FRAGMENT"
RESULT=$(docker exec neo4j-$(echo "$PODCAST_NAME" | tr ' ' '_' | tr '[:upper:]' '[:lower:]') \
    cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
    "MATCH (e:Episode) WHERE e.title CONTAINS '$TITLE_FRAGMENT' RETURN e.title, e.youtube_url" \
    2>&1)

if [[ $RESULT == *"no changes, no records"* ]] || [[ $RESULT == *"0 rows"* ]]; then
    echo "No episode found with title containing: $TITLE_FRAGMENT"
    exit 1
fi

echo "Found episode. Current details:"
echo "$RESULT"

# Update the YouTube URL
echo ""
echo "Updating YouTube URL to: $YOUTUBE_URL"
UPDATE_RESULT=$(docker exec neo4j-$(echo "$PODCAST_NAME" | tr ' ' '_' | tr '[:upper:]' '[:lower:]') \
    cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
    "MATCH (e:Episode) WHERE e.title CONTAINS '$TITLE_FRAGMENT' SET e.youtube_url = '$YOUTUBE_URL' RETURN e.title, e.youtube_url" \
    2>&1)

echo ""
echo "Update complete. New details:"
echo "$UPDATE_RESULT"