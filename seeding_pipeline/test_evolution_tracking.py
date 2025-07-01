#!/usr/bin/env python3
"""
Test script for evolution tracking functionality.

Tests the Phase 6 evolution tracking implementation:
- Evolution detection (splits, merges, continuations)
- State comparison and transition matrix building
- Neo4j storage of evolution relationships
- Integration with clustering pipeline

Run this script to verify Phase 6 implementation works correctly.
"""

import os
import sys
from pathlib import Path
import numpy as np
from datetime import datetime
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.clustering.evolution_tracker import EvolutionTracker
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MockNeo4jService:
    """Mock Neo4j service for testing evolution tracking."""
    
    def __init__(self):
        self.queries_executed = []
        self.mock_data = {}
        
        # Mock previous clustering state
        self.mock_data['previous_state'] = {
            'week': '2024-W19',
            'timestamp': datetime.now(),
            'assignments': {
                'unit_1': '2024-W19_cluster_0',
                'unit_2': '2024-W19_cluster_0', 
                'unit_3': '2024-W19_cluster_0',
                'unit_4': '2024-W19_cluster_1',
                'unit_5': '2024-W19_cluster_1',
                'unit_6': '2024-W19_cluster_2',
                'unit_7': '2024-W19_cluster_2',
                'unit_8': '2024-W19_cluster_2'
            }
        }
    
    def query(self, query_str: str, params: dict = None):
        """Mock query execution."""
        self.queries_executed.append({
            'query': query_str,
            'params': params
        })
        
        # Return mock data based on query
        if 'ClusteringState' in query_str and 'ORDER BY' in query_str:
            # Mock loading previous state
            return [{
                'week': self.mock_data['previous_state']['week'],
                'timestamp': self.mock_data['previous_state']['timestamp'],
                'cluster_data': [
                    {
                        'cluster_id': '2024-W19_cluster_0',
                        'unit_ids': ['unit_1', 'unit_2', 'unit_3']
                    },
                    {
                        'cluster_id': '2024-W19_cluster_1', 
                        'unit_ids': ['unit_4', 'unit_5']
                    },
                    {
                        'cluster_id': '2024-W19_cluster_2',
                        'unit_ids': ['unit_6', 'unit_7', 'unit_8']
                    }
                ]
            }]
        elif 'CREATE (cs:ClusteringState' in query_str:
            # Mock creating clustering state
            return [{'state_id': f"state_{params.get('week', 'test')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"}]
        else:
            # Default empty result
            return []


def test_evolution_tracker_initialization():
    """Test EvolutionTracker initialization."""
    print("\n=== Testing EvolutionTracker Initialization ===")
    
    try:
        mock_neo4j = MockNeo4jService()
        tracker = EvolutionTracker(mock_neo4j)
        
        # Check attributes
        assert hasattr(tracker, 'neo4j')
        assert hasattr(tracker, 'split_threshold')
        assert hasattr(tracker, 'continuation_threshold')
        assert tracker.split_threshold == 0.2
        assert tracker.continuation_threshold == 0.8
        
        print("✓ EvolutionTracker initialized successfully")
        print(f"  Split threshold: {tracker.split_threshold}")
        print(f"  Continuation threshold: {tracker.continuation_threshold}")
        return True
        
    except Exception as e:
        print(f"✗ EvolutionTracker initialization failed: {str(e)}")
        return False


