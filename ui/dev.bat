@echo off
REM Development script for the UI module on Windows
REM Starts both backend and frontend servers for development

echo Starting Podcast Knowledge UI Development Environment...

REM Check if Python is installed
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3 and add it to your PATH
    pause
    exit /b 1
)

REM Check if npm is installed
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: npm is not installed or not in PATH
    echo Please install Node.js and npm and add them to your PATH
    pause
    exit /b 1
)

REM Check if ports are available
netstat -an | findstr :8001 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo Error: Port 8001 is already in use
    echo Please stop the process using port 8001
    pause
    exit /b 1
)

netstat -an | findstr :5173 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo Error: Port 5173 is already in use
    echo Please stop the process using port 5173
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "backend\venv" (
    echo Creating Python virtual environment...
    cd backend
    python -m venv venv
    cd ..
)

REM Install backend dependencies
echo Installing backend dependencies...
cd backend
call venv\Scripts\activate.bat
pip install -r requirements.txt

REM Start backend server in new window
echo Starting backend server on port 8001...
start "Backend Server" cmd /k "venv\Scripts\activate.bat && python main.py"
cd ..

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Install frontend dependencies if needed
if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

REM Start frontend server in new window
echo Starting frontend server on port 5173...
cd frontend
start "Frontend Server" cmd /k "npm run dev"
cd ..

echo.
echo Development servers started!
echo Backend API: http://localhost:8001
echo Frontend UI: http://localhost:5173
echo.
echo Close the server windows to stop the servers
pause