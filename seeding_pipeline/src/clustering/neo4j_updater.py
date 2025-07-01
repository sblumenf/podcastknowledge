"""
Neo4j updater for semantic clustering.

Updates Neo4j with cluster assignments and relationships.
All clustering data stored in Neo4j as single source of truth.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
from src.utils.logging import get_logger

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
        current_week: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update Neo4j with new cluster assignments.
        
        Args:
            cluster_results: Results from HDBSCAN clusterer
            labeled_clusters: Optional dict with cluster labels (from Phase 5)
            current_week: ISO week string (e.g., "2024-W20")
            
        Returns:
            Statistics about the update operation
        """
        if not current_week:
            current_week = datetime.now().strftime("%Y-W%U")
        
        logger.info(f"Updating Neo4j with clustering results for week {current_week}")
        
        stats = {
            'clusters_created': 0,
            'relationships_created': 0,
            'clustering_state_created': False,
            'errors': []
        }
        
        try:
            # Start transaction
            with self.neo4j.driver.session() as session:
                # Step 1: Create ClusteringState node
                state_id = self._create_clustering_state(
                    session, cluster_results, current_week
                )
                stats['clustering_state_created'] = True
                
                # Step 2: Archive old cluster assignments
                self._archive_old_assignments(session, current_week)
                
                # Step 3: Create Cluster nodes
                for cluster_id, units in cluster_results['clusters'].items():
                    cluster_node_id = f"{current_week}_cluster_{cluster_id}"
                    
                    # Get label if available, otherwise use generic label
                    if labeled_clusters and cluster_id in labeled_clusters:
                        label = labeled_clusters[cluster_id].get('label', f'Cluster {cluster_id}')
                    else:
                        label = f'Cluster {cluster_id}'
                    
                    # Get centroid
                    centroid = cluster_results['centroids'].get(cluster_id, [])
                    
                    # Create cluster node
                    self._create_cluster_node(
                        session,
                        cluster_node_id,
                        label,
                        current_week,
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
                            unit_data['confidence'],
                            current_week
                        )
                        stats['relationships_created'] += 1
                
                # Step 5: Link ClusteringState to created clusters
                self._link_state_to_clusters(session, state_id, current_week)
                
            logger.info(
                f"Neo4j update complete: {stats['clusters_created']} clusters, "
                f"{stats['relationships_created']} relationships"
            )
            
        except Exception as e:
            logger.error(f"Failed to update Neo4j: {str(e)}", exc_info=True)
            stats['errors'].append(str(e))
            raise
        
        return stats
    
    def _create_clustering_state(
        self,
        session,
        cluster_results: Dict[str, Any],
        current_week: str
    ) -> str:
        """Create ClusteringState node to track this clustering run."""
        
        timestamp = datetime.now()
        state_id = f"state_{current_week}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        query = """
        CREATE (cs:ClusteringState {
            id: $state_id,
            week: $week,
            timestamp: $timestamp,
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
            'week': current_week,
            'timestamp': timestamp,
            'n_clusters': cluster_results['n_clusters'],
            'n_outliers': cluster_results['n_outliers'],
            'total_units': cluster_results['total_units'],
            'outlier_ratio': cluster_results['outlier_ratio'],
            'avg_cluster_size': cluster_results['avg_cluster_size'],
            'min_cluster_size': cluster_results['min_cluster_size'],
            'max_cluster_size': cluster_results['max_cluster_size'],
        })
        
        return result.single()['state_id']
    
    def _archive_old_assignments(self, session, current_week: str):
        """Mark old cluster assignments as non-primary."""
        
        query = """
        MATCH (m:MeaningfulUnit)-[r:IN_CLUSTER]->(:Cluster)
        WHERE r.is_primary = true
        SET r.is_primary = false,
            r.archived_week = $week
        """
        
        session.run(query, {'week': current_week})
        logger.info("Archived old cluster assignments")
    
    def _create_cluster_node(
        self,
        session,
        cluster_id: str,
        label: str,
        created_week: str,
        member_count: int,
        centroid: List[float]
    ):
        """Create a Cluster node in Neo4j."""
        
        query = """
        CREATE (c:Cluster {
            id: $cluster_id,
            label: $label,
            created_week: $created_week,
            member_count: $member_count,
            status: 'active',
            centroid: $centroid,
            created_timestamp: datetime()
        })
        """
        
        session.run(query, {
            'cluster_id': cluster_id,
            'label': label,
            'created_week': created_week,
            'member_count': member_count,
            'centroid': centroid.tolist() if hasattr(centroid, 'tolist') else list(centroid)
        })
    
    def _create_cluster_assignment(
        self,
        session,
        unit_id: str,
        cluster_id: str,
        confidence: float,
        assigned_week: str
    ):
        """Create IN_CLUSTER relationship."""
        
        query = """
        MATCH (m:MeaningfulUnit {id: $unit_id})
        MATCH (c:Cluster {id: $cluster_id})
        CREATE (m)-[:IN_CLUSTER {
            confidence: $confidence,
            assigned_week: $assigned_week,
            is_primary: true,
            assignment_method: 'hdbscan'
        }]->(c)
        """
        
        session.run(query, {
            'unit_id': unit_id,
            'cluster_id': cluster_id,
            'confidence': confidence,
            'assigned_week': assigned_week
        })
    
    def _link_state_to_clusters(self, session, state_id: str, current_week: str):
        """Link ClusteringState to the clusters it created."""
        
        query = """
        MATCH (cs:ClusteringState {id: $state_id})
        MATCH (c:Cluster {created_week: $week})
        CREATE (cs)-[:CREATED_CLUSTER]->(c)
        """
        
        session.run(query, {
            'state_id': state_id,
            'week': current_week
        })
    
