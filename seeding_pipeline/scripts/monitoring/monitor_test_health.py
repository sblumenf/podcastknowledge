#!/usr/bin/env python3
"""
Test health monitoring script for VTT pipeline.

This script provides continuous monitoring of test health metrics including:
- Test pass/fail rates
- Flaky test detection
- Performance regression detection
- Coverage trends
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET


class TestHealthMonitor:
    """Monitor test health metrics for the VTT pipeline."""
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.results_dir = self.project_root / "test_results"
        self.results_dir.mkdir(exist_ok=True)
        
        # Health metrics file
        self.health_metrics_file = self.results_dir / "test_health_metrics.json"
        self.health_history = self._load_health_history()
        
    def _load_health_history(self) -> Dict:
        """Load historical health metrics."""
        if self.health_metrics_file.exists():
            with open(self.health_metrics_file) as f:
                return json.load(f)
        return {"runs": []}
        
    def _save_health_history(self):
        """Save health metrics to file."""
        with open(self.health_metrics_file, 'w') as f:
            json.dump(self.health_history, f, indent=2)
            
    def run_tests(self, test_suite: str = "vtt") -> Dict:
        """Run tests and collect metrics."""
        timestamp = datetime.now().isoformat()
        
        # Run tests with junit output
        junit_file = self.results_dir / f"junit_{test_suite}_{timestamp.replace(':', '-')}.xml"
        coverage_file = self.results_dir / f"coverage_{test_suite}_{timestamp.replace(':', '-')}.xml"
        
        cmd = [
            "python", "-m", "pytest",
            f"-m", test_suite,
            f"--junit-xml={junit_file}",
            f"--cov-report=xml:{coverage_file}",
            "--cov=src",
            "-v"
        ]
        
        print(f"Running {test_suite} tests...")
        result = subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True
        )
        
        # Parse results
        metrics = self._parse_test_results(junit_file, coverage_file)
        metrics["timestamp"] = timestamp
        metrics["test_suite"] = test_suite
        metrics["exit_code"] = result.returncode
        
        return metrics
        
    def _parse_test_results(self, junit_file: Path, coverage_file: Path) -> Dict:
        """Parse test results from JUnit XML."""
        metrics = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "duration": 0.0,
            "coverage": 0.0,
            "failed_tests": [],
            "slow_tests": []
        }
        
        # Parse JUnit results
        if junit_file.exists():
            tree = ET.parse(junit_file)
            root = tree.getroot()
            
            testsuites = root if root.tag == 'testsuites' else [root]
            
            for testsuite in testsuites:
                if testsuite.tag == 'testsuite':
                    metrics["total_tests"] += int(testsuite.get('tests', 0))
                    metrics["failed"] += int(testsuite.get('failures', 0))
                    metrics["errors"] += int(testsuite.get('errors', 0))
                    metrics["skipped"] += int(testsuite.get('skipped', 0))
                    metrics["duration"] += float(testsuite.get('time', 0))
                    
                    # Find failed and slow tests
                    for testcase in testsuite.findall('.//testcase'):
                        test_name = f"{testcase.get('classname')}.{testcase.get('name')}"
                        test_time = float(testcase.get('time', 0))
                        
                        # Check for failures
                        if testcase.find('failure') is not None:
                            metrics["failed_tests"].append(test_name)
                            
                        # Flag slow tests (>5 seconds)
                        if test_time > 5.0:
                            metrics["slow_tests"].append({
                                "name": test_name,
                                "duration": test_time
                            })
            
            metrics["passed"] = metrics["total_tests"] - metrics["failed"] - metrics["errors"] - metrics["skipped"]
            
        # Parse coverage results
        if coverage_file.exists():
            tree = ET.parse(coverage_file)
            root = tree.getroot()
            
            # Get overall coverage percentage
            coverage_elem = root.find('.//coverage')
            if coverage_elem is not None:
                line_rate = float(coverage_elem.get('line-rate', 0))
                metrics["coverage"] = round(line_rate * 100, 2)
                
        return metrics
        
    def detect_flaky_tests(self, num_runs: int = 5) -> List[str]:
        """Detect flaky tests by running multiple times."""
        print(f"Detecting flaky tests (running {num_runs} times)...")
        
        test_results = {}
        
        for i in range(num_runs):
            print(f"Run {i+1}/{num_runs}...")
            metrics = self.run_tests("vtt")
            
            for test in metrics.get("failed_tests", []):
                if test not in test_results:
                    test_results[test] = {"failed": 0, "passed": 0}
                test_results[test]["failed"] += 1
                
        # Find tests that don't fail consistently
        flaky_tests = []
        for test, results in test_results.items():
            if results["failed"] > 0 and results["failed"] < num_runs:
                flaky_tests.append(test)
                
        return flaky_tests
        
    def analyze_trends(self) -> Dict:
        """Analyze test health trends."""
        if len(self.health_history["runs"]) < 2:
            return {"status": "insufficient_data"}
            
        recent_runs = self.health_history["runs"][-10:]  # Last 10 runs
        
        trends = {
            "coverage_trend": "stable",
            "failure_trend": "stable",
            "performance_trend": "stable",
            "average_duration": 0,
            "average_coverage": 0,
            "average_pass_rate": 0
        }
        
        # Calculate averages
        total_duration = sum(r["duration"] for r in recent_runs)
        total_coverage = sum(r["coverage"] for r in recent_runs)
        total_pass_rate = sum(
            (r["passed"] / r["total_tests"] * 100) if r["total_tests"] > 0 else 0
            for r in recent_runs
        )
        
        trends["average_duration"] = round(total_duration / len(recent_runs), 2)
        trends["average_coverage"] = round(total_coverage / len(recent_runs), 2)
        trends["average_pass_rate"] = round(total_pass_rate / len(recent_runs), 2)
        
        # Detect trends
        if len(recent_runs) >= 3:
            # Coverage trend
            recent_coverage = [r["coverage"] for r in recent_runs[-3:]]
            if all(recent_coverage[i] < recent_coverage[i-1] for i in range(1, len(recent_coverage))):
                trends["coverage_trend"] = "declining"
            elif all(recent_coverage[i] > recent_coverage[i-1] for i in range(1, len(recent_coverage))):
                trends["coverage_trend"] = "improving"
                
            # Failure trend
            recent_failures = [r["failed"] + r["errors"] for r in recent_runs[-3:]]
            if all(recent_failures[i] > recent_failures[i-1] for i in range(1, len(recent_failures))):
                trends["failure_trend"] = "worsening"
            elif all(recent_failures[i] < recent_failures[i-1] for i in range(1, len(recent_failures))):
                trends["failure_trend"] = "improving"
                
            # Performance trend
            recent_durations = [r["duration"] for r in recent_runs[-3:]]
            if all(recent_durations[i] > recent_durations[i-1] * 1.1 for i in range(1, len(recent_durations))):
                trends["performance_trend"] = "degrading"
            elif all(recent_durations[i] < recent_durations[i-1] * 0.9 for i in range(1, len(recent_durations))):
                trends["performance_trend"] = "improving"
                
        return trends
        
    def generate_report(self, metrics: Dict) -> str:
        """Generate a health report."""
        report = f"""
# VTT Pipeline Test Health Report
Generated: {metrics['timestamp']}

## Test Results
- Total Tests: {metrics['total_tests']}
- Passed: {metrics['passed']} ({metrics['passed']/metrics['total_tests']*100:.1f}%)
- Failed: {metrics['failed']}
- Errors: {metrics['errors']}
- Skipped: {metrics['skipped']}
- Duration: {metrics['duration']:.2f}s
- Coverage: {metrics['coverage']}%

## Failed Tests
"""
        for test in metrics.get('failed_tests', []):
            report += f"- {test}\n"
            
        report += "\n## Slow Tests (>5s)\n"
        for test in sorted(metrics.get('slow_tests', []), key=lambda x: x['duration'], reverse=True):
            report += f"- {test['name']}: {test['duration']:.2f}s\n"
            
        # Add trends if available
        trends = self.analyze_trends()
        if trends.get("status") != "insufficient_data":
            report += f"""
## Trends (Last 10 Runs)
- Coverage Trend: {trends['coverage_trend']}
- Failure Trend: {trends['failure_trend']}
- Performance Trend: {trends['performance_trend']}
- Average Duration: {trends['average_duration']}s
- Average Coverage: {trends['average_coverage']}%
- Average Pass Rate: {trends['average_pass_rate']}%
"""
        
        return report
        
    def monitor_continuous(self):
        """Run continuous monitoring."""
        print("Starting continuous test health monitoring...")
        
        # Run tests and collect metrics
        metrics = self.run_tests("vtt")
        
        # Save to history
        self.health_history["runs"].append(metrics)
        
        # Keep only last 100 runs
        if len(self.health_history["runs"]) > 100:
            self.health_history["runs"] = self.health_history["runs"][-100:]
            
        self._save_health_history()
        
        # Generate and display report
        report = self.generate_report(metrics)
        print(report)
        
        # Save report
        report_file = self.results_dir / f"health_report_{metrics['timestamp'].replace(':', '-')}.md"
        with open(report_file, 'w') as f:
            f.write(report)
            
        print(f"\nReport saved to: {report_file}")
        
        # Check for issues
        if metrics["failed"] > 0 or metrics["errors"] > 0:
            print("\n⚠️  TESTS FAILING - Immediate attention required!")
            return 1
            
        trends = self.analyze_trends()
        if trends.get("coverage_trend") == "declining":
            print("\n⚠️  Coverage is declining!")
        if trends.get("failure_trend") == "worsening":
            print("\n⚠️  Test failures are increasing!")
        if trends.get("performance_trend") == "degrading":
            print("\n⚠️  Test performance is degrading!")
            
        return 0


def main():
    """Main entry point."""
    monitor = TestHealthMonitor()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--detect-flaky":
        flaky_tests = monitor.detect_flaky_tests()
        if flaky_tests:
            print(f"\n🔍 Found {len(flaky_tests)} flaky tests:")
            for test in flaky_tests:
                print(f"  - {test}")
        else:
            print("\n✅ No flaky tests detected!")
    else:
        exit_code = monitor.monitor_continuous()
        sys.exit(exit_code)


if __name__ == "__main__":
    main()