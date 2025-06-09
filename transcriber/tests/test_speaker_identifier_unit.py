"""Unit tests for speaker identification module."""

import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import asdict

from src.speaker_identifier import SpeakerIdentifier, SpeakerMapping


class TestSpeakerMapping:
    """Test SpeakerMapping dataclass."""
    
    def test_init(self):
        """Test SpeakerMapping initialization."""
        mapping = SpeakerMapping(
            generic_label="SPEAKER_1",
            identified_name="John Doe (Host)",
            confidence=0.95,
            evidence=["Introduced as host", "Says 'Welcome to my show'"]
        )
        
        assert mapping.generic_label == "SPEAKER_1"
        assert mapping.identified_name == "John Doe (Host)"
        assert mapping.confidence == 0.95
        assert len(mapping.evidence) == 2
    
    def test_to_dict(self):
        """Test converting SpeakerMapping to dictionary."""
        mapping = SpeakerMapping(
            generic_label="SPEAKER_2",
            identified_name="Jane Smith (Guest)",
            confidence=0.85,
            evidence=["Mentioned by name"]
        )
        
        result = mapping.to_dict()
        
        assert result == {
            'generic_label': 'SPEAKER_2',
            'identified_name': 'Jane Smith (Guest)',
            'confidence': 0.85,
            'evidence': ['Mentioned by name']
        }


