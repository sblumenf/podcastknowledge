"""Comprehensive tests for metadata indexing system with memory optimization."""

import json
import csv
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, mock_open
import pytest

from src.metadata_index import MetadataIndex, SearchResult, get_metadata_index
from src.file_organizer import EpisodeMetadata


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory for testing."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    yield data_dir
    # Cleanup happens automatically with tmp_path


@pytest.fixture
def sample_episodes():
    """Create small sample episodes for testing."""
    episodes = [
        EpisodeMetadata(
            title="Episode 1: Introduction",
            podcast_name="Tech Talk",
            publication_date="2024-01-01",
            file_path="tech_talk/2024-01-01_episode_1.vtt",
            speakers=["Alice", "Bob"],
            duration=1800.5,
            episode_number=1,
            description="An introduction to our tech podcast",
            processed_date="2024-01-02T10:00:00"
        ),
        EpisodeMetadata(
            title="Episode 2: Python Basics",
            podcast_name="Tech Talk",
            publication_date="2024-01-08",
            file_path="tech_talk/2024-01-08_episode_2.vtt",
            speakers=["Alice", "Charlie"],
            duration=2100.0,
            episode_number=2,
            description="Learn the basics of Python programming",
            processed_date="2024-01-09T10:00:00"
        ),
        EpisodeMetadata(
            title="Data Science Overview",
            podcast_name="Science Hour",
            publication_date="2024-01-05",
            file_path="science_hour/2024-01-05_data_science.vtt",
            speakers=["David", "Eve"],
            duration=2400.5,
            episode_number=10,
            description="Overview of data science and machine learning",
            processed_date="2024-01-06T10:00:00"
        )
    ]
    return episodes


@pytest.fixture
def metadata_index(temp_data_dir):
    """Create a metadata index instance with cleanup."""
    index = MetadataIndex(str(temp_data_dir))
    yield index
    # Clear any in-memory data
    index.episodes.clear()
    index.speaker_index.clear()
    index.podcast_index.clear()
    index.date_index.clear()
    index.word_index.clear()


@pytest.fixture
def populated_index(metadata_index, sample_episodes):
    """Create a populated index for testing search operations."""
    for episode in sample_episodes:
        metadata_index.add_episode(episode)
    yield metadata_index


class TestMetadataIndex:
    """Test MetadataIndex initialization and basic operations."""
    
    def test_initialization(self, temp_data_dir):
        """Test index initialization with proper directory creation."""
        index = MetadataIndex(str(temp_data_dir))
        
        assert index.base_dir == temp_data_dir
        assert index.index_file == temp_data_dir / "index.json"
        assert len(index.episodes) == 0
        assert len(index.speaker_index) == 0
        assert len(index.podcast_index) == 0
        assert len(index.date_index) == 0
        assert len(index.word_index) == 0
    
    def test_initialization_creates_directory(self, tmp_path):
        """Test that initialization creates missing directories."""
        non_existent = tmp_path / "new_dir"
        index = MetadataIndex(str(non_existent))
        
        assert non_existent.exists()
        assert index.base_dir == non_existent
    
    def test_add_episode(self, metadata_index, sample_episodes):
        """Test adding episodes to the index."""
        episode = sample_episodes[0]
        
        metadata_index.add_episode(episode)
        
        assert len(metadata_index.episodes) == 1
        assert metadata_index.episodes[0] == episode
        
        # Check indices were updated
        assert "alice" in metadata_index.speaker_index
        assert "bob" in metadata_index.speaker_index
        assert "tech talk" in metadata_index.podcast_index
        assert "2024-01-01" in metadata_index.date_index
        assert "2024-01" in metadata_index.date_index  # Year-month index
        
        # Check word index
        assert "episode" in metadata_index.word_index
        assert "introduction" in metadata_index.word_index
        assert "tech" in metadata_index.word_index
    
    def test_add_duplicate_episode(self, metadata_index, sample_episodes):
        """Test updating an existing episode."""
        episode = sample_episodes[0]
        
        # Add episode twice
        metadata_index.add_episode(episode)
        metadata_index.add_episode(episode)
        
        # Should only have one episode
        assert len(metadata_index.episodes) == 1
        
        # Modify and re-add
        modified = EpisodeMetadata(
            title="Episode 1: Updated",
            podcast_name=episode.podcast_name,
            publication_date=episode.publication_date,
            file_path=episode.file_path,  # Same file path
            speakers=["Alice", "Bob", "Charlie"],
            duration=episode.duration,
            episode_number=episode.episode_number,
            description=episode.description,
            processed_date=episode.processed_date
        )
        
        metadata_index.add_episode(modified)
        
        assert len(metadata_index.episodes) == 1
        assert metadata_index.episodes[0].title == "Episode 1: Updated"
        assert "charlie" in metadata_index.speaker_index
    
    def test_extract_words(self, metadata_index):
        """Test word extraction from text."""
        text = "This is a Test! With some-punctuation and numbers123."
        words = metadata_index._extract_words(text)
        
        # Should extract words > 2 characters
        assert "this" in words
        assert "test" in words
        assert "with" in words
        assert "punctuation" in words
        assert "numbers123" in words
        assert "is" not in words  # Too short
        assert "a" not in words   # Too short
    
    def test_remove_from_indices(self, populated_index):
        """Test removing episode from indices."""
        # Get initial state
        initial_speaker_count = sum(len(s) for s in populated_index.speaker_index.values())
        
        # Remove first episode from indices
        populated_index._remove_from_indices(0)
        
        # Check that episode was removed from all indices
        final_speaker_count = sum(len(s) for s in populated_index.speaker_index.values())
        assert final_speaker_count < initial_speaker_count
        
        # Episode 0 should not be in any index
        for speaker_set in populated_index.speaker_index.values():
            assert 0 not in speaker_set
        for podcast_set in populated_index.podcast_index.values():
            assert 0 not in podcast_set


