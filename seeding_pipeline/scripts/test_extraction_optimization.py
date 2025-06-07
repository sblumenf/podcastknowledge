#!/usr/bin/env python3
"""Test script for extraction performance optimization."""

import sys
import time
import random
from pathlib import Path
from typing import List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig
from src.core.models import Segment
from src.services.llm import LLMService
from src.core.config import PipelineConfig

def generate_test_segments(num_segments: int = 100) -> List[Segment]:
    """Generate test segments for benchmarking."""
    segments = []
    
    # Topics for realistic content
    topics = [
        ("machine learning", "Dr. Sarah Johnson", [
            "Machine learning is revolutionizing healthcare diagnostics",
            "Neural networks can detect cancer in medical imaging with high accuracy",
            "We're seeing AI transform patient outcomes through early detection",
            "The key is training models on diverse datasets for better generalization"
        ]),
        ("artificial intelligence", "Prof. Mike Chen", [
            "Artificial intelligence is becoming more accessible to developers",
            "The democratization of AI tools is driving innovation",
            "Large language models are changing how we interact with technology",
            "Ethics in AI development is crucial for responsible deployment"
        ]),
        ("healthcare", "Dr. Emily Williams", [
            "Digital health solutions are improving patient engagement",
            "Telemedicine has expanded access to care in rural areas", 
            "Wearable devices provide continuous health monitoring",
            "Data privacy remains a key concern in healthcare tech"
        ])
    ]
    
    # Generate segments
    current_time = 0.0
    for i in range(num_segments):
        topic, speaker, sentences = random.choice(topics)
        
        # Mix informative and non-informative segments
        if i % 5 == 0:
            # Non-informative segment
            text = random.choice(["um, yeah", "uh huh", "[laughter]", "okay, so...", "you know"])
            duration = 1.0
        else:
            # Informative segment
            num_sentences = random.randint(1, 3)
            selected_sentences = random.sample(sentences, min(num_sentences, len(sentences)))
            text = f"{speaker}: {' '.join(selected_sentences)}"
            duration = len(text.split()) * 0.3  # ~0.3 seconds per word
        
        segment = Segment(
            id=f"seg_{i}",
            text=text,
            start_time=current_time,
            end_time=current_time + duration,
            speaker=speaker if i % 5 != 0 else None
        )
        segments.append(segment)
        current_time += duration
    
    return segments

def benchmark_sequential_extraction(extractor: KnowledgeExtractor, segments: List[Segment]) -> dict:
    """Benchmark sequential extraction."""
    print("\n" + "="*50)
    print("SEQUENTIAL EXTRACTION")
    print("="*50)
    
    start_time = time.time()
    results = []
    entities_found = 0
    quotes_found = 0
    skipped = 0
    
    for i, segment in enumerate(segments):
        if i % 20 == 0:
            print(f"Processing segment {i+1}/{len(segments)}...")
        
        result = extractor.extract_knowledge(segment)
        results.append(result)
        
        if result.metadata.get('skipped'):
            skipped += 1
        else:
            entities_found += len(result.entities)
            quotes_found += len(result.quotes)
    
    total_time = time.time() - start_time
    
    print(f"\nProcessed {len(segments)} segments in {total_time:.2f}s")
    print(f"  Entities found: {entities_found}")
    print(f"  Quotes found: {quotes_found}")
    print(f"  Segments skipped: {skipped}")
    print(f"  Rate: {len(segments)/total_time:.1f} segments/s")
    
    return {
        'method': 'sequential',
        'total_time': total_time,
        'segments': len(segments),
        'entities': entities_found,
        'quotes': quotes_found,
        'skipped': skipped,
        'rate': len(segments)/total_time
    }

