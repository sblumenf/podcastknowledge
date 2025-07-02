# Evolution Removal and Clustering Simplification Plan

**COMPLETED: 2025-07-02**

## Executive Summary

This plan removes ALL evolution tracking functionality from the clustering system, creating a clean, KISS-compliant implementation that only maintains current clusters. The system will be reduced from ~1000+ lines of evolution code to a simple clustering pipeline that groups MeaningfulUnits based on their embeddings, stores them in Neo4j, and nothing else.

## CRITICAL IMPLEMENTATION GUIDELINES

1. **No Intuition**: Do NOT make assumptions about what is or isn't evolution-related. If unclear, ASK THE HUMAN.
2. **Stay on Course**: Before each task, review the overall goal - remove ALL evolution, temporal, and state tracking features.
3. **Human-in-the-Loop**: Questions are expected and encouraged. Better to ask than to leave evolution remnants.
4. **KISS Principle**: When in doubt, choose the simpler solution. No over-engineering.
5. **Complete Removal**: Evolution tracking was a flawed design - remove it completely, don't try to "fix" or "improve" it.

## Success Criteria

1. **Zero Evolution Code**: No imports, functions, or references to evolution tracking remain
2. **Simple Architecture**: Only 4 core files for clustering functionality
3. **Clean Neo4j Schema**: Only Cluster nodes and IN_CLUSTER relationships
4. **No Temporal Features**: No quarters, snapshots, states, or history
5. **Minimal Documentation**: Only essential clustering documentation remains

## Phase 1: File Deletion and Initial Cleanup

### Task 1.1: Delete Evolution-Related Files
- [ ] **Description**: Remove all files specifically created for evolution tracking functionality. This includes the main evolution tracker module, its test suite, and the comprehensive plan document that guided its implementation. These files contain only evolution-specific code and have no other purpose in the system.
- **Purpose**: Eliminate the core evolution tracking implementation completely
- **Steps**:
  1. Delete `src/clustering/evolution_tracker.py` (624 lines of evolution code)
  2. Delete `test_evolution_tracking.py` (514 lines of evolution tests)
  3. Delete `docs/plans/dual-mode-clustering-evolution-plan.md` (335 lines of evolution planning)
  4. Verify files are removed with `ls` commands
- **Reference**: Phase 1 focuses on removing standalone evolution files
- **Validation**: Run `find . -name "*evolution*" -type f` to ensure no evolution-named files remain
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

### Task 1.2: Remove Evolution Configuration
- [ ] **Description**: Remove the evolution detection configuration section from the clustering configuration file. This section contains thresholds and parameters specifically for tracking cluster evolution over time. The configuration file will remain but be simplified to only contain basic clustering parameters.
- **Purpose**: Eliminate evolution-specific configuration parameters
- **Steps**:
  1. Open `config/clustering_config.yaml`
  2. Remove lines 30-38 (evolution detection configuration section)
  3. Save the simplified configuration file
  4. Use context7 MCP tool to verify YAML syntax remains valid
- **Reference**: Phase 1 cleanup of configuration files
- **Validation**: Load config file in Python to ensure it parses correctly
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

### Task 1.3: Clean Up Module Exports
- [ ] **Description**: Remove EvolutionTracker from the clustering module's public exports. The __init__.py file currently imports and exports EvolutionTracker as part of the clustering module's public API. This needs to be removed to prevent any accidental imports of non-existent evolution functionality.
- **Purpose**: Prevent import errors and clean up module interface
- **Steps**:
  1. Open `src/clustering/__init__.py`
  2. Remove line 14: import of EvolutionTracker
  3. Remove EvolutionTracker from line 22 __all__ list
  4. Save the file
- **Reference**: Phase 1 module cleanup
- **Validation**: Run `python -c "from src.clustering import *"` to verify no import errors
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

## Phase 2: Simplify SemanticClusteringSystem

