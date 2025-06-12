#!/bin/bash
# Install dependencies for VTT Pipeline
# This script ensures virtual environment is active and installs core dependencies

echo "==================================="
echo "VTT Pipeline Dependency Installation"
echo "==================================="

# Function to check if we're in a virtual environment
check_venv() {
    if [[ -z "$VIRTUAL_ENV" ]]; then
        # Check if venv exists
        if [ -d "venv" ]; then
            echo "❌ Error: Virtual environment not activated"
            echo ""
            echo "Please activate the virtual environment first:"
            echo "  source venv/bin/activate"
            echo ""
            echo "Or create one with:"
            echo "  ./scripts/setup_venv.sh"
            return 1
        else
            echo "❌ Error: No virtual environment found"
            echo ""
            echo "Please create a virtual environment first:"
            echo "  ./scripts/setup_venv.sh"
            return 1
        fi
    fi
    return 0
}

# Function to display progress
show_progress() {
    echo "ℹ️  $1"
}

# Function to display error
show_error() {
    echo "❌ Error: $1" >&2
}

# Function to display success
show_success() {
    echo "✅ $1"
}

# Check if in virtual environment
if ! check_venv; then
    exit 1
fi

show_success "Virtual environment detected: $VIRTUAL_ENV"

# Check Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    show_error "Python 3.8 or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

show_success "Python version: $PYTHON_VERSION"

# Check if requirements-core.txt exists
if [ ! -f "requirements-core.txt" ]; then
    show_error "requirements-core.txt not found"
    echo "Please run this script from the project root directory"
    exit 1
fi

# Upgrade pip first
show_progress "Upgrading pip..."
python -m pip install --upgrade pip --quiet
if [ $? -ne 0 ]; then
    show_error "Failed to upgrade pip"
    exit 1
fi
show_success "pip upgraded successfully"

# Install core dependencies
show_progress "Installing core dependencies..."
echo ""

# Use pip with progress bar and error capture
python -m pip install -r requirements-core.txt 2>&1 | while IFS= read -r line; do
    # Filter out unimportant lines
    if [[ $line == *"Collecting"* ]] || [[ $line == *"Installing"* ]] || [[ $line == *"Successfully"* ]]; then
        echo "  $line"
    elif [[ $line == *"ERROR"* ]] || [[ $line == *"error"* ]]; then
        show_error "$line"
    fi
done

# Check if installation was successful
if python -m pip check 2>/dev/null; then
    show_success "All dependencies installed successfully!"
else
    show_error "Some dependencies may have issues"
    echo "Run 'pip check' for details"
fi

# Display installed packages
echo ""
echo "Installed packages:"
echo "-------------------"
python -m pip list | grep -E "neo4j|google-generativeai|psutil|networkx|tqdm|PyYAML|python-dotenv"

echo ""
echo "==================================="
echo "Installation Complete!"
echo "==================================="
echo ""
echo "Core dependencies are now installed."
echo ""
echo "Optional installations:"
echo "  - For API server: pip install -r requirements-api.txt"
echo "  - For all features: pip install -r requirements.txt"
echo ""
echo "To test the installation:"
echo "  python -m src.cli.cli --help"