class TestSearchOperations:
    """Test search functionality with memory optimization."""
    
    def test_search_by_speaker(self, populated_index):
        """Test searching episodes by speaker name."""
        # Exact match (case insensitive)
        result = populated_index.search_by_speaker("Alice")
        assert result.total_results == 2
        assert all("Alice" in ep.speakers for ep in result.episodes)
        
        # Partial match
        result = populated_index.search_by_speaker("ali")
        assert result.total_results == 2
        
        # Non-existent speaker
        result = populated_index.search_by_speaker("Frank")
        assert result.total_results == 0
        assert len(result.episodes) == 0
    
    def test_search_by_podcast(self, populated_index):
        """Test searching episodes by podcast name."""
        # Exact match
        result = populated_index.search_by_podcast("Tech Talk")
        assert result.total_results == 2
        assert all(ep.podcast_name == "Tech Talk" for ep in result.episodes)
        
        # Partial match
        result = populated_index.search_by_podcast("tech")
        assert result.total_results == 2
        
        # Another podcast
        result = populated_index.search_by_podcast("Science")
        assert result.total_results == 1
        assert result.episodes[0].podcast_name == "Science Hour"
    
    def test_search_by_date_range(self, populated_index):
        """Test searching episodes by date range."""
        # Single date
        result = populated_index.search_by_date_range("2024-01-01")
        assert result.total_results == 1
        assert result.episodes[0].publication_date == "2024-01-01"
        
        # Date range
        result = populated_index.search_by_date_range("2024-01-01", "2024-01-05")
        assert result.total_results == 2
        
        # Year-month search
        result = populated_index.search_by_date_range("2024-01", "2024-01")
        assert result.total_results == 3  # All episodes in January 2024
        
        # No results
        result = populated_index.search_by_date_range("2023-01-01", "2023-12-31")
        assert result.total_results == 0
    
    def test_search_by_keywords(self, populated_index):
        """Test searching episodes by keywords."""
        # Single keyword
        result = populated_index.search_by_keywords("python")
        assert result.total_results == 1
        assert "Python" in result.episodes[0].title
        
        # Multiple keywords (as list)
        result = populated_index.search_by_keywords(["data", "science"])
        assert result.total_results == 1
        
        # Keyword in description
        result = populated_index.search_by_keywords("basics")
        assert result.total_results == 1
        
        # Common word
        result = populated_index.search_by_keywords("episode")
        assert result.total_results == 2  # Episode 1 and 2 have "episode" in title
        
        # Empty keyword
        result = populated_index.search_by_keywords("")
        assert result.total_results == 0
    
    def test_search_all(self, populated_index):
        """Test searching across all fields."""
        # Search for speaker name
        result = populated_index.search_all("Alice")
        assert result.total_results == 2
        
        # Search for podcast name
        result = populated_index.search_all("Science")
        assert result.total_results == 1
        
        # Search for keyword
        result = populated_index.search_all("python")
        assert result.total_results == 1
        
        # Search that matches multiple criteria
        result = populated_index.search_all("tech")
        assert result.total_results == 2  # Matches "Tech Talk" podcast
    
    def test_search_result_properties(self, populated_index):
        """Test SearchResult object properties."""
        result = populated_index.search_by_speaker("Alice")
        
        assert isinstance(result, SearchResult)
        assert result.query == "speaker:Alice"
        assert result.total_results == 2
        assert isinstance(result.episodes, list)
        assert result.search_time_ms >= 0
        assert isinstance(result.search_time_ms, float)


