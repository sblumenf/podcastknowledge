"""Comprehensive unit tests for transcript ingestion module."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
import hashlib
import json

import pytest

from src.seeding.transcript_ingestion import (
    VTTFile, TranscriptIngestion
)
from src.core.config import PipelineConfig
from src.core.exceptions import ValidationError
from src.core.interfaces import TranscriptSegment
from src.vtt import VTTParser


class TestVTTFile:
    """Test VTTFile dataclass."""
    
    def test_vtt_file_creation(self):
        """Test creating VTTFile instance."""
        path = Path("/test/file.vtt")
        created_at = datetime.now()
        metadata = {"key": "value"}
        
        vtt_file = VTTFile(
            path=path,
            podcast_name="Test Podcast",
            episode_title="Episode 1",
            file_hash="abc123",
            size_bytes=1024,
            created_at=created_at,
            metadata=metadata
        )
        
        assert vtt_file.path == path
        assert vtt_file.podcast_name == "Test Podcast"
        assert vtt_file.episode_title == "Episode 1"
        assert vtt_file.file_hash == "abc123"
        assert vtt_file.size_bytes == 1024
        assert vtt_file.created_at == created_at
        assert vtt_file.metadata == metadata
    
    def test_vtt_file_to_dict(self):
        """Test converting VTTFile to dictionary."""
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        
        vtt_file = VTTFile(
            path=Path("/test/file.vtt"),
            podcast_name="Test Podcast",
            episode_title="Episode 1",
            file_hash="abc123",
            size_bytes=1024,
            created_at=created_at,
            metadata={"key": "value"}
        )
        
        result = vtt_file.to_dict()
        
        assert result["path"] == "/test/file.vtt"
        assert result["podcast_name"] == "Test Podcast"
        assert result["episode_title"] == "Episode 1"
        assert result["file_hash"] == "abc123"
        assert result["size_bytes"] == 1024
        assert result["created_at"] == "2024-01-01T12:00:00"
        assert result["metadata"] == {"key": "value"}
    
    def test_vtt_file_defaults(self):
        """Test VTTFile with default values."""
        vtt_file = VTTFile(
            path=Path("/test/file.vtt"),
            podcast_name="Test",
            episode_title="Episode",
            file_hash="hash",
            size_bytes=100,
            created_at=datetime.now()
        )
        
        assert vtt_file.metadata is None


class TestTranscriptIngestion:
    """Test TranscriptIngestion functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test config."""
        config = Mock(spec=PipelineConfig)
        config.merge_short_segments = True
        config.min_segment_duration = 2.0
        return config
    
    @pytest.fixture
    def ingestion(self, config):
        """Create TranscriptIngestion instance."""
        return TranscriptIngestion(config)
    
    def test_initialization(self, ingestion, config):
        """Test TranscriptIngestion initialization."""
        assert ingestion.config == config
        assert hasattr(ingestion, 'vtt_parser')
        assert isinstance(ingestion._processed_files, set)
        assert len(ingestion._processed_files) == 0
    
    def test_scan_directory_not_found(self, ingestion):
        """Test scanning non-existent directory."""
        with pytest.raises(ValidationError, match="Directory not found"):
            ingestion.scan_directory(Path("/non/existent"))
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.rglob')
    def test_scan_directory_recursive(self, mock_rglob, mock_exists, ingestion):
        """Test scanning directory recursively."""
        mock_exists.return_value = True
        
        # Mock file paths
        mock_file1 = Mock(spec=Path)
        mock_file1.is_file.return_value = True
        mock_file1.stat.return_value.st_size = 1024
        mock_file1.stat.return_value.st_mtime = 1234567890
        
        mock_file2 = Mock(spec=Path)
        mock_file2.is_file.return_value = True
        mock_file2.stat.return_value.st_size = 2048
        mock_file2.stat.return_value.st_mtime = 1234567891
        
        mock_rglob.return_value = [mock_file1, mock_file2]
        
        # Mock _create_vtt_file to return valid objects
        with patch.object(ingestion, '_create_vtt_file') as mock_create:
            mock_create.side_effect = [
                VTTFile(mock_file1, "Podcast1", "Episode1", "hash1", 1024, datetime.now()),
                VTTFile(mock_file2, "Podcast2", "Episode2", "hash2", 2048, datetime.now())
            ]
            
            result = ingestion.scan_directory(Path("/test"), "*.vtt", True)
        
        assert len(result) == 2
        assert all(isinstance(f, VTTFile) for f in result)
        mock_rglob.assert_called_once_with("*.vtt")
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.glob')
    def test_scan_directory_non_recursive(self, mock_glob, mock_exists, ingestion):
        """Test scanning directory non-recursively."""
        mock_exists.return_value = True
        
        mock_file = Mock(spec=Path)
        mock_file.is_file.return_value = True
        mock_glob.return_value = [mock_file]
        
        with patch.object(ingestion, '_create_vtt_file', return_value=None):
            result = ingestion.scan_directory(Path("/test"), "*.vtt", False)
        
        assert len(result) == 0  # None filtered out
        mock_glob.assert_called_once_with("*.vtt")
    
    @patch('builtins.open', mock_open(read_data=b'test data'))
    def test_calculate_file_hash(self, ingestion):
        """Test file hash calculation."""
        result = ingestion._calculate_file_hash(Path("/test/file.vtt"))
        
        # Calculate expected hash
        expected = hashlib.sha256(b'test data').hexdigest()
        assert result == expected
    
    def test_infer_metadata_from_path(self, ingestion):
        """Test inferring metadata from file path."""
        path = Path("/podcasts/My-Podcast/Episode_001.vtt")
        
        podcast, episode = ingestion._infer_metadata_from_path(path)
        
        assert podcast == "My-Podcast"
        assert episode == "Episode 001"  # Underscores replaced with spaces
    
    def test_infer_metadata_from_path_complex(self, ingestion):
        """Test inferring metadata from complex path."""
        path = Path("/data/shows/tech-talk/2024-01-15-guest-interview.vtt")
        
        podcast, episode = ingestion._infer_metadata_from_path(path)
        
        assert podcast == "tech-talk"
        assert episode == "2024 01 15 guest interview"  # Hyphens replaced
    
    @patch('builtins.open', mock_open(read_data='{"podcast": {"name": "Test Show"}, "episode": {"title": "Ep 1"}}'))
    @patch('pathlib.Path.exists')
    def test_load_metadata_file_success(self, mock_exists, ingestion):
        """Test loading metadata file successfully."""
        mock_exists.return_value = True
        
        result = ingestion._load_metadata_file(Path("/test"))
        
        assert result == {"podcast": {"name": "Test Show"}, "episode": {"title": "Ep 1"}}
    
    @patch('pathlib.Path.exists')
    def test_load_metadata_file_not_found(self, mock_exists, ingestion):
        """Test loading metadata when file doesn't exist."""
        mock_exists.return_value = False
        
        result = ingestion._load_metadata_file(Path("/test"))
        
        assert result is None
    
    @patch('builtins.open', side_effect=json.JSONDecodeError("Invalid", "", 0))
    @patch('pathlib.Path.exists')
    def test_load_metadata_file_invalid_json(self, mock_exists, mock_file, ingestion):
        """Test loading invalid metadata file."""
        mock_exists.return_value = True
        
        result = ingestion._load_metadata_file(Path("/test"))
        
        assert result is None
    
    def test_create_vtt_file_success(self, ingestion):
        """Test creating VTTFile object successfully."""
        mock_path = Mock(spec=Path)
        mock_path.stat.return_value.st_size = 1024
        mock_path.stat.return_value.st_mtime = 1234567890
        mock_path.parent.name = "TestPodcast"
        mock_path.stem = "Episode1"
        
        with patch.object(ingestion, '_calculate_file_hash', return_value="hash123"):
            with patch.object(ingestion, '_load_metadata_file', return_value=None):
                result = ingestion._create_vtt_file(mock_path)
        
        assert isinstance(result, VTTFile)
        assert result.path == mock_path
        assert result.podcast_name == "TestPodcast"
        assert result.episode_title == "Episode1"
        assert result.file_hash == "hash123"
        assert result.size_bytes == 1024
    
    def test_create_vtt_file_with_metadata(self, ingestion):
        """Test creating VTTFile with metadata override."""
        mock_path = Mock(spec=Path)
        mock_path.stat.return_value.st_size = 1024
        mock_path.stat.return_value.st_mtime = 1234567890
        mock_path.parent.name = "OldName"
        mock_path.stem = "OldTitle"
        
        metadata = {
            "podcast": {"name": "NewPodcast"},
            "episode": {"title": "NewTitle"}
        }
        
        with patch.object(ingestion, '_calculate_file_hash', return_value="hash123"):
            with patch.object(ingestion, '_load_metadata_file', return_value=metadata):
                result = ingestion._create_vtt_file(mock_path)
        
        assert result.podcast_name == "NewPodcast"
        assert result.episode_title == "NewTitle"
        assert result.metadata == metadata
    
    def test_create_vtt_file_error(self, ingestion):
        """Test creating VTTFile with error."""
        mock_path = Mock(spec=Path)
        mock_path.stat.side_effect = OSError("File error")
        
        result = ingestion._create_vtt_file(mock_path)
        
        assert result is None
    
    def test_process_vtt_file_already_processed(self, ingestion):
        """Test processing already processed file."""
        vtt_file = VTTFile(
            Path("/test.vtt"),
            "Podcast",
            "Episode",
            "hash123",
            1024,
            datetime.now()
        )
        
        ingestion._processed_files.add("hash123")
        
        result = ingestion.process_vtt_file(vtt_file)
        
        assert result['status'] == 'skipped'
        assert result['reason'] == 'already_processed'
    
    @patch.object(VTTParser, 'parse_file')
    def test_process_vtt_file_success(self, mock_parse, ingestion):
        """Test successful VTT file processing."""
        vtt_file = VTTFile(
            Path("/test.vtt"),
            "Podcast",
            "Episode",
            "hash123",
            1024,
            datetime.now()
        )
        
        segments = [
            TranscriptSegment("seg_0", "Text 1", 0.0, 2.0, "Speaker1", 1.0),
            TranscriptSegment("seg_1", "Text 2", 2.0, 4.0, "Speaker2", 1.0)
        ]
        mock_parse.return_value = segments
        
        with patch.object(ingestion.vtt_parser, 'merge_short_segments', return_value=segments):
            result = ingestion.process_vtt_file(vtt_file)
        
        assert result['status'] == 'success'
        assert result['segment_count'] == 2
        assert 'episode' in result
        assert 'segments' in result
        assert "hash123" in ingestion._processed_files
    
    @patch.object(VTTParser, 'parse_file')
    def test_process_vtt_file_error(self, mock_parse, ingestion):
        """Test VTT file processing with error."""
        vtt_file = VTTFile(
            Path("/test.vtt"),
            "Podcast",
            "Episode",
            "hash123",
            1024,
            datetime.now()
        )
        
        mock_parse.side_effect = Exception("Parse error")
        
        result = ingestion.process_vtt_file(vtt_file)
        
        assert result['status'] == 'error'
        assert result['error'] == "Parse error"
        assert "hash123" not in ingestion._processed_files
    
    def test_create_episode_data(self, ingestion):
        """Test creating episode data."""
        vtt_file = VTTFile(
            Path("/test.vtt"),
            "Test Podcast",
            "Test Episode",
            "abcdef123456789",
            1024,
            datetime.now()
        )
        
        segments = [
            TranscriptSegment("seg_0", "Text 1", 0.0, 10.0, "Speaker1", 1.0),
            TranscriptSegment("seg_1", "Text 2", 10.0, 20.0, "Speaker2", 1.0),
            TranscriptSegment("seg_2", "Text 3", 20.0, 30.0, "Speaker1", 1.0)
        ]
        
        result = ingestion._create_episode_data(vtt_file, segments)
        
        assert result['id'] == "abcdef123456"  # First 12 chars
        assert result['title'] == "Test Episode"
        assert result['podcast_name'] == "Test Podcast"
        assert result['duration_seconds'] == 30.0
        assert result['speaker_count'] == 2
        assert set(result['speakers']) == {"Speaker1", "Speaker2"}
        assert result['segment_count'] == 3
        assert result['file_path'] == "/test.vtt"
        assert 'processed_at' in result
    
    def test_create_episode_data_empty_segments(self, ingestion):
        """Test creating episode data with no segments."""
        vtt_file = VTTFile(
            Path("/test.vtt"),
            "Test Podcast",
            "Test Episode",
            "abcdef123456789",
            1024,
            datetime.now()
        )
        
        result = ingestion._create_episode_data(vtt_file, [])
        
        assert result['duration_seconds'] == 0.0
        assert result['speaker_count'] == 0
        assert result['speakers'] == []
        assert result['segment_count'] == 0
    
    def test_process_directory(self, ingestion):
        """Test processing directory of VTT files."""
        vtt_files = [
            VTTFile(Path("/test1.vtt"), "P1", "E1", "hash1", 100, datetime.now()),
            VTTFile(Path("/test2.vtt"), "P1", "E2", "hash2", 200, datetime.now()),
            VTTFile(Path("/test3.vtt"), "P2", "E1", "hash3", 300, datetime.now())
        ]
        
        with patch.object(ingestion, 'scan_directory', return_value=vtt_files):
            with patch.object(ingestion, 'process_vtt_file') as mock_process:
                mock_process.side_effect = [
                    {'status': 'success', 'segment_count': 10},
                    {'status': 'skipped', 'reason': 'already_processed'},
                    {'status': 'error', 'error': 'Parse error'}
                ]
                
                result = ingestion.process_directory(Path("/test"))
        
        assert result['total_files'] == 3
        assert result['processed'] == 1
        assert result['skipped'] == 1
        assert result['errors'] == 1
        assert result['total_segments'] == 10
        assert len(result['files']) == 3
    
    def test_process_directory_with_max_files(self, ingestion):
        """Test processing directory with file limit."""
        vtt_files = [
            VTTFile(Path(f"/test{i}.vtt"), "P", f"E{i}", f"hash{i}", 100, datetime.now())
            for i in range(10)
        ]
        
        with patch.object(ingestion, 'scan_directory', return_value=vtt_files):
            with patch.object(ingestion, 'process_vtt_file') as mock_process:
                mock_process.return_value = {'status': 'success', 'segment_count': 5}
                
                result = ingestion.process_directory(Path("/test"), max_files=3)
        
        assert mock_process.call_count == 3
        assert result['total_files'] == 3
        assert result['processed'] == 3
    
    def test_group_by_podcast(self, ingestion):
        """Test grouping VTT files by podcast."""
        vtt_files = [
            VTTFile(Path("/test1.vtt"), "Podcast1", "E1", "hash1", 100, datetime.now()),
            VTTFile(Path("/test2.vtt"), "Podcast1", "E2", "hash2", 200, datetime.now()),
            VTTFile(Path("/test3.vtt"), "Podcast2", "E1", "hash3", 300, datetime.now()),
            VTTFile(Path("/test4.vtt"), "Podcast2", "E2", "hash4", 400, datetime.now()),
            VTTFile(Path("/test5.vtt"), "Podcast1", "E3", "hash5", 500, datetime.now())
        ]
        
        result = ingestion.group_by_podcast(vtt_files)
        
        assert len(result) == 2
        assert len(result["Podcast1"]) == 3
        assert len(result["Podcast2"]) == 2
        assert all(f.podcast_name == "Podcast1" for f in result["Podcast1"])
        assert all(f.podcast_name == "Podcast2" for f in result["Podcast2"])
    
    @patch('builtins.open', mock_open(read_data='WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nTest'))
    def test_validate_vtt_file_valid(self, ingestion):
        """Test validating valid VTT file."""
        result = ingestion.validate_vtt_file(Path("/test.vtt"))
        assert result is True
    
    @patch('builtins.open', mock_open(read_data='NOT A VTT FILE'))
    def test_validate_vtt_file_invalid(self, ingestion):
        """Test validating invalid VTT file."""
        result = ingestion.validate_vtt_file(Path("/test.vtt"))
        assert result is False
    
    @patch('builtins.open', side_effect=IOError("Cannot read"))
    def test_validate_vtt_file_error(self, mock_file, ingestion):
        """Test validating VTT file with read error."""
        result = ingestion.validate_vtt_file(Path("/test.vtt"))
        assert result is False
    
    def test_process_file(self, ingestion):
        """Test processing single file by path."""
        with patch.object(ingestion, '_create_vtt_file') as mock_create:
            with patch.object(ingestion, 'process_vtt_file') as mock_process:
                mock_vtt = Mock(spec=VTTFile)
                mock_create.return_value = mock_vtt
                mock_process.return_value = {'status': 'success'}
                
                result = ingestion.process_file("/test.vtt")
        
        assert result == {'status': 'success'}
        mock_create.assert_called_once()
        mock_process.assert_called_once_with(mock_vtt)
    
    def test_process_file_create_error(self, ingestion):
        """Test processing file when creation fails."""
        with patch.object(ingestion, '_create_vtt_file', return_value=None):
            result = ingestion.process_file("/test.vtt")
        
        assert result['status'] == 'error'
        assert 'Failed to create VTTFile' in result['error']
    
    def test_compute_file_hash(self, ingestion):
        """Test compute_file_hash alias."""
        with patch.object(ingestion, '_calculate_file_hash', return_value="hash123"):
            result = ingestion._compute_file_hash("/test.vtt")
        
        assert result == "hash123"

