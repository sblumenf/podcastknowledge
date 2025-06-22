# Multi-Podcast Support Implementation Plan

**Status**: COMPLETED  
**Completion Date**: 2025-06-22

## Executive Summary

This plan enables the podcast knowledge system to support multiple podcasts with proper isolation and simple management. Each podcast will have its own Neo4j database in a separate Docker container for performance isolation. Users will be able to add new podcasts with a simple command, and the pipeline will automatically handle RSS feed lookup and routing to the correct database. The implementation prioritizes simplicity (KISS) while ensuring the system can scale to dozens of podcasts without performance degradation.

## Success Criteria

1. **Podcast Management**: Successfully add a new podcast with one command
2. **Database Isolation**: Each podcast runs in its own Neo4j container
3. **RSS Storage**: Pipeline uses stored RSS URLs from configuration
4. **Backward Compatibility**: Existing Mel Robbins podcast continues working
5. **Performance**: No degradation when multiple podcasts are active
6. **Automation**: All directories and databases created automatically

## Technology Requirements

No new technologies required. Uses existing:
- Docker (already in use for Neo4j)
- Bash scripting
- YAML configuration
- Neo4j database

## Phase 1: Update Existing Infrastructure

### Task 1.1: Add RSS URL to Mel Robbins Configuration
- [x] Update podcasts.yaml to include RSS URL field
- **Purpose**: Store RSS URL so users don't need to provide it repeatedly
- **Steps**:
  1. Use Read tool to examine current structure of `/home/sergeblumenfeld/podcastknowledge/seeding_pipeline/config/podcasts.yaml`
  2. Use Edit tool to add `rss_feed_url: "https://feeds.simplecast.com/UCwaTX1J"` under the mel_robbins_podcast entry
  3. Ensure proper YAML indentation matches existing structure
  4. Use context7 MCP tool to check YAML syntax documentation if needed
- **Validation**: Read file back and verify RSS URL is present and properly formatted

### Task 1.2: Add Podcast Parameter to run_pipeline.sh
- [x] Add --podcast parameter handling to the script
- **Purpose**: Allow users to specify which podcast to process
- **Steps**:
  1. Use Read tool to examine argument parsing section of `/home/sergeblumenfeld/podcastknowledge/run_pipeline.sh`
  2. Use Edit tool to add new parameter case for `-p|--podcast)` in the argument parsing switch statement
  3. Add variable `PODCAST_NAME=""` at the top with other variable declarations
  4. Set `PODCAST_NAME="$2"` in the new case and add `shift 2` to consume both flag and value
  5. Use context7 MCP tool to verify bash parameter parsing best practices
- **Validation**: Run script with --help to ensure new parameter appears in usage

### Task 1.3: Implement RSS URL Lookup from Configuration
- [x] Create function to read RSS URL from podcasts.yaml
- **Purpose**: Eliminate need to specify RSS URL on every run
- **Steps**:
  1. Use Edit tool to add new function `get_rss_url()` in run_pipeline.sh after the prerequisite check function
  2. Function should use Python one-liner to parse YAML and extract RSS URL for given podcast name
  3. Example: `python3 -c "import yaml; data=yaml.safe_load(open('seeding_pipeline/config/podcasts.yaml')); print([p['rss_feed_url'] for p in data['podcasts'] if p['name'] == '$PODCAST_NAME'][0])"`
  4. Add error handling if podcast not found or RSS URL missing
  5. Use context7 MCP tool to check Python YAML parsing documentation
- **Validation**: Test function with known podcast name and verify correct URL returned

### Task 1.4: Update Transcriber Module Call
- [x] Modify transcriber to use RSS URL from config when --podcast is provided
- **Purpose**: Use stored RSS URL instead of requiring --feed-url
- **Steps**:
  1. Use Read tool to find where run_transcriber function calls the CLI in run_pipeline.sh
  2. Add logic: if PODCAST_NAME is set and FEED_URL is empty, call get_rss_url function
  3. Store result in FEED_URL variable for use by existing code
  4. Ensure --feed-url parameter still works as override when explicitly provided
  5. Use context7 MCP tool for bash conditional syntax if needed
- **Validation**: Run pipeline with just --podcast parameter and verify it finds and uses correct RSS URL

