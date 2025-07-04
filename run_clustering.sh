#!/bin/bash
# Manual clustering script for podcast knowledge pipeline
# Runs clustering on existing data in the database

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
VERBOSE=false
PODCAST_NAME=""
FORCE=false

# Print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Run clustering on existing data in the database for a specific podcast."
    echo ""
    echo "Required Options:"
    echo "  -p, --podcast NAME   Podcast name (must match name in podcasts.yaml)"
    echo ""
    echo "Optional Options:"
    echo "  -v, --verbose        Enable verbose output"
    echo "  -f, --force          Force clustering even if data seems insufficient"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --podcast \"The Mel Robbins Podcast\""
    echo "  $0 -p \"My First Million\" --verbose"
    echo "  $0 --podcast \"The Mel Robbins Podcast\" --force --verbose"
    echo ""
    echo "Note: This command clusters existing MeaningfulUnits in the database."
    echo "      It does not process new VTT files."
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--podcast)
            PODCAST_NAME="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -f|--force)
            FORCE=true
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

# Validation
if [ -z "$PODCAST_NAME" ]; then
    echo -e "${RED}Error: --podcast is required${NC}"
    echo "Use --help for usage information"
    exit 1
fi

# Function to check prerequisites
check_prerequisites() {
    echo -e "${BLUE}Checking prerequisites...${NC}"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python 3 is required but not found${NC}"
        exit 1
    fi
    
    # Check if seeding_pipeline directory exists
    if [ ! -d "$PROJECT_ROOT/seeding_pipeline" ]; then
        echo -e "${RED}seeding_pipeline directory not found${NC}"
        echo "Please run this script from the project root directory"
        exit 1
    fi
    
    # Check if cluster_existing.py exists
    if [ ! -f "$PROJECT_ROOT/seeding_pipeline/cluster_existing.py" ]; then
        echo -e "${RED}cluster_existing.py not found${NC}"
        echo "The clustering script is missing from seeding_pipeline/"
        exit 1
    fi
    
    echo -e "${GREEN}Prerequisites check complete${NC}"
}

# Function to run clustering
run_clustering() {
    echo -e "${BLUE}Running Manual Clustering...${NC}"
    echo "Podcast: $PODCAST_NAME"
    
    cd seeding_pipeline
    
    # Check if virtual environment exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    
    # Build command
    CMD="python3 cluster_existing.py --podcast \"$PODCAST_NAME\""
    
    if [ "$VERBOSE" = true ]; then
        CMD="$CMD --verbose"
    fi
    
    if [ "$FORCE" = true ]; then
        CMD="$CMD --force"
    fi
    
    # Run clustering
    echo -e "${BLUE}Executing clustering...${NC}"
    if [ "$VERBOSE" = true ]; then
        echo "Command: $CMD"
    fi
    
    eval $CMD
    CLUSTERING_EXIT=$?
    
    if [ -d "venv" ]; then
        deactivate
    fi
    
    cd ..
    
    return $CLUSTERING_EXIT
}

# Main execution
echo -e "${BLUE}=== Podcast Knowledge Manual Clustering ===${NC}"
echo "Podcast: $PODCAST_NAME"
if [ "$VERBOSE" = true ]; then
    echo "Verbose: ENABLED"
fi
if [ "$FORCE" = true ]; then
    echo "Force: ENABLED"
fi
echo ""

# Check prerequisites
check_prerequisites

# Run clustering
run_clustering
CLUSTERING_EXIT=$?

if [ $CLUSTERING_EXIT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}Clustering completed successfully!${NC}"
else
    echo ""
    echo -e "${RED}Clustering failed with exit code: $CLUSTERING_EXIT${NC}"
    exit $CLUSTERING_EXIT
fi