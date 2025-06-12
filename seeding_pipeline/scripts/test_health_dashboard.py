#!/usr/bin/env python3
"""
Simple test health dashboard for VTT pipeline.

This script provides a quick overview of test health metrics.
"""

import json
from pathlib import Path
from datetime import datetime
import sys


def load_health_metrics():
    """Load test health metrics."""
    results_dir = Path(__file__).parent.parent / "test_results"
    metrics_file = results_dir / "test_health_metrics.json"
    
    if not metrics_file.exists():
        print("No test health metrics found. Run monitor_test_health.py first.")
        return None
        
    with open(metrics_file) as f:
        return json.load(f)


def print_dashboard(health_data):
    """Print test health dashboard."""
    if not health_data or not health_data.get("runs"):
        print("No test runs recorded.")
        return
        
    runs = health_data["runs"]
    latest_run = runs[-1]
    
    # Header
    print("\n" + "="*60)
    print("VTT PIPELINE TEST HEALTH DASHBOARD")
    print("="*60)
    
    # Latest run summary
    print(f"\nLatest Run: {latest_run['timestamp']}")
    print(f"Test Suite: {latest_run.get('test_suite', 'unknown')}")
    print("-"*40)
    
    total = latest_run['total_tests']
    passed = latest_run['passed']
    failed = latest_run['failed']
    errors = latest_run['errors']
    skipped = latest_run['skipped']
    
    # Test results bar
    if total > 0:
        pass_rate = (passed / total) * 100
        
        # Color codes
        if pass_rate >= 95:
            status = "✅ HEALTHY"
            color = "\033[92m"  # Green
        elif pass_rate >= 80:
            status = "⚠️  WARNING"
            color = "\033[93m"  # Yellow
        else:
            status = "❌ CRITICAL"
            color = "\033[91m"  # Red
        reset = "\033[0m"
        
        print(f"\nTest Status: {color}{status}{reset}")
        print(f"Pass Rate: {color}{pass_rate:.1f}%{reset}")
        
        # Visual bar
        bar_width = 40
        passed_width = int((passed / total) * bar_width)
        failed_width = int(((failed + errors) / total) * bar_width)
        skipped_width = int((skipped / total) * bar_width)
        
        bar = "["
        bar += "=" * passed_width
        bar += "!" * failed_width
        bar += "-" * skipped_width
        bar += " " * (bar_width - passed_width - failed_width - skipped_width)
        bar += "]"
        
        print(f"\nProgress: {bar}")
        print(f"         Passed: {passed} | Failed: {failed} | Errors: {errors} | Skipped: {skipped}")
    
    # Performance metrics
    print(f"\nDuration: {latest_run['duration']:.2f}s")
    print(f"Coverage: {latest_run['coverage']:.1f}%")
    
    # Failed tests
    if latest_run.get('failed_tests'):
        print("\n❌ Failed Tests:")
        for test in latest_run['failed_tests'][:5]:  # Show max 5
            print(f"   - {test}")
        if len(latest_run['failed_tests']) > 5:
            print(f"   ... and {len(latest_run['failed_tests']) - 5} more")
    
    # Slow tests
    if latest_run.get('slow_tests'):
        print("\n🐌 Slow Tests (>5s):")
        for test in sorted(latest_run['slow_tests'], key=lambda x: x['duration'], reverse=True)[:3]:
            print(f"   - {test['name']}: {test['duration']:.1f}s")
    
    # Historical trends
    if len(runs) >= 5:
        print("\n📊 Recent Trends (Last 5 Runs):")
        recent_runs = runs[-5:]
        
        # Pass rate trend
        pass_rates = [(r['passed'] / r['total_tests'] * 100) if r['total_tests'] > 0 else 0 for r in recent_runs]
        pass_trend = "📈" if pass_rates[-1] > pass_rates[0] else "📉" if pass_rates[-1] < pass_rates[0] else "➡️"
        print(f"   Pass Rate: {pass_trend} {' → '.join(f'{pr:.0f}%' for pr in pass_rates)}")
        
        # Coverage trend
        coverages = [r['coverage'] for r in recent_runs]
        cov_trend = "📈" if coverages[-1] > coverages[0] else "📉" if coverages[-1] < coverages[0] else "➡️"
        print(f"   Coverage:  {cov_trend} {' → '.join(f'{c:.0f}%' for c in coverages)}")
        
        # Duration trend
        durations = [r['duration'] for r in recent_runs]
        dur_trend = "📉" if durations[-1] < durations[0] else "📈" if durations[-1] > durations[0] else "➡️"
        print(f"   Duration:  {dur_trend} {' → '.join(f'{d:.0f}s' for d in durations)}")
    
    print("\n" + "="*60)
    print("Run 'python scripts/monitor_test_health.py' to update metrics")
    print("="*60 + "\n")


def main():
    """Main entry point."""
    health_data = load_health_metrics()
    if health_data:
        print_dashboard(health_data)
        
        # Return exit code based on latest run
        latest_run = health_data["runs"][-1] if health_data.get("runs") else None
        if latest_run and (latest_run["failed"] > 0 or latest_run["errors"] > 0):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())