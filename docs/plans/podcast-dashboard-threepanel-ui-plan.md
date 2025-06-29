# Podcast Dashboard and Three-Panel UI Implementation Plan

## Executive Summary

This plan delivers a desktop web application for podcast knowledge discovery. Users see all podcasts on a dashboard and click to open a three-panel interface: chat (left), knowledge graph placeholder (middle), and episode list (right). The implementation uses the existing React/TypeScript/Vite/CSS Modules stack with FastAPI backend and neo4j-graphrag for chat. Every task follows KISS principles with explicit instructions and no assumptions.

### Key Implementation Details:
- **Navigation**: React Router for traditional URL-based routing (prevents memory issues)
- **Source of Truth**: `seeding_pipeline/config/podcasts.yaml` for podcasts, Neo4j databases for episodes
- **Directory Structure**: Flat component structure (no subdirectories) following KISS principle
- **Admin Preservation**: Existing admin functionality explicitly preserved
- **Chat Integration**: Maintains existing neo4j-graphrag with persona support
- **Performance Focus**: Traditional routing prevents loading multiple visualizations simultaneously

## Phase 1: Project Setup and Structure (Day 1)

### Task 1.1: Clean and Prepare UI Directory
- [ ] **Task**: Remove experimental UI code while explicitly preserving the admin functionality and technology stack configuration. This involves identifying and keeping all admin-related components and routes while removing only the experimental dashboard and chat components. The cleanup ensures a fresh start for the new UI while maintaining both the admin interface and the established build pipeline.
- **Purpose**: Create a clean slate for new UI while preserving admin functionality and configuration
- **Steps**:
  1. Navigate to `ui/frontend/src/components` and identify admin-related components
  2. Delete only non-admin experimental components (old dashboard, chat)
  3. Preserve all admin routes and components
  4. Keep all configuration files (package.json, vite.config.ts, etc.) unchanged
  5. Verify admin functionality still works by testing admin routes
  6. Verify build still works by running `npm run dev`
- **Reference**: This task aligns with preserving needed admin functionality while removing only experimental code
- **Validation**: Admin pages load correctly and `npm run dev` starts without errors
- **REMINDER**: Review plan goals - KISS principle, preserve admin, use existing stack only

### Task 1.2: Setup React Router
- [ ] **Task**: Configure React Router for traditional navigation between dashboard and podcast views to prevent memory issues from loading all podcasts at once. This setup enables proper URL-based routing where each podcast loads in isolation, preventing the performance problems that would occur with SPA state management. React Router is already in the package.json so no new technology is introduced.
- **Purpose**: Enable traditional navigation to prevent memory overload from multiple visualizations
- **Steps**:
  1. Create `ui/frontend/src/App.tsx` with React Router setup
  2. Define routes: "/" for dashboard, "/podcast/:id" for three-panel view
  3. Preserve existing admin routes in the router configuration
  4. Import BrowserRouter and wrap the app
  5. Create route components for Dashboard and ThreePanel views
  6. Consult Context7 MCP tool for React Router v6 patterns
- **Reference**: Implements traditional navigation to address performance concerns from plan
- **Validation**: Navigation to "/" and "/podcast/123" URLs works correctly
- **REMINDER**: Review plan goals - prevent performance issues, KISS principle, use existing dependencies

### Task 1.3: Define TypeScript Interfaces
- [ ] **Task**: Create simple TypeScript interfaces in a flat structure for all data types including Podcast, Episode, ChatMessage, and PanelState. The interfaces must exactly match the existing backend response formats without adding extra properties. Keep all interfaces in the existing types folder without creating subdirectories to maintain KISS principles.
- **Purpose**: Establish type safety matching existing backend data structures
- **Steps**:
  1. Create `ui/frontend/src/types.ts` file (single file for simplicity)
  2. Define Podcast interface matching `/api/podcasts` response
  3. Define Episode interface for Neo4j episode data
  4. Define ChatMessage interface matching `/api/chat/{podcast_id}` response
  5. Define simple PanelState interface for resize/collapse states
  6. Consult Context7 MCP tool for TypeScript interface best practices
