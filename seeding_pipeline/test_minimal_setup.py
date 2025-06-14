#!/usr/bin/env python3
"""
Test script to verify the system works with minimal dependencies.
Run this after installing only requirements-minimal.txt
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that core components can be imported."""
    print("Testing core imports with minimal dependencies...")
    
    results = []
    
    # Test optional dependency handling
    try:
        from src.utils.optional_dependencies import PSUTIL_AVAILABLE, get_memory_info
        results.append(("psutil handling", True, f"Available: {PSUTIL_AVAILABLE}"))
        
        mem_info = get_memory_info()
        results.append(("Memory info mock", True, f"Memory: {mem_info['process_memory_mb']}MB"))
    except Exception as e:
        results.append(("psutil handling", False, str(e)))
    
    try:
        from src.utils.optional_google import GOOGLE_AI_AVAILABLE, get_genai
        results.append(("google-ai handling", True, f"Available: {GOOGLE_AI_AVAILABLE}"))
        
        genai = get_genai()
        results.append(("Gemini mock", True, f"Type: {type(genai).__name__}"))
    except Exception as e:
        results.append(("google-ai handling", False, str(e)))
    
    # Test core imports that require pydantic
    imports_to_test = [
        ("Config", "src.core.config", "PipelineConfig"),
        ("Models", "src.core.models", "Episode"),
        ("VTT Parser", "src.vtt.vtt_parser", "VTTParser"),
        ("Graph Storage", "src.storage.graph_storage", "GraphStorageService"),
    ]
    
    for name, module_path, class_name in imports_to_test:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            results.append((name, True, f"Imported {class_name}"))
        except ImportError as e:
            results.append((name, False, f"Import error: {e}"))
        except Exception as e:
            results.append((name, False, f"Error: {e}"))
    
    # Print results
    print("\nImport Test Results:")
    print("-" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, success, message in results:
        status = "✓" if success else "✗"
        print(f"{status} {test_name:<25} {message}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print("-" * 60)
    print(f"Passed: {passed}, Failed: {failed}")
    
    return failed == 0


def test_mock_functionality():
    """Test that mocks work correctly."""
    print("\n\nTesting mock functionality...")
    
    results = []
    
    # Test mock embeddings
    try:
        from src.services.embeddings_gemini import GeminiEmbeddingsService
        
        service = GeminiEmbeddingsService(api_key="test_key")
        embedding = service.generate_embedding("test text")
        
        results.append(("Mock embedding generation", True, 
                       f"Generated {len(embedding)}-dim embedding"))
        
        # Test cosine similarity without numpy
        similarity = service.cosine_similarity(embedding, embedding)
        results.append(("Pure Python cosine similarity", True, 
                       f"Similarity: {similarity:.2f}"))
        
    except Exception as e:
        results.append(("Mock embeddings", False, str(e)))
    
    # Test performance optimizer without psutil
    try:
        from src.services.performance_optimizer import PerformanceOptimizer
        
        optimizer = PerformanceOptimizer()
        mem_stats = optimizer.optimize_memory_usage()
        
        results.append(("Memory optimization mock", True, 
                       f"Memory: {mem_stats['final_memory_mb']}MB"))
    except Exception as e:
        results.append(("Performance optimizer", False, str(e)))
    
    # Print results
    print("\nMock Functionality Results:")
    print("-" * 60)
    
    for test_name, success, message in results:
        status = "✓" if success else "✗"
        print(f"{status} {test_name:<25} {message}")
    
    print("-" * 60)
    
    return all(success for _, success, _ in results)


def main():
    """Run all tests."""
    print("=" * 60)
    print("VTT Knowledge Graph Pipeline - Minimal Setup Test")
    print("=" * 60)
    
    # Check Python version
    print(f"\nPython Version: {sys.version}")
    if sys.version_info < (3, 8):
        print("ERROR: Python 3.8+ required")
        return 1
    
    # Test imports
    imports_ok = test_imports()
    
    # Test mock functionality  
    mocks_ok = test_mock_functionality()
    
    # Summary
    print("\n" + "=" * 60)
    if imports_ok and mocks_ok:
        print("✅ SUCCESS: System works with minimal dependencies!")
        print("\nYou can now run:")
        print("  python -m src.cli.cli process-vtt --help")
        return 0
    else:
        print("❌ FAILED: Some tests failed.")
        print("\nMake sure you have installed:")
        print("  pip install -r requirements-minimal.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())