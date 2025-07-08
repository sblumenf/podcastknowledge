#!/bin/bash

# manage_ui_servers.sh - Manage UI frontend and backend servers
# This script checks if the servers are running and restarts or starts them as needed

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
FRONTEND_PORT=5173
BACKEND_PORT=8000
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_DIR="$SCRIPT_DIR/backend"
LOG_DIR="$SCRIPT_DIR/logs"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to print colored output
print_status() {
    echo -e "${2}${1}${NC}"
}

# Function to check if a port is in use
check_port() {
    local port=$1
    
    # Try lsof first
    if command -v lsof &> /dev/null; then
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            return 0
        else
            return 1
        fi
    # Try ss as fallback
    elif command -v ss &> /dev/null; then
        if ss -tuln | grep -q ":$port "; then
            return 0
        else
            return 1
        fi
    # Try netstat as last resort
    elif command -v netstat &> /dev/null; then
        if netstat -tuln | grep -q ":$port "; then
            return 0
        else
            return 1
        fi
    else
        print_status "Warning: No suitable command found to check ports (lsof, ss, or netstat)" "$YELLOW"
        return 1
    fi
}

# Function to get PID of process on port
get_pid_on_port() {
    local port=$1
    
    # Try lsof first
    if command -v lsof &> /dev/null; then
        lsof -Pi :$port -sTCP:LISTEN -t 2>/dev/null | head -n 1
    # Try ss with more complex parsing
    elif command -v ss &> /dev/null; then
        ss -tlnp 2>/dev/null | grep ":$port " | awk -F'pid=' '{print $2}' | cut -d',' -f1 | head -n 1
    else
        echo ""
    fi
}

# Function to kill process on port
kill_process_on_port() {
    local port=$1
    local service=$2
    
    print_status "Checking for existing $service on port $port..." "$BLUE"
    
    if check_port $port; then
        local pid=$(get_pid_on_port $port)
        if [ ! -z "$pid" ]; then
            print_status "Found $service running (PID: $pid). Stopping..." "$YELLOW"
            kill -9 $pid 2>/dev/null || true
            sleep 2
            
            # Verify it's stopped
            if check_port $port; then
                print_status "Failed to stop $service on port $port" "$RED"
                return 1
            else
                print_status "$service stopped successfully" "$GREEN"
            fi
        else
            print_status "Process on port $port found but couldn't get PID. Please stop it manually." "$RED"
            return 1
        fi
    else
        print_status "No $service running on port $port" "$BLUE"
    fi
    
    return 0
}

# Function to start frontend server
start_frontend() {
    print_status "\nStarting Frontend Server..." "$BLUE"
    
    cd "$FRONTEND_DIR"
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        print_status "Installing frontend dependencies..." "$YELLOW"
        npm install
    fi
    
    # Start the frontend server in background
    print_status "Starting Vite dev server on port $FRONTEND_PORT..." "$BLUE"
    nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
    local frontend_pid=$!
    
    # Give it time to start
    sleep 3
    
    # Check if it started successfully
    if check_port $FRONTEND_PORT; then
        print_status "Frontend server started successfully (PID: $frontend_pid)" "$GREEN"
        print_status "Frontend URL: http://localhost:$FRONTEND_PORT" "$GREEN"
        return 0
    else
        print_status "Failed to start frontend server. Check $LOG_DIR/frontend.log for details" "$RED"
        return 1
    fi
}

# Function to start backend server
start_backend() {
    print_status "\nStarting Backend Server..." "$BLUE"
    
    cd "$BACKEND_DIR"
    
    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        print_status "Creating Python virtual environment..." "$YELLOW"
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Check if dependencies are installed
    if ! python -c "import fastapi" 2>/dev/null; then
        print_status "Installing backend dependencies..." "$YELLOW"
        pip install -r requirements.txt
    fi
    
    # Start the backend server in background
    print_status "Starting FastAPI server on port $BACKEND_PORT..." "$BLUE"
    nohup uvicorn main:app --reload --port $BACKEND_PORT > "$LOG_DIR/backend.log" 2>&1 &
    local backend_pid=$!
    
    # Give it time to start
    sleep 5
    
    # Check if it started successfully
    if check_port $BACKEND_PORT; then
        print_status "Backend server started successfully (PID: $backend_pid)" "$GREEN"
        print_status "Backend URL: http://localhost:$BACKEND_PORT" "$GREEN"
        print_status "API docs: http://localhost:$BACKEND_PORT/docs" "$GREEN"
        return 0
    else
        print_status "Failed to start backend server. Check $LOG_DIR/backend.log for details" "$RED"
        return 1
    fi
}

# Main execution
main() {
    print_status "=== UI Server Management Script ===" "$BLUE"
    print_status "This script will manage both frontend and backend servers" "$BLUE"
    echo
    
    # Kill existing processes if running
    kill_process_on_port $FRONTEND_PORT "Frontend"
    kill_process_on_port $BACKEND_PORT "Backend"
    
    # Start servers
    if start_backend; then
        if start_frontend; then
            print_status "\n✓ Both servers are now running!" "$GREEN"
            print_status "\nServer Status:" "$BLUE"
            print_status "- Frontend: http://localhost:$FRONTEND_PORT" "$GREEN"
            print_status "- Backend:  http://localhost:$BACKEND_PORT" "$GREEN"
            print_status "- API Docs: http://localhost:$BACKEND_PORT/docs" "$GREEN"
            print_status "\nLogs:" "$BLUE"
            print_status "- Frontend: $LOG_DIR/frontend.log" "$NC"
            print_status "- Backend:  $LOG_DIR/backend.log" "$NC"
            print_status "\nTo stop servers, use:" "$BLUE"
            print_status "  kill -9 \$(lsof -ti:$FRONTEND_PORT)" "$NC"
            print_status "  kill -9 \$(lsof -ti:$BACKEND_PORT)" "$NC"
        else
            print_status "\n✗ Frontend failed to start, but backend is running" "$RED"
            exit 1
        fi
    else
        print_status "\n✗ Backend failed to start" "$RED"
        exit 1
    fi
}

# Run main function
main

# Deactivate virtual environment
deactivate 2>/dev/null || true