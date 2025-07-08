# Podcast Knowledge Graph UI

This is the user interface for the Podcast Knowledge Graph application, featuring a dashboard and three-panel graph visualization.

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd ui/backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the backend server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd ui/frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Run the development server:
   ```bash
   npm run dev
   ```

4. Open your browser to `http://localhost:3000`

## Features

- **Dashboard**: View all configured podcasts in a grid layout
- **Three-Panel Layout**: 
  - Left: Navigation menu (180px)
  - Center: Graph visualization
  - Right: Statements panel (340px)
- **Theme Support**: Light/dark mode with persistence
- **Collapsible Panels**: Toggle menu and statements panels
- **Graph Visualization**: Progressive loading with clusters → topics → meaningful units

## Architecture

- **Frontend**: React + Vite + Tailwind CSS + Sigma.js
- **Backend**: FastAPI + neo4j-graphrag
- **Database**: Neo4j (multiple instances, one per podcast)

## Important Notes

- The backend expects the podcast configuration at `../seeding_pipeline/config/podcasts.yaml`
- Each podcast should have its own Neo4j instance running on the configured port
- Only the Mel Robbins database currently has clusters; others will fallback to topics