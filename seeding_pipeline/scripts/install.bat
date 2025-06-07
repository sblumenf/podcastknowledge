@echo off
REM Install dependencies for VTT Pipeline
REM This script ensures virtual environment is active and installs core dependencies

echo ===================================
echo VTT Pipeline Dependency Installation
echo ===================================

REM Function to check if we're in a virtual environment
if "%VIRTUAL_ENV%"=="" (
    if exist "venv\Scripts\activate.bat" (
        echo Error: Virtual environment not activated
        echo.
        echo Please activate the virtual environment first:
        echo   venv\Scripts\activate
        echo.
        echo Or create one with:
        echo   scripts\setup_venv.bat
        exit /b 1
    ) else (
        echo Error: No virtual environment found
        echo.
        echo Please create a virtual environment first:
        echo   scripts\setup_venv.bat
        exit /b 1
    )
)

echo [OK] Virtual environment detected: %VIRTUAL_ENV%

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python version: %PYTHON_VERSION%

REM Check if requirements-core.txt exists
if not exist "requirements-core.txt" (
    echo Error: requirements-core.txt not found
    echo Please run this script from the project root directory
    exit /b 1
)

REM Upgrade pip first
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo Error: Failed to upgrade pip
    exit /b 1
)
echo [OK] pip upgraded successfully

REM Install core dependencies
echo [INFO] Installing core dependencies...
echo.

python -m pip install -r requirements-core.txt
if errorlevel 1 (
    echo Error: Failed to install dependencies
    exit /b 1
)

REM Check if installation was successful
python -m pip check >nul 2>&1
if errorlevel 0 (
    echo [OK] All dependencies installed successfully!
) else (
    echo Warning: Some dependencies may have issues
    echo Run 'pip check' for details
)

REM Display installed packages
echo.
echo Installed packages:
echo -------------------
python -m pip list | findstr /I "neo4j google-generativeai psutil networkx tqdm PyYAML python-dotenv"

echo.
echo ===================================
echo Installation Complete!
echo ===================================
echo.
echo Core dependencies are now installed.
echo.
echo Optional installations:
echo   - For API server: pip install -r requirements-api.txt
echo   - For all features: pip install -r requirements.txt
echo.
echo To test the installation:
echo   python -m src.cli.cli --help