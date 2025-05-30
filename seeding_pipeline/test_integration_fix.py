#!/usr/bin/env python3
"""Quick test to verify the VTT to knowledge extraction integration is fixed."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.seeding.transcript_ingestion import TranscriptIngestion
from src.core.config import PipelineConfig


def test_basic_parsing():
    """Test basic VTT parsing functionality."""
    
    # Create test VTT
    test_vtt = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v Alice>Let's discuss machine learning algorithms.

00:00:05.000 --> 00:00:10.000
<v Bob>Yes, especially neural networks and deep learning.
"""
    
    # Write test file
    test_file = Path("test.vtt")
    test_file.write_text(test_vtt)
    
    try:
        # Test parsing
        config = PipelineConfig()
        ingestion = TranscriptIngestion(config)
        result = ingestion.process_file(test_file)
        
        print("Parsing result:")
        print(f"  Status: {result['status']}")
        if result['status'] == 'success':
            print(f"  Segments: {result['segment_count']}")
            print(f"  Episode: {result['episode']['title']}")
            
            # Check segments
            segments = result.get('segments', [])
            for i, seg in enumerate(segments):
                print(f"\n  Segment {i+1}:")
                print(f"    Speaker: {seg.speaker}")
                print(f"    Text: {seg.text}")
                print(f"    Time: {seg.start_time} - {seg.end_time}")
        else:
            print(f"  Error: {result.get('error')}")
            
        return result['status'] == 'success'
        
    finally:
        test_file.unlink(missing_ok=True)


def test_knowledge_extraction():
    """Test that knowledge extraction is connected."""
    
    from src.core.config import PipelineConfig
    from src.seeding.orchestrator import PodcastKnowledgePipeline
    from src.seeding.transcript_ingestion import VTTFile
    from datetime import datetime
    
    # Create test VTT with rich content
    test_vtt = """WEBVTT

00:00:00.000 --> 00:00:10.000
<v Dr. Smith>Today we're discussing OpenAI's GPT-4 and how it's revolutionizing natural language processing.

00:00:10.000 --> 00:00:20.000
<v Prof. Johnson>Indeed, the transformer architecture has enabled remarkable advances in AI capabilities.

00:00:20.000 --> 00:00:30.000
<v Dr. Smith>Companies like Google, Microsoft, and Meta are all investing heavily in large language models.
"""
    
    # Write test file
    test_file = Path("test_knowledge.vtt")
    test_file.write_text(test_vtt)
    
    try:
        # Initialize pipeline
        config = PipelineConfig()
        config.log_level = "INFO"
        pipeline = PodcastKnowledgePipeline(config)
        
        print("\nInitializing components...")
        if not pipeline.initialize_components():
            print("Failed to initialize components!")
            return False
            
        # Create VTT file object
        vtt_file = VTTFile(
            path=test_file,
            podcast_name="AI Talks",
            episode_title="GPT-4 Discussion",
            file_hash="test123",
            size_bytes=len(test_vtt),
            created_at=datetime.now()
        )
        
        # Process through pipeline
        print("\nProcessing VTT file...")
        result = pipeline.process_vtt_files([vtt_file])
        
        print("\nExtraction Results:")
        print(f"  Files processed: {result['files_processed']}")
        print(f"  Total segments: {result['total_segments']}")
        print(f"  Total entities: {result['total_entities']}")
        print(f"  Total insights: {result['total_insights']}")
        
        success = result['files_processed'] > 0 and result['total_entities'] > 0
        
        if not success and result.get('errors'):
            print("\nErrors encountered:")
            for error in result['errors']:
                print(f"  - {error}")
                
        return success
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    print("=== Testing VTT Integration Fix ===\n")
    
    print("1. Testing basic VTT parsing:")
    parsing_ok = test_basic_parsing()
    
    print("\n" + "="*50 + "\n")
    
    print("2. Testing knowledge extraction integration:")
    extraction_ok = test_knowledge_extraction()
    
    print("\n" + "="*50 + "\n")
    
    if parsing_ok and extraction_ok:
        print("✅ All tests passed! Integration is working.")
    else:
        print("❌ Some tests failed. Check the output above.")
        
    sys.exit(0 if parsing_ok and extraction_ok else 1)