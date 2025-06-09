#!/usr/bin/env python3
"""
Optimized test runner for VTT pipeline tests.

This script provides efficient test execution with various optimization strategies.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


class VTTTestRunner:
    """Optimized test runner for VTT tests."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        
    def run_unit_tests(self):
        """Run fast unit tests."""
        print("Running VTT unit tests...")
        cmd = [
            "python", "-m", "pytest",
            "tests/unit/test_vtt_parser_unit.py",
            "tests/unit/test_vtt_segmentation_unit.py",
            "tests/processing/test_vtt_parser.py",
            "tests/processing/test_vtt_segmentation.py",
            "-v", "--tb=short"
        ]
        return subprocess.run(cmd, cwd=self.project_root).returncode
        
    def run_integration_tests(self):
        """Run VTT integration tests."""
        print("\nRunning VTT integration tests...")
        cmd = [
            "python", "-m", "pytest",
            "tests/processing/test_vtt_extraction.py",
            "tests/integration/test_vtt_processing.py",
            "tests/integration/test_vtt_e2e.py",
            "-v", "--tb=short"
        ]
        return subprocess.run(cmd, cwd=self.project_root).returncode
        
    def run_e2e_tests(self):
        """Run end-to-end tests."""
        print("\nRunning VTT E2E tests...")
        cmd = [
            "python", "-m", "pytest",
            "tests/e2e/test_critical_path.py",
            "tests/e2e/test_vtt_pipeline_e2e.py",
            "-v", "--tb=short"
        ]
        return subprocess.run(cmd, cwd=self.project_root).returncode
        
    def run_all_vtt_tests(self):
        """Run all VTT tests in order of speed."""
        start_time = time.time()
        
        # Run in order: unit -> integration -> e2e
        results = []
        
        # Unit tests (fastest)
        print("=" * 60)
        print("PHASE 1: Unit Tests")
        print("=" * 60)
        results.append(("Unit", self.run_unit_tests()))
        
        # Integration tests
        print("\n" + "=" * 60)
        print("PHASE 2: Integration Tests")
        print("=" * 60)
        results.append(("Integration", self.run_integration_tests()))
        
        # E2E tests (slowest)
        print("\n" + "=" * 60)
        print("PHASE 3: End-to-End Tests")
        print("=" * 60)
        results.append(("E2E", self.run_e2e_tests()))
        
        # Summary
        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        for test_type, returncode in results:
            status = "PASSED" if returncode == 0 else "FAILED"
            print(f"{test_type} Tests: {status}")
            
        print(f"\nTotal time: {elapsed:.2f} seconds")
        
        # Return non-zero if any tests failed
        return any(code != 0 for _, code in results)
        
    def run_critical_tests(self):
        """Run only critical VTT tests."""
        print("Running critical VTT tests...")
        cmd = [
            "python", "-m", "pytest",
            "tests/processing/test_vtt_parser.py::TestVTTParser::test_parse_simple_vtt",
            "tests/processing/test_vtt_parser.py::TestVTTParser::test_parse_vtt_with_speakers",
            "tests/unit/test_vtt_segmentation_unit.py::TestVTTSegmenter::test_process_segments_basic",
            "tests/e2e/test_critical_path.py::TestCriticalPath::test_vtt_to_knowledge_graph_flow",
            "-v", "--tb=short"
        ]
        return subprocess.run(cmd, cwd=self.project_root).returncode
        
    def run_with_coverage(self):
        """Run tests with coverage reporting."""
        print("Running VTT tests with coverage...")
        cmd = [
            "python", "-m", "pytest",
            "--cov=src.vtt",
            "--cov=src.extraction",
            "--cov=src.processing",
            "--cov-report=term-missing",
            "--cov-report=html",
            "tests/processing/test_vtt_parser.py",
            "tests/processing/test_vtt_extraction.py",
            "tests/unit/test_vtt_segmentation_unit.py",
            "-v"
        ]
        return subprocess.run(cmd, cwd=self.project_root).returncode


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Optimized VTT test runner")
    parser.add_argument(
        "--mode", 
        choices=["all", "unit", "integration", "e2e", "critical", "coverage"],
        default="all",
        help="Test execution mode"
    )
    
    args = parser.parse_args()
    runner = VTTTestRunner()
    
    if args.mode == "all":
        return runner.run_all_vtt_tests()
    elif args.mode == "unit":
        return runner.run_unit_tests()
    elif args.mode == "integration":
        return runner.run_integration_tests()
    elif args.mode == "e2e":
        return runner.run_e2e_tests()
    elif args.mode == "critical":
        return runner.run_critical_tests()
    elif args.mode == "coverage":
        return runner.run_with_coverage()
        

if __name__ == "__main__":
    sys.exit(main())