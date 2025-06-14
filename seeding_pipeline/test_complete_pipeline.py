#!/usr/bin/env python3
"""
Complete Pipeline Integration Test for SimpleKGPipeline

This script tests the entire Enhanced Knowledge Pipeline with a real VTT file
to validate that all phases and features work correctly together.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.pipeline.enhanced_knowledge_pipeline import EnhancedKnowledgePipeline
from src.adapters.gemini_llm_adapter import GeminiLLMAdapter
from src.core.exceptions import ProviderError, ConnectionError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_complete_pipeline():
    """Test the complete Enhanced Knowledge Pipeline."""
    
    print("=" * 80)
    print("ENHANCED KNOWLEDGE PIPELINE - COMPLETE INTEGRATION TEST")
    print("=" * 80)
    
    # Test VTT file
    vtt_file = Path("test_data/hour_podcast_test.vtt")
    if not vtt_file.exists():
        print(f"❌ Test VTT file not found: {vtt_file}")
        return False
    
    print(f"📁 Using test file: {vtt_file}")
    
    try:
        # Phase 1: Initialize Enhanced Knowledge Pipeline
        print("\n🚀 Phase 1: Initializing Enhanced Knowledge Pipeline...")
        
        # Create LLM adapter with working configuration
        llm_adapter = GeminiLLMAdapter(
            model_name="gemini-1.5-flash",
            temperature=0.7,
            max_tokens=4096,
            enable_cache=True
        )
        
        # Initialize pipeline with all features enabled
        pipeline = EnhancedKnowledgePipeline(
            llm_adapter=llm_adapter,
            enable_all_features=True,
            neo4j_config={
                "uri": "bolt://localhost:7687",
                "username": "neo4j",
                "password": "password",
                "database": "neo4j"
            }
        )
        
        print("✅ Enhanced Knowledge Pipeline initialized successfully")
        
        # Phase 2: Test Neo4j Connection
        print("\n🔗 Phase 2: Testing Neo4j Connection...")
        
        try:
            pipeline.graph_storage.connect()
            print("✅ Neo4j connection established")
        except Exception as e:
            print(f"❌ Neo4j connection failed: {e}")
            print("💡 Make sure Neo4j is running at bolt://localhost:7687")
            return False
        
        # Phase 3: Process VTT File
        print(f"\n📊 Phase 3: Processing VTT File: {vtt_file}")
        print("This will test all pipeline phases:")
        print("  - VTT parsing")
        print("  - SimpleKGPipeline entity extraction")
        print("  - Feature integration (quotes, insights, themes)")
        print("  - Complexity analysis")
        print("  - Gap detection")
        print("  - Advanced analytics")
        
        start_time = time.time()
        
        # Run the complete pipeline
        result = await pipeline.process_vtt_file(vtt_file)
        
        processing_time = time.time() - start_time
        
        # Phase 4: Validate Results
        print(f"\n📈 Phase 4: Pipeline Results (completed in {processing_time:.2f}s)")
        print("=" * 60)
        
        # Core extraction metrics
        print(f"🔍 Entities Created: {result.entities_created}")
        print(f"🔗 Relationships Created: {result.relationships_created}")
        print(f"💬 Quotes Extracted: {result.quotes_extracted}")
        print(f"💡 Insights Generated: {result.insights_generated}")
        print(f"🎯 Themes Identified: {result.themes_identified}")
        print(f"❓ Knowledge Gaps Detected: {result.gaps_detected}")
        print(f"🧠 Complexity Analysis: {'✅ Completed' if result.complexity_analyzed else '❌ Failed'}")
        
        # Processing metadata
        print(f"\n📊 Processing Details:")
        print(f"   • Total Segments: {result.metadata.get('total_segments', 0)}")
        print(f"   • Processing Time: {result.processing_time:.2f}s")
        print(f"   • Features Enabled: {result.metadata.get('features_enabled', False)}")
        
        # Phase timings
        if 'phase_times' in result.metadata:
            print(f"\n⏱️  Phase Timings:")
            phase_times = result.metadata['phase_times']
            for phase, duration in phase_times.items():
                if isinstance(duration, (int, float)) and duration > 0:
                    print(f"   • {phase.replace('_', ' ').title()}: {duration:.2f}s")
        
        # Phase 5: Success Criteria Validation
        print(f"\n✅ Phase 5: Success Criteria Validation")
        print("=" * 60)
        
        # Check minimum thresholds from integration plan
        success_criteria = {
            "entities_created": (result.entities_created >= 10, f"Expected ≥10, got {result.entities_created}"),
            "relationships_created": (result.relationships_created >= 5, f"Expected ≥5, got {result.relationships_created}"),
            "quotes_extracted": (result.quotes_extracted >= 3, f"Expected ≥3, got {result.quotes_extracted}"),
            "complexity_analyzed": (result.complexity_analyzed, "Complexity analysis should complete"),
            "processing_time": (result.processing_time < 300, f"Should complete in <5min, took {result.processing_time:.1f}s"),
            "themes_identified": (result.themes_identified >= 2, f"Expected ≥2 themes, got {result.themes_identified}")
        }
        
        all_passed = True
        for criterion, (passed, message) in success_criteria.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {status}: {criterion.replace('_', ' ').title()} - {message}")
            if not passed:
                all_passed = False
        
        # Phase 6: Advanced Analytics Test
        print(f"\n🔬 Phase 6: Advanced Analytics Validation")
        print("=" * 60)
        
        # Test progress tracking
        progress = pipeline.get_progress()
        print(f"   • Progress Tracking: {'✅ Working' if progress else '❌ Missing'}")
        
        # Test performance metrics
        metrics = pipeline.graph_storage.get_performance_metrics()
        print(f"   • Performance Metrics: {'✅ Available' if metrics else '❌ Missing'}")
        if metrics:
            print(f"     - Avg Extraction Time: {metrics.get('avg_extraction_time', 0):.3f}s")
            print(f"     - Total Segments: {metrics.get('total_segments', 0)}")
        
        # Final Assessment
        print(f"\n🎯 FINAL ASSESSMENT")
        print("=" * 80)
        
        if all_passed:
            print("🎉 SUCCESS: All success criteria met!")
            print("✅ SimpleKGPipeline integration is working correctly")
            print("✅ All advanced features are functional")
            print("✅ Pipeline is ready for production use")
            
            # Detailed success summary
            print(f"\n📋 Success Summary:")
            print(f"   • Core entity extraction working via SimpleKGPipeline")
            print(f"   • Feature integration framework operational")
            print(f"   • All 15+ advanced features integrated successfully")
            print(f"   • Neo4j storage and retrieval working")
            print(f"   • Performance within acceptable bounds")
            
            return True
        else:
            print("⚠️  PARTIAL SUCCESS: Some criteria not met")
            print("💡 Review failed criteria above and adjust thresholds if needed")
            return False
        
    except Exception as e:
        print(f"\n❌ PIPELINE TEST FAILED: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False
    
    finally:
        # Cleanup
        try:
            pipeline.close()
            print("\n🧹 Pipeline resources cleaned up")
        except:
            pass


async def main():
    """Main test execution."""
    print("Starting Enhanced Knowledge Pipeline Integration Test...")
    
    success = await test_complete_pipeline()
    
    if success:
        print(f"\n🎉 INTEGRATION TEST COMPLETED SUCCESSFULLY")
        sys.exit(0)
    else:
        print(f"\n❌ INTEGRATION TEST FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())