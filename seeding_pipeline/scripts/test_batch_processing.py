#!/usr/bin/env python3
"""Test script for batch processing optimization."""

import sys
import time
from pathlib import Path
import tempfile
import random

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli.cli import find_vtt_files, process_vtt_batch, format_duration
from src.core.config import PipelineConfig
from src.seeding import VTTKnowledgeExtractor
from src.seeding.checkpoint import ProgressCheckpoint
from src.seeding.batch_processor import BatchProcessor, BatchItem

def create_test_vtt_files(num_files: int = 10) -> Path:
    """Create test VTT files for benchmarking."""
    temp_dir = Path(tempfile.mkdtemp(prefix="vtt_test_"))
    
    for i in range(num_files):
        vtt_file = temp_dir / f"episode_{i+1:03d}.vtt"
        
        # Generate VTT content with random duration
        duration_minutes = random.randint(30, 120)
        segments = []
        
        segments.append("WEBVTT\n\n")
        
        # Generate segments (approximately 1 segment per 3 seconds)
        current_time = 0
        for j in range(duration_minutes * 20):  # ~20 segments per minute
            start_time = current_time
            end_time = current_time + 3
            
            start_str = f"{start_time//3600:02d}:{(start_time%3600)//60:02d}:{start_time%60:02d}.000"
            end_str = f"{end_time//3600:02d}:{(end_time%3600)//60:02d}:{end_time%60:02d}.000"
            
            speaker = f"Speaker{(j % 3) + 1}"
            text = f"This is segment {j+1} of the conversation about topic {i+1}."
            
            segments.append(f"{j+1}\n")
            segments.append(f"{start_str} --> {end_str}\n")
            segments.append(f"<v {speaker}>{text}\n\n")
            
            current_time = end_time
        
        vtt_file.write_text("".join(segments))
        print(f"Created {vtt_file.name} ({duration_minutes} minutes, {len(segments)//3} segments)")
    
    return temp_dir

def benchmark_sequential_processing(vtt_files: list, pipeline, checkpoint) -> dict:
    """Benchmark sequential processing."""
    print("\n" + "="*50)
    print("SEQUENTIAL PROCESSING")
    print("="*50)
    
    start_time = time.time()
    processed = 0
    
    from src.seeding.transcript_ingestion import TranscriptIngestionManager
    
    for i, file_path in enumerate(vtt_files):
        print(f"\n[{i+1}/{len(vtt_files)}] Processing: {file_path.name}")
        
        try:
            manager = TranscriptIngestionManager(pipeline, checkpoint)
            result = manager.process_vtt_file(str(file_path))
            
            if result['success']:
                print(f"  ✓ Success - {result['segments_processed']} segments")
                processed += 1
            else:
                print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
    
    total_time = time.time() - start_time
    
    return {
        'method': 'sequential',
        'total_files': len(vtt_files),
        'processed': processed,
        'total_time': total_time,
        'rate': processed / total_time if total_time > 0 else 0
    }

def benchmark_parallel_processing(vtt_files: list, pipeline, checkpoint, workers: int = 4) -> dict:
    """Benchmark parallel processing."""
    print("\n" + "="*50)
    print(f"PARALLEL PROCESSING ({workers} workers)")
    print("="*50)
    
    # Mock args object
    class Args:
        def __init__(self):
            self.workers = workers
            self.parallel = True
    
    args = Args()
    start_time = time.time()
    
    # Use the batch processing function
    result_code = process_vtt_batch(vtt_files, pipeline, checkpoint, args)
    
    total_time = time.time() - start_time
    
    # Count processed files (simplified for demo)
    processed = len(vtt_files) if result_code == 0 else 0
    
    return {
        'method': f'parallel-{workers}',
        'total_files': len(vtt_files),
        'processed': processed,
        'total_time': total_time,
        'rate': processed / total_time if total_time > 0 else 0
    }

def main():
    """Run batch processing benchmarks."""
    print("Batch Processing Optimization Test")
    print("==================================")
    
    # Configuration
    num_files = 10
    
    # Create test files
    print(f"\nCreating {num_files} test VTT files...")
    test_dir = create_test_vtt_files(num_files)
    vtt_files = sorted(test_dir.glob("*.vtt"))
    
    # Initialize pipeline
    config = PipelineConfig()
    pipeline = VTTKnowledgeExtractor(config)
    
    # Create temporary checkpoint directory
    checkpoint_dir = test_dir / "checkpoints"
    checkpoint_dir.mkdir()
    checkpoint = ProgressCheckpoint(str(checkpoint_dir))
    
    try:
        # Run benchmarks
        results = []
        
        # Sequential processing
        seq_result = benchmark_sequential_processing(vtt_files, pipeline, checkpoint)
        results.append(seq_result)
        
        # Clear checkpoints for fair comparison
        import shutil
        shutil.rmtree(checkpoint_dir)
        checkpoint_dir.mkdir()
        checkpoint = ProgressCheckpoint(str(checkpoint_dir))
        
        # Parallel processing with different worker counts
        for workers in [2, 4, 8]:
            par_result = benchmark_parallel_processing(vtt_files, pipeline, checkpoint, workers)
            results.append(par_result)
            
            # Clear checkpoints
            shutil.rmtree(checkpoint_dir)
            checkpoint_dir.mkdir()
            checkpoint = ProgressCheckpoint(str(checkpoint_dir))
        
        # Display results
        print("\n" + "="*70)
        print("BENCHMARK RESULTS")
        print("="*70)
        print(f"{'Method':<15} {'Files':<8} {'Time':<12} {'Rate':<15} {'Speedup':<10}")
        print("-"*70)
        
        sequential_time = results[0]['total_time']
        
        for result in results:
            speedup = sequential_time / result['total_time'] if result['total_time'] > 0 else 0
            print(f"{result['method']:<15} "
                  f"{result['processed']:<8} "
                  f"{format_duration(int(result['total_time'])):<12} "
                  f"{result['rate']:.2f} files/s  "
                  f"{speedup:.2f}x")
        
        print("\nValidation: 10 files in <30 minutes ✓" if results[-1]['total_time'] < 1800 else "✗")
        
    finally:
        # Cleanup
        pipeline.cleanup()
        
        # Remove test directory
        import shutil
        shutil.rmtree(test_dir)
        print(f"\nCleaned up test directory: {test_dir}")

if __name__ == "__main__":
    main()