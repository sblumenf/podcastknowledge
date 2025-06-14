#!/usr/bin/env python3
"""Quick script to process a single VTT file through the pipeline."""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.seeding.orchestrator import VTTKnowledgeExtractor
from src.core.config import PipelineConfig, SeedingConfig
from src.seeding.transcript_ingestion import VTTFile
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)

def main():
    # Create pipeline
    config = SeedingConfig()
    
    pipeline = VTTKnowledgeExtractor(
        config=config
    )
    
    # Create VTTFile object
    vtt_path = Path("/home/sergeblumenfeld/podcastknowledge/transcriber/output/transcripts/The_Mel_Robbins_Podcast/2025-06-09_Finally_Feel_Good_in_Your_Body_4_Expert_Steps_to_Feeling_More_Confident_Today.vtt")
    
    # Calculate file hash
    import hashlib
    file_hash = hashlib.sha256(vtt_path.read_bytes()).hexdigest()
    
    vtt_file = VTTFile(
        path=vtt_path,
        podcast_name="The Mel Robbins Podcast",
        episode_title="Finally Feel Good in Your Body: 4 Expert Steps to Feeling More Confident Today",
        file_hash=file_hash,
        size_bytes=vtt_path.stat().st_size,
        created_at=datetime.fromtimestamp(vtt_path.stat().st_ctime)
    )
    
    try:
        results = pipeline.process_vtt_files([vtt_file])
        print(f"\nSuccess! Processed {vtt_path.name}")
        if results:
            print(f"Total segments processed: {results.get('total_segments', 0)}")
            print(f"Total entities extracted: {results.get('total_entities', 0)}")
            print(f"Total quotes extracted: {results.get('total_quotes', 0)}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pipeline.cleanup()

if __name__ == "__main__":
    main()