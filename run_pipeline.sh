#!/bin/bash
# Unified run script for podcast knowledge pipeline
# Supports running transcriber, seeding pipeline, or both

set -e  # Exit on error

# Save project root directory
PROJECT_ROOT="$PWD"

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
MODE="both"
VERBOSE=false
DATA_DIR="/home/sergeblumenfeld/podcastknowledge/data"
FEED_URL=""
MAX_EPISODES="1"
PODCAST_NAME=""

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -t, --transcriber    Run transcriber only"
    echo "  -s, --seeding        Run seeding pipeline only"
    echo "  -b, --both           Run both transcriber and seeding (default)"
    echo "  -p, --podcast NAME   Podcast name (uses RSS URL from config)"
    echo "  -f, --feed-url URL   RSS feed URL (overrides config)"
    echo "  -e, --max-episodes N Maximum episodes to process from feed (default: 1)"
    echo "  -d, --data-dir DIR   Set data directory (default: $DATA_DIR)"
    echo "  -v, --verbose        Enable verbose output"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --both --podcast \"The Mel Robbins Podcast\" --max-episodes 3"
    echo "  $0 --transcriber --feed-url \"https://rss-feed.com\" --max-episodes 5"
    echo "  $0 --seeding         # Process existing VTT files only"
    echo "  $0 -v -b -p \"The Mel Robbins Podcast\" -e 2  # Verbose mode, 2 episodes"
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--transcriber)
            MODE="transcriber"
            shift
            ;;
        -s|--seeding)
            MODE="seeding"
            shift
            ;;
        -b|--both)
            MODE="both"
            shift
            ;;
        -p|--podcast)
            PODCAST_NAME="$2"
            shift 2
            ;;
        -f|--feed-url)
            FEED_URL="$2"
            shift 2
            ;;
        -e|--max-episodes)
            MAX_EPISODES="$2"
            shift 2
            ;;
        -d|--data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
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

# Validation function
validate_parameters() {
    # Check if feed URL or podcast name is required
    if [[ "$MODE" != "seeding" && -z "$FEED_URL" && -z "$PODCAST_NAME" ]]; then
        echo -e "${RED}Error: Either --feed-url or --podcast is required when running transcriber${NC}"
        echo "Use --help for usage information"
        exit 1
    fi
    
    # Validate max episodes is a positive number
    if ! [[ "$MAX_EPISODES" =~ ^[1-9][0-9]*$ ]]; then
        echo -e "${RED}Error: --max-episodes must be a positive number${NC}"
        exit 1
    fi
}

