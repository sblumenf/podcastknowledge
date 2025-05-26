"""
SLO Metrics Tracking Integration

Automatically tracks SLO-related metrics during pipeline processing.
"""

import time
from functools import wraps
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from ..api.metrics import get_metrics_collector
from ..core.error_budget import get_error_budget_tracker
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SLOTracker:
    """Tracks SLO-related metrics during processing."""
    
    def __init__(self):
        self.metrics = get_metrics_collector()
        self.error_budget_tracker = get_error_budget_tracker()
        
        # Initialize SLOs
        self._initialize_slos()
    
    def _initialize_slos(self):
        """Initialize default SLOs for tracking."""
        # Register core SLOs
        self.error_budget_tracker.register_slo(
            name="availability",
            description="Episode processing availability",
            target=99.5,
            measurement_window_days=30
        )
        
        self.error_budget_tracker.register_slo(
            name="latency",
            description="Episode processing latency",
            target=95.0,  # 95% within threshold
            measurement_window_days=30
        )
        
        self.error_budget_tracker.register_slo(
            name="quality",
            description="Extraction quality",
            target=90.0,
            measurement_window_days=30
        )
    
    def track_episode_processing(self, episode_id: str, podcast_id: str):
        """
        Track episode processing with SLO metrics.
        
        Returns a context manager for tracking processing duration and outcome.
        """
        class EpisodeTracker:
            def __init__(self, tracker: SLOTracker, episode_id: str, podcast_id: str):
                self.tracker = tracker
                self.episode_id = episode_id
                self.podcast_id = podcast_id
                self.start_time = None
                self.success = False
                
            def __enter__(self):
                self.start_time = time.time()
                return self
                
            def __exit__(self, exc_type, exc_val, exc_tb):
                duration = time.time() - self.start_time
                
                # Track processing duration
                self.tracker.metrics.processing_duration.observe(
                    duration,
                    labels={"stage": "full_episode"}
                )
                
                # Update last processed timestamp
                self.tracker.metrics.last_processed_timestamp.set(time.time())
                
                if exc_type is None:
                    # Success
                    self.tracker.metrics.episodes_processed.inc()
                    self.success = True
                    logger.info(f"Episode {self.episode_id} processed successfully in {duration:.2f}s")
                else:
                    # Failure
                    self.tracker.metrics.episodes_failed.inc()
                    logger.error(f"Episode {self.episode_id} failed after {duration:.2f}s: {exc_val}")
                
                # Track latency SLO (5 minute threshold)
                if duration <= 300:  # Within SLO
                    self.tracker.metrics.processing_duration.observe(
                        duration,
                        labels={"stage": "full_episode", "slo_met": "true"}
                    )
                
                # Suppress exception to continue tracking
                return False
            
            def set_quality_score(self, score: float):
                """Set quality score for this episode."""
                self.tracker.metrics.extraction_quality.observe(
                    score,
                    labels={"type": "overall"}
                )
        
        return EpisodeTracker(self, episode_id, podcast_id)
    
    def track_transcription_quality(self, episode_id: str, accuracy_score: float):
        """Track transcription quality metrics."""
        self.metrics.extraction_quality.observe(
            accuracy_score,
            labels={"type": "transcription"}
        )
        logger.debug(f"Transcription quality for {episode_id}: {accuracy_score:.2f}")
    
    def track_entity_extraction(self, episode_id: str, entity_count: int):
        """Track entity extraction metrics."""
        self.metrics.entities_per_episode.observe(entity_count)
        self.metrics.entities_extracted_total.inc(entity_count)
        
        # Track against SLO (minimum 5 entities)
        if entity_count >= 5:
            self.metrics.extraction_quality.observe(
                1.0,  # Met threshold
                labels={"type": "entity_extraction"}
            )
        else:
            self.metrics.extraction_quality.observe(
                entity_count / 5.0,  # Partial credit
                labels={"type": "entity_extraction"}
            )
    
    def track_provider_call(self, provider: str, method: str, success: bool, 
                          duration: float, error_type: Optional[str] = None):
        """Track provider call metrics."""
        self.metrics.provider_calls.inc(
            labels={"provider": provider, "method": method}
        )
        
        self.metrics.provider_latency.observe(
            duration,
            labels={"provider": provider, "method": method}
        )
        
        if not success:
            self.metrics.provider_errors.inc(
                labels={"provider": provider, "error_type": error_type or "unknown"}
            )
    
    def track_api_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Track API request metrics."""
        self.metrics.http_requests_total.inc(
            labels={
                "method": method,
                "endpoint": endpoint,
                "status": str(status_code)
            }
        )
        
        self.metrics.http_request_duration.observe(
            duration,
            labels={"method": method, "endpoint": endpoint}
        )
    
    def track_checkpoint_save(self):
        """Track checkpoint save timestamp."""
        self.metrics.last_checkpoint_timestamp.set(time.time())
        logger.debug("Checkpoint saved")
    
    def update_queue_metrics(self, queue_size: int):
        """Update queue size metrics."""
        self.metrics.queue_size.set(queue_size)
    
    def track_graph_updates(self, nodes_created: Dict[str, int], 
                           relationships_created: Dict[str, int]):
        """Track graph update metrics."""
        for node_type, count in nodes_created.items():
            self.metrics.nodes_created.inc(count, labels={"node_type": node_type})
        
        for rel_type, count in relationships_created.items():
            self.metrics.relationships_created.inc(
                count, 
                labels={"relationship_type": rel_type}
            )


# Global SLO tracker instance
_slo_tracker = None


def get_slo_tracker() -> SLOTracker:
    """Get or create the global SLO tracker."""
    global _slo_tracker
    if _slo_tracker is None:
        _slo_tracker = SLOTracker()
    return _slo_tracker


def track_slo_metrics(func: Callable) -> Callable:
    """
    Decorator to automatically track SLO metrics for a function.
    
    Usage:
        @track_slo_metrics
        def process_episode(episode_id: str):
            # Processing logic
            return result
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        tracker = get_slo_tracker()
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Track success
            logger.debug(f"{func.__name__} completed in {duration:.2f}s")
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            
            # Track failure
            logger.error(f"{func.__name__} failed after {duration:.2f}s: {e}")
            raise
    
    return wrapper


def track_api_endpoint(method: str, endpoint: str):
    """
    Decorator to track API endpoint metrics.
    
    Usage:
        @track_api_endpoint("GET", "/api/v1/health")
        async def health_check():
            return {"status": "ok"}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracker = get_slo_tracker()
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Assume 200 for success
                tracker.track_api_request(method, endpoint, 200, duration)
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                # Determine status code from exception
                status_code = getattr(e, "status_code", 500)
                tracker.track_api_request(method, endpoint, status_code, duration)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracker = get_slo_tracker()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                tracker.track_api_request(method, endpoint, 200, duration)
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                status_code = getattr(e, "status_code", 500)
                tracker.track_api_request(method, endpoint, status_code, duration)
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator