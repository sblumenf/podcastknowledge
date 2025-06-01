#!/bin/bash
# Development Docker entrypoint script

set -e

# Set default test environment variables if not provided
export GEMINI_API_KEY_1="${GEMINI_API_KEY_1:-test_key_1}"
export GEMINI_API_KEY_2="${GEMINI_API_KEY_2:-test_key_2}"
export PODCAST_TEST_MODE="${PODCAST_TEST_MODE:-true}"
export PODCAST_MOCK_API_CALLS="${PODCAST_MOCK_API_CALLS:-true}"

# Create test directories
mkdir -p data/test_transcripts logs/test_logs

# If no command provided, run tests
if [ $# -eq 0 ]; then
    echo "Running test suite..."
    exec pytest -v
fi

# Handle common development commands
case "$1" in
    test)
        shift
        exec pytest "$@"
        ;;
    test-fast)
        shift
        exec pytest -m "not slow" "$@"
        ;;
    test-coverage)
        shift
        exec pytest --cov=src --cov-report=term-missing "$@"
        ;;
    lint)
        echo "Running linting checks..."
        black --check src tests
        isort --check-only src tests
        flake8 src tests --max-line-length=100 --ignore=E203,W503
        ;;
    format)
        echo "Formatting code..."
        black src tests
        isort src tests
        ;;
    shell)
        exec /bin/bash
        ;;
    transcribe)
        shift
        exec python -m src.cli transcribe "$@"
        ;;
    *)
        exec "$@"
        ;;
esac