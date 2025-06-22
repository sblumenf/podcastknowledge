#!/bin/bash
# Unified run script for podcast knowledge pipeline
# Supports running transcriber, seeding pipeline, or both

set -e  # Exit on error

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

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -t, --transcriber    Run transcriber only"
    echo "  -s, --seeding        Run seeding pipeline only"
    echo "  -b, --both           Run both transcriber and seeding (default)"
    echo "  -f, --feed-url URL   RSS feed URL (required for transcriber)"
    echo "  -e, --max-episodes N Maximum episodes to process (default: 1)"
    echo "  -d, --data-dir DIR   Set data directory (default: $DATA_DIR)"
    echo "  -v, --verbose        Enable verbose output"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --both --feed-url \"https://rss-feed.com\" --max-episodes 3"
    echo "  $0 --transcriber --feed-url \"https://rss-feed.com\" --max-episodes 5"
    echo "  $0 --seeding         # Process existing VTT files only"
    echo "  $0 -v -b -f \"https://rss-feed.com\" -e 2  # Verbose mode, 2 episodes"
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
    # Check if feed URL is required
    if [[ "$MODE" != "seeding" && -z "$FEED_URL" ]]; then
        echo -e "${RED}Error: --feed-url is required when running transcriber${NC}"
        echo "Use --help for usage information"
        exit 1
    fi
    
    # Validate max episodes is a positive number
    if ! [[ "$MAX_EPISODES" =~ ^[1-9][0-9]*$ ]]; then
        echo -e "${RED}Error: --max-episodes must be a positive number${NC}"
        exit 1
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
    
    if [ "$VERBOSE" = true ]; then
        echo "Output directory: $TRANSCRIPT_OUTPUT_DIR"
        echo "Pipeline mode: $PODCAST_PIPELINE_MODE"
        echo "Feed URL: $FEED_URL"
        echo "Max episodes: $MAX_EPISODES"
        python3 -m src.cli transcribe --feed-url "$FEED_URL" --max-episodes "$MAX_EPISODES" --verbose
    else
        python3 -m src.cli transcribe --feed-url "$FEED_URL" --max-episodes "$MAX_EPISODES"
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
    
    # Count VTT files
    VTT_COUNT=$(find "$VTT_INPUT_DIR" -name "*.vtt" -type f 2>/dev/null | wc -l)
    echo "Found $VTT_COUNT VTT files to process"
    
    if [ $VTT_COUNT -eq 0 ]; then
        echo -e "${YELLOW}No VTT files found in $VTT_INPUT_DIR${NC}"
        if [ -d "venv" ]; then
            deactivate
        fi
        cd ..
        return
    fi
    
    if [ "$VERBOSE" = true ]; then
        python3 -m src.cli.cli process-vtt --folder "$VTT_INPUT_DIR" --recursive --parallel -v
    else
        python3 -m src.cli.cli process-vtt --folder "$VTT_INPUT_DIR" --recursive --parallel
    fi
    
    if [ -d "venv" ]; then
        deactivate
    fi
    
    cd ..
    echo -e "${GREEN}Seeding pipeline completed${NC}"
}

# Main execution
echo -e "${BLUE}=== Podcast Knowledge Pipeline ===${NC}"
echo "Mode: $MODE"
echo "Data directory: $DATA_DIR"
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
        echo ""
        run_seeding
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

# Count files
TRANSCRIPT_COUNT=$(find "$DATA_DIR/transcripts" -name "*.vtt" -type f 2>/dev/null | wc -l)
PROCESSED_COUNT=$(find "$DATA_DIR/processed" -name "*.vtt" -type f 2>/dev/null | wc -l)

echo ""
echo "Files:"
echo "- Transcripts waiting: $TRANSCRIPT_COUNT"
echo "- Files processed: $PROCESSED_COUNT"