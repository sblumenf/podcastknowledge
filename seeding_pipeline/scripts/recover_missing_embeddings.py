#!/usr/bin/env python3
"""
Recover missing embeddings for MeaningfulUnits.

This script finds MeaningfulUnits without embeddings and generates them
using the embeddings service. Failed embeddings during pipeline processing
can be recovered using this tool.

Usage:
    python scripts/recover_missing_embeddings.py [options]
    
Options:
    --dry-run       Show what would be processed without making changes
    --batch-size N  Process N units at a time (default: 100)
    --help          Show this help message
"""

import sys
import os
import argparse
import logging
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.graph_storage import GraphStorageService
from src.services.embeddings import create_embeddings_service
from src.core.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EmbeddingRecovery:
    """Handles recovery of missing embeddings."""
    
    def __init__(self, graph_storage: GraphStorageService, embeddings_service: Any):
        """
        Initialize recovery service.
        
        Args:
            graph_storage: Neo4j storage service
            embeddings_service: Service for generating embeddings
        """
        self.graph_storage = graph_storage
        self.embeddings_service = embeddings_service
        self.success_count = 0
        self.failure_count = 0
        self.failures = []
        
    def find_units_without_embeddings(self) -> List[Dict[str, Any]]:
        """
        Query database for MeaningfulUnits without embeddings.
        
        Returns:
            List of units with id and text fields
        """
        query = """
        MATCH (m:MeaningfulUnit)
        WHERE m.embedding IS NULL
        RETURN m.id as id, m.text as text
        """
        
        try:
            with self.graph_storage.session() as session:
                result = session.run(query)
                units = []
                for record in result:
                    units.append({
                        'id': record['id'],
                        'text': record['text']
                    })
                return units
        except Exception as e:
            logger.error(f"Failed to query units without embeddings: {e}")
            raise
            
    def process_batch(self, units: List[Dict[str, Any]]) -> None:
        """
        Generate embeddings for a batch of units.
        
        Args:
            units: List of units with id and text
        """
        # Extract texts for batch processing
        texts = [unit['text'] for unit in units]
        unit_ids = [unit['id'] for unit in units]
        
        try:
            # Generate embeddings in batch
            embeddings = self.embeddings_service.generate_embeddings(texts)
            
            # Prepare updates
            updates = []
            for i, (unit_id, embedding) in enumerate(zip(unit_ids, embeddings)):
                if embedding:
                    updates.append({
                        'id': unit_id,
                        'embedding': embedding
                    })
                    self.success_count += 1
                else:
                    logger.warning(f"Failed to generate embedding for unit {unit_id}")
                    self.failure_count += 1
                    self.failures.append({
                        'unit_id': unit_id,
                        'error': 'Embedding generation returned None',
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Update database with successful embeddings
            if updates:
                self._update_embeddings(updates)
                
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            # Track all units in batch as failed
            for unit_id in unit_ids:
                self.failure_count += 1
                self.failures.append({
                    'unit_id': unit_id,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
                
    def _update_embeddings(self, updates: List[Dict[str, Any]]) -> None:
        """
        Update Neo4j with generated embeddings.
        
        Args:
            updates: List of dicts with id and embedding
        """
        query = """
        UNWIND $updates as update
        MATCH (m:MeaningfulUnit {id: update.id})
        SET m.embedding = update.embedding
        """
        
        try:
            with self.graph_storage.session() as session:
                session.run(query, updates=updates)
                logger.info(f"Updated {len(updates)} embeddings in database")
        except Exception as e:
            logger.error(f"Failed to update embeddings: {e}")
            # Track update failures
            for update in updates:
                self.failure_count += 1
                self.failures.append({
                    'unit_id': update['id'],
                    'error': f'Database update failed: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                })
                
    def write_failure_log(self) -> None:
        """Write any failures to log file."""
        if not self.failures:
            return
            
        # Create logs directory
        logs_dir = Path("logs/embedding_recovery")
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recovery_failures_{timestamp}.json"
        filepath = logs_dir / filename
        
        # Write failures
        failure_data = {
            'recovery_run': timestamp,
            'failures': self.failures,
            'total_failures': len(self.failures),
            'written_at': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(failure_data, f, indent=2)
            
        logger.info(f"Wrote {len(self.failures)} failures to {filepath}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Recover missing embeddings for MeaningfulUnits',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without making changes'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of units to process at once (default: 100)'
    )
    
    args = parser.parse_args()
    
    # Initialize services
    config = Config()
    graph_storage = GraphStorageService(
        uri=config.neo4j_uri,
        user=config.neo4j_user,
        password=config.neo4j_password
    )
    
    # Initialize embeddings service
    embeddings_service = create_embeddings_service()
    
    # Create recovery instance
    recovery = EmbeddingRecovery(graph_storage, embeddings_service)
    
    try:
        # Find units without embeddings
        logger.info("Querying for MeaningfulUnits without embeddings...")
        units = recovery.find_units_without_embeddings()
        
        if not units:
            logger.info("No units found without embeddings. All units have embeddings!")
            return
            
        logger.info(f"Found {len(units)} units without embeddings")
        
        if args.dry_run:
            logger.info("DRY RUN - Would process the following units:")
            for i, unit in enumerate(units[:10]):  # Show first 10
                logger.info(f"  {i+1}. {unit['id']}")
            if len(units) > 10:
                logger.info(f"  ... and {len(units) - 10} more")
            return
            
        # Process in batches
        total_batches = (len(units) + args.batch_size - 1) // args.batch_size
        logger.info(f"Processing {len(units)} units in {total_batches} batches")
        
        for i in range(0, len(units), args.batch_size):
            batch = units[i:i + args.batch_size]
            batch_num = (i // args.batch_size) + 1
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} units)")
            recovery.process_batch(batch)
            
            # Rate limiting between batches
            if i + args.batch_size < len(units):
                time.sleep(0.1)  # 100ms delay between batches
                
        # Write failure log if any
        recovery.write_failure_log()
        
        # Final summary
        logger.info("Recovery complete!")
        logger.info(f"  Successfully recovered: {recovery.success_count}")
        logger.info(f"  Failed: {recovery.failure_count}")
        logger.info(f"  Success rate: {recovery.success_count / len(units) * 100:.1f}%")
        
    except Exception as e:
        logger.error(f"Recovery script failed: {e}")
        raise
    finally:
        # Clean up
        graph_storage.close()


if __name__ == "__main__":
    main()