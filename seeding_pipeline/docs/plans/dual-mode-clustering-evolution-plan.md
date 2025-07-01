# Dual-Mode Clustering with Episode-Based Evolution Plan

## Executive Summary

This plan implements a dual-mode clustering system that maintains current clusters for user visualization while creating quarterly snapshots for tracking evolution based on episode dates. The system will automatically detect quarter boundaries during episode processing and track how clusters evolve over time. All existing week-based evolution code will be removed and replaced with this simpler, date-based approach.

## Success Criteria

1. Current clusters update after every episode processing batch
2. Quarterly snapshots are created automatically when crossing quarter boundaries
3. Evolution is tracked between adjacent quarters based on episode dates
4. All week-based evolution code is removed
5. Episode dates are extracted from VTT filenames consistently
6. System handles single episodes, small batches, and large batches correctly

## Technology Requirements

- **No new technologies required**
- Uses existing: Neo4j, HDBSCAN, Python
- Uses existing LLM service for cluster labeling

## Phase 1: Remove Existing Week-Based Evolution System

**Phase Overview**: Before starting any task in this phase, review the entire dual-mode clustering plan to understand how removing week-based evolution fits into the larger goal of implementing episode-date-based evolution tracking. This phase lays the groundwork by cleaning out the old system to make room for the new quarter-based approach.

### Task 1.1: Remove week-based code from semantic_clustering.py
- [ ] **Remove the current_week parameter from run_clustering() method and all references to week-based dating throughout the clustering system. This involves deleting the default week calculation using datetime.now().strftime("%Y-W%W") and removing week from all cluster IDs and storage. The purpose is to completely eliminate the misleading week-based system that tracks when clustering runs rather than when episodes were published. Remember: Follow KISS principles - no over-engineering, no stub code, just remove what needs to be removed.**
- Purpose: Eliminate week-based evolution tracking
- Steps:
  1. Open src/clustering/semantic_clustering.py
  2. Remove current_week parameter from run_clustering() method signature
  3. Remove line that sets current_week = datetime.now().strftime("%Y-W%W")
  4. Remove week from cluster ID generation
  5. Update all method calls to remove current_week parameter
  6. Consult context7 MCP tool for Python refactoring best practices
- Reference: Phase 1 focuses on removing all week-based evolution logic as part of the overall dual-mode clustering plan
- Validation: run_clustering() method has no week parameters or week-based logic

### Task 1.2: Update evolution_tracker.py to remove week dependencies
- [ ] **Remove all week-based comparison logic from evolution_tracker.py including the current_week parameters and week-based state lookups. This involves modifying detect_evolution, save_state, and store_evolution_events methods to work without week identifiers. The goal is to prepare the evolution tracker for date-based comparisons instead of clustering-run-based comparisons. Remember: Follow KISS principles - no over-engineering, no stub code, just clean removal of week logic.**
- Purpose: Prepare evolution tracker for date-based tracking
- Steps:
  1. Open src/clustering/evolution_tracker.py
  2. Remove current_week parameter from all methods
  3. Remove week-based state ID generation
  4. Update ClusteringState queries to not use week
  5. Consult context7 MCP tool for evolution tracking best practices
  6. Consult context7 MCP tool for Python method signature changes
- Reference: Phase 1 groundwork for new evolution system as part of the overall dual-mode clustering plan
- Validation: No week parameters or week logic remains in evolution tracker

### Task 1.3: Clean up Neo4j schema references
- [ ] **Update neo4j_updater.py to remove all week-based properties from cluster and state nodes including created_week and week fields. This involves modifying create_cluster_node and create_clustering_state methods to use date-based identifiers instead. The purpose is to ensure the database schema aligns with episode-date-based tracking rather than clustering-run dates. Remember: Follow KISS principles - no over-engineering, no stub code, simple property removal only.**
- Purpose: Remove week properties from database nodes
- Steps:
  1. Open src/clustering/neo4j_updater.py
  2. Remove created_week from cluster node creation
  3. Remove week from ClusteringState node creation
  4. Update cluster ID format to remove week prefix
  5. Test that nodes are created without week properties
  6. Consult context7 MCP tool for Neo4j schema best practices
