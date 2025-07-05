#!/bin/bash
# Efficient test runner with memory management

set -e

# Set environment variables for memory efficiency
export PYTHONDONTWRITEBYTECODE=1
export PYTEST_XDIST_WORKER_COUNT=2
export NODE_OPTIONS="--max-old-space-size=4096"

# Activate virtual environment
source venv/bin/activate

echo "Running tests with memory optimization..."

# Function to run tests by category
run_test_category() {
    local category=$1
    local marker=$2
    echo "Running $category tests..."
    
    # Run with garbage collection and memory limits
    python -X dev -u -m pytest \
        -m "$marker" \
        --timeout=30 \
        --timeout-method=thread \
        -x \
        --tb=short \
        -v \
        2>&1 | tee test_${category}.log
    
    # Force garbage collection between test runs
    python -c "import gc; gc.collect()"
    
    # Brief pause to allow memory to be freed
    sleep 2
}

# Clear any previous test artifacts
echo "Cleaning up test artifacts..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
rm -rf .pytest_cache 2>/dev/null || true

# Run tests in batches
echo "Starting test suite..."

# 1. Run unit tests first (usually fastest and least memory intensive)
run_test_category "unit" "unit and not external"

# 2. Run integration tests (excluding external dependencies)
run_test_category "integration" "integration and not external"

# 3. Run tests with external dependencies separately
run_test_category "external" "external"

# 4. Run e2e tests last (most memory intensive)
run_test_category "e2e" "e2e"

# 5. Run any remaining tests
run_test_category "remaining" "not (unit or integration or external or e2e)"

# Generate final coverage report
echo "Generating coverage report..."
python -m coverage combine || true
python -m coverage report
python -m coverage html

echo "Test run complete!"
echo "Check individual log files for detailed results:"
ls -la test_*.log