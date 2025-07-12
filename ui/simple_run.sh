#!/bin/bash

# Simple script to run just the backend server

echo "Starting Podcast Knowledge Backend API..."

# Function to kill processes on exit
cleanup() {
    echo -e "\nShutting down backend server..."
    kill $BACKEND_PID 2>/dev/null
    exit
}

trap cleanup EXIT INT TERM

# Start backend
echo "Starting backend API server..."
cd backend
python3 -m uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

echo -e "\n✓ Backend API running at: http://localhost:8000"
echo -e "\nYou can test the API at:"
echo "  - http://localhost:8000/api/v1/podcasts"
echo "  - http://localhost:8000/docs"
echo -e "\nPress Ctrl+C to stop the server\n"

# Wait for process
wait