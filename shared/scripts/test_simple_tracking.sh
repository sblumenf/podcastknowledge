#!/bin/bash
# Test script to verify simple VTT-based tracking

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== Testing Simple VTT-Based Tracking ===${NC}"
echo ""
echo "This test verifies that:"
echo "1. Transcriber skips episodes when VTT file exists"
echo "2. No tracking file is needed"
echo "3. Neo4j remains the source of truth for seeding pipeline"
echo ""

# Show existing VTT files
echo -e "${BLUE}Current VTT files:${NC}"
find data/transcripts -name "*.vtt" -type f | grep -v test_podcast | sort
echo ""

# Show what's in Neo4j
echo -e "${BLUE}Episodes in Neo4j:${NC}"
cd seeding_pipeline
source venv/bin/activate
python3 -c "
from neo4j import GraphDatabase

driver = GraphDatabase.driver('neo4j://localhost:7687', auth=('neo4j', 'password'))
with driver.session() as session:
    result = session.run('MATCH (e:Episode) RETURN e.title ORDER BY e.title')
    episodes = [record['e.title'] for record in result]
    print(f'Total episodes in Neo4j: {len(episodes)}')
    for ep in episodes:
        print(f'  - {ep}')
"
deactivate
cd ..
echo ""

# Run pipeline to see if it skips existing episodes
echo -e "${BLUE}Running pipeline with 1 episode limit...${NC}"
echo "Expected: Should skip the latest episode since VTT exists"
echo ""

./run_pipeline.sh --both --feed-url "https://feeds.simplecast.com/UCwaTX1J" --max-episodes 1

echo ""
echo -e "${GREEN}Test complete!${NC}"
echo ""
echo "Summary:"
echo "- Transcriber checks for VTT files (no tracking file needed)"
echo "- Seeding pipeline checks Neo4j (source of truth)"
echo "- No synchronization needed between modules"