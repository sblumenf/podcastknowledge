#!/usr/bin/env python3
"""Test script to demonstrate pipeline metrics collection."""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.monitoring import get_pipeline_metrics
from src.utils.logging import get_logger

logger = get_logger(__name__)


def simulate_file_processing():
    """Simulate file processing with metrics."""
    metrics = get_pipeline_metrics()
    
    # Simulate processing 5 files
    for i in range(5):
        file_name = f"test_file_{i}.vtt"
        start_time = time.time()
        
        # Simulate processing time (varies per file)
        processing_time = 2 + i * 0.5
        time.sleep(processing_time)
        
        # Simulate entity extraction
        entity_count = 10 + i * 5
        metrics.record_entity_extraction(entity_count)
        
        # Record file processing
        end_time = time.time()
        success = i != 2  # Make file 2 fail
        metrics.record_file_processing(
            file_name,
            start_time,
            end_time,
            segments=20 + i * 3,
            success=success
        )
        
        print(f"Processed {file_name}: {'Success' if success else 'Failed'}")


def simulate_api_calls():
    """Simulate API calls with metrics."""
    metrics = get_pipeline_metrics()
    
    # Simulate Gemini API calls
    for i in range(10):
        latency = 0.5 + (i % 3) * 0.2
        success = i != 7  # Make call 7 fail
        
        time.sleep(latency)
        metrics.record_api_call("gemini", success, latency)
    
    # Simulate OpenAI API calls  
    for i in range(5):
        latency = 0.8 + (i % 2) * 0.3
        metrics.record_api_call("openai", True, latency)
        time.sleep(latency)
    
    print("Simulated API calls")


def simulate_database_operations():
    """Simulate database operations with metrics."""
    metrics = get_pipeline_metrics()
    
    # Simulate various database operations
    operations = [
        ("query", 0.05),
        ("create_node", 0.1),
        ("bulk_create_nodes", 0.3),
        ("create_relationship", 0.08),
        ("query", 0.04),
        ("query", 0.06),
        ("bulk_create_nodes", 0.25),
        ("query", 1.2),  # Slow query
    ]
    
    for op_type, latency in operations:
        time.sleep(latency)
        success = latency < 1.0  # Fail slow operations
        metrics.record_db_operation(op_type, latency, success)
    
    print("Simulated database operations")


def test_anomaly_detection():
    """Test anomaly detection with custom callback."""
    metrics = get_pipeline_metrics()
    
    anomalies_detected = []
    
    def anomaly_callback(anomaly_type: str, details: dict):
        """Callback for anomaly detection."""
        anomalies_detected.append({
            'type': anomaly_type,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
        print(f"🚨 Anomaly detected: {anomaly_type}")
        print(f"   Details: {json.dumps(details, indent=2)}")
    
    # Register callback
    metrics.add_anomaly_callback(anomaly_callback)
    
    # Trigger some anomalies
    print("\nTriggering anomalies...")
    
    # High memory usage (simulated)
    # This would normally be detected by the monitoring thread
    metrics._trigger_anomaly('high_memory', {
        'current_mb': 2500,
        'threshold_mb': 2048
    })
    
    # Slow file processing
    metrics.record_file_processing(
        "slow_file.vtt",
        time.time() - 700,  # 11+ minutes ago
        time.time(),
        segments=100,
        success=True
    )
    
    # High API failure rate
    for _ in range(15):
        metrics.record_api_call("failing_api", False, 0.5)
    for _ in range(5):
        metrics.record_api_call("failing_api", True, 0.5)
    
    return anomalies_detected


def main():
    """Main test function."""
    # Set up logging
    setup_enhanced_logging(
        level="INFO",
        log_file="logs/metrics_test.log",
        structured=True,
        enable_metrics=True,
        enable_tracing=True
    )
    
    print("=" * 60)
    print("Pipeline Metrics Collection Test")
    print("=" * 60)
    
    # Get metrics instance and start monitoring
    metrics = get_pipeline_metrics()
    
    print("\n1. Testing File Processing Metrics")
    print("-" * 40)
    simulate_file_processing()
    
    print("\n2. Testing API Call Metrics")
    print("-" * 40)
    simulate_api_calls()
    
    print("\n3. Testing Database Operation Metrics")
    print("-" * 40)
    simulate_database_operations()
    
    print("\n4. Testing Anomaly Detection")
    print("-" * 40)
    anomalies = test_anomaly_detection()
    
    # Wait a bit for background monitoring
    print("\n5. Background Monitoring (5 seconds)")
    print("-" * 40)
    time.sleep(5)
    
    # Get current metrics
    print("\n6. Current Metrics Snapshot")
    print("-" * 40)
    current_metrics = metrics.get_current_metrics()
    
    print(f"Uptime: {current_metrics['uptime_seconds']:.1f} seconds")
    print(f"\nFile Processing:")
    print(f"  Total: {current_metrics['files']['total_processed']}")
    print(f"  Successful: {current_metrics['files']['successful']}")
    print(f"  Failed: {current_metrics['files']['failed']}")
    print(f"  Avg Duration: {current_metrics['files']['average_duration']:.2f}s")
    
    print(f"\nMemory Usage:")
    print(f"  Current: {current_metrics['memory']['current_mb']:.1f}MB")
    print(f"  Average: {current_metrics['memory']['average_mb']:.1f}MB")
    print(f"  Maximum: {current_metrics['memory']['max_mb']:.1f}MB")
    
    print(f"\nDatabase Operations:")
    print(f"  Tracked: {current_metrics['database']['operations_tracked']}")
    print(f"  Avg Latency: {current_metrics['database']['average_latency_ms']:.1f}ms")
    print(f"  Max Latency: {current_metrics['database']['max_latency_ms']:.1f}ms")
    
    print(f"\nAPI Calls:")
    for provider, stats in current_metrics['api'].items():
        print(f"  {provider}:")
        print(f"    Total: {stats['total_calls']}")
        print(f"    Success Rate: {stats['success_rate']*100:.1f}%")
        if stats['failures'] > 0:
            print(f"    Failures: {stats['failures']}")
    
    print(f"\nExtraction Performance:")
    print(f"  Entity Rate: {current_metrics['extraction']['entities_per_minute']:.1f} entities/min")
    
    print(f"\nAnomalies Detected: {len(anomalies)}")
    
    # Export metrics
    print("\n7. Exporting Metrics")
    print("-" * 40)
    export_path = metrics.export_metrics()
    print(f"Metrics exported to: {export_path}")
    
    # Show sample of exported data
    with open(export_path, 'r') as f:
        data = json.load(f)
        print(f"\nExported metrics contains:")
        print(f"  - Current snapshot")
        print(f"  - {len(data['detailed_metrics']['metrics'])} detailed metric types")
        print(f"  - {len(data['file_details'])} file processing records")
        print(f"  - Configured thresholds")
    
    # Cleanup
    cleanup_metrics()
    print("\n✅ Metrics collection test completed successfully!")


if __name__ == "__main__":
    main()