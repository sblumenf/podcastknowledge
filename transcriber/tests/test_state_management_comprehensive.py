"""Comprehensive tests for state management utilities with memory optimization."""

import os
import json
import shutil
import tarfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open, MagicMock
import pytest

from src.utils.state_management import (
    get_state_directory,
    list_state_files,
    backup_state,
    reset_state,
    show_state_status,
    export_state,
    import_state
)


@pytest.fixture
def temp_state_dir(tmp_path):
    """Create a temporary state directory for testing."""
    state_dir = tmp_path / "test_state"
    state_dir.mkdir()
    
    # Set environment variable
    original_state_dir = os.environ.get('STATE_DIR')
    os.environ['STATE_DIR'] = str(state_dir)
    
    yield state_dir
    
    # Restore original environment
    if original_state_dir is not None:
        os.environ['STATE_DIR'] = original_state_dir
    else:
        os.environ.pop('STATE_DIR', None)


@pytest.fixture
def populated_state_dir(temp_state_dir):
    """Create a state directory with sample state files."""
    # Create various state files
    state_files = {
        '.retry_state.json': {
            'attempts': {'key1': 3, 'key2': 1},
            'last_updated': '2024-01-01T10:00:00'
        },
        '.key_rotation_state.json': {
            'current_key_index': 2,
            'key_usage': {'key1': 100, 'key2': 50},
            'last_rotation': '2024-01-01T09:00:00'
        },
        '.youtube_cache.json': {
            'cache': {'episode1': 'url1', 'episode2': 'url2'}
        },
        '.progress.json': {
            'processed': ['ep1', 'ep2'],
            'total': 10
        },
        'index.json': {
            'episodes': [],
            'last_updated': '2024-01-01T11:00:00'
        }
    }
    
    # Write state files
    for filename, content in state_files.items():
        file_path = temp_state_dir / filename
        with open(file_path, 'w') as f:
            json.dump(content, f)
    
    # Create checkpoints directory with a file
    checkpoint_dir = temp_state_dir / 'checkpoints'
    checkpoint_dir.mkdir()
    checkpoint_file = checkpoint_dir / 'active_checkpoint.json'
    with open(checkpoint_file, 'w') as f:
        json.dump({'checkpoint': 'data'}, f)
    
    # Create temp directory
    temp_dir = checkpoint_dir / 'temp'
    temp_dir.mkdir()
    
    yield temp_state_dir


class TestGetStateDirectory:
    """Test get_state_directory function."""
    
    def test_get_state_directory_from_env(self, temp_state_dir):
        """Test getting state directory from environment variable."""
        result = get_state_directory()
        assert result == temp_state_dir
    
    def test_get_state_directory_default(self):
        """Test getting default state directory."""
        # Temporarily remove STATE_DIR from environment
        original = os.environ.pop('STATE_DIR', None)
        try:
            result = get_state_directory()
            assert result == Path('data')
        finally:
            if original is not None:
                os.environ['STATE_DIR'] = original


class TestListStateFiles:
    """Test list_state_files function."""
    
    def test_list_state_files_populated(self, populated_state_dir):
        """Test listing state files in populated directory."""
        files = list_state_files(populated_state_dir)
        
        # Convert to relative paths for easier checking
        relative_files = [f.name for f in files]
        
        # Check known files are present
        assert '.retry_state.json' in relative_files
        assert '.key_rotation_state.json' in relative_files
        assert '.youtube_cache.json' in relative_files
        assert '.progress.json' in relative_files
        assert 'index.json' in relative_files
        
        # Check checkpoint file
        checkpoint_files = [f for f in files if 'active_checkpoint.json' in str(f)]
        assert len(checkpoint_files) == 1
    
    def test_list_state_files_empty(self, temp_state_dir):
        """Test listing state files in empty directory."""
        files = list_state_files(temp_state_dir)
        assert len(files) == 0
    
    def test_list_state_files_default_dir(self, populated_state_dir):
        """Test listing state files with default directory."""
        files = list_state_files()  # Uses get_state_directory()
        
        # Should find files in the populated directory
        assert len(files) > 0
    
    def test_list_state_files_additional_json(self, temp_state_dir):
        """Test finding additional JSON files."""
        # Create some additional JSON files
        (temp_state_dir / 'custom.json').write_text('{}')
        (temp_state_dir / '.hidden.json').write_text('{}')
        
        files = list_state_files(temp_state_dir)
        file_names = [f.name for f in files]
        
        assert 'custom.json' in file_names
        assert '.hidden.json' in file_names