- **Reference**: These types support all subsequent phases and maintain backend compatibility
- **Validation**: TypeScript compiler shows no errors when importing these types
- **REMINDER**: Review plan goals - KISS principle, single types file, match backend exactly

## Phase 2: Dashboard Implementation (Day 2)

### Task 2.1: Create Dashboard Layout Component
- [ ] **Task**: Build the main dashboard component that displays all podcasts in a responsive card grid layout. This component will fetch podcast data from the existing `/api/podcasts` endpoint which reads from `seeding_pipeline/config/podcasts.yaml` as the source of truth. The layout must use CSS Grid for simplicity and performance, keeping all components in the flat components directory.
- **Purpose**: Provide the entry point showing all available podcasts from the YAML configuration
- **Steps**:
  1. Create `ui/frontend/src/components/Dashboard.tsx` (flat structure, no subdirectory)
  2. Implement podcast fetching using native fetch API to `/api/podcasts`
  3. Document that podcasts.yaml is the source of truth for podcast list
  4. Create CSS Grid layout with responsive columns using CSS Modules
  5. Add loading state while fetching podcasts
  6. Add error handling for failed API calls
  7. Consult Context7 MCP tool for React component patterns and CSS Grid best practices
- **Reference**: This is the main entry point described in the plan's dashboard requirements
- **Validation**: Dashboard displays podcast cards in grid layout when accessing root URL
- **REMINDER**: Review plan goals - KISS principle, flat directory structure, use existing API

### Task 2.2: Create Podcast Card Component
- [ ] **Task**: Design and implement individual podcast card components that display podcast metadata and handle click navigation using React Router. Each card shows the podcast title and minimal metadata from the API response. Cards must use React Router's Link component to navigate to `/podcast/:id` route for proper memory management and URL-based navigation.
- **Purpose**: Display individual podcasts as clickable elements with proper routing
- **Steps**:
  1. Create `ui/frontend/src/components/PodcastCard.tsx` (flat structure)
  2. Create `ui/frontend/src/components/PodcastCard.module.css`
  3. Implement card with title display only (KISS principle)
  4. Add hover effects using CSS transitions
  5. Use React Router Link component for navigation to `/podcast/${id}`
  6. Consult Context7 MCP tool for React Router Link usage
- **Reference**: Implements the dashboard card design with traditional navigation
- **Validation**: Cards display podcast info and navigate to correct URL on click
- **REMINDER**: Review plan goals - simple cards, React Router navigation, no complex features

### Task 2.3: Remove Task - Navigation Handled by React Router
- [ ] **Task**: This task is no longer needed as navigation is handled by React Router configuration from Task 1.2. The traditional routing approach eliminates the need for state-based navigation logic. Navigation happens automatically through React Router Links in the PodcastCard component, preventing memory issues from loading multiple podcast visualizations.
- **Purpose**: Document that navigation is already handled by React Router
- **Steps**:
  1. Verify React Router setup from Task 1.2 is complete
  2. Confirm PodcastCard uses Link component for navigation
  3. No additional navigation logic needed (KISS principle)
  4. Document that breadcrumb navigation will use React Router's location
- **Reference**: Simplifies implementation by using React Router's built-in navigation
- **Validation**: Navigation works through URL changes without additional code
- **REMINDER**: Review plan goals - KISS principle, use React Router, avoid redundant code

## Phase 3: Three-Panel Layout Implementation (Day 3)

### Task 3.1: Create Three-Panel Container Component
- [ ] **Task**: Build the main three-panel layout container that houses chat (left), graph placeholder (middle), and episode list (right) panels. This component receives the podcast ID from React Router params and manages the overall layout using CSS Grid. The layout must be kept simple with minimal state to support future heavy graph visualizations without performance issues.
- **Purpose**: Establish the three-panel structure with proper layout management
- **Steps**:
  1. Create `ui/frontend/src/components/ThreePanelLayout.tsx` (flat structure)
  2. Get podcast ID from React Router useParams hook
  3. Implement CSS Grid with three columns (chat, graph, episodes)
  4. Set initial sizes: 25% (chat), 50% (graph), 25% (episodes)
  5. Add refs for panel size management
  6. Create container structure with proper semantic HTML
  7. Consult Context7 MCP tool for CSS Grid three-column layout patterns
