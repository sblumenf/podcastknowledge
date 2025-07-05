#!/bin/bash
# Setup virtual environment for VTT Pipeline
# This script creates an isolated Python environment for the project

echo "==================================="
echo "VTT Pipeline Virtual Environment Setup"
echo "==================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Get Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python version: $PYTHON_VERSION"

# Check if venv already exists
if [ -d "venv" ]; then
    echo "Warning: Virtual environment 'venv' already exists"
    read -p "Do you want to recreate it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing virtual environment..."
        rm -rf venv
    else
        echo "Keeping existing virtual environment"
        exit 0
    fi
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Check if creation was successful
if [ ! -d "venv" ]; then
    echo "Error: Failed to create virtual environment"
    exit 1
fi

echo "Virtual environment created successfully!"

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip to latest version
echo "Upgrading pip..."
python -m pip install --upgrade pip

echo ""
echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To deactivate, run:"
echo "  deactivate"
echo ""
echo "Next step: Run ./scripts/install.sh to install dependencies"