- Reference: Phase 1 database schema cleanup as part of the overall dual-mode clustering plan
- Validation: Neo4j nodes created without any week-related properties

## Phase 2: Add Episode Date Extraction

**Phase Overview**: Before starting any task in this phase, review the entire dual-mode clustering plan to understand how date extraction enables the quarter-based snapshot system. This phase adds the foundation for tracking evolution by episode dates rather than processing dates.

### Task 2.1: Enhance filename parsing to extract dates
- [ ] **Create a new function extract_episode_date() in main.py that extracts the YYYY-MM-DD date from VTT filenames using regex pattern matching for robustness. This function will parse filenames like "2023-04-15_Episode_Title.vtt" and return the date string. The purpose is to establish a consistent way to get episode dates from filenames since the current code discards this information. Remember: Follow KISS principles - no over-engineering, no stub code, simple regex extraction only.**
- Purpose: Extract episode dates from VTT filenames
- Steps:
  1. Open main.py
  2. Create extract_episode_date(filename: str) -> Optional[str] function
  3. Use regex pattern r'^\d{4}-\d{2}-\d{2}' to match date at start
  4. Return date string if found, None otherwise
  5. Add unit tests for various filename formats
  6. Consult context7 MCP tool for Python date parsing best practices
  7. Consult context7 MCP tool for regex pattern best practices
- Reference: Phase 2 establishes date extraction foundation as part of the overall dual-mode clustering plan
- Validation: Function correctly extracts dates from standard VTT filenames

### Task 2.2: Update episode processing to store dates
- [ ] **Modify the process_vtt_file() function in main.py to extract and pass episode dates to the pipeline so they are stored in Episode nodes. This involves calling extract_episode_date() and including the date in episode metadata. The goal is to ensure every Episode node has a published_date populated from the filename when VTT metadata doesn't provide it. Remember: Follow KISS principles - no over-engineering, no stub code, minimal changes to existing flow.**
- Purpose: Ensure all episodes have dates in database
- Steps:
  1. In process_vtt_file(), call extract_episode_date() on VTT filename
  2. Add extracted date to episode_metadata as published_date
  3. Only use filename date if VTT metadata doesn't have a date
  4. Pass updated metadata to pipeline
  5. Verify Episode nodes have published_date populated
  6. Consult context7 MCP tool for data pipeline best practices
- Reference: Phase 2 ensures date availability for clustering as part of the overall dual-mode clustering plan
- Validation: All processed episodes have published_date in Neo4j

### Task 2.3: Create quarter calculation utility
- [ ] **Create a simple get_quarter(date_str: str) -> str function that converts dates to quarter strings like "2023Q1". This function will parse the date and return the appropriate quarter based on month ranges (Q1: Jan-Mar, Q2: Apr-Jun, Q3: Jul-Sep, Q4: Oct-Dec). The purpose is to have a consistent way to determine which quarter an episode belongs to for snapshot creation. Remember: Follow KISS principles - no over-engineering, no stub code, straightforward date to quarter conversion.**
- Purpose: Standardize quarter determination from dates
- Steps:
  1. Create get_quarter() function in semantic_clustering.py
  2. Parse date string to extract year and month
  3. Calculate quarter: Q1 (1-3), Q2 (4-6), Q3 (7-9), Q4 (10-12)
  4. Return format "YYYYQN" (e.g., "2023Q2")
  5. Handle invalid dates gracefully
  6. Consult context7 MCP tool for date parsing utilities
- Reference: Phase 2 utilities support quarter-based snapshots as part of the overall dual-mode clustering plan
- Validation: Function returns correct quarters for various dates

## Phase 3: Implement Dual-Mode Clustering