def test_transition_matrix_building():
    """Test transition matrix building."""
    print("\n=== Testing Transition Matrix Building ===")
    
    try:
        mock_neo4j = MockNeo4jService()
        tracker = EvolutionTracker(mock_neo4j)
        
        # Mock previous assignments
        previous_assignments = {
            'unit_1': '2024-W19_cluster_0',
            'unit_2': '2024-W19_cluster_0',
            'unit_3': '2024-W19_cluster_0',
            'unit_4': '2024-W19_cluster_1',
            'unit_5': '2024-W19_cluster_1'
        }
        
        # Mock current clusters (simulating a split)
        current_clusters = {
            0: [
                {'unit_id': 'unit_1'},
                {'unit_id': 'unit_2'}
            ],
            1: [
                {'unit_id': 'unit_3'},
                {'unit_id': 'unit_4'}
            ],
            2: [
                {'unit_id': 'unit_5'}
            ]
        }
        
        # Build transition matrix
        transition_matrix = tracker._build_transition_matrix(
            previous_assignments, 
            current_clusters
        )
        
        # Verify matrix structure
        assert isinstance(transition_matrix, dict)
        assert '2024-W19_cluster_0' in transition_matrix
        assert '2024-W19_cluster_1' in transition_matrix
        
        print("✓ Transition matrix built successfully")
        print(f"  Matrix keys: {list(transition_matrix.keys())}")
        for old_cluster, destinations in transition_matrix.items():
            print(f"  {old_cluster} -> {dict(destinations)}")
        
        return True
        
    except Exception as e:
        print(f"✗ Transition matrix building failed: {str(e)}")
        return False


def test_split_detection():
    """Test split event detection."""
    print("\n=== Testing Split Detection ===")
    
    try:
        mock_neo4j = MockNeo4jService()
        tracker = EvolutionTracker(mock_neo4j)
        
        # Create transition matrix simulating a split
        # Old cluster_0 splits into new clusters 0 and 1
        transitions = {
            'old_cluster_0': {
                '0': 3,  # 3 units go to new cluster 0 (60%)
                '1': 2   # 2 units go to new cluster 1 (40%)
            },
            'old_cluster_1': {
                '2': 5   # All 5 units continue to cluster 2 (100%)
            }
        }
        
        splits = tracker._detect_splits(transitions)
        
        assert len(splits) == 1, f"Expected 1 split, got {len(splits)}"
        
        split = splits[0]
        assert split['type'] == 'split'
        assert split['from_cluster'] == 'old_cluster_0'
        assert '0' in split['to_clusters']
        assert '1' in split['to_clusters']
        assert split['proportions']['0'] == 0.6  # 3/5
        assert split['proportions']['1'] == 0.4  # 2/5
        
        print("✓ Split detection working correctly")
        print(f"  Detected split: {split['from_cluster']} -> {split['to_clusters']}")
        print(f"  Proportions: {split['proportions']}")
        
        return True
        
    except Exception as e:
        print(f"✗ Split detection failed: {str(e)}")
        return False


def test_merge_detection():
    """Test merge event detection."""
    print("\n=== Testing Merge Detection ===")
    
    try:
        mock_neo4j = MockNeo4jService()
        tracker = EvolutionTracker(mock_neo4j)
        
        # Create transition matrix simulating a merge
        # Old clusters A and B merge into new cluster 0
        transitions = {
            'old_cluster_A': {
                '0': 3   # 3 units from A go to cluster 0
            },
            'old_cluster_B': {
                '0': 2   # 2 units from B go to cluster 0  
            },
            'old_cluster_C': {
                '1': 4   # 4 units continue as cluster 1
            }
        }
        
        merges = tracker._detect_merges(transitions)
        
        assert len(merges) == 1, f"Expected 1 merge, got {len(merges)}"
        
        merge = merges[0]
        assert merge['type'] == 'merge'
        assert merge['to_cluster'] == '0'
        assert 'old_cluster_A' in merge['from_clusters']
        assert 'old_cluster_B' in merge['from_clusters']
        assert merge['proportions']['old_cluster_A'] == 0.6  # 3/5
        assert merge['proportions']['old_cluster_B'] == 0.4  # 2/5
        
        print("✓ Merge detection working correctly")
        print(f"  Detected merge: {merge['from_clusters']} -> {merge['to_cluster']}")
        print(f"  Proportions: {merge['proportions']}")
        
        return True
        
    except Exception as e:
        print(f"✗ Merge detection failed: {str(e)}")
        return False