- **Reference**: Implements the core three-panel design with left chat, middle graph, right episodes
- **Validation**: Three panels display with correct initial proportions at /podcast/:id route
- **REMINDER**: Review plan goals - simple grid layout, chat on left, prepare for graph performance

### Task 3.2: Implement Panel Resize Functionality
- [ ] **Task**: Add draggable dividers between panels that allow users to resize panel widths by dragging. This feature uses mouse events to track drag operations and updates CSS Grid column sizes dynamically. Keep the implementation simple without external libraries to maintain performance for future graph visualizations.
- **Purpose**: Allow users to adjust panel sizes for their workflow
- **Steps**:
  1. Create `ui/frontend/src/components/PanelDivider.tsx` (flat structure)
  2. Implement mousedown, mousemove, and mouseup event handlers
  3. Calculate new panel sizes based on mouse position
  4. Update CSS Grid template columns during drag
  5. Add visual feedback (cursor change) during hover and drag
  6. Implement minimum panel sizes (200px minimum)
  7. Consult Context7 MCP tool for implementing draggable dividers in React
- **Reference**: Addresses the resizable panels requirement from the plan
- **Validation**: Dragging dividers smoothly resizes adjacent panels
- **REMINDER**: Review plan goals - KISS principle, no resize libraries, maintain performance

### Task 3.3: Add Panel Collapse/Expand Controls
- [ ] **Task**: Implement collapse and expand functionality for the chat and episode panels, allowing users to maximize the graph area. Each collapsible panel needs a toggle button that animates the panel to a minimal width. The graph panel remains always visible as it will be the primary focus for heavy visualizations.
- **Purpose**: Maximize space for future graph visualization
- **Steps**:
  1. Add collapse state to ThreePanelLayout using useState
  2. Create collapse toggle buttons in panel headers
  3. Implement CSS transitions for smooth collapse animation
  4. Update grid template columns for collapsed state (64px when collapsed)
  5. Ensure graph panel expands to fill freed space
  6. Save collapse state to localStorage
  7. Use Context7 MCP tool for CSS transition best practices
- **Reference**: Supports future performance needs of heavy graph visualization
- **Validation**: Panels collapse to minimal size and expand back smoothly
- **REMINDER**: Review plan goals - keep animations simple for performance, KISS principle

## Phase 4: Chat Panel Implementation (Day 4)

### Task 4.0: Analyze Existing Chat Implementation
- [ ] **Task**: Study the existing chat functionality to understand how persona integration and markdown rendering currently work in the experimental code. This analysis ensures the new implementation maintains compatibility with the neo4j-graphrag backend that includes persona-based system instructions. Understanding the current implementation prevents breaking existing functionality.
- **Purpose**: Understand existing chat patterns before implementing new UI
- **Steps**:
  1. Examine existing chat components for persona handling
  2. Review how markdown responses are currently rendered
  3. Check existing `/api/chat/{podcast_id}` request/response format
  4. Note how persona is loaded from podcast configuration
  5. Document any special handling for neo4j-graphrag responses
  6. Consult Context7 MCP tool for neo4j-graphrag documentation
- **Reference**: Ensures new chat UI maintains compatibility with existing backend
- **Validation**: Document findings about persona and markdown handling
- **REMINDER**: Review plan goals - maintain existing neo4j-graphrag integration, understand before building

### Task 4.1: Create Chat Panel Layout
- [ ] **Task**: Build the chat panel component that interfaces with the existing neo4j-graphrag powered backend chat endpoint. This panel displays chat history with persona-based responses and provides an input field for user queries. The component must properly display markdown-formatted messages from the neo4j-graphrag backend.
- **Purpose**: Provide interface for neo4j-graphrag powered chat functionality with persona
- **Steps**:
  1. Create `ui/frontend/src/components/ChatPanel.tsx` (flat structure)
  2. Implement message history display with scrollable container
  3. Add input field with send button at bottom
  4. Create message bubble components for user/AI messages
  5. Connect to existing `/api/chat/{podcast_id}` endpoint
  6. Include persona context from podcast configuration
  7. Display loading state during API calls
  8. Consult Context7 MCP tool for chat UI patterns and best practices
