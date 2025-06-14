"""Integration tests for the data flow between transcriber and seeding pipeline."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import patch
import pytest

from src.cli.cli import process_vtt
from src.core.config import PipelineConfig


@pytest.fixture
def temp_data_dir() -> Generator[Path, None, None]:
    """Create temporary data directory structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        
        # Create directory structure
        transcripts_dir = base_path / "transcripts"
        processed_dir = base_path / "processed"
        logs_dir = base_path / "logs"
        
        transcripts_dir.mkdir(parents=True)
        processed_dir.mkdir(parents=True)
        logs_dir.mkdir(parents=True)
        
        yield base_path
        

@pytest.fixture
def sample_vtt_files(temp_data_dir: Path) -> list[Path]:
    """Copy sample VTT files to test transcripts directory."""
    transcripts_dir = temp_data_dir / "transcripts"
    
    # Create a test podcast subdirectory
    podcast_dir = transcripts_dir / "test_podcast"
    podcast_dir.mkdir()
    
    # Get sample VTT files from fixtures
    fixtures_dir = Path(__file__).parent.parent / "fixtures" / "vtt_samples"
    sample_files = ["minimal.vtt", "standard.vtt", "complex.vtt"]
    
    copied_files = []
    for filename in sample_files:
        src_path = fixtures_dir / filename
        if src_path.exists():
            dst_path = podcast_dir / filename
            shutil.copy2(src_path, dst_path)
            copied_files.append(dst_path)
    
    # Also create a VTT file in root transcripts directory
    root_vtt = transcripts_dir / "root_test.vtt"
    if (fixtures_dir / "minimal.vtt").exists():
        shutil.copy2(fixtures_dir / "minimal.vtt", root_vtt)
        copied_files.append(root_vtt)
    
    return copied_files


