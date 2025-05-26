#!/usr/bin/env python3
"""Example demonstrating distributed tracing in the podcast knowledge pipeline."""

import os
import sys
import time
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.config import PipelineConfig
from src.seeding import PodcastKnowledgePipeline
from src.tracing import init_tracing, create_span, add_span_attributes
from src.tracing.config import TracingConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run example with distributed tracing."""
    # Initialize tracing
    logger.info("Initializing distributed tracing...")
    tracing_config = TracingConfig(
        service_name="podcast-kg-example",
        jaeger_host=os.getenv("JAEGER_HOST", "localhost"),
        jaeger_port=int(os.getenv("JAEGER_PORT", "6831")),
        console_export=True,  # Also print to console for demo
    )
    
    init_tracing(
        service_name=tracing_config.service_name,
        jaeger_host=tracing_config.jaeger_host,
        jaeger_port=tracing_config.jaeger_port,
        enable_console=tracing_config.console_export,
    )
    
    # Create a root span for the example
    with create_span("example.main", attributes={"example.type": "demo"}):
        logger.info("Starting podcast knowledge pipeline example...")
        
        # Initialize pipeline
        with create_span("example.pipeline_init"):
            config = PipelineConfig.from_env()
            pipeline = PodcastKnowledgePipeline(config)
            
            logger.info("Initializing pipeline components...")
            if not pipeline.initialize_components():
                logger.error("Failed to initialize pipeline")
                return
        
        # Example podcast configuration
        podcast_config = {
            "id": "example_podcast",
            "name": "Example Podcast",
            "rss_url": "https://example.com/podcast.rss",
            "description": "An example podcast for demonstrating tracing"
        }
        
        # Simulate processing with custom spans
        with create_span("example.simulate_processing"):
            logger.info("Simulating podcast processing...")
            
            # Simulate episode download
            with create_span("example.download_episode") as span:
                logger.info("Downloading episode...")
                time.sleep(1)  # Simulate download time
                span.set_attribute("episode.size_mb", 50)
                span.set_attribute("episode.download_time_ms", 1000)
            
            # Simulate transcription
            with create_span("example.transcribe") as span:
                logger.info("Transcribing audio...")
                time.sleep(2)  # Simulate transcription time
                span.set_attribute("transcription.segments", 150)
                span.set_attribute("transcription.duration_seconds", 3600)
            
            # Simulate knowledge extraction
            with create_span("example.extract_knowledge") as span:
                logger.info("Extracting knowledge...")
                time.sleep(1.5)  # Simulate extraction time
                span.set_attribute("extraction.entities", 25)
                span.set_attribute("extraction.insights", 10)
                span.set_attribute("extraction.topics", 5)
            
            # Simulate graph storage
            with create_span("example.store_graph") as span:
                logger.info("Storing in knowledge graph...")
                time.sleep(0.5)  # Simulate storage time
                span.set_attribute("graph.nodes_created", 40)
                span.set_attribute("graph.relationships_created", 75)
        
        # Add final metrics to root span
        add_span_attributes({
            "example.total_time_seconds": 5,
            "example.status": "success"
        })
        
        logger.info("Example completed successfully!")
        
        # Cleanup
        pipeline.cleanup()
    
    # Give time for spans to be exported
    logger.info("Waiting for spans to be exported to Jaeger...")
    time.sleep(2)
    
    logger.info(f"""
Tracing Example Complete!

To view the traces:
1. Open Jaeger UI at http://localhost:16686
2. Select service: 'podcast-kg-example'
3. Click 'Find Traces'
4. Click on the trace to see the detailed span breakdown

The trace shows:
- Overall execution time
- Time spent in each processing phase
- Custom attributes for each operation
- Nested span relationships
""")


if __name__ == "__main__":
    main()