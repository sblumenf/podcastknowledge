"""Metrics and monitoring for speaker identification system."""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
import statistics

logger = logging.getLogger(__name__)


class SpeakerIdentificationMetrics:
    """Comprehensive metrics tracking for speaker identification."""
    
    def __init__(self, 
                 metrics_dir: Optional[Path] = None,
                 window_size: int = 1000,
                 persist_interval: int = 100):
        """
        Initialize metrics tracker.
        
        Args:
            metrics_dir: Directory for persistent metrics storage
            window_size: Size of rolling window for metrics
            persist_interval: Number of operations between persists
        """
        self.metrics_dir = metrics_dir
        self.window_size = window_size
        self.persist_interval = persist_interval
        self.operation_count = 0
        
        # Initialize metrics storage
        self.metrics = {
            'total_identifications': 0,
            'successful_identifications': 0,
            'cache_hits': 0,
            'cache_attempts': 0,
            'llm_calls': 0,
            'llm_timeouts': 0,
            'llm_errors': 0,
            'total_speakers_identified': 0,
            'total_segments_processed': 0,
            'start_time': datetime.now().isoformat()
        }
        
        # Rolling windows for performance tracking
        self.response_times = deque(maxlen=window_size)
        self.confidence_scores = deque(maxlen=window_size)
        self.speakers_per_episode = deque(maxlen=window_size)
        self.cache_hit_window = deque(maxlen=100)
        
        # Error tracking
        self.error_types = defaultdict(int)
        self.podcast_stats = defaultdict(lambda: {
            'episodes': 0,
            'successful': 0,
            'speakers_identified': 0,
            'avg_confidence': 0.0
        })
        
        # Setup persistence
        if self.metrics_dir:
            self.metrics_dir = Path(self.metrics_dir)
            self.metrics_dir.mkdir(parents=True, exist_ok=True)
            self._load_metrics()
    
    def record_identification(self,
                            podcast_name: str,
                            result: Dict[str, Any],
                            duration: float) -> None:
        """
        Record a speaker identification operation.
        
        Args:
            podcast_name: Name of the podcast
            result: Identification result dict
            duration: Time taken for identification
        """
        self.operation_count += 1
        self.metrics['total_identifications'] += 1
        
        # Extract metrics from result
        performance = result.get('performance', {})
        was_cache_hit = performance.get('cache_hit', False)
        speakers_identified = len(result.get('speaker_mappings', {}))
        segments_processed = performance.get('segments_processed', 0)
        
        # Update counters
        if speakers_identified > 0:
            self.metrics['successful_identifications'] += 1
        
        if was_cache_hit:
            self.metrics['cache_hits'] += 1
            self.cache_hit_window.append(1)
        else:
            self.metrics['llm_calls'] += 1
            self.cache_hit_window.append(0)
            
        if 'cache_attempts' in performance:
            self.metrics['cache_attempts'] += 1
            
        self.metrics['total_speakers_identified'] += speakers_identified
        self.metrics['total_segments_processed'] += segments_processed
        
        # Track errors
        if 'errors' in result:
            for error in result['errors']:
                if 'timeout' in error.lower():
                    self.metrics['llm_timeouts'] += 1
                else:
                    self.metrics['llm_errors'] += 1
        
        # Update rolling windows
        self.response_times.append(duration)
        self.speakers_per_episode.append(speakers_identified)
        
        # Track confidence scores
        for score in result.get('confidence_scores', {}).values():
            self.confidence_scores.append(score)
        
        # Update podcast-specific stats
        podcast_stats = self.podcast_stats[podcast_name]
        podcast_stats['episodes'] += 1
        if speakers_identified > 0:
            podcast_stats['successful'] += 1
            podcast_stats['speakers_identified'] += speakers_identified
            
            # Update average confidence
            scores = list(result.get('confidence_scores', {}).values())
            if scores:
                current_avg = podcast_stats['avg_confidence']
                current_count = podcast_stats['episodes'] - 1
                new_avg = (current_avg * current_count + statistics.mean(scores)) / podcast_stats['episodes']
                podcast_stats['avg_confidence'] = new_avg
        
        # Persist if needed
        if self.operation_count % self.persist_interval == 0:
            self._persist_metrics()
    
    def record_error(self, error_type: str, podcast_name: Optional[str] = None) -> None:
        """
        Record an error occurrence.
        
        Args:
            error_type: Type of error
            podcast_name: Optional podcast name where error occurred
        """
        self.error_types[error_type] += 1
        
        if error_type == 'timeout':
            self.metrics['llm_timeouts'] += 1
        else:
            self.metrics['llm_errors'] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics summary.
        
        Returns:
            Dict with all metrics
        """
        # Calculate rates
        total = self.metrics['total_identifications']
        success_rate = (
            self.metrics['successful_identifications'] / total 
            if total > 0 else 0.0
        )
        
        cache_hit_rate = (
            self.metrics['cache_hits'] / self.metrics['cache_attempts']
            if self.metrics['cache_attempts'] > 0 else 0.0
        )
        
        # Calculate recent cache hit rate
        recent_cache_hits = sum(self.cache_hit_window)
        recent_cache_hit_rate = (
            recent_cache_hits / len(self.cache_hit_window)
            if self.cache_hit_window else 0.0
        )
        
        # Performance statistics
        avg_response_time = (
            statistics.mean(self.response_times) 
            if self.response_times else 0.0
        )
        
        p95_response_time = (
            sorted(self.response_times)[int(len(self.response_times) * 0.95)]
            if len(self.response_times) > 10 else 0.0
        )
        
        avg_confidence = (
            statistics.mean(self.confidence_scores)
            if self.confidence_scores else 0.0
        )
        
        avg_speakers = (
            statistics.mean(self.speakers_per_episode)
            if self.speakers_per_episode else 0.0
        )
        
        # Calculate uptime
        start_time = datetime.fromisoformat(self.metrics['start_time'])
        uptime = datetime.now() - start_time
        
        return {
            'overview': {
                'total_identifications': self.metrics['total_identifications'],
                'successful_identifications': self.metrics['successful_identifications'],
                'success_rate': round(success_rate, 3),
                'total_speakers_identified': self.metrics['total_speakers_identified'],
                'total_segments_processed': self.metrics['total_segments_processed'],
                'uptime_hours': round(uptime.total_seconds() / 3600, 2)
            },
            'cache_performance': {
                'cache_hits': self.metrics['cache_hits'],
                'cache_attempts': self.metrics['cache_attempts'],
                'cache_hit_rate': round(cache_hit_rate, 3),
                'recent_cache_hit_rate': round(recent_cache_hit_rate, 3),
                'llm_calls_saved': self.metrics['cache_hits']
            },
            'llm_performance': {
                'total_llm_calls': self.metrics['llm_calls'],
                'llm_timeouts': self.metrics['llm_timeouts'],
                'llm_errors': self.metrics['llm_errors'],
                'timeout_rate': round(
                    self.metrics['llm_timeouts'] / max(1, self.metrics['llm_calls']), 
                    3
                )
            },
            'response_times': {
                'avg_response_time_ms': round(avg_response_time * 1000, 2),
                'p95_response_time_ms': round(p95_response_time * 1000, 2),
                'min_response_time_ms': round(min(self.response_times) * 1000, 2) if self.response_times else 0,
                'max_response_time_ms': round(max(self.response_times) * 1000, 2) if self.response_times else 0
            },
            'quality_metrics': {
                'avg_confidence_score': round(avg_confidence, 3),
                'avg_speakers_per_episode': round(avg_speakers, 2),
                'high_confidence_rate': round(
                    sum(1 for s in self.confidence_scores if s >= 0.8) / len(self.confidence_scores),
                    3
                ) if self.confidence_scores else 0.0
            },
            'error_breakdown': dict(self.error_types),
            'top_podcasts': self._get_top_podcasts()
        }
    
    def get_podcast_metrics(self, podcast_name: str) -> Dict[str, Any]:
        """
        Get metrics for a specific podcast.
        
        Args:
            podcast_name: Name of the podcast
            
        Returns:
            Dict with podcast-specific metrics
        """
        if podcast_name not in self.podcast_stats:
            return {'error': 'No data for podcast'}
            
        stats = self.podcast_stats[podcast_name]
        return {
            'podcast_name': podcast_name,
            'episodes_processed': stats['episodes'],
            'successful_identifications': stats['successful'],
            'success_rate': round(stats['successful'] / stats['episodes'], 3) if stats['episodes'] > 0 else 0.0,
            'total_speakers_identified': stats['speakers_identified'],
            'avg_speakers_per_episode': round(
                stats['speakers_identified'] / stats['episodes'], 2
            ) if stats['episodes'] > 0 else 0.0,
            'avg_confidence_score': round(stats['avg_confidence'], 3)
        }
    
    def generate_report(self, output_path: Optional[Path] = None) -> str:
        """
        Generate a detailed metrics report.
        
        Args:
            output_path: Optional path to save report
            
        Returns:
            Report as string
        """
        summary = self.get_summary()
        
        report_lines = [
            "# Speaker Identification Metrics Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Overview",
            f"- Total Identifications: {summary['overview']['total_identifications']}",
            f"- Success Rate: {summary['overview']['success_rate']:.1%}",
            f"- Total Speakers Identified: {summary['overview']['total_speakers_identified']}",
            f"- Uptime: {summary['overview']['uptime_hours']:.1f} hours",
            "",
            "## Cache Performance",
            f"- Cache Hit Rate: {summary['cache_performance']['cache_hit_rate']:.1%}",
            f"- Recent Cache Hit Rate: {summary['cache_performance']['recent_cache_hit_rate']:.1%}",
            f"- LLM Calls Saved: {summary['cache_performance']['llm_calls_saved']}",
            "",
            "## Response Times",
            f"- Average: {summary['response_times']['avg_response_time_ms']:.0f}ms",
            f"- P95: {summary['response_times']['p95_response_time_ms']:.0f}ms",
            f"- Range: {summary['response_times']['min_response_time_ms']:.0f}ms - {summary['response_times']['max_response_time_ms']:.0f}ms",
            "",
            "## Quality Metrics",
            f"- Average Confidence: {summary['quality_metrics']['avg_confidence_score']:.2f}",
            f"- High Confidence Rate: {summary['quality_metrics']['high_confidence_rate']:.1%}",
            f"- Avg Speakers/Episode: {summary['quality_metrics']['avg_speakers_per_episode']:.1f}",
            "",
            "## Top Podcasts by Volume",
        ]
        
        for podcast in summary['top_podcasts']:
            report_lines.append(
                f"- {podcast['name']}: {podcast['episodes']} episodes "
                f"({podcast['success_rate']:.1%} success rate)"
            )
        
        report = "\n".join(report_lines)
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report)
            logger.info(f"Metrics report saved to {output_path}")
        
        return report
    
    def _get_top_podcasts(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top podcasts by episode count."""
        sorted_podcasts = sorted(
            self.podcast_stats.items(),
            key=lambda x: x[1]['episodes'],
            reverse=True
        )[:limit]
        
        return [
            {
                'name': name,
                'episodes': stats['episodes'],
                'success_rate': stats['successful'] / stats['episodes'] if stats['episodes'] > 0 else 0.0
            }
            for name, stats in sorted_podcasts
        ]
    
    def _persist_metrics(self) -> None:
        """Persist metrics to disk."""
        if not self.metrics_dir:
            return
            
        try:
            # Save main metrics
            metrics_file = self.metrics_dir / "speaker_metrics.json"
            with open(metrics_file, 'w') as f:
                json.dump({
                    'metrics': self.metrics,
                    'podcast_stats': dict(self.podcast_stats),
                    'error_types': dict(self.error_types)
                }, f, indent=2)
            
            # Save recent summary
            summary_file = self.metrics_dir / "speaker_metrics_summary.json"
            with open(summary_file, 'w') as f:
                json.dump(self.get_summary(), f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to persist metrics: {e}")
    
    def _load_metrics(self) -> None:
        """Load metrics from disk."""
        if not self.metrics_dir:
            return
            
        metrics_file = self.metrics_dir / "speaker_metrics.json"
        if metrics_file.exists():
            try:
                with open(metrics_file, 'r') as f:
                    data = json.load(f)
                    
                self.metrics.update(data.get('metrics', {}))
                
                # Restore podcast stats
                for name, stats in data.get('podcast_stats', {}).items():
                    self.podcast_stats[name].update(stats)
                    
                # Restore error types
                for error_type, count in data.get('error_types', {}).items():
                    self.error_types[error_type] = count
                    
                logger.info("Loaded existing metrics from disk")
                
            except Exception as e:
                logger.warning(f"Failed to load metrics: {e}")