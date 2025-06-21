#!/usr/bin/env python3
"""
Test script to verify performance benchmarking functionality.
"""

import asyncio
import json
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.monitoring.pipeline_benchmarking import get_benchmark, UnitMetrics
from src.pipeline.unified_pipeline import UnifiedKnowledgePipeline
from src.storage.graph_storage import GraphStorageService
from src.services.llm import LLMService
from src.core.config import Config


async def test_benchmarking():
    """Test the benchmarking functionality."""
    print("Testing Pipeline Benchmarking...")
    
    # Initialize benchmark
    benchmark = get_benchmark()
    
    # Simulate episode processing
    episode_id = "test_episode_001"
    benchmark.start_episode(episode_id)
    
    # Simulate phase 1: VTT Parsing
    benchmark.start_phase("VTT_PARSING")
    await asyncio.sleep(0.5)  # Simulate work
    benchmark.end_phase("VTT_PARSING")
    
    # Simulate phase 2: Speaker Identification
    benchmark.start_phase("SPEAKER_IDENTIFICATION")
    await asyncio.sleep(0.3)  # Simulate work
    benchmark.end_phase("SPEAKER_IDENTIFICATION")
    
    # Simulate phase 3: Knowledge Extraction with multiple units
    benchmark.start_phase("knowledge_extraction")
    
    # Simulate processing 5 units in parallel
    for i in range(5):
        start_time = asyncio.get_event_loop().time()
        await asyncio.sleep(0.1)  # Simulate unit processing
        end_time = asyncio.get_event_loop().time()
        
        benchmark.track_unit_processing(
            unit_id=f"unit_{i}",
            start_time=start_time,
            end_time=end_time,
            success=True if i < 4 else False,  # Simulate 1 failure
            error="Simulated error" if i == 4 else None,
            extraction_type="combined" if i < 3 else "separate"
        )
    
    benchmark.end_phase("knowledge_extraction")
    
    # End episode and generate summary
    benchmark.end_episode()
    
    # Get and display summary
    summary = benchmark.generate_summary()
    print("\nPerformance Summary:")
    print(json.dumps(summary, indent=2))
    
    # Verify key metrics
    assert summary['episode_id'] == episode_id
    assert len(summary['phases']) == 3
    assert summary['phases']['knowledge_extraction']['unit_stats']['total_units'] == 5
    assert summary['phases']['knowledge_extraction']['unit_stats']['successful_units'] == 4
    assert summary['performance_indicators']['combined_extraction_usage'] == 60.0
    
    print("\n✅ All benchmarking tests passed!")


async def test_real_pipeline():
    """Test benchmarking with a real pipeline run (if test data available)."""
    test_vtt = Path("test_data/sample_episode.vtt")
    
    if not test_vtt.exists():
        print(f"\nSkipping real pipeline test - {test_vtt} not found")
        return
    
    print("\nTesting benchmarking with real pipeline...")
    
    # Initialize services (simplified for testing)
    config = Config()
    
    # This would require actual service initialization
    # For now, just demonstrate the structure
    print("Would run real pipeline with benchmarking enabled...")
    

if __name__ == "__main__":
    asyncio.run(test_benchmarking())
    asyncio.run(test_real_pipeline())