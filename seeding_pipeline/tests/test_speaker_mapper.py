"""Unit tests for SpeakerMapper post-processing functionality.

Tests cover all pattern matching methods, YouTube API integration,
LLM-based identification, and database update logic.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path
import json
from datetime import datetime

from src.post_processing.speaker_mapper import SpeakerMapper
from src.core.config import PipelineConfig


class TestSpeakerMapper:
    """Test suite for SpeakerMapper class."""
    
    @pytest.fixture
    def mock_storage(self):
        """Create mock storage service."""
        storage = Mock()
        storage.driver = Mock()
        storage.driver.session.return_value.begin_transaction.return_value = Mock()
        return storage
    
    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service."""
        llm = Mock()
        llm.generate_text = Mock(return_value="John Smith")
        return llm
    
    @pytest.fixture
    def mock_config(self):
        """Create mock pipeline config."""
        return PipelineConfig()
    
    @pytest.fixture
    def speaker_mapper(self, mock_storage, mock_llm_service, mock_config):
        """Create SpeakerMapper instance with mocked dependencies."""
        return SpeakerMapper(
            storage=mock_storage,
            llm_service=mock_llm_service,
            config=mock_config
        )
    
    @pytest.fixture
    def sample_episode_data(self):
        """Sample episode data for testing."""
        return {
            'episode': {'episodeId': 'test_episode_1'},
            'units': [
                {
                    'unitId': 'unit_1',
                    'content': 'Welcome everyone. I\'m Jane Doe and today we have a special guest.',
                    'speakers': '{"Host": 1}'
                },
                {
                    'unitId': 'unit_2', 
                    'content': 'Thanks for having me, Jane. My name is Dr. Robert Johnson.',
                    'speakers': '{"Guest Expert (Psychiatrist)": 1}'
                },
                {
                    'unitId': 'unit_3',
                    'content': 'Thank you Dr. Johnson for sharing your insights.',
                    'speakers': '{"Host": 1}'
                }
            ],
            'description': 'Today we\'re joined by Dr. Robert Johnson, a renowned psychiatrist and author of "Mind Matters".',
            'title': 'Understanding Mental Health with Dr. Robert Johnson',
            'youtube_url': 'https://www.youtube.com/watch?v=test123',
            'podcast': 'Health & Wellness Podcast'
        }
    
    def test_initialization(self, speaker_mapper):
        """Test SpeakerMapper initialization."""
        assert speaker_mapper is not None
        assert speaker_mapper.storage is not None
        assert speaker_mapper.llm_service is not None
        assert speaker_mapper.config is not None
        assert speaker_mapper.youtube_client is None  # Lazy initialization
        assert speaker_mapper._cache == {}
    
    def test_identify_generic_speakers(self, speaker_mapper, sample_episode_data):
        """Test identification of generic speaker names."""
        generic_speakers = speaker_mapper._identify_generic_speakers(sample_episode_data)
        
        assert 'Guest Expert (Psychiatrist)' in generic_speakers
        assert 'Host' not in generic_speakers  # Not considered generic
        assert len(generic_speakers) == 1
    
    def test_is_generic_speaker(self, speaker_mapper):
        """Test generic speaker name detection."""
        # Generic names
        assert speaker_mapper._is_generic_speaker('Guest Expert (Psychiatrist)')
        assert speaker_mapper._is_generic_speaker('Guest/Contributor')
        assert speaker_mapper._is_generic_speaker('Co-host/Producer')
        assert speaker_mapper._is_generic_speaker('Guest (Speaker 1)')
        
        # Real names
        assert not speaker_mapper._is_generic_speaker('Jane Doe')
        assert not speaker_mapper._is_generic_speaker('Dr. Robert Johnson')
        assert not speaker_mapper._is_generic_speaker('John Smith III')
    
    def test_match_from_episode_description(self, speaker_mapper):
        """Test speaker name extraction from episode description."""
        episode_data = {
            'description': 'Join us as we welcome Dr. Sarah Mitchell, a leading expert in neuroscience. '
                          'Also featuring our co-host Mike Stevens.',
            'units': []
        }
        generic_speakers = ['Guest Expert', 'Co-host/Producer']
        
        mappings = speaker_mapper._match_from_episode_description(episode_data, generic_speakers)
        
        assert len(mappings) > 0
        # Should match "Dr. Sarah Mitchell" with "Guest Expert"
        assert any('Sarah Mitchell' in name for name in mappings.values())
    
    def test_match_from_introductions(self, speaker_mapper, sample_episode_data):
        """Test speaker name extraction from transcript introductions."""
        generic_speakers = ['Guest Expert (Psychiatrist)']
        
        mappings = speaker_mapper._match_from_introductions(sample_episode_data, generic_speakers)
        
        # Should find "Dr. Robert Johnson" from "My name is Dr. Robert Johnson"
        assert 'Guest Expert (Psychiatrist)' in mappings
        assert 'Dr. Robert Johnson' in mappings.values()
    
    def test_match_from_closing_credits(self, speaker_mapper):
        """Test speaker name extraction from closing credits."""
        episode_data = {
            'units': [
                {'content': 'Regular content here'},
                {'content': 'More regular content'},
                {'content': 'Almost done with the episode'},
                {
                    'content': 'Special thanks to our guest Dr. Emily Chen for joining us today.',
                    'speakers': '{"Host": 1}'
                },
                {
                    'content': 'This episode was produced by Amanda Rodriguez.',
                    'speakers': '{"Host": 1}'
                }
            ]
        }
        generic_speakers = ['Guest Expert', 'Co-host/Producer']
        
        mappings = speaker_mapper._match_from_closing_credits(episode_data, generic_speakers)
        
        assert len(mappings) > 0
        # Should find "Dr. Emily Chen" and "Amanda Rodriguez"
        assert any('Emily Chen' in name for name in mappings.values())
    
    @patch('src.post_processing.speaker_mapper.YouTubeDescriptionFetcher')
    def test_match_from_youtube(self, mock_youtube_fetcher_class, speaker_mapper):
        """Test speaker name extraction from YouTube descriptions."""
        # Mock YouTube client
        mock_youtube_client = Mock()
        mock_youtube_client.is_available.return_value = True
        mock_youtube_client.get_video_description.return_value = """
        Guest: Dr. Michael Thompson - Behavioral Psychologist
        
        In this episode, we discuss mental health strategies with Dr. Thompson.
        
        Host: Jane Doe
        Producer: Sarah Lee
        """
        mock_youtube_fetcher_class.return_value = mock_youtube_client
        
        episode_data = {
            'youtube_url': 'https://www.youtube.com/watch?v=test123'
        }
        generic_speakers = ['Guest Expert', 'Co-host/Producer']
        
        # Initialize YouTube client
        speaker_mapper.youtube_client = None
        mappings = speaker_mapper._match_from_youtube(episode_data, generic_speakers)
        
        assert len(mappings) > 0
        # Should extract "Dr. Michael Thompson" and "Sarah Lee"
        assert any('Michael Thompson' in name for name in mappings.values())
    
    def test_generate_speaker_prompt(self, speaker_mapper, sample_episode_data):
        """Test LLM prompt generation."""
        generic_speaker = 'Guest Expert (Psychiatrist)'
        speaker_segments = [
            'Thanks for having me, Jane. My name is Dr. Robert Johnson.',
            'In my practice, I often see patients struggling with anxiety.',
            'My latest book explores these themes in detail.'
        ]
        
        prompt = speaker_mapper._generate_speaker_prompt(
            sample_episode_data,
            generic_speaker,
            speaker_segments
        )
        
        # Verify prompt contains key elements
        assert 'Guest Expert (Psychiatrist)' in prompt
        assert 'Health & Wellness Podcast' in prompt
        assert 'Understanding Mental Health' in prompt
        assert 'Thanks for having me, Jane' in prompt
        assert 'UNKNOWN' in prompt  # Fallback instruction
    
    def test_match_from_llm(self, speaker_mapper, sample_episode_data, mock_llm_service):
        """Test LLM-based speaker identification."""
        generic_speakers = ['Guest Expert (Psychiatrist)']
        
        # Mock LLM response
        mock_llm_service.generate_text.return_value = 'Dr. Robert Johnson'
        
        mappings = speaker_mapper._match_from_llm(sample_episode_data, generic_speakers)
        
        assert 'Guest Expert (Psychiatrist)' in mappings
        assert mappings['Guest Expert (Psychiatrist)'] == 'Dr. Robert Johnson'
        mock_llm_service.generate_text.assert_called_once()
    
    def test_match_from_llm_invalid_response(self, speaker_mapper, sample_episode_data, mock_llm_service):
        """Test LLM identification with invalid response."""
        generic_speakers = ['Guest Expert']
        
        # Mock invalid LLM responses
        mock_llm_service.generate_text.return_value = 'UNKNOWN'
        
        mappings = speaker_mapper._match_from_llm(sample_episode_data, generic_speakers)
        
        assert len(mappings) == 0  # Should not map UNKNOWN
    
    def test_update_speakers_in_database(self, speaker_mapper, mock_storage):
        """Test database update functionality."""
        episode_id = 'test_episode_1'
        mappings = {
            'Guest Expert (Psychiatrist)': 'Dr. Robert Johnson',
            'Co-host/Producer': 'Sarah Lee'
        }
        
        # Mock transaction
        mock_tx = Mock()
        mock_tx.run.return_value.single.return_value = {'updated_count': 3}
        mock_storage.driver.session.return_value.begin_transaction.return_value = mock_tx
        
        # Execute update
        speaker_mapper._update_speakers_in_database(episode_id, mappings)
        
        # Verify transaction was used
        mock_tx.commit.assert_called_once()
        assert mock_tx.run.call_count >= len(mappings)  # At least one query per mapping
        
        # Verify queries contain correct parameters
        calls = mock_tx.run.call_args_list
        assert any('Guest Expert (Psychiatrist)' in str(call) for call in calls)
        assert any('Dr. Robert Johnson' in str(call) for call in calls)
    
    def test_update_speakers_database_error(self, speaker_mapper, mock_storage):
        """Test database update error handling."""
        episode_id = 'test_episode_1'
        mappings = {'Guest Expert': 'Dr. Smith'}
        
        # Mock transaction that fails
        mock_tx = Mock()
        mock_tx.run.side_effect = Exception("Database error")
        mock_storage.driver.session.return_value.begin_transaction.return_value = mock_tx
        
        # Should raise exception and rollback
        with pytest.raises(Exception) as exc_info:
            speaker_mapper._update_speakers_in_database(episode_id, mappings)
        
        assert "Database error" in str(exc_info.value)
        mock_tx.rollback.assert_called_once()
    
    @patch('src.post_processing.speaker_mapper.Path')
    @patch('builtins.open', create=True)
    @patch('src.post_processing.speaker_mapper.json')
    def test_log_speaker_changes(self, mock_json, mock_open, mock_path, speaker_mapper, mock_storage):
        """Test audit trail logging."""
        episode_id = 'test_episode_1'
        mappings = {'Guest Expert': 'Dr. Smith'}
        
        # Mock file operations
        mock_path.return_value.mkdir.return_value = None
        mock_path.return_value.exists.return_value = False
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Execute logging
        speaker_mapper._log_speaker_changes(episode_id, mappings)
        
        # Verify file was written
        mock_json.dump.assert_called_once()
        audit_data = mock_json.dump.call_args[0][0]
        assert len(audit_data) == 1
        assert audit_data[0]['episode_id'] == episode_id
        assert audit_data[0]['mappings'] == mappings
        
        # Verify Neo4j audit was attempted
        mock_storage.query.assert_called_once()
        query_args = mock_storage.query.call_args[0]
        assert 'SpeakerMappingAudit' in query_args[0]
    
    def test_process_episode_full_flow(self, speaker_mapper, mock_storage):
        """Test complete episode processing flow."""
        episode_id = 'test_episode_1'
        
        # Mock episode data retrieval
        mock_storage.query.return_value = [{
            'e': {
                'episodeId': episode_id,
                'title': 'Test Episode',
                'description': 'Featuring Dr. Jane Smith',
                'episodeUrl': 'https://youtube.com/watch?v=test'
            },
            'units': [
                {
                    'unitId': 'unit_1',
                    'content': 'Welcome, I\'m your host John.',
                    'speakers': '{"Host": 1}'
                },
                {
                    'unitId': 'unit_2',
                    'content': 'Thanks John, I\'m Dr. Jane Smith.',
                    'speakers': '{"Guest Expert": 1}'
                }
            ]
        }]
        
        # Mock database update transaction
        mock_tx = Mock()
        mock_tx.run.return_value.single.return_value = {'updated_count': 1}
        mock_storage.driver.session.return_value.begin_transaction.return_value = mock_tx
        
        # Process episode
        with patch('src.post_processing.speaker_mapper.Path'):
            with patch('builtins.open', create=True):
                mappings = speaker_mapper.process_episode(episode_id)
        
        # Should find and map "Guest Expert" to "Dr. Jane Smith"
        assert len(mappings) > 0
        assert any('Jane Smith' in name for name in mappings.values())
    
    def test_process_episode_no_generic_speakers(self, speaker_mapper, mock_storage):
        """Test processing episode with no generic speakers."""
        episode_id = 'test_episode_2'
        
        # Mock episode data with only real names
        mock_storage.query.return_value = [{
            'e': {'episodeId': episode_id},
            'units': [
                {
                    'speakers': '{"Jane Doe": 1, "John Smith": 1}'
                }
            ]
        }]
        
        mappings = speaker_mapper.process_episode(episode_id)
        
        assert len(mappings) == 0  # No generic speakers to map
    
    def test_youtube_api_not_available(self, speaker_mapper):
        """Test handling when YouTube API is not available."""
        episode_data = {'youtube_url': 'https://youtube.com/watch?v=test'}
        generic_speakers = ['Guest Expert']
        
        # YouTube client not available
        speaker_mapper.youtube_client = Mock()
        speaker_mapper.youtube_client.is_available.return_value = False
        
        mappings = speaker_mapper._match_from_youtube(episode_data, generic_speakers)
        
        assert len(mappings) == 0  # Should return empty when API not available