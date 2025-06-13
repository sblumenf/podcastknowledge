"""
Neo4j-based episode tracking system.

This module provides a simple tracking system using Neo4j as the single source of truth.
Episodes with processing_status = 'complete' are considered fully processed.
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class EpisodeTracker:
    """
    Simple Neo4j-based episode tracking.
    
    Uses Neo4j as the single source of truth for tracking processed episodes.
    No separate tracking files or synchronization needed.
    """
    
    def __init__(self, graph_storage):
        """
        Initialize episode tracker with graph storage dependency.
        
        Args:
            graph_storage: Neo4j graph storage instance for database access
        """
        self.storage = graph_storage
        logger.info("Initialized Neo4j-based episode tracker")
    
    def is_episode_processed(self, episode_id: str) -> bool:
        """
        Check if episode is fully processed in Neo4j.
        
        Args:
            episode_id: Unique episode identifier
            
        Returns:
            True if episode exists with processing_status = 'complete'
        """
        query = """
        MATCH (e:Episode {id: $episode_id})
        WHERE e.processing_status = 'complete'
        RETURN COUNT(e) > 0 as is_processed
        """
        try:
            result = self.storage.query(query, {"episode_id": episode_id})
            is_processed = result[0]['is_processed'] if result else False
            logger.debug(f"Episode {episode_id} processed: {is_processed}")
            return is_processed
        except Exception as e:
            logger.error(f"Error checking episode status: {e}")
            return False
    
    def mark_episode_complete(self, episode_id: str, file_hash: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Mark episode as complete in Neo4j.
        
        Args:
            episode_id: Unique episode identifier
            file_hash: MD5 hash of the VTT file
            metadata: Optional metadata about the episode (e.g., segment_count, entity_count)
        """
        # Build SET clause for metadata
        metadata = metadata or {}
        set_clauses = [
            "e.processing_status = 'complete'",
            "e.processed_at = datetime()",
            "e.file_hash = $file_hash"
        ]
        
        # Add optional metadata fields
        params = {
            "episode_id": episode_id,
            "file_hash": file_hash
        }
        
        if 'segment_count' in metadata:
            set_clauses.append("e.segment_count = $segment_count")
            params['segment_count'] = metadata['segment_count']
            
        if 'entity_count' in metadata:
            set_clauses.append("e.entity_count = $entity_count")
            params['entity_count'] = metadata['entity_count']
            
        if 'vtt_path' in metadata:
            set_clauses.append("e.vtt_path = $vtt_path")
            params['vtt_path'] = metadata['vtt_path']
            
        if 'podcast_id' in metadata:
            set_clauses.append("e.podcast_id = $podcast_id")
            params['podcast_id'] = metadata['podcast_id']
        
        set_clause = ", ".join(set_clauses)
        
        query = f"""
        MATCH (e:Episode {{id: $episode_id}})
        SET {set_clause}
        RETURN e.id as episode_id
        """
        
        try:
            result = self.storage.query(query, params)
            if result:
                logger.info(f"Marked episode {episode_id} as complete")
            else:
                # Episode doesn't exist, create it
                create_query = f"""
                CREATE (e:Episode {{id: $episode_id}})
                SET {set_clause}
                RETURN e.id as episode_id
                """
                self.storage.query(create_query, params)
                logger.info(f"Created and marked episode {episode_id} as complete")
        except Exception as e:
            logger.error(f"Error marking episode complete: {e}")
            raise
    
    def get_processed_episodes(self, podcast_id: str) -> List[Dict[str, Any]]:
        """
        Get all fully processed episodes for a podcast from Neo4j.
        
        Args:
            podcast_id: Podcast identifier
            
        Returns:
            List of processed episode information
        """
        query = """
        MATCH (e:Episode {podcast_id: $podcast_id})
        WHERE e.processing_status = 'complete'
        RETURN e.id as episode_id, 
               e.title as title,
               e.file_hash as file_hash,
               e.processed_at as processed_at,
               e.segment_count as segment_count,
               e.entity_count as entity_count
        ORDER BY e.processed_at DESC
        """
        try:
            result = self.storage.query(query, {"podcast_id": podcast_id})
            logger.info(f"Found {len(result)} processed episodes for podcast {podcast_id}")
            return result
        except Exception as e:
            logger.error(f"Error getting processed episodes: {e}")
            return []
    
    def get_pending_episodes(self, podcast_id: str, vtt_files: List[str]) -> List[str]:
        """
        Get list of VTT files that haven't been processed yet.
        
        Args:
            podcast_id: Podcast identifier
            vtt_files: List of VTT file paths to check
            
        Returns:
            List of VTT files that need processing
        """
        pending = []
        
        for vtt_file in vtt_files:
            # Generate episode ID from file
            episode_id = generate_episode_id(vtt_file, podcast_id)
            
            # Check if already processed
            if not self.is_episode_processed(episode_id):
                pending.append(vtt_file)
        
        logger.info(f"Found {len(pending)} pending episodes out of {len(vtt_files)} total")
        return pending
    
    def get_all_episodes_status(self, podcast_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get status summary of all episodes.
        
        Args:
            podcast_id: Optional podcast ID to filter by
            
        Returns:
            Dictionary with status counts and details
        """
        # Base query
        base_match = "MATCH (e:Episode)"
        if podcast_id:
            base_match += " {podcast_id: $podcast_id}"
        
        # Count queries
        total_query = f"{base_match} RETURN COUNT(e) as total"
        complete_query = f"{base_match} WHERE e.processing_status = 'complete' RETURN COUNT(e) as complete"
        failed_query = f"{base_match} WHERE e.processing_status = 'failed' RETURN COUNT(e) as failed"
        
        params = {"podcast_id": podcast_id} if podcast_id else {}
        
        try:
            total = self.storage.query(total_query, params)[0]['total']
            complete = self.storage.query(complete_query, params)[0]['complete']
            failed = self.storage.query(failed_query, params)[0]['failed']
            
            return {
                'total_episodes': total,
                'completed': complete,
                'failed': failed,
                'pending': total - complete - failed,
                'completion_rate': (complete / total * 100) if total > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting episode status: {e}")
            return {
                'total_episodes': 0,
                'completed': 0,
                'failed': 0,
                'pending': 0,
                'completion_rate': 0
            }
    
    def mark_episode_failed(self, episode_id: str, error_message: str):
        """
        Mark an episode as failed in Neo4j.
        
        Args:
            episode_id: Episode identifier
            error_message: Error description
        """
        query = """
        MATCH (e:Episode {id: $episode_id})
        SET e.processing_status = 'failed',
            e.failed_at = datetime(),
            e.error_message = $error_message
        RETURN e.id as episode_id
        """
        
        try:
            result = self.storage.query(query, {
                "episode_id": episode_id,
                "error_message": error_message
            })
            if not result:
                # Create if doesn't exist
                create_query = """
                CREATE (e:Episode {id: $episode_id})
                SET e.processing_status = 'failed',
                    e.failed_at = datetime(),
                    e.error_message = $error_message
                RETURN e.id as episode_id
                """
                self.storage.query(create_query, {
                    "episode_id": episode_id,
                    "error_message": error_message
                })
            logger.warning(f"Marked episode {episode_id} as failed: {error_message}")
        except Exception as e:
            logger.error(f"Error marking episode as failed: {e}")


# Note: generate_episode_id is now imported from shared module in __init__.py
# This ensures consistent episode ID generation across transcriber and seeding_pipeline


def calculate_file_hash(file_path: str) -> str:
    """
    Calculate MD5 hash of a file.
    
    Args:
        file_path: Path to file
        
    Returns:
        MD5 hash string
    """
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating file hash: {e}")
        return ""