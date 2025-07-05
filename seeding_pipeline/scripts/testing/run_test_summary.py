#!/usr/bin/env python3
"""Quick test summary to check test suite status."""

import subprocess
import sys
import time
import json

def run_test_category(marker, timeout=30):
    """Run tests with specific marker and return results."""
    print(f"\n{'='*60}")
    print(f"Running {marker} tests...")
    print('='*60)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "-m", marker,
        "--tb=no",
        "--no-header",
        "-q",
        "--timeout", str(timeout),
        "--json-report",
        "--json-report-file=test_report.json"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+10)
        
        # Parse results
        if result.returncode == 0:
            print(f"✓ {marker} tests: PASSED")
        else:
            print(f"✗ {marker} tests: FAILED or ERRORS")
            
        # Try to get summary from json report
        try:
            with open("test_report.json", "r") as f:
                report = json.load(f)
                summary = report.get("summary", {})
                print(f"  Passed: {summary.get('passed', 0)}")
                print(f"  Failed: {summary.get('failed', 0)}")
                print(f"  Errors: {summary.get('error', 0)}")
                print(f"  Skipped: {summary.get('skipped', 0)}")
        except:
            # Fallback to parsing output
            output_lines = result.stdout.split('\n')
            for line in output_lines[-10:]:
                if "passed" in line or "failed" in line or "error" in line:
                    print(f"  {line.strip()}")
                    
    except subprocess.TimeoutExpired:
        print(f"✗ {marker} tests: TIMEOUT after {timeout}s")
        return False
        
    return result.returncode == 0


def main():
    """Run test summary."""
    print("Test Suite Summary")
    print("="*60)
    print("Checking test categories...")
    
    categories = [
        ("unit", 60),
        ("not unit and not integration and not e2e", 30),  # Other tests
    ]
    
    all_passed = True
    
    for marker, timeout in categories:
        passed = run_test_category(marker, timeout)
        all_passed = all_passed and passed
        time.sleep(2)  # Brief pause between categories
        
    print("\n" + "="*60)
    print("OVERALL SUMMARY")
    print("="*60)
    
    if all_passed:
        print("✓ All test categories completed successfully")
    else:
        print("✗ Some test categories failed or timed out")
        
    # Get coverage summary
    print("\nCoverage Summary:")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "coverage", "report", "--format=total"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  Total Coverage: {result.stdout.strip()}%")
    except:
        print("  Coverage data not available")
        

if __name__ == "__main__":
    main()