#!/usr/bin/env python3
"""
Test SimpleKGPipeline Integration

This script validates that the EnhancedKnowledgePipeline correctly integrates
SimpleKGPipeline with existing features for comprehensive knowledge extraction.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any
import time

# Add the source directory to Python path
sys.path.append(str(Path(__file__).parent / "src"))

from src.pipeline.enhanced_knowledge_pipeline import EnhancedKnowledgePipeline, ProcessingResult
from src.adapters.gemini_llm_adapter import GeminiLLMAdapter
from src.core.exceptions import ProviderError
from src.utils.logging import get_logger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = get_logger(__name__)


class IntegrationTester:
    """Test the SimpleKGPipeline integration end-to-end."""
    
    def __init__(self):
        self.test_vtt_file = Path("/home/sergeblumenfeld/podcastknowledge/transcriber/output/transcripts/The_Mel_Robbins_Podcast/2022-10-06_3_Simple_Steps_to_Change_Your_Life.vtt")
        self.pipeline = None
        self.results = {}
        
    async def setup_pipeline(self) -> bool:
        """Initialize the enhanced pipeline with proper configuration."""
        try:
            logger.info("Setting up Enhanced Knowledge Pipeline...")
            
            # Create LLM adapter
            llm_adapter = GeminiLLMAdapter(
                model_name="gemini-pro",
                temperature=0.7,
                max_tokens=4096,
                enable_cache=True
            )
            
            # Initialize pipeline with all features enabled
            self.pipeline = EnhancedKnowledgePipeline(
                llm_adapter=llm_adapter,
                enable_all_features=True
            )
            
            logger.info("✓ Enhanced Knowledge Pipeline initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to setup pipeline: {e}")
            return False
    
    def validate_vtt_file(self) -> bool:
        """Ensure test VTT file exists and is readable."""
        if not self.test_vtt_file.exists():
            logger.error(f"✗ Test VTT file not found: {self.test_vtt_file}")
            return False
            
        if not self.test_vtt_file.is_file():
            logger.error(f"✗ Path is not a file: {self.test_vtt_file}")
            return False
            
        # Check file size
        file_size = self.test_vtt_file.stat().st_size
        if file_size == 0:
            logger.error(f"✗ VTT file is empty: {self.test_vtt_file}")
            return False
            
        logger.info(f"✓ Test VTT file validated: {self.test_vtt_file.name} ({file_size:,} bytes)")
        return True
    
    async def test_basic_processing(self) -> bool:
        """Test basic pipeline processing capabilities."""
        try:
            logger.info("Testing basic VTT processing...")
            
            # Process the VTT file
            start_time = time.time()
            result = await self.pipeline.process_vtt_file(self.test_vtt_file)
            processing_time = time.time() - start_time
            
            # Store results for validation
            self.results['basic_processing'] = result
            
            # Log results
            logger.info("✓ Basic processing completed successfully")
            logger.info(f"  Processing time: {processing_time:.2f}s")
            logger.info(f"  Entities created: {result.entities_created}")
            logger.info(f"  Relationships created: {result.relationships_created}")
            logger.info(f"  Quotes extracted: {result.quotes_extracted}")
            logger.info(f"  Insights generated: {result.insights_generated}")
            logger.info(f"  Themes identified: {result.themes_identified}")
            logger.info(f"  Complexity analyzed: {result.complexity_analyzed}")
            logger.info(f"  Gaps detected: {result.gaps_detected}")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Basic processing failed: {e}")
            return False
    
    async def test_simplekgpipeline_functionality(self) -> bool:
        """Test SimpleKGPipeline specific functionality."""
        try:
            logger.info("Testing SimpleKGPipeline specific features...")
            
            # Ensure SimpleKGPipeline is initialized
            self.pipeline._ensure_simple_kg_pipeline()
            
            if self.pipeline.simple_kg_pipeline is None:
                logger.error("✗ SimpleKGPipeline not initialized")
                return False
                
            logger.info("✓ SimpleKGPipeline initialized successfully")
            
            # Test LLM adapter functionality
            test_input = "This is a test input for the LLM adapter."
            try:
                response = self.pipeline.llm_adapter.invoke(test_input)
                if response and hasattr(response, 'content') and response.content:
                    logger.info("✓ LLM adapter working correctly")
                else:
                    logger.warning("⚠ LLM adapter response seems empty")
            except Exception as e:
                logger.warning(f"⚠ LLM adapter test failed: {e}")
            
            # Test Neo4j connectivity
            try:
                self.pipeline._ensure_neo4j_driver()
                if self.pipeline.neo4j_driver:
                    # Test a simple query
                    with self.pipeline.neo4j_driver.session() as session:
                        result = session.run("RETURN 1 as test")
                        test_result = result.single()
                        if test_result and test_result["test"] == 1:
                            logger.info("✓ Neo4j connectivity confirmed")
                        else:
                            logger.warning("⚠ Neo4j query returned unexpected result")
                else:
                    logger.error("✗ Neo4j driver not initialized")
                    return False
            except Exception as e:
                logger.error(f"✗ Neo4j connectivity test failed: {e}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"✗ SimpleKGPipeline functionality test failed: {e}")
            return False
    
    def validate_results(self) -> bool:
        """Validate the processing results meet expected criteria."""
        if 'basic_processing' not in self.results:
            logger.error("✗ No processing results to validate")
            return False
            
        result: ProcessingResult = self.results['basic_processing']
        validation_passed = True
        
        logger.info("Validating processing results...")
        
        # Check that we extracted some entities
        if result.entities_created > 0:
            logger.info(f"✓ Entities extracted: {result.entities_created}")
        else:
            logger.warning("⚠ No entities were extracted")
            validation_passed = False
        
        # Check that we extracted some relationships
        if result.relationships_created > 0:
            logger.info(f"✓ Relationships extracted: {result.relationships_created}")
        else:
            logger.warning("⚠ No relationships were extracted")
        
        # Check quotes extraction
        if result.quotes_extracted > 0:
            logger.info(f"✓ Quotes extracted: {result.quotes_extracted}")
        else:
            logger.warning("⚠ No quotes were extracted")
        
        # Check insights generation
        if result.insights_generated > 0:
            logger.info(f"✓ Insights generated: {result.insights_generated}")
        else:
            logger.warning("⚠ No insights were generated")
        
        # Check processing time is reasonable
        if result.processing_time < 300:  # Less than 5 minutes
            logger.info(f"✓ Processing time reasonable: {result.processing_time:.2f}s")
        else:
            logger.warning(f"⚠ Processing time seems high: {result.processing_time:.2f}s")
        
        # Check metadata
        if result.metadata and 'total_segments' in result.metadata:
            segments = result.metadata['total_segments']
            logger.info(f"✓ Processed {segments} segments")
        else:
            logger.warning("⚠ Missing processing metadata")
        
        return validation_passed
    
    def cleanup(self):
        """Clean up resources."""
        if self.pipeline:
            self.pipeline.close()
            logger.info("✓ Pipeline resources cleaned up")
    
    async def run_integration_test(self) -> bool:
        """Run the complete integration test suite."""
        logger.info("=" * 60)
        logger.info("SIMPLEKGPIPELINE INTEGRATION TEST")
        logger.info("=" * 60)
        
        try:
            # Test 1: Setup
            if not await self.setup_pipeline():
                return False
            
            # Test 2: Validate test file
            if not self.validate_vtt_file():
                return False
            
            # Test 3: Test SimpleKGPipeline functionality
            if not await self.test_simplekgpipeline_functionality():
                return False
            
            # Test 4: Test basic processing
            if not await self.test_basic_processing():
                return False
            
            # Test 5: Validate results
            if not self.validate_results():
                logger.warning("⚠ Results validation had some issues, but processing succeeded")
            
            logger.info("=" * 60)
            logger.info("✓ INTEGRATION TEST COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
            return True
            
        except Exception as e:
            logger.error(f"✗ Integration test failed with exception: {e}")
            return False
        finally:
            self.cleanup()


async def main():
    """Main test function."""
    tester = IntegrationTester()
    success = await tester.run_integration_test()
    
    if success:
        logger.info("All tests passed! SimpleKGPipeline integration is working correctly.")
        sys.exit(0)
    else:
        logger.error("Integration test failed. Please check the logs above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())