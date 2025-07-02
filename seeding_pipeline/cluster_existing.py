#!/usr/bin/env python3
"""
Manual clustering script for existing data in Neo4j database.

This script allows manual triggering of the clustering process for a specific podcast's
existing MeaningfulUnits in the database. It uses the same clustering system as the 
main pipeline but can be run independently.
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime
import yaml
import logging

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from src.storage.graph_storage import GraphStorageService
from src.services.llm import LLMService
from src.clustering.semantic_clustering import SemanticClusteringSystem
from src.core.env_config import EnvironmentConfig


def load_podcast_config(podcast_name: str) -> dict:
    """Load podcast configuration from podcasts.yaml.
    
    Args:
        podcast_name: Name of the podcast
        
    Returns:
        Dictionary containing podcast configuration
        
    Raises:
        ValueError: If podcast not found in configuration
    """
    config_path = Path(__file__).parent / 'config' / 'podcasts.yaml'
    
    if not config_path.exists():
        raise ValueError(f"Podcast configuration file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Find podcast by name
    for podcast in config.get('podcasts', []):
        if podcast.get('name') == podcast_name:
            return podcast
    
    # List available podcasts for user
    available = [p.get('name') for p in config.get('podcasts', []) if p.get('name')]
    raise ValueError(
        f"Podcast '{podcast_name}' not found in configuration.\n"
        f"Available podcasts: {', '.join(available)}"
    )


def validate_clustering_data(graph_storage: GraphStorageService, force: bool = False) -> tuple[bool, str, dict]:
    """Validate that there's sufficient data for clustering.
    
    Args:
        graph_storage: Connected graph storage service
        force: If True, skip validation and allow clustering anyway
        
    Returns:
        Tuple of (can_cluster, message, stats)
    """
    stats = {}
    
    try:
        # Check for MeaningfulUnits with embeddings
        count_query = """
        MATCH (m:MeaningfulUnit)
        WHERE m.embedding IS NOT NULL
        RETURN count(m) as units_with_embeddings
        """
        result = graph_storage.query(count_query)
        units_with_embeddings = result[0]['units_with_embeddings'] if result else 0
        stats['units_with_embeddings'] = units_with_embeddings
        
        # Check for existing clusters
        cluster_query = """
        MATCH (c:Cluster)
        RETURN count(c) as existing_clusters
        """
        result = graph_storage.query(cluster_query)
        existing_clusters = result[0]['existing_clusters'] if result else 0
        stats['existing_clusters'] = existing_clusters
        
        # Check total units
        total_query = """
        MATCH (m:MeaningfulUnit)
        RETURN count(m) as total_units
        """
        result = graph_storage.query(total_query)
        total_units = result[0]['total_units'] if result else 0
        stats['total_units'] = total_units
        
        # Load clustering config to get minimum requirements
        config_path = Path(__file__).parent / 'config' / 'clustering_config.yaml'
        with open(config_path, 'r') as f:
            clustering_config = yaml.safe_load(f)
        
        min_cluster_size = clustering_config.get('clustering', {}).get('min_cluster_size_fixed', 5)
        
        if units_with_embeddings == 0:
            return False, "No MeaningfulUnits with embeddings found in database", stats
        
        if units_with_embeddings < min_cluster_size * 2:
            if force:
                return True, f"Warning: Only {units_with_embeddings} units found (minimum recommended: {min_cluster_size * 2}). Proceeding due to --force flag.", stats
            else:
                return False, f"Insufficient units for meaningful clustering: {units_with_embeddings} found, need at least {min_cluster_size * 2}", stats
        
        return True, f"Found {units_with_embeddings} units ready for clustering", stats
        
    except Exception as e:
        return False, f"Error validating data: {str(e)}", stats


def run_manual_clustering(podcast_name: str, verbose: bool = False, force: bool = False):
    """Run clustering for a specific podcast.
    
    Args:
        podcast_name: Name of the podcast to cluster
        verbose: Enable verbose output
        force: Force clustering even with insufficient data
    """
    print(f"\n{'='*60}")
    print(f"MANUAL CLUSTERING FOR: {podcast_name}")
    print(f"{'='*60}\n")
    
    try:
        # Load podcast configuration
        if verbose:
            print("Loading podcast configuration...")
        podcast_config = load_podcast_config(podcast_name)
        
        # Extract database configuration
        db_config = podcast_config.get('database', {})
        neo4j_uri = db_config.get('uri', os.getenv('NEO4J_URI', 'neo4j://localhost:7687'))
        neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
        neo4j_password = db_config.get('neo4j_password', os.getenv('NEO4J_PASSWORD', 'password'))
        
        if verbose:
            # Don't print password
            print(f"Database URI: {neo4j_uri}")
            print(f"Database User: {neo4j_user}")
        
        # Initialize services
        print("Initializing services...")
        
        # Connect to Neo4j
        graph_storage = GraphStorageService(
            uri=neo4j_uri,
            username=neo4j_user,
            password=neo4j_password
        )
        graph_storage.connect()
        
        # Validate data
        print("\nValidating data...")
        can_cluster, message, stats = validate_clustering_data(graph_storage, force)
        print(f"  {message}")
        
        if verbose and stats:
            print(f"\nDatabase Statistics:")
            print(f"  Total MeaningfulUnits: {stats.get('total_units', 0)}")
            print(f"  Units with embeddings: {stats.get('units_with_embeddings', 0)}")
            print(f"  Existing clusters: {stats.get('existing_clusters', 0)}")
        
        if not can_cluster:
            print("\nClustering cannot proceed. Use --force to override.")
            sys.exit(1)
        
        # Get API key for LLM service
        gemini_api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not gemini_api_key:
            print("\n✗ Clustering requires GEMINI_API_KEY for label generation")
            raise ValueError("Missing GEMINI_API_KEY")
        
        # Initialize LLM service
        llm_service = LLMService(
            api_key=gemini_api_key,
            model_name=EnvironmentConfig.get_pro_model(),
            max_tokens=65000,
            temperature=0.3
        )
        
        # Load global clustering configuration as base
        config_path = Path(__file__).parent / 'config' / 'clustering_config.yaml'
        with open(config_path, 'r') as f:
            clustering_config = yaml.safe_load(f)
        
        # Use podcast-specific clustering parameters
        if 'clustering' in podcast_config:
            # Update the clustering section with podcast-specific values
            clustering_config['clustering'].update(podcast_config['clustering'])
            
            # Update quality section if max_outlier_ratio is specified
            if 'max_outlier_ratio' in podcast_config['clustering']:
                clustering_config['quality']['max_outlier_ratio'] = podcast_config['clustering']['max_outlier_ratio']
        
        if verbose:
            print(f"\nClustering Configuration:")
            print(f"  Algorithm: HDBSCAN")
            clustering_params = clustering_config.get('clustering', {})
            print(f"  Min cluster size: {clustering_params.get('min_cluster_size_fixed', 5)}")
            print(f"  Min samples: {clustering_params.get('min_samples', 3)}")
            print(f"  Epsilon: {clustering_params.get('epsilon', 0.3)}")
            print(f"  Max outlier ratio: {clustering_config.get('quality', {}).get('max_outlier_ratio', 0.3)}")
        
        # Create clustering system
        clustering_system = SemanticClusteringSystem(graph_storage, llm_service, clustering_config)
        
        # Run clustering
        print(f"\n{'='*60}")
        print("RUNNING CLUSTERING")
        print(f"{'='*60}")
        
        start_time = datetime.now()
        result = clustering_system.run_clustering()
        duration = (datetime.now() - start_time).total_seconds()
        
        # Report results
        print(f"\n{'='*60}")
        print("CLUSTERING RESULTS")
        print(f"{'='*60}")
        
        if result['status'] == 'success':
            print("✓ Clustering completed successfully")
            print(f"  Duration: {duration:.1f}s")
            
            if 'stats' in result:
                stats = result['stats']
                print(f"\n  Clusters created: {stats.get('clusters_created', 'N/A')}")
                print(f"  Units clustered: {stats.get('units_clustered', 'N/A')}")
                print(f"  Outliers: {stats.get('outliers', 'N/A')}")
                
                if verbose and 'cluster_details' in stats:
                    print(f"\n  Cluster Details:")
                    for cluster in stats['cluster_details']:
                        print(f"    - {cluster['label']}: {cluster['size']} units")
        else:
            print(f"⚠ Clustering completed with issues: {result.get('message', 'Unknown issue')}")
            if verbose and 'error' in result:
                print(f"  Error details: {result['error']}")
        
        # Close connection
        graph_storage.close()
        
    except Exception as e:
        print(f"\n✗ Clustering failed: {str(e)}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run clustering on existing data in the database for a specific podcast."
    )
    
    parser.add_argument(
        '--podcast', '-p',
        required=True,
        help='Name of the podcast (must match name in podcasts.yaml)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force clustering even if data seems insufficient'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run clustering
    run_manual_clustering(
        podcast_name=args.podcast,
        verbose=args.verbose,
        force=args.force
    )


if __name__ == "__main__":
    main()