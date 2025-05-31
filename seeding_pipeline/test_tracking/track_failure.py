#!/usr/bin/env python3
"""
Test Failure Tracking System for VTT Knowledge Graph Pipeline

Provides systematic approach to handling and documenting test failures.
Part of Phase 6: Test Failure Resolution

Usage:
    from test_tracking.track_failure import FailureTracker
    
    tracker = FailureTracker()
    tracker.record_failure(test_name, error_details)
    tracker.update_fix_attempt(failure_id, fix_description)
    tracker.mark_resolved(failure_id, resolution_details)
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from enum import Enum


class ErrorType(Enum):
    """Categories of test errors."""
    CONNECTION = "connection"
    IMPORT = "import"
    ASSERTION = "assertion"
    TIMEOUT = "timeout"
    CONFIGURATION = "configuration"
    DATA = "data"
    DEPENDENCY = "dependency"
    ENVIRONMENT = "environment"
    OTHER = "other"


class Severity(Enum):
    """Severity levels for test failures."""
    CRITICAL = "critical"  # Blocks all E2E functionality
    HIGH = "high"         # Blocks major functionality
    MEDIUM = "medium"     # Impacts some functionality
    LOW = "low"          # Minor issues, workarounds available


class FailureStatus(Enum):
    """Status of failure resolution."""
    NEW = "new"
    IN_PROGRESS = "in_progress"
    NEEDS_INVESTIGATION = "needs_investigation"
    BLOCKED = "blocked"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"


# Base failure record template
failure_record = {
    "id": "",
    "test_name": "",
    "first_seen": "",
    "last_seen": "",
    "error_type": "",
    "severity": "",
    "status": "",
    "root_cause": "",
    "attempted_fixes": [],
    "resolution": "",
    "lessons_learned": "",
    "metadata": {
        "test_category": "",
        "test_file": "",
        "error_message": "",
        "stack_trace": "",
        "environment": "",
        "frequency": 0,
        "related_failures": []
    }
}


class FailureTracker:
    """Manages test failure tracking and resolution workflow."""
    
    def __init__(self, tracking_dir: Optional[Path] = None):
        """Initialize failure tracker with specified directory."""
        self.tracking_dir = tracking_dir or Path(__file__).parent
        self.failures_file = self.tracking_dir / "failures.json"
        self.categories_file = self.tracking_dir / "failure_categories.json"
        
        # Ensure tracking directory exists
        self.tracking_dir.mkdir(exist_ok=True)
        
        # Initialize files if they don't exist
        self._initialize_tracking_files()
    
    def _initialize_tracking_files(self):
        """Create initial tracking files if they don't exist."""
        if not self.failures_file.exists():
            self._save_failures([])
        
        if not self.categories_file.exists():
            self._save_categories(self._get_default_categories())
    
    def _get_default_categories(self) -> Dict[str, Any]:
        """Get default failure categories and priorities."""
        return {
            "error_types": {
                "connection": {
                    "description": "Database connection, network, or service connectivity issues",
                    "priority": "high",
                    "common_causes": ["Neo4j not running", "Wrong credentials", "Network issues"]
                },
                "import": {
                    "description": "Module import errors, missing dependencies",
                    "priority": "critical",
                    "common_causes": ["Missing packages", "Circular imports", "PYTHONPATH issues"]
                },
                "assertion": {
                    "description": "Test assertion failures, unexpected results",
                    "priority": "medium",
                    "common_causes": ["Logic errors", "Data mismatch", "Timing issues"]
                },
                "timeout": {
                    "description": "Test execution timeouts",
                    "priority": "medium",
                    "common_causes": ["Slow operations", "Deadlocks", "Resource contention"]
                },
                "configuration": {
                    "description": "Environment or configuration-related failures",
                    "priority": "high",
                    "common_causes": ["Missing .env", "Wrong settings", "Path issues"]
                },
                "data": {
                    "description": "Test data or fixture-related issues",
                    "priority": "medium",
                    "common_causes": ["Missing fixtures", "Corrupted data", "Schema mismatch"]
                },
                "dependency": {
                    "description": "External dependency failures",
                    "priority": "high",
                    "common_causes": ["Service unavailable", "API changes", "Version conflicts"]
                },
                "environment": {
                    "description": "Operating system or environment-specific issues",
                    "priority": "medium",
                    "common_causes": ["OS differences", "Permission issues", "Resource limits"]
                }
            },
            "severity_guidelines": {
                "critical": "Blocks all E2E functionality, prevents basic testing",
                "high": "Blocks major functionality, impacts multiple test categories",
                "medium": "Impacts specific functionality, workarounds available",
                "low": "Minor issues, cosmetic problems, edge cases"
            },
            "resolution_priorities": {
                "critical": "Fix immediately, blocks all progress",
                "high": "Fix within 1 day, blocks major features",
                "medium": "Fix within 1 week, plan in next sprint",
                "low": "Fix when convenient, document workarounds"
            }
        }
    
    def _load_failures(self) -> List[Dict[str, Any]]:
        """Load failure records from file."""
        try:
            with open(self.failures_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_failures(self, failures: List[Dict[str, Any]]):
        """Save failure records to file."""
        with open(self.failures_file, 'w') as f:
            json.dump(failures, f, indent=2, default=str)
    
    def _save_categories(self, categories: Dict[str, Any]):
        """Save failure categories to file."""
        with open(self.categories_file, 'w') as f:
            json.dump(categories, f, indent=2)
    
    def record_failure(
        self,
        test_name: str,
        error_message: str,
        error_type: Union[ErrorType, str] = ErrorType.OTHER,
        severity: Union[Severity, str] = Severity.MEDIUM,
        test_category: str = "",
        test_file: str = "",
        stack_trace: str = "",
        environment: str = "unknown"
    ) -> str:
        """Record a new test failure."""
        failure_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()
        
        # Convert enums to strings if needed
        if isinstance(error_type, ErrorType):
            error_type = error_type.value
        if isinstance(severity, Severity):
            severity = severity.value
        
        # Check for existing failure with same test name
        existing_failure = self.find_failure_by_test(test_name)
        if existing_failure:
            # Update existing failure
            existing_failure["last_seen"] = timestamp
            existing_failure["metadata"]["frequency"] += 1
            existing_failure["metadata"]["error_message"] = error_message
            existing_failure["metadata"]["stack_trace"] = stack_trace
            
            failures = self._load_failures()
            for i, failure in enumerate(failures):
                if failure["id"] == existing_failure["id"]:
                    failures[i] = existing_failure
                    break
            
            self._save_failures(failures)
            return existing_failure["id"]
        
        # Create new failure record
        failure = {
            "id": failure_id,
            "test_name": test_name,
            "first_seen": timestamp,
            "last_seen": timestamp,
            "error_type": error_type,
            "severity": severity,
            "status": FailureStatus.NEW.value,
            "root_cause": "",
            "attempted_fixes": [],
            "resolution": "",
            "lessons_learned": "",
            "metadata": {
                "test_category": test_category,
                "test_file": test_file,
                "error_message": error_message,
                "stack_trace": stack_trace,
                "environment": environment,
                "frequency": 1,
                "related_failures": []
            }
        }
        
        failures = self._load_failures()
        failures.append(failure)
        self._save_failures(failures)
        
        return failure_id
    
    def find_failure_by_test(self, test_name: str) -> Optional[Dict[str, Any]]:
        """Find existing failure by test name."""
        failures = self._load_failures()
        for failure in failures:
            if failure["test_name"] == test_name:
                return failure
        return None
    
    def find_failure_by_id(self, failure_id: str) -> Optional[Dict[str, Any]]:
        """Find failure by ID."""
        failures = self._load_failures()
        for failure in failures:
            if failure["id"] == failure_id:
                return failure
        return None
    
    def update_fix_attempt(self, failure_id: str, fix_description: str, fix_type: str = "attempted") -> bool:
        """Record a fix attempt for a failure."""
        failures = self._load_failures()
        
        for failure in failures:
            if failure["id"] == failure_id:
                fix_record = {
                    "timestamp": datetime.now().isoformat(),
                    "type": fix_type,
                    "description": fix_description,
                    "success": False  # Will be updated when resolution is confirmed
                }
                failure["attempted_fixes"].append(fix_record)
                failure["status"] = FailureStatus.IN_PROGRESS.value
                self._save_failures(failures)
                return True
        
        return False
    
    def mark_resolved(self, failure_id: str, resolution_details: str, lessons_learned: str = "") -> bool:
        """Mark a failure as resolved."""
        failures = self._load_failures()
        
        for failure in failures:
            if failure["id"] == failure_id:
                failure["status"] = FailureStatus.RESOLVED.value
                failure["resolution"] = resolution_details
                failure["lessons_learned"] = lessons_learned
                
                # Mark last fix attempt as successful
                if failure["attempted_fixes"]:
                    failure["attempted_fixes"][-1]["success"] = True
                
                self._save_failures(failures)
                return True
        
        return False
    
    def mark_wont_fix(self, failure_id: str, reason: str) -> bool:
        """Mark a failure as won't fix."""
        failures = self._load_failures()
        
        for failure in failures:
            if failure["id"] == failure_id:
                failure["status"] = FailureStatus.WONT_FIX.value
                failure["resolution"] = f"Won't fix: {reason}"
                self._save_failures(failures)
                return True
        
        return False
    
    def get_failures_by_status(self, status: Union[FailureStatus, str]) -> List[Dict[str, Any]]:
        """Get all failures with specified status."""
        if isinstance(status, FailureStatus):
            status = status.value
        
        failures = self._load_failures()
        return [f for f in failures if f["status"] == status]
    
    def get_failures_by_severity(self, severity: Union[Severity, str]) -> List[Dict[str, Any]]:
        """Get all failures with specified severity."""
        if isinstance(severity, Severity):
            severity = severity.value
        
        failures = self._load_failures()
        return [f for f in failures if f["severity"] == severity]
    
    def get_critical_failures(self) -> List[Dict[str, Any]]:
        """Get all critical failures that need immediate attention."""
        return self.get_failures_by_severity(Severity.CRITICAL)
    
    def get_active_failures(self) -> List[Dict[str, Any]]:
        """Get all active (unresolved) failures."""
        failures = self._load_failures()
        active_statuses = [FailureStatus.NEW.value, FailureStatus.IN_PROGRESS.value, FailureStatus.NEEDS_INVESTIGATION.value]
        return [f for f in failures if f["status"] in active_statuses]
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate summary report of all failures."""
        failures = self._load_failures()
        
        # Count by status
        status_counts = {}
        for status in FailureStatus:
            status_counts[status.value] = len([f for f in failures if f["status"] == status.value])
        
        # Count by severity
        severity_counts = {}
        for severity in Severity:
            severity_counts[severity.value] = len([f for f in failures if f["severity"] == severity.value])
        
        # Count by error type
        error_type_counts = {}
        for error_type in ErrorType:
            error_type_counts[error_type.value] = len([f for f in failures if f["error_type"] == error_type.value])
        
        return {
            "total_failures": len(failures),
            "active_failures": len(self.get_active_failures()),
            "critical_failures": len(self.get_critical_failures()),
            "status_breakdown": status_counts,
            "severity_breakdown": severity_counts,
            "error_type_breakdown": error_type_counts,
            "most_frequent_failures": sorted(failures, key=lambda f: f["metadata"]["frequency"], reverse=True)[:5]
        }


# Convenience functions for quick failure tracking
def record_test_failure(test_name: str, error_message: str, **kwargs) -> str:
    """Quick function to record a test failure."""
    tracker = FailureTracker()
    return tracker.record_failure(test_name, error_message, **kwargs)


def update_failure_fix(failure_id: str, fix_description: str) -> bool:
    """Quick function to update a fix attempt."""
    tracker = FailureTracker()
    return tracker.update_fix_attempt(failure_id, fix_description)


def resolve_failure(failure_id: str, resolution: str, lessons: str = "") -> bool:
    """Quick function to resolve a failure."""
    tracker = FailureTracker()
    return tracker.mark_resolved(failure_id, resolution, lessons)


if __name__ == "__main__":
    # Demo usage
    tracker = FailureTracker()
    
    # Record a sample failure
    failure_id = tracker.record_failure(
        test_name="test_vtt_file_processing",
        error_message="Neo4j connection failed",
        error_type=ErrorType.CONNECTION,
        severity=Severity.HIGH,
        test_category="e2e"
    )
    
    print(f"Recorded failure: {failure_id}")
    
    # Update with fix attempt
    tracker.update_fix_attempt(failure_id, "Started Neo4j service")
    
    # Show summary
    summary = tracker.generate_summary_report()
    print(f"Total failures: {summary['total_failures']}")
    print(f"Active failures: {summary['active_failures']}")