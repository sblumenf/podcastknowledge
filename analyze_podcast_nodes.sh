#!/bin/bash

# analyze_podcast_nodes.sh - Analyze Neo4j node types for a podcast database

set -e

# Function to display usage
usage() {
    echo "Usage: $0 --podcast PODCAST_NAME [OPTIONS]"
    echo ""
    echo "Analyze Neo4j node types and properties for a specific podcast database."
    echo ""
    echo "Required:"
    echo "  -p, --podcast NAME    Name or ID of the podcast to analyze"
    echo ""
    echo "Options:"
    echo "  -o, --output FILE     Output file path (default: neo4j_node_analysis_<podcast>.json)"
    echo "  -f, --format FORMAT   Output format: json or summary (default: json)"
    echo "  -v, --verbose         Verbose output during analysis"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --podcast \"The Mel Robbins Podcast\""
    echo "  $0 -p mel_robbins_podcast -v"
    echo "  $0 --podcast \"My First Million\" --format summary"
    echo "  $0 -p \"Tech Talk\" -o tech_talk_analysis.json -v"
    exit 1
}

# Check if no arguments provided
if [ $# -eq 0 ]; then
    usage
fi

# Forward all arguments to the Python script
cd seeding_pipeline
python3 scripts/analysis/analyze_neo4j_nodes.py "$@"