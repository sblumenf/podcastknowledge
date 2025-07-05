#!/usr/bin/env python3
"""Test script to demonstrate enhanced logging capabilities."""

import sys
import time
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging import (
    setup_enhanced_logging,
    get_logger,
    log_performance_metric,
    trace_operation,
    log_batch_progress,
    get_metrics_collector,
    ProcessingTraceLogger
)


@trace_operation("sample_processing")
def process_sample_data(items: list) -> dict:
    """Sample function demonstrating tracing."""
    logger = get_logger(__name__)
    logger.info("Starting sample processing", extra={
        'item_count': len(items),
        'operation': 'sample_processing'
    })
    
    # Simulate processing
    results = []
    for i, item in enumerate(items):
        time.sleep(0.1)  # Simulate work
        results.append(f"Processed: {item}")
        
        # Log progress
        log_batch_progress(
            logger,
            i + 1,
            len(items),
            "processing_items",
            time.time()
        )
    
    # Log performance metric
    log_performance_metric(
        logger,
        "sample_processing.items_per_second",
        len(items) / (len(items) * 0.1),
        unit="items/second",
        operation="sample_processing"
    )
    
    return {'results': results, 'count': len(results)}


def test_trace_logger():
    """Test the ProcessingTraceLogger."""
    logger = get_logger(__name__)
    tracer = ProcessingTraceLogger(logger)
    
    # Start a trace
    trace_id = tracer.start_trace("database_operation", {
        'query_type': 'SELECT',
        'table': 'episodes'
    })
    
    # Simulate operation
    time.sleep(0.2)
    
    # End trace with result
    tracer.end_trace(trace_id, result={'rows_returned': 42})
    
    # Test error trace
    error_trace_id = tracer.start_trace("failing_operation")
    try:
        raise ValueError("Simulated error")
    except Exception as e:
        tracer.end_trace(error_trace_id, error=e)


def test_metrics_collection():
    """Test metrics collection."""
    logger = get_logger(__name__)
    collector = get_metrics_collector()
    
    # Record various metrics
    for i in range(10):
        collector.record_metric(
            "test.latency",
            0.1 * (i + 1),
            unit="seconds",
            tags={'endpoint': '/api/test', 'method': 'GET'}
        )
    
    # Get summary
    summary = collector.get_summary("test.latency")
    logger.info("Metrics summary", extra={
        'metric': 'test.latency',
        'summary': summary
    })
    
    # Get all metrics
    all_metrics = collector.get_metrics()
    logger.info(f"Total metrics collected: {len(all_metrics['metrics'])}")


def main():
    """Main test function."""
    # Set up enhanced logging
    log_file = "logs/enhanced_logging_test.log"
    setup_enhanced_logging(
        level="DEBUG",
        log_file=log_file,
        max_bytes=5 * 1024 * 1024,  # 5MB
        backup_count=3,
        structured=True,
        enable_metrics=True,
        enable_tracing=True
    )
    
    logger = get_logger(__name__)
    logger.info("Enhanced logging test started")
    
    # Test 1: Traced operation
    print("\n=== Testing Traced Operations ===")
    items = ['item1', 'item2', 'item3', 'item4', 'item5']
    result = process_sample_data(items)
    print(f"Processing result: {result}")
    
    # Test 2: Trace logger
    print("\n=== Testing Trace Logger ===")
    test_trace_logger()
    
    # Test 3: Metrics collection
    print("\n=== Testing Metrics Collection ===")
    test_metrics_collection()
    
    # Test 4: Log rotation
    print("\n=== Testing Log Rotation ===")
    logger.info("Testing log rotation by writing many messages")
    for i in range(100):
        logger.debug(f"Log rotation test message {i}", extra={
            'message_index': i,
            'test_data': 'x' * 1000  # Make messages larger
        })
    
    # Display metrics summary
    print("\n=== Metrics Summary ===")
    collector = get_metrics_collector()
    metrics = collector.get_metrics()
    
    print(f"Uptime: {metrics['uptime_seconds']:.2f} seconds")
    print(f"Metrics collected: {len(metrics['metrics'])}")
    
    for metric_name, metric_data in metrics['metrics'].items():
        summary = collector.get_summary(metric_name)
        if summary:
            print(f"\n{metric_name}:")
            print(f"  Count: {summary['count']}")
            print(f"  Average: {summary['avg']:.3f}")
            print(f"  Min: {summary['min']:.3f}")
            print(f"  Max: {summary['max']:.3f}")
    
    # Check log file
    print(f"\n=== Log File Info ===")
    log_path = Path(log_file)
    if log_path.exists():
        size = log_path.stat().st_size
        print(f"Log file: {log_path}")
        print(f"Size: {size:,} bytes")
        
        # Check for rotated files
        rotated_files = list(log_path.parent.glob(f"{log_path.name}.*"))
        if rotated_files:
            print(f"Rotated files: {len(rotated_files)}")
            for rf in rotated_files:
                print(f"  - {rf.name} ({rf.stat().st_size:,} bytes)")
    
    print("\n=== Sample Log Entries ===")
    if log_path.exists():
        with open(log_path, 'r') as f:
            # Read last 5 lines
            lines = f.readlines()
            for line in lines[-5:]:
                try:
                    log_entry = json.loads(line)
                    print(f"[{log_entry['level']}] {log_entry['message']}")
                    if 'duration_seconds' in log_entry:
                        print(f"  Duration: {log_entry['duration_seconds']:.3f}s")
                except:
                    pass
    
    logger.info("Enhanced logging test completed")
    print("\nTest completed successfully!")


if __name__ == "__main__":
    main()