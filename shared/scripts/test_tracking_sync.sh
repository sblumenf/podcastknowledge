#!/bin/bash
# Test script to verify tracking synchronization between transcriber and seeding pipeline

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== Testing Tracking Synchronization ===${NC}"
echo ""

# Test parameters
FEED_URL="https://feeds.megaphone.fm/melrobbins"
MAX_EPISODES="1"

# Check initial state
echo -e "${BLUE}1. Checking initial tracking state...${NC}"
if [ -f "transcriber/data/transcribed_episodes.json" ]; then
    echo "Current tracking file contents:"
    cat transcriber/data/transcribed_episodes.json | jq '.'
else
    echo "No tracking file exists yet"
fi

echo ""
echo -e "${BLUE}2. Running full pipeline (Mode 2)...${NC}"
echo "This will:"
echo "  - Transcribe 1 new episode"
echo "  - Process it through seeding pipeline"
echo "  - Update tracking file after successful seeding"
echo ""

# Run the pipeline
./run_pipeline.sh --both --feed-url "$FEED_URL" --max-episodes "$MAX_EPISODES" --verbose

echo ""
echo -e "${BLUE}3. Checking tracking file after pipeline...${NC}"
if [ -f "transcriber/data/transcribed_episodes.json" ]; then
    echo "Updated tracking file contents:"
    cat transcriber/data/transcribed_episodes.json | jq '.'
else
    echo -e "${RED}ERROR: Tracking file not found!${NC}"
fi

echo ""
echo -e "${BLUE}4. Testing duplicate prevention...${NC}"
echo "Running pipeline again with same parameters..."
echo "Expected: Should skip transcription since episode is already tracked"
echo ""

# Run again to test duplicate prevention
./run_pipeline.sh --both --feed-url "$FEED_URL" --max-episodes "$MAX_EPISODES"

echo ""
echo -e "${GREEN}Test complete!${NC}"
echo ""
echo "Summary:"
echo "- If the second run skipped transcription, tracking sync is working correctly"
echo "- If it re-transcribed the same episode, there's an issue with tracking"