- **Reference**: Integrates with existing neo4j-graphrag backend with persona support
- **Validation**: Chat messages display with persona context and new messages can be sent
- **REMINDER**: Review plan goals - use existing neo4j-graphrag API, maintain persona functionality

### Task 4.2: Implement Chat Message Components
- [ ] **Task**: Create reusable message components that display user queries and AI responses with appropriate styling and markdown formatting. Messages must properly render markdown responses from the neo4j-graphrag backend using the existing react-markdown library. The implementation must match how the current experimental chat handles markdown to ensure consistency.
- **Purpose**: Display chat messages with proper markdown formatting
- **Steps**:
  1. Create `ui/frontend/src/components/Message.tsx` (flat structure)
  2. Implement user message styling (right-aligned, different color)
  3. Implement AI message styling (left-aligned, includes avatar)
  4. Integrate react-markdown for rendering formatted responses
  5. Copy markdown configuration from existing chat if present
  6. Add timestamp display for each message
  7. Handle long messages with proper text wrapping
  8. Consult Context7 MCP tool for react-markdown usage patterns
- **Reference**: Ensures markdown rendering matches existing implementation
- **Validation**: Messages render markdown correctly including code blocks and formatting
- **REMINDER**: Review plan goals - use existing react-markdown, match current markdown handling

### Task 4.3: Add Chat State Management
- [ ] **Task**: Implement local state management for chat history that persists messages for the current session and handles message sending flow. This includes managing loading states, error handling, and proper message ordering. The state must integrate cleanly with the existing chat API structure.
- **Purpose**: Manage chat conversation state and API interactions
- **Steps**:
  1. Add chat state using useState in ChatPanel
  2. Implement addMessage function for new messages
  3. Create sendMessage function that calls API and updates state
  4. Add error handling for failed API calls
  5. Implement auto-scroll to latest message
  6. Clear chat when switching podcasts
  7. Consult Context7 MCP tool for React state management patterns
- **Reference**: Maintains simple state management as specified in plan
- **Validation**: Chat maintains history and handles errors gracefully
- **REMINDER**: Review plan goals - simple state, no complex state libraries, KISS

## Phase 5: Episode List Panel Implementation (Day 5)

### Task 5.0: Create Episodes API Endpoint
- [ ] **Task**: Create a new API endpoint `/api/podcasts/{podcast_id}/episodes` that queries the podcast's Neo4j database to retrieve all episodes. The Neo4j database for each podcast is the source of truth for episodes, containing meaningful units that represent individual episodes. This endpoint must connect to the correct podcast-specific Neo4j instance and return episode data.
- **Purpose**: Provide episode data from Neo4j database source of truth
- **Steps**:
  1. Create new route in `ui/backend/routes/episodes.py`
  2. Use existing database connection pattern from chat service
  3. Query Neo4j for nodes representing episodes/meaningful units
  4. Return list with episode title and any available metadata
  5. Handle database connection errors gracefully
  6. Add route to main FastAPI app
  7. Consult Context7 MCP tool for Neo4j query patterns
- **Reference**: Establishes Neo4j as source of truth for episode data as specified
- **Validation**: Endpoint returns episode list from podcast's Neo4j database
- **REMINDER**: Review plan goals - Neo4j is source of truth, reuse existing connection patterns

### Task 5.1: Create Episode List Panel
- [ ] **Task**: Build the episode list panel that displays all episodes from the podcast's Neo4j database with virtual scrolling for performance. This panel fetches episodes from the new `/api/podcasts/{podcast_id}/episodes` endpoint and must handle potentially thousands of episodes efficiently. The implementation uses a simple virtual scrolling approach without external libraries.
- **Purpose**: Display large episode lists from Neo4j without performance issues
- **Steps**:
  1. Create `ui/frontend/src/components/EpisodePanel.tsx` (flat structure)
  2. Fetch episodes from `/api/podcasts/{podcast_id}/episodes` endpoint
  3. Implement container with fixed height and overflow scroll
  4. Add basic virtual scrolling logic using scroll position
  5. Calculate visible items based on container height
  6. Render only visible items plus buffer
  7. Consult Context7 MCP tool for virtual scrolling implementation patterns
