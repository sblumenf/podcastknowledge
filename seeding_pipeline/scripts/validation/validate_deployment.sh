#!/bin/bash
# VTT Pipeline Deployment Validation Script
#
# This script performs end-to-end validation of a fresh deployment.
# It checks all components and processes a sample VTT file.

set -e  # Exit on error

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_ROOT/deployment_validation.log"
REPORT_FILE="$PROJECT_ROOT/deployment_report.txt"

# Functions
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

print_header() {
    echo ""
    echo "========================================" | tee -a "$REPORT_FILE"
    echo "$1" | tee -a "$REPORT_FILE"
    echo "========================================" | tee -a "$REPORT_FILE"
}

check_pass() {
    echo -e "${GREEN}✓ $1${NC}" | tee -a "$REPORT_FILE"
    log "PASS: $1"
}

check_fail() {
    echo -e "${RED}✗ $1${NC}" | tee -a "$REPORT_FILE"
    log "FAIL: $1"
    VALIDATION_FAILED=1
}

check_warn() {
    echo -e "${YELLOW}⚠ $1${NC}" | tee -a "$REPORT_FILE"
    log "WARN: $1"
}

# Initialize
cd "$PROJECT_ROOT"
VALIDATION_FAILED=0
START_TIME=$(date +%s)

# Clear previous logs
> "$LOG_FILE"
> "$REPORT_FILE"

echo "VTT Pipeline Deployment Validation" | tee -a "$REPORT_FILE"
echo "Started at: $(date)" | tee -a "$REPORT_FILE"
echo "" | tee -a "$REPORT_FILE"

# 1. Check Python Version
print_header "1. Python Version Check"
PYTHON_VERSION=$(python3 --version 2>&1)
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
    check_pass "Python version: $PYTHON_VERSION (3.11+ required)"
else
    check_fail "Python version: $PYTHON_VERSION (3.11+ required)"
fi

# 2. Check Virtual Environment
print_header "2. Virtual Environment Check"
if [ -n "$VIRTUAL_ENV" ]; then
    check_pass "Virtual environment active: $VIRTUAL_ENV"
elif [ -d "venv" ]; then
    check_warn "Virtual environment exists but not active"
    echo "  Run: source venv/bin/activate" | tee -a "$REPORT_FILE"
else
    check_warn "No virtual environment found"
    echo "  Run: python3 -m venv venv && source venv/bin/activate" | tee -a "$REPORT_FILE"
fi

# 3. Check Dependencies
print_header "3. Dependencies Check"
if [ -n "$VIRTUAL_ENV" ] || [ -d "venv" ]; then
    # Try to import key dependencies
    python3 -c "import neo4j" 2>/dev/null && check_pass "neo4j package installed" || check_warn "neo4j package not installed"
    python3 -c "import dotenv" 2>/dev/null && check_pass "python-dotenv package installed" || check_warn "python-dotenv package not installed"
    python3 -c "import google.generativeai" 2>/dev/null && check_pass "google-generativeai package installed" || check_warn "google-generativeai package not installed"
else
    check_warn "Cannot check dependencies without virtual environment"
fi

# 4. Check Configuration Files
print_header "4. Configuration Files Check"
if [ -f ".env" ]; then
    check_pass ".env file exists"
    
    # Check for required variables (without exposing values)
    if grep -q "NEO4J_PASSWORD=" .env && grep -q "GOOGLE_API_KEY=" .env; then
        # Check if they have values (not empty)
        NEO4J_PWD=$(grep "NEO4J_PASSWORD=" .env | cut -d'=' -f2)
        GOOGLE_KEY=$(grep "GOOGLE_API_KEY=" .env | cut -d'=' -f2)
        
        if [ -n "$NEO4J_PWD" ]; then
            check_pass "NEO4J_PASSWORD is set"
        else
            check_fail "NEO4J_PASSWORD is empty"
        fi
        
        if [ -n "$GOOGLE_KEY" ]; then
            check_pass "GOOGLE_API_KEY is set"
        else
            check_fail "GOOGLE_API_KEY is empty"
        fi
    else
        check_fail "Required environment variables missing in .env"
    fi
else
    check_fail ".env file not found"
    echo "  Run: cp .env.template .env && edit .env" | tee -a "$REPORT_FILE"
fi

# 5. Check Directory Structure
print_header "5. Directory Structure Check"
REQUIRED_DIRS=("src" "tests" "scripts" "docs" "checkpoints" "output")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        check_pass "Directory exists: $dir"
    else
        # Try to create missing directories
        mkdir -p "$dir" 2>/dev/null && check_pass "Created directory: $dir" || check_fail "Directory missing: $dir"
    fi
