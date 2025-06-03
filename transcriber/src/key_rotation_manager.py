"""Multi-Key Rotation Manager for Podcast Transcription Pipeline.

This module manages round-robin API key rotation to distribute load evenly
across multiple Gemini API keys and avoid hitting rate limits.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from src.utils.logging import get_logger

logger = get_logger('key_rotation_manager')


class KeyStatus(Enum):
    """Status of an API key."""
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    ERROR = "error"


@dataclass
class APIKeyState:
    """State information for a single API key."""
    index: int
    key_name: str
    status: KeyStatus = KeyStatus.AVAILABLE
    last_used: Optional[datetime] = None
    consecutive_failures: int = 0
    error_message: Optional[str] = None
    
    def is_usable(self) -> bool:
        """Check if this key can be used."""
        return self.status == KeyStatus.AVAILABLE
    
    def mark_success(self):
        """Mark a successful use of this key."""
        self.consecutive_failures = 0
        self.status = KeyStatus.AVAILABLE
        self.last_used = datetime.now(timezone.utc)
        self.error_message = None
    
    def mark_failure(self, error_message: str):
        """Mark a failed use of this key."""
        self.consecutive_failures += 1
        self.last_used = datetime.now(timezone.utc)
        self.error_message = error_message
        
        # Determine status based on error
        if "quota" in error_message.lower():
            self.status = KeyStatus.QUOTA_EXCEEDED
        elif "rate" in error_message.lower():
            self.status = KeyStatus.RATE_LIMITED
        else:
            # Mark as error after 3 consecutive failures
            if self.consecutive_failures >= 3:
                self.status = KeyStatus.ERROR
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'index': self.index,
            'key_name': self.key_name,
            'status': self.status.value,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'consecutive_failures': self.consecutive_failures,
            'error_message': self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'APIKeyState':
        """Create from dictionary."""
        last_used = None
        if data.get('last_used'):
            last_used = datetime.fromisoformat(data['last_used'])
        
        return cls(
            index=data['index'],
            key_name=data['key_name'],
            status=KeyStatus(data.get('status', 'available')),
            last_used=last_used,
            consecutive_failures=data.get('consecutive_failures', 0),
            error_message=data.get('error_message')
        )


class KeyRotationManager:
    """Manages round-robin rotation of multiple API keys."""
    
    def __init__(self, api_keys: List[str], state_dir: Optional[Path] = None):
        """Initialize with list of API keys.
        
        Args:
            api_keys: List of API key strings
            state_dir: Directory for state files. Uses env var STATE_DIR or 'data' if not provided.
        """
        if not api_keys:
            raise ValueError("At least one API key must be provided")
        
        self.api_keys = api_keys
        self.key_states: List[APIKeyState] = []
        self.current_index = 0
        
        # Determine state directory
        if state_dir:
            base_dir = state_dir
        elif os.environ.get('STATE_DIR'):
            base_dir = Path(os.environ['STATE_DIR'])
        else:
            base_dir = Path("data")
        
        self.state_file = base_dir / ".key_rotation_state.json"
        
        # Initialize key states
        for i, key in enumerate(api_keys):
            # Mask key for logging (show first 8 chars)
            key_name = f"key_{i+1} ({key[:8]}...)"
            self.key_states.append(APIKeyState(index=i, key_name=key_name))
        
        # Load saved state if exists
        self._load_state()
        
        logger.info(f"Initialized key rotation manager with {len(api_keys)} keys")
    
    def _load_state(self):
        """Load saved rotation state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                
                # Restore current index
                self.current_index = data.get('current_index', 0)
                
                # Restore key states
                for state_data in data.get('key_states', []):
                    idx = state_data['index']
                    if idx < len(self.key_states):
                        self.key_states[idx] = APIKeyState.from_dict(state_data)
                
                # Check for daily reset
                last_reset = data.get('last_reset')
                if last_reset:
                    last_reset_date = datetime.fromisoformat(last_reset).date()
                    if last_reset_date < datetime.now(timezone.utc).date():
                        self._daily_reset()
                
                logger.info(f"Loaded rotation state, current index: {self.current_index}")
                
            except Exception as e:
                logger.warning(f"Failed to load rotation state: {e}")
    
    def _save_state(self):
        """Save current rotation state to file."""
        self.state_file.parent.mkdir(exist_ok=True)
        
        data = {
            'current_index': self.current_index,
            'last_reset': datetime.now(timezone.utc).date().isoformat(),
            'key_states': [state.to_dict() for state in self.key_states],
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save rotation state: {e}")
    
    def _daily_reset(self):
        """Reset key states for a new day."""
        logger.info("Performing daily reset of key states")
        for state in self.key_states:
            if state.status in (KeyStatus.RATE_LIMITED, KeyStatus.QUOTA_EXCEEDED):
                state.status = KeyStatus.AVAILABLE
                state.consecutive_failures = 0
                state.error_message = None
    
    def get_next_key(self) -> Tuple[str, int]:
        """Get the next available API key using round-robin rotation.
        
        Returns:
            Tuple of (api_key, key_index)
            
        Raises:
            Exception: If no keys are available
        """
        # Try up to len(keys) times to find an available key
        attempts = 0
        starting_index = self.current_index
        
        while attempts < len(self.api_keys):
            state = self.key_states[self.current_index]
            
            if state.is_usable():
                key = self.api_keys[self.current_index]
                key_index = self.current_index
                
                # Move to next key for next call (round-robin)
                self.current_index = (self.current_index + 1) % len(self.api_keys)
                self._save_state()
                
                logger.info(f"Selected {state.key_name} for next request")
                return key, key_index
            
            # Try next key
            self.current_index = (self.current_index + 1) % len(self.api_keys)
            attempts += 1
        
        # No available keys found
        self._log_key_status()
        raise Exception("No API keys available. All keys are rate limited or have errors.")
    
    def mark_key_success(self, key_index: int):
        """Mark a key as successfully used.
        
        Args:
            key_index: Index of the key that was used
        """
        if 0 <= key_index < len(self.key_states):
            state = self.key_states[key_index]
            state.mark_success()
            self._save_state()
            logger.debug(f"{state.key_name} marked as successful")
    
    def mark_key_failure(self, key_index: int, error_message: str):
        """Mark a key as failed.
        
        Args:
            key_index: Index of the key that failed
            error_message: Error message from the failure
        """
        if 0 <= key_index < len(self.key_states):
            state = self.key_states[key_index]
            state.mark_failure(error_message)
            self._save_state()
            logger.warning(f"{state.key_name} marked as failed: {error_message}")
    
    def get_key_by_index(self, key_index: int) -> Optional[str]:
        """Get a specific API key by index.
        
        Args:
            key_index: Index of the key to retrieve
            
        Returns:
            API key string or None if index invalid
        """
        if 0 <= key_index < len(self.api_keys):
            return self.api_keys[key_index]
        return None
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of all key statuses.
        
        Returns:
            Dictionary with status information
        """
        summary = {
            'total_keys': len(self.api_keys),
            'current_index': self.current_index,
            'available_keys': sum(1 for s in self.key_states if s.is_usable()),
            'key_states': []
        }
        
        for state in self.key_states:
            summary['key_states'].append({
                'name': state.key_name,
                'status': state.status.value,
                'last_used': state.last_used.isoformat() if state.last_used else None,
                'failures': state.consecutive_failures,
                'error': state.error_message
            })
        
        return summary
    
    def _log_key_status(self):
        """Log the current status of all keys."""
        logger.info("Current key status:")
        for state in self.key_states:
            status_msg = f"  {state.key_name}: {state.status.value}"
            if state.error_message:
                status_msg += f" - {state.error_message}"
            logger.info(status_msg)
    
    def force_reset_key(self, key_index: int):
        """Force reset a key to available status.
        
        Args:
            key_index: Index of the key to reset
        """
        if 0 <= key_index < len(self.key_states):
            state = self.key_states[key_index]
            state.status = KeyStatus.AVAILABLE
            state.consecutive_failures = 0
            state.error_message = None
            self._save_state()
            logger.info(f"Force reset {state.key_name} to available")


def create_key_rotation_manager(state_dir: Optional[Path] = None) -> Optional[KeyRotationManager]:
    """Create a key rotation manager from environment variables.
    
    Args:
        state_dir: Directory for state files. Uses env var STATE_DIR or 'data' if not provided.
    
    Returns:
        KeyRotationManager instance or None if no keys found
    """
    api_keys = []
    
    # Try to load multiple API keys
    for i in range(1, 10):  # Support up to 9 keys
        key = os.getenv(f'GEMINI_API_KEY_{i}')
        if key:
            api_keys.append(key)
        else:
            # Stop looking after first missing key
            break
    
    # Fallback to single key variable
    if not api_keys:
        single_key = os.getenv('GEMINI_API_KEY')
        if single_key:
            api_keys.append(single_key)
    
    if not api_keys:
        logger.error("No API keys found in environment")
        return None
    
    return KeyRotationManager(api_keys, state_dir)