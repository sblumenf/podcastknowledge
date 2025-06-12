#!/usr/bin/env python3
"""Script to migrate from old requirements structure to new modular structure."""

import os
import shutil
from pathlib import Path
from datetime import datetime


def backup_old_requirements():
    """Backup existing requirements files."""
    backup_dir = Path("requirements_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    backup_dir.mkdir(exist_ok=True)
    
    old_files = [
        "requirements.txt",
        "requirements-minimal.txt",
        "requirements-lean.txt",
        "requirements-dev.txt",
        "requirements-dev-minimal.txt"
    ]
    
    backed_up = []
    for file in old_files:
        if Path(file).exists():
            shutil.copy2(file, backup_dir / file)
            backed_up.append(file)
    
    print(f"✓ Backed up {len(backed_up)} files to {backup_dir}/")
    return backup_dir


def create_compatibility_links():
    """Create symbolic links for backward compatibility."""
    links = {
        "requirements.txt": "requirements/base.txt",
        "requirements-dev.txt": "requirements/dev.txt"
    }
    
    for old, new in links.items():
        if os.path.exists(old):
            os.remove(old)
        os.symlink(new, old)
        print(f"✓ Created compatibility link: {old} -> {new}")


def update_documentation():
    """Update README and other docs with new structure."""
    readme_updates = """
## Installation

### For Development
```bash
pip install -r requirements/dev.txt
```

### For Production (Minimal)
```bash
pip install -r requirements/base.txt
```

### For Production (API Server)
```bash
pip install -r requirements/api.txt
```

### For Production (All Features)
```bash
pip install -r requirements/all.txt
```
"""
    
    print("\n📝 Please update your README.md with the following installation instructions:")
    print(readme_updates)


def update_dockerfile():
    """Generate updated Dockerfile content."""
    dockerfile_content = """# Multi-stage build for optimal size
FROM python:3.9-slim as builder

WORKDIR /app

# Install only required dependencies based on build arg
ARG INSTALL_TYPE=base
COPY requirements/${INSTALL_TYPE}.txt .
RUN pip install --user --no-cache-dir -r ${INSTALL_TYPE}.txt

# Runtime stage
FROM python:3.9-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Ensure pip packages are in PATH
ENV PATH=/root/.local/bin:$PATH

CMD ["python", "-m", "src.cli.cli"]
"""
    
    print("\n🐳 Suggested Dockerfile updates:")
    print(dockerfile_content)
    print("\nBuild commands:")
    print("  docker build --build-arg INSTALL_TYPE=base -t vtt-extractor:minimal .")
    print("  docker build --build-arg INSTALL_TYPE=api -t vtt-extractor:api .")
    print("  docker build --build-arg INSTALL_TYPE=all -t vtt-extractor:full .")


def update_ci_config():
    """Generate updated CI/CD configuration."""
    github_actions = """
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
        install-type: [base, all]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Cache dependencies
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('requirements/*.txt') }}
    
    - name: Install dependencies
      run: |
        pip install -r requirements/${{ matrix.install-type }}.txt
        pip install -r requirements/dev.txt
    
    - name: Run tests
      run: pytest tests/
"""
    
    print("\n🔧 Suggested GitHub Actions configuration:")
    print(github_actions)


def verify_imports():
    """Check if all imports are satisfied by new requirements."""
    print("\n🔍 Verifying imports...")
    
    # Key packages to check
    packages_to_check = {
        "neo4j": "neo4j",
        "dotenv": "python-dotenv",
        "yaml": "PyYAML",
        "numpy": "numpy",
        "tqdm": "tqdm",
        "google.generativeai": "google-generativeai",
        "langchain_google_genai": "langchain-google-genai",
        "fastapi": "fastapi",
        "networkx": "networkx",
        "scipy": "scipy"
    }
    
    missing = []
    for import_name, package_name in packages_to_check.items():
        try:
            __import__(import_name)
            print(f"  ✓ {import_name} ({package_name})")
        except ImportError:
            missing.append(package_name)
            print(f"  ✗ {import_name} ({package_name}) - Not installed")
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("  Install with: pip install " + " ".join(missing))
    else:
        print("\n✅ All core imports verified!")


def main():
    """Run the migration process."""
    print("🚀 Starting requirements migration...\n")
    
    # Ensure requirements directory exists
    Path("requirements").mkdir(exist_ok=True)
    
    # Check if new structure already exists
    if Path("requirements/base.txt").exists():
        print("✓ New requirements structure already in place!")
    else:
        print("❌ New requirements files not found. Please create them first.")
        return
    
    # Backup old files
    backup_dir = backup_old_requirements()
    
    # Create compatibility links
    create_compatibility_links()
    
    # Show documentation updates
    update_documentation()
    update_dockerfile() 
    update_ci_config()
    
    # Verify imports
    verify_imports()
    
    print("\n✅ Migration complete!")
    print(f"   Old files backed up to: {backup_dir}/")
    print("   Please review and update your documentation and CI/CD configs.")
    print("\n📦 To test the new structure:")
    print("   pip install -r requirements/base.txt  # Minimal")
    print("   pip install -r requirements/all.txt   # Full features")


if __name__ == "__main__":
    main()