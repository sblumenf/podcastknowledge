#!/bin/bash

# Script to run tests with coverage reporting
# Usage: ./scripts/run_coverage.sh [options]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
COVERAGE_THRESHOLD=8.43
HTML_REPORT=false
FAIL_UNDER=false
MODULE=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--html)
            HTML_REPORT=true
            shift
            ;;
        -t|--threshold)
            COVERAGE_THRESHOLD="$2"
            FAIL_UNDER=true
            shift 2
            ;;
        -m|--module)
            MODULE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  -h, --html          Generate HTML coverage report"
            echo "  -t, --threshold     Set coverage threshold (default: 8.43)"
            echo "  -m, --module        Run coverage for specific module"
            echo "  --help              Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}Running tests with coverage...${NC}"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run tests with coverage
if [ -n "$MODULE" ]; then
    echo -e "${YELLOW}Running coverage for module: $MODULE${NC}"
    pytest tests/ -k "$MODULE" --cov=src --cov-report=term-missing --cov-report=xml
else
    pytest --cov=src --cov-report=term-missing --cov-report=xml --cov-branch
fi

# Generate HTML report if requested
if [ "$HTML_REPORT" = true ]; then
    echo -e "${GREEN}Generating HTML coverage report...${NC}"
    coverage html
    echo -e "${GREEN}HTML report generated in htmlcov/index.html${NC}"
fi

# Check coverage threshold
if [ "$FAIL_UNDER" = true ]; then
    echo -e "${YELLOW}Checking coverage threshold: $COVERAGE_THRESHOLD%${NC}"
    if coverage report --fail-under=$COVERAGE_THRESHOLD; then
        echo -e "${GREEN}✅ Coverage threshold met!${NC}"
    else
        echo -e "${RED}❌ Coverage below threshold!${NC}"
        exit 1
    fi
fi

# Display coverage summary
echo -e "\n${GREEN}Coverage Summary:${NC}"
coverage report --skip-covered --sort=cover | head -20

# Show uncovered files
echo -e "\n${YELLOW}Files with lowest coverage:${NC}"
coverage report --sort=cover | grep -E "^src/" | head -10

# Calculate coverage improvement needed
CURRENT_COVERAGE=$(coverage report | tail -1 | awk '{print $4}' | sed 's/%//')
TARGET_COVERAGE=90
IMPROVEMENT_NEEDED=$(echo "$TARGET_COVERAGE - $CURRENT_COVERAGE" | bc)

echo -e "\n${GREEN}Progress Report:${NC}"
echo "Current Coverage: ${CURRENT_COVERAGE}%"
echo "Target Coverage: ${TARGET_COVERAGE}%"
echo "Improvement Needed: ${IMPROVEMENT_NEEDED}%"

# Suggest next steps
echo -e "\n${YELLOW}Next Steps:${NC}"
echo "1. Focus on modules with 0% coverage"
echo "2. Add tests for error handling paths"
echo "3. Increase test coverage for critical business logic"
echo "4. Run with -h flag to generate detailed HTML report"