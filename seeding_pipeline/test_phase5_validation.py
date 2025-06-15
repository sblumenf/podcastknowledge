#!/usr/bin/env python3
"""
Phase 5 Validation Test Script
Verifies that all Phase 5 analysis integration works as expected.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    
    try:
        # Test analysis module imports
        from src.analysis import analysis_orchestrator
        from src.analysis import diversity_metrics
        from src.analysis import gap_detection
        from src.analysis import missing_links
        print("✅ Analysis modules imported successfully")
        
        # Test pipeline imports
        from src.pipeline.unified_pipeline import UnifiedKnowledgePipeline
        print("✅ Unified pipeline imported successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_analysis_functions():
    """Test that analysis functions exist and have correct signatures."""
    print("\nTesting analysis function signatures...")
    
    try:
        from src.analysis.gap_detection import run_gap_detection
        from src.analysis.diversity_metrics import run_diversity_analysis
        from src.analysis.missing_links import run_missing_link_analysis
        from src.analysis.analysis_orchestrator import run_knowledge_discovery
        
        import inspect
        
        # Check run_gap_detection signature
        sig = inspect.signature(run_gap_detection)
        assert 'episode_id' in sig.parameters
        assert 'session' in sig.parameters
        print("✅ gap_detection.run_gap_detection has correct signature")
        
        # Check run_diversity_analysis signature
        sig = inspect.signature(run_diversity_analysis)
        assert 'episode_id' in sig.parameters
        assert 'session' in sig.parameters
        print("✅ diversity_metrics.run_diversity_analysis has correct signature")
        
        # Check run_missing_link_analysis signature
        sig = inspect.signature(run_missing_link_analysis)
        assert 'episode_id' in sig.parameters
        assert 'session' in sig.parameters
        print("✅ missing_links.run_missing_link_analysis has correct signature")
        
        # Check orchestrator signature
        sig = inspect.signature(run_knowledge_discovery)
        assert 'episode_id' in sig.parameters
        assert 'session' in sig.parameters
        print("✅ analysis_orchestrator.run_knowledge_discovery has correct signature")
        
        return True
    except Exception as e:
        print(f"❌ Function signature error: {e}")
        return False

def test_pipeline_integration():
    """Test that the pipeline integrates analysis correctly."""
    print("\nTesting pipeline integration...")
    
    try:
        from src.pipeline.unified_pipeline import UnifiedKnowledgePipeline
        
        # Check that _run_analysis method exists
        assert hasattr(UnifiedKnowledgePipeline, '_run_analysis')
        
        # Check imports in pipeline file
        with open('src/pipeline/unified_pipeline.py', 'r') as f:
            content = f.read()
            
        # Verify analysis imports
        assert 'from src.analysis import analysis_orchestrator' in content
        assert 'from src.analysis import diversity_metrics' in content
        assert 'from src.analysis import gap_detection' in content
        assert 'from src.analysis import missing_links' in content
        print("✅ Pipeline has all required analysis imports")
        
        # Verify orchestrator is called
        assert 'analysis_orchestrator.run_knowledge_discovery' in content
        print("✅ Pipeline calls analysis orchestrator")
        
        # Verify conversation_structure parameter in _store_episode_structure
        assert '_store_episode_structure(episode_metadata, meaningful_units, conversation_structure)' in content
        print("✅ Pipeline passes conversation_structure for Topic creation")
        
        return True
    except Exception as e:
        print(f"❌ Pipeline integration error: {e}")
        return False

def test_storage_integration():
    """Test that storage integration supports analysis requirements."""
    print("\nTesting storage integration...")
    
    try:
        from src.storage.graph_storage import GraphStorageService
        
        # Check that create_topic_for_episode method exists
        assert hasattr(GraphStorageService, 'create_topic_for_episode')
        print("✅ GraphStorageService has create_topic_for_episode method")
        
        return True
    except Exception as e:
        print(f"❌ Storage integration error: {e}")
        return False

def main():
    """Run all validation tests."""
    print("Phase 5 Validation Test")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_analysis_functions,
        test_pipeline_integration,
        test_storage_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All Phase 5 validations PASSED!")
        return True
    else:
        print("❌ Some Phase 5 validations FAILED!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)