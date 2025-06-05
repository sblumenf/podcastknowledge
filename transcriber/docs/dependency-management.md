# Dependency Management Guide

This guide explains how to manage Python dependencies in the Podcast Transcriber project.

## Overview

The project uses two requirements files:
- `requirements.txt` - Production dependencies only
- `requirements-dev.txt` - Development and testing dependencies

## Adding New Dependencies

### Production Dependencies

If your code needs a new library to function:

1. Add it to `requirements.txt` with a version constraint:
   ```
   package-name>=1.0.0
   ```

2. Keep dependencies minimal - only add what's essential for the application to run.

### Development Dependencies

If you need a tool for development, testing, or code quality:

1. Add it to `requirements-dev.txt`:
   ```
   package-name>=1.0.0
   ```

2. Common development dependencies include:
   - Testing: pytest, pytest-cov, pytest-mock, psutil (for performance tests)
   - Code quality: black, flake8, mypy, isort
   - Documentation: sphinx, sphinx-rtd-theme

## Installation

### For Development

Always install both files for development work:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### For Production

Only install production dependencies:
```bash
pip install -r requirements.txt
```

## Running Import Audit

To check for missing or unused dependencies:

```bash
python scripts/audit_imports.py
```

This script will:
- Scan all Python files for imports
- Identify third-party dependencies
- Show which files use each dependency

## CI/CD Considerations

GitHub Actions workflows are configured to:
- Use `requirements-dev.txt` for all test jobs
- Run import verification on every PR
- Ensure all dependencies are properly declared

### Import Verification

The CI includes an `import-verification` job that:
1. Runs the import audit script
2. Verifies all critical imports resolve
3. Tests that each module can be imported

## Common Issues

### Import Errors in Tests

If you see import errors when running tests:
1. Check you've installed `requirements-dev.txt`
2. Verify the package is listed in the correct requirements file
3. Run the import audit to identify missing dependencies

### CI/CD Failures

If CI fails due to import errors:
1. The import verification job will show which import failed
2. Add the missing package to the appropriate requirements file
3. Ensure the package name matches PyPI (e.g., `PyYAML` not `yaml`)

## Best Practices

1. **Keep dependencies minimal** - Only add what you truly need
2. **Pin major versions** - Use `>=` to allow minor updates but prevent breaking changes
3. **Separate concerns** - Production deps in `requirements.txt`, dev deps in `requirements-dev.txt`
4. **Document unusual dependencies** - Add comments explaining why a package is needed
5. **Regular audits** - Run the import audit script periodically to catch issues early

## Troubleshooting Import Errors

1. **Verify installation**:
   ```bash
   pip list | grep package-name
   ```

2. **Check import name vs package name**:
   Some packages have different import names:
   - Install: `pip install PyYAML`
   - Import: `import yaml`

3. **Check Python path**:
   ```python
   import sys
   print(sys.path)
   ```

4. **Run import audit**:
   ```bash
   python scripts/audit_imports.py
   ```

This will show all imports and their usage across the codebase.