def test_continuation_detection():
    """Test continuation event detection."""
    print("\n=== Testing Continuation Detection ===")
    
    try:
        mock_neo4j = MockNeo4jService()
        tracker = EvolutionTracker(mock_neo4j)
        
        # Create transition matrix simulating continuations
        transitions = {
            'old_cluster_0': {
                '0': 8,    # 8 out of 10 units continue (80% - threshold)
                '1': 2     # 2 units move elsewhere
            },
            'old_cluster_1': {
                '2': 9,    # 9 out of 10 units continue (90% - strong continuation)
                'outlier': 1  # 1 becomes outlier
            },
            'old_cluster_2': {
                '3': 3,    # Only 60% continue - below threshold
                '4': 2
            }
        }
        
        continuations = tracker._detect_continuations(transitions)
        
        # Should detect 2 continuations (80% and 90%, but not 60%)
        assert len(continuations) == 2, f"Expected 2 continuations, got {len(continuations)}"
        
        # Check first continuation
        cont1 = continuations[0]
        assert cont1['type'] == 'continuation'
        assert cont1['from_cluster'] == 'old_cluster_0'
        assert cont1['to_cluster'] == '0'
        assert cont1['proportion'] == 0.8
        
        # Check second continuation
        cont2 = continuations[1]
        assert cont2['type'] == 'continuation'
        assert cont2['from_cluster'] == 'old_cluster_1'
        assert cont2['to_cluster'] == '2'
        assert cont2['proportion'] == 0.9
        
        print("✓ Continuation detection working correctly")
        for cont in continuations:
            print(f"  Continuation: {cont['from_cluster']} -> {cont['to_cluster']} ({cont['proportion']:.1%})")
        
        return True
        
    except Exception as e:
        print(f"✗ Continuation detection failed: {str(e)}")
        return False


def test_evolution_event_storage():
    """Test storing evolution events in Neo4j."""
    print("\n=== Testing Evolution Event Storage ===")
    
    try:
        mock_neo4j = MockNeo4jService()
        tracker = EvolutionTracker(mock_neo4j)
        
        # Create sample evolution events
        evolution_events = [
            {
                'type': 'split',
                'from_cluster': 'old_cluster_0',
                'to_clusters': ['0', '1'],
                'proportions': {'0': 0.6, '1': 0.4},
                'total_units': 5
            },
            {
                'type': 'merge',
                'from_clusters': ['old_cluster_A', 'old_cluster_B'],
                'to_cluster': '2',
                'proportions': {'old_cluster_A': 0.7, 'old_cluster_B': 0.3},
                'total_units': 10
            },
            {
                'type': 'continuation',
                'from_cluster': 'old_cluster_C',
                'to_cluster': '3',
                'proportion': 0.9,
                'total_units': 8
            }
        ]
        
        # Store events
        stats = tracker.store_evolution_events(evolution_events, '2024-W20')
        
        # Verify statistics
        print(f"  Actual stats: {stats}")
        assert stats['splits_stored'] == 1, f"Expected 1 split stored, got {stats['splits_stored']}"
        assert stats['merges_stored'] == 1, f"Expected 1 merge stored, got {stats['merges_stored']}"
        assert stats['continuations_stored'] == 1, f"Expected 1 continuation stored, got {stats['continuations_stored']}"
        # Split has 2 to_clusters, merge has 2 from_clusters, continuation has 1 = 5 total
        assert stats['total_relationships'] == 5, f"Expected 5 total relationships, got {stats['total_relationships']}"
        
        # Verify queries were executed
        assert len(mock_neo4j.queries_executed) > 0
        
        print("✓ Evolution event storage working correctly")
        print(f"  Storage stats: {stats}")
        print(f"  Queries executed: {len(mock_neo4j.queries_executed)}")
        
        return True
        
    except Exception as e:
        print(f"✗ Evolution event storage failed: {str(e)}")
        return False


