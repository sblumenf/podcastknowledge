# Hub-and-Spoke Cluster Visualization Implementation Plan

## Executive Summary

This plan transforms the existing Sigma.js cluster network visualization in GraphPanel.tsx into an interactive hub-and-spoke design. Users will click clusters to reveal their most representative MeaningfulUnits as spokes arranged in a circle, colored by sentiment. The implementation maintains the current cluster network view while adding drill-down capability to explore cluster contents without overwhelming the visualization.

## Phase 1: Backend API Enhancement

### Task 1.1: Create MeaningfulUnit Endpoint
- [x] Create a new FastAPI endpoint `/api/podcasts/{podcast_id}/clusters/{cluster_id}/meaningful-units` that returns the top K MeaningfulUnits for a cluster ranked by centroid distance. This endpoint will query Neo4j to find units belonging to a cluster, calculate cosine similarity between each unit's embedding and the cluster's centroid vector, and return the top K units sorted by similarity. The endpoint must include sentiment data (polarity, score, energy_level) for each unit and support a configurable K parameter (default 10).
  - Purpose: Provides frontend with representative cluster content for spoke visualization
  - Steps:
    1. Add endpoint to `ui/backend/api/routes/knowledge_graph.py`
    2. Implement Neo4j query using cypher to match cluster-contains-meaningfulunit relationships
    3. Calculate cosine similarity using embedding vectors
    4. Include sentiment data in response
    5. Test with curl/httpie to verify response format
  - Reference: Aligns with Phase 1 backend preparation for hub-and-spoke interaction
  - Validation: Endpoint returns K units with embeddings, summaries, and sentiment data

### Task 1.2: Add Centroid Vector to Cluster Response
- [x] Modify the existing `/api/podcasts/{podcast_id}/knowledge-graph` endpoint to include centroid vectors in cluster data. This requires updating the Neo4j query to fetch the centroid property from Cluster nodes and including it in the GraphCluster response model. The centroid is essential for client-side calculations if needed and for understanding cluster representation.
  - Purpose: Enables potential client-side centroid distance calculations
  - Steps:
    1. Update GraphCluster model in `ui/backend/api/models/graph.py` to include optional centroid field
    2. Modify Neo4j query in knowledge_graph endpoint to return c.centroid
    3. Ensure centroid vector is properly serialized in JSON response
    4. Update any existing tests to handle new field
  - Reference: Supports Phase 2 frontend visualization requirements
  - Validation: API response includes centroid arrays for each cluster

### Task 1.3: Implement Efficient Connection Strength Calculation
- [x] Update the edge weight calculation in the knowledge graph endpoint to use logarithmic scaling for shared entity counts. This prevents visual distortion when some cluster pairs share hundreds of entities while others share just a few. The implementation will apply log10 scaling to entity counts and normalize weights to a 0-1 range for consistent visualization.
  - Purpose: Provides visually balanced edge weights despite large entity count variations
  - Steps:
    1. Modify edge weight calculation in `/api/podcasts/{podcast_id}/knowledge-graph`
    2. Apply formula: weight = log10(shared_count + 1) / log10(max_possible + 1)
    3. Ensure weights are normalized between 0 and 1
    4. Test with clusters having varying shared entity counts
  - Reference: Implements logarithmic scaling discussed in plan requirements
  - Validation: Edge weights show reasonable variation without extreme outliers

## Phase 2: Frontend Visualization Updates

### Task 2.1: Add MeaningfulUnit Data Types
- [x] Create TypeScript interfaces for MeaningfulUnit data structures including sentiment properties in the frontend codebase. This involves defining interfaces for MeaningfulUnit with properties like id, text, summary, embedding, sentiment (with polarity, score, energy_level), and any other fields returned by the API. These types ensure type safety throughout the frontend implementation.
  - Purpose: Provides type-safe data structures for spoke visualization
  - Steps:
    1. Create new file `ui/frontend/src/types/meaningfulUnit.ts`
    2. Define MeaningfulUnit interface with all properties from API
    3. Define Sentiment interface with polarity, score, energy_level
    4. Export types for use in components
    5. Consult Sigma.js documentation using context7 MCP tool for node data type requirements
  - Reference: Foundation for Phase 2 frontend type safety
  - Validation: TypeScript compilation succeeds with new types

### Task 2.2: Implement Spoke Visualization State Management
- [x] Add React state management to GraphPanel.tsx for tracking selected cluster and its spoke nodes. This includes state for the currently selected cluster ID, the list of MeaningfulUnits to display as spokes, and UI configuration like number of spokes to show. The state should integrate cleanly with existing Sigma.js instance and graph state.
  - Purpose: Manages hub-and-spoke interaction state
  - Steps:
    1. Add useState hooks for selectedClusterId and spokeUnits
    2. Add useState for spokeConfig (count, show/hide)
    3. Create helper functions to manage spoke visibility
    4. Ensure state updates trigger appropriate Sigma.js re-renders
    5. Research Sigma.js state management patterns using context7 MCP tool
  - Reference: Core state management for Phase 2 interactivity
  - Validation: State updates correctly trigger visual changes

### Task 2.3: Create Click Handler for Cluster Selection
- [x] Implement cluster click event handler that fetches and displays MeaningfulUnit spokes. When a user clicks a cluster node, the handler should check if it's already selected (toggle off if so), fetch the top K MeaningfulUnits from the API if newly selected, and update the graph to show spoke nodes arranged in a circle around the cluster. The handler must also manage clearing previous spokes when selecting a new cluster.
  - Purpose: Enables primary user interaction for hub-and-spoke pattern
  - Steps:
    1. Add clickNode event listener to Sigma instance
    2. Check if clicked node is a cluster (not a spoke)
    3. Fetch meaningful units from API endpoint
    4. Calculate spoke positions in circle around cluster
    5. Add/remove nodes and edges from graph
    6. Look up Sigma.js event handling best practices using context7 MCP tool
  - Reference: Implements main interaction from Phase 2 requirements
  - Validation: Clicking cluster shows/hides spokes correctly

