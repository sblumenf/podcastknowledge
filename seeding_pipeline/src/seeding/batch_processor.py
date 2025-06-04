"""Batch processing utilities for efficient parallel podcast processing."""

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from queue import Queue
from typing import List, Dict, Any, Callable, Optional, Union, Tuple
import logging
import multiprocessing as mp
import os
import threading
import time

from src.core.exceptions import BatchProcessingError
from src.utils.memory import cleanup_memory
logger = logging.getLogger(__name__)


@dataclass
class BatchItem:
    """Item to be processed in a batch."""
    id: str
    data: Any
    priority: int = 0
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class BatchResult:
    """Result from processing a batch item."""
    item_id: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    metadata: Optional[Dict[str, Any]] = None


class BatchProcessor:
    """Processor for handling batch operations with parallel execution."""
    
    def __init__(self,
                 max_workers: Optional[int] = None,
                 batch_size: int = 10,
                 use_processes: bool = False,
                 memory_limit_mb: Optional[int] = None,
                 progress_callback: Optional[Callable[[int, int], None]] = None,
                 config: Optional[Dict[str, Any]] = None,
                 is_schemaless: bool = False):
        """Initialize batch processor.
        
        Args:
            max_workers: Maximum parallel workers (None for CPU count)
            batch_size: Size of each batch
            use_processes: Use processes instead of threads
            memory_limit_mb: Memory limit in MB
            progress_callback: Callback for progress updates (current, total)
            config: Optional configuration dictionary
            is_schemaless: Enable schemaless mode for schema discovery
        """
        self.max_workers = max_workers or mp.cpu_count()
        self.batch_size = batch_size
        self.use_processes = use_processes
        self.memory_limit_mb = memory_limit_mb
        self.progress_callback = progress_callback
        self.config = config or {}
        
        # Batch size optimization
        self._optimal_batch_size = batch_size
        self._batch_performance_history: List[Tuple[int, float]] = []
        
        # Progress tracking
        self._items_processed = 0
        self._total_items = 0
        self._start_time = None
        self._success_count = 0
        self._failure_count = 0
        self._lock = threading.Lock()
        
        # Schema evolution tracking for schemaless mode
        self._discovered_types = set()
        self._type_frequencies = {}
        self._relationship_types = set()
        self.is_schemaless = is_schemaless or self.config.get('use_schemaless_extraction', False)
        
        mode = "SCHEMALESS" if self.is_schemaless else "FIXED SCHEMA"
        logger.info(f"Initialized BatchProcessor in {mode} mode with {self.max_workers} workers, "
                   f"batch_size={batch_size}, use_processes={use_processes}")
    
    def process_items(self,
                     items: List[BatchItem],
                     process_func: Callable[[BatchItem], Any],
                     batch_func: Optional[Callable[[List[BatchItem]], List[Any]]] = None) -> List[BatchResult]:
        """Process items in batches with parallel execution.
        
        Args:
            items: List of items to process
            process_func: Function to process individual items
            batch_func: Optional function to process entire batches
            
        Returns:
            List of processing results
        """
        if not items:
            return []
        
        self._start_time = time.time()
        self._items_processed = 0
        self._success_count = 0
        self._failure_count = 0
        self._total_items = len(items)
        
        # Sort by priority
        sorted_items = sorted(items, key=lambda x: x.priority, reverse=True)
        
        # Split into batches
        batches = self._create_batches(sorted_items)
        logger.info(f"Processing {len(items)} items in {len(batches)} batches")
        
        # Process batches
        if batch_func:
            results = self._process_with_batch_func(batches, batch_func)
        else:
            results = self._process_individual_items(sorted_items, process_func)
        
        # Log summary
        total_time = time.time() - self._start_time
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Processed {len(results)} items in {total_time:.2f}s "
                   f"({success_count} successful)")
        
        return results
    
    def _create_batches(self, items: List[BatchItem]) -> List[List[BatchItem]]:
        """Create optimized batches from items."""
        batches = []
        current_batch = []
        
        for item in items:
            current_batch.append(item)
            
            if len(current_batch) >= self._optimal_batch_size:
                batches.append(current_batch)
                current_batch = []
                
                # Check memory if limit set
                if self.memory_limit_mb and self._check_memory_usage():
                    logger.warning("Memory limit approaching, reducing batch size")
                    self._optimal_batch_size = max(1, self._optimal_batch_size // 2)
        
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _check_memory_usage(self) -> bool:
        """Check if memory usage is approaching limit."""
        if not self.memory_limit_mb:
            return False
        
        try:
            import psutil
            memory = psutil.virtual_memory()
            used_mb = memory.used / (1024 * 1024)
            return used_mb > self.memory_limit_mb * 0.9  # 90% threshold
        except ImportError:
            return False
    
    def _process_individual_items(self,
                                 items: List[BatchItem],
                                 process_func: Callable[[BatchItem], Any]) -> List[BatchResult]:
        """Process items individually with parallel execution."""
        results = []
        
        # Choose executor based on configuration
        executor_class = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor
        
        with executor_class(max_workers=self.max_workers) as executor:
            # Submit all items
            future_to_item = {
                executor.submit(self._process_single_item, item, process_func): item
                for item in items
            }
            
            # Process completed items
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to process item {item.id}: {e}")
                    results.append(BatchResult(
                        item_id=item.id,
                        success=False,
                        error=str(e)
                    ))
                
                # Update progress
                with self._lock:
                    self._items_processed += 1
                    if result.success:
                        self._success_count += 1
                    else:
                        self._failure_count += 1
                self._update_progress()
                
                # Track schema discovery for schemaless mode
                if self.is_schemaless:
                    self.track_schema_discovery(result)
        
        return results
    
    def _process_single_item(self,
                           item: BatchItem,
                           process_func: Callable[[BatchItem], Any]) -> BatchResult:
        """Process a single item and return result."""
        start_time = time.time()
        
        try:
            result = process_func(item)
            processing_time = time.time() - start_time
            
            return BatchResult(
                item_id=item.id,
                success=True,
                result=result,
                processing_time=processing_time,
                metadata=item.metadata
            )
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error processing item {item.id}: {e}")
            
            return BatchResult(
                item_id=item.id,
                success=False,
                error=str(e),
                processing_time=processing_time,
                metadata=item.metadata
            )
    
    def _process_with_batch_func(self,
                               batches: List[List[BatchItem]],
                               batch_func: Callable[[List[BatchItem]], List[Any]]) -> List[BatchResult]:
        """Process batches using batch function."""
        results = []
        
        for i, batch in enumerate(batches):
            logger.debug(f"Processing batch {i+1}/{len(batches)} with {len(batch)} items")
            start_time = time.time()
            
            try:
                batch_results = batch_func(batch)
                processing_time = time.time() - start_time
                
                # Convert to BatchResult objects
                for j, item in enumerate(batch):
                    if j < len(batch_results):
                        results.append(BatchResult(
                            item_id=item.id,
                            success=True,
                            result=batch_results[j],
                            processing_time=processing_time / len(batch),
                            metadata=item.metadata
                        ))
                    else:
                        results.append(BatchResult(
                            item_id=item.id,
                            success=False,
                            error="No result returned from batch function",
                            metadata=item.metadata
                        ))
                
                # Record batch performance
                self._record_batch_performance(len(batch), processing_time)
                
            except Exception as e:
                logger.error(f"Error processing batch {i+1}: {e}")
                
                # Mark all items in batch as failed
                for item in batch:
                    results.append(BatchResult(
                        item_id=item.id,
                        success=False,
                        error=str(e),
                        metadata=item.metadata
                    ))
            
            # Update progress
            with self._lock:
                self._items_processed += len(batch)
                success_in_batch = sum(1 for r in results[-(len(batch)):] if r.success)
                self._success_count += success_in_batch
                self._failure_count += len(batch) - success_in_batch
            self._update_progress()
            
            # Clean up memory after each batch
            cleanup_memory()
        
        return results
    
    def _update_progress(self):
        """Update progress and call callback if provided."""
        with self._lock:
            current = self._items_processed
            total = self._total_items
        
        if self.progress_callback:
            try:
                self.progress_callback(current, total)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
        
        # Log progress periodically
        if current % 10 == 0 or current == total:
            elapsed = time.time() - self._start_time
            rate = current / elapsed if elapsed > 0 else 0
            eta = (total - current) / rate if rate > 0 else 0
            
            progress_msg = f"Progress: {current}/{total} ({current/total*100:.1f}%) " \
                          f"Rate: {rate:.1f} items/s, ETA: {eta:.1f}s"
            
            # Add schema discovery info for schemaless mode
            if self.is_schemaless and self._discovered_types:
                progress_msg += f" | Discovered {len(self._discovered_types)} entity types"
            
            logger.info(progress_msg)
    
    def _record_batch_performance(self, batch_size: int, processing_time: float):
        """Record batch performance for optimization."""
        items_per_second = batch_size / processing_time if processing_time > 0 else 0
        self._batch_performance_history.append((batch_size, items_per_second))
        
        # Keep only recent history
        if len(self._batch_performance_history) > 100:
            self._batch_performance_history.pop(0)
        
        # Optimize batch size based on performance
        if len(self._batch_performance_history) >= 10:
            self._optimize_batch_size()
    
    def _optimize_batch_size(self):
        """Optimize batch size based on performance history."""
        # Group by batch size and calculate average performance
        size_performance = {}
        for size, perf in self._batch_performance_history:
            if size not in size_performance:
                size_performance[size] = []
            size_performance[size].append(perf)
        
        # Find best performing batch size
        best_size = self.batch_size
        best_perf = 0
        
        for size, perfs in size_performance.items():
            avg_perf = sum(perfs) / len(perfs)
            if avg_perf > best_perf:
                best_perf = avg_perf
                best_size = size
        
        # Adjust batch size gradually
        if best_size > self._optimal_batch_size:
            self._optimal_batch_size = min(
                best_size,
                self._optimal_batch_size + 5
            )
        elif best_size < self._optimal_batch_size:
            self._optimal_batch_size = max(
                1,
                self._optimal_batch_size - 5
            )
        
        logger.debug(f"Optimized batch size to {self._optimal_batch_size}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        if not self._start_time:
            return {}
        
        elapsed = time.time() - self._start_time
        
        stats = {
            'items_processed': self._items_processed,
            'total_processed': self._items_processed,  # Alias for compatibility
            'total_items': self._total_items,
            'elapsed_time': elapsed,
            'average_rate': self._items_processed / elapsed if elapsed > 0 else 0,
            'optimal_batch_size': self._optimal_batch_size,
            'worker_count': self.max_workers,
            'success_count': self._success_count,
            'failure_count': self._failure_count,
            'average_processing_time': elapsed / self._items_processed if self._items_processed > 0 else 0,
            'performance_metrics': {}  # TODO: Add actual metrics
        }
        
        # Add schemaless-specific statistics
        if self.is_schemaless:
            stats['schema_discovery'] = {
                'discovered_types': sorted(list(self._discovered_types)),
                'type_count': len(self._discovered_types),
                'relationship_types': sorted(list(self._relationship_types)),
                'relationship_type_count': len(self._relationship_types),
                'type_frequencies': dict(sorted(self._type_frequencies.items(), 
                                              key=lambda x: x[1], reverse=True)[:10])  # Top 10
            }
        
        return stats
    
    def track_schema_discovery(self, result: BatchResult):
        """Track discovered schema from schemaless extraction results.
        
        Args:
            result: Processing result containing extraction data
        """
        if not self.is_schemaless or not result.success:
            return
        
        # Extract schema information from result metadata
        if result.metadata:
            # Track entity types
            if 'discovered_types' in result.metadata:
                for entity_type in result.metadata['discovered_types']:
                    self._discovered_types.add(entity_type)
                    self._type_frequencies[entity_type] = \
                        self._type_frequencies.get(entity_type, 0) + 1
            
            # Track relationship types
            if 'relationship_types' in result.metadata:
                self._relationship_types.update(result.metadata['relationship_types'])
    
    def get_schema_evolution_report(self) -> Dict[str, Any]:
        """Generate a report on schema evolution during processing.
        
        Returns:
            Schema evolution statistics and patterns
        """
        if not self.is_schemaless:
            return {'message': 'Schema evolution tracking only available in schemaless mode'}
        
        return {
            'total_types_discovered': len(self._discovered_types),
            'entity_types': sorted(list(self._discovered_types)),
            'relationship_types': sorted(list(self._relationship_types)),
            'most_common_types': dict(sorted(self._type_frequencies.items(), 
                                            key=lambda x: x[1], reverse=True)[:20]),
            'type_distribution': self._calculate_type_distribution(),
            'items_processed': self._items_processed
        }
    
    def _calculate_type_distribution(self) -> Dict[str, float]:
        """Calculate percentage distribution of entity types."""
        total = sum(self._type_frequencies.values())
        if total == 0:
            return {}
        
        return {
            entity_type: (count / total) * 100
            for entity_type, count in sorted(self._type_frequencies.items(), 
                                           key=lambda x: x[1], reverse=True)[:10]
        }


class PriorityBatchProcessor(BatchProcessor):
    """Batch processor with priority queue support."""
    
    def __init__(self, **kwargs):
        """Initialize priority batch processor."""
        super().__init__(**kwargs)
        self._priority_queue = Queue()
        self._processing = False
        self._worker_thread = None
    
    def start(self):
        """Start the priority processor."""
        if self._processing:
            return
        
        self._processing = True
        self._worker_thread = threading.Thread(target=self._process_queue)
        self._worker_thread.start()
        logger.info("Started priority batch processor")
    
    def stop(self):
        """Stop the priority processor."""
        self._processing = False
        if self._worker_thread:
            self._worker_thread.join()
        logger.info("Stopped priority batch processor")
    
    def add_item(self, item: BatchItem):
        """Add item to priority queue."""
        self._priority_queue.put((-item.priority, item))  # Negative for max heap
    
    def _process_queue(self):
        """Process items from priority queue."""
        batch = []
        
        while self._processing:
            try:
                # Collect items for batch
                while len(batch) < self.batch_size and not self._priority_queue.empty():
                    _, item = self._priority_queue.get(timeout=0.1)
                    batch.append(item)
                
                # Process batch if we have items
                if batch:
                    logger.debug(f"Processing priority batch with {len(batch)} items")
                    # Process batch (would need process function)
                    batch = []
                else:
                    # No items, wait a bit
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error in priority queue processing: {e}")


def create_batch_items(data_list: List[Any],
                      id_func: Optional[Callable[[Any], str]] = None,
                      priority_func: Optional[Callable[[Any], int]] = None) -> List[BatchItem]:
    """Create batch items from a list of data.
    
    Args:
        data_list: List of data objects
        id_func: Function to generate ID from data
        priority_func: Function to calculate priority from data
        
    Returns:
        List of BatchItem objects
    """
    items = []
    
    for i, data in enumerate(data_list):
        item_id = id_func(data) if id_func else str(i)
        priority = priority_func(data) if priority_func else 0
        
        items.append(BatchItem(
            id=item_id,
            data=data,
            priority=priority
        ))
    
    return items


def batch_with_timeout(items: List[Any],
                      process_func: Callable[[Any], Any],
                      timeout_seconds: float = 300,
                      max_workers: int = 4) -> List[Union[Any, None]]:
    """Process items in batch with timeout per item.
    
    Args:
        items: Items to process
        process_func: Processing function
        timeout_seconds: Timeout per item
        max_workers: Number of parallel workers
        
    Returns:
        List of results (None for timed out items)
    """
    import signal
    from functools import partial
    
    def timeout_handler(signum, frame):
        raise TimeoutError("Processing timed out")
    
    def process_with_timeout(item):
        # Set up timeout (only works on Unix)
        if hasattr(signal, 'SIGALRM'):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout_seconds))
        
        try:
            result = process_func(item)
            return result
        finally:
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)  # Cancel timeout
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_with_timeout, item) for item in items]
        
        for future, item in zip(futures, items):
            try:
                result = future.result(timeout=timeout_seconds)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process item: {e}")
                results.append(None)
    
    return results