class TestStatisticsAndExport:
    """Test statistics and export functionality."""
    
    def test_get_all_episodes(self, populated_index, sample_episodes):
        """Test getting all episodes."""
        all_episodes = populated_index.get_all_episodes()
        
        assert len(all_episodes) == len(sample_episodes)
        assert all_episodes == populated_index.episodes
        # Should be a copy, not the same list
        assert all_episodes is not populated_index.episodes
    
    def test_get_statistics_empty_index(self, metadata_index):
        """Test statistics on empty index."""
        stats = metadata_index.get_statistics()
        
        assert stats['total_episodes'] == 0
        assert len(stats) == 1  # Only total_episodes for empty index
    
    def test_get_statistics_populated_index(self, populated_index):
        """Test statistics on populated index."""
        stats = populated_index.get_statistics()
        
        assert stats['total_episodes'] == 3
        assert stats['unique_speakers'] == 5  # Alice, Bob, Charlie, David, Eve
        assert stats['unique_podcasts'] == 2  # Tech Talk, Science Hour
        assert stats['unique_dates'] == 3
        assert stats['date_range'] == ("2024-01-01", "2024-01-08")
        assert stats['total_duration_seconds'] == 6301.0
        assert stats['total_duration_hours'] == 1.75
        assert stats['average_duration_seconds'] == 2100.33
        assert stats['index_size_kb'] > 0
    
    def test_export_to_csv_basic(self, populated_index, tmp_path):
        """Test basic CSV export."""
        csv_path = tmp_path / "export.csv"
        
        result_path = populated_index.export_to_csv(str(csv_path), include_all_fields=False)
        
        assert result_path == str(csv_path)
        assert csv_path.exists()
        
        # Read and verify CSV
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 3
        
        # Check basic fields
        assert 'title' in rows[0]
        assert 'podcast_name' in rows[0]
        assert 'speakers' in rows[0]
        assert 'description' not in rows[0]  # Not included in basic export
        
        # Check speaker formatting
        assert rows[0]['speakers'] == "Alice, Bob"
    
    def test_export_to_csv_full(self, populated_index, tmp_path):
        """Test full CSV export with all fields."""
        csv_path = tmp_path / "export_full.csv"
        
        result_path = populated_index.export_to_csv(str(csv_path), include_all_fields=True)
        
        assert csv_path.exists()
        
        # Read and verify CSV
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 3
        
        # Check all fields present
        expected_fields = [
            'title', 'podcast_name', 'publication_date', 'file_path',
            'speakers', 'duration', 'episode_number', 'description', 'processed_date'
        ]
        for field in expected_fields:
            assert field in rows[0]
    
    def test_export_to_csv_creates_directory(self, populated_index, tmp_path):
        """Test CSV export creates missing directories."""
        csv_path = tmp_path / "new_dir" / "export.csv"
        
        result_path = populated_index.export_to_csv(str(csv_path))
        
        assert csv_path.exists()
        assert csv_path.parent.exists()
    
    def test_export_to_csv_error_handling(self, populated_index, tmp_path):
        """Test CSV export error handling."""
        # Try to export to a read-only location
        csv_path = tmp_path / "readonly.csv"
        csv_path.touch()
        csv_path.chmod(0o444)  # Read-only
        
        with pytest.raises(Exception):
            populated_index.export_to_csv(str(csv_path))


