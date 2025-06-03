"""State Management Utilities for Podcast Transcription Pipeline.

This module provides utilities for managing state files across the application,
including isolation between test and production environments.
"""

import os
import shutil
import json
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

from src.utils.logging import get_logger

logger = get_logger('state_management')


def get_state_directory() -> Path:
    """Get the state directory from environment or default.
    
    Returns:
        Path to state directory
    """
    state_dir = os.environ.get('STATE_DIR', 'data')
    return Path(state_dir)


def list_state_files(state_dir: Optional[Path] = None) -> List[Path]:
    """List all state files in the state directory.
    
    Args:
        state_dir: State directory to scan (uses get_state_directory() if None)
    
    Returns:
        List of state file paths
    """
    if state_dir is None:
        state_dir = get_state_directory()
    
    state_files = []
    
    # Known state file patterns
    patterns = [
        '.retry_state.json',
        '.key_rotation_state.json',
        '.youtube_cache.json',
        '.progress.json',
        '.transcription_progress.json',
        'index.json',
        'checkpoints/active_checkpoint.json'
    ]
    
    for pattern in patterns:
        file_path = state_dir / pattern
        if file_path.exists():
            state_files.append(file_path)
    
    # Also look for any .json files in the state directory
    for json_file in state_dir.glob('*.json'):
        if json_file not in state_files:
            state_files.append(json_file)
    
    # Look for hidden JSON files
    for hidden_file in state_dir.glob('.*.json'):
        if hidden_file not in state_files:
            state_files.append(hidden_file)
    
    return state_files


def backup_state(state_dir: Optional[Path] = None, backup_name: Optional[str] = None) -> Path:
    """Create a backup of all state files.
    
    Args:
        state_dir: State directory to backup (uses get_state_directory() if None)
        backup_name: Name for backup directory (uses timestamp if None)
    
    Returns:
        Path to backup directory
    """
    if state_dir is None:
        state_dir = get_state_directory()
    
    if backup_name is None:
        backup_name = f"state_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    backup_dir = state_dir.parent / 'state_backups' / backup_name
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    state_files = list_state_files(state_dir)
    
    for state_file in state_files:
        relative_path = state_file.relative_to(state_dir)
        backup_path = backup_dir / relative_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            shutil.copy2(state_file, backup_path)
            logger.info(f"Backed up {relative_path} to {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to backup {state_file}: {e}")
    
    logger.info(f"State backup created at: {backup_dir}")
    return backup_dir


def reset_state(state_dir: Optional[Path] = None, 
                create_backup: bool = True,
                keep_backups: int = 5) -> bool:
    """Reset all state files with optional backup.
    
    Args:
        state_dir: State directory to reset (uses get_state_directory() if None)
        create_backup: Whether to create a backup before reset
        keep_backups: Number of recent backups to keep
    
    Returns:
        True if reset was successful
    """
    if state_dir is None:
        state_dir = get_state_directory()
    
    try:
        # Create backup if requested
        if create_backup:
            backup_dir = backup_state(state_dir)
            
            # Clean up old backups
            backup_parent = backup_dir.parent
            if backup_parent.exists():
                backups = sorted(backup_parent.iterdir(), key=lambda p: p.stat().st_mtime)
                if len(backups) > keep_backups:
                    for old_backup in backups[:-keep_backups]:
                        shutil.rmtree(old_backup)
                        logger.info(f"Removed old backup: {old_backup.name}")
        
        # Get all state files
        state_files = list_state_files(state_dir)
        
        # Remove each state file
        for state_file in state_files:
            try:
                if state_file.is_file():
                    state_file.unlink()
                    logger.info(f"Removed state file: {state_file}")
                elif state_file.is_dir():
                    shutil.rmtree(state_file)
                    logger.info(f"Removed state directory: {state_file}")
            except Exception as e:
                logger.error(f"Failed to remove {state_file}: {e}")
        
        # Remove checkpoint temp files
        checkpoint_dir = state_dir / 'checkpoints'
        if checkpoint_dir.exists():
            # Remove temp directory
            temp_dir = checkpoint_dir / 'temp'
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                temp_dir.mkdir()
                logger.info("Cleared checkpoint temp directory")
            
            # Remove any .tmp files
            for tmp_file in checkpoint_dir.glob('*.tmp'):
                tmp_file.unlink()
                logger.info(f"Removed temp file: {tmp_file.name}")
        
        logger.info("State reset completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"State reset failed: {e}")
        return False


def show_state_status(state_dir: Optional[Path] = None) -> Dict[str, any]:
    """Show status of all state files.
    
    Args:
        state_dir: State directory to check (uses get_state_directory() if None)
    
    Returns:
        Dictionary with state file information
    """
    if state_dir is None:
        state_dir = get_state_directory()
    
    status = {
        'state_directory': str(state_dir),
        'state_files': {}
    }
    
    state_files = list_state_files(state_dir)
    
    for state_file in state_files:
        try:
            stat = state_file.stat()
            info = {
                'exists': True,
                'size_bytes': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
            }
            
            # Try to load and get basic info if it's JSON
            if state_file.suffix == '.json':
                try:
                    with open(state_file, 'r') as f:
                        data = json.load(f)
                    
                    if isinstance(data, dict):
                        info['entries'] = len(data)
                        if 'last_updated' in data:
                            info['last_updated'] = data['last_updated']
                        if 'episodes' in data:
                            info['episodes'] = len(data['episodes'])
                except:
                    pass
            
            status['state_files'][str(state_file.relative_to(state_dir))] = info
            
        except FileNotFoundError:
            status['state_files'][str(state_file.relative_to(state_dir))] = {'exists': False}
    
    return status


def export_state(state_dir: Optional[Path] = None, export_path: Optional[Path] = None) -> Path:
    """Export state to a file for backup/migration.
    
    Args:
        state_dir: State directory to export (uses get_state_directory() if None)
        export_path: Path for export file (uses timestamped name if None)
    
    Returns:
        Path to export file
    """
    if state_dir is None:
        state_dir = get_state_directory()
    
    if export_path is None:
        export_path = Path(f"state_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar.gz")
    
    import tarfile
    
    with tarfile.open(export_path, "w:gz") as tar:
        for state_file in list_state_files(state_dir):
            if state_file.exists():
                arcname = state_file.relative_to(state_dir)
                tar.add(state_file, arcname=str(arcname))
    
    logger.info(f"State exported to: {export_path}")
    return export_path


def import_state(import_path: Path, state_dir: Optional[Path] = None, create_backup: bool = True) -> bool:
    """Import state from an export file.
    
    Args:
        import_path: Path to import file
        state_dir: State directory to import to (uses get_state_directory() if None)
        create_backup: Whether to backup current state before import
    
    Returns:
        True if import was successful
    """
    if state_dir is None:
        state_dir = get_state_directory()
    
    if not import_path.exists():
        logger.error(f"Import file not found: {import_path}")
        return False
    
    try:
        # Backup current state if requested
        if create_backup:
            backup_state(state_dir, f"pre_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        import tarfile
        
        with tarfile.open(import_path, "r:gz") as tar:
            tar.extractall(state_dir)
        
        logger.info(f"State imported from: {import_path}")
        return True
        
    except Exception as e:
        logger.error(f"State import failed: {e}")
        return False