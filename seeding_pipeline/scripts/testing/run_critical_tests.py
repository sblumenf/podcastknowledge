#!/usr/bin/env python3
"""Run critical path tests for the seeding pipeline."""

import subprocess
import sys
import time
from pathlib import Path


def check_docker():
    """Ensure Docker is running."""
    try:
        result = subprocess.run(
            ["docker", "ps"], 
            check=True, 
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError:
        print("ERROR: Docker is not running!")
        print("Please start Docker and try again.")
        return False
    except FileNotFoundError:
        print("ERROR: Docker is not installed!")
        print("Please install Docker from https://docs.docker.com/get-docker/")
        return False


def run_tests():
    """Run critical path tests with proper configuration."""
    # Ensure we're in the right directory
    project_root = Path(__file__).parent.parent
    
    # Check Docker first
    if not check_docker():
        return 1
    
    print("=" * 70)
    print("Running Critical Path Tests for Seeding Pipeline")
    print("=" * 70)
    print()
    
    # Define test files in order of execution
    test_files = [
        "tests/integration/test_neo4j_critical_path.py",
        "tests/integration/test_vtt_processing.py",
        "tests/integration/test_e2e_critical_path.py"
    ]
    
    # Run tests with markers
    cmd = [
        "pytest",
        "-v",
        "-m", "integration",
        "--tb=short",
        "--timeout=300",  # 5 minute timeout per test
        "-x",  # Stop on first failure
    ] + test_files
    
    print(f"Running command: {' '.join(cmd)}")
    print()
    
    start_time = time.time()
    
    # Run tests
    result = subprocess.run(cmd, cwd=project_root)
    
    elapsed = time.time() - start_time
    
    print()
    print("=" * 70)
    print(f"Test execution completed in {elapsed:.2f} seconds")
    
    if result.returncode == 0:
        print("✅ All critical path tests passed!")
    else:
        print("❌ Some tests failed. See output above for details.")
    
    print("=" * 70)
    
    return result.returncode


def run_performance_tests():
    """Run performance baseline tests separately."""
    project_root = Path(__file__).parent.parent
    
    print()
    print("=" * 70)
    print("Running Performance Baseline Tests")
    print("=" * 70)
    print()
    
    cmd = [
        "pytest",
        "-v",
        "-m", "performance",
        "--tb=short",
        "tests/performance/test_baseline_performance.py"
    ]
    
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run critical path tests")
    parser.add_argument(
        "--performance",
        action="store_true",
        help="Also run performance baseline tests"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all critical path tests including performance"
    )
    
    args = parser.parse_args()
    
    # Run main tests
    exit_code = run_tests()
    
    # Run performance tests if requested
    if exit_code == 0 and (args.performance or args.all):
        perf_code = run_performance_tests()
        exit_code = max(exit_code, perf_code)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())