#!/usr/bin/env python3
"""
Simple Pipeline Validation Script for Phase 6 Task 6.2

Validates pipeline structure and capability without requiring live database connections.
Performs simple pass/fail validation as specified in the plan.
"""

import sys
import os
from pathlib import Path

# Add the project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_pipeline_imports():
    """Test that all pipeline components can be imported."""
    print("Testing pipeline component imports...")
    
    try:
        from src.pipeline.unified_pipeline import UnifiedKnowledgePipeline
        print("✅ UnifiedKnowledgePipeline imported successfully")
        
        from src.storage.graph_storage import GraphStorageService
        print("✅ GraphStorageService imported successfully")
        
        from src.services.llm import LLMService
        print("✅ LLMService imported successfully")
        
        from src.services.embeddings import EmbeddingsService
        print("✅ EmbeddingsService imported successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_pipeline_instantiation():
    """Test that pipeline class can be imported and has correct structure."""
    print("\nTesting pipeline class structure...")
    
    try:
        from src.pipeline.unified_pipeline import UnifiedKnowledgePipeline
        
        # Check class exists and has constructor
        if hasattr(UnifiedKnowledgePipeline, '__init__'):
            print("✅ Pipeline class has constructor")
        else:
            print("❌ Pipeline class missing constructor")
            return False, None
        
        # Check constructor signature
        import inspect
        sig = inspect.signature(UnifiedKnowledgePipeline.__init__)
        
        required_params = ['graph_storage', 'llm_service']
        for param in required_params:
            if param in sig.parameters:
                print(f"✅ Constructor has {param} parameter")
            else:
                print(f"❌ Constructor missing {param} parameter")
                return False, None
        
        print("✅ Pipeline class structure validated")
        return True, UnifiedKnowledgePipeline
        
    except Exception as e:
        print(f"❌ Pipeline class validation failed: {e}")
        return False, None


def test_pipeline_methods():
    """Test that pipeline has all required methods."""
    print("\nTesting pipeline methods...")
    
    try:
        success, pipeline_class = test_pipeline_instantiation()
        if not success:
            return False
        
        # Check required methods exist on the class
        required_methods = [
            'process_vtt_file',
            '_parse_vtt',
            '_identify_speakers', 
            '_analyze_conversation',
            '_create_meaningful_units',
            '_store_episode_structure',
            '_extract_knowledge',
            '_store_knowledge',
            '_run_analysis'
        ]
        
        for method in required_methods:
            if hasattr(pipeline_class, method):
                print(f"✅ Method {method} exists")
            else:
                print(f"❌ Method {method} missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Method validation failed: {e}")
        return False


def test_vtt_file_exists():
    """Test that the comprehensive test VTT file exists and is valid."""
    print("\nTesting VTT file...")
    
    try:
        vtt_path = Path("test_data/comprehensive_test_episode.vtt")
        
        if not vtt_path.exists():
            print(f"❌ VTT file not found: {vtt_path}")
            return False
        
        # Read and validate basic VTT structure
        with open(vtt_path, 'r') as f:
            content = f.read()
        
        # Check basic VTT format
        if not content.startswith('WEBVTT'):
            print("❌ Invalid VTT format - missing WEBVTT header")
            return False
        
        # Check for speaker tags
        speaker_count = content.count('<v ')
        if speaker_count < 4:  # We expect 4 speakers
            print(f"❌ Expected at least 4 speakers, found {speaker_count}")
            return False
        
        # Check for timestamps
        timestamp_count = content.count('-->')
        if timestamp_count < 10:  # Should have many timestamps
            print(f"❌ Expected multiple timestamps, found {timestamp_count}")
            return False
        
        print(f"✅ VTT file valid - {speaker_count} speaker tags, {timestamp_count} timestamps")
        return True
        
    except Exception as e:
        print(f"❌ VTT validation failed: {e}")
        return False


def test_expected_extractions_documented():
    """Test that expected extractions are documented."""
    print("\nTesting expected extractions documentation...")
    
    try:
        doc_path = Path("test_data/comprehensive_test_episode_expected_extractions.md")
        
        if not doc_path.exists():
            print(f"❌ Expected extractions doc not found: {doc_path}")
            return False
        
        with open(doc_path, 'r') as f:
            content = f.read()
        
        # Check for key sections
        required_sections = [
            "Expected Speaker Identification",
            "Expected Entity Types",
            "Expected Quote Types", 
            "Expected Relationship Types",
            "Expected Insight Types",
            "Expected Themes/Topics",
            "Expected Analysis Results"
        ]
        
        for section in required_sections:
            if section in content:
                print(f"✅ Section '{section}' documented")
            else:
                print(f"❌ Section '{section}' missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Documentation validation failed: {e}")
        return False


def test_analysis_modules():
    """Test that all analysis modules can be imported."""
    print("\nTesting analysis module imports...")
    
    try:
        from src.analysis import analysis_orchestrator
        print("✅ analysis_orchestrator imported")
        
        from src.analysis import diversity_metrics
        print("✅ diversity_metrics imported")
        
        from src.analysis import gap_detection
        print("✅ gap_detection imported")
        
        from src.analysis import missing_links
        print("✅ missing_links imported")
        
        # Check key functions exist
        functions_to_check = [
            (analysis_orchestrator, 'run_knowledge_discovery'),
            (diversity_metrics, 'run_diversity_analysis'),
            (gap_detection, 'run_gap_detection'),
            (missing_links, 'run_missing_link_analysis')
        ]
        
        for module, func_name in functions_to_check:
            if hasattr(module, func_name):
                print(f"✅ Function {func_name} exists in {module.__name__}")
            else:
                print(f"❌ Function {func_name} missing from {module.__name__}")
                return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Analysis module import failed: {e}")
        return False


def test_storage_methods():
    """Test that storage service has required methods."""
    print("\nTesting storage service methods...")
    
    try:
        from src.storage.graph_storage import GraphStorageService
        
        # Check required methods exist
        required_methods = [
            'create_episode',
            'create_meaningful_unit',
            'create_entity',
            'create_quote',
            'create_insight',
            'create_sentiment',
            'create_topic_for_episode'
        ]
        
        for method in required_methods:
            if hasattr(GraphStorageService, method):
                print(f"✅ Storage method {method} exists")
            else:
                print(f"❌ Storage method {method} missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Storage method validation failed: {e}")
        return False


def main():
    """Run all validation tests."""
    print("Phase 6 Task 6.2: Simple Pipeline Validation")
    print("="*50)
    print("Note: This validates pipeline structure without requiring live database connections")
    print()
    
    tests = [
        ("Pipeline Imports", test_pipeline_imports),
        ("Pipeline Methods", test_pipeline_methods),
        ("VTT Test File", test_vtt_file_exists),
        ("Expected Extractions Doc", test_expected_extractions_documented),
        ("Analysis Modules", test_analysis_modules),
        ("Storage Methods", test_storage_methods)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 20)
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "="*50)
    print("VALIDATION SUMMARY")
    print("="*50)
    print(f"Passed: {passed}/{total} tests")
    
    if passed == total:
        print("🎉 ALL VALIDATIONS PASSED!")
        print("Pipeline structure is ready for end-to-end testing.")
        print("\nNext steps:")
        print("1. Ensure Neo4j is running")
        print("2. Configure environment variables")
        print("3. Run full end-to-end test with live database")
        return True
    else:
        print("❌ Some validations failed.")
        print("Fix the issues above before proceeding.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)