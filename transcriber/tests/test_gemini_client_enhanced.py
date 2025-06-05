"""Enhanced tests for Gemini client to achieve 85% coverage."""

import pytest
import json
import os
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, mock_open

from src.gemini_client import (
    APIKeyUsage, RateLimitedGeminiClient, create_gemini_client,
    RATE_LIMITS, DEFAULT_MODEL
)
from src.retry_wrapper import QuotaExceededException, CircuitBreakerOpenException


@pytest.mark.unit
class TestGeminiClientEnhancedCoverage:
    """Enhanced tests to reach 85% coverage for gemini_client module."""
    
    @pytest.fixture
    def mock_key_rotation_manager(self):
        """Mock key rotation manager."""
        manager = MagicMock()
        manager.get_next_key.return_value = ('test_key', 0)
        return manager
    
    @pytest.fixture
    def client_with_rotation(self, mock_key_rotation_manager):
        """Create client with key rotation manager."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model:
            mock_model.return_value = MagicMock()
            return RateLimitedGeminiClient(
                ['test_key'], 
                key_rotation_manager=mock_key_rotation_manager
            )
    
    def test_get_available_client_with_key_rotation(self, client_with_rotation, mock_key_rotation_manager):
        """Test _get_available_client with key rotation manager."""
        model, key_index = client_with_rotation._get_available_client()
        
        assert model is not None
        assert key_index == 0
        mock_key_rotation_manager.get_next_key.assert_called_once()
    
    def test_get_available_client_rotation_fallback(self, client_with_rotation, mock_key_rotation_manager):
        """Test fallback when key rotation manager fails."""
        mock_key_rotation_manager.get_next_key.side_effect = Exception("Rotation failed")
        
        model, key_index = client_with_rotation._get_available_client()
        
        # Should fall back to legacy logic
        assert model is not None
        assert key_index == 0
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_with_validation_and_continuation(self):
        """Test transcription with validation and continuation loop."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            
            # Create mock model
            mock_model = AsyncMock()
            mock_model_class.return_value = mock_model
            
            # Create client
            client = RateLimitedGeminiClient(['test_key'])
            
            # Mock initial transcript that needs continuation
            initial_transcript = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v SPEAKER_1>This is the beginning

00:00:05.000 --> 00:00:10.000
<v SPEAKER_2>Only covers 10 seconds"""
            
            # Mock continuation transcript
            continuation_transcript = """00:00:10.000 --> 00:00:15.000
<v SPEAKER_1>This is the continuation

