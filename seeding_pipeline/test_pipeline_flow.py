#!/usr/bin/env python3
"""Test the complete pipeline flow with a sample VTT file."""

import asyncio
import sys
from pathlib import Path
import logging
import os

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import main processing function
from main import process_vtt_file

async def test_pipeline():
    """Test the pipeline with a sample VTT file."""
    # Check for test VTT file
    vtt_path = Path("test_vtt/sample.vtt")
    if not vtt_path.exists():
        logger.error(f"Test VTT file not found: {vtt_path}")
        return 1
        
    # Set test environment variables if not already set
    if not os.getenv('NEO4J_URI'):
        os.environ['NEO4J_URI'] = 'neo4j://localhost:7687'
    if not os.getenv('NEO4J_USER'):
        os.environ['NEO4J_USER'] = 'neo4j'
    if not os.getenv('NEO4J_PASSWORD'):
        logger.error("NEO4J_PASSWORD environment variable must be set")
        return 1
    if not os.getenv('GEMINI_API_KEY'):
        logger.error("GEMINI_API_KEY environment variable must be set")
        return 1
        
    try:
        logger.info("Starting pipeline test...")
        logger.info(f"Processing VTT file: {vtt_path}")
        
        result = await process_vtt_file(
            vtt_path=vtt_path,
            podcast_name="Test Podcast",
            episode_title="Test Episode",
            episode_url="https://youtube.com/watch?v=test"
        )
        
        logger.info("Pipeline test completed successfully!")
        logger.info(f"Result status: {result.get('status')}")
        logger.info(f"Processing time: {result.get('processing_time', 0):.2f} seconds")
        
        # Display some statistics
        logger.info("\nProcessing Statistics:")
        logger.info(f"  Segments processed: {result.get('segments_processed', 0)}")
        logger.info(f"  Meaningful units created: {result.get('meaningful_units_created', 0)}")
        logger.info(f"  Entities extracted: {result.get('entities_extracted', 0)}")
        logger.info(f"  Quotes extracted: {result.get('quotes_extracted', 0)}")
        logger.info(f"  Insights extracted: {result.get('insights_extracted', 0)}")
        logger.info(f"  Relationships created: {result.get('relationships_created', 0)}")
        
        if result.get('errors'):
            logger.warning(f"\nErrors encountered: {len(result['errors'])}")
            for error in result['errors']:
                logger.warning(f"  - {error}")
                
        return 0
        
    except Exception as e:
        logger.error(f"Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(test_pipeline())
    sys.exit(exit_code)