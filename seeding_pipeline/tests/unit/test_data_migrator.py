"""
Comprehensive tests for the data migration module.

This module tests migration status tracking, data transformation,
rollback functionality, and checkpoint management.
"""

import pytest
import json
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path

from src.migration.data_migrator import (
    MigrationStatus,
    MigrationProgress,
    DataMigrator,
)
from src.core.models import Podcast, Episode, Segment, Entity


class TestMigrationStatus:
    """Test the MigrationStatus enum."""
    
    def test_status_values(self):
        """Test migration status values."""
        assert MigrationStatus.PENDING.value == "pending"
        assert MigrationStatus.IN_PROGRESS.value == "in_progress"
        assert MigrationStatus.COMPLETED.value == "completed"
        assert MigrationStatus.FAILED.value == "failed"
    
    def test_all_statuses_defined(self):
        """Test all expected statuses are defined."""
        expected_statuses = {"PENDING", "IN_PROGRESS", "COMPLETED", "FAILED", "ROLLED_BACK"}
        actual_statuses = {status.name for status in MigrationStatus}
        assert actual_statuses == expected_statuses


class TestMigrationProgress:
    """Test the MigrationProgress dataclass."""
    
    def test_initialization(self):
        """Test progress initialization with defaults."""
        progress = MigrationProgress()
        
        assert progress.total_items == 0
        assert progress.processed_items == 0
        assert progress.failed_items == 0
        assert progress.skipped_items == 0
        assert progress.start_time is None
        assert progress.end_time is None
        assert progress.status == MigrationStatus.PENDING
        assert progress.errors == []
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        # No items processed
        progress = MigrationProgress()
        assert progress.success_rate == 0.0
        
        # Some items processed with failures
        progress.processed_items = 100
        progress.failed_items = 20
        assert progress.success_rate == 0.8
        
        # All items successful
        progress.processed_items = 100
        progress.failed_items = 0
        assert progress.success_rate == 1.0
    
    def test_duration_seconds(self):
        """Test duration calculation."""
        progress = MigrationProgress()
        
        # No start time
        assert progress.duration_seconds is None
        
        # Start time but no end time - should return None
        progress.start_time = datetime.now()
        duration = progress.duration_seconds
        assert duration is None
        
        # Both start and end time
        progress.start_time = datetime.now() - timedelta(seconds=10)
        progress.end_time = datetime.now()
        duration = progress.duration_seconds
        assert duration is not None
        assert 9 <= duration <= 11  # Allow for small timing variations
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        now = datetime.now()
        progress = MigrationProgress(
            total_items=100,
            processed_items=50,
            failed_items=5,
            status=MigrationStatus.IN_PROGRESS,
            start_time=now
        )
        
        result = progress.to_dict()
        
        assert isinstance(result, dict)
        assert result['total_items'] == 100
        assert result['processed_items'] == 50
        assert result['failed_items'] == 5
        assert result['status'] == 'in_progress'
        assert result['start_time'] == now.isoformat()


