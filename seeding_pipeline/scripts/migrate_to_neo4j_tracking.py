#!/usr/bin/env python3
"""
Migration script to mark existing Neo4j episodes as complete.

This script updates existing Episode nodes in Neo4j to add tracking properties
required by the new Neo4j-based episode tracking system.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import PipelineConfig
from src.storage import GraphStorageService
from src.utils.log_utils import get_logger

logger = get_logger(__name__)


def migrate_episodes(graph_service: GraphStorageService, dry_run: bool = False) -> dict:
    """
    Migrate existing episodes to have proper tracking fields.
    
    Args:
        graph_service: Neo4j graph storage service
        dry_run: If True, only show what would be done without making changes
        
    Returns:
        Dictionary with migration statistics
    """
    stats = {
        'total_episodes': 0,
        'episodes_with_segments': 0,
        'episodes_marked_complete': 0,
        'episodes_missing_segments': 0,
        'episodes_already_complete': 0,
        'errors': []
    }
    
    try:
        # Query all Episode nodes
        query = """
        MATCH (e:Episode)
        OPTIONAL MATCH (e)-[:HAS_SEGMENT]->(s:Segment)
        WITH e, COUNT(s) as segment_count
        RETURN e.id as episode_id,
               e.processing_status as status,
               e.title as title,
               e.vtt_path as vtt_path,
               segment_count,
               e.processed_at as processed_at
        ORDER BY e.id
        """
        
        episodes = graph_service.query(query)
        stats['total_episodes'] = len(episodes)
        
        logger.info(f"Found {len(episodes)} episodes in Neo4j")
        
        for episode in episodes:
            episode_id = episode['episode_id']
            current_status = episode.get('status')
            segment_count = episode['segment_count']
            
            # Check if already has tracking status
            if current_status == 'complete':
                stats['episodes_already_complete'] += 1
                logger.debug(f"Episode {episode_id} already marked as complete")
                continue
            
            # Check if episode has segments (indicates it was processed)
            if segment_count > 0:
                stats['episodes_with_segments'] += 1
                
                if not dry_run:
                    # Update episode with tracking properties
                    update_query = """
                    MATCH (e:Episode {id: $episode_id})
                    SET e.processing_status = 'complete',
                        e.segment_count = $segment_count
                    """
                    # Add processed_at if not already present
                    if not episode.get('processed_at'):
                        update_query += ", e.processed_at = datetime()"
                    
                    update_query += " RETURN e.id"
                    
                    params = {
                        'episode_id': episode_id,
                        'segment_count': segment_count
                    }
                    
                    try:
                        result = graph_service.query(update_query, params)
                        if result:
                            stats['episodes_marked_complete'] += 1
                            logger.info(f"Marked episode {episode_id} as complete with {segment_count} segments")
                    except Exception as e:
                        error_msg = f"Failed to update episode {episode_id}: {str(e)}"
                        logger.error(error_msg)
                        stats['errors'].append(error_msg)
                else:
                    logger.info(f"[DRY RUN] Would mark episode {episode_id} as complete with {segment_count} segments")
                    stats['episodes_marked_complete'] += 1
            else:
                stats['episodes_missing_segments'] += 1
                logger.warning(f"Episode {episode_id} has no segments, skipping")
        
        # Add file hash calculation if VTT files are available
        if not dry_run and stats['episodes_marked_complete'] > 0:
            logger.info("Calculating file hashes for marked episodes...")
            
            hash_query = """
            MATCH (e:Episode)
            WHERE e.processing_status = 'complete' 
            AND e.vtt_path IS NOT NULL 
            AND e.file_hash IS NULL
            RETURN e.id as episode_id, e.vtt_path as vtt_path
            """
            
            episodes_needing_hash = graph_service.query(hash_query)
            
            for episode in episodes_needing_hash:
                vtt_path = episode['vtt_path']
                if Path(vtt_path).exists():
                    try:
                        from src.tracking import calculate_file_hash
                        file_hash = calculate_file_hash(vtt_path)
                        
                        hash_update_query = """
                        MATCH (e:Episode {id: $episode_id})
                        SET e.file_hash = $file_hash
                        """
                        
                        graph_service.query(hash_update_query, {
                            'episode_id': episode['episode_id'],
                            'file_hash': file_hash
                        })
                        
                        logger.debug(f"Added file hash to episode {episode['episode_id']}")
                    except Exception as e:
                        logger.warning(f"Could not calculate hash for {vtt_path}: {e}")
        
        return stats
        
    except Exception as e:
        error_msg = f"Migration failed: {str(e)}"
        logger.error(error_msg)
        stats['errors'].append(error_msg)
        return stats


def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(
        description='Migrate existing Neo4j episodes for tracking system'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Load configuration
        if args.config:
            config = PipelineConfig.from_file(Path(args.config))
        else:
            config = PipelineConfig()
        
        # Initialize graph service
        graph_service = GraphStorageService(config)
        
        # Run migration
        print(f"\nStarting episode migration {'(DRY RUN)' if args.dry_run else ''}...")
        stats = migrate_episodes(graph_service, dry_run=args.dry_run)
        
        # Print results
        print("\nMigration Results:")
        print("=" * 50)
        print(f"Total episodes found:        {stats['total_episodes']}")
        print(f"Episodes with segments:      {stats['episodes_with_segments']}")
        print(f"Episodes already complete:   {stats['episodes_already_complete']}")
        print(f"Episodes marked complete:    {stats['episodes_marked_complete']}")
        print(f"Episodes without segments:   {stats['episodes_missing_segments']}")
        
        if stats['errors']:
            print(f"\nErrors encountered: {len(stats['errors'])}")
            for error in stats['errors']:
                print(f"  - {error}")
        
        if args.dry_run:
            print("\nThis was a dry run. No changes were made.")
            print("Run without --dry-run to apply changes.")
        else:
            print("\nMigration completed successfully!")
        
        return 0 if not stats['errors'] else 1
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        print(f"\nError: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())