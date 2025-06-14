#!/usr/bin/env python3
"""
Test the Enhanced Knowledge Pipeline without LLM dependencies.

This test validates the pipeline integration and features by bypassing
the SimpleKGPipeline LLM requirement and directly testing the integration
framework and advanced features.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.pipeline.enhanced_knowledge_pipeline import EnhancedKnowledgePipeline
from src.storage.graph_storage import GraphStorageService
from src.vtt.vtt_parser import VTTParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_pipeline_features():
    """Test the enhanced features without LLM dependency."""
    
    print("=" * 80)
    print("ENHANCED KNOWLEDGE PIPELINE - FEATURE INTEGRATION TEST")
    print("=" * 80)
    
    # Test VTT file
    vtt_file = Path("test_data/hour_podcast_test.vtt")
    if not vtt_file.exists():
        print(f"❌ Test VTT file not found: {vtt_file}")
        return False
    
    print(f"📁 Using test file: {vtt_file}")
    
    try:
        print("\n🚀 Phase 1: Testing VTT Parsing...")
        
        # Test VTT parsing directly
        parser = VTTParser()
        segments = parser.parse_file(vtt_file)
        print(f"✅ Parsed {len(segments)} segments from VTT file")
        
        print("\n🔗 Phase 2: Testing Neo4j Connection...")
        
        # Test Neo4j connection
        graph_storage = GraphStorageService(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password",
            database="neo4j"
        )
        
        try:
            graph_storage.connect()
            print("✅ Neo4j connection established")
        except Exception as e:
            print(f"❌ Neo4j connection failed: {e}")
            print("💡 Make sure Neo4j is running at bolt://localhost:7687")
            return False
        
        print("\n📊 Phase 3: Testing Enhanced Features...")
        
        # Initialize pipeline with features enabled but bypass LLM 
        pipeline = EnhancedKnowledgePipeline(
            llm_adapter=None,  # Skip LLM initialization
            enable_all_features=True,
            neo4j_config={
                "uri": "bolt://localhost:7687",
                "username": "neo4j",
                "password": "password",
                "database": "neo4j"
            }
        )
        
        # Test individual feature components
        start_time = time.time()
        
        print("  🔍 Testing theme extraction...")
        combined_text = " ".join([segment.text for segment in segments[:10]])  # Use first 10 segments
        themes = pipeline._extract_themes_from_text(combined_text)
        print(f"    ✅ Extracted {len(themes)} themes: {[t['name'] for t in themes[:3]]}")
        
        print("  🔍 Testing gap detection...")
        gaps = pipeline._analyze_knowledge_gaps(segments[:10])
        print(f"    ✅ Detected {len(gaps)} knowledge gaps: {[g['type'] for g in gaps[:3]]}")
        
        print("  🔍 Testing complexity analysis...")
        complexity_analyzed = False
        if hasattr(pipeline, 'complexity_analyzer') and pipeline.complexity_analyzer:
            try:
                complexity = pipeline.complexity_analyzer.classify_segment_complexity(segments[0].text)
                complexity_analyzed = True
                print(f"    ✅ Complexity analysis working: score={complexity.complexity_score:.2f}")
            except Exception as e:
                print(f"    ⚠️  Complexity analysis failed: {e}")
        else:
            print("    ⚠️  Complexity analyzer not available")
        
        print("  🔍 Testing quote extraction...")
        quotes_count = 0
        if hasattr(pipeline, 'knowledge_extractor') and pipeline.knowledge_extractor:
            try:
                from src.core.models import Segment
                test_segment = Segment(
                    id="test_seg_1",
                    text=segments[0].text,
                    start_time=0.0,
                    end_time=5.0,
                    speaker="TestSpeaker"
                )
                result = pipeline.knowledge_extractor.extract_knowledge(test_segment)
                quotes_count = len(result.quotes) if result.quotes else 0
                print(f"    ✅ Quote extraction working: extracted {quotes_count} quotes")
            except Exception as e:
                print(f"    ⚠️  Quote extraction failed: {e}")
        
        processing_time = time.time() - start_time
        
        print(f"\n📈 Phase 4: Feature Test Results (completed in {processing_time:.2f}s)")
        print("=" * 60)
        print(f"🎯 Themes Extracted: {len(themes)}")
        print(f"❓ Knowledge Gaps Detected: {len(gaps)}")
        print(f"💬 Quotes Extracted: {quotes_count}")
        print(f"🧠 Complexity Analysis: {'✅ Working' if complexity_analyzed else '❌ Not Working'}")
        print(f"📊 VTT Segments Parsed: {len(segments)}")
        print(f"⏱️  Processing Time: {processing_time:.2f}s")
        
        print(f"\n✅ Phase 5: Feature Integration Assessment")
        print("=" * 60)
        
        # Check feature integration success criteria
        success_criteria = {
            "vtt_parsing": (len(segments) >= 50, f"Expected ≥50 segments, got {len(segments)}"),
            "themes_extracted": (len(themes) >= 2, f"Expected ≥2 themes, got {len(themes)}"),
            "gap_detection": (len(gaps) >= 1, f"Expected ≥1 gaps, got {len(gaps)}"),
            "neo4j_connection": (True, "Neo4j connection working"),
            "processing_time": (processing_time < 60, f"Should complete in <1min, took {processing_time:.1f}s"),
            "pipeline_initialization": (pipeline is not None, "Pipeline initialized successfully")
        }
        
        all_passed = True
        for criterion, (passed, message) in success_criteria.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {status}: {criterion.replace('_', ' ').title()} - {message}")
            if not passed:
                all_passed = False
        
        print(f"\n🎯 FEATURE INTEGRATION ASSESSMENT")
        print("=" * 80)
        
        if all_passed:
            print("🎉 SUCCESS: All feature integration tests passed!")
            print("✅ VTT parsing working correctly")
            print("✅ Theme extraction functional")  
            print("✅ Gap detection operational")
            print("✅ Neo4j connectivity established")
            print("✅ Enhanced features ready for SimpleKGPipeline integration")
            
            print(f"\n💡 Next Steps:")
            print("   • Configure valid Gemini API key for LLM functionality")
            print("   • Test complete pipeline with SimpleKGPipeline entity extraction")
            print("   • Validate full end-to-end knowledge graph creation")
            
            return True
        else:
            print("⚠️  PARTIAL SUCCESS: Some feature tests failed")
            print("💡 Review failed criteria above and fix issues")
            return False
        
    except Exception as e:
        print(f"\n❌ FEATURE TEST FAILED: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False
    
    finally:
        # Cleanup
        try:
            if 'graph_storage' in locals():
                graph_storage.disconnect()
            if 'pipeline' in locals():
                pipeline.close()
            print("\n🧹 Test resources cleaned up")
        except:
            pass


async def main():
    """Main test execution."""
    print("Starting Enhanced Knowledge Pipeline Feature Integration Test...")
    
    success = await test_pipeline_features()
    
    if success:
        print(f"\n🎉 FEATURE INTEGRATION TEST COMPLETED SUCCESSFULLY")
        sys.exit(0)
    else:
        print(f"\n❌ FEATURE INTEGRATION TEST FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())