#!/bin/bash
# Script to add a new podcast to the knowledge system
# Creates Neo4j container, database, directories, and updates configuration

set -e  # Exit on error

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
PODCAST_NAME=""
FEED_URL=""

# Print usage
usage() {
    echo "Usage: $0 --name \"Podcast Name\" --feed \"RSS Feed URL\""
    echo ""
    echo "This script adds a new podcast to the knowledge system by:"
    echo "  - Creating a new Neo4j Docker container"
    echo "  - Setting up the database"
    echo "  - Creating necessary directories"
    echo "  - Updating the configuration"
    echo ""
    echo "Options:"
    echo "  -n, --name NAME     Name of the podcast (required)"
    echo "  -f, --feed URL      RSS feed URL for the podcast (required)"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 --name \"Tech Talk Show\" --feed \"https://feeds.example.com/techtalk\""
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--name)
            PODCAST_NAME="$2"
            shift 2
            ;;
        -f|--feed)
            FEED_URL="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            ;;
    esac
done

# Validate parameters
if [ -z "$PODCAST_NAME" ]; then
    echo -e "${RED}Error: Podcast name is required${NC}"
    usage
fi

if [ -z "$FEED_URL" ]; then
    echo -e "${RED}Error: RSS feed URL is required${NC}"
    usage
fi

echo -e "${BLUE}=== Adding New Podcast ===${NC}"
echo "Name: $PODCAST_NAME"
echo "Feed: $FEED_URL"
echo ""

# Function to generate podcast ID from name
generate_podcast_id() {
    local name="$1"
    # Convert to lowercase, replace spaces with underscores, remove special characters
    local id=$(echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '_' | tr -cd '[:alnum:]_')
    # Remove multiple underscores and trim
    id=$(echo "$id" | sed 's/__*/_/g' | sed 's/^_//;s/_$//')
    echo "$id"
}

# Generate podcast ID
PODCAST_ID=$(generate_podcast_id "$PODCAST_NAME")
echo "Generated ID: $PODCAST_ID"

