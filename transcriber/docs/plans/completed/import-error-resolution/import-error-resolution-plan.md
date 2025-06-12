# Import Error Resolution Plan

**Status**: ✅ COMPLETED  
**Completion Date**: 2025-06-05

## Executive Summary

This plan addresses the immediate psutil import error preventing test execution and implements a comprehensive audit system to identify and resolve all import-related issues across the codebase. The plan ensures development environment consistency and updates CI/CD configurations to prevent future import errors.

## Phase 1: Immediate psutil Resolution

### Task 1.1: Add psutil to development requirements
- [x] Task: Add psutil dependency to requirements-dev.txt
- Purpose: Resolve immediate import error in performance test files
- Steps:
  1. Use context7 MCP tool to check psutil documentation for version requirements
  2. Read current requirements-dev.txt file
  3. Determine appropriate psutil version (latest stable unless conflicts exist)
  4. Add psutil entry to requirements-dev.txt maintaining alphabetical order
  5. Save updated requirements-dev.txt
- Validation: 
  - File contains psutil entry
  - File maintains proper format

### Task 1.2: Verify psutil installation
- [x] Task: Install psutil in current environment
- Purpose: Confirm dependency resolves import errors
- Steps:
  1. Use context7 MCP tool to review pip documentation for best practices
  2. Activate virtual environment
  3. Run `pip install psutil` to test installation
  4. Run `python -c "import psutil; print(psutil.__version__)"` to verify
- Validation:
  - Import command executes without error
  - Version number is displayed

### Task 1.3: Test performance modules import
- [x] Task: Verify all performance test files can be imported
- Purpose: Confirm psutil resolves the identified import errors
- Steps:
  1. Use context7 MCP tool to check pytest documentation for import testing
  2. For each file: test_performance.py, test_performance_comprehensive.py, test_performance_fixed.py
  3. Run `python -c "import tests.test_performance"` for each
  4. Document any remaining import errors
- Validation:
  - All three test files import successfully
  - No ModuleNotFoundError for psutil

## Phase 2: Comprehensive Import Audit

### Task 2.1: Create import scanning script
- [x] Task: Develop utility to extract all imports from Python files
- Purpose: Systematically identify all external dependencies
- Steps:
  1. Use context7 MCP tool to research AST module for import parsing
  2. Create script that:
     - Walks through all .py files in src/ and tests/
     - Extracts import statements using AST
     - Identifies third-party vs standard library imports
     - Outputs list of unique external dependencies
  3. Save script as scripts/audit_imports.py
- Validation:
  - Script executes without errors
  - Produces list of all imports

### Task 2.2: Run import audit
- [x] Task: Execute import audit across entire codebase
- Purpose: Generate comprehensive list of all dependencies
- Steps:
  1. Use context7 MCP tool to review Python import system documentation
  2. Run audit script: `python scripts/audit_imports.py`
  3. Capture output to temporary file
  4. Parse results to identify third-party packages
- Validation:
  - Complete list of imports generated
  - Third-party packages clearly identified

### Task 2.3: Cross-reference with requirements
- [x] Task: Compare discovered imports against requirements files
- Purpose: Identify any missing dependencies
- Steps:
  1. Use context7 MCP tool to check pip documentation for package naming
  2. Read requirements.txt and requirements-dev.txt
  3. Compare audit results with both files
  4. Create list of imports not in requirements
  5. Verify each missing import is actually a third-party package
- Validation:
  - Discrepancy list created
  - False positives (standard library) filtered out

### Task 2.4: Test missing imports
- [x] Task: Verify each missing dependency causes import errors
- Purpose: Confirm which dependencies actually need to be added
- Steps:
  1. Use context7 MCP tool to review Python module documentation
  2. For each potentially missing dependency:
     - Try importing in Python interpreter
     - Document if ImportError occurs
     - Note which files use this import
  3. Create final list of confirmed missing dependencies
- Validation:
  - Each missing dependency verified
  - Usage locations documented

## Phase 3: Update Requirements Files

### Task 3.1: Add missing dependencies
- [x] Task: Update requirements-dev.txt with all missing dependencies
- Purpose: Ensure all imports can be resolved
- Steps:
  1. Use context7 MCP tool to check each package's documentation
  2. For each confirmed missing dependency:
     - Research appropriate version constraints
     - Add to requirements-dev.txt in alphabetical order
     - Include comment if dependency is for specific test type
  3. Save updated requirements-dev.txt