def benchmark_batch_extraction(extractor: KnowledgeExtractor, segments: List[Segment]) -> dict:
    """Benchmark batch extraction."""
    print("\n" + "="*50)
    print("BATCH EXTRACTION (OPTIMIZED)")
    print("="*50)
    
    start_time = time.time()
    
    # Process in batches
    batch_size = 10
    all_results = []
    entities_found = 0
    quotes_found = 0
    skipped = 0
    
    for i in range(0, len(segments), batch_size):
        batch = segments[i:i+batch_size]
        if i % 50 == 0:
            print(f"Processing batch starting at segment {i+1}...")
        
        batch_results = extractor.extract_knowledge_batch(batch)
        all_results.extend(batch_results)
        
        for result in batch_results:
            if result.metadata.get('skipped'):
                skipped += 1
            else:
                entities_found += len(result.entities)
                quotes_found += len(result.quotes)
    
    total_time = time.time() - start_time
    
    print(f"\nProcessed {len(segments)} segments in {total_time:.2f}s")
    print(f"  Entities found: {entities_found}")
    print(f"  Quotes found: {quotes_found}")
    print(f"  Segments skipped: {skipped}")
    print(f"  Rate: {len(segments)/total_time:.1f} segments/s")
    
    # Check cache hits
    cache_hits = sum(1 for r in all_results if r.metadata.get('cached', False))
    print(f"  Cache hits: {cache_hits}")
    
    return {
        'method': 'batch',
        'total_time': total_time,
        'segments': len(segments),
        'entities': entities_found,
        'quotes': quotes_found,
        'skipped': skipped,
        'rate': len(segments)/total_time,
        'cache_hits': cache_hits
    }

def benchmark_pre_filtering(extractor: KnowledgeExtractor, segments: List[Segment]) -> dict:
    """Benchmark impact of pre-filtering."""
    print("\n" + "="*50)
    print("PRE-FILTERING ANALYSIS")
    print("="*50)
    
    start_time = time.time()
    
    # Count segments that would be skipped
    skipped_count = 0
    for segment in segments:
        if extractor.should_skip_segment(segment):
            skipped_count += 1
    
    filter_time = time.time() - start_time
    
    print(f"Pre-filtering analysis:")
    print(f"  Total segments: {len(segments)}")
    print(f"  Would skip: {skipped_count} ({skipped_count/len(segments)*100:.1f}%)")
    print(f"  Would process: {len(segments) - skipped_count}")
    print(f"  Filter time: {filter_time*1000:.1f}ms")
    print(f"  Time saved: ~{skipped_count * 0.1:.1f}s (assuming 100ms per segment)")
    
    return {
        'total_segments': len(segments),
        'skipped': skipped_count,
        'skip_rate': skipped_count/len(segments),
        'time_saved_estimate': skipped_count * 0.1
    }

def main():
    """Run extraction optimization benchmarks."""
    print("Knowledge Extraction Optimization Test")
    print("=====================================")
    
    # Initialize components
    config = PipelineConfig()
    llm_service = LLMService(
        api_key=config.gemini_api_key or "dummy-key",
        model_name='gemini-2.5-flash'
    )
    
    extraction_config = ExtractionConfig(
        min_quote_length=5,
        max_quote_length=50,
        extract_quotes=True
    )
    
    extractor = KnowledgeExtractor(
        llm_service=llm_service,
        config=extraction_config
    )
    
    # Generate test data
    print("\nGenerating test segments...")
    segments = generate_test_segments(100)
    print(f"Generated {len(segments)} segments")
    
    # Run benchmarks
    results = []
    
    # Pre-filtering analysis
    filter_stats = benchmark_pre_filtering(extractor, segments)
    
    # Sequential extraction
    seq_result = benchmark_sequential_extraction(extractor, segments)
    results.append(seq_result)
    
    # Clear cache for fair comparison
    extractor._entity_cache.clear()
    
    # Batch extraction
    batch_result = benchmark_batch_extraction(extractor, segments)
    results.append(batch_result)
    
    # Display summary
    print("\n" + "="*70)
    print("BENCHMARK SUMMARY")
    print("="*70)
    print(f"{'Method':<15} {'Time (s)':<10} {'Rate (seg/s)':<15} {'Speedup':<10}")
    print("-"*70)
    
    sequential_time = results[0]['total_time']
    for result in results:
        speedup = sequential_time / result['total_time'] if result['total_time'] > 0 else 0
        print(f"{result['method']:<15} {result['total_time']:<10.2f} "
              f"{result['rate']:<15.1f} {speedup:.2f}x")
    
    # Calculate API call reduction
    if 'cache_hits' in batch_result:
        api_reduction = batch_result['cache_hits'] / batch_result['segments'] * 100
        print(f"\nAPI call reduction: {api_reduction:.1f}% (from caching)")
    
    skip_reduction = filter_stats['skip_rate'] * 100
    print(f"Segment skip rate: {skip_reduction:.1f}% (from pre-filtering)")
    
    total_reduction = api_reduction + skip_reduction
    print(f"\nTotal processing reduction: {total_reduction:.1f}%")
    print(f"Validation: 50% reduction in API calls ", end="")
    print("✓" if total_reduction >= 50 else "✗")

if __name__ == "__main__":
    main()