# Check if podcast already exists
existing_check=$(python3 -c "
import yaml
import sys

try:
    with open('seeding_pipeline/config/podcasts.yaml', 'r') as f:
        data = yaml.safe_load(f)
    
    for podcast in data.get('podcasts', []):
        if podcast.get('id') == '$PODCAST_ID' or podcast.get('name') == '$PODCAST_NAME':
            print('EXISTS')
            sys.exit(0)
    print('OK')
except Exception:
    print('OK')
" 2>/dev/null)

if [ "$existing_check" = "EXISTS" ]; then
    echo -e "${RED}Error: Podcast already exists in configuration${NC}"
    exit 1
fi

# Function to find next available port
find_next_port() {
    local start_port=7687
    local max_port=7700  # Reasonable upper limit
    
    # Get all used ports from podcasts.yaml
    local used_ports=$(python3 -c "
import yaml
import sys

try:
    with open('seeding_pipeline/config/podcasts.yaml', 'r') as f:
        data = yaml.safe_load(f)
    
    ports = []
    for podcast in data.get('podcasts', []):
        db_config = podcast.get('database', {})
        port = db_config.get('neo4j_port')
        if port:
            ports.append(int(port))
    
    if ports:
        print(' '.join(map(str, sorted(ports))))
except Exception as e:
    sys.exit(1)
" 2>/dev/null || echo "")
    
    # Find next available port
    local port=$start_port
    while [ $port -le $max_port ]; do
        # Check if port is in used list
        if ! echo "$used_ports" | grep -q -w "$port"; then
            # Also check if port is actually available on system
            if ! nc -z localhost $port 2>/dev/null; then
                echo $port
                return 0
            fi
        fi
        port=$((port + 1))
    done
    
    echo -e "${RED}Error: No available ports found in range $start_port-$max_port${NC}" >&2
    return 1
}

# Find next available port
NEO4J_PORT=$(find_next_port)
if [ $? -ne 0 ]; then
    exit 1
fi
echo "Will use port: $NEO4J_PORT"

# Function to create Neo4j container and database
create_neo4j_container() {
    local podcast_id="$1"
    local port="$2"
    local container_name="neo4j-${podcast_id}"
    
    echo ""
    echo -e "${BLUE}Creating Neo4j container...${NC}"
    
    # Get Neo4j credentials from environment or use defaults
    local neo4j_user="${NEO4J_USER:-neo4j}"
    local neo4j_password="${NEO4J_PASSWORD:-password}"
    
    # Create Docker container
    echo "Starting container: $container_name on port $port"
    docker run -d \
        --name "$container_name" \
        -p "$((port - 200)):7474" \
        -p "${port}:7687" \
        -e NEO4J_AUTH="${neo4j_user}/${neo4j_password}" \
        -e NEO4J_ACCEPT_LICENSE_AGREEMENT=yes \
        --restart unless-stopped \
        neo4j:latest
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to create Docker container${NC}"
        return 1
    fi
    
    # Wait for container to be healthy
    echo "Waiting for Neo4j to start..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker exec "$container_name" cypher-shell -u "$neo4j_user" -p "$neo4j_password" "RETURN 1" >/dev/null 2>&1; then
            echo -e "${GREEN}Neo4j is ready${NC}"
            break
        fi
        sleep 2
        attempt=$((attempt + 1))
        echo -n "."
    done
    echo ""
    
    if [ $attempt -eq $max_attempts ]; then
        echo -e "${RED}Error: Neo4j failed to start within 60 seconds${NC}"
        return 1
    fi
    
    # Create database for the podcast
    echo "Creating database: $podcast_id"
    docker exec "$container_name" cypher-shell -u "$neo4j_user" -p "$neo4j_password" "CREATE DATABASE $podcast_id" 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Database created successfully${NC}"
    else
        echo -e "${YELLOW}Note: Database may already exist or creation not supported in this Neo4j version${NC}"
    fi
    
    return 0
}

# Create Neo4j container
create_neo4j_container "$PODCAST_ID" "$NEO4J_PORT"
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to create Neo4j container${NC}"
    exit 1
fi

# Function to add podcast to configuration
add_to_config() {
    local podcast_id="$1"
    local podcast_name="$2"
    local feed_url="$3"
    local port="$4"
    
    echo ""
    echo -e "${BLUE}Updating configuration...${NC}"
    
    # Use Python to add the new podcast to YAML
    python3 -c "
import yaml
import sys

try:
    # Read existing config
    with open('seeding_pipeline/config/podcasts.yaml', 'r') as f:
        data = yaml.safe_load(f)
    
    # Check if podcast already exists
    for podcast in data.get('podcasts', []):
        if podcast.get('id') == '$podcast_id':
            print('ERROR: Podcast ID already exists in configuration', file=sys.stderr)
            sys.exit(1)
    
    # Create new podcast entry
    new_podcast = {
        'id': '$podcast_id',
        'name': '$podcast_name',
        'rss_feed_url': '$feed_url',
        'enabled': True,
        'database': {
            'uri': f'neo4j://localhost:$port',
            'neo4j_port': $port,
            'database_name': '$podcast_id'
        },
        'processing': {
            'batch_size': 10,
            'max_retries': 3,
            'enable_flow_analysis': True,
            'enable_graph_enhancement': True,
            'use_large_context': True
        },
        'metadata': {
            'language': 'en'
        }
    }
    
    # Add to podcasts list
    if 'podcasts' not in data:
        data['podcasts'] = []
    data['podcasts'].append(new_podcast)
    
    # Write back to file
    with open('seeding_pipeline/config/podcasts.yaml', 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    print('Configuration updated successfully')
except Exception as e:
    print(f'ERROR: Failed to update configuration: {e}', file=sys.stderr)
    sys.exit(1)
"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Configuration updated${NC}"
        return 0
    else
        return 1
    fi
}

# Update configuration
add_to_config "$PODCAST_ID" "$PODCAST_NAME" "$FEED_URL" "$NEO4J_PORT"
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to update configuration${NC}"
    # Note: Container is already created, manual cleanup may be needed
    exit 1
fi

# Function to create directory structure
create_directories() {
    local podcast_name="$1"
    
    echo ""
    echo -e "${BLUE}Creating directories...${NC}"
    
    # Convert podcast name to directory format (spaces to underscores)
    local dir_name=$(echo "$podcast_name" | tr ' ' '_')
    
    # Create directories
    local base_dir="/home/sergeblumenfeld/podcastknowledge/data"
    local dirs=(
        "$base_dir/transcripts/$dir_name"
        "$base_dir/processed/$dir_name"
    )
    
    for dir in "${dirs[@]}"; do
        if mkdir -p "$dir"; then
            echo "Created: $dir"
        else
            echo -e "${RED}Failed to create: $dir${NC}"
            return 1
        fi
    done
    
    # Set permissions to match existing directories
    for dir in "${dirs[@]}"; do
        chmod 755 "$dir"
    done
    
    echo -e "${GREEN}Directories created${NC}"
    return 0
}

# Create directories
create_directories "$PODCAST_NAME"
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to create directories${NC}"
    exit 1
fi

# Success summary
echo ""
echo -e "${GREEN}=== Podcast Successfully Added ===${NC}"
echo ""
echo "Podcast Name: $PODCAST_NAME"
echo "Podcast ID: $PODCAST_ID"
echo "RSS Feed: $FEED_URL"
echo "Neo4j Port: $NEO4J_PORT"
echo "Container: neo4j-${PODCAST_ID}"
echo ""
echo "To process episodes, run:"
echo "  ./run_pipeline.sh --both --podcast \"$PODCAST_NAME\" --max-episodes 5"
echo ""
echo "To check Neo4j:"
echo "  Browser: http://localhost:$((NEO4J_PORT - 200))"
echo "  Bolt: neo4j://localhost:${NEO4J_PORT}"
echo ""