"""
HDBSCAN clustering implementation for semantic clustering.

Implements clustering with config-based parameters following KISS principle.
IMPORTANT: HDBSCAN is NOT self-healing. If results are poor, manually adjust 
parameters and re-run.
"""

import numpy as np
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from src.utils.logging import get_logger

# Import HDBSCAN - will be installed if not present
try:
    import hdbscan
except ImportError:
    logger = get_logger(__name__)
    logger.error("HDBSCAN not installed. Install with: pip install hdbscan")
    raise

logger = get_logger(__name__)


class SimpleHDBSCANClusterer:
    """
    Simple HDBSCAN clustering implementation with config-based parameters.
    
    Key principles:
    - Parameters from configuration, not hardcoded
    - No self-healing - manual parameter tuning required
    - Calculates centroids for each cluster
    - Returns comprehensive clustering results
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize clusterer with configuration.
        
        If config is not provided, loads from config/clustering_config.yaml.
        
        Args:
            config: Configuration dictionary. If None, loads from YAML file.
        """
        if config is None:
            # Load config from YAML file
            config_path = Path(__file__).parent.parent.parent / 'config' / 'clustering_config.yaml'
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    logger.info(f"Loaded clustering config from {config_path}")
            else:
                logger.warning(f"Config file not found at {config_path}, using defaults")
                config = {}
        
        self.config = config.get('clustering', {})
        
        # Extract parameters with defaults
        self.min_samples = self.config.get('min_samples', 3)
        self.epsilon = self.config.get('epsilon', 0.3)
        self.min_cluster_size_formula = self.config.get('min_cluster_size_formula', 'sqrt')
        self.min_cluster_size_fixed = self.config.get('min_cluster_size_fixed', 10)
        
        logger.info(f"Initialized clusterer with config: {self.config}")
    
    def cluster(self, embeddings: np.ndarray, unit_ids: List[str]) -> Dict[str, Any]:
        """
        Perform HDBSCAN clustering on embeddings.
        
        Args:
            embeddings: numpy array of shape (n_samples, 768)
            unit_ids: List of unit identifiers matching embeddings
            
        Returns:
            Dictionary containing:
            - 'clusters': Dict mapping cluster_id to list of unit assignments
            - 'centroids': Dict mapping cluster_id to centroid vector
            - 'n_clusters': Number of clusters formed
            - 'n_outliers': Number of outlier points
            - 'total_units': Total number of units processed
            - 'outlier_ratio': Fraction of points that are outliers
            - 'clusterer': HDBSCAN clusterer object for advanced use
        """
        n_samples = len(embeddings)
        
        if n_samples == 0:
            logger.warning("No embeddings to cluster")
            return self._empty_results()
        
        # Calculate min_cluster_size based on formula
        min_cluster_size = self._calculate_min_cluster_size(n_samples)
        
        logger.info(
            f"Clustering {n_samples} units with parameters: "
            f"min_cluster_size={min_cluster_size}, "
            f"min_samples={self.min_samples}, "
            f"epsilon={self.epsilon}"
        )
        
        # Configure HDBSCAN
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=self.min_samples,
            metric='cosine',  # Best for text embeddings
            cluster_selection_epsilon=self.epsilon,
            cluster_selection_method='eom',  # Excess of Mass
            prediction_data=True,  # Enable soft clustering
            core_dist_n_jobs=-1  # Use all CPU cores
        )
        
        # Perform clustering
        cluster_labels = clusterer.fit_predict(embeddings)
        
        # Process results
        results = self._process_clustering_results(
            cluster_labels,
            clusterer.probabilities_,
            embeddings,
            unit_ids,
            clusterer
        )
        
        # Note: Quality score calculation removed per Phase 3 requirements
        
        logger.info(
            f"Clustering complete: {results['n_clusters']} clusters, "
            f"{results['n_outliers']} outliers ({results['outlier_ratio']:.1%}), "
            f"avg cluster size: {results['avg_cluster_size']:.1f}"
        )
        
        return results
    
    def _calculate_min_cluster_size(self, n_samples: int) -> int:
        """Calculate min_cluster_size based on configuration."""
        if self.min_cluster_size_formula == 'fixed':
            return self.min_cluster_size_fixed
        elif self.min_cluster_size_formula == 'sqrt':
            # Use sqrt formula with minimum of 5
            return max(5, int(np.sqrt(n_samples) / 2))
        else:
            # Default to sqrt if unknown formula
            logger.warning(
                f"Unknown min_cluster_size_formula: {self.min_cluster_size_formula}, "
                "defaulting to sqrt"
            )
            return max(5, int(np.sqrt(n_samples) / 2))
    
    def _process_clustering_results(
        self,
        cluster_labels: np.ndarray,
        probabilities: np.ndarray,
        embeddings: np.ndarray,
        unit_ids: List[str],
        clusterer: hdbscan.HDBSCAN
    ) -> Dict[str, Any]:
        """Process raw clustering results into structured format."""
        
        # Count clusters and outliers
        unique_labels = np.unique(cluster_labels)
        n_clusters = len(unique_labels[unique_labels >= 0])
        n_outliers = np.sum(cluster_labels == -1)
        
        # Build cluster assignments
        clusters = defaultdict(list)
        for idx, (unit_id, label, prob) in enumerate(zip(unit_ids, cluster_labels, probabilities)):
            if label >= 0:  # Not an outlier
                clusters[int(label)].append({
                    'unit_id': unit_id,
                    'confidence': float(prob),
                    'index': idx  # Keep index for centroid calculation
                })
        
        # Calculate centroids (Task 3.3)
        centroids = self._calculate_centroids(clusters, embeddings)
        
        # Calculate cluster statistics
        cluster_sizes = [len(units) for units in clusters.values()]
        
        return {
            'clusters': dict(clusters),
            'centroids': centroids,
            'n_clusters': n_clusters,
            'n_outliers': n_outliers,
            'total_units': len(unit_ids),
            'outlier_ratio': n_outliers / len(unit_ids) if unit_ids else 0,
            'cluster_sizes': cluster_sizes,
            'avg_cluster_size': np.mean(cluster_sizes) if cluster_sizes else 0,
            'min_cluster_size': min(cluster_sizes) if cluster_sizes else 0,
            'max_cluster_size': max(cluster_sizes) if cluster_sizes else 0,
            'clusterer': clusterer  # Keep for soft clustering later
        }
    
    def _calculate_centroids(
        self,
        clusters: Dict[int, List[Dict[str, Any]]],
        embeddings: np.ndarray
    ) -> Dict[int, np.ndarray]:
        """
        Calculate centroid for each cluster (Task 3.3).
        
        Centroid is the mean of all embeddings in the cluster.
        """
        centroids = {}
        
        for cluster_id, units in clusters.items():
            # Get indices of units in this cluster
            indices = [unit['index'] for unit in units]
            
            # Get embeddings for these units
            cluster_embeddings = embeddings[indices]
            
            # Calculate mean (centroid)
            centroid = np.mean(cluster_embeddings, axis=0)
            
            # Normalize to unit length for cosine similarity
            centroid_norm = np.linalg.norm(centroid)
            if centroid_norm > 0:
                centroid = centroid / centroid_norm
            
            centroids[cluster_id] = centroid
            
        return centroids
    
    
    def _empty_results(self) -> Dict[str, Any]:
        """Return empty results structure."""
        return {
            'clusters': {},
            'centroids': {},
            'n_clusters': 0,
            'n_outliers': 0,
            'total_units': 0,
            'outlier_ratio': 0,
            'cluster_sizes': [],
            'avg_cluster_size': 0,
            'min_cluster_size': 0,
            'max_cluster_size': 0,
            'clusterer': None
        }
    