### Task 1.5: Remove Hardcoded Podcast References
- [x] Replace all hardcoded "The Mel Robbins Podcast" references
- **Purpose**: Make pipeline work with any podcast specified by user
- **Steps**:
  1. Use Grep tool to find all instances of "The Mel Robbins Podcast" in run_pipeline.sh
  2. Replace hardcoded values with $PODCAST_NAME variable
  3. Special attention to seeding pipeline section where podcast directory is determined
  4. Update directory detection logic to use podcast name from parameter
  5. Ensure all replacements maintain proper quoting for spaces in names
- **Validation**: Run with different podcast name and verify no hardcoded references cause issues

### Task 1.6: Update Port Configuration in podcasts.yaml
- [x] Add neo4j_port field to existing configuration
- **Purpose**: Prepare for multi-container architecture
- **Steps**:
  1. Use Edit tool to add `neo4j_port: 7687` under database section of mel_robbins_podcast
  2. This documents current port usage and prepares for port-based routing
  3. Ensure indentation matches existing database configuration structure
  4. Add comment explaining this is the default Neo4j port for the first podcast
  5. Use context7 MCP tool to verify YAML structure best practices
- **Validation**: Parse YAML with Python and confirm port field is accessible

## Phase 2: Create Podcast Management System

### Task 2.1: Create add_podcast.sh Script Structure
- [x] Create new script with proper structure and permissions
- **Purpose**: Provide simple command to add new podcasts to the system
- **Steps**:
  1. Use Write tool to create `/home/sergeblumenfeld/podcastknowledge/add_podcast.sh`
  2. Add shebang `#!/bin/bash`, set -e for error handling, and color variables for output
  3. Add usage function explaining parameters: --name "Podcast Name" --feed "RSS URL"
  4. Set up argument parsing similar to run_pipeline.sh structure
  5. Use Bash tool to chmod +x the script
- **Validation**: Run script with --help and verify usage instructions display correctly

### Task 2.2: Implement Podcast ID Generation
- [x] Add function to generate valid podcast IDs from names
- **Purpose**: Create consistent, filesystem-safe identifiers
- **Steps**:
  1. Add generate_podcast_id function that takes podcast name as input
  2. Convert to lowercase, replace spaces with underscores, remove special characters
  3. Use sed or tr commands: `echo "$1" | tr '[:upper:]' '[:lower:]' | tr ' ' '_' | tr -cd '[:alnum:]_'`
  4. Ensure function handles edge cases like multiple spaces or special characters
  5. Use context7 MCP tool for bash string manipulation best practices
- **Validation**: Test with various podcast names including special characters and verify safe IDs generated

### Task 2.3: Find Next Available Port
- [x] Implement port allocation for new Neo4j containers
- **Purpose**: Automatically assign non-conflicting ports to each podcast
- **Steps**:
  1. Add find_next_port function that reads all existing ports from podcasts.yaml
  2. Parse YAML to extract all neo4j_port values using Python one-liner
  3. Find highest port number and add 1 (start at 7687 if none exist)
  4. Include check that port is not already in use using netstat or nc command
  5. Return next available port number
- **Validation**: Manually add test entries with different ports and verify function finds correct next port

### Task 2.4: Create Neo4j Container for New Podcast
- [x] Implement Docker container creation with database setup
- **Purpose**: Provide isolated Neo4j instance for each podcast
- **Steps**:
  1. Add create_neo4j_container function taking podcast_id and port as parameters
  2. Generate container name as "neo4j-${podcast_id}"
  3. Run docker command: `docker run -d --name <container_name> -p <port>:7687 -e NEO4J_AUTH=neo4j/password --restart unless-stopped neo4j:latest`
  4. Wait for container to be healthy using docker inspect in a loop (max 30 seconds)
  5. Create database using cypher-shell: `docker exec <container_name> cypher-shell -u neo4j -p password "CREATE DATABASE ${podcast_id}"`
- **Validation**: Check docker ps for running container and verify database exists via cypher-shell

### Task 2.5: Update podcasts.yaml with New Podcast
- [x] Add new podcast configuration to YAML file
- **Purpose**: Register podcast in system configuration
- **Steps**:
  1. Create function add_to_config taking all podcast details as parameters
  2. Build YAML structure for new podcast entry including id, name, RSS URL, port, database settings
  3. Use Python script to load existing YAML, append new podcast, and write back
  4. Ensure proper formatting and structure matches existing entries
  5. Include all default processing settings from existing podcast as template
- **Validation**: Read back YAML file and verify new podcast entry is properly formatted

