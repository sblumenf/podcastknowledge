#!/usr/bin/env python3
"""Integration test for field consistency fixes.

This script tests the complete pipeline with a sample VTT file
to ensure field consistency issues are resolved.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline.unified_pipeline import UnifiedKnowledgePipeline
from src.storage.graph_storage import GraphStorageService
from src.services.llm import LLMService
from src.services.llm_gemini_direct import GeminiDirectService
from src.core.config import PipelineConfig
from src.utils.logging import get_logger

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = get_logger(__name__)


def test_field_consistency():
    """Test the pipeline with a sample VTT file."""
    
    # Initialize services
    logger.info("Initializing services...")
    
    # Use mock storage for testing
    class MockGraphStorage:
        """Mock storage that logs field access."""
        
        def __init__(self):
            self.entities_stored = []
            self.quotes_stored = []
            self.insights_stored = []
            
        def create_entity(self, entity_data, episode_id):
            """Mock entity creation that validates fields."""
            logger.info(f"Storing entity with fields: {list(entity_data.keys())}")
            
            # Verify 'value' field exists (not 'name')
            if 'value' not in entity_data:
                raise KeyError("Entity missing 'value' field")
            if 'type' not in entity_data:
                raise KeyError("Entity missing 'type' field")
                
            self.entities_stored.append(entity_data)
            return f"entity_{len(self.entities_stored)}"
            
        def create_quote(self, quote_data, episode_id, meaningful_unit_id):
            """Mock quote creation that validates fields."""
            logger.info(f"Storing quote with fields: {list(quote_data.keys())}")
            
            # Verify 'text' field exists (not 'value')
            if 'text' not in quote_data:
                raise KeyError("Quote missing 'text' field")
                
            self.quotes_stored.append(quote_data)
            return f"quote_{len(self.quotes_stored)}"
            
        def create_insight(self, insight_data, episode_id, meaningful_unit_id):
            """Mock insight creation that validates fields."""
            logger.info(f"Storing insight with fields: {list(insight_data.keys())}")
            
            # Verify 'text' field exists (for storage)
            if 'text' not in insight_data:
                raise KeyError("Insight missing 'text' field for storage")
                
            self.insights_stored.append(insight_data)
            return f"insight_{len(self.insights_stored)}"
            
        def create_relationship(self, source_id, target_id, rel_type, properties):
            """Mock relationship creation."""
            logger.info(f"Creating relationship: {source_id} -{rel_type}-> {target_id}")
            return "rel_1"
            
        def create_meaningful_unit(self, unit_data, episode_id):
            """Mock meaningful unit creation."""
            return f"unit_{unit_data.get('id', '1')}"
            
        def create_episode(self, episode_data, podcast_id):
            """Mock episode creation."""
            return "episode_1"
            
        def create_podcast(self, podcast_data):
            """Mock podcast creation."""
            return "podcast_1"
            
        def connect(self):
            """Mock connection."""
            pass
    
    # Initialize mock storage
    graph_storage = MockGraphStorage()
    
    # Initialize LLM service (use mock or real)
    try:
        llm_service = GeminiDirectService()
        logger.info("Using real Gemini service")
    except Exception as e:
        logger.warning(f"Could not initialize Gemini: {e}")
        # Create a mock LLM service
        class MockLLMService:
            def __init__(self):
                self.config = PipelineConfig()
                
            def generate(self, prompt, response_format=None, **kwargs):
                """Return mock extraction data."""
                return {
                    "entities": [
                        {"name": "Test Person", "type": "PERSON"},
                        {"name": "Test Company", "type": "ORGANIZATION"}
                    ],
                    "quotes": [
                        {"text": "This is a test quote", "speaker": "Test Person"}
                    ],
                    "insights": [
                        {"title": "Test Insight", "description": "This is a test insight"}
                    ],
                    "relationships": [
                        {"source": "Test Person", "target": "Test Company", "type": "WORKS_FOR"}
                    ],
                    "conversation_structure": {}
                }
        
        llm_service = MockLLMService()
        logger.info("Using mock LLM service")
    
    # Initialize pipeline
    pipeline = UnifiedKnowledgePipeline(
        graph_storage=graph_storage,
        llm_service=llm_service,
        enable_speaker_mapping=False
    )
    
    # Test with minimal VTT file
    vtt_path = Path("tests/fixtures/vtt_samples/minimal.vtt")
    if not vtt_path.exists():
        # Create a minimal test VTT
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
Speaker 1: Hello, this is a test of the knowledge extraction pipeline.

00:00:05.000 --> 00:00:10.000
Speaker 2: Great! Let's discuss artificial intelligence and its impact.

00:00:10.000 --> 00:00:15.000
Speaker 1: AI is transforming how we work and live.
"""
        vtt_path.parent.mkdir(parents=True, exist_ok=True)
        vtt_path.write_text(vtt_content)
        logger.info(f"Created test VTT file: {vtt_path}")
    
    # Process the VTT file
    logger.info(f"Processing VTT file: {vtt_path}")
    
    try:
        # Use the sync wrapper instead
        import asyncio
        
        async def run_pipeline():
            return await pipeline.process_vtt_file(
                vtt_path=vtt_path,
                episode_metadata={
                    "id": "test_episode",
                    "title": "Field Consistency Test Episode",
                    "description": "Testing field naming consistency",
                    "podcast_id": "test_podcast"
                }
            )
        
        result = asyncio.run(run_pipeline())
        
        logger.info("Pipeline processing completed successfully!")
        
        # Verify results
        logger.info(f"Entities stored: {len(graph_storage.entities_stored)}")
        logger.info(f"Quotes stored: {len(graph_storage.quotes_stored)}")
        logger.info(f"Insights stored: {len(graph_storage.insights_stored)}")
        
        # Check field names
        if graph_storage.entities_stored:
            entity = graph_storage.entities_stored[0]
            assert 'value' in entity, "Entity should have 'value' field"
            assert 'name' not in entity, "Entity should not have 'name' field"
            logger.info("✓ Entity field validation passed")
        
        if graph_storage.quotes_stored:
            quote = graph_storage.quotes_stored[0]
            assert 'text' in quote, "Quote should have 'text' field"
            assert 'value' not in quote, "Quote should not have 'value' field"
            logger.info("✓ Quote field validation passed")
        
        if graph_storage.insights_stored:
            insight = graph_storage.insights_stored[0]
            assert 'text' in insight, "Insight should have 'text' field for storage"
            logger.info("✓ Insight field validation passed")
        
        logger.info("\n✅ All field consistency tests passed!")
        return True
        
    except KeyError as e:
        logger.error(f"❌ Field consistency error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_field_consistency()
    sys.exit(0 if success else 1)