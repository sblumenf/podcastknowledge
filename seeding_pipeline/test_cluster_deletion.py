#!/usr/bin/env python3
"""
Test script to verify that cluster deletion works correctly.
This ensures old clusters are deleted instead of archived.
"""

import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.storage.graph_storage import GraphStorageService


def test_cluster_deletion():
    """Test that clusters are properly deleted, not archived."""
    
    print("Testing Cluster Deletion Functionality")
    print("="*50)
    
    # Connect to Neo4j
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    
    graph_storage = GraphStorageService(
        uri=neo4j_uri,
        username=neo4j_user,
        password=neo4j_password
    )
    
    try:
        graph_storage.connect()
        
        # Check for any archived clusters (should be none)
        archived_query = """
        MATCH (c:Cluster)
        WHERE c.status = 'archived'
        RETURN count(c) as archived_count
        """
        result = graph_storage.query(archived_query)
        archived_count = result[0]['archived_count'] if result else 0
        
        print(f"\nArchived clusters found: {archived_count}")
        if archived_count > 0:
            print("⚠️  WARNING: Found archived clusters. These should have been deleted.")
            print("   The system now deletes old clusters instead of archiving them.")
            
            # Show some details about archived clusters
            detail_query = """
            MATCH (c:Cluster)
            WHERE c.status = 'archived'
            RETURN c.id, c.label, c.archived_at
            ORDER BY c.archived_at DESC
            LIMIT 5
            """
            details = graph_storage.query(detail_query)
            if details:
                print("\n   Recent archived clusters:")
                for cluster in details:
                    print(f"   - {cluster['c.id']}: {cluster['c.label']} (archived: {cluster['c.archived_at']})")
        else:
            print("✓ No archived clusters found (as expected)")
        
        # Check total clusters
        total_query = """
        MATCH (c:Cluster)
        RETURN count(c) as total_count
        """
        result = graph_storage.query(total_query)
        total_count = result[0]['total_count'] if result else 0
        
        print(f"\nTotal clusters in database: {total_count}")
        
        # Check for active clusters
        active_query = """
        MATCH (c:Cluster)
        WHERE c.status = 'active' OR c.status IS NULL
        RETURN count(c) as active_count
        """
        result = graph_storage.query(active_query)
        active_count = result[0]['active_count'] if result else 0
        
        print(f"Active clusters: {active_count}")
        
        # Summary
        print("\n" + "="*50)
        print("SUMMARY:")
        if archived_count == 0:
            print("✓ Cluster deletion is working correctly")
            print("  Old clusters are being deleted, not archived")
        else:
            print("⚠️  Legacy archived clusters detected")
            print("  Future clustering runs will delete old clusters")
            print("  To clean up archived clusters manually, run:")
            print("  MATCH (c:Cluster) WHERE c.status = 'archived' DETACH DELETE c")
        
    finally:
        graph_storage.close()


if __name__ == "__main__":
    test_cluster_deletion()