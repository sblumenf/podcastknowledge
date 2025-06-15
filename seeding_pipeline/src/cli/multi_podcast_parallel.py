"""Parallel processing support for multi-podcast mode."""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from dataclasses import dataclass

from src.config.podcast_databases import PodcastDatabaseConfig
from src.utils.logging import get_logger
from src.monitoring import get_pipeline_metrics

logger = get_logger(__name__)


@dataclass
class PodcastProcessingResult:
    """Result of processing a single podcast."""
    podcast_id: str
    processed: int
    failed: int
    duration: float
    error: Optional[str] = None


class MultiPodcastParallelProcessor:
    """Handles parallel processing of multiple podcasts."""
    
    def __init__(self, max_workers: int = 4, rate_limit_per_podcast: float = 0.5):
        """Initialize parallel processor.
        
        Args:
            max_workers: Maximum number of concurrent podcast processors
            rate_limit_per_podcast: Minimum seconds between processing files in same podcast
        """
        self.max_workers = max_workers
        self.rate_limit_per_podcast = rate_limit_per_podcast
        self.metrics = get_pipeline_metrics()
        self._processing_times: Dict[str, float] = {}
    
    def process_podcasts_parallel(self, 
                                 podcast_ids: List[str], 
                                 process_func,
                                 args) -> Dict[str, PodcastProcessingResult]:
        """Process multiple podcasts in parallel.
        
        Args:
            podcast_ids: List of podcast IDs to process
            process_func: Function to process a single podcast
            args: Arguments to pass to process function
            
        Returns:
            Dictionary mapping podcast_id to processing result
        """
        results = {}
        total_start = time.time()
        
        logger.info(f"Starting parallel processing of {len(podcast_ids)} podcasts with {self.max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all podcast processing tasks
            future_to_podcast = {
                executor.submit(self._process_podcast_with_metrics, podcast_id, process_func, args): podcast_id
                for podcast_id in podcast_ids
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_podcast):
                podcast_id = future_to_podcast[future]
                try:
                    result = future.result()
                    results[podcast_id] = result
                    
                    # Log individual podcast completion
                    logger.info(
                        f"Completed {podcast_id}: {result.processed} processed, "
                        f"{result.failed} failed in {result.duration:.2f}s"
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing podcast {podcast_id}: {e}")
                    results[podcast_id] = PodcastProcessingResult(
                        podcast_id=podcast_id,
                        processed=0,
                        failed=0,
                        duration=0.0,
                        error=str(e)
                    )
        
        # Record overall metrics
        total_duration = time.time() - total_start
        total_processed = sum(r.processed for r in results.values())
        total_failed = sum(r.failed for r in results.values())
        
        # Log metrics since record_batch_processing doesn't exist
        logger.info(f"Batch processing metrics: {len(podcast_ids)} podcasts, "
                   f"{total_duration:.2f}s total duration")
        
        logger.info(
            f"Parallel processing complete: {len(podcast_ids)} podcasts, "
            f"{total_processed} files processed, {total_failed} failed in {total_duration:.2f}s"
        )
        
        return results
    
    def _process_podcast_with_metrics(self, podcast_id: str, process_func, args) -> PodcastProcessingResult:
        """Process a single podcast with metrics and rate limiting.
        
        Args:
            podcast_id: ID of podcast to process
            process_func: Function to process the podcast
            args: Arguments for process function
            
        Returns:
            Processing result
        """
        start_time = time.time()
        
        try:
            # Apply rate limiting
            self._apply_rate_limit(podcast_id)
            
            # Process the podcast
            result = process_func(args, podcast_id)
            
            duration = time.time() - start_time
            
            # Log per-podcast metrics
            logger.debug(f"Podcast {podcast_id} processed in {duration:.2f}s")
            
            return PodcastProcessingResult(
                podcast_id=podcast_id,
                processed=result.get('processed', 0),
                failed=result.get('failed', 0),
                duration=duration
            )
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Failed to process podcast {podcast_id}: {e}")
            
            return PodcastProcessingResult(
                podcast_id=podcast_id,
                processed=0,
                failed=0,
                duration=duration,
                error=str(e)
            )
    
    def _apply_rate_limit(self, podcast_id: str) -> None:
        """Apply rate limiting for a podcast.
        
        Args:
            podcast_id: Podcast identifier
        """
        if podcast_id in self._processing_times:
            last_time = self._processing_times[podcast_id]
            elapsed = time.time() - last_time
            
            if elapsed < self.rate_limit_per_podcast:
                sleep_time = self.rate_limit_per_podcast - elapsed
                logger.debug(f"Rate limiting {podcast_id}: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
        
        self._processing_times[podcast_id] = time.time()


class DatabaseConnectionPool:
    """Manages database connections for multi-podcast processing."""
    
    def __init__(self, max_connections_per_db: int = 10):
        """Initialize connection pool manager.
        
        Args:
            max_connections_per_db: Maximum connections per database
        """
        self.max_connections_per_db = max_connections_per_db
        self._connection_counts: Dict[str, int] = {}
        self.podcast_config = PodcastDatabaseConfig()
    
    def acquire_connection(self, podcast_id: str) -> bool:
        """Try to acquire a connection for a podcast.
        
        Args:
            podcast_id: Podcast identifier
            
        Returns:
            True if connection acquired, False if limit reached
        """
        db_name = self.podcast_config.get_database_for_podcast(podcast_id)
        
        current_count = self._connection_counts.get(db_name, 0)
        if current_count >= self.max_connections_per_db:
            logger.warning(f"Connection limit reached for database {db_name}")
            return False
        
        self._connection_counts[db_name] = current_count + 1
        return True
    
    def release_connection(self, podcast_id: str) -> None:
        """Release a connection for a podcast.
        
        Args:
            podcast_id: Podcast identifier
        """
        db_name = self.podcast_config.get_database_for_podcast(podcast_id)
        
        if db_name in self._connection_counts:
            self._connection_counts[db_name] = max(0, self._connection_counts[db_name] - 1)
    
    def get_connection_stats(self) -> Dict[str, int]:
        """Get current connection statistics.
        
        Returns:
            Dictionary of database names to connection counts
        """
        return self._connection_counts.copy()


def optimize_worker_count(podcast_count: int, requested_workers: int = 4) -> int:
    """Optimize worker count based on podcast count and system resources.
    
    Args:
        podcast_count: Number of podcasts to process
        requested_workers: Requested number of workers
        
    Returns:
        Optimized worker count
    """
    # Get CPU count
    cpu_count = os.cpu_count() or 4
    
    # Don't use more workers than podcasts
    max_useful_workers = min(podcast_count, requested_workers)
    
    # Don't exceed CPU count for CPU-bound tasks
    # For I/O bound tasks (like ours), we can go higher
    max_system_workers = cpu_count * 2
    
    # Choose the minimum of all constraints
    optimal_workers = min(max_useful_workers, max_system_workers)
    
    logger.info(
        f"Optimized worker count: {optimal_workers} "
        f"(podcasts: {podcast_count}, requested: {requested_workers}, CPUs: {cpu_count})"
    )
    
    return optimal_workers