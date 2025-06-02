"""Resource management utilities for handling files, connections, and cleanup."""

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict, List, Callable, Union
import logging
import os
import pickle
import shutil
import tempfile
import weakref

import atexit
try:
    import psutil
except ImportError:
    # Use mock psutil if real one not available
    from tests.utils import mock_psutil as psutil
logger = logging.getLogger(__name__)


class TempFileManager:
    """Manager for temporary files with automatic cleanup."""
    
    def __init__(self):
        """Initialize the temporary file manager."""
        self._temp_files: List[str] = []
        self._temp_dirs: List[str] = []
        # Register cleanup on exit
        atexit.register(self.cleanup_all)
    
    def create_temp_file(self, 
                        suffix: Optional[str] = None,
                        prefix: Optional[str] = None,
                        dir: Optional[str] = None,
                        delete: bool = False) -> str:
        """Create a temporary file.
        
        Args:
            suffix: File suffix (e.g., '.txt')
            prefix: File prefix
            dir: Directory for temp file
            delete: Whether to delete on close (default False for manual cleanup)
            
        Returns:
            Path to temporary file
        """
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir)
        os.close(fd)  # Close the file descriptor
        
        if not delete:
            self._temp_files.append(path)
        
        logger.debug(f"Created temporary file: {path}")
        return path
    
    def create_temp_dir(self,
                       suffix: Optional[str] = None,
                       prefix: Optional[str] = None,
                       dir: Optional[str] = None) -> str:
        """Create a temporary directory.
        
        Args:
            suffix: Directory suffix
            prefix: Directory prefix
            dir: Parent directory
            
        Returns:
            Path to temporary directory
        """
        path = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        self._temp_dirs.append(path)
        logger.debug(f"Created temporary directory: {path}")
        return path
    
    def cleanup_file(self, path: str) -> bool:
        """Clean up a specific temporary file.
        
        Args:
            path: Path to file to clean up
            
        Returns:
            True if cleanup successful
        """
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug(f"Removed temporary file: {path}")
            
            if path in self._temp_files:
                self._temp_files.remove(path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to remove temporary file {path}: {e}")
            return False
    
    def cleanup_dir(self, path: str) -> bool:
        """Clean up a specific temporary directory.
        
        Args:
            path: Path to directory to clean up
            
        Returns:
            True if cleanup successful
        """
        try:
            if os.path.exists(path):
                shutil.rmtree(path)
                logger.debug(f"Removed temporary directory: {path}")
            
            if path in self._temp_dirs:
                self._temp_dirs.remove(path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to remove temporary directory {path}: {e}")
            return False
    
    def cleanup_all(self) -> None:
        """Clean up all temporary files and directories."""
        # Clean up files
        for path in self._temp_files[:]:  # Copy list to avoid modification during iteration
            self.cleanup_file(path)
        
        # Clean up directories
        for path in self._temp_dirs[:]:
            self.cleanup_dir(path)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup_all()


@contextmanager
def temp_file(suffix: Optional[str] = None, 
              prefix: Optional[str] = None,
              mode: str = 'w+b') -> Any:
    """Context manager for temporary file that auto-deletes.
    
    Args:
        suffix: File suffix
        prefix: File prefix
        mode: File open mode
        
    Yields:
        File object
    """
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    try:
        # Close the OS file descriptor and open with Python
        os.close(fd)
        with open(path, mode) as f:
            yield f
    finally:
        try:
            os.remove(path)
        except Exception as e:
            logger.error(f"Failed to remove temp file {path}: {e}")


@contextmanager
def temp_dir(suffix: Optional[str] = None,
             prefix: Optional[str] = None) -> str:
    """Context manager for temporary directory that auto-deletes.
    
    Args:
        suffix: Directory suffix
        prefix: Directory prefix
        
    Yields:
        Path to temporary directory
    """
    path = tempfile.mkdtemp(suffix=suffix, prefix=prefix)
    try:
        yield path
    finally:
        try:
            shutil.rmtree(path)
        except Exception as e:
            logger.error(f"Failed to remove temp dir {path}: {e}")


class ProgressCheckpoint:
    """Enhanced checkpoint system for resumable processing."""
    
    def __init__(self, checkpoint_dir: Optional[str] = None):
        """Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory for storing checkpoints
        """
        self.checkpoint_dir = checkpoint_dir or os.path.join(
            os.getcwd(), 'checkpoints'
        )
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        logger.info(f"Initialized checkpoint manager at: {self.checkpoint_dir}")
    
    def save_episode_progress(self, 
                            episode_id: str, 
                            stage: str, 
                            data: Any) -> bool:
        """Save progress checkpoint for an episode.
        
        Args:
            episode_id: Unique episode identifier
            stage: Processing stage name
            data: Data to checkpoint
            
        Returns:
            True if save successful
        """
        checkpoint_file = os.path.join(
            self.checkpoint_dir, 
            f"episode_{episode_id}_{stage}.pkl"
        )
        
        checkpoint_data = {
            'episode_id': episode_id,
            'stage': stage,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        
        try:
            with open(checkpoint_file, 'wb') as f:
                pickle.dump(checkpoint_data, f)
            logger.info(f"Saved checkpoint: {stage} for episode {episode_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False
    
    def load_episode_progress(self, 
                            episode_id: str, 
                            stage: str) -> Optional[Any]:
        """Load progress checkpoint for an episode.
        
        Args:
            episode_id: Unique episode identifier
            stage: Processing stage name
            
        Returns:
            Checkpoint data or None if not found
        """
        checkpoint_file = os.path.join(
            self.checkpoint_dir, 
            f"episode_{episode_id}_{stage}.pkl"
        )
        
        if not os.path.exists(checkpoint_file):
            return None
        
        try:
            with open(checkpoint_file, 'rb') as f:
                checkpoint_data = pickle.load(f)
            logger.info(f"Loaded checkpoint: {stage} for episode {episode_id}")
            return checkpoint_data['data']
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def get_completed_episodes(self) -> List[str]:
        """Get list of completed episode IDs from checkpoints.
        
        Returns:
            List of episode IDs that have been completed
        """
        completed = set()
        
        try:
            for filename in os.listdir(self.checkpoint_dir):
                if filename.startswith("episode_") and filename.endswith("_complete.pkl"):
                    episode_id = filename.split("_")[1]
                    completed.add(episode_id)
        except Exception as e:
            logger.error(f"Failed to scan checkpoints: {e}")
        
        return list(completed)
    
    def clean_episode_checkpoints(self, episode_id: str) -> None:
        """Remove all checkpoints for a specific episode.
        
        Args:
            episode_id: Episode ID to clean up
        """
        try:
            for filename in os.listdir(self.checkpoint_dir):
                if filename.startswith(f"episode_{episode_id}_"):
                    filepath = os.path.join(self.checkpoint_dir, filename)
                    os.remove(filepath)
                    logger.debug(f"Removed checkpoint: {filename}")
        except Exception as e:
            logger.error(f"Failed to clean checkpoints for episode {episode_id}: {e}")
    
    def clean_old_checkpoints(self, days: int = 7) -> None:
        """Remove checkpoints older than specified days.
        
        Args:
            days: Number of days to keep checkpoints
        """
        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        try:
            for filename in os.listdir(self.checkpoint_dir):
                filepath = os.path.join(self.checkpoint_dir, filename)
                if os.path.getmtime(filepath) < cutoff_time:
                    os.remove(filepath)
                    logger.info(f"Removed old checkpoint: {filename}")
        except Exception as e:
            logger.error(f"Failed to clean old checkpoints: {e}")


class ResourcePool:
    """Generic resource pool for managing reusable resources."""
    
    def __init__(self, 
                 factory: Callable[[], Any],
                 max_size: int = 10,
                 reset_func: Optional[Callable[[Any], None]] = None):
        """Initialize resource pool.
        
        Args:
            factory: Function to create new resources
            max_size: Maximum pool size
            reset_func: Function to reset resource before reuse
        """
        self.factory = factory
        self.max_size = max_size
        self.reset_func = reset_func
        self._available: List[Any] = []
        self._in_use: weakref.WeakSet = weakref.WeakSet()
        self._created_count = 0
    
    def acquire(self) -> Any:
        """Acquire a resource from the pool.
        
        Returns:
            Resource instance
        """
        # Try to get from available pool
        if self._available:
            resource = self._available.pop()
            if self.reset_func:
                try:
                    self.reset_func(resource)
                except Exception as e:
                    logger.error(f"Failed to reset resource: {e}")
                    # Create new resource if reset fails
                    resource = self._create_resource()
        else:
            resource = self._create_resource()
        
        self._in_use.add(resource)
        return resource
    
    def release(self, resource: Any) -> None:
        """Release a resource back to the pool.
        
        Args:
            resource: Resource to release
        """
        if resource in self._in_use:
            self._in_use.discard(resource)
            
            # Only return to pool if under max size
            if len(self._available) < self.max_size:
                self._available.append(resource)
            else:
                # Let it be garbage collected
                pass
    
    def _create_resource(self) -> Any:
        """Create a new resource."""
        resource = self.factory()
        self._created_count += 1
        logger.debug(f"Created resource #{self._created_count}")
        return resource
    
    @contextmanager
    def get_resource(self):
        """Context manager for acquiring and releasing resources.
        
        Yields:
            Resource instance
        """
        resource = self.acquire()
        try:
            yield resource
        finally:
            self.release(resource)
    
    def clear(self) -> None:
        """Clear all available resources."""
        self._available.clear()
        logger.info(f"Cleared resource pool (created {self._created_count} total)")


class ConnectionManager:
    """Manager for database connections with automatic cleanup."""
    
    def __init__(self, 
                 connection_factory: Callable[[], Any],
                 close_func: Optional[Callable[[Any], None]] = None):
        """Initialize connection manager.
        
        Args:
            connection_factory: Function to create connections
            close_func: Function to close connections
        """
        self.connection_factory = connection_factory
        self.close_func = close_func or (lambda conn: conn.close())
        self._connection = None
    
    def get_connection(self) -> Any:
        """Get or create a connection.
        
        Returns:
            Connection instance
        """
        if self._connection is None:
            self._connection = self.connection_factory()
            logger.info("Created new connection")
        return self._connection
    
    def close(self) -> None:
        """Close the connection."""
        if self._connection is not None:
            try:
                self.close_func(self._connection)
                logger.info("Connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
            finally:
                self._connection = None
    
    def __enter__(self):
        """Context manager entry."""
        return self.get_connection()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


@contextmanager
def file_lock(filepath: str, timeout: float = 10.0):
    """Simple file-based lock for coordinating access.
    
    Args:
        filepath: Path to file to lock
        timeout: Maximum time to wait for lock
        
    Yields:
        None
    """
    import time
    lockfile = f"{filepath}.lock"
    start_time = time.time()
    
    # Try to acquire lock
    while os.path.exists(lockfile):
        if time.time() - start_time > timeout:
            raise TimeoutError(f"Could not acquire lock for {filepath}")
        time.sleep(0.1)
    
    # Create lock file
    try:
        with open(lockfile, 'w') as f:
            f.write(str(os.getpid()))
        yield
    finally:
        # Remove lock file
        try:
            os.remove(lockfile)
        except Exception as e:
            logger.error(f"Failed to remove lock file {lockfile}: {e}")


def get_system_resources() -> Dict[str, Any]:
    """Get current system resource usage.
    
    Returns:
        Dictionary with resource usage metrics
    """
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_total_gb = memory.total / (1024 ** 3)
        memory_used_gb = memory.used / (1024 ** 3)
        memory_available_gb = memory.available / (1024 ** 3)
        memory_percent = memory.percent
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_total_gb = disk.total / (1024 ** 3)
        disk_used_gb = disk.used / (1024 ** 3)
        disk_free_gb = disk.free / (1024 ** 3)
        disk_percent = disk.percent
        
        # GPU usage (if available)
        gpu_info = _get_gpu_usage()
        
        return {
            "cpu_percent": cpu_percent,
            "cpu_count": cpu_count,
            "memory_total_gb": round(memory_total_gb, 2),
            "memory_used_gb": round(memory_used_gb, 2),
            "memory_available_gb": round(memory_available_gb, 2),
            "memory_percent": memory_percent,
            "disk_total_gb": round(disk_total_gb, 2),
            "disk_used_gb": round(disk_used_gb, 2),
            "disk_free_gb": round(disk_free_gb, 2),
            "disk_percent": disk_percent,
            "gpu": gpu_info
        }
    except Exception as e:
        logger.error(f"Failed to get system resources: {e}")
        return {
            "error": str(e),
            "cpu_percent": 0,
            "memory_percent": 0,
            "disk_percent": 0
        }


def _get_gpu_usage() -> Optional[Dict[str, Any]]:
    """Get GPU usage if available.
    
    Returns:
        GPU usage information or None if not available
    """
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpus = []
            
            for i in range(gpu_count):
                props = torch.cuda.get_device_properties(i)
                memory_total = props.total_memory / (1024 ** 3)
                memory_allocated = torch.cuda.memory_allocated(i) / (1024 ** 3)
                memory_cached = torch.cuda.memory_reserved(i) / (1024 ** 3)
                
                gpus.append({
                    "id": i,
                    "name": props.name,
                    "memory_total_gb": round(memory_total, 2),
                    "memory_allocated_gb": round(memory_allocated, 2),
                    "memory_cached_gb": round(memory_cached, 2),
                    "memory_percent": round((memory_allocated / memory_total) * 100, 2)
                })
            
            return {
                "available": True,
                "count": gpu_count,
                "devices": gpus
            }
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Error getting GPU info: {e}")
    
    return {"available": False}