### Task 2.1: Remove Evolution Imports and Functions
- [ ] **Description**: Clean up the semantic clustering module by removing all evolution-related imports, utility functions, and class members. This includes the EvolutionTracker import, quarter calculation functions that were used for snapshot timing, and the evolution tracker instance variable. These elements exist solely to support evolution tracking and have no purpose in current-state clustering.
- **Purpose**: Remove evolution dependencies from the main clustering orchestrator
- **Steps**:
  1. Open `src/clustering/semantic_clustering.py`
  2. Remove line 22: `from .evolution_tracker import EvolutionTracker`
  3. Remove lines 28-93: `get_quarter()` and `get_previous_quarter()` functions
  4. Remove line 129: `self.evolution_tracker = EvolutionTracker(neo4j_service)`
  5. Use context7 MCP tool to understand the file structure before editing
- **Reference**: Phase 2 simplification of core clustering module
- **Validation**: Run pylint on the file to check for undefined references
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

### Task 2.2: Simplify run_clustering Method
- [ ] **Description**: Remove all evolution tracking steps from the main clustering pipeline method. Currently the method has 7 steps, but steps 4, 6, and 7 are purely for evolution tracking. The method also has mode parameters and complex result statistics related to evolution. This will be simplified to just the core clustering steps: extract, cluster, label, update.
- **Purpose**: Create a clean, single-purpose clustering method
- **Steps**:
  1. Remove the `mode` and `snapshot_period` parameters from method signature
  2. Remove parameter validation code (lines 162-166)
  3. Remove Step 4 (lines 212-216): evolution detection
  4. Remove Step 6 (lines 226-230): evolution event storage
  5. Remove Step 7 (lines 232-234): state saving
  6. Remove evolution statistics from results (lines 249-256)
  7. Simplify the result message to remove evolution details
  8. Use context7 MCP tool for Python method refactoring best practices
- **Reference**: Phase 2 method simplification following KISS principles
- **Validation**: Method should have only 4 steps after cleanup
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

### Task 2.3: Remove Quarterly Processing Methods
- [ ] **Description**: Delete all methods related to quarterly snapshot processing from the semantic clustering class. These methods include detect_quarter_boundaries (65 lines), process_quarter_snapshot (140 lines), and _extract_embeddings_by_date (85 lines). These methods exist solely for creating historical snapshots and have no role in current-state clustering.
- **Purpose**: Remove temporal processing capabilities entirely
- **Steps**:
  1. Delete entire `detect_quarter_boundaries()` method (lines 351-415)
  2. Delete entire `process_quarter_snapshot()` method (lines 417-556)
  3. Delete entire `_extract_embeddings_by_date()` method (lines 558-642)
  4. Verify no references to these methods remain in the file
- **Reference**: Phase 2 removal of temporal features
- **Validation**: Search for any calls to these deleted methods
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

### Task 2.4: Update Method Calls
- [ ] **Description**: Update all calls to the simplified run_clustering method throughout the codebase. Since we're removing the mode and snapshot_period parameters, any existing calls need to be updated. The primary call site is in main.py where clustering is invoked after episode processing.
- **Purpose**: Ensure all method calls match the new simplified signature
- **Steps**:
  1. Search for all calls to `run_clustering()` in the codebase
  2. Remove `mode="current"` parameter from all calls
  3. Remove any `snapshot_period` parameters if present
  4. Use context7 MCP tool to find all call sites accurately
- **Reference**: Phase 2 method signature alignment
- **Validation**: Run the pipeline to ensure no parameter errors
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

## Phase 3: Simplify Neo4jClusterUpdater

