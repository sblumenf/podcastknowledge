@echo off
REM Setup virtual environment for VTT Pipeline (Windows)
REM This script creates an isolated Python environment for the project

echo ===================================
echo VTT Pipeline Virtual Environment Setup
echo ===================================

REM Check if Python 3 is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed
    echo Please install Python 3.8 or higher
    exit /b 1
)

REM Get Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python version: %PYTHON_VERSION%

REM Check if venv already exists
if exist "venv" (
    echo Warning: Virtual environment 'venv' already exists
    set /p RECREATE="Do you want to recreate it? (y/n): "
    if /i "%RECREATE%"=="y" (
        echo Removing existing virtual environment...
        rmdir /s /q venv
    ) else (
        echo Keeping existing virtual environment
        exit /b 0
    )
)

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

REM Check if creation was successful
if not exist "venv" (
    echo Error: Failed to create virtual environment
    exit /b 1
)

echo Virtual environment created successfully!

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

REM Upgrade pip to latest version
echo Upgrading pip...
python -m pip install --upgrade pip

echo.
echo ===================================
echo Setup Complete!
echo ===================================
echo.
echo To activate the virtual environment, run:
echo   venv\Scripts\activate
echo.
echo To deactivate, run:
echo   deactivate
echo.
echo Next step: Run scripts\install.bat to install dependencies