# Function to get RSS URL from configuration
get_rss_url() {
    local podcast_name="$1"
    local rss_url
    
    # Use Python to parse YAML and extract RSS URL
    local config_file="$PROJECT_ROOT/seeding_pipeline/config/podcasts.yaml"
    
    rss_url=$(python3 -c "
import yaml
import sys

try:
    with open('$config_file', 'r') as f:
        data = yaml.safe_load(f)
    
    for podcast in data.get('podcasts', []):
        if podcast.get('name') == '$podcast_name':
            rss_url = podcast.get('rss_feed_url')
            if rss_url:
                print(rss_url)
                sys.exit(0)
            else:
                print('ERROR: No RSS URL found for podcast', file=sys.stderr)
                sys.exit(1)
    
    print('ERROR: Podcast not found in configuration', file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'ERROR: Failed to read configuration: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1)
    
    if [ $? -eq 0 ]; then
        echo "$rss_url"
        return 0
    else
        echo -e "${RED}$rss_url${NC}" >&2
        return 1
    fi
}

# Function to check prerequisites
check_prerequisites() {
    echo -e "${BLUE}Checking prerequisites...${NC}"
    
    # Check if data directory exists
    if [ ! -d "$DATA_DIR" ]; then
        echo -e "${YELLOW}Data directory not found. Creating: $DATA_DIR${NC}"
        mkdir -p "$DATA_DIR/transcripts" "$DATA_DIR/processed" "$DATA_DIR/logs"
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python 3 is required but not found${NC}"
        exit 1
    fi
    
    # Check Neo4j
    if ! nc -z localhost 7687 2>/dev/null; then
        echo -e "${YELLOW}Warning: Neo4j appears to be offline (port 7687)${NC}"
        echo "Seeding pipeline may fail if Neo4j is required"
    fi
    
    echo -e "${GREEN}Prerequisites check complete${NC}"
}

# Function to run transcriber
run_transcriber() {
    echo -e "${BLUE}Running Transcriber Module...${NC}"
    
    TRANSCRIBER_DIR="$PWD/transcriber"
    cd transcriber
    
    # Check if virtual environment exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    
    # Set environment variables
    export TRANSCRIPT_OUTPUT_DIR="$DATA_DIR/transcripts"
    export PODCAST_DATA_DIR="$DATA_DIR"
    
    # Set pipeline mode for smart detection
    if [ "$MODE" = "both" ]; then
        export PODCAST_PIPELINE_MODE="combined"
    else
        export PODCAST_PIPELINE_MODE="independent"
    fi
    
    # Get RSS URL from config if podcast name is provided but no feed URL
    if [ -n "$PODCAST_NAME" ] && [ -z "$FEED_URL" ]; then
        if [ "$VERBOSE" = true ]; then
            echo "Looking up RSS URL for podcast: $PODCAST_NAME"
        fi
        FEED_URL=$(get_rss_url "$PODCAST_NAME")
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to get RSS URL for podcast: $PODCAST_NAME${NC}"
            exit 1
        fi
        if [ "$VERBOSE" = true ]; then
            echo "Found RSS URL: $FEED_URL"
        fi
    fi
    
    # Pass max episodes directly to transcriber
    # --max-episodes specifies the total number of episodes to check from the feed
    ACTUAL_MAX_EPISODES=$MAX_EPISODES
    
    if [ "$VERBOSE" = true ]; then
        echo "Output directory: $TRANSCRIPT_OUTPUT_DIR"
        echo "Pipeline mode: $PODCAST_PIPELINE_MODE"
        echo "Feed URL: $FEED_URL"
        echo "Max episodes to process: $ACTUAL_MAX_EPISODES"
        python3 -m src.cli -v transcribe --feed-url "$FEED_URL" --max-episodes "$ACTUAL_MAX_EPISODES"
    else
        python3 -m src.cli transcribe --feed-url "$FEED_URL" --max-episodes "$ACTUAL_MAX_EPISODES"
    fi
    
    if [ -d "venv" ]; then
        deactivate
    fi
    
    cd ..
    echo -e "${GREEN}Transcriber completed${NC}"
}

# Function to run seeding pipeline
run_seeding() {
    echo -e "${BLUE}Running Seeding Pipeline...${NC}"
    
    cd seeding_pipeline
    
    # Check if virtual environment exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    
    # Set environment variables
    export VTT_INPUT_DIR="$DATA_DIR/transcripts"
    export PROCESSED_DIR="$DATA_DIR/processed"
    export PODCAST_DATA_DIR="$DATA_DIR"
    
    # Set pipeline mode for consistency
    if [ "$MODE" = "both" ]; then
        export PODCAST_PIPELINE_MODE="combined"
    else
        export PODCAST_PIPELINE_MODE="independent"
    fi
    
    # Determine podcast directory
    if [ -n "$PODCAST_NAME" ]; then
        # Convert podcast name to directory format (spaces to underscores)
        PODCAST_DIR_NAME=$(echo "$PODCAST_NAME" | tr ' ' '_')
        PODCAST_DIR="$VTT_INPUT_DIR/$PODCAST_DIR_NAME"
    else
        # If no podcast specified, process all VTT files
        PODCAST_DIR="$VTT_INPUT_DIR"
    fi
    
    # Count VTT files in the podcast directory
    VTT_COUNT=$(find "$PODCAST_DIR" -name "*.vtt" -type f 2>/dev/null | wc -l)
    echo "Found $VTT_COUNT VTT files in $PODCAST_DIR"
    
    if [ $VTT_COUNT -eq 0 ]; then
        echo -e "${YELLOW}No VTT files found in $PODCAST_DIR${NC}"
        if [ -d "venv" ]; then
            deactivate
        fi
        cd ..
        return 0  # Return success code even if no files
    fi
    
    # Process the directory - let seeding pipeline handle duplicate detection
    echo "Starting seeding pipeline..."
    
    # Use podcast name if provided, otherwise try to detect from directory
    if [ -z "$PODCAST_NAME" ]; then
        # Try to detect podcast name from directory being processed
        if [ "$PODCAST_DIR" != "$VTT_INPUT_DIR" ]; then
            PODCAST_NAME=$(basename "$PODCAST_DIR" | tr '_' ' ')
        else
            PODCAST_NAME="Unknown Podcast"
        fi
    fi
    echo "Using podcast: $PODCAST_NAME"
    
    if [ "$VERBOSE" = true ]; then
        echo "Running seeding pipeline in verbose mode..."
        echo "Input directory: $PODCAST_DIR"
        echo "Podcast: $PODCAST_NAME"
        python3 main.py "$PODCAST_DIR" --directory --podcast "$PODCAST_NAME" --verbose
    else
        python3 main.py "$PODCAST_DIR" --directory --podcast "$PODCAST_NAME"
    fi
    
    SEEDING_EXIT_CODE=$?
    
    if [ -d "venv" ]; then
        deactivate
    fi
    
    cd ..
    
    # Return the exit code from seeding
    return $SEEDING_EXIT_CODE
}

# Main execution
echo -e "${BLUE}=== Podcast Knowledge Pipeline ===${NC}"
echo "Mode: $MODE"
echo "Data directory: $DATA_DIR"
if [ "$VERBOSE" = true ]; then
    echo "Verbose: ENABLED"
fi
echo ""

# Validate parameters
validate_parameters

# Check prerequisites
check_prerequisites

# Run based on mode
case $MODE in
    transcriber)
        run_transcriber
        ;;
    seeding)
        run_seeding
        ;;
    both)
        run_transcriber
        TRANSCRIBER_EXIT=$?
        echo ""
        
        if [ $TRANSCRIBER_EXIT -eq 0 ]; then
            run_seeding
            SEEDING_EXIT=$?
            
            # Both succeeded - no tracking file needed
        else
            echo -e "${RED}Transcriber failed, skipping seeding pipeline${NC}"
        fi
        ;;
esac

echo ""
echo -e "${GREEN}Pipeline execution completed!${NC}"

# Show summary
echo ""
echo -e "${BLUE}Summary:${NC}"
echo "- Transcripts directory: $DATA_DIR/transcripts"
echo "- Processed directory: $DATA_DIR/processed"
echo "- Logs directory: $DATA_DIR/logs"

# File statistics are shown in the batch processing summary above