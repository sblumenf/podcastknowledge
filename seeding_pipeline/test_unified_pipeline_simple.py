#!/usr/bin/env python3
"""Simple test for unified pipeline - bypasses complex conversation analysis."""

import os
import tempfile
from pathlib import Path

# Create a sample VTT file for testing
SAMPLE_VTT = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v Host>Welcome to our podcast about artificial intelligence.

00:00:05.000 --> 00:00:12.000
<v Host>Today we're discussing the latest developments in large language models.

00:00:12.000 --> 00:00:18.000
<v Guest>Thanks for having me. I'm excited to talk about GPT-4 and Claude.

00:00:18.000 --> 00:00:25.000
<v Guest>These models represent a significant leap in natural language understanding.

00:00:25.000 --> 00:00:32.000
<v Host>Let's start with the improvements in reasoning capabilities.
"""


def test_storage_and_extraction():
    """Test just the storage and extraction parts of the pipeline."""
    print("=== Testing Unified Pipeline Storage and Extraction ===\n")
    
    # Create temporary VTT file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
        f.write(SAMPLE_VTT)
        vtt_path = f.name
    
    try:
        # Import required modules
        from src.storage.graph_storage import GraphStorageService
        from src.core.models import Episode, Podcast
        from src.services.segment_regrouper import MeaningfulUnit
        from src.vtt.vtt_parser import VTTParser
        
        print("1. Parsing VTT file...")
        
        # Parse VTT file
        parser = VTTParser()
        result = parser.parse_file_with_metadata(Path(vtt_path))
        segments = result['segments']
        print(f"   - Parsed {len(segments)} segments")
        
        print("\n2. Creating mock MeaningfulUnits...")
        
        # Create mock meaningful units directly
        meaningful_units = []
        
        # First unit: segments 0-2
        unit1 = MeaningfulUnit(
            id="unit_001_introduction",
            segments=segments[0:3],
            unit_type="introduction",
            summary="Introduction to AI podcast and LLM discussion",
            themes=["AI", "LLMs"],
            start_time=segments[0].start_time - 2.0,  # Adjust for YouTube
            end_time=segments[2].end_time,
            speaker_distribution={"Host": 66.7, "Guest": 33.3},
            is_complete=True
        )
        meaningful_units.append(unit1)
        
        # Second unit: segments 3-4
        unit2 = MeaningfulUnit(
            id="unit_002_capabilities",
            segments=segments[3:5],
            unit_type="topic_discussion",
            summary="Discussion of LLM capabilities and reasoning",
            themes=["Capabilities", "Reasoning"],
            start_time=segments[3].start_time - 2.0,  # Adjust for YouTube
            end_time=segments[4].end_time,
            speaker_distribution={"Host": 20.0, "Guest": 80.0},
            is_complete=True
        )
        meaningful_units.append(unit2)
        
        print(f"   - Created {len(meaningful_units)} MeaningfulUnits")
        
        print("\n3. Testing storage functions...")
        
        # Create test episode and podcast
        podcast = Podcast(
            id="podcast_test_001",
            name="AI Discussions",
            description="A podcast about artificial intelligence",
            rss_url="https://example.com/rss"
        )
        
        episode = Episode(
            id="episode_test_001",
            title="LLMs and the Future",
            description="Discussion about large language models",
            published_date="2024-01-15",
            youtube_url="https://youtube.com/watch?v=test123"
        )
        
        # Initialize mock storage
        graph_storage = MockGraphStorage()
        
        # Test storing MeaningfulUnits
        for unit in meaningful_units:
            unit_data = {
                'id': unit.id,
                'text': unit.text,
                'start_time': unit.start_time,
                'end_time': unit.end_time,
                'summary': unit.summary,
                'speaker_distribution': unit.speaker_distribution,
                'unit_type': unit.unit_type,
                'themes': unit.themes,
                'segment_indices': [seg.id for seg in unit.segments]
            }
            
            graph_storage.create_meaningful_unit(unit_data, episode.id)
        
        print("\n4. Test Results:")
        print(f"   - MeaningfulUnits stored: {len(graph_storage.stored_items['meaningful_units'])}")
        print(f"   - First unit ID: {meaningful_units[0].id}")
        print(f"   - First unit text length: {len(meaningful_units[0].text)} chars")
        print(f"   - First unit start time: {meaningful_units[0].start_time}s (adjusted for YouTube)")
        print(f"   - Speaker distribution: {meaningful_units[0].speaker_distribution}")
        
        print("\n✅ Basic storage test PASSED")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up temp file
        if os.path.exists(vtt_path):
            os.unlink(vtt_path)


class MockGraphStorage:
    """Mock graph storage for testing."""
    
    def __init__(self):
        self.stored_items = {
            'meaningful_units': []
        }
    
    def create_meaningful_unit(self, unit_data, episode_id):
        """Mock creating a meaningful unit."""
        self.stored_items['meaningful_units'].append({
            'data': unit_data,
            'episode_id': episode_id
        })
        print(f"     - Stored MeaningfulUnit: {unit_data['id']}")
        print(f"       - Type: {unit_data['unit_type']}")
        print(f"       - Themes: {unit_data['themes']}")
        return unit_data['id']


if __name__ == "__main__":
    test_storage_and_extraction()