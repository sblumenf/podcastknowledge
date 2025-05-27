"""Signal management component for graceful shutdown handling."""

import signal
import sys
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class SignalManager:
    """Manages signal handling for graceful shutdown of the pipeline."""
    
    def __init__(self):
        """Initialize the signal manager."""
        self._shutdown_requested = False
        self._cleanup_callback: Optional[Callable] = None
        self._original_sigint = None
        self._original_sigterm = None
    
    def setup(self, cleanup_callback: Optional[Callable] = None):
        """Set up signal handlers for graceful shutdown.
        
        Args:
            cleanup_callback: Optional callback to run during shutdown
        """
        self._cleanup_callback = cleanup_callback
        
        # Store original handlers
        self._original_sigint = signal.signal(signal.SIGINT, self._signal_handler)
        self._original_sigterm = signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Signal handlers configured for graceful shutdown")
    
    def _signal_handler(self, signum, frame):
        """Handle received signals.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self._shutdown_requested = True
        
        # Run cleanup callback if provided
        if self._cleanup_callback:
            try:
                self._cleanup_callback()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        
        sys.exit(0)
    
    def shutdown(self):
        """Restore original signal handlers."""
        if self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm:
            signal.signal(signal.SIGTERM, self._original_sigterm)
        
        logger.info("Signal handlers restored")
    
    @property
    def shutdown_requested(self) -> bool:
        """Check if shutdown has been requested.
        
        Returns:
            True if shutdown requested, False otherwise
        """
        return self._shutdown_requested