**Phase Overview**: Before starting any task in this phase, review the entire dual-mode clustering plan to understand how the two modes (current and snapshot) work together. This phase implements the core functionality where current clusters serve users and snapshots track evolution.

### Task 3.1: Add clustering mode parameter
- [ ] **Add a mode parameter to run_clustering() that accepts "current" or "snapshot" to control clustering behavior. This parameter will determine whether the clustering creates/updates the current user-facing clusters or creates a historical snapshot. The purpose is to enable the dual-mode system where current clusters serve users and snapshots track evolution. Remember: Follow KISS principles - no over-engineering, no stub code, simple parameter addition only.**
- Purpose: Enable dual-mode clustering operation
- Steps:
  1. Add mode: str = "current" parameter to run_clustering()
  2. Add snapshot_period: Optional[str] = None parameter
  3. Update method documentation to explain modes
  4. Pass mode through to neo4j_updater methods
  5. Consult context7 MCP tool for function parameter design patterns
  6. Consult context7 MCP tool for Python type hints
- Reference: Phase 3 implements core dual-mode functionality as part of the overall dual-mode clustering plan
- Validation: run_clustering() accepts and processes mode parameter

### Task 3.2: Implement current mode clustering
- [ ] **Implement the "current" mode logic that updates user-facing clusters by replacing any existing current clusters with new ones. This involves marking clusters with type="current" and ensuring only one set of current clusters exists at a time. The purpose is to maintain an always-up-to-date view of all episodes clustered together for the application UI. Remember: Follow KISS principles - no over-engineering, no stub code, reuse existing clustering logic.**
- Purpose: Maintain up-to-date clusters for users
- Steps:
  1. In run_clustering(), check if mode == "current"
  2. Set cluster ID prefix to "current_"
  3. Archive existing current clusters before creating new ones
  4. Mark new clusters with type="current" property
  5. Ensure IN_CLUSTER relationships use is_primary=true
  6. Consult context7 MCP tool for Neo4j node property patterns
- Reference: Phase 3 current mode serves visualization needs as part of the overall dual-mode clustering plan
- Validation: Current clusters update correctly and old ones are archived

### Task 3.3: Implement snapshot mode clustering
- [ ] **Implement the "snapshot" mode logic that creates historical cluster snapshots tagged with specific quarters. This involves creating clusters with IDs like "snapshot_2023Q1_cluster_5" and marking them with type="snapshot" and period="2023Q1". The purpose is to preserve cluster state at quarter boundaries for evolution tracking. Remember: Follow KISS principles - no over-engineering, no stub code, straightforward snapshot creation.**
- Purpose: Create historical snapshots for evolution tracking
- Steps:
  1. In run_clustering(), check if mode == "snapshot"
  2. Use snapshot_period in cluster ID: f"snapshot_{period}_cluster_{id}"
  3. Mark clusters with type="snapshot" and period properties
  4. Create IN_CLUSTER relationships with is_primary=false
  5. Add snapshot_period to ClusteringState node
  6. Consult context7 MCP tool for temporal data modeling
- Reference: Phase 3 snapshot mode enables evolution analysis as part of the overall dual-mode clustering plan
- Validation: Snapshot clusters created with correct period tagging

## Phase 4: Implement Quarter Boundary Detection

**Phase Overview**: Before starting any task in this phase, review the entire dual-mode clustering plan to understand how automatic quarter boundary detection triggers snapshot creation. This phase makes the system intelligent about when to create historical snapshots.

### Task 4.1: Create quarter boundary detection logic
- [ ] **Create detect_quarter_boundaries() function that analyzes episodes in the database to find which quarters need snapshots created. This function queries all episodes, extracts their quarters, compares to existing snapshots, and returns a list of quarters that need processing. The purpose is to automatically identify when the system has crossed quarter boundaries during episode processing. Remember: Follow KISS principles - no over-engineering, no stub code, simple set comparison logic.**
- Purpose: Automatically detect when to create snapshots
- Steps:
  1. Create detect_quarter_boundaries() in semantic_clustering.py
  2. Query all Episode nodes and their published_date values
  3. Calculate quarters for all episodes using get_quarter()
  4. Query existing snapshot ClusteringStates to see which quarters exist
  5. Return list of quarters that have episodes but no snapshots
  6. Consult context7 MCP tool for Neo4j query optimization
  7. Consult context7 MCP tool for set operations in Python