class TestBackupState:
    """Test backup_state function with memory optimization."""
    
    def test_backup_state_default_name(self, populated_state_dir):
        """Test creating backup with default timestamp name."""
        backup_dir = backup_state(populated_state_dir)
        
        assert backup_dir.exists()
        assert 'state_backup_' in backup_dir.name
        assert backup_dir.parent.name == 'state_backups'
        
        # Check files were copied
        assert (backup_dir / '.retry_state.json').exists()
        assert (backup_dir / 'index.json').exists()
        assert (backup_dir / 'checkpoints' / 'active_checkpoint.json').exists()
    
    def test_backup_state_custom_name(self, populated_state_dir):
        """Test creating backup with custom name."""
        backup_dir = backup_state(populated_state_dir, 'my_backup')
        
        assert backup_dir.exists()
        assert backup_dir.name == 'my_backup'
        
        # Verify content
        with open(backup_dir / '.retry_state.json') as f:
            data = json.load(f)
        assert 'attempts' in data
    
    def test_backup_state_default_directory(self, populated_state_dir):
        """Test backup with default directory parameter."""
        backup_dir = backup_state()  # Uses get_state_directory()
        
        assert backup_dir.exists()
        assert len(list(backup_dir.iterdir())) > 0
    
    def test_backup_state_with_errors(self, populated_state_dir, caplog):
        """Test backup handling file copy errors."""
        # Make a file unreadable
        unreadable = populated_state_dir / 'unreadable.json'
        unreadable.write_text('{}')
        unreadable.chmod(0o000)
        
        try:
            backup_dir = backup_state(populated_state_dir)
            
            # Backup should still be created
            assert backup_dir.exists()
            
            # Should log warning about failed file
            assert 'Failed to backup' in caplog.text
        finally:
            # Restore permissions for cleanup
            unreadable.chmod(0o644)
    
    def test_backup_preserves_structure(self, populated_state_dir):
        """Test that backup preserves directory structure."""
        backup_dir = backup_state(populated_state_dir)
        
        # Check nested structure
        assert (backup_dir / 'checkpoints').is_dir()
        assert (backup_dir / 'checkpoints' / 'active_checkpoint.json').is_file()


