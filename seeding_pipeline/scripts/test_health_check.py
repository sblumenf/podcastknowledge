#!/usr/bin/env python3
"""Test script to demonstrate health check functionality."""

import sys
import json
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.health_check import get_health_checker, HealthStatus
from src.utils.logging_enhanced import setup_enhanced_logging


def test_health_checks():
    """Test all health check functionality."""
    print("=" * 60)
    print("VTT Pipeline Health Check Test")
    print("=" * 60)
    
    # Get health checker
    health_checker = get_health_checker()
    
    # Test 1: Full health check
    print("\n1. Full System Health Check")
    print("-" * 40)
    
    health_data = health_checker.check_all()
    
    print(f"Overall Status: {health_data['status']}")
    print(f"Summary: {health_data['summary']}")
    print(f"Check Duration: {health_data['duration_seconds']:.2f}s")
    
    print("\nComponent Details:")
    for component in health_data['components']:
        status_icon = {
            'healthy': '✅',
            'degraded': '⚠️',
            'unhealthy': '❌'
        }.get(component['status'], '❓')
        
        print(f"  {status_icon} {component['name']:<15} - {component['message']}")
    
    # Test 2: Individual component checks
    print("\n2. Individual Component Checks")
    print("-" * 40)
    
    components = ['system', 'neo4j', 'llm_api', 'checkpoints', 'metrics']
    
    for comp_name in components:
        try:
            check_method = health_checker._component_checks[comp_name]
            result = check_method()
            
            print(f"\n{comp_name.upper()}:")
            print(f"  Status: {result.status}")
            print(f"  Message: {result.message}")
            if result.details:
                print(f"  Details: {json.dumps(result.details, indent=4)}")
        except Exception as e:
            print(f"\n{comp_name.upper()}: Error - {str(e)}")
    
    # Test 3: CLI formatted output
    print("\n3. CLI Formatted Output")
    print("-" * 40)
    cli_summary = health_checker.get_cli_summary()
    print(cli_summary)
    
    # Test 4: Anomaly callbacks
    print("\n4. Testing Anomaly Detection Callbacks")
    print("-" * 40)
    
    anomalies = []
    
    def anomaly_callback(anomaly_type: str, details: dict):
        anomalies.append({
            'type': anomaly_type,
            'details': details,
            'timestamp': time.time()
        })
        print(f"  🚨 Anomaly: {anomaly_type}")
        print(f"     Details: {json.dumps(details, indent=6)}")
    
    health_checker.add_anomaly_callback = lambda cb: None  # Mock if not available
    
    # Test 5: Export health data as JSON
    print("\n5. JSON Export")
    print("-" * 40)
    
    # Export to file
    export_file = Path("health_check_export.json")
    with open(export_file, 'w') as f:
        json.dump(health_data, f, indent=2)
    
    print(f"Health data exported to: {export_file}")
    print(f"File size: {export_file.stat().st_size} bytes")
    
    # Show sample of exported data
    print("\nSample of exported data:")
    print(json.dumps({
        'status': health_data['status'],
        'timestamp': health_data['timestamp'],
        'component_count': len(health_data['components']),
        'summary': health_data['summary']
    }, indent=2))
    
    # Cleanup
    export_file.unlink()
    
    # Test 6: Performance of health checks
    print("\n6. Health Check Performance")
    print("-" * 40)
    
    # Time individual checks
    check_times = {}
    
    for comp_name, check_method in health_checker._component_checks.items():
        start_time = time.time()
        try:
            check_method()
            check_time = time.time() - start_time
            check_times[comp_name] = check_time
        except:
            check_times[comp_name] = -1
    
    print("Component check times:")
    for comp, check_time in check_times.items():
        if check_time >= 0:
            print(f"  {comp:<15}: {check_time*1000:.1f}ms")
        else:
            print(f"  {comp:<15}: Failed")
    
    total_time = sum(t for t in check_times.values() if t >= 0)
    print(f"\nTotal time for all checks: {total_time*1000:.1f}ms")
    
    print("\n✅ Health check test completed successfully!")


def test_cli_command():
    """Test the CLI health command."""
    print("\n\n" + "=" * 60)
    print("Testing CLI Health Command")
    print("=" * 60)
    
    import subprocess
    
    # Test 1: Basic health check
    print("\n1. Basic health check (text format)")
    print("-" * 40)
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.cli", "health"],
        capture_output=True,
        text=True
    )
    print("Exit code:", result.returncode)
    print("Output:")
    print(result.stdout)
    
    # Test 2: JSON format
    print("\n2. Health check (JSON format)")
    print("-" * 40)
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.cli", "health", "--format", "json"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            print(f"Status: {data['status']}")
            print(f"Components checked: {len(data['components'])}")
        except:
            print("Failed to parse JSON output")
    
    # Test 3: Specific component
    print("\n3. Check specific component (system)")
    print("-" * 40)
    result = subprocess.run(
        [sys.executable, "-m", "src.cli.cli", "health", "--component", "system"],
        capture_output=True,
        text=True
    )
    print(result.stdout)


def main():
    """Main test function."""
    # Set up logging
    setup_enhanced_logging(
        level="INFO",
        log_file="logs/health_check_test.log",
        structured=True
    )
    
    # Run tests
    test_health_checks()
    
    # Optionally test CLI (uncomment to test)
    # test_cli_command()


if __name__ == "__main__":
    main()