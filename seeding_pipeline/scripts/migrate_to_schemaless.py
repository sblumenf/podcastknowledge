#!/usr/bin/env python3
"""Migration script for transitioning from fixed to schemaless graph schema."""

import argparse
import logging
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import time

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.core.config import PipelineConfig
from src.providers.graph.neo4j import Neo4jProvider
from src.providers.graph.schemaless_neo4j import SchemalessNeo4jProvider
from src.migration.query_translator import QueryTranslator
from src.migration.result_standardizer import ResultStandardizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SchemalesssMigrator:
    """Handles migration from fixed to schemaless graph schema."""
    
    def __init__(self, config: Dict[str, Any], dry_run: bool = False):
        """
        Initialize migrator with configuration.
        
        Args:
            config: Neo4j configuration
            dry_run: If True, simulate migration without making changes
        """
        self.config = config
        self.dry_run = dry_run
        
        # Initialize providers
        self.fixed_provider = Neo4jProvider(config)
        self.schemaless_provider = SchemalessNeo4jProvider(config)
        
        # Migration utilities
        self.query_translator = QueryTranslator()
        self.result_standardizer = ResultStandardizer()
        
        # Migration state
        self.migration_stats = {
            'nodes_migrated': 0,
            'relationships_migrated': 0,
            'errors': [],
            'start_time': None,
            'end_time': None
        }
        
        # Checkpoint for resumable migration
        self.checkpoint_file = Path('migration_checkpoint.json')
        self.checkpoint_data = self._load_checkpoint()
    
    def _load_checkpoint(self) -> Dict[str, Any]:
        """Load migration checkpoint if exists."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")
        return {
            'last_node_id': None,
            'last_relationship_id': None,
            'migrated_nodes': set(),
            'migrated_relationships': set()
        }
    
    def _save_checkpoint(self):
        """Save migration checkpoint."""
        if not self.dry_run:
            # Convert sets to lists for JSON serialization
            checkpoint_data = self.checkpoint_data.copy()
            checkpoint_data['migrated_nodes'] = list(checkpoint_data['migrated_nodes'])
            checkpoint_data['migrated_relationships'] = list(checkpoint_data['migrated_relationships'])
            
            with open(self.checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)
    
    def export_fixed_schema_data(self, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Export current fixed schema graph data.
        
        Args:
            output_file: Optional file to save export
            
        Returns:
            Dictionary with exported data
        """
        logger.info("Exporting fixed schema data...")
        
        # Connect to fixed schema
        self.fixed_provider.connect()
        
        export_data = {
            'metadata': {
                'export_time': datetime.now().isoformat(),
                'schema_type': 'fixed'
            },
            'nodes': {},
            'relationships': []
        }
        
        try:
            # Export nodes by type
            node_types = ['Podcast', 'Episode', 'Segment', 'Entity', 'Quote', 'Insight', 'Topic', 'Speaker']
            
            for node_type in node_types:
                logger.info(f"Exporting {node_type} nodes...")
                
                query = f"MATCH (n:{node_type}) RETURN n"
                results = self.fixed_provider.query(query)
                
                export_data['nodes'][node_type] = []
                for result in results:
                    node_data = dict(result['n'])
                    export_data['nodes'][node_type].append(node_data)
                
                logger.info(f"Exported {len(export_data['nodes'][node_type])} {node_type} nodes")
            
            # Export relationships
            logger.info("Exporting relationships...")
            rel_query = """
                MATCH (a)-[r]->(b)
                RETURN id(a) as source_id, id(b) as target_id, 
                       type(r) as rel_type, properties(r) as properties,
                       labels(a)[0] as source_type, labels(b)[0] as target_type
            """
            rel_results = self.fixed_provider.query(rel_query)
            
            for result in rel_results:
                export_data['relationships'].append({
                    'source_id': result['source_id'],
                    'target_id': result['target_id'],
                    'type': result['rel_type'],
                    'properties': result['properties'] or {},
                    'source_type': result['source_type'],
                    'target_type': result['target_type']
                })
            
            logger.info(f"Exported {len(export_data['relationships'])} relationships")
            
            # Save to file if specified
            if output_file and not self.dry_run:
                with open(output_file, 'w') as f:
                    json.dump(export_data, f, indent=2)
                logger.info(f"Export saved to {output_file}")
            
            # Calculate statistics
            total_nodes = sum(len(nodes) for nodes in export_data['nodes'].values())
            export_data['metadata']['statistics'] = {
                'total_nodes': total_nodes,
                'total_relationships': len(export_data['relationships']),
                'node_types': {k: len(v) for k, v in export_data['nodes'].items() if v}
            }
            
            return export_data
            
        finally:
            self.fixed_provider.disconnect()
    
    def transform_to_schemaless(self, export_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Transform and import data to schemaless structure.
        
        Args:
            export_data: Previously exported data, or None to export fresh
        """
        if not export_data:
            export_data = self.export_fixed_schema_data()
        
        logger.info("Starting transformation to schemaless...")
        self.migration_stats['start_time'] = datetime.now()
        
        # Connect to schemaless provider
        self.schemaless_provider.connect()
        
        try:
            # Setup schemaless schema (indexes)
            if not self.dry_run:
                self.schemaless_provider.setup_schema()
            
            # Migrate nodes by type
            node_id_mapping = {}  # Old ID -> New ID mapping
            
            for node_type, nodes in export_data['nodes'].items():
                logger.info(f"Migrating {len(nodes)} {node_type} nodes...")
                
                for node in nodes:
                    # Skip if already migrated (checkpoint recovery)
                    old_id = node.get('id')
                    if old_id in self.checkpoint_data['migrated_nodes']:
                        continue
                    
                    try:
                        # Transform node for schemaless
                        if not self.dry_run:
                            new_id = self.schemaless_provider.create_node(node_type, node)
                            node_id_mapping[old_id] = new_id
                        else:
                            new_id = f"dry_run_{old_id}"
                            node_id_mapping[old_id] = new_id
                        
                        self.migration_stats['nodes_migrated'] += 1
                        self.checkpoint_data['migrated_nodes'].add(old_id)
                        
                        # Log progress
                        if self.migration_stats['nodes_migrated'] % 100 == 0:
                            logger.info(f"Migrated {self.migration_stats['nodes_migrated']} nodes...")
                            self._save_checkpoint()
                            
                    except Exception as e:
                        error_msg = f"Failed to migrate {node_type} node {old_id}: {e}"
                        logger.error(error_msg)
                        self.migration_stats['errors'].append(error_msg)
            
            # Migrate relationships
            logger.info(f"Migrating {len(export_data['relationships'])} relationships...")
            
            for rel in export_data['relationships']:
                # Create unique relationship ID for checkpoint
                rel_id = f"{rel['source_id']}-{rel['type']}-{rel['target_id']}"
                
                if rel_id in self.checkpoint_data['migrated_relationships']:
                    continue
                
                try:
                    # Map IDs
                    source_id = node_id_mapping.get(rel['source_id'], rel['source_id'])
                    target_id = node_id_mapping.get(rel['target_id'], rel['target_id'])
                    
                    if not self.dry_run:
                        self.schemaless_provider.create_relationship(
                            source_id,
                            target_id,
                            rel['type'],
                            rel['properties']
                        )
                    
                    self.migration_stats['relationships_migrated'] += 1
                    self.checkpoint_data['migrated_relationships'].add(rel_id)
                    
                    # Log progress
                    if self.migration_stats['relationships_migrated'] % 100 == 0:
                        logger.info(f"Migrated {self.migration_stats['relationships_migrated']} relationships...")
                        self._save_checkpoint()
                        
                except Exception as e:
                    error_msg = f"Failed to migrate relationship {rel_id}: {e}"
                    logger.error(error_msg)
                    self.migration_stats['errors'].append(error_msg)
            
            self.migration_stats['end_time'] = datetime.now()
            
            # Final checkpoint save
            self._save_checkpoint()
            
            # Log summary
            duration = (self.migration_stats['end_time'] - self.migration_stats['start_time']).total_seconds()
            logger.info(f"""
Migration completed:
- Nodes migrated: {self.migration_stats['nodes_migrated']}
- Relationships migrated: {self.migration_stats['relationships_migrated']}
- Errors: {len(self.migration_stats['errors'])}
- Duration: {duration:.2f} seconds
            """)
            
        finally:
            self.schemaless_provider.disconnect()
    
    def validate_migration(self, sample_size: int = 100) -> Dict[str, Any]:
        """
        Validate migration by comparing fixed and schemaless data.
        
        Args:
            sample_size: Number of nodes to sample for validation
            
        Returns:
            Validation report
        """
        logger.info("Validating migration...")
        
        validation_report = {
            'timestamp': datetime.now().isoformat(),
            'sample_size': sample_size,
            'validations': [],
            'issues': []
        }
        
        try:
            # Connect both providers
            self.fixed_provider.connect()
            self.schemaless_provider.connect()
            
            # Validate node counts
            logger.info("Validating node counts...")
            node_types = ['Podcast', 'Episode', 'Segment', 'Entity', 'Quote']
            
            for node_type in node_types:
                # Count in fixed schema
                fixed_count_query = f"MATCH (n:{node_type}) RETURN COUNT(n) as count"
                fixed_count = self.fixed_provider.query(fixed_count_query)[0]['count']
                
                # Count in schemaless
                schemaless_count_query = "MATCH (n:Node {_type: $type}) RETURN COUNT(n) as count"
                schemaless_count = self.schemaless_provider.query(
                    schemaless_count_query, 
                    {'type': node_type}
                )[0]['count']
                
                validation = {
                    'type': 'node_count',
                    'node_type': node_type,
                    'fixed_count': fixed_count,
                    'schemaless_count': schemaless_count,
                    'match': fixed_count == schemaless_count
                }
                
                validation_report['validations'].append(validation)
                
                if not validation['match']:
                    issue = f"Node count mismatch for {node_type}: fixed={fixed_count}, schemaless={schemaless_count}"
                    validation_report['issues'].append(issue)
                    logger.warning(issue)
            
            # Validate sample nodes
            logger.info("Validating sample nodes...")
            
            # Sample entities
            sample_query = f"MATCH (n:Entity) RETURN n LIMIT {sample_size}"
            sample_nodes = self.fixed_provider.query(sample_query)
            
            for node_data in sample_nodes:
                node = node_data['n']
                node_id = node.get('id')
                
                # Fetch from schemaless
                schemaless_query = "MATCH (n:Node {id: $id}) RETURN n"
                schemaless_results = self.schemaless_provider.query(
                    schemaless_query,
                    {'id': node_id}
                )
                
                if not schemaless_results:
                    issue = f"Node {node_id} not found in schemaless graph"
                    validation_report['issues'].append(issue)
                    continue
                
                schemaless_node = schemaless_results[0]['n']
                
                # Compare properties
                for prop in ['name', 'description', 'confidence']:
                    if prop in node:
                        fixed_value = node[prop]
                        schemaless_value = schemaless_node.get(prop)
                        
                        if fixed_value != schemaless_value:
                            # Check if property was mapped
                            mapped_prop = self.result_standardizer.property_mappings.get(prop, prop)
                            schemaless_value = schemaless_node.get(mapped_prop, schemaless_value)
                        
                        if fixed_value != schemaless_value:
                            issue = f"Property mismatch for node {node_id}.{prop}: fixed={fixed_value}, schemaless={schemaless_value}"
                            validation_report['issues'].append(issue)
            
            # Calculate validation score
            total_validations = len(validation_report['validations']) + sample_size
            issues_count = len(validation_report['issues'])
            validation_report['score'] = (total_validations - issues_count) / total_validations * 100
            
            logger.info(f"Validation score: {validation_report['score']:.2f}%")
            
            return validation_report
            
        finally:
            self.fixed_provider.disconnect()
            self.schemaless_provider.disconnect()
    
    def rollback_migration(self) -> None:
        """
        Rollback migration by removing schemaless data.
        
        WARNING: This will delete all data in the schemaless graph!
        """
        if self.dry_run:
            logger.info("DRY RUN: Would delete all schemaless data")
            return
        
        logger.warning("Rolling back migration - this will delete all schemaless data!")
        
        response = input("Are you sure you want to rollback? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Rollback cancelled")
            return
        
        try:
            self.schemaless_provider.connect()
            
            # Delete all nodes (and relationships)
            delete_query = "MATCH (n:Node) DETACH DELETE n"
            self.schemaless_provider.query(delete_query)
            
            # Remove checkpoint
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
            
            logger.info("Rollback completed - schemaless data deleted")
            
        finally:
            self.schemaless_provider.disconnect()
    
    def get_migration_progress(self) -> Dict[str, Any]:
        """Get current migration progress."""
        return {
            'stats': self.migration_stats,
            'checkpoint': {
                'nodes_migrated': len(self.checkpoint_data['migrated_nodes']),
                'relationships_migrated': len(self.checkpoint_data['migrated_relationships']),
                'last_node_id': self.checkpoint_data['last_node_id'],
                'last_relationship_id': self.checkpoint_data['last_relationship_id']
            }
        }


def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(description='Migrate from fixed to schemaless Neo4j schema')
    
    parser.add_argument('action', choices=['export', 'migrate', 'validate', 'rollback', 'status'],
                        help='Migration action to perform')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--neo4j-uri', type=str, default='bolt://localhost:7687',
                        help='Neo4j connection URI')
    parser.add_argument('--neo4j-user', type=str, default='neo4j',
                        help='Neo4j username')
    parser.add_argument('--neo4j-password', type=str, required=True,
                        help='Neo4j password')
    parser.add_argument('--database', type=str, default='neo4j',
                        help='Neo4j database name')
    parser.add_argument('--export-file', type=str, default='graph_export.json',
                        help='Export file path')
    parser.add_argument('--dry-run', action='store_true',
                        help='Simulate migration without making changes')
    parser.add_argument('--sample-size', type=int, default=100,
                        help='Sample size for validation')
    
    args = parser.parse_args()
    
    # Build configuration
    config = {
        'uri': args.neo4j_uri,
        'username': args.neo4j_user,
        'password': args.neo4j_password,
        'database': args.database
    }
    
    # Create migrator
    migrator = SchemalesssMigrator(config, dry_run=args.dry_run)
    
    # Execute action
    if args.action == 'export':
        export_data = migrator.export_fixed_schema_data(args.export_file)
        print(f"Export completed: {export_data['metadata']['statistics']}")
        
    elif args.action == 'migrate':
        # Load export if exists
        export_data = None
        if Path(args.export_file).exists():
            with open(args.export_file, 'r') as f:
                export_data = json.load(f)
        
        migrator.transform_to_schemaless(export_data)
        
    elif args.action == 'validate':
        report = migrator.validate_migration(sample_size=args.sample_size)
        print(f"Validation score: {report['score']:.2f}%")
        if report['issues']:
            print(f"Found {len(report['issues'])} issues:")
            for issue in report['issues'][:10]:  # Show first 10
                print(f"  - {issue}")
                
    elif args.action == 'rollback':
        migrator.rollback_migration()
        
    elif args.action == 'status':
        progress = migrator.get_migration_progress()
        print(json.dumps(progress, indent=2))


if __name__ == '__main__':
    main()