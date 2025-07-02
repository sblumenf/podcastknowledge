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
    - ClusteringState nodes to track runs
    
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
        labeled_clusters: Optional[Dict[int, Dict[str, Any]]] = None,
        mode: str = "current",
        snapshot_period: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update Neo4j with new cluster assignments.
        
        Args:
            cluster_results: Results from HDBSCAN clusterer
            labeled_clusters: Optional dict with cluster labels (from Phase 5)
            mode: Clustering mode - "current" or "snapshot"
            snapshot_period: Quarter period for snapshot mode (e.g., "2023Q1")
            
        Returns:
            Statistics about the update operation
        """
        logger.info(f"Updating Neo4j with clustering results in {mode} mode" + 
                   (f" for period {snapshot_period}" if snapshot_period else ""))
        
        stats = {
            'clusters_created': 0,
            'relationships_created': 0,
            'clustering_state_created': False,
            'errors': []
        }
        
        def _execute_update():
            # Start transaction
            with self.neo4j.driver.session() as session:
                # Step 1: Create ClusteringState node
                state_id = self._create_clustering_state(
                    session, cluster_results, mode, snapshot_period
                )
                stats['clustering_state_created'] = True
                
                # Step 2: Archive old cluster assignments
                # Only archive if in current mode (snapshots don't affect current clusters)
                if mode == "current":
                    self._archive_old_clusters(session)
                    self._archive_old_assignments(session)
                
                # Step 3: Create Cluster nodes
                for cluster_id, units in cluster_results['clusters'].items():
                    # Generate cluster ID based on mode
                    if mode == "current":
                        cluster_node_id = f"current_cluster_{cluster_id}"
                    else:  # snapshot mode
                        cluster_node_id = f"snapshot_{snapshot_period}_cluster_{cluster_id}"
                    
                    # Get label if available, otherwise use generic label
                    if labeled_clusters and cluster_id in labeled_clusters:
                        label = labeled_clusters[cluster_id].get('label', f'Cluster {cluster_id}')
                    else:
                        label = f'Cluster {cluster_id}'
                    
                    # Get centroid
                    centroid = cluster_results['centroids'].get(cluster_id, [])
                    
                    # Create cluster node with mode-specific properties
                    self._create_cluster_node(
                        session,
                        cluster_node_id,
                        label,
                        len(units),
                        centroid,
                        mode=mode,
                        period=snapshot_period
                    )
                    stats['clusters_created'] += 1
                    
                    # Step 4: Create IN_CLUSTER relationships
                    for unit_data in units:
                        self._create_cluster_assignment(
                            session,
                            unit_data['unit_id'],
                            cluster_node_id,
                            unit_data['confidence'],
                            mode
                        )
                        stats['relationships_created'] += 1
                
                # Step 5: Link ClusteringState to created clusters
                self._link_state_to_clusters(session, state_id)
        
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
    
    def _create_clustering_state(
        self,
        session,
        cluster_results: Dict[str, Any],
        mode: str,
        snapshot_period: Optional[str] = None
    ) -> str:
        """Create ClusteringState node to track this clustering run."""
        
        timestamp = datetime.now()
        if mode == "snapshot" and snapshot_period:
            state_id = f"state_{snapshot_period}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        else:
            state_id = f"state_current_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        query = """
        CREATE (cs:ClusteringState {
            id: $state_id,
            timestamp: $timestamp,
            type: $type,
            period: $period,
            n_clusters: $n_clusters,
            n_outliers: $n_outliers,
            total_units: $total_units,
            outlier_ratio: $outlier_ratio,
            avg_cluster_size: $avg_cluster_size,
            min_cluster_size: $min_cluster_size,
            max_cluster_size: $max_cluster_size,
            status: 'completed'
        })
        RETURN cs.id as state_id
        """
        
        result = session.run(query, {
            'state_id': state_id,
            'timestamp': timestamp,
            'type': mode,
            'period': snapshot_period,
            'n_clusters': cluster_results['n_clusters'],
            'n_outliers': cluster_results['n_outliers'],
            'total_units': cluster_results['total_units'],
            'outlier_ratio': cluster_results['outlier_ratio'],
            'avg_cluster_size': cluster_results['avg_cluster_size'],
            'min_cluster_size': cluster_results['min_cluster_size'],
            'max_cluster_size': cluster_results['max_cluster_size'],
        })
        
        return result.single()['state_id']
    
    def _archive_old_clusters(self, session):
        """Archive existing current clusters."""
        
        query = """
        MATCH (c:Cluster {type: 'current'})
        SET c.status = 'archived',
            c.archived_at = datetime()
        """
        
        session.run(query)
        logger.info("Archived existing current clusters")
    
    def _archive_old_assignments(self, session):
        """Mark old cluster assignments as non-primary."""
        
        query = """
        MATCH (m:MeaningfulUnit)-[r:IN_CLUSTER]->(c:Cluster {type: 'current'})
        WHERE r.is_primary = true
        SET r.is_primary = false,
            r.archived_at = datetime()
        """
        
        session.run(query)
        logger.info("Archived old cluster assignments")
    
    def _create_cluster_node(
        self,
        session,
        cluster_id: str,
        label: str,
        member_count: int,
        centroid: List[float],
        mode: str = "current",
        period: Optional[str] = None
    ):
        """Create a Cluster node in Neo4j with mode-specific properties."""
        
        # Build properties based on mode
        properties = {
            'id': cluster_id,
            'label': label,
            'member_count': member_count,
            'status': 'active',
            'centroid': centroid.tolist() if hasattr(centroid, 'tolist') else list(centroid),
            'created_timestamp': datetime.now(),
            'type': mode  # Add type property
        }
        
        # Add period for snapshot mode
        if mode == "snapshot" and period:
            properties['period'] = period
        
        query = """
        CREATE (c:Cluster $properties)
        """
        
        session.run(query, properties=properties)
    
    def _create_cluster_assignment(
        self,
        session,
        unit_id: str,
        cluster_id: str,
        confidence: float,
        mode: str = "current"
    ):
        """Create IN_CLUSTER relationship with mode-specific properties."""
        
        # Set is_primary based on mode
        # Current mode: is_primary=true (user-facing clusters)
        # Snapshot mode: is_primary=false (historical clusters)
        is_primary = mode == "current"
        
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
    
    def _link_state_to_clusters(self, session, state_id: str):
        """Link ClusteringState to the clusters it created."""
        
        # Get the timestamp from the state to find clusters created at the same time
        query = """
        MATCH (cs:ClusteringState {id: $state_id})
        MATCH (c:Cluster)
        WHERE c.created_timestamp >= cs.timestamp - duration('PT1S')
          AND c.created_timestamp <= cs.timestamp + duration('PT1S')
        CREATE (cs)-[:CREATED_CLUSTER]->(c)
        """
        
        session.run(query, {
            'state_id': state_id
        })
    
