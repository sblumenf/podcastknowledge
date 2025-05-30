"""
Example: Processing VTT Files with Knowledge Extraction

This example shows how to process VTT transcript files through the complete
knowledge extraction pipeline, from parsing to graph storage.
"""

import os
from pathlib import Path
from src.core.config import PipelineConfig
from src.seeding.orchestrator import PodcastKnowledgePipeline


def process_vtt_folder_example():
    """Example of processing a folder of VTT files."""
    
    # Configure the pipeline
    config = PipelineConfig()
    config.log_level = "INFO"
    config.use_large_context = True
    config.merge_short_segments = True
    config.min_segment_duration = 2.0
    
    # Initialize the pipeline
    pipeline = PodcastKnowledgePipeline(config)
    
    # Initialize all components (providers, extractors, etc.)
    if not pipeline.initialize_components():
        print("Failed to initialize pipeline components")
        return
    
    # Process a directory of VTT files
    vtt_directory = Path("data/transcripts")
    result = pipeline.process_vtt_directory(
        vtt_directory,
        pattern="*.vtt",
        recursive=True,
        use_large_context=True
    )
    
    # Display results
    print(f"Processing Summary:")
    print(f"  Files processed: {result['files_processed']}")
    print(f"  Files failed: {result['files_failed']}")
    print(f"  Total segments: {result['total_segments']}")
    print(f"  Total entities extracted: {result['total_entities']}")
    print(f"  Total insights: {result['total_insights']}")
    print(f"  Total relationships: {result['total_relationships']}")
    
    # Clean up
    pipeline.cleanup()


def process_single_vtt_example():
    """Example of processing a single VTT file."""
    
    from src.seeding.transcript_ingestion import TranscriptIngestion
    from src.processing.extraction import KnowledgeExtractor
    from src.providers.llm.base import LLMProvider
    from src.factories.provider_factory import ProviderFactory
    
    # Set up configuration
    config = PipelineConfig()
    
    # Initialize providers
    factory = ProviderFactory()
    llm_provider = factory.create_llm_provider(config)
    
    # Initialize components
    ingestion = TranscriptIngestion(config)
    extractor = KnowledgeExtractor(llm_provider, config)
    
    # Process VTT file
    vtt_file = "podcast_episode_001.vtt"
    result = ingestion.process_file(vtt_file)
    
    if result['status'] == 'success':
        # Extract knowledge from segments
        segments = result['segments']
        extraction = extractor.extract_from_segments(
            segments,
            podcast_name="My Podcast",
            episode_title=result['episode']['title']
        )
        
        print(f"Extracted:")
        print(f"  {len(extraction['entities'])} entities")
        print(f"  {len(extraction['insights'])} insights")
        print(f"  {len(extraction['quotes'])} quotes")
        
        # Entity examples
        for entity in extraction['entities'][:3]:
            print(f"\nEntity: {entity['name']} ({entity['type']})")
            print(f"  Importance: {entity['importance_score']}")
            print(f"  Context: {entity['context'][:100]}...")


def custom_processing_example():
    """Example of custom processing with specific configurations."""
    
    # Custom configuration
    config = PipelineConfig()
    config.use_schemaless_extraction = True  # Use schemaless mode
    config.entity_resolution_threshold = 0.85  # Higher threshold for entity matching
    config.max_properties_per_node = 50  # Allow more properties per node
    
    # Initialize pipeline with custom config
    pipeline = PodcastKnowledgePipeline(config)
    pipeline.initialize_components()
    
    # Process with custom metadata
    from src.seeding.transcript_ingestion import VTTFile
    from datetime import datetime
    
    vtt_file = VTTFile(
        path=Path("episode_123.vtt"),
        podcast_name="Tech Talks",
        episode_title="Future of AI",
        file_hash="abc123",
        size_bytes=1024,
        created_at=datetime.now(),
        metadata={
            "tags": ["AI", "Technology", "Future"],
            "guests": ["Dr. Smith", "Prof. Johnson"],
            "episode_number": 123
        }
    )
    
    # Process with custom metadata
    result = pipeline.process_vtt_files([vtt_file])
    
    print("Custom processing complete!")


if __name__ == "__main__":
    # Run the examples
    print("=== VTT Processing Examples ===\n")
    
    print("1. Processing a folder of VTT files:")
    process_vtt_folder_example()
    
    print("\n2. Processing a single VTT file:")
    process_single_vtt_example()
    
    print("\n3. Custom processing configuration:")
    custom_processing_example()