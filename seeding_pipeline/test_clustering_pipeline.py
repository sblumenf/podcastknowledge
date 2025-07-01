#!/usr/bin/env python3
"""
Test script for semantic clustering pipeline.

Tests the core clustering implementation:
- Embeddings extraction
- HDBSCAN clustering 
- Neo4j updates
- Configuration loading

Run this script to verify Phase 3 implementation works correctly.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.services.neo4j_service import GraphStorageService
from src.clustering import (
    SemanticClusteringSystem,
    EmbeddingsExtractor,
    SimpleHDBSCANClusterer,
    Neo4jClusterUpdater
)
import yaml
from pathlib import Path
from src.utils.logging import get_logger

logger = get_logger(__name__)


def test_config_loading():
    """Test configuration loading."""
    print("\n=== Testing Configuration Loading ===")
    
    try:
        config_path = Path(__file__).parent / 'config' / 'clustering_config.yaml'
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        print("✓ Configuration loaded successfully")
        print(f"  Clustering params: {config.get('clustering')}")
        return True
    except Exception as e:
        print(f"✗ Configuration loading failed: {str(e)}")
        return False


def test_embeddings_extraction(neo4j_service):
    """Test embeddings extraction from Neo4j."""
    print("\n=== Testing Embeddings Extraction ===")
    
    try:
        extractor = EmbeddingsExtractor(neo4j_service)
        
        # Get counts first
        counts = extractor.count_embeddings()
        print(f"✓ Embedding counts retrieved:")
        print(f"  Total units: {counts['total_units']}")
        print(f"  Units with embeddings: {counts['units_with_embeddings']}")
        print(f"  Valid embeddings: {counts['valid_embeddings']}")
        print(f"  Coverage: {counts['embedding_coverage_percent']}%")
        
        if counts['units_with_embeddings'] == 0:
            print("⚠ No embeddings found in database. Run episode processing first.")
            return False
        
        # Extract all embeddings
        embeddings_data = extractor.extract_all_embeddings()
        print(f"✓ Extracted {len(embeddings_data['unit_ids'])} embeddings")
        print(f"  Embedding shape: {embeddings_data['embeddings'].shape}")
        
        return True
        
    except Exception as e:
        print(f"✗ Embeddings extraction failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_clustering(embeddings_data, config):
    """Test HDBSCAN clustering."""
    print("\n=== Testing HDBSCAN Clustering ===")
    
    try:
        clusterer = SimpleHDBSCANClusterer(config)
        
        # Run clustering
        results = clusterer.cluster(
            embeddings_data['embeddings'],
            embeddings_data['unit_ids']
        )
        
        print("✓ Clustering completed successfully")
        print(f"  Clusters formed: {results['n_clusters']}")
        print(f"  Outliers: {results['n_outliers']} ({results['outlier_ratio']:.1%})")
        print(f"  Avg cluster size: {results['avg_cluster_size']:.1f}")
        # Quality score removed per Phase 3 requirements
        
        # Show cluster size distribution
        if results['cluster_sizes']:
            print(f"  Cluster sizes: min={results['min_cluster_size']}, "
                  f"max={results['max_cluster_size']}")
        
        return results
        
    except Exception as e:
        print(f"✗ Clustering failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_neo4j_update(neo4j_service, cluster_results):
    """Test Neo4j update with clustering results."""
    print("\n=== Testing Neo4j Update ===")
    
    try:
        updater = Neo4jClusterUpdater(neo4j_service)
        
        # Update graph
        stats = updater.update_graph(cluster_results)
        
        print("✓ Neo4j updated successfully")
        print(f"  Clusters created: {stats['clusters_created']}")
        print(f"  Relationships created: {stats['relationships_created']}")
        print(f"  Clustering state created: {stats['clustering_state_created']}")
        
        if stats['errors']:
            print(f"  ⚠ Errors encountered: {stats['errors']}")
        
        return True
        
    except Exception as e:
        print(f"✗ Neo4j update failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_full_pipeline(neo4j_service):
    """Test the complete clustering pipeline."""
    print("\n=== Testing Full Clustering Pipeline ===")
    
    try:
        # Initialize system
        clustering_system = SemanticClusteringSystem(neo4j_service)
        
        # Run clustering
        result = clustering_system.run_clustering()
        
        if result['status'] == 'success':
            print("✓ Full pipeline executed successfully")
            print(f"  {result['message']}")
            print(f"  Stats: {result['stats']}")
        else:
            print(f"✗ Pipeline failed: {result['message']}")
            if result['errors']:
                print(f"  Errors: {result['errors']}")
        
        # Summary and health methods removed per Phase 3 requirements
        
        return result['status'] == 'success'
        
    except Exception as e:
        print(f"✗ Full pipeline test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_data(neo4j_service):
    """Clean up test clustering data (optional)."""
    print("\n=== Cleanup (Optional) ===")
    
    response = input("Remove test clustering data? (y/N): ").strip().lower()
    if response != 'y':
        print("Skipping cleanup")
        return
    
    try:
        # Remove test clusters and relationships
        query = """
        MATCH (c:Cluster)<-[r:IN_CLUSTER]-(m:MeaningfulUnit)
        DELETE r, c
        """
        neo4j_service.query(query)
        
        # Remove clustering states
        query = """
        MATCH (cs:ClusteringState)
        DETACH DELETE cs
        """
        neo4j_service.query(query)
        
        print("✓ Test data cleaned up")
        
    except Exception as e:
        print(f"✗ Cleanup failed: {str(e)}")


def main():
    """Run all tests."""
    print("=== Semantic Clustering Pipeline Test ===")
    print("This script tests the Phase 3 clustering implementation")
    
    # Initialize Neo4j connection
    print("\n=== Initializing Neo4j Connection ===")
    try:
        neo4j_service = GraphStorageService()
        print("✓ Connected to Neo4j")
    except Exception as e:
        print(f"✗ Failed to connect to Neo4j: {str(e)}")
        print("Make sure Neo4j is running and credentials are configured")
        return 1
    
    # Run tests
    all_passed = True
    
    # Test 1: Config loading
    if not test_config_loading():
        all_passed = False
        print("⚠ Continuing with remaining tests...")
    
    # Test 2: Embeddings extraction
    if test_embeddings_extraction(neo4j_service):
        # Get embeddings for subsequent tests
        extractor = EmbeddingsExtractor(neo4j_service)
        embeddings_data = extractor.extract_all_embeddings()
        
        if len(embeddings_data['unit_ids']) > 0:
            # Test 3: Clustering
            config_path = Path(__file__).parent / 'config' / 'clustering_config.yaml'
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            cluster_results = test_clustering(embeddings_data, config)
            
            if cluster_results and cluster_results['n_clusters'] > 0:
                # Test 4: Neo4j update
                if not test_neo4j_update(neo4j_service, cluster_results):
                    all_passed = False
            else:
                print("⚠ No clusters formed, skipping Neo4j update test")
                all_passed = False
    else:
        all_passed = False
    
    # Test 5: Full pipeline
    if not test_full_pipeline(neo4j_service):
        all_passed = False
    
    # Summary
    print("\n=== Test Summary ===")
    if all_passed:
        print("✅ All tests passed! Core clustering pipeline is working.")
        print("\nNext steps:")
        print("1. Review clustering results in Neo4j")
        print("2. Adjust HDBSCAN parameters in config/clustering_config.yaml if needed")
        print("3. Proceed to Phase 4: Pipeline Integration")
    else:
        print("❌ Some tests failed. Review the output above and fix issues.")
        print("\nCommon issues:")
        print("- No embeddings: Run episode processing first")
        print("- Poor clustering: Adjust HDBSCAN parameters")
        print("- Neo4j errors: Check database connection and schema")
    
    # Optional cleanup
    cleanup_test_data(neo4j_service)
    
    # Close Neo4j connection
    neo4j_service.close()
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())