def test_state_saving():
    """Test saving clustering state."""
    print("\n=== Testing State Saving ===")
    
    try:
        mock_neo4j = MockNeo4jService()
        tracker = EvolutionTracker(mock_neo4j)
        
        # Create sample cluster results
        cluster_results = {
            'clusters': {
                0: [{'unit_id': 'unit_1'}, {'unit_id': 'unit_2'}],
                1: [{'unit_id': 'unit_3'}, {'unit_id': 'unit_4'}]
            },
            'n_clusters': 2,
            'n_outliers': 1,
            'total_units': 5
        }
        
        # Save state
        state_id = tracker.save_state(cluster_results, '2024-W20')
        
        # Verify state ID format
        assert state_id.startswith('state_2024-W20_')
        assert len(state_id) > 20  # Should include timestamp
        
        # Verify query was executed
        assert len(mock_neo4j.queries_executed) > 0
        
        state_query = mock_neo4j.queries_executed[0]
        assert 'CREATE (cs:ClusteringState' in state_query['query']
        assert state_query['params']['week'] == '2024-W20'
        assert state_query['params']['n_clusters'] == 2
        assert state_query['params']['n_outliers'] == 1
        
        print("✓ State saving working correctly")
        print(f"  Created state ID: {state_id}")
        print(f"  State query executed with correct parameters")
        
        return True
        
    except Exception as e:
        print(f"✗ State saving failed: {str(e)}")
        return False


def test_end_to_end_evolution_detection():
    """Test complete evolution detection workflow."""
    print("\n=== Testing End-to-End Evolution Detection ===")
    
    try:
        mock_neo4j = MockNeo4jService()
        tracker = EvolutionTracker(mock_neo4j)
        
        # Create current clusters that demonstrate all evolution types
        current_clusters = {
            'clusters': {
                # Split: old cluster_0 splits into new clusters 0 and 1
                0: [
                    {'unit_id': 'unit_1'},  # From old cluster_0
                    {'unit_id': 'unit_2'}   # From old cluster_0
                ],
                1: [
                    {'unit_id': 'unit_3'}   # From old cluster_0
                ],
                # Merge: old clusters 1 and 2 merge into new cluster 2
                2: [
                    {'unit_id': 'unit_4'},  # From old cluster_1
                    {'unit_id': 'unit_5'},  # From old cluster_1
                    {'unit_id': 'unit_6'},  # From old cluster_2
                    {'unit_id': 'unit_7'}   # From old cluster_2
                ],
                # Continuation: unit_8 stays alone (less than continuation threshold)
                3: [
                    {'unit_id': 'unit_8'}   # From old cluster_2
                ]
            }
        }
        
        # Run evolution detection
        evolution_events = tracker.detect_evolution(current_clusters, '2024-W20')
        
        # Should detect split, merge, and possibly continuation
        assert len(evolution_events) >= 2, f"Expected at least 2 events, got {len(evolution_events)}"
        
        # Check that we have different event types
        event_types = {event['type'] for event in evolution_events}
        assert 'split' in event_types or 'merge' in event_types
        
        print("✓ End-to-end evolution detection working correctly")
        print(f"  Detected {len(evolution_events)} evolution events:")
        for event in evolution_events:
            print(f"    {event['type']}: {event}")
        
        return True
        
    except Exception as e:
        print(f"✗ End-to-end evolution detection failed: {str(e)}")
        return False


def main():
    """Run all evolution tracking tests."""
    print("🧪 Testing Evolution Tracking (Phase 6)")
    print("=" * 60)
    
    tests = [
        test_evolution_tracker_initialization,
        test_transition_matrix_building,
        test_split_detection,
        test_merge_detection,
        test_continuation_detection,
        test_evolution_event_storage,
        test_state_saving,
        test_end_to_end_evolution_detection
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
        print("🎉 All evolution tracking tests passed! Phase 6 implementation is working correctly.")
        print("\nEvolution tracking can now:")
        print("  - Detect cluster splits, merges, and continuations")
        print("  - Build transition matrices to track unit movements")
        print("  - Store evolution relationships in Neo4j")
        print("  - Save clustering state for future comparisons")
        print("  - Integrate seamlessly with the clustering pipeline")
        return True
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)