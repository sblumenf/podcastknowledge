#!/usr/bin/env python3
"""
Database cleanup script to remove all Topic nodes and HAS_TOPIC relationships.

This script removes all traces of the topic system from Neo4j databases
as part of the transition to semantic clustering.

Usage:
    python cleanup_topics_from_database.py --podcast-name "mel_robbins" --neo4j-uri "neo4j://localhost:7687"
    python cleanup_topics_from_database.py --podcast-name "mfm" --neo4j-uri "neo4j://localhost:7688"
"""

import argparse
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.graph_storage import GraphStorageService
from src.utils.logging import setup_logging, get_logger

# Setup logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)


class TopicSystemCleaner:
    """
    Removes all Topic nodes and HAS_TOPIC relationships from Neo4j database.
    """
    
    def __init__(self, neo4j_uri: str, username: str = "neo4j", password: str = "password"):
        """
        Initialize the topic system cleaner.
        
        Args:
            neo4j_uri: Neo4j connection URI (e.g., "neo4j://localhost:7687")
            username: Neo4j username
            password: Neo4j password
        """
        self.graph_storage = GraphStorageService(
            uri=neo4j_uri,
            username=username,
            password=password
        )
        self.cleanup_log = []
        
    def cleanup_topic_system(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Remove all Topic nodes and HAS_TOPIC relationships.
        
        Args:
            dry_run: If True, show what would be removed without actually removing
            
        Returns:
            Dict with cleanup results
        """
        logger.info(f"Starting topic system cleanup (dry_run={dry_run})")
        
        try:
            # Connect to database
            self.graph_storage.connect()
            
            # Step 1: Count existing topics and relationships
            topic_count = self._count_topics()
            relationship_count = self._count_topic_relationships()
            
            logger.info(f"Found {topic_count} Topic nodes and {relationship_count} HAS_TOPIC relationships")
            self.cleanup_log.append(f"Found {topic_count} topics and {relationship_count} relationships")
            
            if not dry_run:
                # Step 2: Create backup
                self._create_backup()
                
                # Step 3: Remove HAS_TOPIC relationships first
                relationships_removed = self._remove_topic_relationships()
                logger.info(f"Removed {relationships_removed} HAS_TOPIC relationships")
                
                # Step 4: Remove Topic nodes
                topics_removed = self._remove_topic_nodes()
                logger.info(f"Removed {topics_removed} Topic nodes")
                
                # Step 5: Drop topic constraints (if any exist)
                self._drop_topic_constraints()
                
                # Step 6: Validate removal
                validation = self._validate_removal()
                
                return {
                    'dry_run': False,
                    'topics_removed': topics_removed,
                    'relationships_removed': relationships_removed,
                    'validation': validation,
                    'log': self.cleanup_log
                }
            else:
                logger.info("DRY RUN - No changes made to database")
                return {
                    'dry_run': True,
                    'topics_found': topic_count,
                    'relationships_found': relationship_count,
                    'log': self.cleanup_log
                }
                
        except Exception as e:
            logger.error(f"Topic cleanup failed: {e}", exc_info=True)
            raise
        finally:
            self.graph_storage.disconnect()
    
    def _count_topics(self) -> int:
        """Count existing Topic nodes."""
        result = self.graph_storage.query("MATCH (t:Topic) RETURN count(t) as count")
        return result[0]['count'] if result else 0
    
    def _count_topic_relationships(self) -> int:
        """Count HAS_TOPIC relationships."""
        result = self.graph_storage.query("MATCH ()-[r:HAS_TOPIC]->() RETURN count(r) as count")
        return result[0]['count'] if result else 0
    
    def _create_backup(self):
        """Create backup of topic data before removal."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Export topics and relationships to backup file
            backup_query = f"""
            CALL apoc.export.cypher.query(
                "MATCH (t:Topic) OPTIONAL MATCH (e:Episode)-[r:HAS_TOPIC]->(t) RETURN *",
                "backups/topic_backup_{timestamp}.cypher",
                {{format: 'cypher-shell', cypherFormat: 'create'}}
            )
            """
            
            self.graph_storage.query(backup_query)
            self.cleanup_log.append(f"Created backup: topic_backup_{timestamp}.cypher")
            logger.info(f"Created backup: topic_backup_{timestamp}.cypher")
            
        except Exception as e:
            logger.warning(f"Backup creation failed (proceeding anyway): {e}")
            self.cleanup_log.append(f"Backup failed: {e}")
    
    def _remove_topic_relationships(self) -> int:
        """Remove all HAS_TOPIC relationships."""
        query = """
        MATCH ()-[r:HAS_TOPIC]->()
        WITH count(r) as total
        MATCH ()-[r:HAS_TOPIC]->()
        DELETE r
        RETURN total
        """
        
        result = self.graph_storage.query(query)
        count = result[0]['total'] if result else 0
        self.cleanup_log.append(f"Removed {count} HAS_TOPIC relationships")
        return count
    
    def _remove_topic_nodes(self) -> int:
        """Remove all Topic nodes."""
        query = """
        MATCH (t:Topic)
        WITH count(t) as total
        MATCH (t:Topic)
        DELETE t
        RETURN total
        """
        
        result = self.graph_storage.query(query)
        count = result[0]['total'] if result else 0
        self.cleanup_log.append(f"Removed {count} Topic nodes")
        return count
    
    def _drop_topic_constraints(self):
        """Drop any topic-related constraints."""
        try:
            self.graph_storage.query("DROP CONSTRAINT topic_name_unique IF EXISTS")
            self.cleanup_log.append("Dropped topic constraints")
            logger.info("Dropped topic constraints")
        except Exception as e:
            logger.info(f"No topic constraints to drop: {e}")
            self.cleanup_log.append("No topic constraints found")
    
    def _validate_removal(self) -> Dict[str, bool]:
        """Validate that all topics have been removed."""
        validations = {
            'no_topic_nodes': self._count_topics() == 0,
            'no_topic_relationships': self._count_topic_relationships() == 0
        }
        
        all_passed = all(validations.values())
        
        if all_passed:
            self.cleanup_log.append("✓ Topic system completely removed")
            logger.info("✓ Topic system completely removed")
        else:
            failed = [k for k, v in validations.items() if not v]
            self.cleanup_log.append(f"✗ Cleanup incomplete: {failed}")
            logger.error(f"✗ Cleanup incomplete: {failed}")
        
        return {
            'passed': all_passed,
            'validations': validations
        }


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Remove Topic system from Neo4j database')
    parser.add_argument('--podcast-name', required=True, help='Name of the podcast')
    parser.add_argument('--neo4j-uri', required=True, help='Neo4j URI (e.g., neo4j://localhost:7687)')
    parser.add_argument('--username', default='neo4j', help='Neo4j username')
    parser.add_argument('--password', default='password', help='Neo4j password')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be removed without making changes')
    
    args = parser.parse_args()
    
    logger.info(f"Starting topic cleanup for podcast: {args.podcast_name}")
    logger.info(f"Neo4j URI: {args.neo4j_uri}")
    
    try:
        cleaner = TopicSystemCleaner(
            neo4j_uri=args.neo4j_uri,
            username=args.username,
            password=args.password
        )
        
        results = cleaner.cleanup_topic_system(dry_run=args.dry_run)
        
        # Print results
        logger.info("=== CLEANUP RESULTS ===")
        for key, value in results.items():
            logger.info(f"{key}: {value}")
        
        # Print cleanup log
        logger.info("=== CLEANUP LOG ===")
        for log_entry in results.get('log', []):
            logger.info(log_entry)
        
        if not args.dry_run and results.get('validation', {}).get('passed', False):
            logger.info("✓ Topic system successfully removed from database")
        elif args.dry_run:
            logger.info("DRY RUN completed - run without --dry-run to perform actual cleanup")
        else:
            logger.error("✗ Topic cleanup failed or incomplete")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()