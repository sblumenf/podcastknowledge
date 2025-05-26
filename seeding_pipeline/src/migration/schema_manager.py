"""
Schema evolution manager for Neo4j database.

This module handles schema versioning, migrations, and rollbacks
for the podcast knowledge graph database.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from enum import Enum

from ..core.exceptions import PodcastProcessingError, DatabaseConnectionError
from ..providers.graph.base import GraphProvider

logger = logging.getLogger(__name__)


class MigrationDirection(Enum):
    """Direction of schema migration."""
    UP = "up"
    DOWN = "down"


@dataclass
class SchemaVersion:
    """Represents a schema version."""
    version: str
    description: str
    applied_at: Optional[datetime] = None
    migrations: Dict[str, str] = None  # up/down migration queries
    
    def __post_init__(self):
        if self.migrations is None:
            self.migrations = {"up": "", "down": ""}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "version": self.version,
            "description": self.description,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
        }


class SchemaManager:
    """
    Manages database schema evolution and migrations.
    
    This class handles:
    - Schema version tracking
    - Migration execution
    - Rollback support
    - Schema validation
    """
    
    # Define schema migrations
    MIGRATIONS = [
        SchemaVersion(
            version="0.0.0",
            description="Initial schema",
            migrations={
                "up": """
                // Initial schema - no changes needed
                RETURN 'Initial schema' as status
                """,
                "down": """
                // Cannot rollback from initial schema
                RETURN 'Cannot rollback initial schema' as status
                """
            }
        ),
        SchemaVersion(
            version="1.0.0",
            description="Add schema versioning and enhanced indexes",
            migrations={
                "up": """
                // Create schema version tracking
                CREATE CONSTRAINT IF NOT EXISTS FOR (v:SchemaVersion) REQUIRE v.version IS UNIQUE;
                
                // Add version tracking node
                MERGE (v:SchemaVersion {version: '1.0.0'})
                SET v.applied_at = datetime(),
                    v.description = 'Add schema versioning and enhanced indexes';
                
                // Add schema_version to existing nodes
                MATCH (n)
                WHERE n:Podcast OR n:Episode OR n:Entity OR n:Insight OR n:Quote OR n:Topic OR n:Segment
                SET n.schema_version = '1.0.0';
                
                // Create additional indexes for performance
                CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.mention_count);
                CREATE INDEX IF NOT EXISTS FOR (e:Episode) ON (e.published_date);
                CREATE INDEX IF NOT EXISTS FOR (s:Segment) ON (s.episode_id);
                CREATE INDEX IF NOT EXISTS FOR (q:Quote) ON (q.segment_id);
                
                RETURN 'Schema updated to v1.0.0' as status
                """,
                "down": """
                // Remove version 1.0.0 changes
                MATCH (v:SchemaVersion {version: '1.0.0'})
                DELETE v;
                
                // Remove schema_version from nodes
                MATCH (n)
                WHERE n:Podcast OR n:Episode OR n:Entity OR n:Insight OR n:Quote OR n:Topic OR n:Segment
                REMOVE n.schema_version;
                
                // Drop additional indexes
                DROP INDEX IF EXISTS FOR (e:Entity) ON (e.mention_count);
                DROP INDEX IF EXISTS FOR (e:Episode) ON (e.published_date);
                DROP INDEX IF EXISTS FOR (s:Segment) ON (s.episode_id);
                DROP INDEX IF EXISTS FOR (q:Quote) ON (q.segment_id);
                
                RETURN 'Rolled back to v0.0.0' as status
                """
            }
        ),
        SchemaVersion(
            version="1.1.0",
            description="Add migration tracking and backup markers",
            migrations={
                "up": """
                // Create migration history tracking
                CREATE CONSTRAINT IF NOT EXISTS FOR (m:MigrationHistory) REQUIRE m.id IS UNIQUE;
                
                // Create backup marker constraint
                CREATE CONSTRAINT IF NOT EXISTS FOR (b:BackupMarker) REQUIRE b.id IS UNIQUE;
                
                // Update schema version
                MERGE (v:SchemaVersion {version: '1.1.0'})
                SET v.applied_at = datetime(),
                    v.description = 'Add migration tracking and backup markers';
                
                RETURN 'Schema updated to v1.1.0' as status
                """,
                "down": """
                // Remove migration tracking
                MATCH (m:MigrationHistory)
                DELETE m;
                
                // Remove backup markers
                MATCH (b:BackupMarker)
                DELETE b;
                
                // Drop constraints
                DROP CONSTRAINT IF EXISTS FOR (m:MigrationHistory) REQUIRE m.id IS UNIQUE;
                DROP CONSTRAINT IF EXISTS FOR (b:BackupMarker) REQUIRE b.id IS UNIQUE;
                
                // Remove version
                MATCH (v:SchemaVersion {version: '1.1.0'})
                DELETE v;
                
                RETURN 'Rolled back to v1.0.0' as status
                """
            }
        ),
    ]
    
    def __init__(self, graph_provider: GraphProvider):
        """
        Initialize schema manager.
        
        Args:
            graph_provider: Graph database provider
        """
        self.graph_provider = graph_provider
        
    def get_current_version(self) -> Optional[SchemaVersion]:
        """
        Get the current schema version from the database.
        
        Returns:
            Current schema version or None if not versioned
        """
        try:
            query = """
            MATCH (v:SchemaVersion)
            RETURN v.version as version, 
                   v.description as description,
                   v.applied_at as applied_at
            ORDER BY v.applied_at DESC
            LIMIT 1
            """
            
            results = self.graph_provider.execute_query(query)
            
            if not results:
                return SchemaVersion(
                    version="0.0.0",
                    description="Initial schema",
                    applied_at=None
                )
            
            result = results[0]
            return SchemaVersion(
                version=result["version"],
                description=result["description"],
                applied_at=datetime.fromisoformat(result["applied_at"]) if result["applied_at"] else None
            )
            
        except Exception as e:
            logger.error(f"Failed to get current schema version: {e}")
            return None
    
    def get_available_migrations(self, current_version: str) -> List[SchemaVersion]:
        """
        Get list of migrations that can be applied.
        
        Args:
            current_version: Current schema version
            
        Returns:
            List of applicable migrations
        """
        available = []
        found_current = False
        
        for migration in self.MIGRATIONS:
            if migration.version == current_version:
                found_current = True
                continue
            if found_current:
                available.append(migration)
        
        return available
    
    def migrate_to(self, target_version: str) -> bool:
        """
        Migrate to a specific schema version.
        
        Args:
            target_version: Target version to migrate to
            
        Returns:
            True if successful, False otherwise
        """
        current = self.get_current_version()
        if not current:
            raise DatabaseConnectionError("Cannot determine current schema version")
        
        logger.info(f"Current schema version: {current.version}")
        
        if current.version == target_version:
            logger.info("Already at target version")
            return True
        
        # Determine migration path
        migrations = self._get_migration_path(current.version, target_version)
        
        if not migrations:
            logger.error(f"No migration path from {current.version} to {target_version}")
            return False
        
        # Execute migrations
        for migration, direction in migrations:
            logger.info(f"Applying migration {migration.version} ({direction.value})")
            
            if not self._apply_migration(migration, direction):
                logger.error(f"Migration {migration.version} failed")
                return False
            
            # Record migration in history
            self._record_migration(migration, direction)
        
        logger.info(f"Successfully migrated to version {target_version}")
        return True
    
    def _get_migration_path(
        self, 
        from_version: str, 
        to_version: str
    ) -> List[tuple[SchemaVersion, MigrationDirection]]:
        """
        Determine the migration path between versions.
        
        Args:
            from_version: Starting version
            to_version: Target version
            
        Returns:
            List of (migration, direction) tuples
        """
        from_idx = -1
        to_idx = -1
        
        for i, migration in enumerate(self.MIGRATIONS):
            if migration.version == from_version:
                from_idx = i
            if migration.version == to_version:
                to_idx = i
        
        if from_idx == -1 or to_idx == -1:
            return []
        
        path = []
        
        if from_idx < to_idx:
            # Moving forward
            for i in range(from_idx + 1, to_idx + 1):
                path.append((self.MIGRATIONS[i], MigrationDirection.UP))
        else:
            # Moving backward
            for i in range(from_idx, to_idx, -1):
                path.append((self.MIGRATIONS[i], MigrationDirection.DOWN))
        
        return path
    
    def _apply_migration(
        self, 
        migration: SchemaVersion, 
        direction: MigrationDirection
    ) -> bool:
        """
        Apply a single migration.
        
        Args:
            migration: Migration to apply
            direction: Direction (up or down)
            
        Returns:
            True if successful
        """
        try:
            query = migration.migrations[direction.value]
            
            # Create backup marker before migration
            self._create_backup_marker(migration.version, direction)
            
            # Execute migration
            result = self.graph_provider.execute_write(query)
            
            logger.info(f"Migration result: {result}")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    def _create_backup_marker(self, version: str, direction: MigrationDirection):
        """Create a backup marker before migration."""
        try:
            query = """
            CREATE (b:BackupMarker {
                id: randomUUID(),
                version: $version,
                direction: $direction,
                timestamp: datetime(),
                node_count: SIZE([(n) | n]),
                relationship_count: SIZE([(r) | r])
            })
            """
            
            self.graph_provider.execute_write(
                query,
                {
                    "version": version,
                    "direction": direction.value
                }
            )
            
        except Exception as e:
            logger.warning(f"Failed to create backup marker: {e}")
    
    def _record_migration(self, migration: SchemaVersion, direction: MigrationDirection):
        """Record migration in history."""
        try:
            query = """
            CREATE (m:MigrationHistory {
                id: randomUUID(),
                version: $version,
                direction: $direction,
                description: $description,
                applied_at: datetime()
            })
            """
            
            self.graph_provider.execute_write(
                query,
                {
                    "version": migration.version,
                    "direction": direction.value,
                    "description": migration.description
                }
            )
            
        except Exception as e:
            logger.warning(f"Failed to record migration history: {e}")
    
    def validate_schema(self) -> Dict[str, Any]:
        """
        Validate the current schema state.
        
        Returns:
            Validation results
        """
        results = {
            "valid": True,
            "version": None,
            "errors": [],
            "warnings": [],
            "node_types": {},
            "relationship_types": {},
            "constraints": [],
            "indexes": []
        }
        
        try:
            # Get current version
            current = self.get_current_version()
            results["version"] = current.version if current else "unknown"
            
            # Check node types and counts
            node_query = """
            MATCH (n)
            RETURN labels(n)[0] as NodeType, count(n) as Count
            ORDER BY Count DESC
            """
            
            node_results = self.graph_provider.execute_query(node_query)
            for row in node_results:
                results["node_types"][row["NodeType"]] = row["Count"]
            
            # Check relationship types
            rel_query = """
            MATCH ()-[r]->()
            RETURN type(r) as RelType, count(r) as Count
            ORDER BY Count DESC
            """
            
            rel_results = self.graph_provider.execute_query(rel_query)
            for row in rel_results:
                results["relationship_types"][row["RelType"]] = row["Count"]
            
            # Check constraints
            constraint_query = "SHOW CONSTRAINTS"
            constraints = self.graph_provider.execute_query(constraint_query)
            results["constraints"] = constraints
            
            # Check indexes
            index_query = "SHOW INDEXES"
            indexes = self.graph_provider.execute_query(index_query)
            results["indexes"] = indexes
            
            # Validate data integrity
            self._validate_data_integrity(results)
            
        except Exception as e:
            results["valid"] = False
            results["errors"].append(f"Schema validation failed: {str(e)}")
        
        return results
    
    def _validate_data_integrity(self, results: Dict[str, Any]):
        """Validate data integrity rules."""
        # Check for orphaned episodes
        orphan_query = """
        MATCH (e:Episode)
        WHERE NOT (e)<-[:HAS_EPISODE]-(:Podcast)
        RETURN count(e) as count
        """
        
        orphans = self.graph_provider.execute_query(orphan_query)
        if orphans and orphans[0]["count"] > 0:
            results["warnings"].append(
                f"Found {orphans[0]['count']} orphaned episodes"
            )
        
        # Check for segments without episodes
        segment_query = """
        MATCH (s:Segment)
        WHERE NOT (s)<-[:HAS_SEGMENT]-(:Episode)
        RETURN count(s) as count
        """
        
        segments = self.graph_provider.execute_query(segment_query)
        if segments and segments[0]["count"] > 0:
            results["warnings"].append(
                f"Found {segments[0]['count']} segments without episodes"
            )
        
        # Check for duplicate IDs
        dup_query = """
        MATCH (n)
        WHERE n.id IS NOT NULL
        WITH n.id as id, labels(n)[0] as label, count(n) as count
        WHERE count > 1
        RETURN label, id, count
        ORDER BY count DESC
        LIMIT 10
        """
        
        duplicates = self.graph_provider.execute_query(dup_query)
        if duplicates:
            results["errors"].append(
                f"Found {len(duplicates)} duplicate IDs"
            )
            results["valid"] = False