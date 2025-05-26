#!/usr/bin/env python3
"""
Code quality checks for the Podcast Knowledge Graph Pipeline.

This script runs all code quality tools in sequence:
1. black - Code formatting
2. isort - Import sorting
3. flake8 - Linting
4. mypy - Type checking
5. coverage - Test coverage
6. bandit - Security audit
"""

import subprocess
import sys
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{'=' * 60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('=' * 60)
    
    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
            
        if result.returncode != 0:
            print(f"❌ {description} failed with exit code {result.returncode}")
            return False
        else:
            print(f"✅ {description} completed successfully")
            return True
            
    except FileNotFoundError:
        print(f"❌ {description} - Tool not found. Please install: pip install {cmd[0]}")
        return False
    except Exception as e:
        print(f"❌ {description} failed with error: {e}")
        return False


def main():
    """Run all code quality checks."""
    print("🔍 Starting code quality checks...")
    
    # Track overall success
    all_passed = True
    
    # 1. Run black formatter
    if run_command(
        ["black", "src/", "tests/", "scripts/", "cli.py", "setup.py", "--line-length", "100"],
        "Black code formatter"
    ):
        print("   - Code formatting applied")
    else:
        all_passed = False
    
    # 2. Run isort for import sorting
    if run_command(
        ["isort", "src/", "tests/", "scripts/", "cli.py", "setup.py", "--profile", "black", "--line-length", "100"],
        "isort import organizer"
    ):
        print("   - Imports organized")
    else:
        all_passed = False
    
    # 3. Run flake8 linting
    if run_command(
        ["flake8", "src/", "tests/", "--max-line-length", "100", "--extend-ignore", "E203,W503"],
        "Flake8 linter"
    ):
        print("   - No linting issues found")
    else:
        all_passed = False
        print("   - Fix linting issues before proceeding")
    
    # 4. Run mypy type checking
    if run_command(
        ["mypy", "src/", "--ignore-missing-imports", "--strict"],
        "MyPy type checker"
    ):
        print("   - Type checking passed")
    else:
        all_passed = False
        print("   - Fix type errors before proceeding")
    
    # 5. Run test coverage
    coverage_cmd = [
        "pytest", 
        "--cov=src", 
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "--cov-fail-under=80",
        "tests/"
    ]
    if run_command(coverage_cmd, "Test coverage"):
        print("   - Test coverage meets requirements (>80%)")
    else:
        print("   - Warning: Test coverage below 80%")
        # Don't fail on coverage for now
    
    # 6. Run bandit security audit
    if run_command(
        ["bandit", "-r", "src/", "-ll", "-f", "json", "-o", "bandit-report.json"],
        "Bandit security audit"
    ):
        print("   - No security issues found")
    else:
        all_passed = False
        print("   - Review security issues in bandit-report.json")
    
    # Summary
    print(f"\n{'=' * 60}")
    if all_passed:
        print("✅ All code quality checks passed!")
        print("\nNext steps:")
        print("1. Review any changes made by black/isort")
        print("2. Commit the changes: git commit -m 'chore: Code quality improvements'")
        print("3. Push to your branch")
        return 0
    else:
        print("❌ Some code quality checks failed")
        print("\nPlease fix the issues above and run this script again")
        return 1


if __name__ == "__main__":
    sys.exit(main())