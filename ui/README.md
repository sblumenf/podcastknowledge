# Podcast Knowledge UI

Simple dashboard interface for browsing podcast knowledge graphs.

## Architecture

- **Frontend**: React with Vite, minimal dependencies
- **Backend**: FastAPI serving podcast metadata from YAML config
- **Styling**: Dark theme matching NotebookLM aesthetic

## Running the UI

```bash
./run_servers.sh
```

This starts:
- Backend API at http://localhost:8000
- Frontend UI at http://localhost:3000

## Features

- Dashboard showing all configured podcasts
- Sort by name, episode count, or last updated
- Click podcast to view its knowledge graph (placeholder)
- Reads directly from existing `podcasts.yaml` configuration

## Design Philosophy

Following KISS principles:
- No state management libraries
- No complex build tools
- Minimal API - just list podcasts
- Reuses existing database connections
- Simple dark theme CSS