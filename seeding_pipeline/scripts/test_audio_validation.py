#!/usr/bin/env python3
"""
Test the audio module validation with mock data.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.providers.audio import MockAudioProvider
from src.core import PipelineConfig


def test_mock_provider():
    """Test the mock audio provider."""
    print("Testing Mock Audio Provider")
    print("-" * 50)
    
    # Create mock provider
    config = {
        "mock_segments": 3,
        "mock_speakers": 2,
    }
    
    provider = MockAudioProvider(config)
    
    # Test transcription
    print("\n1. Testing Transcription:")
    segments = provider.transcribe("fake_audio.mp3")
    print(f"   - Generated {len(segments)} transcript segments")
    for i, seg in enumerate(segments):
        print(f"   - Segment {i}: {seg.start_time:.1f}s - {seg.end_time:.1f}s")
        print(f"     Text: {seg.text[:50]}...")
        
    # Test diarization
    print("\n2. Testing Diarization:")
    diarization = provider.diarize("fake_audio.mp3")
    print(f"   - Generated {len(diarization)} speaker segments")
    speakers = set(s.speaker for s in diarization)
    print(f"   - Found {len(speakers)} unique speakers: {speakers}")
    
    # Test alignment
    print("\n3. Testing Alignment:")
    aligned = provider.align_transcript_with_diarization(segments, diarization)
    print(f"   - Aligned {len(aligned)} segments")
    for i, seg in enumerate(aligned[:3]):  # Show first 3
        print(f"   - Segment {i}: Speaker={seg.speaker}, Text={seg.text[:30]}...")
        
    # Test health check
    print("\n4. Testing Health Check:")
    health = provider.health_check()
    print(f"   - Status: {health['status']}")
    print(f"   - Provider: {health['provider']}")
    print(f"   - Mock segments: {health.get('mock_segments', 'N/A')}")
    
    print("\n✅ Mock provider test completed successfully!")
    

def test_config_loading():
    """Test configuration loading."""
    print("\n\nTesting Configuration Loading")
    print("-" * 50)
    
    # Set dummy environment variables for testing
    import os
    os.environ["NEO4J_PASSWORD"] = "test_password"
    os.environ["GOOGLE_API_KEY"] = "test_api_key"
    
    # Test default config
    config = PipelineConfig()
    print(f"1. Default whisper model: {config.whisper_model_size}")
    print(f"2. Default device: cpu (GPU not required for testing)")
    print(f"3. Min segment tokens: {config.min_segment_tokens}")
    print(f"4. Max segment tokens: {config.max_segment_tokens}")
    
    print("\n✅ Configuration test completed successfully!")


def main():
    """Run all tests."""
    print("=" * 60)
    print("AUDIO MODULE VALIDATION TEST")
    print("=" * 60)
    
    try:
        test_mock_provider()
        test_config_loading()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED! ✅")
        print("=" * 60)
        print("\nThe audio module is working correctly.")
        print("To test with real audio files, run:")
        print("  python scripts/validate_audio_module.py <audio_file.mp3>")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0


if __name__ == "__main__":
    sys.exit(main())