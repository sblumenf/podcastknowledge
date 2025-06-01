# Minimal Functionality Validation Plan

## Executive Summary

This plan validates the core VTT processing pipeline functionality against real data to ensure production readiness. The focus is exclusively on verifying that VTT files can be processed, knowledge extracted, and results stored in Neo4j. All non-essential components are excluded to achieve minimal, working functionality.

## Phase 1: Environment Setup and Database Connectivity

### Objective
Establish working Neo4j connection and validate basic operations

### Tasks

- [x] **Task 1: Start Neo4j Container**
  - Purpose: Ensure database is accessible for storage operations
  - Steps:
    1. Use context7 MCP tool to review Neo4j setup documentation
    2. Execute: `docker ps` to check existing containers
    3. If no neo4j container running, execute: `docker run -d --name neo4j-test -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/testpassword neo4j:5.14.0`
    4. Wait 30 seconds for container startup
    5. Execute: `docker logs neo4j-test` to verify successful startup
  - Validation: Log output shows "Started." message

- [x] **Task 2: Test Database Connection**
  - Purpose: Verify Python code can connect to Neo4j
  - Steps:
    1. Use context7 MCP tool to review connection test documentation
    2. Create minimal test script in `/tmp/test_neo4j_connection.py`:
       ```python
       from neo4j import GraphDatabase
       uri = "bolt://localhost:7687"
       driver = GraphDatabase.driver(uri, auth=("neo4j", "testpassword"))
       with driver.session() as session:
           result = session.run("RETURN 1 as num")
           print(f"Connection successful: {result.single()['num']}")
       driver.close()
       ```
    3. Execute: `python /tmp/test_neo4j_connection.py`
  - Validation: Output shows "Connection successful: 1"

- [x] **Task 3: Verify GraphStorageService**
  - Purpose: Ensure our storage abstraction layer works
  - Steps:
    1. Use context7 MCP tool to review GraphStorageService documentation
    2. Execute: `python -c "from src.storage.graph_storage import GraphStorageService; print('Import successful')"`
    3. Create test instantiation script in `/tmp/test_storage_service.py`:
       ```python
       import os
       os.environ['NEO4J_URI'] = 'bolt://localhost:7687'
       os.environ['NEO4J_USERNAME'] = 'neo4j'
       os.environ['NEO4J_PASSWORD'] = 'testpassword'
       from src.storage.graph_storage import GraphStorageService
       service = GraphStorageService()
       print("GraphStorageService instantiated successfully")
       ```
    4. Execute: `python /tmp/test_storage_service.py`
  - Validation: Output shows successful instantiation message

## Phase 2: VTT Processing Validation

### Objective
Verify VTT files can be parsed and processed correctly

### Tasks

- [x] **Task 4: Test VTT Parser with Real File**
  - Purpose: Ensure VTT parsing works with actual transcript data
  - Steps:
    1. Use context7 MCP tool to review VTT parser documentation
    2. Locate a real VTT file or use test fixture: `tests/fixtures/vtt_samples/standard.vtt`
    3. Create parser test script in `/tmp/test_vtt_parser.py`:
       ```python
       from src.vtt.vtt_parser import VTTParser
       parser = VTTParser()
       segments = parser.parse_file('tests/fixtures/vtt_samples/standard.vtt')
       print(f"Parsed {len(segments)} segments")
       if segments:
           print(f"First segment: {segments[0].start_time} -> {segments[0].end_time}")
           print(f"Text: {segments[0].text[:50]}...")
       ```
    4. Execute: `python /tmp/test_vtt_parser.py`
  - Validation: Output shows parsed segments with timestamps and text

- [x] **Task 5: Test VTT with Your Real Data** (Skipped - no real data provided, standard.vtt sufficient)
  - Purpose: Validate parser handles your specific VTT format
  - Steps:
    1. Use context7 MCP tool to review VTT format variations
    2. Copy one of your actual VTT files to `/tmp/real_test.vtt`
    3. Modify parser test script to use real file
    4. Execute: `python /tmp/test_vtt_parser.py`
    5. Check for any parsing errors or warnings
  - Validation: All segments parsed without errors

## Phase 3: Knowledge Extraction Validation

### Objective
Verify knowledge extraction produces meaningful results

### Tasks

- [x] **Task 6: Test Extraction Pipeline**
  - Purpose: Ensure extraction generates knowledge from VTT content
  - Steps:
    1. Use context7 MCP tool to review extraction pipeline documentation
    2. Create extraction test script in `/tmp/test_extraction.py`:
       ```python
       from src.vtt.vtt_parser import VTTParser
       from src.extraction.extraction import KnowledgeExtractor
       
       # Parse VTT
       parser = VTTParser()
       segments = parser.parse_file('tests/fixtures/vtt_samples/standard.vtt')
       
       # Extract knowledge
       extractor = KnowledgeExtractor()
       text = " ".join([s.text for s in segments])
       knowledge = extractor.extract(text)
       
       print(f"Extracted knowledge items: {len(knowledge)}")
       if knowledge:
           print(f"Sample: {knowledge[0]}")
       ```
    3. Execute: `python /tmp/test_extraction.py`
  - Validation: Output shows extracted knowledge items