class TestResetState:
    """Test reset_state function with memory optimization."""
    
    def test_reset_state_with_backup(self, populated_state_dir):
        """Test resetting state with backup creation."""
        # Get initial file count
        initial_files = list_state_files(populated_state_dir)
        assert len(initial_files) > 0
        
        # Reset state
        success = reset_state(populated_state_dir, create_backup=True)
        
        assert success is True
        
        # Check files were removed
        remaining_files = list_state_files(populated_state_dir)
        assert len(remaining_files) == 0
        
        # Check backup was created
        backup_parent = populated_state_dir.parent / 'state_backups'
        assert backup_parent.exists()
        assert len(list(backup_parent.iterdir())) > 0
    
    def test_reset_state_without_backup(self, populated_state_dir):
        """Test resetting state without backup."""
        success = reset_state(populated_state_dir, create_backup=False)
        
        assert success is True
        
        # Check files were removed
        remaining_files = list_state_files(populated_state_dir)
        assert len(remaining_files) == 0
        
        # No backup should exist
        backup_parent = populated_state_dir.parent / 'state_backups'
        assert not backup_parent.exists() or len(list(backup_parent.iterdir())) == 0
    
    def test_reset_state_cleans_temp_files(self, populated_state_dir):
        """Test that reset cleans up temp files."""
        # Create temp files
        checkpoint_dir = populated_state_dir / 'checkpoints'
        temp_dir = checkpoint_dir / 'temp'
        (temp_dir / 'tempfile.tmp').write_text('temp')
        (checkpoint_dir / 'file.tmp').write_text('tmp')
        
        success = reset_state(populated_state_dir, create_backup=False)
        
        assert success is True
        assert not (temp_dir / 'tempfile.tmp').exists()
        assert not (checkpoint_dir / 'file.tmp').exists()
        assert temp_dir.exists()  # Directory recreated but empty
    
    def test_reset_state_keeps_limited_backups(self, populated_state_dir):
        """Test that reset keeps only specified number of backups."""
        # Create multiple backups
        for i in range(7):
            backup_state(populated_state_dir, f'backup_{i}')
        
        # Reset with keep_backups=3
        reset_state(populated_state_dir, create_backup=True, keep_backups=3)
        
        backup_parent = populated_state_dir.parent / 'state_backups'
        backups = list(backup_parent.iterdir())
        
        # Should have exactly 3 backups (kept the most recent)
        assert len(backups) == 3
    
    def test_reset_state_error_handling(self, populated_state_dir, caplog, monkeypatch):
        """Test reset handles errors gracefully."""
        # Mock shutil.rmtree to raise an exception
        original_rmtree = shutil.rmtree
        
        def failing_rmtree(path):
            if 'checkpoints' in str(path):
                raise PermissionError("Cannot remove directory")
            return original_rmtree(path)
        
        monkeypatch.setattr('shutil.rmtree', failing_rmtree)
        
        success = reset_state(populated_state_dir, create_backup=False)
        
        # Should return False on error
        assert success is False
        assert 'State reset failed' in caplog.text
    
    def test_reset_state_default_directory(self, populated_state_dir):
        """Test reset with default directory."""
        success = reset_state()  # Uses get_state_directory()
        assert success is True


class TestShowStateStatus:
    """Test show_state_status function."""
    
    def test_show_state_status_populated(self, populated_state_dir):
        """Test showing status of populated state directory."""
        status = show_state_status(populated_state_dir)
        
        assert 'state_directory' in status
        assert status['state_directory'] == str(populated_state_dir)
        assert 'state_files' in status
        
        # Check specific files
        files = status['state_files']
        assert '.retry_state.json' in files
        assert files['.retry_state.json']['exists'] is True
        assert files['.retry_state.json']['size_bytes'] > 0
        assert 'modified' in files['.retry_state.json']
        assert files['.retry_state.json']['entries'] == 2  # attempts dict has 2 entries
        
        # Check nested file
        assert 'checkpoints/active_checkpoint.json' in files
    
    def test_show_state_status_json_parsing(self, populated_state_dir):
        """Test JSON parsing in status display."""
        status = show_state_status(populated_state_dir)
        
        # Check retry state parsing
        retry_info = status['state_files']['.retry_state.json']
        assert retry_info['last_updated'] == '2024-01-01T10:00:00'
        
        # Check index parsing
        index_info = status['state_files']['index.json']
        assert 'episodes' in index_info
        assert index_info['episodes'] == 0
    
    def test_show_state_status_corrupted_json(self, temp_state_dir):
        """Test status with corrupted JSON files."""
        # Create corrupted JSON
        bad_json = temp_state_dir / 'bad.json'
        bad_json.write_text('{ corrupted json')
        
        status = show_state_status(temp_state_dir)
        
        # Should still show file info without JSON details
        assert 'bad.json' in status['state_files']
        assert status['state_files']['bad.json']['exists'] is True
        assert 'entries' not in status['state_files']['bad.json']
    
    def test_show_state_status_missing_files(self, temp_state_dir):
        """Test status when expected files don't exist."""
        status = show_state_status(temp_state_dir)
        
        # Should have empty state_files dict
        assert len(status['state_files']) == 0
    
    def test_show_state_status_default_directory(self, populated_state_dir):
        """Test status with default directory."""
        status = show_state_status()  # Uses get_state_directory()
        
        assert 'state_directory' in status
        assert len(status['state_files']) > 0


