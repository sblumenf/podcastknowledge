#!/usr/bin/env python3
"""
Test script to verify the simplified clustering system works correctly.
Run this after completing the evolution removal.
"""

import sys
from datetime import datetime
from src.services.graph_storage import GraphStorageService
from src.services.llm_service import LLMService
from src.clustering import SemanticClusteringSystem
from src.utils.config import Config

def test_simplified_clustering():
    """Test the simplified clustering system."""
    
    print("="*60)
    print("TESTING SIMPLIFIED CLUSTERING SYSTEM")
    print("="*60)
    
    try:
        # Initialize services
        print("\n1. Initializing services...")
        config = Config()
        graph_storage = GraphStorageService(config.get_neo4j_config())
        llm_service = LLMService(
            api_key=config.gemini_api_key,
            model_name=config.gemini_model
        )
        
        # Create clustering system
        print("2. Creating clustering system...")
        clustering_system = SemanticClusteringSystem(graph_storage, llm_service)
        
        # Check for data
        print("3. Checking for MeaningfulUnits with embeddings...")
        query = """
        MATCH (m:MeaningfulUnit)
        WHERE m.embedding IS NOT NULL
        RETURN count(m) as count
        """
        result = graph_storage.query(query)
        unit_count = result[0]['count'] if result else 0
        print(f"   Found {unit_count} units with embeddings")
        
        if unit_count == 0:
            print("\n⚠️  No units with embeddings found. Please process some episodes first.")
            return False
        
        # Run clustering
        print("\n4. Running simplified clustering...")
        start_time = datetime.now()
        result = clustering_system.run_clustering()
        duration = (datetime.now() - start_time).total_seconds()
        
        # Check results
        if result['status'] == 'success':
            print(f"\n✓ Clustering completed successfully in {duration:.1f}s")
            stats = result.get('stats', {})
            print(f"   - Total units: {stats.get('total_units', 'N/A')}")
            print(f"   - Clusters created: {stats.get('n_clusters', 'N/A')}")
            print(f"   - Outliers: {stats.get('n_outliers', 'N/A')} ({stats.get('outlier_ratio', 0):.1%})")
            print(f"   - Labeled clusters: {stats.get('labeled_clusters', 'N/A')}")
            
            # Verify clusters in Neo4j
            print("\n5. Verifying clusters in Neo4j...")
            cluster_query = """
            MATCH (c:Cluster)
            RETURN c.id, c.label, c.member_count
            ORDER BY c.member_count DESC
            LIMIT 5
            """
            clusters = graph_storage.query(cluster_query)
            
            if clusters:
                print("   Top clusters:")
                for cluster in clusters:
                    print(f"   - {cluster['c.label']}: {cluster['c.member_count']} units")
            
            # Check for clean schema (no evolution artifacts)
            print("\n6. Verifying clean schema...")
            checks = [
                ("ClusteringState nodes", "MATCH (cs:ClusteringState) RETURN count(cs) as count"),
                ("EVOLVED_INTO relationships", "MATCH ()-[r:EVOLVED_INTO]->() RETURN count(r) as count"),
                ("Clusters with type property", "MATCH (c:Cluster) WHERE exists(c.type) RETURN count(c) as count"),
                ("Clusters with period property", "MATCH (c:Cluster) WHERE exists(c.period) RETURN count(c) as count")
            ]
            
            all_clean = True
            for check_name, check_query in checks:
                check_result = graph_storage.query(check_query)
                count = check_result[0]['count'] if check_result else 0
                status = "✓" if count == 0 else "✗"
                print(f"   {status} {check_name}: {count}")
                if count > 0:
                    all_clean = False
            
            if all_clean:
                print("\n✓ ALL TESTS PASSED - Simplified clustering working correctly!")
                return True
            else:
                print("\n✗ SCHEMA NOT CLEAN - Evolution artifacts still present!")
                return False
            
        else:
            print(f"\n✗ Clustering failed: {result.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            graph_storage.close()
        except:
            pass

if __name__ == "__main__":
    success = test_simplified_clustering()
    sys.exit(0 if success else 1)