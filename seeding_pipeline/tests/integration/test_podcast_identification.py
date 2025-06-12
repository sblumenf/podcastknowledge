"""Test podcast identification from VTT files."""

import os
import shutil
from pathlib import Path
import tempfile
import pytest
from src.vtt import VTTParser
from src.seeding.transcript_ingestion import TranscriptIngestion, TranscriptIngestionManager
from src.core.config import PipelineConfig
from unittest.mock import Mock


class TestPodcastIdentification:
    """Test podcast ID extraction from VTT files."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def vtt_parser(self):
        """Create VTT parser instance."""
        return VTTParser()
    
    def test_extract_podcast_id_from_metadata(self, vtt_parser, temp_dir):
        """Test extracting podcast ID from VTT metadata."""
        # Create VTT with podcast metadata
        vtt_content = """WEBVTT

NOTE
podcast_id: tech_talk_show
episode: Episode 123
description: A great episode

00:00:00.000 --> 00:00:05.000
Hello and welcome to our show.

00:00:05.000 --> 00:00:10.000
Today we're discussing technology.
"""
        vtt_file = temp_dir / "test_episode.vtt"
        vtt_file.write_text(vtt_content)
        
        # Parse file with metadata
        result = vtt_parser.parse_file_with_metadata(vtt_file)
        
        assert 'metadata' in result
        assert result['metadata']['podcast_id'] == 'tech_talk_show'
        assert 'segments' in result
        assert len(result['segments']) == 2
    
    def test_extract_podcast_id_from_json_metadata(self, vtt_parser, temp_dir):
        """Test extracting podcast ID from JSON metadata block."""
        # Create VTT with JSON metadata
        vtt_content = """WEBVTT

NOTE JSON Metadata
{
  "podcast_id": "data_science_pod",
  "episode": "DS101",
  "date": "2024-01-15"
}

00:00:00.000 --> 00:00:05.000
Welcome to Data Science Podcast.
"""
        vtt_file = temp_dir / "data_science.vtt"
        vtt_file.write_text(vtt_content)
        
        # Parse file with metadata
        result = vtt_parser.parse_file_with_metadata(vtt_file)
        
        assert result['metadata']['podcast_id'] == 'data_science_pod'
        assert result['metadata']['episode'] == 'DS101'
        assert result['metadata']['date'] == '2024-01-15'
    
    def test_extract_podcast_id_from_path(self, vtt_parser, temp_dir):
        """Test extracting podcast ID from file path."""
        # Create VTT in podcast-specific directory
        podcast_dir = temp_dir / "podcasts" / "my_awesome_podcast" / "transcripts"
        podcast_dir.mkdir(parents=True)
        
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
No metadata in this file.
"""
        vtt_file = podcast_dir / "episode_001.vtt"
        vtt_file.write_text(vtt_content)
        
        # Parse file with metadata
        result = vtt_parser.parse_file_with_metadata(vtt_file)
        
        # Should extract from path
        assert result['metadata']['podcast_id'] == 'my_awesome_podcast'
    
    def test_podcast_id_normalization(self, vtt_parser, temp_dir):
        """Test that podcast IDs are normalized correctly."""
        # Create VTT with special characters in podcast name
        vtt_content = """WEBVTT

NOTE
podcast: My Awesome Podcast! (2024)

00:00:00.000 --> 00:00:05.000
Testing normalization.
"""
        vtt_file = temp_dir / "test.vtt"
        vtt_file.write_text(vtt_content)
        
        # Parse file with metadata
        result = vtt_parser.parse_file_with_metadata(vtt_file)
        
        # Should normalize special characters
        assert result['metadata']['podcast_id'] == 'my_awesome_podcast___2024_'
    
    def test_multi_podcast_processing(self, temp_dir):
        """Test processing files in multi-podcast mode."""
        # Set up multi-podcast mode
        os.environ['PODCAST_MODE'] = 'multi'
        os.environ['PODCAST_DATA_DIR'] = str(temp_dir)
        
        # Create test VTT files for different podcasts
        podcasts = {
            'tech_show': 'Tech Talk Episode 1',
            'science_pod': 'Science Hour Episode 1'
        }
        
        for podcast_id, title in podcasts.items():
            vtt_content = f"""WEBVTT

NOTE
podcast_id: {podcast_id}
episode: {title}

00:00:00.000 --> 00:00:05.000
Content for {podcast_id}.
"""
            vtt_file = temp_dir / f"{podcast_id}_ep1.vtt"
            vtt_file.write_text(vtt_content)
        
        # Create mock pipeline and checkpoint
        mock_pipeline = Mock()
        mock_pipeline.config = PipelineConfig()
        mock_checkpoint = Mock()
        
        # Create ingestion manager
        manager = TranscriptIngestionManager(mock_pipeline, mock_checkpoint)
        
        # Process files
        for podcast_id in podcasts:
            vtt_file = temp_dir / f"{podcast_id}_ep1.vtt"
            result = manager.process_vtt_file(str(vtt_file))
            
            if result['success']:
                # Verify podcast-specific directory was created
                podcast_dir = temp_dir / 'podcasts' / podcast_id
                assert podcast_dir.exists()
                
                # Verify file was moved to podcast-specific processed directory
                processed_dir = podcast_dir / 'processed'
                assert processed_dir.exists()
        
        # Clean up
        del os.environ['PODCAST_MODE']
    
    def test_fallback_podcast_id(self, vtt_parser, temp_dir):
        """Test fallback when no podcast ID can be determined."""
        # Create VTT with no identifying information
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
No metadata here.
"""
        vtt_file = temp_dir / "anonymous.vtt"
        vtt_file.write_text(vtt_content)
        
        # Parse file with metadata
        result = vtt_parser.parse_file_with_metadata(vtt_file)
        
        # Should use fallback
        assert result['metadata']['podcast_id'] == 'unknown_podcast'