# Manual Testing Checklist

## Pre-Testing Setup

1. **Backend Requirements**
   - [ ] Ensure backend is running on `http://localhost:8000`
   - [ ] Verify Neo4j database is populated with podcast data
   - [ ] Check that all required API endpoints are accessible

2. **Frontend Setup**
   - [ ] Run `npm install` to ensure all dependencies are installed
   - [ ] Start dev server with `npm run dev`
   - [ ] Open browser at `http://localhost:5173`

## Dashboard Testing

### Basic Functionality
- [ ] Dashboard loads without errors
- [ ] Podcast cards display correctly
- [ ] All podcast information is visible (name, host, category)

### Loading States
- [ ] Skeleton loaders appear while fetching podcasts
- [ ] Fade-in animation plays when navigating to dashboard

### Error Handling
- [ ] Stop backend and refresh page
- [ ] Error message displays with retry button
- [ ] Clicking retry attempts to reload (will fail without backend)
- [ ] Start backend and click retry - podcasts should load

### Navigation
- [ ] Click on a podcast card
- [ ] Verify navigation to three-panel view
- [ ] URL updates to `/podcast/{id}`

## Three-Panel Layout Testing

### Initial Load
- [ ] Three panels display correctly
- [ ] Breadcrumbs show "Dashboard > Podcast Name"
- [ ] All panels have content or loading states

### Panel Resizing
- [ ] Drag left divider to resize chat/episode panels
- [ ] Drag right divider to resize episode/graph panels
- [ ] Verify minimum panel width constraints (200px)
- [ ] Verify maximum panel width constraints (40%)
- [ ] Refresh page - panel sizes should persist

### Panel Collapse/Expand
- [ ] Click collapse button on left panel
- [ ] Chat panel collapses to 64px width
- [ ] Click expand button to restore
- [ ] Repeat for right panel
- [ ] Refresh page - collapse states should persist

### Breadcrumb Navigation
- [ ] Click "Dashboard" in breadcrumbs
- [ ] Verify navigation back to dashboard
- [ ] Fade-in animation should play

## Chat Panel Testing

### Basic Functionality
- [ ] Empty state shows "Ask a question about this podcast!"
- [ ] Type a message in the input field
- [ ] Press Enter or click Send
- [ ] Message appears in chat history
- [ ] "Thinking..." loading state displays
- [ ] Response appears when ready

### Message Display
- [ ] User messages align to the right
- [ ] Assistant messages align to the left with "AI" avatar
- [ ] Timestamps display correctly
- [ ] Markdown formatting works in assistant messages
  - [ ] **Bold text**
  - [ ] *Italic text*
  - [ ] `Code blocks`
  - [ ] Lists and bullet points

### Error Handling
- [ ] Stop backend
- [ ] Send a message
- [ ] Error message appears in chat
- [ ] Start backend and try again

### Edge Cases
- [ ] Send empty message (should be disabled)
- [ ] Send very long message (should wrap properly)
- [ ] Send 50+ messages (old messages should be removed)
- [ ] Switch podcasts - chat should clear

## Episode Panel Testing

### Basic Functionality
- [ ] Episodes load and display
- [ ] Episode numbers show correctly
- [ ] Episode titles are visible

### Virtual Scrolling
- [ ] Scroll through episode list
- [ ] Verify smooth scrolling performance
- [ ] Check that only visible items render

### Search Functionality
- [ ] Type in search box
- [ ] Results filter after 300ms delay
- [ ] Result count displays ("X of Y episodes")
- [ ] Clear search - all episodes return
- [ ] Search with no results - "No episodes match" message

### Error Handling
- [ ] Create new podcast in URL (e.g., `/podcast/fake-id`)
- [ ] Episode panel shows error with retry
- [ ] Navigate to valid podcast - episodes load

## Graph Panel Testing

### Placeholder
- [ ] Graph panel displays placeholder text
- [ ] Panel maintains consistent styling

## Performance Testing

### Memory Usage
- [ ] Navigate between dashboard and panels multiple times
- [ ] Check browser memory usage doesn't grow excessively
- [ ] Verify no memory leaks from event listeners

### Responsive Design
- [ ] Resize browser window
- [ ] Panels adjust appropriately
- [ ] Minimum widths maintained

### Animation Performance
- [ ] Route transitions complete in under 300ms
- [ ] Panel resize is smooth
- [ ] No janky animations

## Accessibility Testing

### Keyboard Navigation
- [ ] Tab through all interactive elements
- [ ] Enter key works on buttons and links
- [ ] Escape key clears focus where appropriate

### Screen Reader (Optional)
- [ ] Enable screen reader
- [ ] Navigate through panels
- [ ] Verify content is announced correctly

## Cross-Browser Testing

Test in multiple browsers:
- [ ] Chrome/Edge
- [ ] Firefox
- [ ] Safari (if on macOS)

## Edge Cases and Stress Testing

### Data Edge Cases
- [ ] Podcast with very long name
- [ ] Podcast with no episodes
- [ ] Podcast with 1000+ episodes
- [ ] Very long episode titles

### Network Conditions
- [ ] Slow network (throttle in DevTools)
- [ ] Intermittent connection
- [ ] API timeout scenarios

### State Persistence
- [ ] Clear localStorage
- [ ] Verify app works with defaults
- [ ] Set extreme panel sizes in localStorage
- [ ] Verify constraints are enforced

## Final Verification

- [ ] No console errors during normal usage
- [ ] All user flows complete successfully
- [ ] UI remains responsive under all conditions
- [ ] Error states provide clear user feedback
- [ ] Loading states appear for all async operations