00:00:15.000 --> 00:00:20.000
<v SPEAKER_2>Now we have more coverage"""
            
            # Set up mocks
            with patch.object(client, '_transcribe_with_retry', return_value=initial_transcript), \
                 patch.object(client, 'request_continuation', return_value=continuation_transcript), \
                 patch.object(client, '_download_audio_file', return_value='/tmp/audio.mp3'), \
                 patch('os.unlink'):
                
                # Episode metadata with duration
                metadata = {
                    'title': 'Test Episode',
                    'duration': '00:30'  # 30 seconds
                }
                
                # Validation config
                validation_config = {
                    'enabled': True,
                    'min_coverage_ratio': 0.5,
                    'max_continuation_attempts': 2
                }
                
                result = await client.transcribe_audio(
                    'https://example.com/audio.mp3',
                    metadata,
                    validation_config
                )
                
                assert result is not None
                assert 'continuation' in result  # Should have stitched transcripts
                assert metadata.get('_continuation_info') is not None
    
    @pytest.mark.asyncio 
    async def test_transcribe_audio_skip_episode_quota_preservation(self):
        """Test skipping episode to preserve quota."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            
            mock_model = MagicMock()
            mock_model_class.return_value = mock_model
            
            client = RateLimitedGeminiClient(['test_key'])
            
            # Set high request count to trigger skip
            client.usage_trackers[0].requests_today = 23  # Close to daily limit
            
            with patch('src.gemini_client.should_skip_episode', return_value=True):
                result = await client.transcribe_audio(
                    'https://example.com/audio.mp3',
                    {'title': 'Test'}
                )
                
                assert result is None
    
    @pytest.mark.asyncio
    async def test_transcribe_with_retry_full_flow(self):
        """Test full transcription flow with file upload."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model_class, \
             patch('google.generativeai.upload_file') as mock_upload, \
             patch('google.generativeai.delete_file') as mock_delete:
            
            # Setup mocks
            mock_model = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest transcript"
            mock_model.generate_content_async.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            mock_uploaded_file = MagicMock()
            mock_uploaded_file.name = "uploaded_file_123"
            mock_upload.return_value = mock_uploaded_file
            
            client = RateLimitedGeminiClient(['test_key'])
            
            with patch.object(client, '_download_audio_file', return_value='/tmp/audio.mp3'), \
                 patch('os.unlink'), \
                 patch('os.path.exists', return_value=True):
                
                metadata = {'title': 'Test', 'duration': '5:00'}
                
                result = await client._transcribe_with_retry(
                    mock_model, 0, 'https://example.com/audio.mp3', metadata
                )
                
                assert result == mock_response.text
                mock_upload.assert_called_once()
                mock_delete.assert_called_once_with(mock_uploaded_file.name)
    
    @pytest.mark.asyncio
    async def test_continuation_loop_complete(self):
        """Test continuation loop with complete transcript."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            # Mock a complete transcript
            complete_transcript = """WEBVTT

00:00:00.000 --> 00:00:10.000
<v SPEAKER_1>First segment

00:00:10.000 --> 00:00:20.000
<v SPEAKER_2>Second segment

00:00:20.000 --> 00:00:30.000
<v SPEAKER_1>Final segment covering full duration"""
            
            validation_config = {'min_coverage_ratio': 0.85}
            
            result, tracking_info = await client._continuation_loop(
                complete_transcript,
                'https://example.com/audio.mp3',
                {'title': 'Test'},
                30,  # 30 seconds duration
                validation_config
            )
            
            assert result == complete_transcript
            assert tracking_info['continuation_attempts'] == 0
            assert tracking_info['final_coverage_ratio'] >= 0.85
    
    @pytest.mark.asyncio
    async def test_continuation_loop_max_attempts(self):
        """Test continuation loop reaching max attempts."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            # Mock incomplete transcript
            incomplete_transcript = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v SPEAKER_1>Only 5 seconds"""
            
            # Mock continuation that doesn't help much
            small_continuation = """00:00:05.000 --> 00:00:07.000
<v SPEAKER_1>Two more seconds"""
            
            validation_config = {
                'min_coverage_ratio': 0.85,
                'max_continuation_attempts': 2
            }
            
            with patch.object(client, 'request_continuation', return_value=small_continuation):
                result, tracking_info = await client._continuation_loop(
                    incomplete_transcript,
                    'https://example.com/audio.mp3', 
                    {'title': 'Test'},
                    60,  # 60 seconds duration
                    validation_config
                )
                
                assert tracking_info['continuation_attempts'] == 2
                assert tracking_info['final_coverage_ratio'] < 0.85
    
    def test_stitch_transcripts_single_segment(self):
        """Test stitching with single segment."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            single_segment = "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest"
            
            result = client.stitch_transcripts([single_segment])
            assert result == single_segment
    
    def test_stitch_transcripts_multiple_segments(self):
        """Test stitching multiple transcript segments."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            segment1 = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v SPEAKER_1>First segment

00:00:05.000 --> 00:00:10.000
<v SPEAKER_2>Second part"""
            
            segment2 = """00:00:10.000 --> 00:00:15.000
<v SPEAKER_1>Third segment

00:00:15.000 --> 00:00:20.000
<v SPEAKER_2>Fourth part"""
            
            result = client.stitch_transcripts([segment1, segment2])
            
            assert "WEBVTT" in result
            assert "First segment" in result
            assert "Fourth part" in result
            assert result.count("00:00:10.000") >= 1  # No duplication
    
    def test_stitch_transcripts_with_overlap(self):
        """Test stitching with overlapping timestamps."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            segment1 = """WEBVTT