- **Reference**: Displays episodes from Neo4j database with performance optimization
- **Validation**: Scrolling through long lists remains performant
- **REMINDER**: Review plan goals - simple virtual scrolling, Neo4j as source, no complex libraries

### Task 5.2: Create Episode List Item Component
- [ ] **Task**: Design episode list items that display just the episode title as specified in the requirements. Each item must have consistent height for virtual scrolling calculations. The design should be minimal but clear, with hover states for future interactivity.
- **Purpose**: Display individual episodes in the list
- **Steps**:
  1. Create `ui/frontend/src/components/ThreePanel/EpisodePanel/EpisodeItem.tsx`
  2. Implement fixed-height item with title display
  3. Add CSS Module for consistent styling
  4. Implement hover state for future functionality
  5. Ensure text truncation for long titles
  6. Add episode number if available in data
  7. Consult Context7 MCP tool for list item accessibility
- **Reference**: Implements the "just title" requirement from plan
- **Validation**: Episodes display with consistent height and truncated titles
- **REMINDER**: Review plan goals - title only, no additional metadata, keep simple

### Task 5.3: Implement Episode Search/Filter
- [ ] **Task**: Add a simple search input at the top of the episode panel that filters the episode list by title. The search must be performant even with large lists by using debouncing. The filtered results should maintain virtual scrolling functionality.
- **Purpose**: Help users find specific episodes in large lists
- **Steps**:
  1. Add search input component at top of EpisodePanel
  2. Implement filter state using useState
  3. Add debounce logic (300ms) for search input
  4. Filter episodes array based on search term
  5. Update virtual scrolling to use filtered array
  6. Show result count when filtering
  7. Use Context7 MCP tool for search UX best practices
- **Reference**: Supports usability with large episode lists as mentioned in plan
- **Validation**: Search filters episodes in real-time with good performance
- **REMINDER**: Review plan goals - simple search only, maintain performance

## Phase 6: Graph Placeholder and Integration (Day 6)

### Task 6.1: Create Knowledge Graph Placeholder
- [ ] **Task**: Build a simple placeholder component for the knowledge graph panel that displays "Coming Soon" messaging. The placeholder must be styled consistently with the rest of the application and provide visual context for what will eventually be displayed. This panel takes up the center space and is the primary focus area.
- **Purpose**: Reserve space for future graph visualization
- **Steps**:
  1. Create `ui/frontend/src/components/ThreePanel/GraphPanel/GraphPanel.tsx`
  2. Implement centered "Coming Soon" message
  3. Add subtle background pattern or illustration
  4. Include brief description of future functionality
  5. Ensure panel fills available space
  6. Add CSS Module for styling
  7. Consult Context7 MCP tool for placeholder UI patterns
- **Reference**: Implements the "coming soon" placeholder requirement from plan
- **Validation**: Placeholder displays centered in middle panel
- **REMINDER**: Review plan goals - simple placeholder only, prepare for future heavy visualization

### Task 6.2: Add Navigation Breadcrumbs
- [ ] **Task**: Implement breadcrumb navigation at the top of the three-panel view that shows "Dashboard > [Podcast Name]" and allows users to return to the dashboard. The breadcrumb uses React Router's Link component for navigation and gets the current podcast info from router params. The implementation must be simple without external breadcrumb libraries.
- **Purpose**: Provide clear navigation back to dashboard using React Router
- **Steps**:
  1. Create `ui/frontend/src/components/Breadcrumbs.tsx` (flat structure)
  2. Use React Router's useParams to get current podcast ID
  3. Display "Dashboard > [Current Podcast Name]"
  4. Use React Router Link component for "Dashboard" navigation to "/"
  5. Style with CSS Modules for consistent appearance
  6. Add hover state for clickable elements
  7. Position at top of three-panel layout
  8. Consult Context7 MCP tool for React Router breadcrumb patterns