- Reference: Phase 4 enables automatic snapshot creation as part of the overall dual-mode clustering plan
- Validation: Function correctly identifies missing quarter snapshots

### Task 4.2: Implement snapshot creation for quarters
- [ ] **Create process_quarter_snapshot(quarter: str) function that creates a snapshot for a specific quarter by filtering episodes and running clustering. This function queries only episodes up through the quarter end date, extracts their embeddings, runs clustering, and saves as a snapshot. The purpose is to create point-in-time snapshots that represent cluster state at each quarter boundary. Remember: Follow KISS principles - no over-engineering, no stub code, reuse existing clustering with date filter.**
- Purpose: Create snapshots for specific quarters
- Steps:
  1. Create process_quarter_snapshot() function
  2. Calculate quarter end date from quarter string
  3. Modify embeddings extraction to filter by date
  4. Call run_clustering(mode="snapshot", snapshot_period=quarter)
  5. Return snapshot creation result
  6. Consult context7 MCP tool for date range filtering
- Reference: Phase 4 snapshot creation logic as part of the overall dual-mode clustering plan
- Validation: Snapshots contain only episodes up through quarter end

### Task 4.3: Integrate boundary detection into main flow
- [ ] **Modify the main clustering trigger in main.py to detect and process quarter boundaries after episode processing completes. This involves calling detect_quarter_boundaries() and creating snapshots for any newly completed quarters before updating current clusters. The purpose is to automatically maintain historical snapshots as episodes are processed in any order. Remember: Follow KISS principles - no over-engineering, no stub code, minimal changes to existing flow.**
- Purpose: Automatically create snapshots during processing
- Steps:
  1. In main.py after episode processing succeeds
  2. Call detect_quarter_boundaries() to find new quarters
  3. For each new quarter, call process_quarter_snapshot()
  4. After all snapshots, run regular current clustering
  5. Add logging for snapshot creation
  6. Consult context7 MCP tool for pipeline integration patterns
- Reference: Phase 4 integrates snapshots into main pipeline as part of the overall dual-mode clustering plan
- Validation: Processing episodes triggers appropriate snapshots

## Phase 5: Implement Episode-Based Evolution Tracking

**Phase Overview**: Before starting any task in this phase, review the entire dual-mode clustering plan to understand how evolution tracking between quarters provides real temporal insights. This phase modifies evolution detection to work with quarterly snapshots instead of clustering runs.

**Critical Understanding**: Evolution tracking compares clusters between adjacent quarters to show how topics actually evolved over time. For example:
- 2023Q1 snapshot has cluster "Personal Development" with 45 units
- 2023Q2 snapshot has clusters "Morning Routines" (25 units) and "Goal Setting" (30 units)
- Evolution detection discovers that 60% of "Personal Development" units moved to "Morning Routines" and 40% to "Goal Setting"
- This creates a SPLIT evolution: "Personal Development" → "Morning Routines" + "Goal Setting"

The system tracks three types of evolution:
1. **SPLIT**: One cluster becomes multiple (when >20% goes to each new cluster)
2. **MERGE**: Multiple clusters become one (when multiple old clusters contribute >20% each)
3. **CONTINUATION**: Cluster remains stable (when >80% stays in same cluster)

