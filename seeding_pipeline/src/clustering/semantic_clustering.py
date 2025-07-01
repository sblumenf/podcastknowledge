"""
Main semantic clustering system orchestrator.

Coordinates the complete clustering pipeline:
1. Extract embeddings from Neo4j
2. Perform HDBSCAN clustering
3. Update Neo4j with results
4. Track clustering state

Follows KISS principle - no caching, no optimization unless needed.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from src.utils.logging import get_logger
from .embeddings_extractor import EmbeddingsExtractor
from .hdbscan_clusterer import SimpleHDBSCANClusterer
from .neo4j_updater import Neo4jClusterUpdater
from .label_generator import ClusterLabeler

logger = get_logger(__name__)


class SemanticClusteringSystem:
    """
    Main orchestrator for semantic clustering pipeline.
    
    Ties together:
    - EmbeddingsExtractor: Gets embeddings from Neo4j
    - SimpleHDBSCANClusterer: Performs clustering
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
        self.neo4j_updater = Neo4jClusterUpdater(neo4j_service)
        
        
        logger.info("Initialized SemanticClusteringSystem")
    
    def run_clustering(self, current_week: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the complete clustering pipeline.
        
        Steps:
        1. Extract all embeddings from Neo4j
        2. Run HDBSCAN clustering
        3. Update Neo4j with cluster assignments
        4. Return summary statistics
        
        Args:
            current_week: ISO week string (e.g., "2024-W20"). If None, uses current week.
            
        Returns:
            Dictionary containing:
            - 'status': 'success' or 'error'
            - 'message': Description of outcome
            - 'stats': Clustering statistics
            - 'errors': List of any errors encountered
        """
        if not current_week:
            current_week = datetime.now().strftime("%Y-W%U")
            
        logger.info(f"Starting semantic clustering for week {current_week}")
        
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
            
            # Step 3: Generate cluster labels
            logger.info("Step 3: Generating human-readable cluster labels")
            labeled_clusters = self.labeler.generate_labels(
                cluster_results, 
                embeddings_data
            )
            
            # Step 4: Update Neo4j
            logger.info("Step 4: Updating Neo4j with cluster assignments")
            update_stats = self.neo4j_updater.update_graph(
                cluster_results,
                labeled_clusters=labeled_clusters,
                current_week=current_week
            )
            
            # Compile statistics
            result['stats'] = {
                'total_units': cluster_results['total_units'],
                'n_clusters': cluster_results['n_clusters'],
                'n_outliers': cluster_results['n_outliers'],
                'outlier_ratio': cluster_results['outlier_ratio'],
                'avg_cluster_size': cluster_results['avg_cluster_size'],
                'labeled_clusters': len(labeled_clusters),
                'clusters_created': update_stats['clusters_created'],
                'relationships_created': update_stats['relationships_created'],
                'label_validation': self.labeler.get_validation_stats(),
                'week': current_week
            }
            
            result['message'] = (
                f"Successfully clustered {result['stats']['total_units']} units into "
                f"{result['stats']['n_clusters']} clusters with labels "
                f"({result['stats']['n_outliers']} outliers)"
            )
            
            logger.info(result['message'])
            
        except Exception as e:
            logger.error(f"Clustering pipeline failed: {str(e)}", exc_info=True)
            result['status'] = 'error'
            result['message'] = f'Clustering failed: {str(e)}'
            result['errors'].append(str(e))
        
        return result
    
    
