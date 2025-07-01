"""
Main semantic clustering system orchestrator.

Coordinates the complete clustering pipeline:
1. Extract embeddings from Neo4j
2. Perform HDBSCAN clustering
3. Update Neo4j with results
4. Track clustering state

Follows KISS principle - no caching, no optimization unless needed.
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional
import numpy as np
from src.utils.logging import get_logger
from .embeddings_extractor import EmbeddingsExtractor
from .hdbscan_clusterer import SimpleHDBSCANClusterer
from .neo4j_updater import Neo4jClusterUpdater
from .label_generator import ClusterLabeler
from .evolution_tracker import EvolutionTracker

logger = get_logger(__name__)


def get_quarter(date_str: str) -> str:
    """Convert a date string to a quarter string.
    
    Args:
        date_str: Date in YYYY-MM-DD format
        
    Returns:
        Quarter string in format YYYYQN (e.g., "2023Q1")
        
    Raises:
        ValueError: If date_str is invalid
    """
    try:
        # Parse date
        if not date_str:
            raise ValueError("Empty date string")
            
        parts = date_str.split('-')
        if len(parts) != 3:
            raise ValueError(f"Invalid date format: {date_str}")
            
        year = int(parts[0])
        month = int(parts[1])
        
        # Validate month
        if month < 1 or month > 12:
            raise ValueError(f"Invalid month: {month}")
        
        # Calculate quarter
        if month <= 3:
            quarter = 1
        elif month <= 6:
            quarter = 2
        elif month <= 9:
            quarter = 3
        else:
            quarter = 4
            
        return f"{year}Q{quarter}"
        
    except (ValueError, IndexError) as e:
        logger.error(f"Failed to parse date '{date_str}': {e}")
        raise ValueError(f"Invalid date string: {date_str}")


class SemanticClusteringSystem:
    """
    Main orchestrator for semantic clustering pipeline.
    
    Ties together:
    - EmbeddingsExtractor: Gets embeddings from Neo4j
    - SimpleHDBSCANClusterer: Performs clustering
    - ClusterLabeler: Generates human-readable labels
    - EvolutionTracker: Tracks cluster evolution over time
    - Neo4jClusterUpdater: Stores results back to Neo4j
    
    This is the main entry point for clustering operations.
    """
    
    def __init__(self, neo4j_service, llm_service, config: Optional[Dict[str, Any]] = None):
        """
        Initialize semantic clustering system.
        
        Args:
            neo4j_service: GraphStorageService instance
            llm_service: LLMService instance for label generation
            config: Optional configuration dictionary. If None, loads from YAML.
        """
        self.neo4j = neo4j_service
        self.llm_service = llm_service
        
        # Pass config to clusterer
        self.config = config
        
        # Initialize components
        self.embeddings_extractor = EmbeddingsExtractor(neo4j_service)
        self.clusterer = SimpleHDBSCANClusterer(self.config)
        self.labeler = ClusterLabeler(llm_service)
        self.evolution_tracker = EvolutionTracker(neo4j_service)
        self.neo4j_updater = Neo4jClusterUpdater(neo4j_service)
        
        
        logger.info("Initialized SemanticClusteringSystem")
    
    def run_clustering(self, mode: str = "current", snapshot_period: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the complete clustering pipeline.
        
        Steps:
        1. Extract all embeddings from Neo4j
        2. Run HDBSCAN clustering
        3. Generate human-readable cluster labels
        4. Detect evolution from previous clustering (if exists)
        5. Update Neo4j with cluster assignments and evolution
        6. Save clustering state for next comparison
        7. Return summary statistics
        
        Args:
            mode: Clustering mode - "current" for user-facing clusters, "snapshot" for historical snapshots
            snapshot_period: Quarter period for snapshot mode (e.g., "2023Q1"). Required if mode="snapshot"
            
        Returns:
            Dictionary containing:
            - 'status': 'success' or 'error'
            - 'message': Description of outcome
            - 'stats': Clustering statistics
            - 'errors': List of any errors encountered
        
        Raises:
            ValueError: If mode="snapshot" but snapshot_period is not provided
        """
        # Validate parameters
        if mode not in ["current", "snapshot"]:
            raise ValueError(f"Invalid mode '{mode}'. Must be 'current' or 'snapshot'")
        if mode == "snapshot" and not snapshot_period:
            raise ValueError("snapshot_period is required when mode='snapshot'")
            
        # Start monitoring - track execution time
        start_time = time.time()
        
        logger.info(f"Starting semantic clustering in {mode} mode" + 
                   (f" for period {snapshot_period}" if snapshot_period else ""))
        
        result = {
            'status': 'success',
            'message': '',
            'stats': {},
            'errors': []
        }
        
        try:
            # Step 1: Extract embeddings
            logger.info("Step 1: Extracting embeddings from Neo4j")
            embeddings_data = self.embeddings_extractor.extract_all_embeddings()
            
            if not embeddings_data['unit_ids']:
                result['status'] = 'error'
                result['message'] = 'No MeaningfulUnits with embeddings found'
                logger.warning(result['message'])
                return result
            
            logger.info(f"Extracted {len(embeddings_data['unit_ids'])} embeddings")
            
            # Step 2: Perform clustering
            logger.info("Step 2: Performing HDBSCAN clustering")
            cluster_results = self.clusterer.cluster(
                embeddings_data['embeddings'],
                embeddings_data['unit_ids']
            )
            
            # Monitoring: Log clustering quality metrics
            self._log_clustering_metrics(cluster_results)
            
            # Step 3: Generate cluster labels
            logger.info("Step 3: Generating human-readable cluster labels")
            labeled_clusters = self.labeler.generate_labels(
                cluster_results, 
                embeddings_data
            )
            
            # Step 4: Detect evolution from previous clustering
            logger.info("Step 4: Detecting evolution from previous clustering")
            evolution_events = self.evolution_tracker.detect_evolution(
                cluster_results
            )
            
            # Step 5: Update Neo4j
            logger.info("Step 5: Updating Neo4j with cluster assignments")
            update_stats = self.neo4j_updater.update_graph(
                cluster_results,
                labeled_clusters=labeled_clusters,
                mode=mode,
                snapshot_period=snapshot_period
            )
            
            # Step 6: Store evolution events in Neo4j
            logger.info("Step 6: Storing evolution relationships in Neo4j")
            evolution_stats = self.evolution_tracker.store_evolution_events(
                evolution_events
            )
            
            # Step 7: Save clustering state for next comparison
            logger.info("Step 7: Saving clustering state for future evolution tracking")
            state_id = self.evolution_tracker.save_state(cluster_results)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Compile statistics with monitoring metrics
            result['stats'] = {
                'total_units': cluster_results['total_units'],
                'n_clusters': cluster_results['n_clusters'],
                'n_outliers': cluster_results['n_outliers'],
                'outlier_ratio': cluster_results['outlier_ratio'],
                'avg_cluster_size': cluster_results['avg_cluster_size'],
                'min_cluster_size': cluster_results.get('min_cluster_size', 0),
                'max_cluster_size': cluster_results.get('max_cluster_size', 0),
                'labeled_clusters': len(labeled_clusters),
                'clusters_created': update_stats['clusters_created'],
                'relationships_created': update_stats['relationships_created'],
                'evolution_events': len(evolution_events),
                'evolution_splits': evolution_stats['splits_stored'],
                'evolution_merges': evolution_stats['merges_stored'],
                'evolution_continuations': evolution_stats['continuations_stored'],
                'evolution_relationships': evolution_stats['total_relationships'],
                'clustering_state_id': state_id,
                'label_validation': self.labeler.get_validation_stats(),
                'execution_time_seconds': round(execution_time, 2),
                'units_per_second': round(cluster_results['total_units'] / execution_time, 1) if execution_time > 0 else 0
            }
            
            result['message'] = (
                f"Successfully clustered {result['stats']['total_units']} units into "
                f"{result['stats']['n_clusters']} clusters with labels "
                f"({result['stats']['n_outliers']} outliers, {result['stats']['outlier_ratio']:.1%}). "
                f"Evolution tracking: {result['stats']['evolution_events']} events detected "
                f"({result['stats']['evolution_splits']} splits, "
                f"{result['stats']['evolution_merges']} merges, "
                f"{result['stats']['evolution_continuations']} continuations). "
                f"Execution time: {result['stats']['execution_time_seconds']}s "
                f"({result['stats']['units_per_second']} units/sec)"
            )
            
            logger.info(result['message'])
            
        except Exception as e:
            logger.error(f"Clustering pipeline failed: {str(e)}", exc_info=True)
            result['status'] = 'error'
            result['message'] = f'Clustering failed: {str(e)}'
            result['errors'].append(str(e))
        
        return result
    
    def _log_clustering_metrics(self, cluster_results: Dict[str, Any]):
        """
        Log clustering quality metrics and performance indicators.
        
        Monitors:
        - Cluster count and size distribution
        - Outlier ratio with warnings
        - Size imbalances
        
        Args:
            cluster_results: Results from HDBSCAN clustering
        """
        total_units = cluster_results['total_units']
        n_clusters = cluster_results['n_clusters']
        n_outliers = cluster_results['n_outliers']
        outlier_ratio = cluster_results['outlier_ratio']
        
        # Calculate cluster sizes for distribution analysis
        cluster_sizes = []
        for cluster_units in cluster_results['clusters'].values():
            cluster_sizes.append(len(cluster_units))
        
        if cluster_sizes:
            min_size = min(cluster_sizes)
            max_size = max(cluster_sizes)
            avg_size = sum(cluster_sizes) / len(cluster_sizes)
            median_size = sorted(cluster_sizes)[len(cluster_sizes) // 2]
            
            # Store these for later use in stats
            cluster_results['min_cluster_size'] = min_size
            cluster_results['max_cluster_size'] = max_size
            cluster_results['median_cluster_size'] = median_size
        else:
            min_size = max_size = avg_size = median_size = 0
            cluster_results['min_cluster_size'] = 0
            cluster_results['max_cluster_size'] = 0 
            cluster_results['median_cluster_size'] = 0
        
        # Log cluster statistics
        logger.info(f"📊 CLUSTERING METRICS:")
        logger.info(f"   Total units processed: {total_units}")
        logger.info(f"   Clusters created: {n_clusters}")
        logger.info(f"   Outliers: {n_outliers} ({outlier_ratio:.1%})")
        logger.info(f"   Cluster sizes: min={min_size}, max={max_size}, avg={avg_size:.1f}, median={median_size}")
        
        # Quality warnings
        if outlier_ratio > 0.3:
            logger.warning(f"⚠️  HIGH OUTLIER RATIO: {outlier_ratio:.1%} exceeds 30% threshold")
            logger.warning("   Consider reducing min_cluster_size parameter")
            
        if n_clusters < 3:
            logger.warning(f"⚠️  VERY FEW CLUSTERS: Only {n_clusters} clusters created")
            logger.warning("   Consider reducing cluster_selection_epsilon parameter")
            
        if max_size > 100:
            logger.warning(f"⚠️  VERY LARGE CLUSTER: Cluster with {max_size} units detected")
            logger.warning("   Large clusters may need further subdivision")
            
        if min_size < 3 and n_clusters > 0:
            logger.warning(f"⚠️  VERY SMALL CLUSTER: Cluster with {min_size} units detected")
            logger.warning("   Consider increasing min_cluster_size parameter")
    
    
