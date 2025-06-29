# Component Documentation

## Overview

This document provides an overview of all React components in the Podcast Knowledge Discovery UI.

## Component Hierarchy

```
App
├── ErrorBoundary
│   └── Dashboard
│       ├── PodcastCard
│       └── PodcastCardSkeleton
└── ErrorBoundary
    └── ThreePanelLayout
        ├── Breadcrumbs
        ├── ChatPanel
        │   └── Message
        ├── EpisodePanel
        ├── GraphPanel
        └── PanelDivider
```

## Component Reference

### App
**Location**: `src/App.tsx`  
**Purpose**: Main application component with routing  
**Key Features**:
- Wraps content with ErrorBoundary
- Defines routes for Dashboard and ThreePanelLayout
- Applies fade-in animation

### ErrorBoundary
**Location**: `src/components/ErrorBoundary.tsx`  
**Purpose**: Catches JavaScript errors in component tree  
**Props**: 
- `children: ReactNode` - Child components to wrap
**Key Features**:
- Displays user-friendly error message
- Provides "Try again" button to reset state

### ErrorDisplay
**Location**: `src/components/ErrorDisplay.tsx`  
**Purpose**: Reusable error display component  
**Props**:
- `error: string` - Error message to display
- `onRetry?: () => void` - Optional retry callback
**Key Features**:
- Consistent error UI across panels
- Optional retry functionality

### Dashboard
**Location**: `src/components/Dashboard.tsx`  
**Purpose**: Main landing page showing all podcasts  
**API**: `GET /api/podcasts`  
**Key Features**:
- Displays grid of podcast cards
- Shows skeleton loaders while fetching
- Error handling with retry

### PodcastCard
**Location**: `src/components/PodcastCard.tsx`  
**Purpose**: Individual podcast display card  
**Props**:
- `podcast: Podcast` - Podcast data object
**Key Features**:
- Links to three-panel view
- Displays name, host, and category
- Memoized for performance

### PodcastCardSkeleton
**Location**: `src/components/PodcastCardSkeleton.tsx`  
**Purpose**: Loading placeholder for podcast cards  
**Key Features**:
- Shimmer animation effect
- Matches PodcastCard dimensions

### ThreePanelLayout
**Location**: `src/components/ThreePanelLayout.tsx`  
**Purpose**: Main podcast view with three resizable panels  
**Route Params**:
- `id: string` - Podcast ID from URL
**Key Features**:
- Resizable panels with drag handles
- Collapsible side panels
- State persistence in localStorage
- Responsive layout

### Breadcrumbs
**Location**: `src/components/Breadcrumbs.tsx`  
**Purpose**: Navigation breadcrumbs  
**Props**:
- `podcastId: string` - Current podcast ID
**Key Features**:
- Shows Dashboard > Podcast Name
- Fetches podcast name from API

### ChatPanel
**Location**: `src/components/ChatPanel.tsx`  
**Purpose**: Interactive chat interface  
**Props**:
- `podcastId: string` - Current podcast ID
**API**: `POST /api/chat/{podcastId}`  
**Key Features**:
- Message history (50 message limit)
- Auto-scroll to bottom
- Loading state with "Thinking..."
- Error handling with user-friendly messages
- Clears chat on podcast switch

### Message
**Location**: `src/components/Message.tsx`  
**Purpose**: Individual chat message display  
**Props**:
- `message: ChatMessage` - Message data
**Key Features**:
- Markdown rendering for assistant messages
- Timestamp display
- Different styles for user/assistant
- Memoized for performance

### EpisodePanel
**Location**: `src/components/EpisodePanel.tsx`  
**Purpose**: List of podcast episodes  
**Props**:
- `podcastId: string` - Current podcast ID
**API**: `GET /api/podcasts/{podcastId}/episodes`  
**Key Features**:
- Virtual scrolling for performance
- Search with 300ms debounce
- Throttled scroll events (60fps)
- Shows episode numbers
- Error handling with retry

### GraphPanel
**Location**: `src/components/GraphPanel.tsx`  
**Purpose**: Knowledge graph visualization placeholder  
**Props**:
- `podcastId: string` - Current podcast ID
**Key Features**:
- Placeholder for future graph implementation
- Consistent panel styling

### PanelDivider
**Location**: `src/components/PanelDivider.tsx`  
**Purpose**: Draggable divider between panels  
**Props**:
- `onResize: (delta: number) => void` - Resize callback
- `orientation?: 'vertical' | 'horizontal'` - Divider direction
**Key Features**:
- Drag to resize panels
- Visual handle indicator
- Proper event cleanup

## State Management

### Panel State
Stored in localStorage as `panelState`:
```typescript
{
  leftWidth: number,    // Percentage
  rightWidth: number,   // Percentage
  leftCollapsed: boolean,
  rightCollapsed: boolean
}
```

### Chat State
- Messages stored in component state
- Limited to 50 messages for performance
- Clears on podcast change

### Episode State
- Episodes fetched on podcast change
- Virtual scrolling maintains performance with large lists
- Search state managed locally

## Performance Optimizations

1. **React.memo**: PodcastCard and Message components
2. **Virtual Scrolling**: EpisodePanel for large lists
3. **Throttled Scrolling**: 60fps throttle on episode scroll
4. **Debounced Search**: 300ms debounce on episode search
5. **Traditional Navigation**: React Router prevents SPA memory issues

## CSS Architecture

- CSS Modules for component isolation
- Consistent naming conventions
- Responsive design with CSS Grid and Flexbox
- Animations under 300ms for performance