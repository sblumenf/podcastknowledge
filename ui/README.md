# UI Module

## Overview
This is the UI module for the Podcast Knowledge application. It provides a web interface for exploring the knowledge graphs stored in Neo4j databases by the seeding pipeline. This module is completely independent from the transcriber and seeding pipeline modules.

## Module Independence
- **Read-only**: This module only reads data from Neo4j databases, never writes
- **No shared code**: No imports from transcriber or seeding_pipeline modules
- **Database as interface**: Neo4j is the only connection point between modules
- **Deletable**: This entire module can be removed without affecting data collection or processing

## Purpose
The UI module serves as a viewer for the podcast knowledge graphs. It reads the configuration from the seeding pipeline to understand which podcasts exist and connects to their respective Neo4j instances to display data.

## Architecture
```
ui/
├── backend/          # FastAPI server
│   ├── main.py      # API entry point
│   ├── routes/      # API endpoints
│   └── config.py    # Reads podcast configuration
└── frontend/        # React application
    └── (Vite-powered React app)
```

## Current Status
- Simple welcome page displaying the number of available podcasts
- Basic API structure ready for expansion

## Future Features (Planned)
- User authentication
- Interactive knowledge graph visualization
- Podcast browsing and search
- RAG-powered chat interface
- Analytics dashboard