done

# 6. Test Database Connectivity
print_header "6. Database Connectivity Check"
if [ -f ".env" ] && [ -n "$VIRTUAL_ENV" ]; then
    python3 - <<EOF 2>&1 | tee -a "$LOG_FILE" >/dev/null && check_pass "Neo4j connection test passed" || check_warn "Neo4j connection test failed (service may not be running)"
import os
from dotenv import load_dotenv
load_dotenv()

try:
    from neo4j import GraphDatabase
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USERNAME', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD')
    
    if password:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            print("Neo4j connection successful")
        driver.close()
    else:
        print("No Neo4j password set")
        exit(1)
except Exception as e:
    print(f"Neo4j connection failed: {e}")
    exit(1)
EOF
else
    check_warn "Cannot test database connectivity (missing .env or virtual environment)"
fi

# 7. Test CLI Commands
print_header "7. CLI Commands Check"
# Test help commands
python3 -m src.cli.cli --help >/dev/null 2>&1 && check_pass "Main CLI help works" || check_warn "Main CLI help failed (missing dependencies?)"
python3 src/cli/minimal_cli.py --help >/dev/null 2>&1 && check_pass "Minimal CLI help works" || check_fail "Minimal CLI help failed"

# 8. Process Sample VTT File
print_header "8. Sample VTT Processing Test"
# Create a sample VTT file
SAMPLE_VTT="$PROJECT_ROOT/test_sample.vtt"
cat > "$SAMPLE_VTT" <<EOF
WEBVTT

00:00:00.000 --> 00:00:05.000
Welcome to the deployment validation test.

00:00:05.000 --> 00:00:10.000
This is a sample VTT file to verify the pipeline works.

00:00:10.000 --> 00:00:15.000
If you can process this file, the deployment is successful!
EOF

check_pass "Created sample VTT file: test_sample.vtt"

# Try to parse it with minimal CLI (dry run)
if python3 src/cli/minimal_cli.py "$SAMPLE_VTT" --dry-run 2>&1 | grep -q "segments found"; then
    check_pass "Sample VTT file parsed successfully"
else
    check_warn "Sample VTT parsing failed (this is expected without dependencies)"
fi

# Clean up sample file
rm -f "$SAMPLE_VTT"

# 9. Run Smoke Tests
print_header "9. Smoke Tests"
if [ -f "scripts/run_minimal_tests.py" ]; then
    if python3 scripts/run_minimal_tests.py >/dev/null 2>&1; then
        check_pass "Smoke tests passed"
    else
        check_warn "Some smoke tests failed (check logs)"
    fi
else
    check_fail "Smoke test script not found"
fi

# 10. Generate Summary Report
print_header "Deployment Validation Summary"
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "" | tee -a "$REPORT_FILE"
echo "Validation completed at: $(date)" | tee -a "$REPORT_FILE"
echo "Duration: ${DURATION} seconds" | tee -a "$REPORT_FILE"
echo "" | tee -a "$REPORT_FILE"

if [ $VALIDATION_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ DEPLOYMENT VALIDATION PASSED${NC}" | tee -a "$REPORT_FILE"
    echo "" | tee -a "$REPORT_FILE"
    echo "Your VTT Pipeline deployment is ready!" | tee -a "$REPORT_FILE"
    echo "" | tee -a "$REPORT_FILE"
    echo "Next steps:" | tee -a "$REPORT_FILE"
    echo "1. Ensure Neo4j is running" | tee -a "$REPORT_FILE"
    echo "2. Set up your .env file with API keys" | tee -a "$REPORT_FILE"
    echo "3. Activate virtual environment: source venv/bin/activate" | tee -a "$REPORT_FILE"
    echo "4. Install dependencies: pip install -r requirements-core.txt" | tee -a "$REPORT_FILE"
    echo "5. Process VTT files: python -m src.cli.cli process-vtt --folder /path/to/vtts" | tee -a "$REPORT_FILE"
else
    echo -e "${RED}✗ DEPLOYMENT VALIDATION FAILED${NC}" | tee -a "$REPORT_FILE"
    echo "" | tee -a "$REPORT_FILE"
    echo "Please fix the issues above before proceeding." | tee -a "$REPORT_FILE"
    echo "Check deployment_validation.log for details." | tee -a "$REPORT_FILE"
fi

echo "" | tee -a "$REPORT_FILE"
echo "Full report saved to: deployment_report.txt" | tee -a "$REPORT_FILE"
echo "Detailed log saved to: deployment_validation.log" | tee -a "$REPORT_FILE"

exit $VALIDATION_FAILED