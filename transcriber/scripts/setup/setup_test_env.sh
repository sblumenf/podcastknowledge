#!/bin/bash
# Setup script for test environment

set -e

echo "Setting up test environment for Podcast Transcriber..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    print_warning "Virtual environment not found. Creating one..."
    python3 -m venv venv
    print_status "Virtual environment created"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install test dependencies
print_status "Installing test dependencies..."
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-mock pytest-cov pytest-timeout

# Optional: Install additional test tools
read -p "Install additional test tools (pytest-xdist, pytest-watch, coverage)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Installing additional test tools..."
    pip install pytest-xdist pytest-watch coverage[toml]
fi

# Create necessary directories
print_status "Creating test directories..."
mkdir -p data/test_transcripts
mkdir -p logs/test_logs
mkdir -p htmlcov

# Copy test environment file if it doesn't exist
if [ ! -f ".env" ]; then
    if [ -f ".env.test" ]; then
        print_status "Copying test environment variables..."
        cp .env.test .env
    else
        print_warning ".env.test not found. Please set up environment variables."
    fi
fi

# Clean any existing test artifacts
print_status "Cleaning test artifacts..."
rm -rf .pytest_cache
rm -rf .coverage
rm -f tests.log
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Run a simple test to verify setup
print_status "Verifying test setup..."
if pytest --collect-only -q > /dev/null 2>&1; then
    TEST_COUNT=$(pytest --collect-only -q | grep -E "^<" | wc -l)
    print_status "Test setup complete! Found $TEST_COUNT tests."
else
    print_error "Test collection failed. Please check your setup."
    exit 1
fi

# Display helpful commands
echo
echo "Test environment setup complete! 🎉"
echo
echo "Useful commands:"
echo "  make test           - Run all tests"
echo "  make test-fast      - Run fast tests only"
echo "  make coverage       - Run tests with coverage"
echo "  make test-watch     - Run tests in watch mode"
echo "  make clean-test     - Clean test artifacts"
echo
echo "Or use pytest directly:"
echo "  pytest              - Run all tests"
echo "  pytest -m unit      - Run unit tests only"
echo "  pytest -k keyword   - Run tests matching keyword"
echo "  pytest -x           - Stop on first failure"
echo "  pytest --lf         - Run last failed tests"
echo
print_status "Happy testing!"