#!/usr/bin/env python3
"""
Failure Management Script for VTT Knowledge Graph Pipeline

Command-line interface for managing test failures systematically.
Part of Phase 6: Test Failure Resolution

Usage:
    ./scripts/manage_failures.py list                    # List all failures
    ./scripts/manage_failures.py active                  # Show active failures
    ./scripts/manage_failures.py critical               # Show critical failures
    ./scripts/manage_failures.py record "test_name"     # Record new failure
    ./scripts/manage_failures.py update FAILURE_ID      # Update failure with fix attempt
    ./scripts/manage_failures.py resolve FAILURE_ID     # Mark failure as resolved
    ./scripts/manage_failures.py summary                # Show summary report
    ./scripts/manage_failures.py --help                 # Show this help
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from test_tracking import FailureTracker, ErrorType, Severity, FailureStatus
except ImportError as e:
    print(f"Error importing failure tracking: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


class FailureManager:
    """Command-line interface for failure management."""
    
    def __init__(self):
        self.tracker = FailureTracker()
    
    def list_failures(self, status_filter=None, severity_filter=None):
        """List failures with optional filtering."""
        failures = self.tracker._load_failures()
        
        # Apply filters
        if status_filter:
            failures = [f for f in failures if f["status"] == status_filter]
        if severity_filter:
            failures = [f for f in failures if f["severity"] == severity_filter]
        
        if not failures:
            print("📭 No failures found matching criteria")
            return
        
        print(f"📋 Found {len(failures)} failure(s):")
        print("-" * 100)
        print(f"{'ID':<8} {'Status':<12} {'Severity':<8} {'Type':<12} {'Test Name':<30} {'Last Seen'}")
        print("-" * 100)
        
        for failure in failures:
            last_seen = failure.get('last_seen', failure.get('first_seen', 'Unknown'))
            if last_seen != 'Unknown':
                try:
                    last_seen_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                    last_seen = last_seen_dt.strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    pass  # Keep original format if parsing fails
            
            status_icon = self._get_status_icon(failure["status"])
            severity_icon = self._get_severity_icon(failure["severity"])
            
            print(f"{failure['id']:<8} {status_icon}{failure['status']:<11} "
                  f"{severity_icon}{failure['severity']:<7} {failure['error_type']:<12} "
                  f"{failure['test_name'][:29]:<30} {last_seen}")
        
        print("-" * 100)
    
    def show_failure_details(self, failure_id):
        """Show detailed information about a specific failure."""
        failure = self.tracker.find_failure_by_id(failure_id)
        if not failure:
            print(f"❌ Failure {failure_id} not found")
            return
        
        print(f"🔍 Failure Details: {failure_id}")
        print("=" * 60)
        print(f"Test Name: {failure['test_name']}")
        print(f"Status: {self._get_status_icon(failure['status'])} {failure['status']}")
        print(f"Severity: {self._get_severity_icon(failure['severity'])} {failure['severity']}")
        print(f"Error Type: {failure['error_type']}")
        print(f"First Seen: {failure['first_seen']}")
        print(f"Last Seen: {failure['last_seen']}")
        print(f"Frequency: {failure['metadata']['frequency']}")
        
        if failure['metadata']['error_message']:
            print(f"\nError Message:")
            print(f"  {failure['metadata']['error_message']}")
        
        if failure['root_cause']:
            print(f"\nRoot Cause:")
            print(f"  {failure['root_cause']}")
        
        if failure['attempted_fixes']:
            print(f"\nAttempted Fixes ({len(failure['attempted_fixes'])}):")
            for i, fix in enumerate(failure['attempted_fixes'], 1):
                success = "✅" if fix.get('success') else "⏳"
                print(f"  {i}. {success} {fix['description']} ({fix['timestamp'][:10]})")
        
        if failure['resolution']:
            print(f"\nResolution:")
            print(f"  {failure['resolution']}")
        
        if failure['lessons_learned']:
            print(f"\nLessons Learned:")
            print(f"  {failure['lessons_learned']}")
    
    def record_failure_interactive(self, test_name=None):
        """Interactively record a new failure."""
        if not test_name:
            test_name = input("Test name: ").strip()
            if not test_name:
                print("❌ Test name is required")
                return
        
        error_message = input("Error message: ").strip()
        if not error_message:
            print("❌ Error message is required")
            return
        
        # Show error type options
        print("\nError Types:")
        for i, error_type in enumerate(ErrorType, 1):
            print(f"  {i}. {error_type.value}")
        
        try:
            error_type_choice = int(input(f"Error type (1-{len(ErrorType)}): "))
            error_type = list(ErrorType)[error_type_choice - 1]
        except (ValueError, IndexError):
            error_type = ErrorType.OTHER
            print(f"Using default: {error_type.value}")
        
        # Show severity options
        print("\nSeverity Levels:")
        for i, severity in enumerate(Severity, 1):
            print(f"  {i}. {severity.value}")
        
        try:
            severity_choice = int(input(f"Severity (1-{len(Severity)}): "))
            severity = list(Severity)[severity_choice - 1]
        except (ValueError, IndexError):
            severity = Severity.MEDIUM
            print(f"Using default: {severity.value}")
        
        test_category = input("Test category (e.g., unit, integration, e2e): ").strip()
        
        # Record the failure
        failure_id = self.tracker.record_failure(
            test_name=test_name,
            error_message=error_message,
            error_type=error_type,
            severity=severity,
            test_category=test_category
        )
        
        print(f"✅ Failure recorded: {failure_id}")
        return failure_id
    
    def update_failure_interactive(self, failure_id):
        """Interactively update a failure with fix attempt."""
        failure = self.tracker.find_failure_by_id(failure_id)
        if not failure:
            print(f"❌ Failure {failure_id} not found")
            return
        
        print(f"📝 Updating failure: {failure['test_name']}")
        fix_description = input("Describe the fix attempt: ").strip()
        if not fix_description:
            print("❌ Fix description is required")
            return
        
        success = self.tracker.update_fix_attempt(failure_id, fix_description)
        if success:
            print("✅ Fix attempt recorded")
        else:
            print("❌ Failed to update failure")
    
    def resolve_failure_interactive(self, failure_id):
        """Interactively resolve a failure."""
        failure = self.tracker.find_failure_by_id(failure_id)
        if not failure:
            print(f"❌ Failure {failure_id} not found")
            return
        
        print(f"✅ Resolving failure: {failure['test_name']}")
        resolution = input("Describe the resolution: ").strip()
        if not resolution:
            print("❌ Resolution description is required")
            return
        
        lessons = input("Lessons learned (optional): ").strip()
        
        success = self.tracker.mark_resolved(failure_id, resolution, lessons)
        if success:
            print("✅ Failure marked as resolved")
        else:
            print("❌ Failed to resolve failure")
    
    def show_summary(self):
        """Show summary report of all failures."""
        summary = self.tracker.generate_summary_report()
        
        print("📊 Failure Summary Report")
        print("=" * 50)
        print(f"Total Failures: {summary['total_failures']}")
        print(f"Active Failures: {summary['active_failures']}")
        print(f"Critical Failures: {summary['critical_failures']}")
        
        print(f"\n📈 Status Breakdown:")
        for status, count in summary['status_breakdown'].items():
            icon = self._get_status_icon(status)
            print(f"  {icon} {status}: {count}")
        
        print(f"\n🚨 Severity Breakdown:")
        for severity, count in summary['severity_breakdown'].items():
            icon = self._get_severity_icon(severity)
            print(f"  {icon} {severity}: {count}")
        
        print(f"\n🔧 Error Type Breakdown:")
        for error_type, count in summary['error_type_breakdown'].items():
            if count > 0:
                print(f"  • {error_type}: {count}")
        
        # Show most frequent failures
        if summary['most_frequent_failures']:
            print(f"\n🔁 Most Frequent Failures:")
            for failure in summary['most_frequent_failures'][:3]:
                if failure['metadata']['frequency'] > 1:
                    print(f"  • {failure['test_name']} ({failure['metadata']['frequency']} times)")
    
    def _get_status_icon(self, status):
        """Get icon for failure status."""
        icons = {
            'new': '🆕',
            'in_progress': '⏳',
            'needs_investigation': '🔍',
            'blocked': '🚫',
            'resolved': '✅',
            'wont_fix': '❌'
        }
        return icons.get(status, '❓')
    
    def _get_severity_icon(self, severity):
        """Get icon for failure severity."""
        icons = {
            'critical': '🚨',
            'high': '🔴',
            'medium': '🟡',
            'low': '🟢'
        }
        return icons.get(severity, '❓')


def main():
    """Main entry point for failure management."""
    parser = argparse.ArgumentParser(
        description="Manage test failures systematically",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all failures')
    list_parser.add_argument('--status', help='Filter by status')
    list_parser.add_argument('--severity', help='Filter by severity')
    
    # Active command
    subparsers.add_parser('active', help='Show active failures')
    
    # Critical command
    subparsers.add_parser('critical', help='Show critical failures')
    
    # Record command
    record_parser = subparsers.add_parser('record', help='Record new failure')
    record_parser.add_argument('test_name', nargs='?', help='Name of failing test')
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update failure with fix attempt')
    update_parser.add_argument('failure_id', help='Failure ID to update')
    
    # Resolve command
    resolve_parser = subparsers.add_parser('resolve', help='Mark failure as resolved')
    resolve_parser.add_argument('failure_id', help='Failure ID to resolve')
    
    # Details command
    details_parser = subparsers.add_parser('details', help='Show failure details')
    details_parser.add_argument('failure_id', help='Failure ID to show')
    
    # Summary command
    subparsers.add_parser('summary', help='Show summary report')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    manager = FailureManager()
    
    try:
        if args.command == 'list':
            manager.list_failures(args.status, args.severity)
        elif args.command == 'active':
            manager.list_failures(status_filter='new')
            manager.list_failures(status_filter='in_progress')
        elif args.command == 'critical':
            manager.list_failures(severity_filter='critical')
        elif args.command == 'record':
            manager.record_failure_interactive(args.test_name)
        elif args.command == 'update':
            manager.update_failure_interactive(args.failure_id)
        elif args.command == 'resolve':
            manager.resolve_failure_interactive(args.failure_id)
        elif args.command == 'details':
            manager.show_failure_details(args.failure_id)
        elif args.command == 'summary':
            manager.show_summary()
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())