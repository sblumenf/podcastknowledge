#!/usr/bin/env python3
"""
Recreate Neo4j indexes and constraints.

This script recreates all the necessary indexes and constraints for the knowledge graph database.
It's based on the setup_schema() method in GraphStorageService.

Usage:
    python scripts/recreate_indexes.py
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig
from src.utils.logging import get_logger
import click

logger = get_logger(__name__)


def recreate_indexes(storage: GraphStorageService) -> bool:
    """Recreate all indexes and constraints using the built-in setup_schema method."""
    
    try:
        logger.info("Starting index recreation...")
        
        # Call the existing setup_schema method which contains all index definitions
        storage.setup_schema()
        
        logger.info("✓ Index recreation complete")
        return True
        
    except Exception as e:
        logger.error(f"Error recreating indexes: {str(e)}")
        return False


def verify_indexes(storage: GraphStorageService):
    """Verify that indexes were created successfully."""
    
    logger.info("\nVerifying indexes...")
    
    # Check indexes
    try:
        indexes = storage.query("SHOW INDEXES")
        if indexes:
            logger.info(f"\nFound {len(indexes)} indexes:")
            for idx in indexes:
                logger.info(f"  - {idx.get('name', 'unnamed')} on {idx.get('labelsOrTypes', [])} ({idx.get('properties', [])})")
        else:
            logger.warning("No indexes found")
    except Exception as e:
        logger.error(f"Could not query indexes: {e}")
    
    # Check constraints
    try:
        constraints = storage.query("SHOW CONSTRAINTS")
        if constraints:
            logger.info(f"\nFound {len(constraints)} constraints:")
            for const in constraints:
                logger.info(f"  - {const.get('name', 'unnamed')} on {const.get('labelsOrTypes', [])} ({const.get('properties', [])})")
        else:
            logger.warning("No constraints found")
    except Exception as e:
        logger.error(f"Could not query constraints: {e}")


@click.command()
@click.option('--verify-only', is_flag=True, help='Only verify existing indexes without creating new ones')
def main(verify_only: bool):
    """Recreate Neo4j indexes and constraints."""
    
    print("\n" + "="*80)
    print("NEO4J INDEX RECREATION UTILITY")
    print("="*80 + "\n")
    
    # Initialize storage
    config = PipelineConfig()
    storage = GraphStorageService(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password,
        database=config.neo4j_database
    )
    
    try:
        # Connect to database
        storage.connect()
        
        if verify_only:
            verify_indexes(storage)
        else:
            print("This will recreate the following indexes and constraints:")
            print("\nConstraints (for uniqueness):")
            print("  - Podcast.id")
            print("  - Episode.id")
            print("  - MeaningfulUnit.id")
            print("  - Entity.id")
            print("  - Topic.name")
            
            print("\nIndexes (for performance):")
            print("  - Podcast.title")
            print("  - Episode.title")
            print("  - Episode.published_date")
            print("  - Episode.youtube_url")
            print("  - MeaningfulUnit.start_time")
            print("  - MeaningfulUnit.primary_speaker")
            print("  - Entity.name")
            print("  - Entity.type")
            print("  - MENTIONED_IN.confidence")
            print("  - Vector index on MeaningfulUnit.embedding (768 dimensions, cosine similarity)")
            
            if click.confirm("\nProceed with index recreation?"):
                success = recreate_indexes(storage)
                
                if success:
                    print("\n✓ Indexes recreated successfully")
                    verify_indexes(storage)
                else:
                    print("\n✗ Index recreation failed")
            else:
                print("Index recreation cancelled.")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        print(f"\n✗ Error: {str(e)}")
    finally:
        storage.close()


if __name__ == "__main__":
    main()