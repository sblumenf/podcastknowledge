#!/usr/bin/env python3
"""
Simple test runner to validate the test setup.
Run this to ensure the test infrastructure is working correctly.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and report results."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print('='*60)
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ SUCCESS")
        if result.stdout:
            print(result.stdout)
    else:
        print("❌ FAILED")
        if result.stderr:
            print("Error:", result.stderr)
        if result.stdout:
            print("Output:", result.stdout)
    
    return result.returncode == 0


def main():
    """Run smoke tests and validation."""
    project_root = Path(__file__).parent.parent
    
    # Check if we're in the right directory
    if not (project_root / "pyproject.toml").exists():
        print(f"Error: Not in project root. Expected to find pyproject.toml in {project_root}")
        sys.exit(1)
    
    print(f"Project root: {project_root}")
    
    all_passed = True
    
    # 1. Check Python version
    all_passed &= run_command(
        "python3 --version",
        "Check Python version (should be 3.9+)"
    )
    
    # 2. Check test fixtures exist
    fixtures_path = project_root / "tests" / "fixtures" / "sample_transcripts.json"
    if fixtures_path.exists():
        print(f"\n✅ Test fixtures found at {fixtures_path}")
    else:
        print(f"\n❌ Test fixtures not found at {fixtures_path}")
        all_passed = False
    
    # 3. Run pytest (dry run to check it works)
    all_passed &= run_command(
        f"cd {project_root} && python3 -m pytest tests/test_smoke.py --collect-only",
        "Collect tests (dry run)"
    )
    
    # 4. Check if requirements files exist
    for req_file in ["requirements.txt", "requirements-dev.txt"]:
        req_path = project_root / req_file
        if req_path.exists():
            print(f"\n✅ {req_file} found")
        else:
            print(f"\n❌ {req_file} not found")
            all_passed = False
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    
    if all_passed:
        print("✅ All checks passed! Test infrastructure is ready.")
        print("\nNext steps:")
        print("1. Create virtual environment: python3 -m venv venv")
        print("2. Activate it: source venv/bin/activate")
        print("3. Install dependencies: pip install -r requirements-dev.txt")
        print("4. Run tests: pytest tests/test_smoke.py -v")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()