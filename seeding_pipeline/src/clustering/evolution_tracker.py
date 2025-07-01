"""
Evolution tracker for semantic clustering.

Tracks how clusters evolve over time by detecting splits, merges, and continuations.
Compares current clustering results with previous state stored in Neo4j to identify
evolution patterns that show how knowledge domains develop.

All evolution data is stored in Neo4j as relationships connecting clusters across time.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EvolutionTracker:
    """
    Tracks cluster evolution by comparing current state with previous state.
    
    Detects three types of evolution:
    - Splits: One cluster becomes multiple clusters (topic differentiation)
    - Merges: Multiple clusters become one cluster (topic convergence) 
    - Continuations: Cluster remains largely stable (topic persistence)
    
    All evolution events are stored as relationships in Neo4j.
    """
    
    def __init__(self, neo4j_service):
        """
        Initialize evolution tracker.
        
        Args:
            neo4j_service: GraphStorageService instance for Neo4j operations
        """
        self.neo4j = neo4j_service
        self.split_threshold = 0.2  # 20% minimum for significant split destination
        self.continuation_threshold = 0.8  # 80% minimum for continuation
        
        logger.info("Initialized EvolutionTracker")
    
    def detect_evolution(self, current_clusters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect how clusters evolved from previous clustering run.
        
        Args:
            current_clusters: Results from current clustering with cluster assignments
            
        Returns:
            List of evolution events with types and metadata:
            [
                {
                    'type': 'split',
                    'from_cluster': 'old_cluster_id',
                    'to_clusters': ['new_cluster_1', 'new_cluster_2'],
                    'proportions': {'new_cluster_1': 0.6, 'new_cluster_2': 0.4}
                },
                ...
            ]
        """
        logger.info("Detecting evolution from previous clustering")
        
        # Load previous clustering state from Neo4j
        previous_state = self._load_previous_state()
        if not previous_state:
            logger.info("No previous state found - this is the first clustering run")
            return []
        
        logger.info("Comparing with previous clustering state")
        
        # Build transition matrix showing unit movements
        transition_matrix = self._build_transition_matrix(
            previous_state['assignments'],
            current_clusters['clusters']
        )
        
        evolution_events = []
        
        # Detect different types of evolution
        evolution_events.extend(self._detect_splits(transition_matrix))
        evolution_events.extend(self._detect_merges(transition_matrix))
        evolution_events.extend(self._detect_continuations(transition_matrix))
        
        logger.info(f"Detected {len(evolution_events)} evolution events:")
        for event in evolution_events:
            logger.info(f"  {event['type']}: {event}")
        
        return evolution_events
    
    def _load_previous_state(self) -> Optional[Dict[str, Any]]:
        """
        Load the most recent clustering state from Neo4j.
        
        Returns:
            Dictionary with previous cluster assignments and metadata,
            or None if no previous state exists
        """
        # Query for the most recent clustering state
        query = """
        MATCH (cs:ClusteringState)
        WITH cs
        ORDER BY cs.timestamp DESC
        LIMIT 1
        
        OPTIONAL MATCH (cs)-[:CREATED_CLUSTER]->(c:Cluster)
        OPTIONAL MATCH (c)<-[r:IN_CLUSTER]-(m:MeaningfulUnit)
        
        WITH cs, collect({
            cluster_id: c.id,
            unit_ids: collect(m.id)
        }) as cluster_data
        
        RETURN cs.timestamp as timestamp,
               cluster_data
        """
        
        try:
            results = self.neo4j.query(query)
            if not results:
                return None
            
            result = results[0]
            
            # Build assignments dictionary: unit_id -> cluster_id
            assignments = {}
            for cluster_info in result['cluster_data']:
                if cluster_info['cluster_id'] and cluster_info['unit_ids']:
                    for unit_id in cluster_info['unit_ids']:
                        if unit_id:  # Skip None values
                            assignments[unit_id] = cluster_info['cluster_id']
            
            return {
                'timestamp': result['timestamp'],
                'assignments': assignments
            }
            
        except Exception as e:
            logger.error(f"Failed to load previous clustering state: {e}")
            return None
    
    def _build_transition_matrix(self, previous_assignments: Dict[str, str], 
                                current_clusters: Dict[int, List[Dict]]) -> Dict[str, Dict[str, int]]:
        """
        Build transition matrix showing how units moved between clusters.
        
        Args:
            previous_assignments: Dict mapping unit_id -> old_cluster_id
            current_clusters: Dict mapping cluster_id -> list of units
            
        Returns:
            Transition matrix: old_cluster_id -> {new_cluster_id -> count}
        """
        logger.debug("Building transition matrix")
        
        # Build current assignments: unit_id -> new_cluster_id
        current_assignments = {}
        for cluster_id, units in current_clusters.items():
            for unit in units:
                current_assignments[unit['unit_id']] = str(cluster_id)
        
        # Count transitions
        transitions = defaultdict(lambda: defaultdict(int))
        
        for unit_id, old_cluster in previous_assignments.items():
            new_cluster = current_assignments.get(unit_id, 'outlier')
            transitions[old_cluster][new_cluster] += 1
        
        logger.debug(f"Built transition matrix with {len(transitions)} old clusters")
        return dict(transitions)
    
    def _detect_splits(self, transitions: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
        """
        Detect when one cluster splits into multiple clusters.
        
        A split occurs when units from one old cluster disperse to multiple new clusters,
        with each destination having >20% of the original units.
        
        Args:
            transitions: Transition matrix showing unit movements
            
        Returns:
            List of split events
        """
        split_events = []
        
        for old_cluster, destinations in transitions.items():
            if len(destinations) <= 1:
                continue  # No split if only one destination
            
            total_units = sum(destinations.values())
            if total_units == 0:
                continue
            
            # Find significant destinations (>20% threshold)
            significant_destinations = []
            for new_cluster, count in destinations.items():
                proportion = count / total_units
                if proportion >= self.split_threshold and new_cluster != 'outlier':
                    significant_destinations.append((new_cluster, count, proportion))
            
            # Must have at least 2 significant destinations to be a split
            if len(significant_destinations) >= 2:
                split_events.append({
                    'type': 'split',
                    'from_cluster': old_cluster,
                    'to_clusters': [dest[0] for dest in significant_destinations],
                    'proportions': {dest[0]: dest[2] for dest in significant_destinations},
                    'total_units': total_units
                })
                
                logger.debug(f"Detected split: {old_cluster} -> {[d[0] for d in significant_destinations]}")
        
        return split_events
    
    def _detect_merges(self, transitions: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
        """
        Detect when multiple clusters merge into one cluster.
        
        A merge occurs when a new cluster receives significant units (>20%) 
        from multiple old clusters.
        
        Args:
            transitions: Transition matrix showing unit movements
            
        Returns:
            List of merge events
        """
        merge_events = []
        
        # Reverse transitions to view from new cluster perspective
        reverse_transitions = defaultdict(lambda: defaultdict(int))
        for old_cluster, destinations in transitions.items():
            for new_cluster, count in destinations.items():
                if new_cluster != 'outlier':
                    reverse_transitions[new_cluster][old_cluster] = count
        
        for new_cluster, sources in reverse_transitions.items():
            if len(sources) <= 1:
                continue  # No merge if only one source
            
            total_units = sum(sources.values())
            if total_units == 0:
                continue
            
            # Find significant sources (>20% threshold)
            significant_sources = []
            for old_cluster, count in sources.items():
                proportion = count / total_units
                if proportion >= self.split_threshold:
                    significant_sources.append((old_cluster, count, proportion))
            
            # Must have at least 2 significant sources to be a merge
            if len(significant_sources) >= 2:
                merge_events.append({
                    'type': 'merge',
                    'from_clusters': [src[0] for src in significant_sources],
                    'to_cluster': new_cluster,
                    'proportions': {src[0]: src[2] for src in significant_sources},
                    'total_units': total_units
                })
                
                logger.debug(f"Detected merge: {[s[0] for s in significant_sources]} -> {new_cluster}")
        
        return merge_events
    
    def _detect_continuations(self, transitions: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
        """
        Detect when a cluster continues largely unchanged.
        
        A continuation occurs when >80% of units from an old cluster 
        move to a single new cluster.
        
        Args:
            transitions: Transition matrix showing unit movements
            
        Returns:
            List of continuation events
        """
        continuation_events = []
        
        for old_cluster, destinations in transitions.items():
            total_units = sum(destinations.values())
            if total_units == 0:
                continue
            
            # Find the dominant destination
            dominant_destination = None
            max_count = 0
            
            for new_cluster, count in destinations.items():
                if new_cluster != 'outlier' and count > max_count:
                    max_count = count
                    dominant_destination = new_cluster
            
            if dominant_destination and max_count > 0:
                proportion = max_count / total_units
                
                # Check if this is a strong continuation (>80% threshold)
                if proportion >= self.continuation_threshold:
                    continuation_events.append({
                        'type': 'continuation',
                        'from_cluster': old_cluster,
                        'to_cluster': dominant_destination,
                        'proportion': proportion,
                        'total_units': total_units
                    })
                    
                    logger.debug(f"Detected continuation: {old_cluster} -> {dominant_destination} ({proportion:.1%})")
        
        return continuation_events
    
    def save_state(self, cluster_results: Dict[str, Any]) -> str:
        """
        Save current clustering state to Neo4j for next comparison.
        
        Args:
            cluster_results: Results from clustering
            
        Returns:
            Created ClusteringState node ID
        """
        logger.info("Saving clustering state")
        
        timestamp = datetime.now()
        state_id = f"state_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Calculate statistics
        cluster_sizes = [len(units) for units in cluster_results['clusters'].values()]
        avg_cluster_size = sum(cluster_sizes) / len(cluster_sizes) if cluster_sizes else 0
        min_cluster_size = min(cluster_sizes) if cluster_sizes else 0
        max_cluster_size = max(cluster_sizes) if cluster_sizes else 0
        outlier_ratio = cluster_results['n_outliers'] / cluster_results['total_units'] if cluster_results['total_units'] > 0 else 0
        
        # Create ClusteringState node
        state_query = """
        CREATE (cs:ClusteringState {
            id: $state_id,
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
        
        result = self.neo4j.query(state_query, {
            'state_id': state_id,
            'timestamp': timestamp,
            'n_clusters': cluster_results['n_clusters'],
            'n_outliers': cluster_results['n_outliers'],
            'total_units': cluster_results['total_units'],
            'outlier_ratio': outlier_ratio,
            'avg_cluster_size': avg_cluster_size,
            'min_cluster_size': min_cluster_size,
            'max_cluster_size': max_cluster_size
        })
        
        created_state_id = result[0]['state_id']
        logger.info(f"Created ClusteringState node: {created_state_id}")
        
        return created_state_id
    
    def store_evolution_events(self, evolution_events: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Store evolution events as relationships in Neo4j.
        
        Creates relationships between cluster nodes to represent evolution:
        - EVOLVED_INTO for splits and continuations
        - MERGED_FROM for merges
        
        Args:
            evolution_events: List of evolution events from detect_evolution()
            
        Returns:
            Statistics about stored relationships
        """
        logger.info(f"Storing {len(evolution_events)} evolution events in Neo4j")
        
        stats = {
            'splits_stored': 0,
            'merges_stored': 0,
            'continuations_stored': 0,
            'total_relationships': 0
        }
        
        for event in evolution_events:
            try:
                if event['type'] == 'split':
                    self._store_split_event(event)
                    stats['splits_stored'] += 1
                    stats['total_relationships'] += len(event['to_clusters'])
                    
                elif event['type'] == 'merge':
                    self._store_merge_event(event)
                    stats['merges_stored'] += 1
                    stats['total_relationships'] += len(event['from_clusters'])
                    
                elif event['type'] == 'continuation':
                    self._store_continuation_event(event)
                    stats['continuations_stored'] += 1
                    stats['total_relationships'] += 1
                    
            except Exception as e:
                logger.error(f"Failed to store evolution event {event}: {e}")
        
        logger.info(f"Stored evolution relationships: {stats}")
        return stats
    
    def _store_split_event(self, event: Dict[str, Any]):
        """Store split event as EVOLVED_INTO relationships."""
        
        from_cluster_id = event['from_cluster']
        
        for to_cluster in event['to_clusters']:
            to_cluster_id = f"cluster_{to_cluster}"
            proportion = event['proportions'].get(to_cluster, 0.0)
            
            query = """
            MATCH (from_cluster:Cluster {id: $from_cluster_id})
            MATCH (to_cluster:Cluster {id: $to_cluster_id})
            CREATE (from_cluster)-[:EVOLVED_INTO {
                type: 'split',
                proportion: $proportion,
                total_units: $total_units,
                created_at: datetime()
            }]->(to_cluster)
            """
            
            self.neo4j.query(query, {
                'from_cluster_id': from_cluster_id,
                'to_cluster_id': to_cluster_id,
                'proportion': proportion,
                'total_units': event['total_units']
            })
            
            logger.debug(f"Stored split relationship: {from_cluster_id} -> {to_cluster_id}")
    
    def _store_merge_event(self, event: Dict[str, Any]):
        """Store merge event as EVOLVED_INTO relationships."""
        
        to_cluster_id = f"cluster_{event['to_cluster']}"
        
        for from_cluster in event['from_clusters']:
            from_cluster_id = from_cluster
            proportion = event['proportions'].get(from_cluster, 0.0)
            
            query = """
            MATCH (from_cluster:Cluster {id: $from_cluster_id})
            MATCH (to_cluster:Cluster {id: $to_cluster_id})
            CREATE (from_cluster)-[:EVOLVED_INTO {
                type: 'merge',
                proportion: $proportion,
                total_units: $total_units,
                created_at: datetime()
            }]->(to_cluster)
            """
            
            self.neo4j.query(query, {
                'from_cluster_id': from_cluster_id,
                'to_cluster_id': to_cluster_id,
                'proportion': proportion,
                'total_units': event['total_units']
            })
            
            logger.debug(f"Stored merge relationship: {from_cluster_id} -> {to_cluster_id}")
    
    def _store_continuation_event(self, event: Dict[str, Any]):
        """Store continuation event as EVOLVED_INTO relationship."""
        
        from_cluster_id = event['from_cluster']
        to_cluster_id = f"cluster_{event['to_cluster']}"
        
        query = """
        MATCH (from_cluster:Cluster {id: $from_cluster_id})
        MATCH (to_cluster:Cluster {id: $to_cluster_id})
        CREATE (from_cluster)-[:EVOLVED_INTO {
            type: 'continuation',
            proportion: $proportion,
            total_units: $total_units,
            created_at: datetime()
        }]->(to_cluster)
        """
        
        self.neo4j.query(query, {
            'from_cluster_id': from_cluster_id,
            'to_cluster_id': to_cluster_id,
            'proportion': event['proportion'],
            'total_units': event['total_units']
        })
        
        logger.debug(f"Stored continuation relationship: {from_cluster_id} -> {to_cluster_id}")