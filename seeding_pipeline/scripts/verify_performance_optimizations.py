#!/usr/bin/env python3
"""
Script to verify that performance optimizations are active in the pipeline.

This script checks:
1. Combined extraction method is available
2. Parallel processing is configured
3. Sentiment analysis has error handling
4. Performance benchmarking is working
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline.unified_pipeline import UnifiedKnowledgePipeline
from src.extraction.extraction import KnowledgeExtractor
from src.extraction.sentiment_analyzer import SentimentAnalyzer
from src.core.pipeline_config import PipelineConfig
from src.monitoring.pipeline_benchmarking import get_benchmark


def verify_combined_extraction():
    """Verify combined extraction is available."""
    print("\n1. Checking Combined Extraction...")
    
    # Create a knowledge extractor (mocked services)
    from unittest.mock import Mock
    extractor = KnowledgeExtractor(
        llm_service=Mock(),
        embedding_service=Mock()
    )
    
    # Check if combined method exists
    has_combined = hasattr(extractor, 'extract_knowledge_combined')
    
    if has_combined:
        print("   ✅ Combined extraction method found: extract_knowledge_combined")
    else:
        print("   ❌ Combined extraction method NOT found!")
        
    # Check for individual methods (should exist as fallback)
    methods = ['extract_entities', 'extract_quotes', 'extract_relationships', 'extract_insights']
    for method in methods:
        if hasattr(extractor, method):
            print(f"   ℹ️  Fallback method found: {method}")
    
    return has_combined


def verify_parallel_processing():
    """Verify parallel processing configuration."""
    print("\n2. Checking Parallel Processing Configuration...")
    
    # Check MAX_CONCURRENT_UNITS setting
    max_concurrent = PipelineConfig.MAX_CONCURRENT_UNITS
    print(f"   ℹ️  MAX_CONCURRENT_UNITS = {max_concurrent}")
    
    if max_concurrent > 1:
        print(f"   ✅ Parallel processing enabled with {max_concurrent} concurrent units")
    else:
        print("   ❌ Parallel processing appears disabled (MAX_CONCURRENT_UNITS = 1)")
    
    # Check timeout configuration
    timeout = PipelineConfig.KNOWLEDGE_EXTRACTION_TIMEOUT
    print(f"   ℹ️  KNOWLEDGE_EXTRACTION_TIMEOUT = {timeout}s ({timeout/60:.1f} minutes)")
    
    return max_concurrent > 1


def verify_sentiment_error_handling():
    """Verify sentiment analysis has proper error handling."""
    print("\n3. Checking Sentiment Analysis Error Handling...")
    
    from unittest.mock import Mock
    
    # Create sentiment analyzer
    analyzer = SentimentAnalyzer(llm_service=Mock())
    
    # Check for error handling methods
    has_analyze_text = hasattr(analyzer, '_analyze_text_sentiment')
    has_fallback = hasattr(analyzer, '_fallback_sentiment_analysis')
    has_text_conversion = hasattr(analyzer, '_convert_text_to_score')
    
    if has_analyze_text:
        print("   ✅ Main analysis method found: _analyze_text_sentiment")
    if has_fallback:
        print("   ✅ Fallback method found: _fallback_sentiment_analysis")
    if has_text_conversion:
        print("   ✅ Text-to-score conversion found: _convert_text_to_score")
    
    # Test error handling with None response
    try:
        mock_llm = Mock()
        mock_llm.complete_with_options = Mock(return_value=None)
        analyzer.llm_service = mock_llm
        
        # This should not crash
        from src.services.segment_regrouper import MeaningfulUnit
        from src.core.interfaces import TranscriptSegment
        
        test_unit = MeaningfulUnit(
            id="test",
            segments=[TranscriptSegment(
                id="seg1",
                start_time=0.0,
                end_time=10.0,
                text="Test",
                speaker="Speaker1"
            )],
            unit_type="test",
            summary="test",
            themes=[],
            start_time=0.0,
            end_time=10.0,
            primary_speaker="Speaker1",
            is_complete=True
        )
        
        result = analyzer.analyze_meaningful_unit(test_unit, {})
        print("   ✅ Handles None response without crashing")
    except Exception as e:
        print(f"   ❌ Failed to handle None response: {e}")
        return False
    
    return True


def verify_benchmarking():
    """Verify performance benchmarking is available."""
    print("\n4. Checking Performance Benchmarking...")
    
    # Get benchmark instance
    benchmark = get_benchmark()
    
    # Check methods exist
    has_start_episode = hasattr(benchmark, 'start_episode')
    has_track_unit = hasattr(benchmark, 'track_unit_processing')
    has_generate_summary = hasattr(benchmark, 'generate_summary')
    
    if has_start_episode:
        print("   ✅ Episode tracking found: start_episode")
    if has_track_unit:
        print("   ✅ Unit tracking found: track_unit_processing")
    if has_generate_summary:
        print("   ✅ Summary generation found: generate_summary")
    
    # Test basic functionality
    try:
        benchmark.start_episode("test_episode")
        benchmark.start_phase("test_phase")
        benchmark.end_phase("test_phase")
        summary = benchmark.generate_summary()
        print("   ✅ Benchmarking functionality works correctly")
    except Exception as e:
        print(f"   ❌ Benchmarking error: {e}")
        return False
    
    return True


def check_pipeline_structure():
    """Check UnifiedKnowledgePipeline structure."""
    print("\n5. Checking Pipeline Structure...")
    
    from unittest.mock import Mock
    
    # Create pipeline with mocks
    pipeline = UnifiedKnowledgePipeline(
        graph_storage=Mock(),
        llm_service=Mock()
    )
    
    # Check key methods exist
    methods = {
        '_process_single_unit': 'Unit processing method',
        '_extract_knowledge': 'Knowledge extraction orchestrator',
        '_start_phase': 'Phase tracking start',
        '_end_phase': 'Phase tracking end'
    }
    
    all_good = True
    for method, description in methods.items():
        if hasattr(pipeline, method):
            print(f"   ✅ {description} found: {method}")
        else:
            print(f"   ❌ {description} NOT found: {method}")
            all_good = False
    
    return all_good


def main():
    """Run all verification checks."""
    print("Performance Optimization Verification")
    print("=" * 50)
    
    results = {
        'Combined Extraction': verify_combined_extraction(),
        'Parallel Processing': verify_parallel_processing(),
        'Sentiment Error Handling': verify_sentiment_error_handling(),
        'Performance Benchmarking': verify_benchmarking(),
        'Pipeline Structure': check_pipeline_structure()
    }
    
    print("\n" + "=" * 50)
    print("Summary:")
    print("=" * 50)
    
    all_passed = True
    for feature, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{feature:.<30} {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 50)
    
    if all_passed:
        print("🎉 All performance optimizations are active!")
        return 0
    else:
        print("⚠️  Some optimizations are missing or not working correctly.")
        return 1


if __name__ == "__main__":
    sys.exit(main())