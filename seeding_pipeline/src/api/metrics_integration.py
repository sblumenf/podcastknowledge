"""
Integration examples for metrics collection in the pipeline.

This module shows how to integrate metrics collection into various
components of the podcast knowledge graph pipeline.
"""

from typing import Dict, Any

from ..monitoring import get_metrics_collector, track_duration, track_api_call
# Example: Orchestrator integration
def process_episode_with_metrics(episode_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example of processing an episode with full metrics tracking.
    
    In production, this would call the actual episode processing logic
    from the main pipeline (e.g., MultiPodcastVTTKnowledgeExtractor).
    """
    collector = get_metrics_collector()
    
    # Track queue wait time
    wait_time = episode_data.get("queue_wait_seconds", 0)
    collector.queue_wait_time.observe(wait_time)
    
    # Update queue size
    collector.queue_size.dec()
    
    try:
        # In production, replace this with actual processing:
        # from ..processing import process_episode
        # result = process_episode(episode_data)
        
        # For this example, we'll just show the structure
        result = episode_data  # This would be the actual processing result
        
        # Track success
        collector.episodes_processed.inc()
        
        # Track quality metrics
        quality_score = result.get("quality_score", 0.8)
        collector.extraction_quality.observe(quality_score)
        
        # Track entities
        entity_count = len(result.get("entities", []))
        collector.entities_per_episode.observe(entity_count)
        
        # Track graph updates
        for node_type, count in result.get("nodes_created", {}).items():
            collector.nodes_created.inc(count, labels={"node_type": node_type})
        
        for rel_type, count in result.get("relationships_created", {}).items():
            collector.relationships_created.inc(count, labels={"relationship_type": rel_type})
        
        return result
        
    except Exception as e:
        # Track failure
        collector.episodes_failed.inc()
        raise


@track_duration(metric_name="processing_duration", stage="transcription")
def transcribe_audio_with_metrics(audio_path: str) -> str:
    """Transcribe audio with duration tracking."""
    # Transcription logic here
    return "transcript"


@track_duration(metric_name="processing_duration", stage="extraction")
def extract_knowledge_with_metrics(transcript: str) -> Dict[str, Any]:
    """Extract knowledge with duration tracking."""
    # Extraction logic here
    return {"entities": [], "insights": []}


# Example: Provider integration
class MetricsAwareProvider:
    """Example of a provider with built-in metrics."""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.collector = get_metrics_collector()
    
    @track_api_call("example_provider", "generate")
    def generate(self, prompt: str) -> str:
        """Generate response with metrics tracking."""
        # Provider logic here
        return "response"
    
    def health_check(self) -> Dict[str, Any]:
        """Health check with metrics."""
        # You could track health check metrics here
        self.collector.provider_calls.inc(
            labels={"provider": self.provider_name, "method": "health_check"}
        )
        return {"status": "healthy"}


# Example: Batch processing with metrics
def process_batch_with_metrics(episodes: list) -> Dict[str, Any]:
    """Process a batch of episodes with comprehensive metrics."""
    collector = get_metrics_collector()
    
    # Update queue size
    collector.queue_size.set(len(episodes))
    
    results = {
        "successful": 0,
        "failed": 0,
        "total_duration": 0
    }
    
    for episode in episodes:
        try:
            with track_duration(metric_name="processing_duration", stage="full_episode"):
                result = process_episode_with_metrics(episode)
                results["successful"] += 1
        except Exception as e:
            results["failed"] += 1
            collector.provider_errors.inc(
                labels={"provider": "pipeline", "error_type": type(e).__name__}
            )
    
    # Calculate and log success rate
    success_rate = results["successful"] / len(episodes) if episodes else 0
    collector.extraction_quality.observe(success_rate)
    
    return results


# Example: Adding custom metrics
def add_custom_metric_example():
    """Example of adding a custom metric."""
    from .metrics import Counter, Histogram
    
    collector = get_metrics_collector()
    
    # Add a custom counter
    collector.custom_events = Counter(
        "podcast_kg_custom_events_total",
        "Total custom events",
        labels=["event_type"]
    )
    
    # Add a custom histogram
    collector.custom_latency = Histogram(
        "podcast_kg_custom_latency_seconds",
        "Custom operation latency",
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
    )
    
    # Use the custom metrics
    collector.custom_events.inc(labels={"event_type": "special_processing"})
    collector.custom_latency.observe(1.23)


# Example: Metrics middleware for web frameworks
def create_metrics_middleware(app):
    """Create middleware that tracks HTTP metrics."""
    try:
        from fastapi import FastAPI, Request
        import time
        
        if isinstance(app, FastAPI):
            @app.middleware("http")
            async def metrics_middleware(request: Request, call_next):
                start_time = time.time()
                
                response = await call_next(request)
                
                duration = time.time() - start_time
                
                # Track HTTP metrics
                collector = get_metrics_collector()
                if not hasattr(collector, "http_requests"):
                    from .metrics import Counter, Histogram
                    collector.http_requests = Counter(
                        "podcast_kg_http_requests_total",
                        "Total HTTP requests",
                        labels=["method", "endpoint", "status"]
                    )
                    collector.http_duration = Histogram(
                        "podcast_kg_http_duration_seconds",
                        "HTTP request duration",
                        labels=["method", "endpoint"]
                    )
                
                collector.http_requests.inc(
                    labels={
                        "method": request.method,
                        "endpoint": request.url.path,
                        "status": str(response.status_code)
                    }
                )
                collector.http_duration.observe(
                    duration,
                    labels={
                        "method": request.method,
                        "endpoint": request.url.path
                    }
                )
                
                return response
    except ImportError:
        pass