### Task 2.4: Implement Sentiment-Based Color Mapping
- [x] Create color calculation functions for MeaningfulUnit nodes based on sentiment polarity. The function should map positive polarity (>0.3) to green (#27ae60), negative polarity (<-0.3) to red (#e74c3c), and neutral values to gray (#95a5a6). The implementation should be configurable to allow users to adjust thresholds and colors if needed later.
  - Purpose: Provides visual sentiment analysis through color coding
  - Steps:
    1. Create getSentimentColor function in GraphPanel.tsx
    2. Implement polarity thresholds and color mapping
    3. Apply colors when creating spoke nodes
    4. Ensure colors work with Sigma.js node rendering
    5. Check Sigma.js color format requirements using context7 MCP tool
  - Reference: Implements sentiment visualization from plan specifications
  - Validation: Spoke nodes display appropriate colors based on sentiment

### Task 2.5: Add Spoke Layout Calculation
- [x] Implement circular layout algorithm for positioning spoke nodes around selected cluster. The algorithm should evenly distribute K spokes in a circle at a fixed radius from the cluster center, avoiding overlap with other clusters, and maintaining consistent spoke distance regardless of cluster size. The positions must update correctly when the graph layout changes.
  - Purpose: Creates clean visual arrangement of cluster spokes
  - Steps:
    1. Create calculateSpokePositions function
    2. Use formula: x = centerX + radius * cos(2π * i/K), y = centerY + radius * sin(2π * i/K)
    3. Ensure radius is appropriate for current zoom level
    4. Handle edge cases (1 spoke, many spokes)
    5. Research Sigma.js coordinate systems using context7 MCP tool
  - Reference: Implements spoke positioning from Phase 2 visualization design
  - Validation: Spokes appear in even circle around cluster

### Task 2.6: Update Edge Rendering for Logarithmic Scaling
- [x] Modify edge thickness calculation to use logarithmic scaling based on connection strength. This involves updating the edge rendering logic to apply log10 scaling to connection weights, mapping the result to a reasonable pixel range (0.5-5px), and ensuring visual consistency across different connection strengths. The implementation should handle edge cases like zero connections gracefully.
  - Purpose: Prevents extreme edge thickness variations with large connection counts
  - Steps:
    1. Update edge size calculation in graph initialization
    2. Implement: size = 0.5 + (Math.log10(weight + 1) / maxLog) * 4.5
    3. Test with various weight values
    4. Ensure edges remain visible at minimum zoom
    5. Consult Sigma.js edge rendering documentation using context7 MCP tool
  - Reference: Implements logarithmic edge scaling from plan requirements
  - Validation: Edge thickness varies reasonably without extremes

## Phase 3: User Interface Controls

### Task 3.1: Add Spoke Count Configuration Control
- [x] Create a UI control (slider or input) that allows users to adjust the number of spokes displayed per cluster. This control should update the spokeConfig state, trigger re-fetching of data if count increases beyond cached amount, and update the visualization immediately. The control should have reasonable limits (3-20 spokes) and persist user preference in local storage.
  - Purpose: Gives users control over visualization density
  - Steps:
    1. Add slider component to GraphPanel controls section
    2. Connect to spokeConfig state
    3. Implement onChange handler to update visualization
    4. Add min/max constraints (3-20)
    5. Save preference to localStorage
  - Reference: Implements user configuration from Phase 3 requirements
  - Validation: Slider changes immediately update spoke count

### Task 3.2: Implement Show/Hide All Spokes Toggle
- [x] Add a toggle control that shows or hides all spokes globally, allowing users to switch between network-only and detailed views. When toggled on with no cluster selected, it should prompt to select a cluster first. When toggled off, all spokes should be removed but the selected cluster state preserved. This provides quick way to declutter the visualization.
  - Purpose: Enables quick visualization mode switching
  - Steps:
    1. Add toggle switch to control panel
    2. Implement global spoke visibility state
    3. Update click handlers to respect toggle state
    4. Ensure smooth animation when hiding/showing
    5. Research Sigma.js node visibility methods using context7 MCP tool
  - Reference: Provides visual control from Phase 3 UI requirements
  - Validation: Toggle instantly hides/shows all spoke nodes

### Task 3.3: Add Sentiment Color Legend
- [x] Create a color legend component that explains the sentiment color mapping for spoke nodes. The legend should show three color swatches for positive (green), neutral (gray), and negative (red) with clear labels. It should be positioned unobtrusively but remain visible when spokes are displayed. The legend helps users interpret the sentiment visualization correctly.
  - Purpose: Helps users understand sentiment color coding
  - Steps:
    1. Create ColorLegend React component
    2. Add three color swatches with labels
    3. Position in corner of graph panel
    4. Show/hide based on spoke visibility
    5. Ensure doesn't overlap with graph controls
  - Reference: Implements user guidance from Phase 3 UI design
  - Validation: Legend clearly explains color meanings

## Phase 4: Performance Optimization

### Task 4.1: Implement Spoke Data Caching
- [ ] Add client-side caching for MeaningfulUnit data to avoid repeated API calls when re-selecting clusters. The cache should store fetched units per cluster ID, invalidate after a reasonable timeout (15 minutes), and handle cache size limits to prevent memory issues. This significantly improves interaction responsiveness for frequently selected clusters.
  - Purpose: Reduces API calls and improves interaction speed
  - Steps:
    1. Create Map-based cache with cluster ID keys
    2. Cache API responses with timestamp
    3. Check cache before making API calls
    4. Implement cache expiration logic
    5. Add cache size limit (max 50 clusters)
  - Reference: Implements performance optimization from Phase 4
  - Validation: Repeated cluster clicks don't trigger API calls

### Task 4.2: Optimize Node Addition/Removal
- [ ] Batch Sigma.js graph updates when adding or removing spoke nodes to improve rendering performance. Instead of adding nodes one by one, collect all changes and apply them in a single graph update. This includes using Sigma.js batch update methods, disabling rendering during updates, and re-enabling with a single refresh call.
  - Purpose: Prevents multiple re-renders during spoke updates
  - Steps:
    1. Use graph.import() for batch additions
    2. Collect all nodes/edges before updating
    3. Disable sigma.refresh during updates
    4. Single refresh after all changes
    5. Research Sigma.js batch update methods using context7 MCP tool
  - Reference: Improves rendering performance per Phase 4 requirements
  - Validation: Spoke transitions appear smooth without flicker

### Task 4.3: Add Loading States
- [ ] Implement loading indicators when fetching MeaningfulUnit data from the API to provide user feedback. This includes showing a spinner or skeleton on the selected cluster while loading, handling error states gracefully with user-friendly messages, and ensuring loading states don't disrupt the visualization layout. The implementation should prevent multiple simultaneous requests to the same endpoint.
  - Purpose: Provides feedback during asynchronous operations
  - Steps:
    1. Add loading state to component state
    2. Show loading indicator on cluster during fetch
    3. Implement error state handling
    4. Prevent concurrent requests for same cluster
    5. Use subtle animation that doesn't distract
  - Reference: Enhances UX per Phase 4 requirements
  - Validation: Clear feedback during data loading

## Phase 5: Testing and Refinement

### Task 5.1: Add Unit Tests for New Functions
- [ ] Create comprehensive unit tests for sentiment color mapping, spoke position calculations, and caching logic. Tests should cover edge cases like extreme sentiment values, single spoke layouts, and cache expiration scenarios. The test suite ensures reliability of core visualization logic and makes future modifications safer.
  - Purpose: Ensures reliability of new visualization features
  - Steps:
    1. Create test file GraphPanel.test.tsx
    2. Test getSentimentColor with various polarities
    3. Test calculateSpokePositions with different K values
    4. Test cache expiration and size limits
    5. Mock API calls for integration tests
  - Reference: Implements testing requirements from Phase 5
  - Validation: All tests pass with >90% coverage

### Task 5.2: Performance Testing with Large Graphs
- [ ] Test visualization performance with maximum expected cluster and spoke counts to identify bottlenecks. This involves creating test data with 50+ clusters and maximum spokes, measuring rendering frame rates during interactions, and profiling memory usage during extended sessions. The results will guide final optimization needs.
  - Purpose: Validates performance at scale
  - Steps:
    1. Create test dataset with 50 clusters
    2. Measure FPS during spoke animations
    3. Profile memory usage over time
    4. Test with multiple clusters selected sequentially
    5. Document performance benchmarks
  - Reference: Validates scalability per Phase 5 requirements
  - Validation: Maintains 30+ FPS with full visualization

### Task 5.3: User Accessibility Review
- [ ] Ensure the visualization is accessible to users with color blindness and screen readers. This includes adding ARIA labels to interactive elements, providing alternative visual encodings beyond color (shapes or patterns), and ensuring keyboard navigation works for cluster selection. The review should follow WCAG 2.1 AA guidelines.
  - Purpose: Makes visualization usable by all users
  - Steps:
    1. Add ARIA labels to clusters and controls
    2. Implement keyboard navigation for selection
    3. Add pattern/shape options for sentiment
    4. Test with screen reader software
    5. Validate color contrast ratios
  - Reference: Ensures accessibility per Phase 5 requirements
  - Validation: Passes accessibility audit tools

## Success Criteria

1. **Functionality**: Users can click any cluster to reveal its top K MeaningfulUnits as spokes
2. **Performance**: Interaction remains smooth (30+ FPS) with 50+ clusters
3. **Usability**: Sentiment colors clearly distinguish positive/negative/neutral content
4. **Configurability**: Users can adjust spoke count from 3-20 per cluster
5. **Responsiveness**: Spoke data loads within 1 second on average
6. **Reliability**: No console errors during normal interaction patterns
7. **Accessibility**: Visualization passes WCAG 2.1 AA standards

## Technology Requirements

All required technologies are already present in the project:
- Sigma.js (already installed and configured)
- React with TypeScript (existing framework)
- Neo4j (existing database)
- FastAPI (existing backend)

No new frameworks, libraries, or databases are required for this implementation.