@pytest.fixture
def mock_environment(temp_data_dir: Path, monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("VTT_INPUT_DIR", str(temp_data_dir / "transcripts"))
    monkeypatch.setenv("PROCESSED_DIR", str(temp_data_dir / "processed"))
    monkeypatch.setenv("PODCAST_DATA_DIR", str(temp_data_dir))
    

class TestDataFlow:
    """Test the complete data flow from transcripts to processed directory."""
    
    def test_vtt_files_discovered(self, temp_data_dir: Path, sample_vtt_files: list[Path], mock_environment):
        """Test that VTT files are discovered in the transcripts directory."""
        from src.cli.cli import find_vtt_files
        
        transcripts_dir = temp_data_dir / "transcripts"
        vtt_files = find_vtt_files(transcripts_dir, "*.vtt", recursive=True)
        
        assert len(vtt_files) == 4  # 3 in podcast dir + 1 in root
        assert all(f.suffix == ".vtt" for f in vtt_files)
        assert all(f.exists() for f in vtt_files)
        
    def test_files_moved_after_processing(self, temp_data_dir: Path, sample_vtt_files: list[Path], mock_environment):
        """Test that files are moved to processed directory after successful processing."""
        # Create mock args for CLI
        class Args:
            folder = str(temp_data_dir / "transcripts")
            pattern = "*.vtt"
            recursive = True
            dry_run = False
            skip_errors = True
            no_checkpoint = False
            checkpoint_dir = str(temp_data_dir / "checkpoints")
            parallel = False
            workers = 1
            config = None
            verbose = False
            
        args = Args()
        
        # Mock the pipeline processing to always succeed
        with patch('src.pipeline.enhanced_knowledge_pipeline.EnhancedKnowledgePipeline') as mock_pipeline:
            # Mock successful processing
            mock_instance = mock_pipeline.return_value
            mock_instance.process_vtt_file.return_value = {
                'status': 'success',
                'segments': [],
                'segment_count': 10,
                'episode': {}
            }
            
            with patch('src.seeding.transcript_ingestion.TranscriptIngestion.process_vtt_file') as mock_process:
                mock_process.return_value = {
                    'status': 'success',
                    'segment_count': 10,
                    'segments': [],
                    'episode': {}
                }
                
                # Process VTT files
                exit_code = process_vtt(args)
                
                # Check that files were moved
                processed_dir = temp_data_dir / "processed"
                processed_files = list(processed_dir.rglob("*.vtt"))
                
                # All 4 files should be in processed directory
                assert len(processed_files) == 4
                
                # Original files should not exist
                transcripts_dir = temp_data_dir / "transcripts"
                remaining_files = list(transcripts_dir.rglob("*.vtt"))
                assert len(remaining_files) == 0
                
                # Directory structure should be maintained
                assert (processed_dir / "test_podcast").exists()
                assert (processed_dir / "test_podcast" / "minimal.vtt").exists()
                
    def test_duplicate_processing_prevention(self, temp_data_dir: Path, sample_vtt_files: list[Path], mock_environment):
        """Test that already processed files are not reprocessed."""
        processed_dir = temp_data_dir / "processed"
        
        # Manually move one file to processed directory
        src_file = sample_vtt_files[0]
        relative_path = src_file.relative_to(temp_data_dir / "transcripts")
        dst_file = processed_dir / relative_path
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_file), str(dst_file))
        
        # Now process - should skip the already processed file
        from src.seeding.transcript_ingestion import TranscriptIngestionManager
        from unittest.mock import Mock
        
        mock_pipeline = Mock()
        mock_checkpoint = Mock()
        
        manager = TranscriptIngestionManager(mock_pipeline, mock_checkpoint)
        
        # Try to process the moved file (using original path)
        result = manager.process_vtt_file(str(src_file))
        
        assert result['success'] is False
        assert result.get('skipped') is True
        assert 'already processed' in result.get('error', '').lower()
        
    def test_error_handling_file_not_moved(self, temp_data_dir: Path, sample_vtt_files: list[Path], mock_environment):
        """Test that processing continues even if file move fails."""
        # Make processed directory read-only to cause move failure
        processed_dir = temp_data_dir / "processed"
        
        # Create mock args for CLI
        class Args:
            folder = str(temp_data_dir / "transcripts")
            pattern = "minimal.vtt"  # Process just one file
            recursive = True
            dry_run = False
            skip_errors = True
            no_checkpoint = False
            checkpoint_dir = str(temp_data_dir / "checkpoints")
            parallel = False
            workers = 1
            config = None
            verbose = False
            
        args = Args()
        
        # Mock successful processing but failed move
        with patch('src.pipeline.enhanced_knowledge_pipeline.EnhancedKnowledgePipeline') as mock_pipeline:
            mock_instance = mock_pipeline.return_value
            
            with patch('src.seeding.transcript_ingestion.TranscriptIngestion.process_vtt_file') as mock_process:
                mock_process.return_value = {
                    'status': 'success',
                    'segment_count': 10,
                    'segments': [],
                    'episode': {}
                }
                
                with patch('shutil.move', side_effect=PermissionError("Cannot move file")):
                    # Process should succeed despite move failure
                    exit_code = process_vtt(args)
                    
                    # Original file should still exist
                    transcripts_dir = temp_data_dir / "transcripts"
                    remaining_files = list(transcripts_dir.rglob("minimal.vtt"))
                    assert len(remaining_files) == 1


