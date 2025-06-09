#!/usr/bin/env python3
"""Run all API key rotation tests."""

import os
import sys
import subprocess
from pathlib import Path

def run_test(test_file: str, description: str) -> bool:
    """Run a single test file."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print('='*60)
    
    test_path = Path(__file__).parent / test_file
    
    try:
        result = subprocess.run(
            [sys.executable, str(test_path)],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print(f"✅ {description} - PASSED")
            return True
        else:
            print(f"❌ {description} - FAILED")
            return False
            
    except Exception as e:
        print(f"❌ Error running {test_file}: {e}")
        return False


def main():
    """Run all rotation tests."""
    print("API Key Rotation Test Suite")
    print("="*60)
    
    # Define test files and descriptions
    tests = [
        ("test_basic_rotation.py", "Basic Rotation Tests"),
        ("test_service_integration.py", "Service Integration Tests"),
        ("test_stress_rotation.py", "Stress Tests"),
        ("test_real_integration.py", "Real API Integration Tests (Optional)")
    ]
    
    results = []
    
    # Run each test
    for test_file, description in tests:
        success = run_test(test_file, description)
        results.append((description, success))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for description, success in results:
        status = "PASSED" if success else "FAILED"
        symbol = "✅" if success else "❌"
        print(f"{symbol} {description}: {status}")
        
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {len(tests)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())