#!/usr/bin/env python3
"""
Test Results Viewer for VTT Knowledge Graph Pipeline

Helper script to view and analyze recent test execution results.
Part of Phase 5: Test Execution & Monitoring

Usage:
    ./scripts/view_test_results.py              # Show latest results
    ./scripts/view_test_results.py --all        # Show all results
    ./scripts/view_test_results.py --type=e2e   # Show results for specific test type
    ./scripts/view_test_results.py --summary    # Show summary statistics
    ./scripts/view_test_results.py --help       # Show this help
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


class TestResultsViewer:
    """Helper to view and analyze test execution results."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.results_dir = self.project_root / "test_results"
    
    def get_results_files(self, test_type: Optional[str] = None) -> List[Path]:
        """Get list of test result files, optionally filtered by test type."""
        if not self.results_dir.exists():
            return []
        
        pattern = f"*_{test_type}.json" if test_type else "*.json"
        files = list(self.results_dir.glob(pattern))
        
        # Sort by creation time (newest first)
        return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)
    
    def load_result(self, result_file: Path) -> Optional[Dict[str, Any]]:
        """Load a single test result file."""
        try:
            with open(result_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  Error loading {result_file.name}: {str(e)}")
            return None
    
    def format_datetime(self, timestamp_str: str) -> str:
        """Format timestamp for display."""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return timestamp_str
    
    def format_duration(self, seconds: float) -> str:
        """Format duration for display."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}m {secs:.1f}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def display_result_summary(self, result: Dict[str, Any], show_details: bool = False):
        """Display a single test result summary."""
        timestamp = self.format_datetime(result.get('timestamp', 'Unknown'))
        test_type = result.get('test_type', 'unknown')
        duration = self.format_duration(result.get('total_time', 0))
        
        passed = result.get('passed', 0)
        failed = result.get('failed', 0)
        skipped = result.get('skipped', 0)
        errors = result.get('errors', 0)
        total = passed + failed + skipped + errors
        
        # Success indicator
        success = "✅" if failed == 0 and errors == 0 else "❌"
        
        print(f"{success} {timestamp} | {test_type:12} | {duration:>8} | "
              f"P:{passed:3} F:{failed:3} S:{skipped:3} E:{errors:3} | Total:{total:3}")
        
        if show_details and (failed > 0 or errors > 0):
            failures = result.get('failures', [])
            if failures:
                print(f"   Failures:")
                for i, failure in enumerate(failures[:2], 1):  # Show first 2
                    lines = failure.split('\n')
                    if lines:
                        print(f"     {i}. {lines[0][:80]}{'...' if len(lines[0]) > 80 else ''}")
                if len(failures) > 2:
                    print(f"     ... and {len(failures) - 2} more")
    
    def show_latest_results(self, count: int = 10, test_type: Optional[str] = None):
        """Show the most recent test results."""
        files = self.get_results_files(test_type)
        
        if not files:
            print("📭 No test results found.")
            print(f"   Results are saved to: {self.results_dir}")
            print(f"   Run tests using: ./scripts/run_tests.py")
            return
        
        type_filter = f" for {test_type}" if test_type else ""
        print(f"📊 Latest {min(count, len(files))} test results{type_filter}:")
        print("-" * 90)
        print(f"{'Status':<2} {'Timestamp':<19} | {'Type':<12} | {'Duration':<8} | "
              f"{'Results':<19} | {'Total':<7}")
        print("-" * 90)
        
        for file in files[:count]:
            result = self.load_result(file)
            if result:
                self.display_result_summary(result)
    
    def show_all_results(self, test_type: Optional[str] = None):
        """Show all test results."""
        files = self.get_results_files(test_type)
        
        if not files:
            print("📭 No test results found.")
            return
        
        type_filter = f" for {test_type}" if test_type else ""
        print(f"📋 All test results{type_filter} ({len(files)} files):")
        print("-" * 90)
        print(f"{'Status':<2} {'Timestamp':<19} | {'Type':<12} | {'Duration':<8} | "
              f"{'Results':<19} | {'Total':<7}")
        print("-" * 90)
        
        for file in files:
            result = self.load_result(file)
            if result:
                self.display_result_summary(result, show_details=True)
    
    def show_summary_statistics(self):
        """Show summary statistics across all test results."""
        files = self.get_results_files()
        
        if not files:
            print("📭 No test results found.")
            return
        
        print(f"📈 Test Results Summary ({len(files)} test runs):")
        print("-" * 60)
        
        # Group by test type
        stats_by_type = {}
        total_stats = {'runs': 0, 'passed': 0, 'failed': 0, 'skipped': 0, 'errors': 0, 'total_time': 0}
        
        for file in files:
            result = self.load_result(file)
            if not result:
                continue
            
            test_type = result.get('test_type', 'unknown')
            if test_type not in stats_by_type:
                stats_by_type[test_type] = {'runs': 0, 'passed': 0, 'failed': 0, 'skipped': 0, 'errors': 0, 'total_time': 0}
            
            stats = stats_by_type[test_type]
            stats['runs'] += 1
            stats['passed'] += result.get('passed', 0)
            stats['failed'] += result.get('failed', 0)
            stats['skipped'] += result.get('skipped', 0)
            stats['errors'] += result.get('errors', 0)
            stats['total_time'] += result.get('total_time', 0)
            
            total_stats['runs'] += 1
            total_stats['passed'] += result.get('passed', 0)
            total_stats['failed'] += result.get('failed', 0)
            total_stats['skipped'] += result.get('skipped', 0)
            total_stats['errors'] += result.get('errors', 0)
            total_stats['total_time'] += result.get('total_time', 0)
        
        # Display by test type
        print(f"{'Test Type':<12} | {'Runs':<4} | {'Passed':<6} | {'Failed':<6} | {'Skipped':<7} | {'Errors':<6} | {'Avg Time'}")
        print("-" * 70)
        
        for test_type, stats in sorted(stats_by_type.items()):
            avg_time = self.format_duration(stats['total_time'] / stats['runs']) if stats['runs'] > 0 else '0s'
            success_rate = (stats['passed'] / max(1, stats['passed'] + stats['failed'])) * 100
            status = "✅" if stats['failed'] == 0 and stats['errors'] == 0 else "❌"
            
            print(f"{status} {test_type:<10} | {stats['runs']:>3} | {stats['passed']:>6} | "
                  f"{stats['failed']:>6} | {stats['skipped']:>7} | {stats['errors']:>6} | {avg_time}")
        
        # Display totals
        print("-" * 70)
        avg_time = self.format_duration(total_stats['total_time'] / total_stats['runs']) if total_stats['runs'] > 0 else '0s'
        print(f"{'TOTAL':<12} | {total_stats['runs']:>3} | {total_stats['passed']:>6} | "
              f"{total_stats['failed']:>6} | {total_stats['skipped']:>7} | {total_stats['errors']:>6} | {avg_time}")
        
        # Additional insights
        if total_stats['runs'] > 0:
            success_rate = (total_stats['passed'] / max(1, total_stats['passed'] + total_stats['failed'])) * 100
            print(f"\n📈 Insights:")
            print(f"   Success Rate: {success_rate:.1f}%")
            print(f"   Total Test Time: {self.format_duration(total_stats['total_time'])}")
            print(f"   Most Recent: {self.format_datetime(self.load_result(files[0]).get('timestamp', ''))}")
            print(f"   Oldest: {self.format_datetime(self.load_result(files[-1]).get('timestamp', ''))}")
    
    def display_help(self):
        """Display help information."""
        print(__doc__)
        print("\nExamples:")
        print("  ./scripts/view_test_results.py              # Show latest 10 results")
        print("  ./scripts/view_test_results.py --all        # Show all results")
        print("  ./scripts/view_test_results.py --type=e2e   # Show E2E test results only")
        print("  ./scripts/view_test_results.py --summary    # Show statistics summary")
        print("\nResult files are stored in test_results/ directory")


def main():
    """Main entry point."""
    viewer = TestResultsViewer()
    
    # Parse arguments
    args = sys.argv[1:]
    
    if '--help' in args or '-h' in args:
        viewer.display_help()
        return 0
    
    if '--summary' in args:
        viewer.show_summary_statistics()
        return 0
    
    # Check for test type filter
    test_type = None
    for arg in args:
        if arg.startswith('--type='):
            test_type = arg.split('=', 1)[1]
            break
    
    if '--all' in args:
        viewer.show_all_results(test_type)
    else:
        # Default: show latest 10
        viewer.show_latest_results(10, test_type)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())