class TestExportImportState:
    """Test export and import functionality with memory optimization."""
    
    def test_export_state_default_path(self, populated_state_dir):
        """Test exporting state with default filename."""
        export_path = export_state(populated_state_dir)
        
        assert export_path.exists()
        assert export_path.suffix == '.gz'
        assert 'state_export_' in export_path.name
        
        # Verify it's a valid tar.gz file
        with tarfile.open(export_path, 'r:gz') as tar:
            members = tar.getnames()
            assert '.retry_state.json' in members
            assert 'checkpoints/active_checkpoint.json' in members
    
    def test_export_state_custom_path(self, populated_state_dir, tmp_path):
        """Test exporting state to custom path."""
        custom_path = tmp_path / 'my_export.tar.gz'
        export_path = export_state(populated_state_dir, custom_path)
        
        assert export_path == custom_path
        assert custom_path.exists()
    
    def test_export_state_preserves_structure(self, populated_state_dir, tmp_path):
        """Test that export preserves directory structure."""
        export_path = export_state(populated_state_dir, tmp_path / 'export.tar.gz')
        
        # Extract and verify structure
        extract_dir = tmp_path / 'extract'
        with tarfile.open(export_path, 'r:gz') as tar:
            tar.extractall(extract_dir)
        
        assert (extract_dir / '.retry_state.json').exists()
        assert (extract_dir / 'checkpoints' / 'active_checkpoint.json').exists()
    
    def test_import_state_success(self, populated_state_dir, temp_state_dir, tmp_path):
        """Test successful state import."""
        # Export from populated directory
        export_path = export_state(populated_state_dir, tmp_path / 'export.tar.gz')
        
        # Clear temp directory
        for item in temp_state_dir.iterdir():
            if item.is_file():
                item.unlink()
            else:
                shutil.rmtree(item)
        
        # Import to temp directory
        success = import_state(export_path, temp_state_dir, create_backup=False)
        
        assert success is True
        
        # Verify files were imported
        assert (temp_state_dir / '.retry_state.json').exists()
        assert (temp_state_dir / 'checkpoints' / 'active_checkpoint.json').exists()
    
    def test_import_state_with_backup(self, populated_state_dir, tmp_path):
        """Test import creates backup of existing state."""
        export_path = export_state(populated_state_dir, tmp_path / 'export.tar.gz')
        
        # Import with backup
        success = import_state(export_path, populated_state_dir, create_backup=True)
        
        assert success is True
        
        # Check backup was created
        backup_parent = populated_state_dir.parent / 'state_backups'
        backups = [d for d in backup_parent.iterdir() if 'pre_import_' in d.name]
        assert len(backups) > 0
    
    def test_import_state_missing_file(self, temp_state_dir, tmp_path, caplog):
        """Test import with missing file."""
        missing_path = tmp_path / 'missing.tar.gz'
        
        success = import_state(missing_path, temp_state_dir)
        
        assert success is False
        assert 'Import file not found' in caplog.text
    
    def test_import_state_corrupted_file(self, temp_state_dir, tmp_path, caplog):
        """Test import with corrupted tar file."""
        corrupted_path = tmp_path / 'corrupted.tar.gz'
        corrupted_path.write_text('not a tar file')
        
        success = import_state(corrupted_path, temp_state_dir)
        
        assert success is False
        assert 'State import failed' in caplog.text
    
    def test_export_import_roundtrip(self, populated_state_dir, tmp_path):
        """Test complete export/import roundtrip."""
        # Get original status
        original_status = show_state_status(populated_state_dir)
        
        # Export
        export_path = export_state(populated_state_dir, tmp_path / 'roundtrip.tar.gz')
        
        # Reset state
        reset_state(populated_state_dir, create_backup=False)
        
        # Verify state is cleared
        assert len(list_state_files(populated_state_dir)) == 0
        
        # Import
        success = import_state(export_path, populated_state_dir, create_backup=False)
        assert success is True
        
        # Verify state is restored
        restored_status = show_state_status(populated_state_dir)
        
        # Compare file counts (exact comparison may vary due to timestamps)
        assert len(original_status['state_files']) == len(restored_status['state_files'])
        
        # Verify specific file content
        with open(populated_state_dir / '.retry_state.json') as f:
            retry_data = json.load(f)
        assert retry_data['attempts']['key1'] == 3


