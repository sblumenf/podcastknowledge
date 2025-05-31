"""Simple progress bar implementation for CLI feedback.

This module provides a lightweight progress bar using only standard library
components to avoid adding dependencies.
"""

import sys
import time
from typing import Optional


class ProgressBar:
    """Simple text-based progress bar for terminal output."""
    
    def __init__(self, total: int, width: int = 50, prefix: str = "Progress"):
        """Initialize progress bar.
        
        Args:
            total: Total number of items to process
            width: Width of the progress bar in characters
            prefix: Text to display before the progress bar
        """
        self.total = total
        self.width = width
        self.prefix = prefix
        self.current = 0
        self.start_time = time.time()
        self.last_update_time = 0
        
    def update(self, current: int, suffix: str = ""):
        """Update progress bar.
        
        Args:
            current: Current item number (1-based)
            suffix: Optional text to display after the progress bar
        """
        self.current = current
        
        # Calculate progress
        if self.total > 0:
            progress = float(current) / float(self.total)
        else:
            progress = 0
        
        # Calculate time elapsed and ETA
        elapsed = time.time() - self.start_time
        if current > 0 and progress < 1:
            eta = (elapsed / current) * (self.total - current)
            eta_str = self._format_time(eta)
        else:
            eta_str = "N/A"
        
        # Build progress bar
        filled = int(self.width * progress)
        bar = "█" * filled + "░" * (self.width - filled)
        
        # Format percentage
        percent = int(progress * 100)
        
        # Build output string
        output = f"\r{self.prefix}: [{bar}] {percent:3d}% ({current}/{self.total})"
        
        if suffix:
            # Truncate suffix if too long
            max_suffix_len = 40
            if len(suffix) > max_suffix_len:
                suffix = suffix[:max_suffix_len-3] + "..."
            output += f" - {suffix}"
        
        output += f" ETA: {eta_str}"
        
        # Clear line and write progress
        sys.stdout.write("\033[K")  # Clear to end of line
        sys.stdout.write(output)
        sys.stdout.flush()
        
        # Add newline when complete
        if current >= self.total:
            print()
    
    def _format_time(self, seconds: float) -> str:
        """Format time in seconds to human readable string.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time string
        """
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
    
    def finish(self, message: Optional[str] = None):
        """Finish progress bar with optional message.
        
        Args:
            message: Optional completion message
        """
        if message:
            # Clear line and print message
            sys.stdout.write("\033[K")
            sys.stdout.write(f"\r{self.prefix}: {message}\n")
        else:
            # Just ensure we're on a new line
            if self.current < self.total:
                print()
        sys.stdout.flush()


def simple_progress(iterable, prefix: str = "Progress"):
    """Wrap an iterable with a simple progress bar.
    
    Args:
        iterable: Iterable to process
        prefix: Text to display before progress bar
        
    Yields:
        Items from the iterable
    """
    items = list(iterable)
    total = len(items)
    
    if total == 0:
        return
    
    progress = ProgressBar(total, prefix=prefix)
    
    for i, item in enumerate(items, 1):
        progress.update(i)
        yield item
    
    progress.finish()


# For backward compatibility with existing code
def log_progress(current: int, total: int, message: str = ""):
    """Simple progress logging function.
    
    Args:
        current: Current item number (1-based)
        total: Total number of items
        message: Optional message to display
    """
    if total > 0:
        percent = int((current / total) * 100)
        print(f"Progress: {percent}% ({current}/{total}) - {message}")
    else:
        print(f"Progress: {current} items - {message}")