### Task 2.6: Create Directory Structure
- [x] Set up all required directories for new podcast
- **Purpose**: Ensure pipeline has all necessary directories
- **Steps**:
  1. Add create_directories function taking podcast_name as parameter
  2. Create `/home/sergeblumenfeld/podcastknowledge/data/transcripts/<Podcast_Name>/`
  3. Create `/home/sergeblumenfeld/podcastknowledge/data/processed/<Podcast_Name>/`
  4. Create any other directories found in existing podcast structure
  5. Set proper permissions to match existing directories
- **Validation**: Use ls -la to verify directories exist with correct permissions

### Task 2.7: Integrate All Components
- [x] Wire together all functions in main script flow
- **Purpose**: Create cohesive podcast addition workflow
- **Steps**:
  1. In main section after argument parsing, validate required parameters present
  2. Call generate_podcast_id to create ID from podcast name
  3. Check if podcast already exists in YAML to prevent duplicates
  4. Call functions in sequence: find_next_port, create_neo4j_container, create_directories, add_to_config
  5. Add success message showing podcast added and ready to use
- **Validation**: Run complete script and verify all components execute successfully

## Phase 3: Pipeline Integration and Testing

### Task 3.1: Update Seeding Pipeline Database Connection
- [x] Modify pipeline to read port from configuration
- **Purpose**: Ensure pipeline connects to correct database for each podcast
- **Steps**:
  1. Use Grep tool to find where database URI is constructed in seeding pipeline
  2. Modify to read port from podcasts.yaml based on podcast name/ID
  3. Update connection string to use localhost:<port> instead of hardcoded localhost:7687
  4. Ensure both main.py and any other connection points are updated
  5. Use context7 MCP tool for Neo4j connection string documentation
- **Validation**: Run seeding pipeline with different podcast and verify connection to correct port

### Task 3.2: Test Existing Mel Robbins Podcast
- [x] Verify existing podcast continues working with updates
- **Purpose**: Ensure backward compatibility maintained
- **Steps**:
  1. Run run_pipeline.sh with --podcast "The Mel Robbins Podcast" (no --feed-url)
  2. Verify it finds RSS URL from config and processes correctly
  3. Check that files go to correct directories
  4. Verify seeding pipeline connects to original database on port 7687
  5. Run a few VTT files through complete pipeline
- **Validation**: Check Neo4j for new episodes and verify no regression in functionality

### Task 3.3: Add Test Podcast
- [x] Use add_podcast.sh to add a second podcast
- **Purpose**: Validate entire multi-podcast workflow
- **Steps**:
  1. Run `./add_podcast.sh --name "Test Podcast" --feed "https://feeds.example.com/test"`
  2. Verify Neo4j container starts on port 7688
  3. Check podcasts.yaml has new entry with correct details
  4. Verify directories created under data/transcripts and data/processed
  5. Manually verify can connect to Neo4j on new port
- **Validation**: Container running, directories exist, configuration updated correctly

### Task 3.4: Test New Podcast Processing
- [x] Process episodes for newly added podcast
- **Purpose**: Validate end-to-end multi-podcast functionality
- **Steps**:
  1. Run run_pipeline.sh with --podcast "Test Podcast" --max-episodes 1
  2. Verify transcriber finds RSS URL from config
  3. Confirm VTT file created in correct directory
  4. Verify seeding pipeline connects to port 7688
  5. Check that data goes to test podcast database, not default
- **Validation**: Episode appears in correct Neo4j database on port 7688

### Task 3.5: Document Updated Workflow
- [x] Create documentation for multi-podcast usage
- **Purpose**: Ensure users understand new capabilities
- **Steps**:
  1. Create docs/multi-podcast-guide.md with clear instructions
  2. Document how to add new podcast with examples
  3. Explain how to process episodes for specific podcasts
  4. Include troubleshooting section for common issues
  5. Add examples of checking which podcasts are configured
- **Validation**: Follow documentation as new user and verify clarity

### Task 3.6: Create Podcast Listing Utility
- [x] Add simple way to see all configured podcasts
- **Purpose**: Help users know which podcasts are available
- **Steps**:
  1. Create list_podcasts.sh script that reads podcasts.yaml
  2. Display formatted table showing name, ID, port, and RSS URL
  3. Include status check showing which Neo4j containers are running
  4. Add episode count for each podcast by checking VTT file count
  5. Use context7 MCP tool for bash text formatting best practices
- **Validation**: Run script and verify clear, useful output for all podcasts