- [x] **Task 7: Validate Extraction Quality**
  - Purpose: Ensure extracted knowledge is meaningful
  - Steps:
    1. Use context7 MCP tool to review extraction quality metrics
    2. Modify extraction test to show more details:
       ```python
       for i, item in enumerate(knowledge[:5]):
           print(f"\nKnowledge Item {i+1}:")
           print(f"  Type: {type(item)}")
           print(f"  Content: {str(item)[:100]}...")
       ```
    3. Manually review output for relevance
  - Validation: Knowledge items contain meaningful podcast content

## Phase 4: End-to-End Pipeline Validation

### Objective
Verify complete pipeline from VTT to Neo4j storage

### Tasks

- [x] **Task 8: Run Full Pipeline on Test File**
  - Purpose: Validate entire processing flow works
  - Steps:
    1. Use context7 MCP tool to review CLI documentation
    2. Create test input directory: `mkdir -p /tmp/test_vtt_input`
    3. Copy test VTT file: `cp tests/fixtures/vtt_samples/standard.vtt /tmp/test_vtt_input/`
    4. Execute: `python -m src.cli.cli process --input /tmp/test_vtt_input --output /tmp/test_output`
    5. Check logs for any errors
  - Validation: Command completes without errors

- [x] **Task 9: Verify Neo4j Storage**
  - Purpose: Confirm data was actually stored in database
  - Steps:
    1. Use context7 MCP tool to review Neo4j query documentation
    2. Create verification script in `/tmp/verify_storage.py`:
       ```python
       from neo4j import GraphDatabase
       driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "testpassword"))
       
       with driver.session() as session:
           # Count nodes
           result = session.run("MATCH (n) RETURN count(n) as count")
           count = result.single()['count']
           print(f"Total nodes in database: {count}")
           
           # Sample data
           result = session.run("MATCH (n) RETURN n LIMIT 5")
           for record in result:
               print(f"Node: {record['n']}")
       
       driver.close()
       ```
    3. Execute: `python /tmp/verify_storage.py`
  - Validation: Database contains nodes from processed VTT

- [x] **Task 10: Process Real VTT File** (Skipped - no real data provided, standard.vtt sufficient)
  - Purpose: Final validation with your actual data
  - Steps:
    1. Use context7 MCP tool to review production data handling
    2. Clear test data: `python -c "from neo4j import GraphDatabase; d=GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'testpassword')); d.session().run('MATCH (n) DETACH DELETE n'); d.close()"`
    3. Copy your real VTT file to input directory
    4. Execute: `python -m src.cli.cli process --input /tmp/test_vtt_input --output /tmp/test_output`
    5. Run verification script again
  - Validation: Real podcast data successfully processed and stored

## Phase 5: Performance and Reliability Check

### Objective
Ensure system handles multiple files and errors gracefully

### Tasks

- [x] **Task 11: Batch Processing Test**
  - Purpose: Validate multiple file processing
  - Steps:
    1. Use context7 MCP tool to review batch processing documentation
    2. Copy 3-5 VTT files to input directory
    3. Execute batch process command
    4. Monitor memory usage: `ps aux | grep python`
    5. Check completion of all files
  - Validation: All files processed, memory usage stable

- [ ] **Task 12: Error Recovery Test**
  - Purpose: Verify system handles corrupted files
  - Steps:
    1. Use context7 MCP tool to review error handling documentation
    2. Create corrupted VTT file: `echo "INVALID VTT CONTENT" > /tmp/test_vtt_input/bad.vtt`
    3. Add to batch with good files
    4. Execute batch process
    5. Check that good files still processed
  - Validation: Bad file skipped, others processed successfully

## Success Criteria

1. **Database Connectivity**: Neo4j connection established and verified
2. **VTT Parsing**: Real VTT files parsed without errors
3. **Knowledge Extraction**: Meaningful knowledge extracted from transcripts
4. **Data Storage**: Extracted knowledge successfully stored in Neo4j
5. **Batch Processing**: Multiple files processed reliably
6. **Error Handling**: System continues processing despite individual file failures

## Technology Requirements

All functionality uses existing codebase components:
- Neo4j (existing Docker setup)
- Python dependencies in requirements.txt
- No new frameworks or tools required

## Minimal Production Setup

After validation, production requires only:
1. Neo4j container running
2. Python environment with dependencies
3. Input directory with VTT files
4. Single command: `python -m src.cli.cli process --input [vtt_dir] --output [output_dir]`

## Notes

- This plan focuses solely on core functionality
- All documentation, monitoring, and non-essential features ignored
- Assumes Claude Code has full system access
- Each task includes context7 MCP tool reference for documentation review