class TestPersistence:
    """Test index persistence and loading with memory optimization."""
    
    def test_save_and_load_index(self, temp_data_dir, sample_episodes):
        """Test saving and loading index from disk."""
        # Create and populate index
        index1 = MetadataIndex(str(temp_data_dir))
        for episode in sample_episodes:
            index1.add_episode(episode)
        
        # Verify index file was created
        assert index1.index_file.exists()
        
        # Create new index instance (should load from disk)
        index2 = MetadataIndex(str(temp_data_dir))
        
        # Verify data was loaded correctly
        assert len(index2.episodes) == len(sample_episodes)
        assert len(index2.speaker_index) > 0
        assert len(index2.podcast_index) > 0
        assert len(index2.date_index) > 0
        assert len(index2.word_index) > 0
        
        # Verify episodes match
        for i, episode in enumerate(index2.episodes):
            assert episode.title == sample_episodes[i].title
            assert episode.file_path == sample_episodes[i].file_path
    
    def test_load_corrupted_index(self, temp_data_dir, caplog):
        """Test loading a corrupted index file."""
        # Create corrupted index file
        index_file = temp_data_dir / "index.json"
        index_file.write_text("{ corrupted json }")
        
        # Create index (should handle corrupted file)
        index = MetadataIndex(str(temp_data_dir))
        
        # Should start with empty index
        assert len(index.episodes) == 0
        assert "Failed to load index" in caplog.text
        assert "Starting with empty index" in caplog.text
    
    def test_save_index_structure(self, populated_index):
        """Test the structure of saved index file."""
        populated_index.save_index()
        
        with open(populated_index.index_file, 'r') as f:
            data = json.load(f)
        
        assert 'version' in data
        assert data['version'] == '1.0'
        assert 'generated_at' in data
        assert 'total_episodes' in data
        assert data['total_episodes'] == 3
        assert 'episodes' in data
        assert len(data['episodes']) == 3
        assert 'statistics' in data
    
    def test_save_index_error_handling(self, populated_index, caplog):
        """Test save index error handling."""
        # Make index file read-only
        populated_index.index_file.touch()
        populated_index.index_file.chmod(0o444)
        
        populated_index.save_index()
        
        assert "Failed to save index" in caplog.text
    
    def test_rebuild_indices(self, populated_index):
        """Test rebuilding indices from episodes list."""
        # Clear indices
        populated_index.speaker_index.clear()
        populated_index.podcast_index.clear()
        populated_index.date_index.clear()
        populated_index.word_index.clear()
        
        # Rebuild
        populated_index._rebuild_indices()
        
        # Verify indices were rebuilt
        assert len(populated_index.speaker_index) > 0
        assert len(populated_index.podcast_index) > 0
        assert len(populated_index.date_index) > 0
        assert len(populated_index.word_index) > 0
        
        # Verify search still works
        result = populated_index.search_by_speaker("Alice")
        assert result.total_results == 2


class TestManifestIntegration:
    """Test integration with file organizer manifest."""
    
    def test_rebuild_from_manifest(self, metadata_index, tmp_path, sample_episodes):
        """Test rebuilding index from manifest file."""
        # Create manifest file
        manifest_data = {
            "generated_at": "2024-01-10T10:00:00",
            "total_episodes": len(sample_episodes),
            "episodes": [
                {
                    "title": ep.title,
                    "podcast_name": ep.podcast_name,
                    "publication_date": ep.publication_date,
                    "file_path": ep.file_path,
                    "speakers": ep.speakers,
                    "duration": ep.duration,
                    "episode_number": ep.episode_number,
                    "description": ep.description,
                    "processed_date": ep.processed_date
                }
                for ep in sample_episodes
            ]
        }
        
        manifest_file = tmp_path / "manifest.json"
        with open(manifest_file, 'w') as f:
            json.dump(manifest_data, f)
        
        # Rebuild from manifest
        metadata_index.rebuild_from_manifest(str(manifest_file))
        
        # Verify episodes were loaded
        assert len(metadata_index.episodes) == len(sample_episodes)
        for i, episode in enumerate(metadata_index.episodes):
            assert episode.title == sample_episodes[i].title
    
    def test_rebuild_from_missing_manifest(self, metadata_index, tmp_path, caplog):
        """Test handling missing manifest file."""
        manifest_file = tmp_path / "missing.json"
        
        metadata_index.rebuild_from_manifest(str(manifest_file))
        
        assert "Manifest file not found" in caplog.text
        assert len(metadata_index.episodes) == 0
    
    def test_rebuild_from_corrupted_manifest(self, metadata_index, tmp_path, caplog):
        """Test handling corrupted manifest file."""
        manifest_file = tmp_path / "bad_manifest.json"
        manifest_file.write_text("{ corrupted }")
        
        metadata_index.rebuild_from_manifest(str(manifest_file))
        
        assert "Failed to rebuild from manifest" in caplog.text
        assert len(metadata_index.episodes) == 0


