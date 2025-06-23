#!/bin/bash
# Development script for the UI module
# Starts both backend and frontend servers for development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=8001
FRONTEND_PORT=5173

echo -e "${GREEN}Starting Podcast Knowledge UI Development Environment...${NC}"

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${RED}Error: Port $port is already in use${NC}"
        echo "Please stop the process using port $port or use a different port"
        return 1
    fi
    return 0
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"

if ! command_exists python3; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    echo "Please install Python 3 and try again"
    exit 1
fi

if ! command_exists npm; then
    echo -e "${RED}Error: npm is not installed${NC}"
    echo "Please install Node.js and npm and try again"
    exit 1
fi

# Check ports
echo -e "${YELLOW}Checking ports...${NC}"
check_port $BACKEND_PORT || exit 1
check_port $FRONTEND_PORT || exit 1

# Create virtual environment if it doesn't exist
if [ ! -d "backend/venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    cd backend
    python3 -m venv venv
    cd ..
fi

# Install backend dependencies
echo -e "${YELLOW}Installing backend dependencies...${NC}"
cd backend
source venv/bin/activate
pip install -r requirements.txt
cd ..

# Install frontend dependencies if node_modules doesn't exist
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    cd frontend
    npm install
    cd ..
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Stopping servers...${NC}"
    # Kill all child processes
    jobs -p | xargs -r kill 2>/dev/null
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup EXIT INT TERM

# Start backend server
echo -e "${GREEN}Starting backend server on port $BACKEND_PORT...${NC}"
cd backend
source venv/bin/activate
python main.py &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 2

# Start frontend server
echo -e "${GREEN}Starting frontend server on port $FRONTEND_PORT...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo -e "${GREEN}Development servers started!${NC}"
echo -e "Backend API: http://localhost:$BACKEND_PORT"
echo -e "Frontend UI: http://localhost:$FRONTEND_PORT"
echo -e "\nPress Ctrl+C to stop both servers"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID