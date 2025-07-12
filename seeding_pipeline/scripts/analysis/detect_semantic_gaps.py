#!/usr/bin/env python3
"""
Run semantic gap detection on existing clusters in the database.

This script analyzes existing clusters to find semantic gaps - clusters that are
moderately distant and could benefit from bridge concepts.
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime
import yaml
import logging

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from src.storage.graph_storage import GraphStorageService
from src.analysis.semantic_gap_detection import detect_semantic_gaps


def load_podcast_config(podcast_name: str) -> dict:
    """Load podcast configuration from podcasts.yaml.
    
    Args:
        podcast_name: Name of the podcast
        
    Returns:
        Dictionary containing podcast configuration
        
    Raises:
        ValueError: If podcast not found in configuration
    """
    config_path = Path(__file__).parent.parent.parent / 'config' / 'podcasts.yaml'
    
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


def validate_clusters(graph_storage: GraphStorageService) -> tuple[bool, str, dict]:
    """Validate that there are sufficient clusters for gap detection.
    
    Args:
        graph_storage: Connected graph storage service
        
    Returns:
        Tuple of (can_detect_gaps, message, stats)
    """
    stats = {}
    
    try:
        # Check for clusters with centroids
        count_query = """
        MATCH (c:Cluster)
        WHERE c.status = 'active' AND c.centroid IS NOT NULL
        RETURN count(c) as clusters_with_centroids
        """
        result = graph_storage.query(count_query)
        clusters_with_centroids = result[0]['clusters_with_centroids'] if result else 0
        stats['clusters_with_centroids'] = clusters_with_centroids
        
        # Check for existing semantic gaps
        gap_query = """
        MATCH ()-[g:SEMANTIC_GAP]->()
        RETURN count(g) as existing_gaps
        """
        result = graph_storage.query(gap_query)
        existing_gaps = result[0]['existing_gaps'] if result else 0
        stats['existing_gaps'] = existing_gaps
        
        # Check total clusters
        total_query = """
        MATCH (c:Cluster)
        RETURN count(c) as total_clusters
        """
        result = graph_storage.query(total_query)
        total_clusters = result[0]['total_clusters'] if result else 0
        stats['total_clusters'] = total_clusters
        
        if clusters_with_centroids == 0:
            return False, "No clusters with centroids found in database", stats
        
        if clusters_with_centroids < 2:
            return False, f"Need at least 2 clusters for gap detection, found {clusters_with_centroids}", stats
        
        return True, f"Found {clusters_with_centroids} clusters ready for gap detection", stats
        
    except Exception as e:
        return False, f"Error validating data: {str(e)}", stats


def run_gap_detection_analysis(podcast_name: str, verbose: bool = False):
    """Run semantic gap detection for a specific podcast.
    
    Args:
        podcast_name: Name of the podcast to analyze
        verbose: Enable verbose output
    """
    print(f"\n{'='*60}")
    print(f"SEMANTIC GAP DETECTION FOR: {podcast_name}")
    print(f"{'='*60}\n")
    
    try:
        # Load podcast configuration
        if verbose:
            print("Loading podcast configuration...")
        podcast_config = load_podcast_config(podcast_name)
        
        # Extract database configuration
        db_config = podcast_config.get('database', {})
        neo4j_uri = db_config.get('uri', os.getenv('NEO4J_URI', 'neo4j://localhost:7687'))
        
        # If URI doesn't include port, extract from config
        if 'localhost' in neo4j_uri and 'neo4j_port' in db_config:
            port = db_config['neo4j_port']
            neo4j_uri = f'neo4j://localhost:{port}'
        
        neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
        neo4j_password = os.getenv('NEO4J_PASSWORD')
        
        if not neo4j_password:
            raise ValueError("NEO4J_PASSWORD environment variable must be set")
        
        # Connect to Neo4j
        print(f"Connecting to Neo4j at {neo4j_uri}...")
        graph_storage = GraphStorageService(
            uri=neo4j_uri,
            username=neo4j_user,
            password=neo4j_password
        )
        graph_storage.connect()
        
        # Validate data
        can_detect, message, stats = validate_clusters(graph_storage)
        print(f"\nValidation: {message}")
        
        if verbose:
            print(f"\nDatabase Statistics:")
            print(f"  Total clusters: {stats.get('total_clusters', 0)}")
            print(f"  Clusters with centroids: {stats.get('clusters_with_centroids', 0)}")
            print(f"  Existing semantic gaps: {stats.get('existing_gaps', 0)}")
        
        if not can_detect:
            print("\n✗ Cannot proceed with gap detection")
            graph_storage.close()
            return
        
        # Run gap detection
        print(f"\n{'='*60}")
        print("RUNNING SEMANTIC GAP DETECTION")
        print(f"{'='*60}")
        
        start_time = datetime.now()
        
        with graph_storage.session() as session:
            results = detect_semantic_gaps(session)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Report results
        print(f"\n{'='*60}")
        print("SEMANTIC GAP DETECTION RESULTS")
        print(f"{'='*60}")
        
        if results.get('errors'):
            print(f"⚠ Detection completed with errors:")
            for error in results['errors']:
                print(f"  - {error}")
        else:
            print("✓ Gap detection completed successfully")
        
        print(f"  Duration: {duration:.1f}s")
        print(f"\n  Clusters analyzed: {results.get('clusters_analyzed', 0)}")
        print(f"  Semantic gaps found: {results.get('gaps_detected', 0)}")
        print(f"  Gap relationships created: {results.get('relationships_created', 0)}")
        
        # Show top gaps
        if results.get('top_gaps'):
            print(f"\n  Top Semantic Gaps:")
            for i, gap in enumerate(results['top_gaps'], 1):
                print(f"\n  {i}. {gap['cluster1']} ↔ {gap['cluster2']}")
                print(f"     Similarity: {gap['similarity']:.3f}")
                print(f"     Gap Score: {gap['gap_score']:.3f}")
        
        # Close connection
        graph_storage.close()
        
    except Exception as e:
        print(f"\n✗ Gap detection failed: {str(e)}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run semantic gap detection on existing clusters in the database."
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
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run gap detection
    run_gap_detection_analysis(
        podcast_name=args.podcast,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()