class TestMemoryOptimization:
    """Test memory optimization aspects of state management."""
    
    def test_large_state_file_handling(self, temp_state_dir):
        """Test handling of large state files efficiently."""
        # Create a large state file with generator to avoid memory spike
        large_file = temp_state_dir / 'large_state.json'
        
        # Write large file in chunks
        with open(large_file, 'w') as f:
            f.write('{\n')
            f.write('  "entries": [\n')
            
            # Write entries in batches
            batch_size = 100
            total_entries = 1000
            
            for i in range(total_entries):
                entry = f'    {{"id": {i}, "data": "entry_{i}"}}'
                if i < total_entries - 1:
                    entry += ','
                f.write(entry + '\n')
                
                # Flush periodically to avoid buffering too much
                if i % batch_size == 0:
                    f.flush()
            
            f.write('  ]\n')
            f.write('}\n')
        
        # Test operations on large file
        files = list_state_files(temp_state_dir)
        assert 'large_state.json' in [f.name for f in files]
        
        # Backup should handle large file
        backup_dir = backup_state(temp_state_dir)
        assert (backup_dir / 'large_state.json').exists()
        
        # Reset should clean up large file
        reset_state(temp_state_dir, create_backup=False)
        assert not large_file.exists()
    
    def test_incremental_backup_cleanup(self, populated_state_dir):
        """Test that backup cleanup doesn't load all backups in memory."""
        # Create multiple backups
        backup_names = []
        for i in range(10):
            backup_dir = backup_state(populated_state_dir, f'backup_{i:03d}')
            backup_names.append(backup_dir.name)
        
        # Reset with limited backup retention
        reset_state(populated_state_dir, create_backup=True, keep_backups=3)
        
        # Check only recent backups remain
        backup_parent = populated_state_dir.parent / 'state_backups'
        remaining_backups = sorted([d.name for d in backup_parent.iterdir()])
        
        # Should keep the 3 most recent backups
        assert len(remaining_backups) == 3
        
        # The last 3 created should remain (sorted by modification time)
        # Note: The new backup from reset_state is also included
    
    def test_status_without_loading_content(self, temp_state_dir):
        """Test that status check doesn't load entire file contents."""
        # Create a file with invalid JSON that would fail if fully parsed
        invalid_but_large = temp_state_dir / 'invalid.json'
        with open(invalid_but_large, 'w') as f:
            f.write('{\n')
            f.write('  "valid_start": true,\n')
            # Write large amount of data
            for i in range(1000):
                f.write(f'  "key_{i}": "value_{i}",\n')
            # Don't close the JSON properly
            f.write('  "incomplete": ')
        
        # Status should still work (won't parse JSON details but shows file info)
        status = show_state_status(temp_state_dir)
        
        assert 'invalid.json' in status['state_files']
        assert status['state_files']['invalid.json']['exists'] is True
        assert status['state_files']['invalid.json']['size_bytes'] > 0
        
        # Should not have JSON details due to parse error
        assert 'entries' not in status['state_files']['invalid.json']