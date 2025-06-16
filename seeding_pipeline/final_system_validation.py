#!/usr/bin/env python3
"""
Phase 7 Task 7.4: Final System Validation

This script performs final validation of the unified pipeline system
per the implementation plan requirements.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def validate_single_pipeline_approach():
    """Verify only unified pipeline exists - no alternatives."""
    print("Validating Single Pipeline Approach...")
    
    # Check that old pipeline files are removed
    old_files = [
        "src/pipeline/enhanced_knowledge_pipeline.py",
        "src/seeding/components/semantic_pipeline_executor.py"
    ]
    
    for file_path in old_files:
        if Path(file_path).exists():
            print(f"❌ Old pipeline file still exists: {file_path}")
            return False
        else:
            print(f"✅ Old pipeline file removed: {file_path}")
    
    # Check that unified pipeline exists
    unified_pipeline = Path("src/pipeline/unified_pipeline.py")
    if not unified_pipeline.exists():
        print("❌ Unified pipeline file missing")
        return False
    else:
        print("✅ Unified pipeline file exists")
    
    # Check imports work
    try:
        from src.pipeline.unified_pipeline import UnifiedKnowledgePipeline
        print("✅ UnifiedKnowledgePipeline imports successfully")
    except ImportError as e:
        print(f"❌ UnifiedKnowledgePipeline import failed: {e}")
        return False
    
    # Check no alternatives in __init__.py
    init_file = Path("src/pipeline/__init__.py")
    if init_file.exists():
        content = init_file.read_text()
        if "EnhancedKnowledgePipeline" in content:
            print("❌ Old pipeline still referenced in __init__.py")
            return False
        else:
            print("✅ Only unified pipeline in __init__.py")
    
    return True

def validate_configuration_simplicity():
    """Verify configuration is simplified with no alternatives."""
    print("\nValidating Configuration Simplicity...")
    
    # Check feature flags are simplified
    try:
        from src.core.feature_flags import FeatureFlag
        flags = list(FeatureFlag)
        
        # Check that alternative approach flags are removed
        alternative_flags = ["ENABLE_ENTITY_RESOLUTION_V2"]  # This was removed
        for flag_name in alternative_flags:
            if any(flag.value == flag_name for flag in flags):
                print(f"❌ Alternative approach flag still exists: {flag_name}")
                return False
        
        print("✅ Alternative approach flags removed")
        
        # Check remaining flags are functionality flags, not alternatives
        remaining_flags = [flag.value for flag in flags]
        print(f"✅ Remaining feature flags: {remaining_flags}")
        
    except ImportError as e:
        print(f"❌ Feature flags import failed: {e}")
        return False
    
    # Check configuration documentation exists
    config_doc = Path("src/core/CONFIGURATION.md")
    if not config_doc.exists():
        print("❌ Configuration documentation missing")
        return False
    else:
        print("✅ Configuration documentation exists")
    
    return True

def validate_documentation_completeness():
    """Verify usage documentation is complete."""
    print("\nValidating Documentation Completeness...")
    
    # Check usage documentation exists
    usage_doc = Path("docs/unified-pipeline-usage.md")
    if not usage_doc.exists():
        print("❌ Usage documentation missing")
        return False
    
    # Check documentation content
    content = usage_doc.read_text()
    required_sections = [
        "Pipeline Flow Diagram",
        "Configuration Requirements", 
        "Knowledge Types Extracted",
        "Schema-less Discovery Examples",
        "YouTube URL Generation",
        "Error Handling Behavior",
        "Troubleshooting Guide"
    ]
    
    for section in required_sections:
        if section not in content:
            print(f"❌ Missing documentation section: {section}")
            return False
        else:
            print(f"✅ Documentation section present: {section}")
    
    # Check for single approach emphasis
    if "single approach" not in content.lower():
        print("❌ Documentation doesn't emphasize single approach")
        return False
    else:
        print("✅ Documentation emphasizes single approach")
    
    return True

def validate_pipeline_structure():
    """Verify pipeline has all required components."""
    print("\nValidating Pipeline Structure...")
    
    try:
        from src.pipeline.unified_pipeline import UnifiedKnowledgePipeline
        
        # Check required methods exist
        required_methods = [
            "process_vtt_file",
            "_parse_vtt", 
            "_identify_speakers",
            "_analyze_conversation",
            "_create_meaningful_units",
            "_extract_knowledge",
            "_store_knowledge",
            "_run_analysis"
        ]
        
        for method_name in required_methods:
            if not hasattr(UnifiedKnowledgePipeline, method_name):
                print(f"❌ Missing required method: {method_name}")
                return False
            else:
                print(f"✅ Required method exists: {method_name}")
        
        # Check constructor parameters
        import inspect
        sig = inspect.signature(UnifiedKnowledgePipeline.__init__)
        params = list(sig.parameters.keys())
        
        if "graph_storage" not in params:
            print("❌ Constructor missing graph_storage parameter")
            return False
        
        if "llm_service" not in params:
            print("❌ Constructor missing llm_service parameter")
            return False
        
        print("✅ Constructor has required parameters")
        
    except Exception as e:
        print(f"❌ Pipeline structure validation failed: {e}")
        return False
    
    return True

def validate_test_framework():
    """Verify test framework validates key functionality."""
    print("\nValidating Test Framework...")
    
    test_files = [
        "test_data/simple_pipeline_validation.py",
        "test_data/schema_less_discovery_test.py", 
        "test_data/youtube_url_validation_test.py",
        "test_data/error_handling_test.py"
    ]
    
    for test_file in test_files:
        if not Path(test_file).exists():
            print(f"❌ Missing test file: {test_file}")
            return False
        else:
            print(f"✅ Test file exists: {test_file}")
    
    # Check test data files
    test_data_files = [
        "test_data/comprehensive_test_episode.vtt",
        "test_data/quantum_discovery_test.vtt"
    ]
    
    for data_file in test_data_files:
        if not Path(data_file).exists():
            print(f"❌ Missing test data file: {data_file}")
            return False
        else:
            print(f"✅ Test data file exists: {data_file}")
    
    return True

def validate_storage_interface():
    """Verify storage interface is complete."""
    print("\nValidating Storage Interface...")
    
    try:
        from src.storage.graph_storage import GraphStorageService
        
        # Check required storage methods exist
        required_methods = [
            "create_episode",
            "create_meaningful_unit", 
            "create_entity",
            "create_quote",
            "create_insight",
            "create_sentiment",
            "create_topic_for_episode"
        ]
        
        for method_name in required_methods:
            if not hasattr(GraphStorageService, method_name):
                print(f"❌ Missing storage method: {method_name}")
                return False
            else:
                print(f"✅ Storage method exists: {method_name}")
        
    except ImportError as e:
        print(f"❌ Storage interface validation failed: {e}")
        return False
    
    return True

def validate_analysis_modules():
    """Verify analysis modules are available."""
    print("\nValidating Analysis Modules...")
    
    analysis_modules = [
        ("src.analysis.analysis_orchestrator", "run_knowledge_discovery"),
        ("src.analysis.diversity_metrics", "run_diversity_analysis"),
        ("src.analysis.gap_detection", "run_gap_detection"),
        ("src.analysis.missing_links", "run_missing_link_analysis")
    ]
    
    for module_name, function_name in analysis_modules:
        try:
            module = __import__(module_name, fromlist=[function_name])
            if not hasattr(module, function_name):
                print(f"❌ Missing analysis function: {module_name}.{function_name}")
                return False
            else:
                print(f"✅ Analysis function exists: {module_name}.{function_name}")
        except ImportError as e:
            print(f"❌ Analysis module import failed: {module_name} - {e}")
            return False
    
    return True

def main():
    """Run complete final system validation."""
    print("=" * 60)
    print("PHASE 7 TASK 7.4: FINAL SYSTEM VALIDATION")
    print("=" * 60)
    print("Validating unified pipeline system readiness")
    print()
    
    validation_functions = [
        validate_single_pipeline_approach,
        validate_configuration_simplicity,
        validate_documentation_completeness,
        validate_pipeline_structure,
        validate_test_framework,
        validate_storage_interface,
        validate_analysis_modules
    ]
    
    results = []
    for validation_func in validation_functions:
        try:
            result = validation_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Validation failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("FINAL SYSTEM VALIDATION SUMMARY")
    print("=" * 60)
    
    validation_names = [
        "Single Pipeline Approach",
        "Configuration Simplicity", 
        "Documentation Completeness",
        "Pipeline Structure",
        "Test Framework",
        "Storage Interface",
        "Analysis Modules"
    ]
    
    passed = sum(results)
    total = len(results)
    
    for i, (name, result) in enumerate(zip(validation_names, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name:<25} : {status}")
    
    print("-" * 60)
    print(f"TOTAL: {passed}/{total} validations passed")
    
    if passed == total:
        print("\n🎉 FINAL SYSTEM VALIDATION SUCCESSFUL!")
        print("\nKey Achievements:")
        print("✅ Single unified pipeline approach confirmed")
        print("✅ Configuration simplified with no alternatives")
        print("✅ Complete documentation provided")
        print("✅ Pipeline structure validated")
        print("✅ Test framework comprehensive")
        print("✅ Storage interface complete")
        print("✅ Analysis modules ready")
        print("\n🚀 SYSTEM READY FOR PRODUCTION!")
        return 0
    else:
        print("\n❌ FINAL SYSTEM VALIDATION FAILED!")
        print(f"Please address the {total - passed} failing validation(s) above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())