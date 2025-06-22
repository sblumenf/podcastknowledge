#!/bin/bash
# Script to list all configured podcasts and their status

set -e  # Exit on error

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if Docker container is running
check_container_status() {
    local container_name="$1"
    if docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
        echo -e "${GREEN}Running${NC}"
    else
        if docker ps -a --format "table {{.Names}}" | grep -q "^${container_name}$"; then
            echo -e "${YELLOW}Stopped${NC}"
        else
            echo -e "${RED}Not Found${NC}"
        fi
    fi
}

# Function to count VTT files
count_vtt_files() {
    local podcast_name="$1"
    local dir_name=$(echo "$podcast_name" | tr ' ' '_')
    local vtt_count=$(find "data/transcripts/$dir_name" -name "*.vtt" -type f 2>/dev/null | wc -l)
    echo "$vtt_count"
}

echo -e "${BLUE}=== Configured Podcasts ===${NC}"
echo ""

# Use Python to parse YAML and display podcasts
python3 -c "
import yaml
import sys
import subprocess

try:
    with open('seeding_pipeline/config/podcasts.yaml', 'r') as f:
        data = yaml.safe_load(f)
    
    # Print header
    print(f\"{'ID':<25} {'Name':<35} {'Port':<8} {'Status':<12} {'Episodes':<10}\")
    print('-' * 90)
    
    for podcast in data.get('podcasts', []):
        podcast_id = podcast.get('id', 'unknown')
        name = podcast.get('name', 'Unknown')
        db_config = podcast.get('database', {})
        port = db_config.get('neo4j_port', 'N/A')
        
        # Container name
        container_name = f'neo4j-{podcast_id}'
        
        # Print podcast info (status and episode count will be added by shell)
        print(f\"{podcast_id:<25} {name:<35} {port:<8}\", end='')
        sys.stdout.flush()
        
        # Return to shell for dynamic checks
        print(f'|CONTAINER:{container_name}|NAME:{name}')
        
except Exception as e:
    print(f'Error reading configuration: {e}', file=sys.stderr)
    sys.exit(1)
" | while IFS='|' read -r base_info container_info name_info; do
    if [[ "$container_info" == CONTAINER:* ]] && [[ "$name_info" == NAME:* ]]; then
        container_name="${container_info#CONTAINER:}"
        podcast_name="${name_info#NAME:}"
        
        # Get container status
        status=$(check_container_status "$container_name")
        
        # Get episode count
        episode_count=$(count_vtt_files "$podcast_name")
        
        # Print the complete line
        printf "%s %s %10s\n" "$base_info" "$status" "$episode_count"
    else
        echo "$base_info"
    fi
done

echo ""
echo -e "${BLUE}RSS Feed URLs:${NC}"
python3 -c "
import yaml

try:
    with open('seeding_pipeline/config/podcasts.yaml', 'r') as f:
        data = yaml.safe_load(f)
    
    for podcast in data.get('podcasts', []):
        name = podcast.get('name', 'Unknown')
        rss_url = podcast.get('rss_feed_url', 'Not configured')
        print(f'{name}: {rss_url}')
        
except Exception as e:
    print(f'Error reading configuration: {e}')
"
echo ""