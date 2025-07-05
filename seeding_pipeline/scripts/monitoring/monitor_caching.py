#!/usr/bin/env python3
"""Real-time monitoring dashboard for Gemini caching performance."""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services import LLMServiceFactory, LLMServiceType
from src.services.cache_manager import CacheManager
from src.utils.key_rotation_manager import create_key_rotation_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CachingMonitor:
    """Monitor and display caching performance metrics."""
    
    def __init__(self):
        """Initialize monitor with service instances."""
        self.key_manager = create_key_rotation_manager()
        
        # Create service with caching
        service_type = os.getenv('LLM_SERVICE_TYPE', LLMServiceType.GEMINI_CACHED)
        self.service = LLMServiceFactory.create_service(
            key_rotation_manager=self.key_manager,
            service_type=service_type
        )
        
        # Get cache manager if available
        if hasattr(self.service, '_cache_manager'):
            self.cache_manager = self.service._cache_manager
        else:
            logger.warning("Service does not have cache manager - creating standalone")
            self.cache_manager = CacheManager()
            
        self.start_time = datetime.now()
        self.last_stats = None
        
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect current metrics."""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'uptime': str(datetime.now() - self.start_time),
            'cache_stats': self.cache_manager.get_cache_stats(),
            'cost_savings': self.cache_manager.estimate_cost_savings(),
            'key_rotation': self.key_manager.get_status_summary()
        }
        
        # Calculate deltas if we have previous stats
        if self.last_stats:
            prev_cache = self.last_stats.get('cache_stats', {})
            curr_cache = metrics['cache_stats']
            
            metrics['deltas'] = {
                'hits': curr_cache.get('hits', 0) - prev_cache.get('hits', 0),
                'misses': curr_cache.get('misses', 0) - prev_cache.get('misses', 0),
                'creates': curr_cache.get('creates', 0) - prev_cache.get('creates', 0),
                'evictions': curr_cache.get('evictions', 0) - prev_cache.get('evictions', 0)
            }
            
        self.last_stats = metrics
        return metrics
        
    def display_dashboard(self, metrics: Dict[str, Any]):
        """Display metrics in dashboard format."""
        # Clear screen (works on Unix-like systems)
        os.system('clear' if os.name != 'nt' else 'cls')
        
        print("=" * 80)
        print(f"🔍 Gemini Caching Monitor - {metrics['timestamp']}")
        print(f"⏱️  Uptime: {metrics['uptime']}")
        print("=" * 80)
        
        # Cache Performance
        cache_stats = metrics['cache_stats']
        print("\n📊 Cache Performance:")
        print(f"  Hit Rate: {cache_stats['hit_rate']:.1%}")
        print(f"  Hits: {cache_stats['hits']:,} | Misses: {cache_stats['misses']:,}")
        print(f"  Active Caches: {cache_stats['active_episode_caches']} episodes, "
              f"{cache_stats['active_prompt_caches']} prompts")
        print(f"  Total Cached Tokens: {cache_stats['total_cached_tokens']:,}")
        
        # Recent Activity
        if 'deltas' in metrics:
            deltas = metrics['deltas']
            if any(deltas.values()):
                print("\n📈 Recent Activity (since last update):")
                if deltas['hits'] > 0:
                    print(f"  ✅ {deltas['hits']} cache hits")
                if deltas['misses'] > 0:
                    print(f"  ❌ {deltas['misses']} cache misses")
                if deltas['creates'] > 0:
                    print(f"  ➕ {deltas['creates']} new caches created")
                if deltas['evictions'] > 0:
                    print(f"  🗑️  {deltas['evictions']} caches evicted")
                    
        # Cost Savings
        savings = metrics['cost_savings']
        print("\n💰 Cost Analysis:")
        print(f"  Tokens Saved: {savings['tokens_saved']:,}")
        print(f"  Estimated Savings: ${savings['estimated_savings_usd']:.4f}")
        print(f"  Savings Rate: {savings['savings_percentage']:.0%}")
        
        # API Key Status
        key_status = metrics['key_rotation']
        print(f"\n🔑 API Key Status:")
        print(f"  Total Keys: {key_status['total_keys']}")
        print(f"  Available: {key_status['available_keys']}")
        
        # Recommendations
        print("\n💡 Recommendations:")
        if cache_stats['hit_rate'] < 0.5:
            print("  ⚠️  Low cache hit rate - consider increasing cache TTL")
        if cache_stats['active_episode_caches'] > 100:
            print("  ⚠️  Many active caches - consider cleanup")
        if savings['estimated_savings_usd'] < 0.01:
            print("  ℹ️  Low savings - process more episodes to see benefits")
        if cache_stats['hit_rate'] > 0.7:
            print("  ✅ Excellent cache performance!")
            
    def export_metrics(self, metrics: Dict[str, Any], filepath: Optional[Path] = None):
        """Export metrics to JSON file."""
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = Path(f"cache_metrics_{timestamp}.json")
            
        with open(filepath, 'w') as f:
            json.dump(metrics, f, indent=2)
            
        logger.info(f"Metrics exported to {filepath}")
        
    def run_continuous(self, interval: int = 10):
        """Run continuous monitoring."""
        print("Starting continuous monitoring... (Press Ctrl+C to stop)")
        
        try:
            while True:
                metrics = self.collect_metrics()
                self.display_dashboard(metrics)
                
                # Show countdown
                for i in range(interval, 0, -1):
                    print(f"\rNext update in {i}s... ", end='', flush=True)
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
            
            # Final export
            if self.last_stats:
                self.export_metrics(self.last_stats)
                
    def run_once(self) -> Dict[str, Any]:
        """Run monitoring once and return metrics."""
        metrics = self.collect_metrics()
        self.display_dashboard(metrics)
        return metrics


def main():
    """Run the monitoring dashboard."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor Gemini caching performance')
    parser.add_argument('--once', action='store_true', 
                       help='Run once instead of continuous monitoring')
    parser.add_argument('--export', type=str,
                       help='Export metrics to specified file')
    parser.add_argument('--interval', type=int, default=10,
                       help='Update interval in seconds (default: 10)')
    
    args = parser.parse_args()
    
    monitor = CachingMonitor()
    
    if args.once:
        metrics = monitor.run_once()
        if args.export:
            monitor.export_metrics(metrics, Path(args.export))
    else:
        monitor.run_continuous(interval=args.interval)


if __name__ == "__main__":
    main()