**Key Design Decisions**:
- Evolution is ONLY tracked between adjacent quarters (Q1→Q2, Q2→Q3, never Q1→Q3)
- Evolution relationships connect snapshot clusters, NOT current clusters
- Each quarter comparison is independent - Q2→Q3 doesn't know about Q1→Q2
- The same meaningful units exist in multiple snapshots (they don't move, just cluster differently)

### Task 5.1: Modify evolution detection for snapshots
- [ ] **Update detect_evolution() to compare snapshot clusters between adjacent quarters instead of clustering runs. This involves loading the previous quarter's snapshot, building transition matrices based on meaningful unit membership changes, and detecting splits/merges/continuations between quarters. The purpose is to track real temporal evolution of topics based on episode dates rather than processing dates. Remember: Follow KISS principles - no over-engineering, no stub code, reuse existing evolution logic.**
- Purpose: Track evolution between quarterly snapshots
- Steps:
  1. Modify detect_evolution() signature to accept from_period: str and to_period: str (e.g., "2023Q1", "2023Q2")
  2. Query Neo4j for snapshot clusters from both periods:
     ```cypher
     MATCH (c:Cluster {type: "snapshot", period: $period})
     MATCH (c)<-[:IN_CLUSTER {is_primary: false}]-(m:MeaningfulUnit)
     RETURN c.id as cluster_id, collect(m.id) as unit_ids
     ```
  3. Build transition matrix showing unit movement between periods:
     - For each unit in from_period, find which cluster it belongs to in to_period
     - Count transitions: old_cluster_X → new_cluster_Y
  4. Apply existing thresholds to detect evolution types:
     - SPLIT: One old cluster has >20% going to multiple new clusters
     - MERGE: Multiple old clusters each contribute >20% to one new cluster
     - CONTINUATION: >80% of old cluster goes to one new cluster
  5. Return list of evolution events with metadata (type, from_cluster, to_cluster(s), proportion)
  6. Consult context7 MCP tool for transition matrix algorithms
  7. Consult context7 MCP tool for Neo4j query optimization for large datasets
- Reference: Phase 5 implements true temporal evolution as part of the overall dual-mode clustering plan
- Validation: Evolution correctly detected between quarter snapshots with proper proportions

### Task 5.2: Create evolution comparison trigger
- [ ] **Add logic to automatically compare adjacent quarter snapshots after creating a new snapshot. This involves checking if a previous quarter snapshot exists and calling evolution detection to compare them. The purpose is to build evolution history automatically as snapshots are created, showing how clusters changed quarter by quarter. Remember: Follow KISS principles - no over-engineering, no stub code, simple quarter sequence logic.**
- Purpose: Automatically track evolution between quarters
- Steps:
  1. In process_quarter_snapshot(), after successfully creating snapshot for quarter (e.g., "2023Q2")
  2. Calculate previous quarter using simple logic:
     ```python
     def get_previous_quarter(quarter: str) -> str:
         year = int(quarter[:4])
         q_num = int(quarter[5])
         if q_num == 1:
             return f"{year-1}Q4"
         else:
             return f"{year}Q{q_num-1}"
     ```
  3. Check if previous quarter snapshot exists in Neo4j:
     ```cypher
     MATCH (cs:ClusteringState {type: "snapshot", period: $previous_quarter})
     RETURN count(cs) > 0 as exists
     ```
  4. If previous snapshot exists:
     - Call evolution_events = detect_evolution(from_period=previous_quarter, to_period=current_quarter)
     - Store evolution relationships using existing store_evolution_events()
     - Log evolution summary: "Detected X splits, Y merges, Z continuations between quarters"
  5. If no previous snapshot, log: "No previous quarter snapshot found, skipping evolution detection"
  6. Consult context7 MCP tool for graph relationship patterns
  7. Consult context7 MCP tool for quarter arithmetic edge cases
- Reference: Phase 5 automatic evolution tracking as part of the overall dual-mode clustering plan
- Validation: Evolution relationships created between adjacent quarters only

### Task 5.3: Update evolution storage
- [ ] **Modify store_evolution_events() to use quarter periods instead of weeks in evolution relationships. This involves updating EVOLVED_INTO relationship properties to include from_period and to_period quarter identifiers. The purpose is to make evolution relationships clearly indicate which time periods they connect rather than arbitrary clustering run weeks. Remember: Follow KISS principles - no over-engineering, no stub code, minimal property changes.**
- Purpose: Store evolution with quarter-based metadata
- Steps:
  1. Update store_evolution_events() parameters
  2. Replace week properties with from_period and to_period
  3. Update relationship creation queries
  4. Ensure evolution type (split/merge/continuation) is preserved
  5. Add quarter information to logging
  6. Consult context7 MCP tool for Neo4j relationship properties
- Reference: Phase 5 evolution storage improvements as part of the overall dual-mode clustering plan
- Validation: Evolution relationships have correct quarter metadata

## Phase 6: Testing and Cleanup

**Phase Overview**: Before starting any task in this phase, review the entire dual-mode clustering plan to understand what needs to be tested and cleaned up. This phase ensures the system works correctly and removes obsolete code.

### Task 6.1: Create comprehensive test suite
- [ ] **Create test_dual_mode_clustering.py with tests covering single episode processing, small batch processing, large batch spanning multiple quarters, and evolution detection between quarters. Tests should verify current clusters update correctly, snapshots are created at boundaries, and evolution is tracked accurately. The purpose is to ensure the system handles all processing scenarios correctly. Remember: Follow KISS principles - no over-engineering, no stub code, focused test cases only.**
- Purpose: Ensure system works correctly in all scenarios
- Steps:
  1. Create test_dual_mode_clustering.py
  2. Test single episode processing (no snapshot)
  3. Test crossing quarter boundary (snapshot created)
  4. Test large batch with multiple quarters
  5. Test evolution detection between quarters
  6. Test edge cases (partial quarters, missing dates)
  7. Consult context7 MCP tool for Python testing best practices
- Reference: Phase 6 validates entire implementation as part of the overall dual-mode clustering plan
- Validation: All tests pass with various processing patterns

### Task 6.2: Remove old test files
- [ ] **Delete test files related to week-based evolution including any tests that check for week parameters or week-based clustering behavior. This cleanup ensures test suites don't test removed functionality and prevents confusion. The purpose is to maintain a clean codebase with only relevant tests. Remember: Follow KISS principles - no over-engineering, no stub code, complete removal only.**
- Purpose: Clean up obsolete test files
- Steps:
  1. Identify test files with week-based evolution tests
  2. Remove tests for current_week parameter
  3. Remove tests for week-based evolution
  4. Update remaining tests to use new approach
  5. Verify test suite still provides good coverage
  6. Consult context7 MCP tool for test cleanup patterns
- Reference: Phase 6 cleanup of obsolete code as part of the overall dual-mode clustering plan
- Validation: No week-based tests remain in codebase

### Task 6.3: Update documentation
- [ ] **Update clustering documentation to explain the dual-mode system, quarterly snapshots, and episode-based evolution tracking. This includes updating user guides, maintenance guides, and code comments to reflect the new approach. The purpose is to ensure future maintainers understand how the system tracks evolution based on episode dates rather than clustering run dates. Remember: Follow KISS principles - no over-engineering, no stub code, clear and concise documentation.**
- Purpose: Document new evolution tracking approach
- Steps:
  1. Update clustering_user_guide.md with dual-mode explanation
  2. Update maintenance guide with snapshot management
  3. Update code docstrings in modified files
  4. Add examples of evolution tracking by quarter
  5. Consult context7 MCP tool for documentation best practices
  6. Consult context7 MCP tool for markdown formatting
- Reference: Phase 6 documentation updates as part of the overall dual-mode clustering plan
- Validation: Documentation accurately reflects new system

## Implementation Notes

- Follow KISS principles throughout - no over-engineering
- Reuse existing code where possible
- Each phase builds on the previous one
- Test after each phase to ensure stability
- Current clusters serve users, snapshots serve analysis
- Evolution only tracked between adjacent quarters