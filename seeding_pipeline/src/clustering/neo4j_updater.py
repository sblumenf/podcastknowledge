"""
Neo4j updater for semantic clustering.

Updates Neo4j with cluster assignments and relationships.
All clustering data stored in Neo4j as single source of truth.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
from src.utils.logging import get_logger
from .retry_utils import retry_with_backoff

logger = get_logger(__name__)


class Neo4jClusterUpdater:
    """
    Updates Neo4j with clustering results.
    
    Creates:
    - Cluster nodes with labels and metadata
    - IN_CLUSTER relationships from MeaningfulUnits to Clusters
    
    Deletes old clusters before creating new ones for a clean slate.
    Stores everything in Neo4j - no external files.
    """
    
    def __init__(self, neo4j_service):
        """
        Initialize Neo4j updater.
        
        Args:
            neo4j_service: GraphStorageService instance
        """
        self.neo4j = neo4j_service
    
    def update_graph(
        self,
        cluster_results: Dict[str, Any],
        labeled_clusters: Optional[Dict[int, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Update Neo4j with new cluster assignments.
        
        Deletes all existing clusters and creates new ones from scratch.
        
        Args:
            cluster_results: Results from HDBSCAN clusterer
            labeled_clusters: Optional dict with cluster labels (from Phase 5)
            
        Returns:
            Statistics about the update operation
        """
        logger.info("Updating Neo4j with clustering results")
        
        stats = {
            'clusters_created': 0,
            'relationships_created': 0,
            'errors': []
        }
        
        def _execute_update():
            # Start transaction
            with self.neo4j.session() as session:
                # Step 1: Delete old clusters and their relationships
                self._delete_old_clusters(session)
                
                # Step 2: Create new clusters
                
                # Step 3: Create Cluster nodes
                for cluster_id, units in cluster_results['clusters'].items():
                    # Generate simple cluster ID
                    cluster_node_id = f"cluster_{cluster_id}"
                    
                    # Get label if available, otherwise use generic label
                    if labeled_clusters and cluster_id in labeled_clusters:
                        label = labeled_clusters[cluster_id]
                    else:
                        label = f'Cluster {cluster_id}'
                    
                    # Get centroid
                    centroid = cluster_results['centroids'].get(cluster_id, [])
                    
                    # Create cluster node
                    self._create_cluster_node(
                        session,
                        cluster_node_id,
                        label,
                        len(units),
                        centroid
                    )
                    stats['clusters_created'] += 1
                    
                    # Step 4: Create IN_CLUSTER relationships
                    for unit_data in units:
                        self._create_cluster_assignment(
                            session,
                            unit_data['unit_id'],
                            cluster_node_id,
                            unit_data['confidence']
                        )
                        stats['relationships_created'] += 1
                
        
        try:
            # Execute update with retry logic
            retry_with_backoff(
                _execute_update,
                max_retries=3,
                initial_delay=2.0,
                backoff_factor=2.0,
                on_retry=lambda e, attempt: logger.warning(
                    f"Neo4j cluster update retry {attempt}/3 after error: {type(e).__name__}"
                )
            )
            
            logger.info(
                f"Neo4j update complete: {stats['clusters_created']} clusters, "
                f"{stats['relationships_created']} relationships"
            )
            
        except Exception as e:
            logger.error(f"Failed to update Neo4j after retries: {str(e)}", exc_info=True)
            stats['errors'].append(str(e))
            raise
        
        return stats
    
    def _delete_old_clusters(self, session):
        """Delete all existing clusters and their relationships.
        
        Uses DETACH DELETE to remove both the Cluster nodes and all
        IN_CLUSTER relationships in a single operation.
        """
        
        # Count existing clusters for logging
        count_query = """
        MATCH (c:Cluster)
        RETURN count(c) as cluster_count
        """
        result = session.run(count_query)
        count = result.single()["cluster_count"]
        
        if count > 0:
            # Delete all clusters and their relationships
            delete_query = """
            MATCH (c:Cluster)
            DETACH DELETE c
            """
            session.run(delete_query)
            logger.info(f"Deleted {count} existing clusters and their relationships")
        else:
            logger.info("No existing clusters to delete")
    
    def _create_cluster_node(
        self,
        session,
        cluster_id: str,
        label: str,
        member_count: int,
        centroid: List[float]
    ):
        """Create a Cluster node in Neo4j."""
        
        properties = {
            'id': cluster_id,
            'label': label,
            'member_count': member_count,
            'status': 'active',
            'centroid': centroid.tolist() if hasattr(centroid, 'tolist') else list(centroid),
            'created_timestamp': datetime.now()
        }
        
        query = """
        CREATE (c:Cluster $properties)
        """
        
        session.run(query, properties=properties)
    
    def _create_cluster_assignment(
        self,
        session,
        unit_id: str,
        cluster_id: str,
        confidence: float
    ):
        """Create IN_CLUSTER relationship."""
        
        # All relationships are primary now
        is_primary = True
        
        query = """
        MATCH (m:MeaningfulUnit {id: $unit_id})
        MATCH (c:Cluster {id: $cluster_id})
        CREATE (m)-[:IN_CLUSTER {
            confidence: $confidence,
            is_primary: $is_primary,
            assignment_method: 'hdbscan',
            assigned_at: datetime()
        }]->(c)
        """
        
        session.run(query, {
            'unit_id': unit_id,
            'cluster_id': cluster_id,
            'confidence': confidence,
            'is_primary': is_primary
        })
    