class TestSpeakerIdentifier:
    """Test SpeakerIdentifier class."""
    
    @pytest.fixture
    def mock_gemini_client(self):
        """Create mock Gemini client."""
        client = AsyncMock()
        client.api_keys = ["test_key"]
        client.usage_trackers = [Mock()]
        return client
    
    @pytest.fixture
    def mock_key_manager(self):
        """Create mock key rotation manager."""
        manager = Mock()
        manager.get_next_key.return_value = ("test_key", 0)
        return manager
    
    @pytest.fixture
    def identifier(self, mock_gemini_client, mock_key_manager):
        """Create SpeakerIdentifier instance."""
        return SpeakerIdentifier(mock_gemini_client, mock_key_manager)
    
    @pytest.fixture
    def sample_vtt_transcript(self):
        """Sample VTT transcript for testing."""
        return """WEBVTT

00:00:01.000 --> 00:00:05.000
<v SPEAKER_1>Welcome to the Tech Talk podcast. I'm your host.

00:00:05.000 --> 00:00:10.000
<v SPEAKER_2>Thanks for having me on the show!

00:00:10.000 --> 00:00:15.000
<v SPEAKER_1>Today we're talking with Dr. Jane Smith about AI.

00:00:15.000 --> 00:00:20.000
<v SPEAKER_2>I'm excited to discuss the latest developments."""
    
    @pytest.fixture
    def sample_metadata(self):
        """Sample episode metadata."""
        return {
            'podcast_name': 'Tech Talk',
            'title': 'AI Innovations with Dr. Jane Smith',
            'author': 'John Doe',
            'description': 'An interview with AI researcher Dr. Jane Smith',
            'published_date': '2025-06-01'
        }
    
    def test_init(self, mock_gemini_client, mock_key_manager):
        """Test SpeakerIdentifier initialization."""
        identifier = SpeakerIdentifier(mock_gemini_client, mock_key_manager)
        
        assert identifier.gemini_client == mock_gemini_client
        assert identifier.key_manager == mock_key_manager
        assert identifier.checkpoint_manager is None
    
    def test_init_with_checkpoint_manager(self, mock_gemini_client, mock_key_manager):
        """Test initialization with checkpoint manager."""
        mock_checkpoint = Mock()
        identifier = SpeakerIdentifier(mock_gemini_client, mock_key_manager, mock_checkpoint)
        
        assert identifier.checkpoint_manager == mock_checkpoint
    
    @pytest.mark.asyncio
    async def test_identify_speakers_success(self, identifier, sample_vtt_transcript, sample_metadata):
        """Test successful speaker identification."""
        # Setup mock response
        identifier.gemini_client.identify_speakers.return_value = {
            'SPEAKER_1': 'John Doe (Host)',
            'SPEAKER_2': 'Dr. Jane Smith (Guest - AI Researcher)'
        }
        
        result = await identifier.identify_speakers(sample_vtt_transcript, sample_metadata)
        
        # Verify API was called
        identifier.gemini_client.identify_speakers.assert_called_once_with(
            sample_vtt_transcript, sample_metadata
        )
        
        # Key manager is not called directly by speaker identifier anymore
        # (it's handled internally by the gemini_client)
        
        # Verify result
        assert result == {
            'SPEAKER_1': 'John Doe (Host)',
            'SPEAKER_2': 'Dr. Jane Smith (Guest - AI Researcher)'
        }
    
    @pytest.mark.asyncio
    async def test_identify_speakers_api_failure(self, identifier, sample_vtt_transcript, sample_metadata):
        """Test speaker identification with API failure."""
        # Setup mock to raise exception
        identifier.gemini_client.identify_speakers.side_effect = Exception("API Error")
        
        result = await identifier.identify_speakers(sample_vtt_transcript, sample_metadata)
        
        # Should return fallback mapping
        assert result == {
            'SPEAKER_1': 'John Doe (Host)',
            'SPEAKER_2': 'Guest'
        }
        
        # Key failures are handled internally by gemini_client
    
    @pytest.mark.asyncio
    async def test_identify_speakers_empty_response(self, identifier, sample_vtt_transcript, sample_metadata):
        """Test handling empty response from API."""
        identifier.gemini_client.identify_speakers.return_value = None
        
        result = await identifier.identify_speakers(sample_vtt_transcript, sample_metadata)
        
        # Should use fallback mapping
        assert 'SPEAKER_1' in result
        assert 'SPEAKER_2' in result
        assert 'Host' in result['SPEAKER_1']
    
    @pytest.mark.asyncio
    async def test_identify_speakers_with_checkpoint(self, mock_gemini_client, mock_key_manager, 
                                                    sample_vtt_transcript, sample_metadata):
        """Test speaker identification with checkpoint manager."""
        mock_checkpoint = Mock()
        identifier = SpeakerIdentifier(mock_gemini_client, mock_key_manager, mock_checkpoint)
        
        mock_gemini_client.identify_speakers.return_value = {
            'SPEAKER_1': 'John Doe (Host)'
        }
        
        await identifier.identify_speakers(sample_vtt_transcript, sample_metadata)
        
        # Verify checkpoint operations
        mock_checkpoint.save_temp_data.assert_called_once()
        mock_checkpoint.complete_stage.assert_called_once_with('speaker_identification')
    
    def test_extract_speaker_labels(self, identifier, sample_vtt_transcript):
        """Test extracting speaker labels from VTT."""
        labels = identifier._extract_speaker_labels(sample_vtt_transcript)
        
        assert labels == ['SPEAKER_1', 'SPEAKER_2']
    
    def test_extract_speaker_labels_complex(self, identifier):
        """Test extracting speaker labels with various formats."""
        transcript = """WEBVTT

00:00:01.000 --> 00:00:05.000
<v SPEAKER_1>Hello

00:00:05.000 --> 00:00:10.000
<v  SPEAKER_2 >With spaces

00:00:10.000 --> 00:00:15.000
<v SPEAKER_10>Double digit

00:00:15.000 --> 00:00:20.000
<v Host_Name>Non-standard format"""
        
        labels = identifier._extract_speaker_labels(transcript)
        
        assert set(labels) == {'SPEAKER_1', 'SPEAKER_2', 'SPEAKER_10', 'Host_Name'}
    
    def test_extract_speaker_labels_no_speakers(self, identifier):
        """Test extracting from transcript with no speakers."""
        transcript = """WEBVTT

00:00:01.000 --> 00:00:05.000
No speaker tags here"""
        
        labels = identifier._extract_speaker_labels(transcript)
        assert labels == []
    
    def test_build_identification_prompt(self, identifier, sample_vtt_transcript, sample_metadata):
        """Test building identification prompt."""
        labels = ['SPEAKER_1', 'SPEAKER_2']
        
        prompt = identifier._build_identification_prompt(
            sample_vtt_transcript, sample_metadata, labels
        )
        
        # Check key components are in prompt
        assert 'Tech Talk' in prompt
        assert 'John Doe' in prompt
        assert 'AI Innovations with Dr. Jane Smith' in prompt
        assert 'SPEAKER_1' in prompt
        assert 'SPEAKER_2' in prompt
        assert 'sample dialogue' in prompt.lower()
        assert 'JSON object' in prompt
    
    def test_extract_speaker_samples(self, identifier, sample_vtt_transcript):
        """Test extracting speaker dialogue samples."""
        labels = ['SPEAKER_1', 'SPEAKER_2']
        
        samples = identifier._extract_speaker_samples(sample_vtt_transcript, labels)
        
        assert 'SPEAKER_1' in samples
        assert 'SPEAKER_2' in samples
        assert len(samples['SPEAKER_1']) == 2
        assert len(samples['SPEAKER_2']) == 2
        assert "Welcome to the Tech Talk podcast" in samples['SPEAKER_1'][0]
        assert "Thanks for having me" in samples['SPEAKER_2'][0]
    
    def test_extract_speaker_samples_max_limit(self, identifier):
        """Test sample extraction respects max limit."""
        transcript = """WEBVTT

""" + "\n\n".join([f"""00:00:{i:02d}.000 --> 00:00:{i+1:02d}.000
<v SPEAKER_1>Sample text number {i} with enough length to be included""" for i in range(10)])
        
        samples = identifier._extract_speaker_samples(transcript, ['SPEAKER_1'], max_samples=3)
        
        assert len(samples['SPEAKER_1']) == 3
    
    def test_validate_mapping_complete(self, identifier, sample_metadata):
        """Test validating complete mapping."""
        mapping = {
            'SPEAKER_1': 'John Doe (Host)',
            'SPEAKER_2': 'Jane Smith (Guest)'
        }
        expected_labels = ['SPEAKER_1', 'SPEAKER_2']
        
        result = identifier._validate_mapping(mapping, expected_labels, sample_metadata)
        
        assert result == mapping
    
    def test_validate_mapping_missing_labels(self, identifier, sample_metadata):
        """Test validating mapping with missing labels."""
        mapping = {
            'SPEAKER_1': 'John Doe (Host)'
        }
        expected_labels = ['SPEAKER_1', 'SPEAKER_2', 'SPEAKER_3']
        
        result = identifier._validate_mapping(mapping, expected_labels, sample_metadata)
        
        assert result['SPEAKER_1'] == 'John Doe (Host)'
        assert result['SPEAKER_2'] == 'Guest'
        assert result['SPEAKER_3'] == 'Guest 2'
    
    def test_validate_mapping_cleanup(self, identifier, sample_metadata):
        """Test mapping validation cleans up values."""
        mapping = {
            'SPEAKER_1': '"John Doe (Host)"',  # With quotes
            'SPEAKER_2': '  Jane Smith  ',     # With spaces
            'SPEAKER_3': 'SPEAKER_3',          # Same as label
            'SPEAKER_4': ''                    # Empty
        }
        expected_labels = ['SPEAKER_1', 'SPEAKER_2', 'SPEAKER_3', 'SPEAKER_4']
        
        result = identifier._validate_mapping(mapping, expected_labels, sample_metadata)
        
        assert result['SPEAKER_1'] == 'John Doe (Host)'
        assert result['SPEAKER_2'] == 'Jane Smith'
        assert 'Guest' in result['SPEAKER_3']
        assert 'Guest' in result['SPEAKER_4']
    
    def test_get_fallback_name_host(self, identifier, sample_metadata):
        """Test fallback name for host."""
        result = identifier._get_fallback_name('SPEAKER_1', sample_metadata)
        assert result == 'John Doe (Host)'
    
    def test_get_fallback_name_guest(self, identifier, sample_metadata):
        """Test fallback name for guests."""
        assert identifier._get_fallback_name('SPEAKER_2', sample_metadata) == 'Guest'
        assert identifier._get_fallback_name('SPEAKER_3', sample_metadata) == 'Guest 2'
        assert identifier._get_fallback_name('SPEAKER_4', sample_metadata) == 'Guest 3'
    
    def test_get_fallback_name_no_author(self, identifier):
        """Test fallback when no author in metadata."""
        metadata = {'title': 'Episode'}
        result = identifier._get_fallback_name('SPEAKER_1', metadata)
        assert result == 'Host'
    
    def test_get_fallback_name_non_standard(self, identifier, sample_metadata):
        """Test fallback for non-standard labels."""
        result = identifier._get_fallback_name('HOST', sample_metadata)
        assert result == 'HOST'
    
    def test_create_fallback_mapping(self, identifier, sample_metadata):
        """Test creating complete fallback mapping."""
        labels = ['SPEAKER_1', 'SPEAKER_2', 'SPEAKER_3']
        
        result = identifier._create_fallback_mapping(labels, sample_metadata)
        
        assert result == {
            'SPEAKER_1': 'John Doe (Host)',
            'SPEAKER_2': 'Guest',
            'SPEAKER_3': 'Guest 2'
        }
    
    def test_apply_speaker_mapping(self, identifier, sample_vtt_transcript):
        """Test applying speaker mapping to transcript."""
        mapping = {
            'SPEAKER_1': 'John Doe (Host)',
            'SPEAKER_2': 'Dr. Jane Smith (Guest)'
        }
        
        result = identifier.apply_speaker_mapping(sample_vtt_transcript, mapping)
        
        assert '<v John Doe (Host)>' in result
        assert '<v Dr. Jane Smith (Guest)>' in result
        assert '<v SPEAKER_1>' not in result
        assert '<v SPEAKER_2>' not in result
    
    def test_apply_speaker_mapping_partial(self, identifier):
        """Test applying mapping avoids partial replacements."""
        transcript = """WEBVTT

00:00:01.000 --> 00:00:05.000
<v SPEAKER_1>Hello from speaker 1

00:00:05.000 --> 00:00:10.000
<v SPEAKER_10>Hello from speaker 10"""
        
        mapping = {
            'SPEAKER_1': 'Host',
            'SPEAKER_10': 'Guest'
        }
        
        result = identifier.apply_speaker_mapping(transcript, mapping)
        
        assert '<v Host>' in result
        assert '<v Guest>' in result
        # Ensure SPEAKER_10 wasn't partially replaced
        assert '<v Guest0>' not in result
    
    def test_generate_speaker_metadata(self, identifier, sample_metadata):
        """Test generating speaker metadata."""
        mapping = {
            'SPEAKER_1': 'John Doe (Host)',
            'SPEAKER_2': 'Jane Smith (Guest)',
            'SPEAKER_3': 'Bob Wilson'
        }
        
        result = identifier.generate_speaker_metadata(mapping, sample_metadata)
        
        assert result['speaker_count'] == 3
        assert result['identification_method'] == 'contextual_analysis'
        assert result['podcast_format'] == 'co-hosted_interview'
        
        speakers = result['speakers']
        assert len(speakers) == 3
        
        # Check first speaker
        assert speakers[0]['label'] == 'SPEAKER_1'
        assert speakers[0]['name'] == 'John Doe'
        assert speakers[0]['role'] == 'Host'
        assert speakers[0]['full_identification'] == 'John Doe (Host)'
        
        # Check speaker without role
        assert speakers[2]['name'] == 'Bob Wilson'
        assert speakers[2]['role'] == 'Unknown'
    
    def test_infer_podcast_format(self, identifier):
        """Test inferring podcast format from speaker count."""
        assert identifier._infer_podcast_format(1) == 'solo'
        assert identifier._infer_podcast_format(2) == 'interview'
        assert identifier._infer_podcast_format(3) == 'co-hosted_interview'
        assert identifier._infer_podcast_format(4) == 'panel'
        assert identifier._infer_podcast_format(5) == 'panel'
    
    def test_extract_speaker_samples_multiline(self, identifier):
        """Test extracting samples with multiline text."""
        transcript = """WEBVTT

00:00:01.000 --> 00:00:05.000
<v SPEAKER_1>This is a longer text that has enough characters to be included in the sample

00:00:05.000 --> 00:00:10.000
<v SPEAKER_2>Another speaker text here"""
        
        samples = identifier._extract_speaker_samples(transcript, ['SPEAKER_1'])
        
        assert len(samples['SPEAKER_1']) == 1
        # The regex captures the text after the speaker tag
        sample_text = samples['SPEAKER_1'][0]
        assert 'This is a longer text' in sample_text
        assert 'enough characters' in sample_text
        # Check newlines are replaced with spaces if any
        assert '\n' not in sample_text
    
    def test_extract_speaker_samples_short_utterances(self, identifier):
        """Test that short utterances are skipped."""
        transcript = """WEBVTT

00:00:01.000 --> 00:00:02.000
<v SPEAKER_1>Hi

00:00:02.000 --> 00:00:05.000
<v SPEAKER_1>This is a longer utterance that should be included"""
        
        samples = identifier._extract_speaker_samples(transcript, ['SPEAKER_1'])
        
        # Only the longer utterance should be included
        assert len(samples['SPEAKER_1']) == 1
        assert 'longer utterance' in samples['SPEAKER_1'][0]
    
    # New tests for hybrid approach
    def test_extract_speaker_labels_hybrid(self, identifier):
        """Test extracting labels with mix of generic and identified speakers."""
        transcript = """WEBVTT

00:00:01.000 --> 00:00:05.000
<v John Smith (Host)>Welcome to the show

00:00:05.000 --> 00:00:10.000
<v SPEAKER_2>Thank you for having me

00:00:10.000 --> 00:00:15.000
<v Dr. Jane Doe>I'm excited to be here"""
        
        labels = identifier._extract_speaker_labels(transcript)
        
        assert set(labels) == {'John Smith (Host)', 'SPEAKER_2', 'Dr. Jane Doe'}
    
    def test_validate_mapping_hybrid_already_identified(self, identifier, sample_metadata):
        """Test validating mapping with already identified speakers."""
        mapping = {
            'John Smith (Host)': 'John Smith (Host)',  # No change needed
            'SPEAKER_2': 'Dr. Jane Doe (Guest)',       # Needs identification
            'Sarah Wilson': 'Sarah Wilson (Co-host)'   # Enhancement with role
        }
        expected_labels = ['John Smith (Host)', 'SPEAKER_2', 'Sarah Wilson']
        
        result = identifier._validate_mapping(mapping, expected_labels, sample_metadata)
        
        assert result['John Smith (Host)'] == 'John Smith (Host)'
        assert result['SPEAKER_2'] == 'Dr. Jane Doe (Guest)'
        assert result['Sarah Wilson'] == 'Sarah Wilson (Co-host)'
    
    def test_validate_mapping_hybrid_no_enhancement(self, identifier, sample_metadata):
        """Test validation preserves existing identifications when no enhancement."""
        mapping = {
            'Dr. Jane Smith': 'Dr. Jane Smith',  # Same value - keep original
            'SPEAKER_2': 'Guest Speaker'         # Generic label gets identification
        }
        expected_labels = ['Dr. Jane Smith', 'SPEAKER_2']
        
        result = identifier._validate_mapping(mapping, expected_labels, sample_metadata)
        
        assert result['Dr. Jane Smith'] == 'Dr. Jane Smith'
        assert result['SPEAKER_2'] == 'Guest Speaker'
    
    def test_create_fallback_mapping_hybrid(self, identifier, sample_metadata):
        """Test creating fallback mapping with mix of speakers."""
        labels = ['John Smith (Host)', 'SPEAKER_2', 'Dr. Jane Doe', 'SPEAKER_4']
        
        result = identifier._create_fallback_mapping(labels, sample_metadata)
        
        # Already identified speakers should remain unchanged
        assert result['John Smith (Host)'] == 'John Smith (Host)'
        assert result['Dr. Jane Doe'] == 'Dr. Jane Doe'
        
        # Generic speakers should get fallback names
        assert result['SPEAKER_2'] == 'Guest'
        assert result['SPEAKER_4'] == 'Guest 3'
    
    def test_build_identification_prompt_hybrid(self, identifier, sample_metadata):
        """Test building prompt with mix of identified and generic speakers."""
        transcript = """WEBVTT

00:00:01.000 --> 00:00:05.000
<v John Smith (Host)>Welcome to the show

00:00:05.000 --> 00:00:10.000
<v SPEAKER_2>Thank you for having me"""
        
        labels = ['John Smith (Host)', 'SPEAKER_2']
        
        prompt = identifier._build_identification_prompt(transcript, sample_metadata, labels)
        
        # Check that it identifies the status correctly
        assert 'Already Identified: John Smith (Host)' in prompt
        assert 'Need Identification: SPEAKER_2' in prompt
        assert '✓ Already identified' in prompt
        assert '⚠ Needs identification' in prompt
    
    def test_apply_speaker_mapping_hybrid(self, identifier):
        """Test applying mapping with mix of generic and identified speakers."""
        transcript = """WEBVTT

00:00:01.000 --> 00:00:05.000
<v John Smith (Host)>Welcome to the show

00:00:05.000 --> 00:00:10.000
<v SPEAKER_2>Thank you for having me

00:00:10.000 --> 00:00:15.000
<v Dr. Jane>I'm excited"""
        
        mapping = {
            'John Smith (Host)': 'John Smith (Host)',  # No change
            'SPEAKER_2': 'Guest Speaker',              # Generic to identified
            'Dr. Jane': 'Dr. Jane Doe (Researcher)'    # Enhancement
        }
        
        result = identifier.apply_speaker_mapping(transcript, mapping)
        
        assert '<v John Smith (Host)>' in result
        assert '<v Guest Speaker>' in result
        assert '<v Dr. Jane Doe (Researcher)>' in result
        assert '<v SPEAKER_2>' not in result
        assert '<v Dr. Jane>' not in result
    
    @pytest.mark.asyncio
    async def test_identify_speakers_hybrid_scenario(self, identifier, sample_metadata):
        """Test complete speaker identification in hybrid scenario."""
        # Transcript with mix of identified and generic speakers
        transcript = """WEBVTT

00:00:01.000 --> 00:00:05.000
<v John Smith (Host)>Welcome to Tech Talk

00:00:05.000 --> 00:00:10.000
<v SPEAKER_2>Thanks for having me

00:00:10.000 --> 00:00:15.000
<v John Smith (Host)>Today we're with Dr. Jane Smith

00:00:15.000 --> 00:00:20.000
<v SPEAKER_2>I'm excited to discuss AI"""
        
        # Mock API response for validation/gap-filling
        identifier.gemini_client.identify_speakers.return_value = {
            'John Smith (Host)': 'John Smith (Host)',
            'SPEAKER_2': 'Dr. Jane Smith (Guest - AI Researcher)'
        }
        
        result = await identifier.identify_speakers(transcript, sample_metadata)
        
        # Verify final mapping
        assert result['John Smith (Host)'] == 'John Smith (Host)'
        assert result['SPEAKER_2'] == 'Dr. Jane Smith (Guest - AI Researcher)'