### Task 3.1: Remove Mode Parameters
- [ ] **Description**: Simplify the Neo4j updater by removing all mode-related parameters and logic. The update_graph method currently accepts mode and snapshot_period parameters that determine how clusters are created and stored. With only current-state clustering, these parameters and all conditional logic based on them can be removed.
- **Purpose**: Create a single, consistent cluster update process
- **Steps**:
  1. Open `src/clustering/neo4j_updater.py`
  2. Remove `mode` and `snapshot_period` parameters from `update_graph()` signature
  3. Remove mode-specific logging (lines 56-57)
  4. Remove all conditional logic based on mode throughout the method
  5. Use context7 MCP tool for understanding Neo4j Cypher query patterns
- **Reference**: Phase 3 Neo4j updater simplification
- **Validation**: Check that method has no mode-related conditionals
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

### Task 3.2: Simplify Cluster ID Generation
- [ ] **Description**: Replace the complex mode-based cluster ID generation with a simple, consistent approach. Currently cluster IDs are generated differently for current mode (current_cluster_X) versus snapshot mode (snapshot_PERIOD_cluster_X). With only current clustering, we can use a simple cluster_X format.
- **Purpose**: Consistent, simple cluster identification
- **Steps**:
  1. Find cluster ID generation logic (lines 84-88)
  2. Replace with simple: `cluster_node_id = f"cluster_{cluster_id}"`
  3. Remove the if/else logic for mode-specific IDs
  4. Update any documentation about cluster ID format
- **Reference**: Phase 3 ID generation simplification
- **Validation**: Create a test cluster and verify ID format
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

### Task 3.3: Remove ClusteringState Functionality
- [ ] **Description**: Remove all ClusteringState node creation and management code. ClusteringState nodes were designed to track when clustering runs occurred and maintain state for evolution comparison. Without evolution tracking, there's no need to track clustering states. This significantly simplifies the update process.
- **Purpose**: Eliminate unnecessary state tracking
- **Steps**:
  1. Remove entire `_create_clustering_state()` method (lines 148-196)
  2. Remove call to create clustering state (lines 69-73)
  3. Remove `_link_state_to_clusters()` method (lines 288-303)
  4. Remove state linking call (line 122)
  5. Remove state_id from statistics
- **Reference**: Phase 3 state removal for KISS compliance
- **Validation**: Verify no ClusteringState nodes are created
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

### Task 3.4: Simplify Cluster Properties
- [ ] **Description**: Remove temporal properties from cluster nodes and relationships. Clusters currently have type and period properties for distinguishing between current and snapshot clusters. With only current clusters, these properties are unnecessary. Similarly, the is_primary flag on relationships can be removed as all relationships will be primary.
- **Purpose**: Clean, minimal cluster data model
- **Steps**:
  1. In `_create_cluster_node()`, remove type property (line 242)
  2. Remove period property and parameter (lines 106, 247)
  3. Remove mode parameter from method signature
  4. In `_create_cluster_assignment()`, always set is_primary=true
  5. Remove mode parameter and conditional logic
- **Reference**: Phase 3 property simplification
- **Validation**: Inspect created clusters to verify clean properties
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

## Phase 4: Clean Up Main Pipeline

### Task 4.1: Remove Quarterly Processing Logic
- [ ] **Description**: Remove all quarterly boundary detection and snapshot processing logic from the main pipeline. The main.py file currently contains ~50 lines of code for detecting quarters that need snapshots and processing them. This entire section can be deleted as we only maintain current clusters.
- **Purpose**: Simplify main pipeline to focus on current clustering only
- **Steps**:
  1. Open `main.py`
  2. Locate quarterly processing section (lines 701-732)
  3. Delete entire section including quarter detection and loop
  4. Delete snapshot processing conditionals (lines 734-753)
  5. Use context7 MCP tool to verify no broken references
- **Reference**: Phase 4 main pipeline cleanup
- **Validation**: Run pipeline to ensure smooth execution
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

### Task 4.2: Update Clustering Call
- [ ] **Description**: Update the clustering system invocation in main.py to use the simplified interface. The current call includes mode="current" parameter which will no longer exist. The section heading and logging should also be updated to remove references to modes or current/snapshot distinctions.
- **Purpose**: Align main pipeline with simplified clustering interface
- **Steps**:
  1. Find clustering invocation section in main.py
  2. Update section heading to just "CLUSTERING"
  3. Remove `mode="current"` from `run_clustering()` call
  4. Simplify logging messages to remove mode references
