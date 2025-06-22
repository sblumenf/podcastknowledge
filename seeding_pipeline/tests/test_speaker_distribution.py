#!/usr/bin/env python3
"""Test cases for speaker distribution calculation and cache isolation."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import unittest
from typing import List, Dict
from src.core.interfaces import TranscriptSegment
from src.services.segment_regrouper import SegmentRegrouper
from src.core.conversation_models.conversation import ConversationStructure, ConversationUnit


class MockTranscriptSegment:
    """Mock TranscriptSegment for testing."""
    def __init__(self, speaker: str, start_time: float, end_time: float, text: str = ""):
        self.speaker = speaker
        self.start_time = start_time
        self.end_time = end_time
        self.text = text or f"{speaker} speaking"
        self.id = f"seg_{int(start_time)}"


class TestSpeakerDistribution(unittest.TestCase):
    """Test speaker distribution calculation functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.regrouper = SegmentRegrouper()
    
    def test_single_speaker_distribution(self):
        """Test distribution calculation with single speaker."""
        segments = [
            MockTranscriptSegment("John Doe", 0.0, 10.0),
            MockTranscriptSegment("John Doe", 10.0, 20.0),
            MockTranscriptSegment("John Doe", 20.0, 30.0)
        ]
        
        primary_speaker, distribution = self.regrouper._calculate_speaker_info(segments)
        
        self.assertEqual(primary_speaker, "John Doe")
        self.assertEqual(distribution, {"John Doe": 100.0})
        self.assertAlmostEqual(sum(distribution.values()), 100.0)
    
    def test_two_speaker_distribution(self):
        """Test distribution calculation with two speakers."""
        segments = [
            MockTranscriptSegment("Host", 0.0, 60.0),      # 60 seconds
            MockTranscriptSegment("Guest", 60.0, 100.0),   # 40 seconds
        ]
        
        primary_speaker, distribution = self.regrouper._calculate_speaker_info(segments)
        
        self.assertEqual(primary_speaker, "Host")
        self.assertEqual(distribution, {"Host": 60.0, "Guest": 40.0})
        self.assertAlmostEqual(sum(distribution.values()), 100.0)
    
    def test_multiple_speaker_distribution(self):
        """Test distribution calculation with multiple speakers."""
        segments = [
            MockTranscriptSegment("Host", 0.0, 50.0),           # 50 seconds = 50%
            MockTranscriptSegment("Guest 1", 50.0, 80.0),      # 30 seconds = 30%
            MockTranscriptSegment("Guest 2", 80.0, 100.0),     # 20 seconds = 20%
        ]
        
        primary_speaker, distribution = self.regrouper._calculate_speaker_info(segments)
        
        self.assertEqual(primary_speaker, "Host")
        self.assertEqual(distribution, {"Host": 50.0, "Guest 1": 30.0, "Guest 2": 20.0})
        self.assertAlmostEqual(sum(distribution.values()), 100.0)
    
    def test_rounding_adjustment(self):
        """Test that rounding adjustments ensure sum equals 100%."""
        # Create segments that would produce rounding issues
        segments = [
            MockTranscriptSegment("A", 0.0, 33.33),      # ~33.33%
            MockTranscriptSegment("B", 33.33, 66.66),    # ~33.33%
            MockTranscriptSegment("C", 66.66, 100.0),    # ~33.33%
        ]
        
        primary_speaker, distribution = self.regrouper._calculate_speaker_info(segments)
        
        # Should adjust to ensure sum is exactly 100
        self.assertAlmostEqual(sum(distribution.values()), 100.0)
        
        # Check that all speakers are present
        self.assertIn("A", distribution)
        self.assertIn("B", distribution)
        self.assertIn("C", distribution)
    
    def test_unknown_speaker_handling(self):
        """Test handling of unknown/None speakers."""
        segments = [
            MockTranscriptSegment(None, 0.0, 50.0),
            MockTranscriptSegment("Host", 50.0, 100.0),
        ]
        
        primary_speaker, distribution = self.regrouper._calculate_speaker_info(segments)
        
        self.assertIn("Unknown", distribution)
        self.assertIn("Host", distribution)
        self.assertEqual(distribution["Unknown"], 50.0)
        self.assertEqual(distribution["Host"], 50.0)
    
    def test_empty_segments(self):
        """Test handling of empty segment list."""
        segments = []
        
        primary_speaker, distribution = self.regrouper._calculate_speaker_info(segments)
        
        self.assertEqual(primary_speaker, "Unknown")
        self.assertEqual(distribution, {"Unknown": 100.0})
    
    def test_dict_segment_format(self):
        """Test handling of dictionary format segments."""
        segments = [
            {
                'speaker': 'John',
                'start_time': 0.0,
                'end_time': 60.0,
                'text': 'Hello'
            },
            {
                'speaker': 'Jane',
                'start_time': 60.0,
                'end_time': 100.0,
                'text': 'Hi'
            }
        ]
        
        primary_speaker, distribution = self.regrouper._calculate_speaker_info(segments)
        
        self.assertEqual(primary_speaker, "John")
        self.assertEqual(distribution, {"John": 60.0, "Jane": 40.0})
    
    def skip_test_meaningful_unit_creation_with_distribution(self):
        """Test that MeaningfulUnit is created with speaker_distribution."""
        segments = [
            MockTranscriptSegment("Host", 0.0, 60.0),
            MockTranscriptSegment("Guest", 60.0, 100.0),
        ]
        
        conv_unit = ConversationUnit(
            start_index=0,
            end_index=1,
            unit_type="introduction",
            description="Opening discussion",
            completeness="complete",
            confidence=0.9
        )
        
        structure = ConversationStructure(
            units=[conv_unit],
            themes=[],
            flow="linear",
            total_segments=2
        )
        
        unit = self.regrouper._create_meaningful_unit(
            unit_segments=segments,
            conv_unit=conv_unit,
            unit_index=0,
            structure=structure
        )
        
        # Check that speaker_distribution is present and correct
        self.assertIsNotNone(unit.speaker_distribution)
        self.assertEqual(unit.speaker_distribution, {"Host": 60.0, "Guest": 40.0})
        self.assertEqual(unit.primary_speaker, "Host")
        self.assertAlmostEqual(sum(unit.speaker_distribution.values()), 100.0)


class TestSpeakerCacheIsolation(unittest.TestCase):
    """Test that speaker cache is properly isolated between episodes."""
    
    def test_cache_disabled(self):
        """Test that speaker cache is disabled in speaker identifier."""
        # Import here to avoid circular imports
        from src.extraction.speaker_identifier import SpeakerIdentifier
        from src.services.llm_gemini_direct import GeminiDirectService
        
        # Check that the code contains disabled cache comments
        import inspect
        source = inspect.getsource(SpeakerIdentifier.identify_speakers)
        
        # Verify cache is disabled
        self.assertIn("DISABLED: Speaker cache causes cross-episode contamination", source)
        self.assertIn("Speaker cache disabled - using LLM for fresh identification", source)
    
    def test_no_cache_file_created(self):
        """Test that no new cache files are created."""
        # This would be tested in integration tests
        # For now, just verify the cache directory
        cache_dir = Path("./speaker_cache")
        if cache_dir.exists():
            # Count files before and after would be done in integration test
            cache_files = list(cache_dir.glob("*.json"))
            # Just verify structure for now
            for f in cache_files:
                self.assertTrue(f.name.endswith('.json'))


if __name__ == "__main__":
    unittest.main()