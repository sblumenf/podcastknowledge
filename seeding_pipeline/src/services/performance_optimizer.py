"""
Performance optimization utilities for semantic processing.

This module provides optimization strategies for the semantic pipeline including:
- Batch processing for LLM calls
- Caching for conversation structure analysis
- Memory optimization for large transcripts
- Performance monitoring and benchmarking
"""

import time
import hashlib
import json
from typing import Dict, Any, List, Optional, Callable, Tuple
from functools import lru_cache, wraps
from datetime import datetime, timedelta
import logging
import gc
import os

from src.utils.logging import get_logger
from src.core.dependencies import get_psutil, get_memory_info

logger = get_logger(__name__)


class PerformanceOptimizer:
    """
    Performance optimizer for semantic pipeline processing.
    
    Provides various optimization strategies to improve processing speed
    and reduce resource usage.
    """
    
    def __init__(self, cache_ttl_minutes: int = 60):
        """
        Initialize performance optimizer.
        
        Args:
            cache_ttl_minutes: Cache time-to-live in minutes
        """
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._structure_cache: Dict[str, Tuple[Any, datetime]] = {}
        self._performance_metrics: Dict[str, List[float]] = {}
        
        # Memory thresholds
        self.memory_warning_threshold = 80  # Percentage
        self.memory_critical_threshold = 90  # Percentage
        
        logger.info(f"Initialized PerformanceOptimizer with {cache_ttl_minutes}min cache TTL")
    
    def batch_llm_calls(
        self,
        items: List[Any],
        process_func: Callable,
        batch_size: int = 3,
        llm_service: Any = None
    ) -> List[Any]:
        """
        Process items in batches for LLM calls to optimize throughput.
        
        Args:
            items: Items to process
            process_func: Function to process each item
            batch_size: Number of items per batch
            llm_service: LLM service instance
            
        Returns:
            List of processed results
        """
        results = []
        total_items = len(items)
        
        logger.info(f"Batch processing {total_items} items in batches of {batch_size}")
        
        for i in range(0, total_items, batch_size):
            batch = items[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_items + batch_size - 1) // batch_size
            
            logger.debug(f"Processing batch {batch_num}/{total_batches}")
            
            # Process batch items
            batch_results = []
            for item in batch:
                try:
                    result = process_func(item)
                    batch_results.append(result)
                except Exception as e:
                    logger.error(f"Error processing item in batch: {e}")
                    batch_results.append(None)
            
            results.extend(batch_results)
            
            # Add delay between batches to avoid rate limiting
            if i + batch_size < total_items:
                time.sleep(0.5)  # 500ms delay between batches
        
        return results
    
    def cache_conversation_structure(
        self,
        transcript_hash: str,
        structure: Any
    ) -> None:
        """
        Cache conversation structure analysis results.
        
        Args:
            transcript_hash: Hash of the transcript
            structure: Conversation structure to cache
        """
        self._structure_cache[transcript_hash] = (structure, datetime.now())
        logger.debug(f"Cached conversation structure for hash {transcript_hash}")
        
        # Clean up old cache entries
        self._cleanup_cache()
    
    def get_cached_structure(self, transcript_hash: str) -> Optional[Any]:
        """
        Retrieve cached conversation structure if available and not expired.
        
        Args:
            transcript_hash: Hash of the transcript
            
        Returns:
            Cached structure or None if not found/expired
        """
        if transcript_hash in self._structure_cache:
            structure, cached_time = self._structure_cache[transcript_hash]
            
            if datetime.now() - cached_time < self.cache_ttl:
                logger.debug(f"Cache hit for conversation structure hash {transcript_hash}")
                return structure
            else:
                # Remove expired entry
                del self._structure_cache[transcript_hash]
                logger.debug(f"Cache expired for hash {transcript_hash}")
        
        return None
    
    def compute_transcript_hash(self, segments: List[Any]) -> str:
        """
        Compute a hash for transcript segments to use as cache key.
        
        Args:
            segments: List of transcript segments
            
        Returns:
            Hash string
        """
        # Create a string representation of segments
        segment_data = []
        for seg in segments:
            segment_data.append({
                'text': seg.text,
                'start': seg.start_time,
                'end': seg.end_time,
                'speaker': seg.speaker
            })
        
        # Compute hash
        content = json.dumps(segment_data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def optimize_memory_usage(self) -> Dict[str, Any]:
        """
        Optimize memory usage by running garbage collection and monitoring.
        
        Returns:
            Memory usage statistics
        """
        # Get initial memory info
        initial_info = get_memory_info()
        initial_memory = initial_info['process_memory_mb']
        
        # Force garbage collection
        gc.collect()
        
        # Get final memory info
        final_info = get_memory_info()
        final_memory = final_info['process_memory_mb']
        memory_freed = initial_memory - final_memory
        memory_percent = final_info['process_memory_percent']
        
        stats = {
            'initial_memory_mb': initial_memory,
            'final_memory_mb': final_memory,
            'memory_freed_mb': memory_freed,
            'memory_percent': memory_percent,
            'warning': memory_percent > self.memory_warning_threshold,
            'critical': memory_percent > self.memory_critical_threshold,
            'psutil_available': final_info.get('available', False)
        }
        
        if stats['warning'] and stats['psutil_available']:
            logger.warning(f"High memory usage: {memory_percent:.1f}%")
        
        if stats['critical'] and stats['psutil_available']:
            logger.error(f"Critical memory usage: {memory_percent:.1f}%")
        
        return stats
    
    def measure_performance(self, operation_name: str):
        """
        Decorator to measure performance of operations.
        
        Args:
            operation_name: Name of the operation being measured
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    elapsed_time = time.time() - start_time
                    
                    # Record metric
                    if operation_name not in self._performance_metrics:
                        self._performance_metrics[operation_name] = []
                    
                    self._performance_metrics[operation_name].append(elapsed_time)
                    
                    logger.debug(f"{operation_name} completed in {elapsed_time:.2f}s")
                    
                    return result
                    
                except Exception as e:
                    elapsed_time = time.time() - start_time
                    logger.error(f"{operation_name} failed after {elapsed_time:.2f}s: {e}")
                    raise
            
            return wrapper
        return decorator
    
    def get_performance_summary(self) -> Dict[str, Dict[str, float]]:
        """
        Get summary of performance metrics.
        
        Returns:
            Dictionary with performance statistics per operation
        """
        summary = {}
        
        for operation, times in self._performance_metrics.items():
            if times:
                summary[operation] = {
                    'count': len(times),
                    'total_time': sum(times),
                    'average_time': sum(times) / len(times),
                    'min_time': min(times),
                    'max_time': max(times)
                }
        
        return summary
    
    def optimize_unit_processing(
        self,
        units: List[Any],
        max_parallel_units: int = 3
    ) -> List[List[Any]]:
        """
        Optimize unit processing by grouping units for parallel extraction.
        
        Args:
            units: List of meaningful units
            max_parallel_units: Maximum units to process in parallel
            
        Returns:
            List of unit groups for parallel processing
        """
        # Group units by estimated processing time
        unit_groups = []
        current_group = []
        current_duration = 0.0
        max_duration_per_group = 300.0  # 5 minutes worth of content
        
        for unit in units:
            unit_duration = unit.duration if hasattr(unit, 'duration') else 60.0
            
            if current_duration + unit_duration > max_duration_per_group or len(current_group) >= max_parallel_units:
                if current_group:
                    unit_groups.append(current_group)
                current_group = [unit]
                current_duration = unit_duration
            else:
                current_group.append(unit)
                current_duration += unit_duration
        
        if current_group:
            unit_groups.append(current_group)
        
        logger.info(f"Optimized {len(units)} units into {len(unit_groups)} processing groups")
        
        return unit_groups
    
    def _cleanup_cache(self) -> None:
        """Clean up expired cache entries."""
        current_time = datetime.now()
        expired_keys = []
        
        for key, (_, cached_time) in self._structure_cache.items():
            if current_time - cached_time > self.cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._structure_cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def create_processing_benchmark(self) -> 'ProcessingBenchmark':
        """
        Create a processing benchmark context manager.
        
        Returns:
            ProcessingBenchmark instance
        """
        return ProcessingBenchmark(self)


class ProcessingBenchmark:
    """Context manager for benchmarking processing operations."""
    
    def __init__(self, optimizer: PerformanceOptimizer):
        """
        Initialize benchmark.
        
        Args:
            optimizer: PerformanceOptimizer instance
        """
        self.optimizer = optimizer
        self.start_time = None
        self.checkpoints = []
        self.operation_name = "benchmark"
    
    def __enter__(self):
        """Start benchmark."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End benchmark and record results."""
        if self.start_time:
            total_time = time.time() - self.start_time
            
            logger.info(f"Benchmark '{self.operation_name}' completed in {total_time:.2f}s")
            
            if self.checkpoints:
                logger.info("Checkpoint times:")
                for checkpoint, checkpoint_time in self.checkpoints:
                    logger.info(f"  - {checkpoint}: {checkpoint_time:.2f}s")
    
    def checkpoint(self, name: str) -> None:
        """
        Record a checkpoint time.
        
        Args:
            name: Name of the checkpoint
        """
        if self.start_time:
            elapsed = time.time() - self.start_time
            self.checkpoints.append((name, elapsed))
            logger.debug(f"Checkpoint '{name}' at {elapsed:.2f}s")
    
    def set_operation_name(self, name: str) -> None:
        """
        Set the operation name for this benchmark.
        
        Args:
            name: Operation name
        """
        self.operation_name = name