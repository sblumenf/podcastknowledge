#!/usr/bin/env python3
"""Benchmark script comparing old vs new Gemini implementations."""

import os
import sys
import time
import json
import statistics
from pathlib import Path
from typing import Dict, Any, List, Tuple
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services import LLMServiceFactory, LLMServiceType, CacheManager
from src.utils.key_rotation_manager import create_key_rotation_manager
from src.extraction.cached_extraction import CachedExtractionService, CachedExtractionConfig
from src.core.interfaces import TranscriptSegment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CachingBenchmark:
    """Benchmark harness for comparing caching implementations."""
    
    def __init__(self):
        """Initialize benchmark with test data."""
        self.key_manager = create_key_rotation_manager()
        self.test_episodes = self._load_test_episodes()
        self.results = {
                'gemini_direct': {'times': [], 'costs': [], 'errors': 0},
            'gemini_cached': {'times': [], 'costs': [], 'errors': 0}
        }
        
    def _load_test_episodes(self) -> List[Dict[str, Any]]:
        """Load or generate test episode data."""
        # Generate synthetic test data
        episodes = []
        
        # Small episode (below caching threshold)
        small_transcript = "This is a test transcript. " * 200  # ~1000 chars
        episodes.append({
            'id': 'test_small_001',
            'transcript': small_transcript,
            'segments': self._create_segments(small_transcript, 5)
        })
        
        # Medium episode
        medium_transcript = "This is a longer podcast transcript with more content. " * 500  # ~10K chars
        episodes.append({
            'id': 'test_medium_001',
            'transcript': medium_transcript,
            'segments': self._create_segments(medium_transcript, 20)
        })
        
        # Large episode (ideal for caching)
        large_transcript = "This is a very detailed podcast with extensive discussions. " * 2000  # ~50K chars
        episodes.append({
            'id': 'test_large_001',
            'transcript': large_transcript,
            'segments': self._create_segments(large_transcript, 100)
        })
        
        return episodes
        
    def _create_segments(self, transcript: str, num_segments: int) -> List[TranscriptSegment]:
        """Create synthetic transcript segments."""
        segments = []
        words = transcript.split()
        words_per_segment = len(words) // num_segments
        
        for i in range(num_segments):
            start_idx = i * words_per_segment
            end_idx = start_idx + words_per_segment
            segment_text = ' '.join(words[start_idx:end_idx])
            
            segments.append(TranscriptSegment(
                text=segment_text,
                start_time=i * 30.0,  # 30 seconds per segment
                end_time=(i + 1) * 30.0,
                speaker='Speaker',
                word_count=len(segment_text.split())
            ))
            
        return segments
        
    def benchmark_service(self, 
                         service_type: LLMServiceType,
                         episode: Dict[str, Any]) -> Tuple[float, float, bool]:
        """Benchmark a single service with an episode.
        
        Returns:
            Tuple of (time_taken, estimated_cost, success)
        """
        start_time = time.time()
        success = True
        estimated_cost = 0.0
        
        try:
            # Create service
            service = LLMServiceFactory.create_service(
                key_rotation_manager=self.key_manager,
                service_type=service_type,
                model_name='gemini-2.5-flash',
                temperature=0.7,
                max_tokens=2048
            )
            
            if service_type == LLMServiceType.GEMINI_CACHED:
                # Use cached extraction service
                cache_manager = service._cache_manager
                extraction_service = CachedExtractionService(
                    llm_service=service,
                    cache_manager=cache_manager,
                    config=CachedExtractionConfig()
                )
                
                # Extract with caching
                results = extraction_service.extract_from_episode(
                    episode_id=episode['id'],
                    transcript=episode['transcript'],
                    segments=episode['segments'][:10]  # Limit for benchmarking
                )
                
                # Get cost estimate
                cost_savings = cache_manager.estimate_cost_savings()
                estimated_cost = self._estimate_cost(episode, service_type, cost_savings)
                
            else:
                # Simple extraction simulation
                prompt = f"Extract entities from: {episode['transcript'][:1000]}"
                response = service.complete(prompt)
                
                # Estimate cost
                estimated_cost = self._estimate_cost(episode, service_type)
                
        except Exception as e:
            logger.error(f"Error benchmarking {service_type}: {e}")
            success = False
            
        time_taken = time.time() - start_time
        return time_taken, estimated_cost, success
        
    def _estimate_cost(self, 
                      episode: Dict[str, Any], 
                      service_type: LLMServiceType,
                      cost_savings: Optional[Dict[str, Any]] = None) -> float:
        """Estimate cost for processing episode."""
        # Base cost calculation
        tokens = len(episode['transcript']) // 4  # Rough token estimate
        segments = len(episode['segments'])
        
        # Assume 2 LLM calls per segment (entity + insight extraction)
        total_tokens = tokens + (segments * 1000)  # Add prompt tokens
        
        # Gemini 2.5 Flash pricing: $0.10 per 1M input tokens
        base_cost = (total_tokens / 1_000_000) * 0.10
        
        if service_type == LLMServiceType.GEMINI_CACHED and cost_savings:
            # Apply savings from caching
            savings_pct = cost_savings.get('savings_percentage', 0)
            return base_cost * (1 - savings_pct)
            
        return base_cost
        
    def run_benchmarks(self, iterations: int = 3) -> Dict[str, Any]:
        """Run full benchmark suite."""
        logger.info(f"Running benchmarks with {iterations} iterations per service")
        
        for service_type in [LLMServiceType.GEMINI_DIRECT,
                           LLMServiceType.GEMINI_CACHED]:
            
            logger.info(f"\nBenchmarking {service_type}...")
            
            for episode in self.test_episodes:
                logger.info(f"  Processing {episode['id']} ({len(episode['transcript'])} chars)")
                
                for i in range(iterations):
                    time_taken, cost, success = self.benchmark_service(service_type, episode)
                    
                    if success:
                        self.results[service_type]['times'].append(time_taken)
                        self.results[service_type]['costs'].append(cost)
                        logger.info(f"    Iteration {i+1}: {time_taken:.2f}s, ${cost:.4f}")
                    else:
                        self.results[service_type]['errors'] += 1
                        
        return self._analyze_results()
        
    def _analyze_results(self) -> Dict[str, Any]:
        """Analyze benchmark results."""
        analysis = {}
        
        for service_type, data in self.results.items():
            if data['times']:
                analysis[service_type] = {
                    'avg_time': statistics.mean(data['times']),
                    'min_time': min(data['times']),
                    'max_time': max(data['times']),
                    'avg_cost': statistics.mean(data['costs']),
                    'total_cost': sum(data['costs']),
                    'errors': data['errors'],
                    'runs': len(data['times'])
                }
            else:
                analysis[service_type] = {'error': 'No successful runs'}
                
        # Calculate improvements
        if 'gemini_direct' in analysis and 'gemini_cached' in analysis:
            base_cost = analysis['gemini_direct']['avg_cost']
            cached_cost = analysis['gemini_cached']['avg_cost']
            
            analysis['improvements'] = {
                'cost_reduction_pct': ((base_cost - cached_cost) / base_cost) * 100,
                'cost_reduction_abs': base_cost - cached_cost,
                'speed_improvement': analysis['gemini_direct']['avg_time'] / analysis['gemini_cached']['avg_time']
            }
            
        return analysis


def main():
    """Run benchmarks and save results."""
    benchmark = CachingBenchmark()
    
    # Run benchmarks
    results = benchmark.run_benchmarks(iterations=2)
    
    # Save results
    output_file = Path(__file__).parent.parent / 'benchmarks' / f'caching_benchmark_{int(time.time())}.json'
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
        
    # Print summary
    print("\n=== Benchmark Results ===\n")
    
    for service_type, metrics in results.items():
        if service_type == 'improvements':
            continue
            
        print(f"{service_type}:")
        if 'error' in metrics:
            print(f"  Error: {metrics['error']}")
        else:
            print(f"  Average time: {metrics['avg_time']:.2f}s")
            print(f"  Average cost: ${metrics['avg_cost']:.4f}")
            print(f"  Total cost: ${metrics['total_cost']:.4f}")
            print(f"  Errors: {metrics['errors']}")
        print()
        
    if 'improvements' in results:
        print("Improvements (Cached vs Direct):")
        print(f"  Cost reduction: {results['improvements']['cost_reduction_pct']:.1f}%")
        print(f"  Cost savings: ${results['improvements']['cost_reduction_abs']:.4f} per episode")
        print(f"  Speed improvement: {results['improvements']['speed_improvement']:.1f}x")
        
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()