- **Reference**: Phase 4 pipeline integration
- **Validation**: Execute pipeline and verify clustering runs
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

## Phase 5: Documentation Cleanup

### Task 5.1: Delete Evolution-Specific Documentation
- [ ] **Description**: Remove all documentation files that are specifically about evolution tracking, dual-mode clustering, or temporal features. This includes implementation guides, visual diagrams, and plans that no longer apply to the simplified system. These documents would only cause confusion as they describe features that no longer exist.
- **Purpose**: Prevent confusion from outdated documentation
- **Steps**:
  1. Delete `docs/plans/dual-mode-clustering-implementation-review.md`
  2. Delete evolution sections from `CLUSTERING_VISUAL_DIAGRAMS.md`
  3. Delete evolution sections from `CLUSTERING_FUNCTIONALITY_REPORT.md`
  4. Delete evolution sections from `docs/clustering_maintenance_guide.md`
  5. Delete evolution sections from `docs/clustering-query-patterns.md`
  6. Use context7 MCP tool to identify all evolution references in docs
- **Reference**: Phase 5 documentation cleanup
- **Validation**: Grep for "evolution" in remaining docs
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

### Task 5.2: Create Minimal Clustering Documentation
- [ ] **Description**: Create a single, concise documentation file that explains the simplified clustering system. This should cover what clustering does (groups MeaningfulUnits by semantic similarity), how to run it (call run_clustering), and what it produces (Cluster nodes with IN_CLUSTER relationships). Keep it under 100 lines following KISS principles.
- **Purpose**: Provide essential documentation without over-engineering
- **Steps**:
  1. Create `docs/clustering-simple.md`
  2. Write brief overview (what it does)
  3. Document the simple API (run_clustering method)
  4. Document Neo4j schema (Cluster node, IN_CLUSTER relationship)
  5. Add example query for finding clusters
  6. Use context7 MCP tool for documentation best practices
- **Reference**: Phase 5 minimal documentation
- **Validation**: Documentation under 100 lines and covers essentials
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

## Phase 6: Database and Testing Cleanup

### Task 6.1: Verify Database State
- [ ] **Description**: Check both Neo4j databases to confirm no evolution-related data exists. This includes searching for EVOLVED_INTO relationships, ClusteringState nodes, and Cluster nodes with type="snapshot". While we expect these to not exist since evolution was never run, we need to verify this assumption.
- **Purpose**: Ensure clean database state
- **Steps**:
  1. Connect to Neo4j database
  2. Run query: `MATCH ()-[r:EVOLVED_INTO]->() RETURN count(r)`
  3. Run query: `MATCH (cs:ClusteringState) RETURN count(cs)`
  4. Run query: `MATCH (c:Cluster) WHERE c.type = 'snapshot' RETURN count(c)`
  5. Document results for confirmation
  6. Use context7 MCP tool for Neo4j query syntax
- **Reference**: Phase 6 database verification
- **Validation**: All counts should be 0
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

### Task 6.2: Remove Evolution Test References
- [ ] **Description**: Clean up any test files that reference evolution tracking functionality. The main end-to-end test file contains evolution assertions that will fail once evolution is removed. These sections need to be deleted or commented out to maintain a passing test suite.
- **Purpose**: Maintain working test suite
- **Steps**:
  1. Open `final_end_to_end_test.py`
  2. Remove/comment line 143 that tests evolution tracking
  3. Search for EVOLVED_INTO relationship tests and remove them
  4. Remove any assertions about ClusteringState nodes
  5. Use context7 MCP tool to understand test structure
- **Reference**: Phase 6 test cleanup
- **Validation**: Run tests to ensure they pass
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

