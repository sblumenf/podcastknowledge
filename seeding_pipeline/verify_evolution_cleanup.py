#!/usr/bin/env python3
"""
Script to verify that no evolution artifacts remain in Neo4j database.
Run this to confirm the evolution removal was successful.
"""

from src.services.graph_storage import GraphStorageService
from src.utils.config import Config

def verify_evolution_cleanup():
    """Check Neo4j for any remaining evolution artifacts."""
    
    print("Verifying evolution cleanup in Neo4j...")
    
    # Initialize Neo4j connection
    config = Config()
    graph_storage = GraphStorageService(config.get_neo4j_config())
    
    checks = []
    
    # Check 1: EVOLVED_INTO relationships
    print("\n1. Checking for EVOLVED_INTO relationships...")
    query1 = "MATCH ()-[r:EVOLVED_INTO]->() RETURN count(r) as count"
    result1 = graph_storage.query(query1)
    evolved_count = result1[0]['count'] if result1 else 0
    checks.append(('EVOLVED_INTO relationships', evolved_count, evolved_count == 0))
    print(f"   Found: {evolved_count} (Expected: 0)")
    
    # Check 2: ClusteringState nodes
    print("\n2. Checking for ClusteringState nodes...")
    query2 = "MATCH (cs:ClusteringState) RETURN count(cs) as count"
    result2 = graph_storage.query(query2)
    state_count = result2[0]['count'] if result2 else 0
    checks.append(('ClusteringState nodes', state_count, state_count == 0))
    print(f"   Found: {state_count} (Expected: 0)")
    
    # Check 3: Snapshot clusters
    print("\n3. Checking for snapshot clusters...")
    query3 = "MATCH (c:Cluster) WHERE c.type = 'snapshot' RETURN count(c) as count"
    result3 = graph_storage.query(query3)
    snapshot_count = result3[0]['count'] if result3 else 0
    checks.append(('Snapshot clusters', snapshot_count, snapshot_count == 0))
    print(f"   Found: {snapshot_count} (Expected: 0)")
    
    # Check 4: Clusters with type property
    print("\n4. Checking for clusters with type property...")
    query4 = "MATCH (c:Cluster) WHERE exists(c.type) RETURN count(c) as count"
    result4 = graph_storage.query(query4)
    type_count = result4[0]['count'] if result4 else 0
    checks.append(('Clusters with type property', type_count, type_count == 0))
    print(f"   Found: {type_count} (Expected: 0)")
    
    # Check 5: Clusters with period property
    print("\n5. Checking for clusters with period property...")
    query5 = "MATCH (c:Cluster) WHERE exists(c.period) RETURN count(c) as count"
    result5 = graph_storage.query(query5)
    period_count = result5[0]['count'] if result5 else 0
    checks.append(('Clusters with period property', period_count, period_count == 0))
    print(f"   Found: {period_count} (Expected: 0)")
    
    # Summary
    print("\n" + "="*50)
    print("VERIFICATION SUMMARY")
    print("="*50)
    
    all_passed = True
    for check_name, count, passed in checks:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {check_name}: {count}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("✓ ALL CHECKS PASSED - Evolution artifacts successfully removed!")
    else:
        print("✗ SOME CHECKS FAILED - Evolution artifacts still present!")
    print("="*50)
    
    graph_storage.close()
    return all_passed

if __name__ == "__main__":
    verify_evolution_cleanup()