#!/usr/bin/env python3
"""Test the VTT pipeline with enhanced logging enabled."""

import sys
import time
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli.cli import setup_logging_cli
from src.seeding import VTTKnowledgeExtractor
from src.core.config import PipelineConfig
from src.vtt import VTTParser
from src.utils.logging_enhanced import get_logger, get_metrics_collector
from src.utils.logging import set_correlation_id, generate_correlation_id


def create_test_vtt():
    """Create a test VTT file."""
    test_vtt = """WEBVTT

00:00:00.000 --> 00:00:05.000
Speaker 1: Welcome to our test podcast about technology and innovation.

00:00:05.000 --> 00:00:10.000
Speaker 2: Thanks for having me. I'm excited to discuss AI and machine learning.

00:00:10.000 --> 00:00:15.000
Speaker 1: Let's start with the basics. What is machine learning?

00:00:15.000 --> 00:00:25.000
Speaker 2: Machine learning is a type of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.

00:00:25.000 --> 00:00:30.000
Speaker 1: That's fascinating. Can you give us a real-world example?

00:00:30.000 --> 00:00:40.000
Speaker 2: Sure! Netflix uses machine learning to recommend shows based on your viewing history. The system learns your preferences over time.

00:00:40.000 --> 00:00:45.000
Speaker 1: How does this differ from traditional programming?

00:00:45.000 --> 00:00:55.000
Speaker 2: Traditional programming requires explicit rules for every scenario. Machine learning discovers patterns in data to make decisions.

00:00:55.000 --> 00:01:00.000
Speaker 1: What are the main challenges in implementing ML systems?

00:01:00.000 --> 00:01:10.000
Speaker 2: The biggest challenges are data quality, computational resources, and ensuring the models are interpretable and unbiased.
"""
    
    test_file = Path("test_vtt/enhanced_logging_test.vtt")
    test_file.parent.mkdir(exist_ok=True)
    test_file.write_text(test_vtt)
    return test_file


def main():
    """Main test function."""
    # Set up enhanced logging
    setup_logging_cli(verbose=True, log_file="logs/pipeline_enhanced_test.log")
    
    logger = get_logger(__name__)
    
    # Set correlation ID for this run
    correlation_id = generate_correlation_id()
    set_correlation_id(correlation_id)
    
    logger.info("Starting pipeline test with enhanced logging", extra={
        'test_type': 'enhanced_logging',
        'correlation_id': correlation_id
    })
    
    # Create test file
    test_file = create_test_vtt()
    logger.info(f"Created test VTT file: {test_file}")
    
    try:
        # Initialize pipeline components
        config = PipelineConfig()
        config.llm_provider = "mock"  # Use mock for testing
        config.neo4j_uri = "bolt://localhost:7687"
        
        # Create pipeline
        pipeline = VTTKnowledgeExtractor(config)
        
        # Process the test file
        logger.info("Processing VTT file")
        start_time = time.time()
        
        result = pipeline.process_vtt_file(str(test_file))
        
        processing_time = time.time() - start_time
        
        # Log results
        logger.info("Processing completed", extra={
            'processing_time': processing_time,
            'segments_processed': len(result.segments) if hasattr(result, 'segments') else 0,
            'success': True
        })
        
        # Display metrics
        print("\n=== Processing Metrics ===")
        collector = get_metrics_collector()
        metrics = collector.get_metrics()
        
        # Show specific metrics
        for metric_name in ['extraction.segment_time', 'neo4j.query.execution_time', 
                           'operation.extract_knowledge.duration']:
            summary = collector.get_summary(metric_name)
            if summary and summary.get('count', 0) > 0:
                print(f"\n{metric_name}:")
                print(f"  Count: {summary['count']}")
                print(f"  Average: {summary['avg']:.3f}s")
                print(f"  Total: {summary['sum']:.3f}s")
        
        # Check log file
        print("\n=== Enhanced Logging Features ===")
        log_file = Path("logs/pipeline_enhanced_test.log")
        
        if log_file.exists():
            print(f"Log file created: {log_file}")
            print(f"Log size: {log_file.stat().st_size:,} bytes")
            
            # Analyze log content
            trace_starts = 0
            trace_ends = 0
            metrics_logged = 0
            progress_logs = 0
            
            with open(log_file, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if 'TRACE_START' in entry.get('message', ''):
                            trace_starts += 1
                        elif 'TRACE_END' in entry.get('message', ''):
                            trace_ends += 1
                        elif 'METRIC:' in entry.get('message', ''):
                            metrics_logged += 1
                        elif 'PROGRESS:' in entry.get('message', ''):
                            progress_logs += 1
                    except:
                        pass
            
            print(f"\nLog Analysis:")
            print(f"  Trace operations started: {trace_starts}")
            print(f"  Trace operations completed: {trace_ends}")
            print(f"  Metrics logged: {metrics_logged}")
            print(f"  Progress updates: {progress_logs}")
            print(f"  Correlation ID: {correlation_id}")
        
        # Sample log entries
        print("\n=== Sample Log Entries ===")
        if log_file.exists():
            with open(log_file, 'r') as f:
                lines = f.readlines()
                
                # Find interesting entries
                for line in lines[-20:]:  # Last 20 lines
                    try:
                        entry = json.loads(line)
                        if any(key in line for key in ['TRACE_', 'METRIC:', 'duration']):
                            timestamp = entry.get('timestamp', 'N/A')
                            level = entry.get('level', 'INFO')
                            message = entry.get('message', '')
                            
                            print(f"[{timestamp}] [{level}] {message}")
                            
                            # Show relevant extra fields
                            if 'duration_seconds' in entry:
                                print(f"    Duration: {entry['duration_seconds']:.3f}s")
                            if 'operation' in entry:
                                print(f"    Operation: {entry['operation']}")
                    except:
                        pass
        
        print("\n✅ Enhanced logging test completed successfully!")
        print(f"Check the full log at: {log_file}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"\n❌ Test failed: {e}")
        raise
    
    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()
            logger.info("Cleaned up test file")


if __name__ == "__main__":
    main()