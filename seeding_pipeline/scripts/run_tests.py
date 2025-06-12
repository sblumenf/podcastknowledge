#!/usr/bin/env python3
"""
Test Runner Script for VTT Knowledge Graph Pipeline

Provides easy commands to run different types of tests with clear reporting.
Part of Phase 5: Test Execution & Monitoring

Usage:
    ./scripts/run_tests.py unit           # Run unit tests only
    ./scripts/run_tests.py integration    # Run integration tests only  
    ./scripts/run_tests.py e2e            # Run end-to-end tests only
    ./scripts/run_tests.py all            # Run all tests (default)
    ./scripts/run_tests.py --help         # Show this help
"""

import subprocess
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class TestRunner:
    """Test execution framework with categorized test running."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'test_type': '',
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'errors': 0,
            'total_time': 0,
            'test_categories': {},
            'failures': [],
            'command_output': ''
        }
    
    def get_test_commands(self) -> Dict[str, Dict[str, str]]:
        """Define test categories and their pytest commands."""
        return {
            'unit': {
                'description': 'Unit tests - Fast, isolated component tests',
                'command': 'pytest tests/unit -v --tb=short',
                'path': 'tests/unit'
            },
            'integration': {
                'description': 'Integration tests - Multi-component tests requiring services',
                'command': 'pytest tests/integration -v --tb=short',
                'path': 'tests/integration'
            },
            'e2e': {
                'description': 'End-to-end tests - Full pipeline VTT → Knowledge Graph',
                'command': 'pytest tests/e2e -v --tb=short',
                'path': 'tests/e2e'
            },
            'processing': {
                'description': 'Processing tests - Core extraction and parsing logic',
                'command': 'pytest tests/processing -v --tb=short',
                'path': 'tests/processing'
            },
            'api': {
                'description': 'API tests - REST API endpoints and contracts',
                'command': 'pytest tests/api -v --tb=short',
                'path': 'tests/api'
            },
            'all': {
                'description': 'All tests - Complete test suite',
                'command': 'pytest -v --tb=short',
                'path': 'tests/'
            }
        }
    
    def check_prerequisites(self) -> bool:
        """Check if test environment is ready."""
        print("🔍 Checking test prerequisites...")
        
        # Check if we're in the right directory
        if not (self.project_root / "pyproject.toml").exists():
            print(f"❌ Error: Not in project root. Expected pyproject.toml in {self.project_root}")
            return False
        
        # Check if test directories exist
        tests_dir = self.project_root / "tests"
        if not tests_dir.exists():
            print(f"❌ Error: Tests directory not found at {tests_dir}")
            return False
        
        # Check if pytest is available
        try:
            result = subprocess.run(['python', '-m', 'pytest', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print("❌ Error: pytest not available. Install with: pip install pytest")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("❌ Error: pytest not found or timeout. Check Python installation.")
            return False
        
        print("✅ Prerequisites check passed")
        return True
    
    def check_test_category_exists(self, test_type: str) -> bool:
        """Check if test category directory exists."""
        commands = self.get_test_commands()
        if test_type not in commands:
            return False
        
        test_path = self.project_root / commands[test_type]['path']
        return test_path.exists()
    
    def run_command(self, command: str, test_type: str) -> Tuple[bool, str, float]:
        """Run a test command and capture results."""
        start_time = time.time()
        
        try:
            # Run in project root
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                cwd=self.project_root,
                timeout=600  # 10 minute timeout
            )
            
            elapsed_time = time.time() - start_time
            
            # Parse pytest output for detailed results
            output = result.stdout + result.stderr
            self._parse_pytest_output(output, test_type)
            
            return result.returncode == 0, output, elapsed_time
            
        except subprocess.TimeoutExpired:
            elapsed_time = time.time() - start_time
            error_msg = f"Test command timed out after 10 minutes"
            return False, error_msg, elapsed_time
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = f"Error running command: {str(e)}"
            return False, error_msg, elapsed_time
    
    def _parse_pytest_output(self, output: str, test_type: str):
        """Parse pytest output to extract test counts and failures."""
        lines = output.split('\n')
        
        # Look for pytest summary line
        for line in lines:
            if 'passed' in line or 'failed' in line or 'error' in line:
                # Parse lines like: "5 passed, 2 failed, 1 skipped in 1.23s"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'passed' and i > 0:
                        try:
                            self.results['passed'] += int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
                    elif part == 'failed' and i > 0:
                        try:
                            self.results['failed'] += int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
                    elif part == 'skipped' and i > 0:
                        try:
                            self.results['skipped'] += int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
                    elif part == 'error' and i > 0:
                        try:
                            self.results['errors'] += int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
        
        # Extract failure details
        failure_section = False
        current_failure = []
        for line in lines:
            if 'FAILURES' in line or 'ERRORS' in line:
                failure_section = True
                continue
            elif failure_section and line.startswith('='):
                if current_failure:
                    self.results['failures'].append('\n'.join(current_failure))
                    current_failure = []
                failure_section = False
            elif failure_section:
                current_failure.append(line)
        
        # Add final failure if exists
        if current_failure:
            self.results['failures'].append('\n'.join(current_failure))
    
    def run_tests(self, test_type: str = 'all') -> bool:
        """Run tests of specified type."""
        commands = self.get_test_commands()
        
        if test_type not in commands:
            print(f"❌ Error: Unknown test type '{test_type}'")
            print(f"Available types: {', '.join(commands.keys())}")
            return False
        
        # Check if test category exists
        if not self.check_test_category_exists(test_type):
            print(f"⚠️  Warning: Test directory for '{test_type}' not found, but continuing...")
        
        self.results['test_type'] = test_type
        command_info = commands[test_type]
        
        print(f"\n{'='*60}")
        print(f"Running: {command_info['description']}")
        print(f"Command: {command_info['command']}")
        print(f"Path: {command_info['path']}")
        print('='*60)
        
        success, output, elapsed_time = self.run_command(command_info['command'], test_type)
        
        self.results['total_time'] = elapsed_time
        self.results['command_output'] = output
        self.results['test_categories'][test_type] = {
            'success': success,
            'elapsed_time': elapsed_time,
            'command': command_info['command']
        }
        
        # Display results
        self._display_results(success, output, elapsed_time)
        
        return success
    
    def _display_results(self, success: bool, output: str, elapsed_time: float):
        """Display test results in a clear format."""
        print(f"\n{'='*60}")
        print("TEST RESULTS")
        print('='*60)
        
        if success:
            print("✅ TESTS PASSED")
        else:
            print("❌ TESTS FAILED")
        
        print(f"⏱️  Execution time: {elapsed_time:.2f} seconds")
        
        # Show test counts
        total_tests = self.results['passed'] + self.results['failed'] + self.results['skipped'] + self.results['errors']
        if total_tests > 0:
            print(f"\n📊 Test Summary:")
            print(f"   ✅ Passed:  {self.results['passed']}")
            print(f"   ❌ Failed:  {self.results['failed']}")
            print(f"   ⏭️  Skipped: {self.results['skipped']}")
            print(f"   🚨 Errors:  {self.results['errors']}")
            print(f"   📈 Total:   {total_tests}")
        
        # Show failures if any
        if self.results['failures']:
            print(f"\n🚨 Failure Details:")
            for i, failure in enumerate(self.results['failures'][:3], 1):  # Show first 3
                print(f"\n--- Failure {i} ---")
                print(failure[:500] + ('...' if len(failure) > 500 else ''))
            
            if len(self.results['failures']) > 3:
                print(f"\n... and {len(self.results['failures']) - 3} more failures")
        
        # Show partial output
        if output:
            print(f"\n📝 Output (last 10 lines):")
            output_lines = output.split('\n')
            for line in output_lines[-10:]:
                if line.strip():
                    print(f"   {line}")
    
    def save_results(self):
        """Save test results to file for tracking."""
        results_dir = self.project_root / "test_results"
        results_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        results_file = results_dir / f"{timestamp}_{self.results['test_type']}.json"
        
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n💾 Results saved to: {results_file}")
        return results_file
    
    def display_help(self):
        """Display help information."""
        commands = self.get_test_commands()
        
        print(__doc__)
        print("\nAvailable Test Categories:")
        print("-" * 40)
        
        for test_type, info in commands.items():
            print(f"  {test_type:12} {info['description']}")
        
        print(f"\nExamples:")
        print(f"  ./scripts/run_tests.py e2e       # Run E2E tests")
        print(f"  python scripts/run_tests.py all  # Run all tests") 
        print(f"  ./scripts/run_tests.py --help    # Show this help")


def main():
    """Main entry point."""
    # Parse arguments
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        if test_type in ['--help', '-h', 'help']:
            TestRunner().display_help()
            return 0
    else:
        test_type = 'all'
    
    # Initialize and run
    runner = TestRunner()
    
    # Check prerequisites
    if not runner.check_prerequisites():
        return 1
    
    # Run tests
    success = runner.run_tests(test_type)
    
    # Save results
    runner.save_results()
    
    # Return appropriate exit code
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())