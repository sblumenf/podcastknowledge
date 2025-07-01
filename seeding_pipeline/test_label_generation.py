#!/usr/bin/env python3
"""
Test script for cluster label generation functionality.

Tests the Phase 5 label generation implementation:
- ClusterLabeler initialization
- Label generation from representative units
- Label validation and cleaning
- Statistics tracking

Run this script to verify Phase 5 implementation works correctly.
"""

import os
import sys
from pathlib import Path
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.clustering.label_generator import ClusterLabeler
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MockLLMService:
    """Mock LLM service for testing."""
    
    def __init__(self):
        self.responses = {
            "machine learning": "Machine Learning",
            "electric vehicles": "Electric Vehicles", 
            "startup funding": "Startup Funding",
            "climate change": "Climate Change Solutions",
            "ai discussion": "Discussion",  # Should trigger banned term
            "general topics": "General",     # Should trigger banned term
            "123 numbers": "123",            # Should trigger numbers-only
            "a": "A",                        # Should trigger too short
            "very long topic name with many words": "Very Long Topic Name With Many Words"  # Should be truncated
        }
    
    def generate(self, prompt: str, temperature: float = 0.3) -> str:
        """Mock LLM response based on prompt content."""
        prompt_lower = prompt.lower()
        
        for key, response in self.responses.items():
            if key in prompt_lower:
                return response
        
        # Default response
        return "Technology Trends"


def test_cluster_labeler_initialization():
    """Test ClusterLabeler initialization."""
    print("\n=== Testing ClusterLabeler Initialization ===")
    
    try:
        mock_llm = MockLLMService()
        labeler = ClusterLabeler(mock_llm)
        
        # Check that required attributes exist
        assert hasattr(labeler, 'llm_service')
        assert hasattr(labeler, 'used_labels')
        assert hasattr(labeler, 'banned_terms')
        assert hasattr(labeler, 'validation_stats')
        
        print("✓ ClusterLabeler initialized successfully")
        print(f"  Banned terms: {labeler.banned_terms}")
        print(f"  Validation stats initialized: {list(labeler.validation_stats.keys())}")
        return True
        
    except Exception as e:
        print(f"✗ ClusterLabeler initialization failed: {str(e)}")
        return False


def test_label_validation():
    """Test label validation functionality."""
    print("\n=== Testing Label Validation ===")
    
    try:
        mock_llm = MockLLMService()
        labeler = ClusterLabeler(mock_llm)
        
        # Test cases for validation
        test_cases = [
            # (input_label, cluster_id, expected_behavior)
            ("Machine Learning", 1, "should_pass"),
            ("Discussion", 2, "should_fail_banned"),
            ("General", 3, "should_fail_banned"),
            ("123", 4, "should_fail_numbers"),
            ("A", 5, "should_fail_too_short"),
            ("Very Long Topic Name With Many", 6, "should_truncate"),
            ("", 7, "should_fail_empty"),
            ("   ", 8, "should_fail_empty"),
        ]
        
        results = {}
        
        for input_label, cluster_id, expected in test_cases:
            result = labeler._validate_and_clean_label(input_label, cluster_id)
            results[input_label or "empty"] = result
            
            if expected == "should_pass":
                assert not result.startswith("Cluster_"), f"Expected valid label but got fallback: {result}"
            elif expected in ["should_fail_banned", "should_fail_numbers", "should_fail_too_short", "should_fail_empty"]:
                assert result.startswith("Cluster_"), f"Expected fallback but got: {result}"
            elif expected == "should_truncate":
                assert len(result.split()) <= 3, f"Expected truncated label but got: {result}"
        
        print("✓ Label validation tests passed")
        for input_label, result in results.items():
            print(f"  '{input_label}' -> '{result}'")
        
        # Check validation statistics
        stats = labeler.get_validation_stats()
        print(f"  Validation stats: {stats}")
        
        return True
        
    except Exception as e:
        print(f"✗ Label validation failed: {str(e)}")
        return False