- Validation:
  - All missing dependencies added
  - File maintains proper format

### Task 3.2: Test full installation
- [x] Task: Verify all dependencies install correctly
- Purpose: Ensure no conflicts between packages
- Steps:
  1. Use context7 MCP tool to review pip conflict resolution docs
  2. Create fresh virtual environment
  3. Run `pip install -r requirements-dev.txt`
  4. Document any conflicts or errors
  5. Resolve conflicts by adjusting version constraints
- Validation:
  - Installation completes without errors
  - No unresolved conflicts

## Phase 4: CI/CD Configuration Updates

### Task 4.1: Audit GitHub Actions workflows
- [x] Task: Review all workflow files for dependency installation
- Purpose: Identify where requirements need updating
- Steps:
  1. Use context7 MCP tool to review GitHub Actions documentation
  2. List all .yml files in .github/workflows/
  3. For each workflow:
     - Check if it installs Python dependencies
     - Note which requirements file is used
     - Identify if it runs tests
  4. Create list of workflows needing updates
- Validation:
  - All workflows reviewed
  - Update locations identified

### Task 4.2: Update test workflows
- [x] Task: Ensure CI/CD uses requirements-dev.txt for test runs
- Purpose: Prevent import errors in CI/CD pipeline
- Steps:
  1. Use context7 MCP tool to check GitHub Actions Python setup docs
  2. For each test-related workflow:
     - Verify it uses requirements-dev.txt not requirements.txt
     - Update pip install commands if needed
     - Ensure virtual environment is activated properly
  3. Commit workflow changes
- Validation:
  - All test workflows use requirements-dev.txt
  - Installation steps are correct

### Task 4.3: Add import verification job
- [x] Task: Create CI job to verify all imports work
- Purpose: Catch import errors before they reach main branch
- Steps:
  1. Use context7 MCP tool to review GitHub Actions job syntax
  2. Create new job in test workflow:
     - Install requirements-dev.txt
     - Run import audit script
     - Verify all imports resolve
  3. Set job to run on all PRs
- Validation:
  - Job definition is syntactically correct
  - Job would catch import errors

## Phase 5: Documentation and Prevention

### Task 5.1: Document dependency management process
- [x] Task: Create guide for adding new dependencies
- Purpose: Prevent future import errors
- Steps:
  1. Use context7 MCP tool to review documentation best practices
  2. Create docs/dependency-management.md with:
     - How to add new dependencies
     - When to use requirements.txt vs requirements-dev.txt
     - How to run import audit
     - CI/CD considerations
  3. Include examples and common pitfalls
- Validation:
  - Documentation is clear and complete
  - Includes actionable steps

### Task 5.2: Update README with setup instructions
- [x] Task: Ensure README covers development dependency installation
- Purpose: Help developers avoid import errors
- Steps:
  1. Use context7 MCP tool to review README best practices
  2. Read current README.md
  3. Add or update development setup section:
     - Specify to use requirements-dev.txt for development
     - Include virtual environment setup
     - Add troubleshooting for import errors
  4. Save updated README.md
- Validation:
  - Setup instructions are clear
  - Development requirements explicitly mentioned

## Success Criteria

1. **Immediate Resolution**: psutil import error is resolved and all performance tests can be collected
2. **Comprehensive Coverage**: All Python imports across the codebase are audited and verified
3. **Requirements Accuracy**: requirements-dev.txt contains all necessary dependencies for development and testing
4. **CI/CD Consistency**: GitHub Actions workflows use correct requirements files and won't fail due to import errors
5. **Future Prevention**: Documentation exists to prevent similar issues and guide proper dependency management

## Technology Requirements

### Existing Technologies (No Approval Needed):
- Python standard library (ast, os, sys)
- pip (already in use)
- pytest (already in use)
- GitHub Actions (already in use)

### New Technologies (Requires Approval):
- psutil: System and process utilities library for Python
  - **Purpose**: Required by performance test files for memory and CPU monitoring
  - **License**: BSD
  - **Approval Status**: Pre-approved by user for this specific case

No other new technologies are required for this plan.