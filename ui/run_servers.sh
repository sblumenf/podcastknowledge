#!/bin/bash

# Script to run both frontend and backend servers

echo "Starting Podcast Knowledge UI..."

# Function to kill processes on exit
cleanup() {
    echo -e "\nShutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}

trap cleanup EXIT INT TERM

# Start backend
echo "Starting backend API server..."
cd backend
python3 -m uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Give backend time to start
sleep 2

# Start frontend
echo "Starting frontend development server..."
cd ../frontend
if [ ! -d "node_modules" ] || [ ! -f "node_modules/.bin/vite" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi
npm run start &
FRONTEND_PID=$!

echo -e "\n✓ Backend API running at: http://localhost:8000"
echo "✓ Frontend UI running at: http://localhost:3000"
echo -e "\nPress Ctrl+C to stop all servers\n"

# Wait for processes
wait