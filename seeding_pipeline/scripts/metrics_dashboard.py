#!/usr/bin/env python3
"""Simple metrics dashboard for VTT pipeline monitoring."""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.monitoring import get_pipeline_metrics


class MetricsDashboard:
    """Simple text-based metrics dashboard."""
    
    def __init__(self):
        self.metrics = get_pipeline_metrics()
        self.refresh_interval = 5  # seconds
        
    def clear_screen(self):
        """Clear terminal screen."""
        print("\033[2J\033[H", end="")
    
    def format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
    
    def format_bytes(self, bytes_val: float) -> str:
        """Format bytes in human-readable format."""
        mb = bytes_val / 1024 / 1024
        if mb < 1024:
            return f"{mb:.1f}MB"
        else:
            gb = mb / 1024
            return f"{gb:.2f}GB"
    
    def draw_bar(self, value: float, max_value: float, width: int = 20) -> str:
        """Draw a simple ASCII progress bar."""
        if max_value <= 0:
            return "─" * width
        
        filled = int((value / max_value) * width)
        filled = min(filled, width)  # Cap at width
        
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"
    
    def display_header(self, data: Dict[str, Any]):
        """Display dashboard header."""
        print("╔" + "═" * 78 + "╗")
        print("║" + " VTT Pipeline Metrics Dashboard ".center(78) + "║")
        print("╠" + "═" * 78 + "╣")
        
        # Current time and uptime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        uptime = self.format_duration(data['uptime_seconds'])
        print(f"║ Time: {current_time:<30} Uptime: {uptime:<20} ║")
        print("╚" + "═" * 78 + "╝")
    
    def display_file_metrics(self, files: Dict[str, Any]):
        """Display file processing metrics."""
        print("\n📁 File Processing")
        print("─" * 40)
        
        total = files['total_processed']
        successful = files['successful']
        failed = files['failed']
        
        if total > 0:
            success_rate = (successful / total) * 100
            print(f"Total Files: {total}")
            print(f"Success: {successful} ({success_rate:.1f}%)")
            print(f"Failed: {failed}")
            
            # Success rate bar
            bar = self.draw_bar(successful, total, 30)
            print(f"Success Rate: {bar} {success_rate:.1f}%")
            
            # Average duration
            avg_duration = files['average_duration']
            print(f"Avg Duration: {self.format_duration(avg_duration)}")
        else:
            print("No files processed yet")
    
    def display_memory_metrics(self, memory: Dict[str, Any]):
        """Display memory usage metrics."""
        print("\n💾 Memory Usage")
        print("─" * 40)
        
        current = memory['current_mb']
        average = memory['average_mb']
        maximum = memory['max_mb']
        
        # Memory bar (assume 2GB threshold)
        threshold = 2048
        bar = self.draw_bar(current, threshold, 30)
        
        print(f"Current: {current:.1f}MB {bar}")
        print(f"Average: {average:.1f}MB")
        print(f"Maximum: {maximum:.1f}MB")
        
        # Warning if approaching threshold
        if current > threshold * 0.8:
            print("⚠️  WARNING: High memory usage!")
    
    def display_database_metrics(self, db: Dict[str, Any]):
        """Display database operation metrics."""
        print("\n🗄️  Database Operations")
        print("─" * 40)
        
        avg_latency = db['average_latency_ms']
        max_latency = db['max_latency_ms']
        ops_count = db['operations_tracked']
        
        if ops_count > 0:
            # Latency bar (assume 100ms is good, 1000ms is threshold)
            bar = self.draw_bar(avg_latency, 100, 30)
            
            print(f"Operations: {ops_count}")
            print(f"Avg Latency: {avg_latency:.1f}ms {bar}")
            print(f"Max Latency: {max_latency:.1f}ms")
            
            # Warning for high latency
            if avg_latency > 100:
                print("⚠️  WARNING: High database latency!")
        else:
            print("No database operations tracked yet")
    
    def display_api_metrics(self, api: Dict[str, Dict[str, Any]]):
        """Display API call metrics."""
        print("\n🌐 API Calls")
        print("─" * 40)
        
        if api:
            for provider, stats in api.items():
                total = stats['total_calls']
                success_rate = stats['success_rate'] * 100
                failures = stats['failures']
                
                # Success rate bar
                bar = self.draw_bar(success_rate, 100, 20)
                
                print(f"{provider.capitalize()}:")
                print(f"  Total Calls: {total}")
                print(f"  Success Rate: {bar} {success_rate:.1f}%")
                if failures > 0:
                    print(f"  Failures: {failures} ⚠️")
        else:
            print("No API calls tracked yet")
    
    def display_extraction_metrics(self, extraction: Dict[str, Any]):
        """Display extraction rate metrics."""
        print("\n⚡ Extraction Performance")
        print("─" * 40)
        
        rate = extraction['entities_per_minute']
        if rate > 0:
            print(f"Entity Extraction Rate: {rate:.1f} entities/minute")
            
            # Performance indicator
            if rate < 10:
                indicator = "🟥 Slow"
            elif rate < 50:
                indicator = "🟨 Normal"
            else:
                indicator = "🟢 Fast"
            
            print(f"Performance: {indicator}")
        else:
            print("No extraction data available yet")
    
    def display_alerts(self, metrics_data: Dict[str, Any]):
        """Display any active alerts based on thresholds."""
        alerts = []
        
        # Check memory
        if metrics_data['memory']['current_mb'] > 2048:
            alerts.append("🚨 Memory usage exceeds 2GB threshold!")
        
        # Check database latency
        if metrics_data['database']['average_latency_ms'] > 1000:
            alerts.append("🚨 Database latency exceeds 1s threshold!")
        
        # Check API failures
        for provider, stats in metrics_data['api'].items():
            if stats.get('success_rate', 1) < 0.9:
                alerts.append(f"🚨 {provider} API success rate below 90%!")
        
        if alerts:
            print("\n⚠️  Active Alerts")
            print("─" * 40)
            for alert in alerts:
                print(alert)
    
    def run_dashboard(self, continuous: bool = True):
        """Run the metrics dashboard.
        
        Args:
            continuous: Whether to continuously refresh
        """
        try:
            while True:
                # Get current metrics
                metrics_data = self.metrics.get_current_metrics()
                
                # Clear screen and display
                if continuous:
                    self.clear_screen()
                
                self.display_header(metrics_data)
                self.display_file_metrics(metrics_data['files'])
                self.display_memory_metrics(metrics_data['memory'])
                self.display_database_metrics(metrics_data['database'])
                self.display_api_metrics(metrics_data['api'])
                self.display_extraction_metrics(metrics_data['extraction'])
                self.display_alerts(metrics_data)
                
                if not continuous:
                    break
                
                # Footer
                print(f"\nRefreshing every {self.refresh_interval} seconds... Press Ctrl+C to exit")
                
                time.sleep(self.refresh_interval)
                
        except KeyboardInterrupt:
            print("\n\nDashboard stopped.")
    
    def export_snapshot(self, output_path: Optional[str] = None):
        """Export current metrics snapshot."""
        path = self.metrics.export_metrics(output_path)
        print(f"\n📊 Metrics exported to: {path}")
        return path


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="VTT Pipeline Metrics Dashboard")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Display metrics once and exit"
    )
    parser.add_argument(
        "--export",
        type=str,
        help="Export metrics to specified file"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Refresh interval in seconds (default: 5)"
    )
    
    args = parser.parse_args()
    
    dashboard = MetricsDashboard()
    dashboard.refresh_interval = args.interval
    
    if args.export:
        dashboard.export_snapshot(args.export)
    else:
        dashboard.run_dashboard(continuous=not args.once)


if __name__ == "__main__":
    main()