"""
Test Failure Tracking System for VTT Knowledge Graph Pipeline

This package provides systematic tracking and resolution of test failures.
Part of Phase 6: Test Failure Resolution

Main Components:
- FailureTracker: Core tracking functionality
- track_failure.py: Main tracking implementation
- failure_handling_process.md: Process documentation

Usage:
    from test_tracking import FailureTracker, record_test_failure
    
    # Record a failure
    failure_id = record_test_failure("test_name", "error_message")
    
    # Track resolution
    tracker = FailureTracker()
    tracker.mark_resolved(failure_id, "Fixed by starting Neo4j")
"""

from .track_failure import (
    FailureTracker,
    ErrorType,
    Severity,
    FailureStatus,
    record_test_failure,
    update_failure_fix,
    resolve_failure
)

__all__ = [
    'FailureTracker',
    'ErrorType', 
    'Severity',
    'FailureStatus',
    'record_test_failure',
    'update_failure_fix',
    'resolve_failure'
]