- **Reference**: Implements breadcrumb navigation using React Router as per updated plan
- **Validation**: Breadcrumbs display and "Dashboard" link navigates to root URL
- **REMINDER**: Review plan goals - use React Router for navigation, maintain KISS principle

### Task 6.3: Implement Panel State Persistence
- [ ] **Task**: Add localStorage persistence for panel sizes and collapse states so user preferences are maintained between sessions. This includes saving panel widths when resized and collapse states when toggled. The implementation must handle edge cases like missing localStorage data gracefully.
- **Purpose**: Remember user's panel configuration preferences
- **Steps**:
  1. Create utility functions for localStorage read/write
  2. Save panel sizes on resize end
  3. Save collapse states on toggle
  4. Load saved state on component mount
  5. Validate saved data before applying
  6. Use default values if no saved state exists
  7. Consult Context7 MCP tool for localStorage best practices
- **Reference**: Implements the state persistence requirement from plan
- **Validation**: Panel states restore correctly after page refresh
- **REMINDER**: Review plan goals - simple persistence, handle edge cases

## Phase 7: Integration and Polish (Day 7)

### Task 7.1: Add Loading States and Transitions
- [ ] **Task**: Implement loading states for all async operations and smooth transitions between dashboard and panel views. This includes skeleton screens for initial loads and spinner indicators for active requests. Transitions should be subtle and not impact performance given the future heavy graph visualization needs.
- **Purpose**: Provide visual feedback during async operations
- **Steps**:
  1. Create loading skeleton for podcast cards
  2. Add loading state to chat panel during message sending
  3. Implement fade transition between dashboard and panel views
  4. Add loading indicator for episode list fetch
  5. Ensure transitions are CSS-only for performance
  6. Keep animations under 300ms duration
  7. Use Context7 MCP tool for loading state patterns
- **Reference**: Addresses the performance consideration from plan requirements
- **Validation**: All async operations show appropriate loading feedback
- **REMINDER**: Review plan goals - simple transitions, performance is priority

### Task 7.2: Implement Error Handling UI
- [ ] **Task**: Add user-friendly error handling throughout the application for failed API calls, network issues, and invalid states. Each error should provide clear feedback and possible actions. The error handling must not interrupt the user experience and should allow recovery without page refresh.
- **Purpose**: Handle failures gracefully with clear user feedback
- **Steps**:
  1. Create `ui/frontend/src/components/Common/ErrorMessage.tsx`
  2. Add error boundaries to catch React errors
  3. Implement retry logic for failed API calls
  4. Show inline errors in chat for message failures
  5. Display error state in dashboard if podcast fetch fails
  6. Add fallback UI for missing data
  7. Consult Context7 MCP tool for error handling UX patterns
- **Reference**: Supports robust user experience as implied by plan
- **Validation**: Errors display clearly and allow recovery
- **REMINDER**: Review plan goals - simple error handling, maintain user flow

### Task 7.3: Performance Optimization Pass
- [ ] **Task**: Review and optimize the application for performance, particularly focusing on render performance and preparing for future heavy graph visualizations. This includes implementing React.memo for expensive components, optimizing re-renders, and ensuring efficient event handlers. The focus is on measurable improvements without premature optimization.
- **Purpose**: Ensure app performs well with large datasets
- **Steps**:
  1. Add React.memo to PodcastCard components
  2. Optimize episode list virtual scrolling
  3. Debounce resize event handlers
  4. Review and minimize component re-renders
  5. Check for memory leaks in event listeners
  6. Profile using React DevTools
  7. Use Context7 MCP tool for React performance best practices
- **Reference**: Addresses performance needs for future graph visualization
- **Validation**: React DevTools shows minimal unnecessary re-renders
- **REMINDER**: Review plan goals - optimize for future graph needs, avoid over-engineering

## Phase 8: Testing and Documentation (Day 8)