### Task 6.3: Update Error Handling
- [ ] **Description**: Simplify error handling in the clustering system by removing evolution-specific error cases. The current error handling includes cases for state saving failures and evolution detection errors that will no longer be possible. The retry logic can remain but be simplified for just clustering and Neo4j updates.
- **Purpose**: Clean, relevant error handling only
- **Steps**:
  1. Review error handling in semantic_clustering.py
  2. Remove any evolution-specific error messages
  3. Simplify retry logic annotations
  4. Update error logging to reflect simplified pipeline
- **Reference**: Phase 6 error handling cleanup
- **Validation**: Trigger an error to test handling
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

## Phase 7: Final Verification and Cleanup

### Task 7.1: Run Complete Pipeline Test
- [ ] **Description**: Execute the complete pipeline with the simplified clustering system to ensure everything works correctly. This includes processing a test episode, generating embeddings, running clustering, and verifying that clusters are created in Neo4j without any evolution tracking artifacts.
- **Purpose**: Validate the complete simplified system
- **Steps**:
  1. Run `./run_pipeline.sh --both --podcast "Test" --max-episodes 1`
  2. Monitor logs for any evolution-related errors
  3. Verify clusters are created in Neo4j
  4. Check that no ClusteringState nodes were created
  5. Query for clusters and verify structure
- **Reference**: Phase 7 system validation
- **Validation**: Pipeline completes successfully with clusters created
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

### Task 7.2: Code Metrics Verification
- [ ] **Description**: Measure the code reduction achieved by removing evolution tracking. This includes counting lines of code removed, number of methods deleted, and complexity reduction. Document these metrics to demonstrate the successful simplification following KISS principles.
- **Purpose**: Quantify the simplification achieved
- **Steps**:
  1. Count lines removed from each modified file
  2. Count number of methods/functions removed
  3. Count number of files deleted
  4. Document before/after complexity metrics
  5. Create summary of simplification achieved
- **Reference**: Phase 7 metrics collection
- **Validation**: Document shows significant reduction
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

### Task 7.3: Final Code Review
- [ ] **Description**: Perform a final review of all modified files to ensure no evolution remnants remain. This includes searching for any remaining references to evolution, snapshot, quarter, temporal, or state tracking concepts. Any found references should be evaluated and removed if they're related to the eliminated functionality.
- **Purpose**: Ensure complete removal of evolution concepts
- **Steps**:
  1. Grep for "evolution" across entire codebase
  2. Grep for "snapshot" in clustering modules
  3. Grep for "quarter" in Python files
  4. Grep for "temporal" in clustering context
  5. Review and clean any remaining references
  6. Use context7 MCP tool for comprehensive search patterns
- **Reference**: Phase 7 final verification
- **Validation**: No evolution-related terms in production code
- **IMPORTANT REMINDERS**:
  - Review the overall plan goal: Create a KISS-compliant clustering system with NO evolution tracking, NO temporal features, NO state management
  - Do NOT use intuition - if unclear about whether something is evolution-related, ASK THE HUMAN
  - Human-in-the-loop is expected - ask questions rather than making assumptions

## Technology Requirements

This plan requires NO new technologies. It only removes existing code and simplifies the current system.

## Risk Mitigation

1. **Backup Current Code**: Create a git branch before starting removal
2. **Test After Each Phase**: Run clustering after each phase to catch issues early
3. **Document Removal**: Keep a log of what was removed for future reference
4. **Gradual Removal**: Remove in phases rather than all at once

## Expected Outcome

After implementation:
- Clustering codebase reduced by ~60% (removing ~1000+ lines)
- No evolution tracking, quarterly processing, or state management
- Simple, maintainable clustering that just works
- Clean Neo4j schema with only essential nodes and relationships
- Minimal documentation that accurately reflects the system

The result will be a KISS-compliant clustering system that does one thing well: groups MeaningfulUnits into semantic clusters.