def test_representative_unit_selection():
    """Test representative unit selection."""
    print("\n=== Testing Representative Unit Selection ===")
    
    try:
        mock_llm = MockLLMService()
        labeler = ClusterLabeler(mock_llm)
        
        # Create mock cluster units
        cluster_units = [
            {'unit_id': 'unit_1'},
            {'unit_id': 'unit_2'},
            {'unit_id': 'unit_3'},
            {'unit_id': 'unit_4'},
            {'unit_id': 'unit_5'},
        ]
        
        # Create mock centroid (768 dimensions)
        centroid = np.random.rand(768)
        
        # Create mock embeddings data
        embeddings_data = {
            'unit_ids': ['unit_1', 'unit_2', 'unit_3', 'unit_4', 'unit_5'],
            'embeddings': np.random.rand(5, 768),  # 5 units with 768 dims each
            'metadata': [
                {'unit_id': 'unit_1', 'summary': 'Discussion about machine learning applications'},
                {'unit_id': 'unit_2', 'summary': 'Analysis of neural network architectures'},
                {'unit_id': 'unit_3', 'summary': 'Deep learning model performance'},
                {'unit_id': 'unit_4', 'summary': 'AI ethics and bias considerations'},
                {'unit_id': 'unit_5', 'summary': 'Future of artificial intelligence'},
            ]
        }
        
        # Test representative unit selection
        representative_units = labeler._get_representative_units(
            cluster_units, centroid, embeddings_data, n_representatives=3
        )
        
        assert len(representative_units) <= 3, f"Expected max 3 units, got {len(representative_units)}"
        assert all('similarity' in unit for unit in representative_units), "Missing similarity scores"
        assert all('summary' in unit for unit in representative_units), "Missing summaries"
        
        print("✓ Representative unit selection passed")
        print(f"  Selected {len(representative_units)} representative units")
        for unit in representative_units:
            print(f"  Unit {unit['unit_id']}: similarity={unit['similarity']:.3f}")
        
        return True
        
    except Exception as e:
        print(f"✗ Representative unit selection failed: {str(e)}")
        return False


def test_end_to_end_label_generation():
    """Test end-to-end label generation."""
    print("\n=== Testing End-to-End Label Generation ===")
    
    try:
        mock_llm = MockLLMService()
        labeler = ClusterLabeler(mock_llm)
        
        # Create mock cluster results
        cluster_results = {
            'clusters': {
                0: [
                    {'unit_id': 'unit_1', 'confidence': 0.9},
                    {'unit_id': 'unit_2', 'confidence': 0.8},
                ],
                1: [
                    {'unit_id': 'unit_3', 'confidence': 0.85},
                    {'unit_id': 'unit_4', 'confidence': 0.75},
                ],
            },
            'centroids': {
                0: np.random.rand(768),
                1: np.random.rand(768),
            },
            'n_clusters': 2,
            'n_outliers': 1,
            'total_units': 5
        }
        
        # Create mock embeddings data
        embeddings_data = {
            'unit_ids': ['unit_1', 'unit_2', 'unit_3', 'unit_4', 'unit_5'],
            'embeddings': np.random.rand(5, 768),
            'metadata': [
                {'unit_id': 'unit_1', 'summary': 'Machine learning algorithm development'},
                {'unit_id': 'unit_2', 'summary': 'Neural network optimization techniques'},
                {'unit_id': 'unit_3', 'summary': 'Electric vehicle battery technology'},
                {'unit_id': 'unit_4', 'summary': 'Tesla charging infrastructure plans'},
                {'unit_id': 'unit_5', 'summary': 'Climate change policy discussions'},
            ]
        }
        
        # Generate labels
        labeled_clusters = labeler.generate_labels(cluster_results, embeddings_data)
        
        assert len(labeled_clusters) == 2, f"Expected 2 labeled clusters, got {len(labeled_clusters)}"
        assert all(cluster_id in labeled_clusters for cluster_id in [0, 1]), "Missing cluster labels"
        
        print("✓ End-to-end label generation passed")
        for cluster_id, label in labeled_clusters.items():
            print(f"  Cluster {cluster_id}: '{label}'")
        
        # Check final validation statistics
        stats = labeler.get_validation_stats()
        print(f"  Final validation stats: success_rate={stats['success_rate']:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"✗ End-to-end label generation failed: {str(e)}")
        return False


def main():
    """Run all tests."""
    print("🧪 Testing Cluster Label Generation (Phase 5)")
    print("=" * 60)
    
    tests = [
        test_cluster_labeler_initialization,
        test_label_validation,
        test_representative_unit_selection,
        test_end_to_end_label_generation,
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"✗ Test {test_func.__name__} failed with exception: {str(e)}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All label generation tests passed! Phase 5 implementation is working correctly.")
        return True
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)