### Task 8.1: Create Component Documentation
- [ ] **Task**: Write clear documentation for each major component describing its purpose, props, and usage examples. This documentation lives alongside the components and helps future development. The documentation should be concise and focus on practical usage rather than extensive technical details.
- **Purpose**: Document components for maintainability
- **Steps**:
  1. Add JSDoc comments to all component files
  2. Document component props with TypeScript
  3. Create README.md in each component directory
  4. Include basic usage examples
  5. Document any non-obvious behavior
  6. List any performance considerations
  7. Use Context7 MCP tool for component documentation standards
- **Reference**: Ensures maintainable codebase per KISS principles
- **Validation**: Each component has clear documentation
- **REMINDER**: Review plan goals - simple, practical documentation only

### Task 8.2: Manual Testing Checklist
- [ ] **Task**: Create and execute a comprehensive manual testing checklist covering all user flows and edge cases. This includes testing with various numbers of podcasts and episodes, different screen sizes, and error conditions. The checklist ensures all functionality works as specified without introducing complex testing frameworks.
- **Purpose**: Verify all functionality works correctly
- **Steps**:
  1. Test dashboard loads and displays all podcasts
  2. Verify podcast click navigation to three-panel view
  3. Test chat functionality with existing backend
  4. Verify episode list scrolling performance
  5. Test panel resize and collapse features
  6. Verify breadcrumb navigation back to dashboard
  7. Test error states and loading states
  8. Check localStorage persistence
  9. Document any issues found
- **Reference**: Validates all features specified in plan work correctly
- **Validation**: All checklist items pass without errors
- **REMINDER**: Review plan goals - focus on specified features only

### Task 8.3: Update API Documentation
- [ ] **Task**: Document the new episodes API endpoint `/api/podcasts/{podcast_id}/episodes` that queries Neo4j for episode data. This documentation must clearly state that Neo4j is the source of truth for episodes and explain how the endpoint connects to podcast-specific databases. Include any performance considerations for large episode lists from Neo4j queries.
- **Purpose**: Document the episodes endpoint and Neo4j integration
- **Steps**:
  1. Document `/api/podcasts/{podcast_id}/episodes` endpoint
  2. Explain Neo4j as source of truth for episode data
  3. Document connection to podcast-specific Neo4j instances
  4. Include example API response with episode structure
  5. Note performance considerations for large result sets
  6. Document any query optimizations used
  7. Update backend README with new endpoint
  8. Use Context7 MCP tool for API documentation standards
- **Reference**: Documents Neo4j integration as specified in plan updates
- **Validation**: API documentation clearly explains Neo4j episode retrieval
- **REMINDER**: Review plan goals - document Neo4j as source, explain implementation clearly

## Success Criteria

1. **Dashboard Functionality**
   - All podcasts display in card grid
   - Cards are clickable and navigate to panel view
   - Grid is responsive to window size

2. **Three-Panel Layout**
   - Panels display in correct proportions
   - Resize dividers work smoothly
   - Collapse/expand functions properly
   - State persists between sessions

3. **Chat Integration**
   - Chat connects to existing neo4j-graphrag backend
   - Messages send and receive correctly
   - Markdown rendering works

4. **Episode List**
   - Handles large lists performantly
   - Search filters work correctly
   - Virtual scrolling performs well

5. **Navigation**
   - Breadcrumbs allow return to dashboard
   - View transitions are smooth
   - No navigation errors or dead ends

6. **Performance**
   - No noticeable lag with many podcasts
   - Episode scrolling remains smooth
   - Panel resize is responsive

## Technology Requirements

All technologies used are already part of the existing stack:
- React 19.1.0
- TypeScript
- Vite 6.3.5
- CSS Modules
- react-markdown 10.1.0
- Native browser APIs (fetch, localStorage)
- Existing FastAPI backend
- Existing neo4j-graphrag integration

**NO NEW TECHNOLOGIES INTRODUCED** - This plan uses only the existing approved technology stack.

## Final Notes

This plan emphasizes:
- KISS principle throughout
- No over-engineering or premature optimization
- Exact adherence to plan specifications
- No intuition-based decisions
- Performance consciousness for future graph needs
- Using only existing technologies

Every task includes explicit reminders to review plan goals and avoid deviation. The implementation focuses on delivering exactly what was specified without adding unnecessary complexity.