class TestErrorHandling:
    """Test error handling in the data flow."""
    
    def test_malformed_vtt_file(self, temp_data_dir: Path, mock_environment):
        """Test handling of malformed VTT files."""
        transcripts_dir = temp_data_dir / "transcripts"
        
        # Create a malformed VTT file
        malformed_vtt = transcripts_dir / "malformed.vtt"
        malformed_vtt.write_text("This is not a valid VTT file\nNo WEBVTT header")
        
        # Create mock args
        class Args:
            folder = str(transcripts_dir)
            pattern = "malformed.vtt"
            recursive = False
            dry_run = False
            skip_errors = True
            no_checkpoint = False
            checkpoint_dir = str(temp_data_dir / "checkpoints")
            parallel = False
            workers = 1
            config = None
            verbose = False
            
        args = Args()
        
        # Process should handle the error gracefully
        exit_code = process_vtt(args)
        
        # File should not be moved to processed
        processed_dir = temp_data_dir / "processed"
        processed_files = list(processed_dir.rglob("*.vtt"))
        assert len(processed_files) == 0
        
        # Original file should still exist
        assert malformed_vtt.exists()
        
    def test_neo4j_connection_failure(self, temp_data_dir: Path, sample_vtt_files: list[Path], mock_environment):
        """Test handling of Neo4j connection failures."""
        from src.seeding.transcript_ingestion import TranscriptIngestionManager
        from unittest.mock import Mock
        from neo4j.exceptions import ServiceUnavailable
        
        mock_pipeline = Mock()
        mock_checkpoint = Mock()
        
        # Mock Neo4j connection failure
        mock_pipeline.storage_coordinator.store_episode.side_effect = ServiceUnavailable("Neo4j unavailable")
        
        manager = TranscriptIngestionManager(mock_pipeline, mock_checkpoint)
        
        # Should handle Neo4j errors gracefully
        with patch('src.seeding.transcript_ingestion.TranscriptIngestion.process_vtt_file') as mock_process:
            mock_process.side_effect = ServiceUnavailable("Neo4j unavailable")
            
            result = manager.process_vtt_file(str(sample_vtt_files[0]))
            
            assert result['success'] is False
            assert 'Neo4j' in result.get('error', '')
            
    def test_file_permission_errors(self, temp_data_dir: Path, sample_vtt_files: list[Path], mock_environment):
        """Test handling of file permission errors."""
        import stat
        
        # Make one file read-only
        test_file = sample_vtt_files[0]
        os.chmod(test_file, stat.S_IRUSR)  # Read-only for owner
        
        from src.seeding.transcript_ingestion import TranscriptIngestionManager
        from unittest.mock import Mock
        
        mock_pipeline = Mock()
        mock_checkpoint = Mock()
        
        manager = TranscriptIngestionManager(mock_pipeline, mock_checkpoint)
        
        # Should handle permission errors gracefully
        with patch('src.seeding.transcript_ingestion.TranscriptIngestion._create_vtt_file') as mock_create:
            mock_create.side_effect = PermissionError("Permission denied")
            
            result = manager.process_vtt_file(str(test_file))
            
            assert result['success'] is False
            assert 'Permission' in result.get('error', '')
            
        # Restore permissions for cleanup
        os.chmod(test_file, stat.S_IRUSR | stat.S_IWUSR)
        
    def test_recovery_from_partial_processing(self, temp_data_dir: Path, sample_vtt_files: list[Path], mock_environment):
        """Test recovery when processing is interrupted."""
        # Create a checkpoint that indicates partial processing
        checkpoint_dir = temp_data_dir / "checkpoints"
        checkpoint_dir.mkdir(exist_ok=True)
        
        vtt_checkpoint = checkpoint_dir / "vtt_processed.json"
        
        # Mark one file as processed in checkpoint
        checkpoint_data = {
            str(sample_vtt_files[0]): {
                "hash": "fake_hash",
                "processed_at": "2024-01-01T00:00:00",
                "segments": 10,
                "moved_to_processed": False
            }
        }
        
        import json
        vtt_checkpoint.write_text(json.dumps(checkpoint_data, indent=2))
        
        # Create mock args
        class Args:
            folder = str(temp_data_dir / "transcripts")
            pattern = "*.vtt"
            recursive = True
            dry_run = False
            skip_errors = True
            no_checkpoint = False
            checkpoint_dir = str(checkpoint_dir)
            parallel = False
            workers = 1
            config = None
            verbose = False
            
        args = Args()
        
        # Mock the pipeline
        with patch('src.pipeline.enhanced_knowledge_pipeline.EnhancedKnowledgePipeline') as mock_pipeline:
            mock_instance = mock_pipeline.return_value
            
            with patch('src.seeding.transcript_ingestion.TranscriptIngestion.process_vtt_file') as mock_process:
                mock_process.return_value = {
                    'status': 'success',
                    'segment_count': 10,
                    'segments': [],
                    'episode': {}
                }
                
                # Process should skip the checkpointed file
                exit_code = process_vtt(args)
                
                # Should process only the non-checkpointed files
                processed_dir = temp_data_dir / "processed"
                processed_files = list(processed_dir.rglob("*.vtt"))
                
                # 3 files should be processed (4 total - 1 checkpointed)
                assert len(processed_files) == 3


@pytest.mark.neo4j
class TestNeo4jIntegration:
    """Test Neo4j integration with data flow."""
    
    def test_neo4j_nodes_created(self, temp_data_dir: Path, sample_vtt_files: list[Path], mock_environment, neo4j_service):
        """Test that Neo4j nodes are created for processed files."""
        # This test requires Neo4j to be running
        # It would verify that Episode and Segment nodes are created
        # Skip for now as it requires full Neo4j setup
        pytest.skip("Requires Neo4j service running")