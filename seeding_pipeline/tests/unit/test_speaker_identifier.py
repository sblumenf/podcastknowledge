"""Unit tests for speaker identification system."""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from pathlib import Path

from src.core.models import TranscriptSegment
from src.extraction.speaker_identifier import SpeakerIdentifier
from src.extraction.speaker_database import SpeakerDatabase
from src.extraction.speaker_metrics import SpeakerIdentificationMetrics


class TestSpeakerIdentifier:
    """Test cases for SpeakerIdentifier class."""
    
    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service."""
        service = Mock()
        service.complete = Mock(return_value=json.dumps({
            "speaker_mappings": {
                "Speaker 0": "John Smith (Host)",
                "Speaker 1": "Dr. Jane Doe (Guest Expert)"
            },
            "confidence_scores": {
                "Speaker 0": 0.9,
                "Speaker 1": 0.85
            },
            "identification_methods": {
                "Speaker 0": "Self-introduction and host pattern",
                "Speaker 1": "Guest introduction by host"
            },
            "unresolved_speakers": []
        }))
        return service
    
    @pytest.fixture
    def sample_segments(self):
        """Create sample transcript segments."""
        return [
            TranscriptSegment(
                text="Welcome to the podcast. I'm John Smith.",
                start_time=0.0,
                end_time=3.0,
                speaker="Speaker 0"
            ),
            TranscriptSegment(
                text="Thanks for having me, John. I'm Dr. Jane Doe.",
                start_time=3.0,
                end_time=6.0,
                speaker="Speaker 1"
            ),
            TranscriptSegment(
                text="Today we'll discuss artificial intelligence.",
                start_time=6.0,
                end_time=9.0,
                speaker="Speaker 0"
            )
        ]
    
    @pytest.fixture
    def sample_metadata(self):
        """Create sample episode metadata."""
        return {
            'podcast_name': 'Tech Talk Podcast',
            'episode_title': 'AI and the Future',
            'description': 'Discussion about AI with Dr. Jane Doe',
            'date': '2024-01-15'
        }
    
    def test_initialization(self, mock_llm_service):
        """Test speaker identifier initialization."""
        identifier = SpeakerIdentifier(
            llm_service=mock_llm_service,
            confidence_threshold=0.8,
            timeout_seconds=20
        )
        
        assert identifier.confidence_threshold == 0.8
        assert identifier.timeout_seconds == 20
        assert identifier.max_segments_for_context == 50
        assert identifier.speaker_db is not None
        assert identifier.speaker_metrics is not None
    
    def test_identify_speakers_success(self, mock_llm_service, sample_segments, sample_metadata):
        """Test successful speaker identification."""
        identifier = SpeakerIdentifier(mock_llm_service)
        
        result = identifier.identify_speakers(
            sample_segments, 
            sample_metadata
        )
        
        assert result['speaker_mappings']['Speaker 0'] == "John Smith (Host)"
        assert result['speaker_mappings']['Speaker 1'] == "Dr. Jane Doe (Guest Expert)"
        assert result['confidence_scores']['Speaker 0'] == 0.9
        assert result['confidence_scores']['Speaker 1'] == 0.85
        assert len(result['unresolved_speakers']) == 0
        assert 'stats' in result
        assert 'performance' in result
    
    def test_identify_speakers_with_cache_hit(self, mock_llm_service, sample_segments, sample_metadata):
        """Test speaker identification with cache hit."""
        identifier = SpeakerIdentifier(mock_llm_service)
        
        # Pre-populate cache
        identifier.speaker_db.store_speakers(
            'Tech Talk Podcast',
            {'Speaker 0': 'John Smith (Host)'},
            {'Speaker 0': 0.95}
        )
        
        result = identifier.identify_speakers(
            sample_segments,
            sample_metadata
        )
        
        # Should have cache hit for Speaker 0
        assert result['performance']['cache_hit'] == True
        assert 'John Smith (Host)' in result['speaker_mappings'].values()
    
    def test_single_speaker_optimization(self, mock_llm_service, sample_metadata):
        """Test optimization for single speaker podcasts."""
        segments = [
            TranscriptSegment(
                text="This is a monologue.",
                start_time=0.0,
                end_time=3.0,
                speaker="Speaker 0"
            )
        ]
        
        identifier = SpeakerIdentifier(mock_llm_service)
        result = identifier.identify_speakers(segments, sample_metadata)
        
        assert result['speaker_mappings']['Speaker 0'] == "Host/Narrator"
        assert mock_llm_service.complete.call_count == 0  # No LLM call needed
    
    def test_empty_segments(self, mock_llm_service, sample_metadata):
        """Test handling of empty segments."""
        identifier = SpeakerIdentifier(mock_llm_service)
        result = identifier.identify_speakers([], sample_metadata)
        
        assert result['speaker_mappings'] == {}
        assert result['errors'] == ['No segments provided']
    
    def test_timeout_handling(self, mock_llm_service, sample_segments, sample_metadata):
        """Test timeout handling."""
        # Make LLM service slow
        import time
        mock_llm_service.complete = Mock(side_effect=lambda *args, **kwargs: time.sleep(5))
        
        identifier = SpeakerIdentifier(
            mock_llm_service,
            timeout_seconds=0.1  # Very short timeout
        )
        
        result = identifier.identify_speakers(sample_segments, sample_metadata)
        
        # Should fall back to descriptive roles
        assert len(result['speaker_mappings']) > 0
        assert 'errors' in result
        assert any('timeout' in error.lower() for error in result['errors'])
    
    def test_low_confidence_handling(self, mock_llm_service, sample_segments, sample_metadata):
        """Test handling of low confidence identifications."""
        mock_llm_service.complete = Mock(return_value=json.dumps({
            "speaker_mappings": {
                "Speaker 0": "Maybe John",
                "Speaker 1": "Unknown Guest"
            },
            "confidence_scores": {
                "Speaker 0": 0.4,  # Below threshold
                "Speaker 1": 0.3   # Below threshold
            },
            "identification_methods": {
                "Speaker 0": "Uncertain",
                "Speaker 1": "No clear identification"
            },
            "unresolved_speakers": ["Speaker 0", "Speaker 1"]
        }))
        
        identifier = SpeakerIdentifier(
            mock_llm_service,
            confidence_threshold=0.7
        )
        
        result = identifier.identify_speakers(sample_segments, sample_metadata)
        
        # Should convert to descriptive roles
        assert "Primary Speaker" in result['speaker_mappings']['Speaker 0']
        assert len(result['unresolved_speakers']) > 0
    
    def test_speaker_statistics_calculation(self, mock_llm_service, sample_segments):
        """Test speaker statistics calculation."""
        identifier = SpeakerIdentifier(mock_llm_service)
        stats = identifier._calculate_speaker_statistics(sample_segments)
        
        assert 'Speaker 0' in stats
        assert 'Speaker 1' in stats
        assert stats['Speaker 0']['turn_count'] == 2
        assert stats['Speaker 1']['turn_count'] == 1
        assert stats['Speaker 0']['speaking_time'] == 6.0  # 3s + 3s
        assert stats['Speaker 1']['speaking_time'] == 3.0
    
    def test_parse_llm_response_with_markdown(self, mock_llm_service):
        """Test parsing LLM response with markdown formatting."""
        identifier = SpeakerIdentifier(mock_llm_service)
        
        response = """```json
        {
            "speaker_mappings": {"Speaker 0": "Host"},
            "confidence_scores": {"Speaker 0": 0.8},
            "identification_methods": {"Speaker 0": "Pattern"},
            "unresolved_speakers": []
        }
        ```"""
        
        result = identifier._parse_llm_response(response)
        
        assert result['speaker_mappings']['Speaker 0'] == "Host"
        assert result['confidence_scores']['Speaker 0'] == 0.8
    
    def test_error_statistics_tracking(self, mock_llm_service):
        """Test error statistics tracking."""
        identifier = SpeakerIdentifier(mock_llm_service)
        
        # Simulate some errors
        identifier.error_counts['timeout'] = 3
        identifier.error_counts['JSONDecodeError'] = 1
        
        stats = identifier.get_error_statistics()
        
        assert stats['total_errors'] == 4
        assert stats['timeout_rate'] == 0.75
        assert stats['parse_error_rate'] == 0.25


class TestSpeakerDatabase:
    """Test cases for SpeakerDatabase class."""
    
    @pytest.fixture
    def temp_cache_dir(self, tmp_path):
        """Create temporary cache directory."""
        cache_dir = tmp_path / "speaker_cache"
        cache_dir.mkdir()
        return cache_dir
    
    def test_store_and_retrieve_speakers(self, temp_cache_dir):
        """Test storing and retrieving speaker information."""
        db = SpeakerDatabase(cache_dir=temp_cache_dir)
        
        # Store speakers
        db.store_speakers(
            'My Podcast',
            {'Speaker 0': 'Alice Host', 'Speaker 1': 'Bob Guest'},
            {'Speaker 0': 0.9, 'Speaker 1': 0.85}
        )
        
        # Retrieve speakers
        speakers = db.get_known_speakers('My Podcast')
        
        assert speakers is not None
        assert speakers['Speaker 0'] == 'Alice Host'
        assert speakers['Speaker 1'] == 'Bob Guest'
    
    def test_podcast_key_normalization(self, temp_cache_dir):
        """Test that similar podcast names map to same key."""
        db = SpeakerDatabase(cache_dir=temp_cache_dir)
        
        # Store with one variant
        db.store_speakers(
            'The Tech Talk Podcast',
            {'Speaker 0': 'Host'},
            {'Speaker 0': 0.9}
        )
        
        # Retrieve with different variant
        speakers = db.get_known_speakers('Tech Talk Show')
        
        # Should find the same data due to normalization
        assert speakers is not None
    
    def test_cache_expiration(self, temp_cache_dir):
        """Test cache expiration."""
        db = SpeakerDatabase(cache_dir=temp_cache_dir, ttl_days=0)  # Expire immediately
        
        db.store_speakers(
            'Expired Podcast',
            {'Speaker 0': 'Host'},
            {'Speaker 0': 0.9}
        )
        
        # Should return None due to expiration
        speakers = db.get_known_speakers('Expired Podcast')
        assert speakers is None
    
    def test_match_speakers(self, temp_cache_dir):
        """Test matching current speakers with known speakers."""
        db = SpeakerDatabase(cache_dir=temp_cache_dir)
        
        # Store known speakers
        db.store_speakers(
            'My Podcast',
            {'Speaker 0': 'Alice (Host)', 'Speaker 1': 'Bob (Co-host)'},
            {'Speaker 0': 0.9, 'Speaker 1': 0.85}
        )
        
        # Current speaker stats
        current_stats = {
            'Speaker 0': {'speaking_percentage': 60},
            'Speaker 1': {'speaking_percentage': 30},
            'Speaker 2': {'speaking_percentage': 10}
        }
        
        mappings, scores = db.match_speakers('My Podcast', current_stats)
        
        assert 'Speaker 0' in mappings
        assert 'host' in mappings['Speaker 0'].lower()
    
    def test_statistics(self, temp_cache_dir):
        """Test database statistics."""
        db = SpeakerDatabase(cache_dir=temp_cache_dir)
        
        # Store data for multiple podcasts
        db.store_speakers('Podcast 1', {'S0': 'Host1'}, {'S0': 0.9})
        db.store_speakers('Podcast 2', {'S0': 'Host2', 'S1': 'Guest'}, {'S0': 0.8, 'S1': 0.7})
        
        stats = db.get_statistics()
        
        assert stats['podcasts_cached'] == 2
        assert stats['total_speakers'] == 3
        assert stats['average_confidence'] > 0


class TestSpeakerMetrics:
    """Test cases for SpeakerIdentificationMetrics class."""
    
    @pytest.fixture
    def temp_metrics_dir(self, tmp_path):
        """Create temporary metrics directory."""
        metrics_dir = tmp_path / "metrics"
        metrics_dir.mkdir()
        return metrics_dir
    
    def test_record_identification(self, temp_metrics_dir):
        """Test recording identification metrics."""
        metrics = SpeakerIdentificationMetrics(metrics_dir=temp_metrics_dir, window_size=10)
        
        # Record successful identification
        result = {
            'speaker_mappings': {'S0': 'Host', 'S1': 'Guest'},
            'confidence_scores': {'S0': 0.9, 'S1': 0.8},
            'performance': {
                'cache_hit': False,
                'segments_processed': 100
            }
        }
        
        metrics.record_identification('My Podcast', result, 1.5)
        
        summary = metrics.get_summary()
        
        assert summary['overview']['total_identifications'] == 1
        assert summary['overview']['successful_identifications'] == 1
        assert summary['overview']['total_speakers_identified'] == 2
        assert summary['response_times']['avg_response_time_ms'] == 1500
    
    def test_cache_metrics_tracking(self, temp_metrics_dir):
        """Test cache hit rate tracking."""
        metrics = SpeakerIdentificationMetrics(metrics_dir=temp_metrics_dir)
        
        # Record mix of cache hits and misses
        for i in range(10):
            result = {
                'speaker_mappings': {'S0': 'Host'},
                'confidence_scores': {'S0': 0.9},
                'performance': {
                    'cache_hit': i % 3 == 0,  # Every 3rd is cache hit
                    'segments_processed': 50
                }
            }
            metrics.record_identification(f'Podcast {i}', result, 0.5)
        
        summary = metrics.get_summary()
        
        assert summary['cache_performance']['cache_hits'] == 4  # 0, 3, 6, 9
        assert summary['cache_performance']['recent_cache_hit_rate'] > 0
    
    def test_error_tracking(self, temp_metrics_dir):
        """Test error metrics tracking."""
        metrics = SpeakerIdentificationMetrics(metrics_dir=temp_metrics_dir)
        
        # Record various errors
        metrics.record_error('timeout', 'Podcast 1')
        metrics.record_error('timeout', 'Podcast 2')
        metrics.record_error('JSONDecodeError', 'Podcast 3')
        
        summary = metrics.get_summary()
        
        assert summary['llm_performance']['llm_timeouts'] == 2
        assert summary['llm_performance']['llm_errors'] == 1
        assert summary['error_breakdown']['timeout'] == 2
        assert summary['error_breakdown']['JSONDecodeError'] == 1
    
    def test_podcast_specific_metrics(self, temp_metrics_dir):
        """Test podcast-specific metrics tracking."""
        metrics = SpeakerIdentificationMetrics(metrics_dir=temp_metrics_dir)
        
        # Record multiple episodes for same podcast
        for i in range(5):
            result = {
                'speaker_mappings': {'S0': 'Host', 'S1': f'Guest{i}'},
                'confidence_scores': {'S0': 0.9, 'S1': 0.7 + i * 0.05},
                'performance': {'segments_processed': 100}
            }
            metrics.record_identification('Tech Talk', result, 1.0)
        
        podcast_metrics = metrics.get_podcast_metrics('Tech Talk')
        
        assert podcast_metrics['episodes_processed'] == 5
        assert podcast_metrics['successful_identifications'] == 5
        assert podcast_metrics['total_speakers_identified'] == 10
        assert podcast_metrics['avg_speakers_per_episode'] == 2.0
    
    def test_metrics_persistence(self, temp_metrics_dir):
        """Test metrics persistence to disk."""
        # Create and populate metrics
        metrics1 = SpeakerIdentificationMetrics(metrics_dir=temp_metrics_dir)
        
        result = {
            'speaker_mappings': {'S0': 'Host'},
            'confidence_scores': {'S0': 0.9},
            'performance': {'segments_processed': 100}
        }
        metrics1.record_identification('Test Podcast', result, 1.0)
        
        # Force persistence
        metrics1._persist_metrics()
        
        # Create new instance and check if data loaded
        metrics2 = SpeakerIdentificationMetrics(metrics_dir=temp_metrics_dir)
        
        summary = metrics2.get_summary()
        assert summary['overview']['total_identifications'] == 1
        
    def test_report_generation(self, temp_metrics_dir):
        """Test metrics report generation."""
        metrics = SpeakerIdentificationMetrics(metrics_dir=temp_metrics_dir)
        
        # Add some data
        for i in range(3):
            result = {
                'speaker_mappings': {'S0': 'Host'},
                'confidence_scores': {'S0': 0.8 + i * 0.05},
                'performance': {
                    'cache_hit': i > 0,
                    'segments_processed': 100
                }
            }
            metrics.record_identification(f'Podcast {i}', result, 1.0 + i * 0.2)
        
        report = metrics.generate_report()
        
        assert "Speaker Identification Metrics Report" in report
        assert "Total Identifications: 3" in report
        assert "Cache Performance" in report
        assert "Response Times" in report
        assert "Quality Metrics" in report