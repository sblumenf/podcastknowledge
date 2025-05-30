#!/usr/bin/env python3
"""Test script to verify VTT to knowledge extraction integration."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import PipelineConfig
from src.seeding.orchestrator import PodcastKnowledgePipeline
from src.seeding.transcript_ingestion import VTTFile
from src.processing.vtt_parser import VTTParser

def test_vtt_integration():
    """Test the complete VTT processing pipeline."""
    
    # Create test VTT content
    test_vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v Alice>Hello, let's talk about artificial intelligence today.

00:00:05.000 --> 00:00:10.000
<v Bob>That's a great topic! AI is transforming many industries.

00:00:10.000 --> 00:00:15.000
<v Alice>Yes, especially in healthcare and finance. Machine learning models are becoming very sophisticated.
"""
    
    # Create test VTT file
    test_dir = Path("test_vtt_files")
    test_dir.mkdir(exist_ok=True)
    test_file = test_dir / "test_episode.vtt"
    
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_vtt_content)
    
    print(f"Created test VTT file: {test_file}")
    
    try:
        # Create minimal config
        config = PipelineConfig()
        config.use_large_context = False
        config.log_level = "DEBUG"
        
        # Initialize pipeline
        print("\nInitializing pipeline...")
        pipeline = PodcastKnowledgePipeline(config)
        
        # Initialize components
        if not pipeline.initialize_components():
            print("ERROR: Failed to initialize components")
            return False
        
        print("Pipeline initialized successfully")
        
        # Process the VTT file through the full pipeline
        print("\nProcessing VTT file...")
        result = pipeline.process_vtt_files(
            [VTTFile(
                path=test_file,
                podcast_name="Test Podcast",
                episode_title="AI Discussion",
                file_hash="test_hash",
                size_bytes=len(test_vtt_content),
                created_at=None,
                metadata={}
            )],
            use_large_context=False
        )
        
        print("\nProcessing Results:")
        print(f"Files processed: {result['files_processed']}")
        print(f"Total segments: {result['total_segments']}")
        print(f"Total entities: {result['total_entities']}")
        print(f"Total insights: {result['total_insights']}")
        print(f"Total relationships: {result['total_relationships']}")
        
        if result['files_failed'] > 0:
            print(f"\nErrors: {result['errors']}")
        
        # Test direct parsing
        print("\n\nTesting direct VTT parsing:")
        parser = VTTParser()
        segments = parser.parse_file(test_file)
        print(f"Parsed {len(segments)} segments:")
        for seg in segments:
            print(f"  {seg.speaker}: {seg.text[:50]}...")
        
        return result['files_processed'] > 0
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()
        if test_dir.exists():
            test_dir.rmdir()
        print("\nTest files cleaned up")

if __name__ == "__main__":
    print("=== VTT Integration Test ===")
    success = test_vtt_integration()
    sys.exit(0 if success else 1)