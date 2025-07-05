#!/usr/bin/env python3
"""
Reset the Neo4j database to a virgin state by removing all nodes, relationships, and indexes.
This script will completely clear the database as if no episodes were ever processed.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig
from src.utils.logging import get_logger
import click

logger = get_logger(__name__)


def clear_all_data(storage: GraphStorageService):
    """Remove all nodes and relationships from the database."""
    
    # Get counts before deletion
    count_query = """
    MATCH (n)
    WITH count(n) as node_count
    MATCH ()-[r]->()
    RETURN node_count, count(r) as rel_count
    """
    
    try:
        counts = storage.query(count_query)
        if counts:
            node_count = counts[0]['node_count']
            rel_count = counts[0]['rel_count']
            logger.info(f"Found {node_count} nodes and {rel_count} relationships to delete")
        else:
            # Handle case where there are nodes but no relationships
            node_only_query = "MATCH (n) RETURN count(n) as node_count"
            node_result = storage.query(node_only_query)
            node_count = node_result[0]['node_count'] if node_result else 0
            rel_count = 0
            logger.info(f"Found {node_count} nodes and {rel_count} relationships to delete")
    except:
        logger.warning("Could not get initial counts")
        node_count = "unknown"
        rel_count = "unknown"
    
    # Delete all relationships first (required before deleting nodes)
    logger.info("Deleting all relationships...")
    storage.query("MATCH ()-[r]->() DELETE r")
    
    # Delete all nodes
    logger.info("Deleting all nodes...")
    storage.query("MATCH (n) DELETE n")
    
    # Verify deletion
    verify_query = "MATCH (n) RETURN count(n) as remaining_nodes"
    result = storage.query(verify_query)
    remaining = result[0]['remaining_nodes'] if result else 0
    
    if remaining == 0:
        logger.info("✓ Database successfully cleared")
        return True
    else:
        logger.error(f"Failed to clear database - {remaining} nodes remain")
        return False


def clear_indexes(storage: GraphStorageService):
    """Remove all indexes and constraints from the database."""
    
    logger.info("Checking for indexes and constraints...")
    
    # Get all indexes
    index_query = "SHOW INDEXES"
    try:
        indexes = storage.query(index_query)
        if indexes:
            logger.info(f"Found {len(indexes)} indexes")
            for idx in indexes:
                try:
                    drop_query = f"DROP INDEX {idx['name']}"
                    storage.query(drop_query)
                    logger.info(f"Dropped index: {idx['name']}")
                except Exception as e:
                    logger.warning(f"Could not drop index {idx.get('name', 'unknown')}: {e}")
    except:
        logger.info("No indexes found or unable to query indexes")
    
    # Get all constraints
    constraint_query = "SHOW CONSTRAINTS"
    try:
        constraints = storage.query(constraint_query)
        if constraints:
            logger.info(f"Found {len(constraints)} constraints")
            for const in constraints:
                try:
                    drop_query = f"DROP CONSTRAINT {const['name']}"
                    storage.query(drop_query)
                    logger.info(f"Dropped constraint: {const['name']}")
                except Exception as e:
                    logger.warning(f"Could not drop constraint {const.get('name', 'unknown')}: {e}")
    except:
        logger.info("No constraints found or unable to query constraints")


def clear_checkpoint_files():
    """Remove any checkpoint files from the filesystem."""
    
    checkpoint_dir = Path("checkpoints")
    if checkpoint_dir.exists():
        checkpoint_files = list(checkpoint_dir.glob("*.json"))
        if checkpoint_files:
            logger.info(f"Found {len(checkpoint_files)} checkpoint files")
            for file in checkpoint_files:
                file.unlink()
                logger.info(f"Deleted checkpoint: {file.name}")
        else:
            logger.info("No checkpoint files found")
    else:
        logger.info("No checkpoints directory found")


def clear_logs():
    """Clear processing logs (optional)."""
    
    log_dir = Path("logs")
    if log_dir.exists():
        log_files = list(log_dir.glob("*.log"))
        if log_files:
            logger.info(f"Found {len(log_files)} log files")
            return len(log_files)
    return 0


@click.command()
@click.option('--force', is_flag=True, help='Skip confirmation prompt')
@click.option('--clear-logs', is_flag=True, help='Also clear log files')
def main(force: bool, clear_logs: bool):
    """Reset the database to a virgin state."""
    
    print("\n" + "="*80)
    print("DATABASE RESET UTILITY")
    print("="*80 + "\n")
    
    print("This will completely clear the Neo4j database, including:")
    print("- All Episode nodes")
    print("- All MeaningfulUnit nodes")
    print("- All Knowledge nodes")
    print("- All Speaker nodes")
    print("- All relationships")
    print("- All indexes and constraints")
    print("- All checkpoint files")
    
    if clear_logs:
        print("- All log files")
    
    print("\nThe system will be reset to its initial virgin state.")
    
    if not force:
        if not click.confirm("\nAre you sure you want to proceed?"):
            print("Reset cancelled.")
            return
    
    # Initialize storage
    config = PipelineConfig()
    storage = GraphStorageService(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password,
        database=config.neo4j_database
    )
    
    try:
        print("\nStarting database reset...")
        
        # Clear all data
        success = clear_all_data(storage)
        
        if success:
            # Clear indexes
            clear_indexes(storage)
            
            # Clear checkpoint files
            clear_checkpoint_files()
            
            # Clear logs if requested
            if clear_logs:
                log_count = clear_logs()
                if log_count > 0:
                    if click.confirm(f"\nDelete {log_count} log files?"):
                        for log_file in Path("logs").glob("*.log"):
                            log_file.unlink()
                        logger.info(f"Deleted {log_count} log files")
            
            print("\n" + "="*80)
            print("✓ DATABASE RESET COMPLETE")
            print("="*80)
            print("\nThe system has been restored to a virgin state.")
            print("You can now process episodes as if starting fresh.")
        else:
            print("\n✗ Database reset failed. Please check the logs.")
            
    except Exception as e:
        logger.error(f"Error during reset: {str(e)}")
        print(f"\n✗ Error: {str(e)}")
    finally:
        storage.close()


if __name__ == "__main__":
    main()