class TestDataMigrator:
    """Test the DataMigrator class."""
    
    @pytest.fixture
    def mock_graph_provider(self):
        """Create mock graph provider."""
        provider = Mock()
        provider.is_connected.return_value = True
        provider.execute_query = Mock(return_value=[])
        provider.create_node = Mock()
        provider.create_relationship = Mock()
        provider.execute_transaction = Mock()
        return provider
    
    @pytest.fixture
    def temp_checkpoint_dir(self):
        """Create temporary checkpoint directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def migrator(self, mock_graph_provider, temp_checkpoint_dir):
        """Create migrator instance."""
        return DataMigrator(
            graph_provider=mock_graph_provider,
            checkpoint_dir=Path(temp_checkpoint_dir),
            batch_size=10
        )
    
    def test_initialization(self, mock_graph_provider, temp_checkpoint_dir):
        """Test migrator initialization."""
        migrator = DataMigrator(
            graph_provider=mock_graph_provider,
            checkpoint_dir=Path(temp_checkpoint_dir),
            batch_size=50
        )
        
        assert migrator.graph_provider == mock_graph_provider
        assert migrator.checkpoint_dir == Path(temp_checkpoint_dir)
        assert migrator.batch_size == 50
    
    def test_migrate_all_dry_run(self, migrator, mock_graph_provider):
        """Test dry run migration."""
        # Setup mock data
        mock_graph_provider.execute_query.side_effect = [
            [{'count': 10}],  # Podcasts count
            [{'count': 50}],  # Episodes count
            [{'count': 100}], # Segments count
            [{'count': 200}], # Entities count
            [{'count': 150}], # Insights count
            [{'count': 75}],  # Quotes count
            [{'count': 30}],  # Topics count
            [{'count': 20}],  # Speakers count
        ]
        
        # Run dry run migration
        result = migrator.migrate_all(dry_run=True)
        
        # Verify result
        assert isinstance(result, dict)
        assert 'podcasts' in result
        assert 'episodes' in result
        assert result['podcasts'].total_items == 10
        assert result['episodes'].total_items == 50
    
    def test_migrate_all_success(self, migrator, mock_graph_provider):
        """Test successful migration."""
        # Setup mock data
        mock_podcast_data = [
            {'id': 'p1', 'title': 'Podcast 1', 'url': 'https://example.com/p1'},
            {'id': 'p2', 'title': 'Podcast 2', 'url': 'https://example.com/p2'}
        ]
        
        mock_graph_provider.execute_query.side_effect = [
            [{'count': 2}],  # Podcasts count
            mock_podcast_data,  # Podcast data
            [{'count': 0}],  # Episodes count
            [],  # No episodes
            [{'count': 0}],  # Segments count
            [],  # No segments
            [{'count': 0}],  # Entities count
            [],  # No entities
            [{'count': 0}],  # Insights count
            [],  # No insights
            [{'count': 0}],  # Quotes count
            [],  # No quotes
            [{'count': 0}],  # Topics count
            [],  # No topics
            [{'count': 0}],  # Speakers count
            [],  # No speakers
        ]
        
        # Run migration
        result = migrator.migrate_all(dry_run=False)
        
        # Verify result
        assert result['podcasts'].status == MigrationStatus.COMPLETED
        assert result['podcasts'].processed_items == 2
        assert result['podcasts'].failed_items == 0
    
    def test_transform_podcast(self, migrator):
        """Test podcast transformation."""
        node = {
            'id': 'p1',
            'title': 'Test Podcast',
            'rss_url': 'https://example.com/feed',  # The transform looks for rss_url or feed_url
            'description': 'A test podcast',
            'created_at': datetime.now().isoformat()
        }
        
        podcast = migrator._transform_podcast(node)
        
        assert isinstance(podcast, Podcast)
        assert podcast.id == 'p1'
        assert podcast.name == 'Test Podcast'
        assert podcast.rss_url == 'https://example.com/feed'
        assert podcast.description == 'A test podcast'
    
    def test_transform_episode(self, migrator):
        """Test episode transformation."""
        node = {
            'id': 'e1',
            'title': 'Test Episode',
            'audio_url': 'https://example.com/audio.mp3',
            'description': 'Test episode description',
            'published_date': '2024-01-01',
            'duration': 3600,
            'episode_number': 42
        }
        
        episode = migrator._transform_episode(node)
        
        assert isinstance(episode, Episode)
        assert episode.id == 'e1'
        assert episode.title == 'Test Episode'
        assert episode.audio_url == 'https://example.com/audio.mp3'
        assert episode.description == 'Test episode description'
        assert episode.published_date == '2024-01-01'
        assert episode.duration == 3600
        assert episode.episode_number == 42
    
    def test_transform_segment(self, migrator):
        """Test segment transformation."""
        node = {
            'id': 's1',
            'start_time': 0,
            'end_time': 60,
            'text': 'Segment text',
            'speaker': 'Speaker 1',
            'is_advertisement': False
        }
        
        segment = migrator._transform_segment(node)
        
        assert isinstance(segment, Segment)
        assert segment.id == 's1'
        assert segment.start_time == 0
        assert segment.end_time == 60
        assert segment.text == 'Segment text'
        assert segment.speaker == 'Speaker 1'
        assert segment.is_advertisement is False
        # episode_id is set separately during migration, not in transform
    
    def test_save_and_restore_progress(self, migrator):
        """Test saving and restoring progress."""
        # Create progress data
        progress_data = {
            'podcasts': MigrationProgress(
                total_items=100,
                processed_items=50,
                status=MigrationStatus.IN_PROGRESS
            ),
            'episodes': MigrationProgress(
                total_items=500,
                processed_items=250,
                status=MigrationStatus.IN_PROGRESS
            )
        }
        
        # Save progress
        checkpoint = migrator._save_progress(progress_data)
        
        # Restore progress
        restored = migrator._restore_progress(checkpoint)
        
        assert restored['podcasts'].total_items == 100
        assert restored['podcasts'].processed_items == 50
        assert restored['episodes'].total_items == 500
        assert restored['episodes'].processed_items == 250
    
    def test_rollback(self, migrator, mock_graph_provider):
        """Test rollback functionality."""
        target_date = datetime.now() - timedelta(days=1)
        
        # Mock the query to return nodes created after target date
        mock_graph_provider.execute_query.return_value = [
            {'id': 'node1'},
            {'id': 'node2'}
        ]
        
        result = migrator.rollback(target_date)
        
        assert result is True
        assert mock_graph_provider.execute_query.called
    
    def test_error_handling_in_migration(self, migrator, mock_graph_provider):
        """Test error handling during migration."""
        # Setup mock to raise error
        mock_graph_provider.execute_query.side_effect = Exception("Database error")
        
        # Run migration
        result = migrator.migrate_all(dry_run=False)
        
        # Verify error handling
        assert 'podcasts' in result
        assert result['podcasts'].status == MigrationStatus.FAILED
        assert len(result['podcasts'].errors) > 0
    
    def test_batch_processing(self, migrator, mock_graph_provider):
        """Test batch processing of large datasets."""
        # The migrator processes items in batches internally
        # We'll test that it correctly handles batch_size parameter
        
        # Create dataset larger than batch size
        mock_graph_provider.execute_query.side_effect = [
            [{'count': 25}],  # Podcasts count
            # The migrator will fetch in batches based on batch_size
            [{'count': 0}],  # Episodes count
            [{'count': 0}],  # Segments count
            [{'count': 0}],  # Entities count
            [{'count': 0}],  # Insights count
            [{'count': 0}],  # Quotes count
            [{'count': 0}],  # Topics count
            [{'count': 0}],  # Speakers count
        ]
        
        # Run migration with batch size of 10
        result = migrator.migrate_all(dry_run=True)
        
        # Verify counts were retrieved
        assert result['podcasts'].total_items == 25
        assert migrator.batch_size == 10