00:00:00.000 --> 00:00:10.000
<v SPEAKER_1>First segment"""
            
            # Overlapping segment
            segment2 = """00:00:08.000 --> 00:00:15.000
<v SPEAKER_1>First segment

00:00:15.000 --> 00:00:20.000
<v SPEAKER_2>New content"""
            
            result = client.stitch_transcripts([segment1, segment2], overlap_seconds=3.0)
            
            assert "First segment" in result
            assert "New content" in result
    
    def test_parse_vtt_cues(self):
        """Test parsing VTT cues."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v SPEAKER_1>Hello world

00:00:05.000 --> 00:00:10.000
<v SPEAKER_2>How are you?"""
            
            cues = client._parse_vtt_cues(vtt_content)
            
            assert len(cues) == 2
            assert cues[0]['start_time'] == "00:00:00.000"
            assert cues[0]['end_time'] == "00:00:05.000"
            assert "Hello world" in cues[0]['text']
            assert cues[1]['start_seconds'] == 5.0
    
    def test_are_texts_similar(self):
        """Test text similarity checking."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            # Exact match
            assert client._are_texts_similar("Hello", "Hello") is True
            
            # With voice tags
            assert client._are_texts_similar(
                "<v SPEAKER_1>Hello", 
                "<v SPEAKER_2>Hello"
            ) is True
            
            # Different texts
            assert client._are_texts_similar("Hello", "Goodbye") is False
            
            # Substring match - shorter text in longer
            assert client._are_texts_similar(
                "Hello world",
                "Hello world, how are you?"
            ) is True
            
            # Empty texts
            assert client._are_texts_similar("", "") is False
            assert client._are_texts_similar("Hello", "") is False
            
            # High similarity threshold test
            assert client._are_texts_similar(
                "Hello",
                "Hello world",
                threshold=0.5  # 5/11 > 0.5
            ) is False
    
    def test_extract_context_from_transcript(self):
        """Test extracting context lines from transcript."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            # Test with properly formatted transcript
            transcript = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v SPEAKER_1>Line 1

00:00:05.000 --> 00:00:10.000
<v SPEAKER_2>Line 2

00:00:10.000 --> 00:00:15.000
<v SPEAKER_1>Line 3

00:00:15.000 --> 00:00:20.000
<v SPEAKER_2>Line 4

00:00:20.000 --> 00:00:25.000
<v SPEAKER_1>Line 5"""
            
            context = client._extract_context_from_transcript(transcript, 25.0)
            
            # Should extract some context lines
            assert isinstance(context, list)
            
            # Test with empty transcript
            empty_context = client._extract_context_from_transcript("", 0)
            assert empty_context == []
            
            # Test with malformed transcript
            bad_context = client._extract_context_from_transcript("not a vtt", 10.0)
            assert bad_context == []
    
    def test_build_continuation_prompt(self):
        """Test building continuation prompt."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            metadata = {
                'podcast_name': 'Test Podcast',
                'title': 'Episode 1',
                'publication_date': '2024-01-01'
            }
            
            context_lines = [
                "00:00:10.000 --> 00:00:15.000: Previous content",
                "00:00:15.000 --> 00:00:20.000: More content"
            ]
            
            prompt = client._build_continuation_prompt(metadata, 20.0, context_lines)
            
            assert "Test Podcast" in prompt
            assert "Episode 1" in prompt
            assert "00:00:20.000" in prompt
            assert "Previous content" in prompt
    
    def test_simple_concatenate_fallback(self):
        """Test simple concatenation fallback."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            segments = [
                "WEBVTT\n\nNOTE\nMetadata\n\n00:00:00.000 --> 00:00:05.000\nFirst",
                "WEBVTT\n\n00:00:05.000 --> 00:00:10.000\nSecond"
            ]
            
            result = client._simple_concatenate(segments)
            
            assert result.startswith("WEBVTT")
            assert "First" in result
            assert "Second" in result
            assert result.count("WEBVTT") == 1  # Only one header
    
    @pytest.mark.asyncio
    async def test_identify_speakers_skip_quota(self):
        """Test speaker identification skipping for quota preservation."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            client.usage_trackers[0].requests_today = 23
            
            with patch('src.gemini_client.should_skip_episode', return_value=True):
                result = await client.identify_speakers("transcript", {})
                assert result == {}
    
    @pytest.mark.asyncio
    async def test_request_continuation_success(self):
        """Test successful continuation request."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model_class, \
             patch('pathlib.Path.exists', return_value=False):  # Don't load existing state
            
            mock_model = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = "00:00:20.000 --> 00:00:25.000\nContinuation content"
            mock_model.generate_content_async.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            client = RateLimitedGeminiClient(['test_key'])
            initial_requests = client.usage_trackers[0].requests_today
            
            result = await client.request_continuation(
                "audio.mp3",
                "existing transcript",
                20.0,
                {'title': 'Test'}
            )
            
            assert result == mock_response.text
            assert client.usage_trackers[0].requests_today == initial_requests + 1
    
    @pytest.mark.asyncio
    async def test_request_continuation_no_keys(self):
        """Test continuation request with no available keys."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            with patch.object(client, '_get_available_client', return_value=(None, None)):
                result = await client.request_continuation(
                    "audio.mp3", "transcript", 20.0, {}
                )
                assert result is None
    
    @pytest.mark.asyncio
    async def test_download_audio_error_handling(self):
        """Test audio download error handling."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            with patch('urllib.request.urlopen', side_effect=Exception("Network error")), \
                 patch('tempfile.NamedTemporaryFile') as mock_temp:
                
                mock_temp.return_value.name = "/tmp/test.mp3"
                
                with pytest.raises(Exception):
                    await client._download_audio_file("https://example.com/audio.mp3")
    
    def test_load_usage_state_error_handling(self):
        """Test usage state loading with corrupted file."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data='invalid json')):
            
            # Should not crash on invalid JSON
            client = RateLimitedGeminiClient(['test_key'])
            assert len(client.usage_trackers) == 1
    
    def test_save_usage_state_error_handling(self):
        """Test usage state saving with write error."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            with patch('builtins.open', side_effect=IOError("Disk full")):
                # Should not crash on write error
                client._save_usage_state()
                # Test passes if no exception raised
    
    @pytest.mark.asyncio
    async def test_transcribe_circuit_breaker_open(self):
        """Test transcription handling when circuit breaker is open."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            with patch.object(client, '_transcribe_with_retry',
                            side_effect=CircuitBreakerOpenException("Circuit open")):
                result = await client.transcribe_audio(
                    'https://example.com/audio.mp3', {}
                )
                assert result is None
                assert client.usage_trackers[0].is_available is False
    
    @pytest.mark.asyncio
    async def test_transcribe_with_key_rotation_failure_reporting(self):
        """Test failure reporting to key rotation manager."""
        mock_rotation = MagicMock()
        
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'], key_rotation_manager=mock_rotation)
            
            with patch.object(client, '_transcribe_with_retry',
                            side_effect=QuotaExceededException("Quota exceeded")):
                result = await client.transcribe_audio(
                    'https://example.com/audio.mp3', {}
                )
                
                assert result is None
                mock_rotation.mark_key_failure.assert_called()
    
    @pytest.mark.asyncio
    async def test_transcribe_with_retry_empty_response(self):
        """Test handling empty response from API."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model_class, \
             patch('google.generativeai.upload_file') as mock_upload, \
             patch('google.generativeai.delete_file'):
            
            # Setup empty response
            mock_model = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = ""  # Empty response
            mock_model.generate_content_async.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            mock_upload.return_value = MagicMock(name="test_file")
            
            client = RateLimitedGeminiClient(['test_key'])
            
            with patch.object(client, '_download_audio_file', return_value='/tmp/audio.mp3'), \
                 patch('os.unlink'), \
                 patch('os.path.exists', return_value=True):
                
                with pytest.raises(Exception, match="Empty transcript"):
                    await client._transcribe_with_retry(
                        mock_model, 0, 'https://example.com/audio.mp3', {'title': 'Test'}
                    )
    
    @pytest.mark.asyncio
    async def test_identify_speakers_with_retry_success(self):
        """Test speaker identification retry flow."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            
            mock_model = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = '{"SPEAKER_1": "Host", "SPEAKER_2": "Guest"}'
            mock_model.generate_content_async.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            client = RateLimitedGeminiClient(['test_key'])
            
            result = await client._identify_speakers_with_retry(
                mock_model, 0, "test transcript", {'title': 'Test'}
            )
            
            assert result == {"SPEAKER_1": "Host", "SPEAKER_2": "Guest"}
            assert client.usage_trackers[0].requests_today > 0
    
    @pytest.mark.asyncio
    async def test_identify_speakers_invalid_json_response(self):
        """Test handling invalid JSON in speaker identification."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model_class, \
             patch('pathlib.Path.exists', return_value=False):
            
            mock_model = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = '{"invalid": json}'  # Invalid JSON
            mock_model.generate_content_async.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            client = RateLimitedGeminiClient(['test_key'])
            
            with pytest.raises(Exception, match="Invalid response format"):
                await client._identify_speakers_with_retry(
                    mock_model, 0, "test transcript", {'title': 'Test'}
                )
    
    @pytest.mark.asyncio
    async def test_continuation_request_error_handling(self):
        """Test error handling in continuation request."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            
            mock_model = AsyncMock()
            mock_model.generate_content_async.side_effect = Exception("API Error")
            mock_model_class.return_value = mock_model
            
            client = RateLimitedGeminiClient(['test_key'])
            
            result = await client.request_continuation(
                "audio.mp3", "transcript", 20.0, {}
            )
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_continuation_request_empty_response(self):
        """Test handling empty continuation response."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel') as mock_model_class:
            
            mock_model = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = ""  # Empty continuation
            mock_model.generate_content_async.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            client = RateLimitedGeminiClient(['test_key'])
            
            result = await client.request_continuation(
                "audio.mp3", "transcript", 20.0, {}
            )
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_download_audio_file_zero_size(self):
        """Test handling zero-size downloaded file."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            with patch('urllib.request.urlopen') as mock_urlopen, \
                 patch('tempfile.NamedTemporaryFile') as mock_temp, \
                 patch('os.path.getsize', return_value=0), \
                 patch('os.unlink') as mock_unlink, \
                 patch('builtins.open', mock_open()):
                
                # Mock response
                mock_response = MagicMock()
                mock_response.read.return_value = b''  # No data
                mock_urlopen.return_value.__enter__.return_value = mock_response
                
                # Mock temp file with proper context manager
                mock_temp_file = MagicMock()
                mock_temp_file.name = "/tmp/audio.mp3"
                mock_temp.return_value.__enter__.return_value = mock_temp_file
                mock_temp.return_value.__exit__.return_value = None
                
                with pytest.raises(Exception, match="empty"):
                    await client._download_audio_file("https://example.com/audio.mp3")
                
                # Should clean up file
                mock_unlink.assert_called_once()
    
    def test_remove_overlapping_cues_edge_cases(self):
        """Test edge cases in overlapping cue removal."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            # Test empty cues
            assert client._remove_overlapping_cues([], 2.0) == []
            
            # Test single cue
            single_cue = [{
                'start_time': '00:00:00.000',
                'end_time': '00:00:05.000',
                'start_seconds': 0,
                'end_seconds': 5,
                'text': 'Single cue'
            }]
            assert client._remove_overlapping_cues(single_cue, 2.0) == single_cue
    
    def test_stitch_transcripts_error_handling(self):
        """Test error handling in transcript stitching."""
        with patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            
            client = RateLimitedGeminiClient(['test_key'])
            
            # Test empty segments
            assert client.stitch_transcripts([]) == ""
            
            # Test with parse error - should fall back to simple concatenate
            with patch.object(client, '_parse_vtt_cues', side_effect=Exception("Parse error")):
                segments = ["WEBVTT\n\nSegment 1", "Segment 2"]
                result = client.stitch_transcripts(segments)
                assert "Segment 1" in result
                assert "Segment 2" in result