class TestGlobalInstance:
    """Test global index instance management."""
    
    def test_get_metadata_index_singleton(self, temp_data_dir, monkeypatch):
        """Test that get_metadata_index returns singleton."""
        # Reset global instance
        import src.metadata_index
        src.metadata_index._index_instance = None
        
        # Get instance twice
        index1 = get_metadata_index(str(temp_data_dir))
        index2 = get_metadata_index(str(temp_data_dir))
        
        # Should be same instance
        assert index1 is index2
        
        # Reset for cleanup
        src.metadata_index._index_instance = None
    
    def test_get_metadata_index_default_directory(self, monkeypatch):
        """Test get_metadata_index with default directory."""
        # Reset global instance
        import src.metadata_index
        src.metadata_index._index_instance = None
        
        index = get_metadata_index()
        
        assert index.base_dir == Path("data")
        
        # Reset for cleanup
        src.metadata_index._index_instance = None


class TestMemoryOptimization:
    """Test memory optimization aspects."""
    
    def test_large_dataset_handling(self, metadata_index):
        """Test handling larger datasets efficiently."""
        # Generate episodes in batches to avoid memory spike
        batch_size = 10
        total_episodes = 50
        
        for batch in range(0, total_episodes, batch_size):
            # Create batch of episodes
            for i in range(batch, min(batch + batch_size, total_episodes)):
                episode = EpisodeMetadata(
                    title=f"Episode {i}",
                    podcast_name=f"Podcast {i % 5}",  # 5 different podcasts
                    publication_date=f"2024-01-{(i % 28) + 1:02d}",
                    file_path=f"podcast_{i % 5}/episode_{i}.vtt",
                    speakers=[f"Speaker{i % 10}", f"Speaker{(i + 1) % 10}"],
                    duration=1800 + i * 10,
                    episode_number=i,
                    description=f"Description for episode {i}",
                    processed_date=f"2024-01-{(i % 28) + 2:02d}T10:00:00"
                )
                metadata_index.add_episode(episode)
            
            # Force save to disk periodically to free memory
            if batch % 20 == 0:
                metadata_index.save_index()
        
        # Verify all episodes added
        assert len(metadata_index.episodes) == total_episodes
        
        # Test search performance
        result = metadata_index.search_by_speaker("Speaker5")
        assert result.total_results > 0
        assert result.search_time_ms < 100  # Should be fast
    
    def test_incremental_index_updates(self, populated_index):
        """Test incremental updates don't duplicate memory usage."""
        initial_episodes = len(populated_index.episodes)
        
        # Update existing episode multiple times
        episode = populated_index.episodes[0]
        for i in range(10):
            episode.description = f"Updated description {i}"
            populated_index.add_episode(episode)
        
        # Should still have same number of episodes
        assert len(populated_index.episodes) == initial_episodes
        
        # Verify last update was applied
        assert populated_index.episodes[0].description == "Updated description 9"
    
    def test_clear_operations(self, populated_index):
        """Test memory is properly cleared during operations."""
        # Test remove from indices clears memory
        populated_index._remove_from_indices(0)
        
        # Verify episode 0 is not in any index
        for index_dict in [populated_index.speaker_index, 
                          populated_index.podcast_index,
                          populated_index.date_index,
                          populated_index.word_index]:
            for episode_set in index_dict.values():
                assert 0 not in episode_set
        
        # Test rebuild clears old data
        old_speaker_count = len(populated_index.speaker_index)
        populated_index._rebuild_indices()
        
        # Should have same structure
        assert len(populated_index.speaker_index) == old_speaker_count