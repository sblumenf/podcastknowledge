"""VTT file validation utilities."""

from pathlib import Path
from typing import Tuple, Optional


def validate_vtt_file(file_path: Path) -> Tuple[bool, Optional[str]]:
    """Validate a VTT file.
    
    Args:
        file_path: Path to VTT file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Check if file exists
        if not file_path.exists():
            return False, f"File does not exist: {file_path}"
        
        # Check if file is readable
        if not file_path.is_file():
            return False, f"Not a file: {file_path}"
            
        # Check file extension
        if file_path.suffix.lower() != '.vtt':
            return False, f"Not a VTT file: {file_path}"
        
        # Try to read first few lines to check format
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            # VTT files should start with WEBVTT
            if not first_line.startswith('WEBVTT'):
                return False, f"Invalid VTT format (missing WEBVTT header): {file_path}"
        
        return True, None
        
    except Exception as e:
        return False, f"Error validating file {file_path}: {str(e)}"