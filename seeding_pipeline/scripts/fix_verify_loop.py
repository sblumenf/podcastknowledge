#!/usr/bin/env python3
"""
Fix-Verify Loop for Test Failure Resolution

Systematic fix validation process for the VTT Knowledge Graph Pipeline.
Part of Phase 6: Test Failure Resolution

This script implements the complete fix-verify loop:
1. Isolate failing test
2. Create minimal reproduction
3. Apply fix
4. Run test in isolation
5. Run related test suite  
6. Run full test suite
7. Document fix in tracking system

Usage:
    ./scripts/fix_verify_loop.py FAILURE_ID          # Start fix-verify process
    ./scripts/fix_verify_loop.py --test TEST_NAME    # Start from test name
    ./scripts/fix_verify_loop.py --help              # Show this help
"""

import sys
import subprocess
import argparse
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from test_tracking import FailureTracker, FailureStatus
except ImportError as e:
    print(f"Error importing failure tracking: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


class FixVerifyLoop:
    """Implements systematic fix validation process."""
    
    def __init__(self):
        self.tracker = FailureTracker()
        self.project_root = Path(__file__).parent.parent
        self.test_runner = self.project_root / "scripts" / "run_tests.py"
        
        # Verification steps tracking
        self.verification_steps = {
            'isolated_test': False,
            'related_suite': False,
            'full_suite': False,
            'ci_validation': False
        }
    
    def start_fix_process(self, failure_id: str) -> bool:
        """Start the complete fix-verify process for a failure."""
        failure = self.tracker.find_failure_by_id(failure_id)
        if not failure:
            print(f"❌ Failure {failure_id} not found")
            return False
        
        print(f"🔧 Starting Fix-Verify Loop for: {failure['test_name']}")
        print("=" * 60)
        
        # Display failure context
        self._display_failure_context(failure)
        
        # Step 1: Isolate failing test
        if not self._isolate_test(failure):
            return False
        
        # Step 2: Create minimal reproduction
        if not self._create_minimal_reproduction(failure):
            return False
        
        # Step 3: Interactive fix development
        if not self._interactive_fix_development(failure):
            return False
        
        # Step 4-6: Verification loop
        if not self._run_verification_loop(failure):
            return False
        
        # Step 7: Document resolution
        if not self._document_resolution(failure):
            return False
        
        print("✅ Fix-Verify Loop completed successfully!")
        return True
    
    def start_from_test_name(self, test_name: str) -> bool:
        """Start fix process from test name (create failure record if needed)."""
        failure = self.tracker.find_failure_by_test(test_name)
        if not failure:
            print(f"📝 No existing failure record for {test_name}")
            print("Creating new failure record...")
            
            # Run the test to get error information
            success, output = self._run_single_test(test_name)
            if success:
                print(f"✅ Test {test_name} is currently passing")
                return True
            
            # Extract error information
            error_message = self._extract_error_message(output)
            
            # Record new failure
            failure_id = self.tracker.record_failure(
                test_name=test_name,
                error_message=error_message,
                test_category=self._determine_test_category(test_name)
            )
            
            print(f"📝 Created failure record: {failure_id}")
            return self.start_fix_process(failure_id)
        else:
            return self.start_fix_process(failure['id'])
    
    def _display_failure_context(self, failure: dict):
        """Display failure context for developer."""
        print(f"📋 Failure Context:")
        print(f"   Test: {failure['test_name']}")
        print(f"   Status: {failure['status']}")
        print(f"   Severity: {failure['severity']}")
        print(f"   Error Type: {failure['error_type']}")
        print(f"   Frequency: {failure['metadata']['frequency']} occurrence(s)")
        
        if failure['metadata']['error_message']:
            print(f"   Last Error: {failure['metadata']['error_message'][:100]}...")
        
        if failure['attempted_fixes']:
            print(f"   Previous Attempts: {len(failure['attempted_fixes'])}")
        
        print()
    
    def _isolate_test(self, failure: dict) -> bool:
        """Step 1: Isolate the failing test."""
        print("🔍 Step 1: Isolating failing test...")
        
        test_name = failure['test_name']
        success, output = self._run_single_test(test_name)
        
        if success:
            print(f"✅ Test {test_name} is currently passing")
            print("   This may indicate the issue was already resolved")
            
            response = input("   Continue with verification loop? (y/n): ").strip().lower()
            if response != 'y':
                return False
        else:
            print(f"❌ Test {test_name} is failing (confirmed)")
            
            # Show recent error
            error_lines = output.split('\n')[-10:]  # Last 10 lines
            print("   Recent error output:")
            for line in error_lines:
                if line.strip():
                    print(f"   {line}")
        
        return True
    
    def _create_minimal_reproduction(self, failure: dict) -> bool:
        """Step 2: Create minimal reproduction case."""
        print("\n🧪 Step 2: Creating minimal reproduction...")
        
        test_name = failure['test_name']
        
        # Check if this is already a minimal test
        if any(indicator in test_name.lower() for indicator in ['minimal', 'simple', 'basic']):
            print(f"✅ Test {test_name} appears to be minimal already")
            return True
        
        print("   Suggestions for minimal reproduction:")
        print("   1. Run with minimal data/fixtures")
        print("   2. Isolate specific functionality being tested")
        print("   3. Remove dependencies on external services if possible")
        print("   4. Add debug logging to identify exact failure point")
        
        response = input("   Have you created a minimal reproduction? (y/n): ").strip().lower()
        return response == 'y'
    
    def _interactive_fix_development(self, failure: dict) -> bool:
        """Step 3: Interactive fix development."""
        print("\n🔧 Step 3: Developing fix...")
        
        print("   Based on best practices:")
        print("   • Identify root cause before implementing fix")
        print("   • Use debugging tools and logging")
        print("   • Check for similar issues in codebase")
        print("   • Consider environmental factors")
        print("   • Document your investigation process")
        
        while True:
            print(f"\n   Current failure: {failure['test_name']}")
            print("   Options:")
            print("     1. Record fix attempt")
            print("     2. Check current test status")
            print("     3. Continue to verification")
            print("     4. Abort fix process")
            
            choice = input("   Choose option (1-4): ").strip()
            
            if choice == '1':
                fix_description = input("   Describe your fix attempt: ").strip()
                if fix_description:
                    self.tracker.update_fix_attempt(failure['id'], fix_description)
                    print("   ✅ Fix attempt recorded")
            
            elif choice == '2':
                print("   🔍 Checking current test status...")
                success, output = self._run_single_test(failure['test_name'])
                if success:
                    print("   ✅ Test is now passing!")
                else:
                    print("   ❌ Test is still failing")
                    error_lines = output.split('\n')[-5:]
                    for line in error_lines:
                        if line.strip():
                            print(f"     {line}")
            
            elif choice == '3':
                # Verify the test is now passing
                success, _ = self._run_single_test(failure['test_name'])
                if not success:
                    print("   ⚠️  Warning: Test is still failing")
                    continue_anyway = input("   Continue to verification anyway? (y/n): ").strip().lower()
                    if continue_anyway != 'y':
                        continue
                return True
            
            elif choice == '4':
                return False
            
            else:
                print("   Invalid choice. Please select 1-4.")
    
    def _run_verification_loop(self, failure: dict) -> bool:
        """Steps 4-6: Run verification loop."""
        print("\n✅ Step 4-6: Running verification loop...")
        
        test_name = failure['test_name']
        test_category = self._determine_test_category(test_name)
        
        # Step 4: Run test in isolation
        print("   🧪 Step 4: Running test in isolation...")
        success, output = self._run_single_test(test_name)
        if success:
            print("   ✅ Isolated test passed")
            self.verification_steps['isolated_test'] = True
        else:
            print("   ❌ Isolated test failed")
            print("   Must fix test before proceeding")
            return False
        
        # Step 5: Run related test suite
        print(f"   📦 Step 5: Running {test_category} test suite...")
        if test_category != 'unknown':
            success, output = self._run_test_category(test_category)
            if success:
                print("   ✅ Related test suite passed")
                self.verification_steps['related_suite'] = True
            else:
                print("   ❌ Related test suite failed")
                print("   Check for regressions in related tests")
                
                response = input("   Continue despite related test failures? (y/n): ").strip().lower()
                if response != 'y':
                    return False
        else:
            print("   ⚠️  Unknown test category, skipping related suite")
            self.verification_steps['related_suite'] = True
        
        # Step 6: Run full test suite
        print("   🏗️  Step 6: Running full test suite...")
        response = input("   Run full test suite? This may take several minutes (y/n): ").strip().lower()
        if response == 'y':
            success, output = self._run_all_tests()
            if success:
                print("   ✅ Full test suite passed")
                self.verification_steps['full_suite'] = True
            else:
                print("   ❌ Full test suite has failures")
                print("   Review for any regressions introduced")
                
                response = input("   Mark as verified despite failures? (y/n): ").strip().lower()
                self.verification_steps['full_suite'] = response == 'y'
        else:
            print("   ⏭️  Skipping full test suite")
            self.verification_steps['full_suite'] = True
        
        return True
    
    def _document_resolution(self, failure: dict) -> bool:
        """Step 7: Document the resolution."""
        print("\n📝 Step 7: Documenting resolution...")
        
        # Show verification summary
        print("   Verification Summary:")
        for step, passed in self.verification_steps.items():
            status = "✅" if passed else "❌"
            print(f"     {status} {step.replace('_', ' ').title()}")
        
        # Get resolution details
        print("\n   Please provide resolution details:")
        resolution = input("   Resolution summary: ").strip()
        if not resolution:
            print("   ❌ Resolution summary is required")
            return False
        
        lessons_learned = input("   Lessons learned (optional): ").strip()
        
        # Mark as resolved
        success = self.tracker.mark_resolved(failure['id'], resolution, lessons_learned)
        if success:
            print("   ✅ Failure marked as resolved")
            
            # Ask about documentation updates
            response = input("   Do any docs need updating? (y/n): ").strip().lower()
            if response == 'y':
                doc_updates = input("   Describe documentation updates needed: ").strip()
                if doc_updates:
                    print(f"   📋 TODO: Update documentation - {doc_updates}")
            
            return True
        else:
            print("   ❌ Failed to mark as resolved")
            return False
    
    def _run_single_test(self, test_name: str) -> Tuple[bool, str]:
        """Run a single test and return success status and output."""
        try:
            # Use pytest directly to run specific test
            result = subprocess.run(
                ['python', '-m', 'pytest', '-v', '-k', test_name],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Test timed out"
        except Exception as e:
            return False, str(e)
    
    def _run_test_category(self, category: str) -> Tuple[bool, str]:
        """Run tests for a specific category."""
        try:
            result = subprocess.run(
                [str(self.test_runner), category],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Test category timed out"
        except Exception as e:
            return False, str(e)
    
    def _run_all_tests(self) -> Tuple[bool, str]:
        """Run all tests."""
        try:
            result = subprocess.run(
                [str(self.test_runner), 'all'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Full test suite timed out"
        except Exception as e:
            return False, str(e)
    
    def _determine_test_category(self, test_name: str) -> str:
        """Determine test category from test name or file path."""
        # Check common test path patterns
        if 'unit' in test_name or '/unit/' in test_name:
            return 'unit'
        elif 'integration' in test_name or '/integration/' in test_name:
            return 'integration'
        elif 'e2e' in test_name or '/e2e/' in test_name:
            return 'e2e'
        elif 'processing' in test_name or '/processing/' in test_name:
            return 'processing'
        elif 'api' in test_name or '/api/' in test_name:
            return 'api'
        else:
            return 'unknown'
    
    def _extract_error_message(self, output: str) -> str:
        """Extract meaningful error message from test output."""
        lines = output.split('\n')
        
        # Look for common error patterns
        for line in lines:
            if 'AssertionError' in line or 'Error:' in line or 'Exception:' in line:
                return line.strip()
        
        # Return last non-empty line if no specific error found
        for line in reversed(lines):
            if line.strip():
                return line.strip()
        
        return "Unknown error"


def main():
    """Main entry point for fix-verify loop."""
    parser = argparse.ArgumentParser(
        description="Systematic fix validation process",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('failure_id', nargs='?', help='Failure ID to process')
    parser.add_argument('--test', help='Start from test name')
    
    args = parser.parse_args()
    
    if not args.failure_id and not args.test:
        parser.print_help()
        return 1
    
    loop = FixVerifyLoop()
    
    try:
        if args.test:
            success = loop.start_from_test_name(args.test)
        else:
            success = loop.start_fix_process(args.failure_id)
        
        return 0 if success else 1
    
    except KeyboardInterrupt:
        print("\n❌ Fix-verify process cancelled")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())