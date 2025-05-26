"""
Migration validators for the podcast knowledge pipeline.

This module provides validation tools to ensure data integrity
before, during, and after migration.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple
import hashlib

from ..core.models import (
    Podcast, Episode, Segment, Entity, Insight, Quote, Topic,
    validate_podcast, validate_episode, validate_segment
)
from ..providers.graph.base import GraphProvider

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Represents a validation error."""
    node_type: str
    node_id: str
    field: str
    error: str
    severity: str = "error"  # error, warning
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_type": self.node_type,
            "node_id": self.node_id,
            "field": self.field,
            "error": self.error,
            "severity": self.severity
        }


@dataclass
class ValidationResult:
    """Result of validation check."""
    valid: bool = True
    total_checked: int = 0
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, error: ValidationError):
        """Add an error to the result."""
        if error.severity == "error":
            self.errors.append(error)
            self.valid = False
        else:
            self.warnings.append(error)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "total_checked": self.total_checked,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [e.to_dict() for e in self.errors[:100]],  # Limit for readability
            "warnings": [w.to_dict() for w in self.warnings[:100]],
            "statistics": self.statistics
        }


class MigrationValidator:
    """
    Validates data before and after migration.
    
    This class provides:
    - Pre-migration validation
    - Post-migration validation
    - Data integrity checks
    - Consistency validation
    """
    
    def __init__(self, graph_provider: GraphProvider):
        """
        Initialize migration validator.
        
        Args:
            graph_provider: Graph database provider
        """
        self.graph_provider = graph_provider
    
    def validate_pre_migration(self) -> ValidationResult:
        """
        Validate data before migration.
        
        Returns:
            Validation result
        """
        logger.info("Starting pre-migration validation")
        
        result = ValidationResult()
        
        # Validate schema readiness
        self._validate_schema_readiness(result)
        
        # Validate node data
        self._validate_all_nodes(result)
        
        # Validate relationships
        self._validate_relationships(result)
        
        # Validate data consistency
        self._validate_consistency(result)
        
        logger.info(f"Pre-migration validation complete. Valid: {result.valid}")
        
        return result
    
    def validate_post_migration(self) -> ValidationResult:
        """
        Validate data after migration.
        
        Returns:
            Validation result
        """
        logger.info("Starting post-migration validation")
        
        result = ValidationResult()
        
        # Validate migration metadata
        self._validate_migration_metadata(result)
        
        # Validate data integrity
        self._validate_data_integrity(result)
        
        # Compare with pre-migration state
        self._validate_migration_completeness(result)
        
        logger.info(f"Post-migration validation complete. Valid: {result.valid}")
        
        return result
    
    def validate_specific_nodes(
        self, 
        node_type: str, 
        node_ids: List[str]
    ) -> ValidationResult:
        """
        Validate specific nodes.
        
        Args:
            node_type: Type of nodes to validate
            node_ids: List of node IDs to validate
            
        Returns:
            Validation result
        """
        result = ValidationResult()
        
        for node_id in node_ids:
            self._validate_node(node_type, node_id, result)
        
        return result
    
    def _validate_schema_readiness(self, result: ValidationResult):
        """Validate that schema is ready for migration."""
        # Check for required constraints
        constraints = self._get_constraints()
        
        required_constraints = {
            "Podcast": "id",
            "Episode": "id",
            "Segment": "id",
            "Entity": "id",
            "Insight": "id",
            "Quote": "id",
            "Topic": "id"
        }
        
        # Simple check - would need to parse constraint details
        if len(constraints) < len(required_constraints):
            result.add_error(ValidationError(
                node_type="Schema",
                node_id="constraints",
                field="constraints",
                error="Missing required constraints",
                severity="error"
            ))
        
        # Check for required indexes
        indexes = self._get_indexes()
        if len(indexes) < 10:  # Expected minimum indexes
            result.add_error(ValidationError(
                node_type="Schema",
                node_id="indexes",
                field="indexes",
                error="Insufficient indexes for performance",
                severity="warning"
            ))
    
    def _validate_all_nodes(self, result: ValidationResult):
        """Validate all nodes in the database."""
        node_types = [
            "Podcast", "Episode", "Segment", "Entity",
            "Insight", "Quote", "Topic", "Speaker"
        ]
        
        for node_type in node_types:
            logger.info(f"Validating {node_type} nodes")
            self._validate_node_type(node_type, result)
    
    def _validate_node_type(self, node_type: str, result: ValidationResult):
        """Validate all nodes of a specific type."""
        # Count nodes
        count_query = f"MATCH (n:{node_type}) RETURN count(n) as count"
        count_result = self.graph_provider.execute_query(count_query)
        total_count = count_result[0]["count"] if count_result else 0
        
        result.statistics[f"{node_type}_count"] = total_count
        
        # Validate in batches
        batch_size = 1000
        skip = 0
        
        while skip < total_count:
            query = f"""
            MATCH (n:{node_type})
            RETURN n
            ORDER BY n.id
            SKIP $skip
            LIMIT $limit
            """
            
            batch = self.graph_provider.execute_query(
                query,
                {"skip": skip, "limit": batch_size}
            )
            
            for record in batch:
                node = record["n"]
                self._validate_node_data(node_type, node, result)
                result.total_checked += 1
            
            skip += batch_size
    
    def _validate_node_data(
        self, 
        node_type: str, 
        node: Dict[str, Any], 
        result: ValidationResult
    ):
        """Validate individual node data."""
        node_id = node.get("id", "unknown")
        
        # Required fields by node type
        required_fields = {
            "Podcast": ["id", "title", "description", "rss_url"],
            "Episode": ["id", "title", "description", "published_date"],
            "Segment": ["id", "text", "start_time", "end_time"],
            "Entity": ["id", "name", "type"],
            "Insight": ["id", "insight_type", "content"],
            "Quote": ["id", "text", "speaker"],
            "Topic": ["id", "name"],
            "Speaker": ["id", "name"]
        }
        
        # Check required fields
        if node_type in required_fields:
            for field in required_fields[node_type]:
                if field not in node or node[field] is None:
                    result.add_error(ValidationError(
                        node_type=node_type,
                        node_id=node_id,
                        field=field,
                        error=f"Missing required field: {field}"
                    ))
        
        # Type-specific validation
        if node_type == "Episode":
            self._validate_episode_data(node, result)
        elif node_type == "Segment":
            self._validate_segment_data(node, result)
        elif node_type == "Entity":
            self._validate_entity_data(node, result)
        elif node_type == "Quote":
            self._validate_quote_data(node, result)
    
    def _validate_episode_data(self, node: Dict[str, Any], result: ValidationResult):
        """Validate episode-specific data."""
        node_id = node.get("id", "unknown")
        
        # Validate date format
        published_date = node.get("published_date")
        if published_date:
            try:
                # Try parsing common date formats
                if not isinstance(published_date, str):
                    result.add_error(ValidationError(
                        node_type="Episode",
                        node_id=node_id,
                        field="published_date",
                        error="Date must be a string",
                        severity="error"
                    ))
            except:
                result.add_error(ValidationError(
                    node_type="Episode",
                    node_id=node_id,
                    field="published_date",
                    error="Invalid date format",
                    severity="warning"
                ))
        
        # Validate duration
        duration = node.get("duration")
        if duration is not None and (not isinstance(duration, (int, float)) or duration < 0):
            result.add_error(ValidationError(
                node_type="Episode",
                node_id=node_id,
                field="duration",
                error="Duration must be a positive number",
                severity="warning"
            ))
    
    def _validate_segment_data(self, node: Dict[str, Any], result: ValidationResult):
        """Validate segment-specific data."""
        node_id = node.get("id", "unknown")
        
        # Validate timestamps
        start_time = node.get("start_time", 0)
        end_time = node.get("end_time", 0)
        
        if not isinstance(start_time, (int, float)) or start_time < 0:
            result.add_error(ValidationError(
                node_type="Segment",
                node_id=node_id,
                field="start_time",
                error="Start time must be a non-negative number"
            ))
        
        if not isinstance(end_time, (int, float)) or end_time < 0:
            result.add_error(ValidationError(
                node_type="Segment",
                node_id=node_id,
                field="end_time",
                error="End time must be a non-negative number"
            ))
        
        if end_time <= start_time:
            result.add_error(ValidationError(
                node_type="Segment",
                node_id=node_id,
                field="timestamps",
                error="End time must be after start time"
            ))
        
        # Validate text
        text = node.get("text", "")
        if not text or len(text.strip()) == 0:
            result.add_error(ValidationError(
                node_type="Segment",
                node_id=node_id,
                field="text",
                error="Segment text cannot be empty"
            ))
        
        # Validate embedding if present
        embedding = node.get("embedding")
        if embedding is not None:
            if not isinstance(embedding, list):
                result.add_error(ValidationError(
                    node_type="Segment",
                    node_id=node_id,
                    field="embedding",
                    error="Embedding must be a list",
                    severity="warning"
                ))
            elif len(embedding) == 0:
                result.add_error(ValidationError(
                    node_type="Segment",
                    node_id=node_id,
                    field="embedding",
                    error="Embedding cannot be empty",
                    severity="warning"
                ))
    
    def _validate_entity_data(self, node: Dict[str, Any], result: ValidationResult):
        """Validate entity-specific data."""
        node_id = node.get("id", "unknown")
        
        # Validate entity type
        entity_type = node.get("type")
        valid_types = ["person", "organization", "product", "concept", 
                      "technology", "location", "event", "other"]
        
        if entity_type and entity_type.lower() not in valid_types:
            result.add_error(ValidationError(
                node_type="Entity",
                node_id=node_id,
                field="type",
                error=f"Invalid entity type: {entity_type}",
                severity="warning"
            ))
        
        # Validate scores
        bridge_score = node.get("bridge_score")
        if bridge_score is not None:
            if not isinstance(bridge_score, (int, float)) or bridge_score < 0 or bridge_score > 1:
                result.add_error(ValidationError(
                    node_type="Entity",
                    node_id=node_id,
                    field="bridge_score",
                    error="Bridge score must be between 0 and 1",
                    severity="warning"
                ))
    
    def _validate_quote_data(self, node: Dict[str, Any], result: ValidationResult):
        """Validate quote-specific data."""
        node_id = node.get("id", "unknown")
        
        # Validate quote type
        quote_type = node.get("quote_type")
        valid_types = ["memorable", "controversial", "humorous", 
                      "insightful", "technical", "general"]
        
        if quote_type and quote_type.lower() not in valid_types:
            result.add_error(ValidationError(
                node_type="Quote",
                node_id=node_id,
                field="quote_type",
                error=f"Invalid quote type: {quote_type}",
                severity="warning"
            ))
        
        # Validate text length
        text = node.get("text", "")
        if len(text) < 10:
            result.add_error(ValidationError(
                node_type="Quote",
                node_id=node_id,
                field="text",
                error="Quote text too short",
                severity="warning"
            ))
    
    def _validate_relationships(self, result: ValidationResult):
        """Validate relationships between nodes."""
        # Check for required relationships
        relationship_checks = [
            {
                "name": "Episodes without podcasts",
                "query": """
                MATCH (e:Episode)
                WHERE NOT (e)<-[:HAS_EPISODE]-(:Podcast)
                RETURN count(e) as count, collect(e.id)[..10] as examples
                """
            },
            {
                "name": "Segments without episodes",
                "query": """
                MATCH (s:Segment)
                WHERE NOT (s)<-[:HAS_SEGMENT]-(:Episode)
                RETURN count(s) as count, collect(s.id)[..10] as examples
                """
            },
            {
                "name": "Quotes without segments",
                "query": """
                MATCH (q:Quote)
                WHERE NOT (q)-[:EXTRACTED_FROM]->(:Segment)
                RETURN count(q) as count, collect(q.id)[..10] as examples
                """
            }
        ]
        
        for check in relationship_checks:
            result_data = self.graph_provider.execute_query(check["query"])
            if result_data and result_data[0]["count"] > 0:
                count = result_data[0]["count"]
                examples = result_data[0].get("examples", [])
                
                result.add_error(ValidationError(
                    node_type="Relationship",
                    node_id=check["name"],
                    field="relationship",
                    error=f"{check['name']}: {count} found",
                    severity="error" if count > 10 else "warning"
                ))
                
                result.statistics[check["name"]] = {
                    "count": count,
                    "examples": examples
                }
    
    def _validate_consistency(self, result: ValidationResult):
        """Validate data consistency."""
        # Check for duplicate IDs within node types
        node_types = ["Podcast", "Episode", "Segment", "Entity", "Insight", "Quote", "Topic"]
        
        for node_type in node_types:
            dup_query = f"""
            MATCH (n:{node_type})
            WHERE n.id IS NOT NULL
            WITH n.id as id, count(n) as count
            WHERE count > 1
            RETURN id, count
            ORDER BY count DESC
            LIMIT 10
            """
            
            duplicates = self.graph_provider.execute_query(dup_query)
            if duplicates:
                for dup in duplicates:
                    result.add_error(ValidationError(
                        node_type=node_type,
                        node_id=dup["id"],
                        field="id",
                        error=f"Duplicate ID found {dup['count']} times"
                    ))
        
        # Check ID format consistency
        self._validate_id_formats(result)
    
    def _validate_id_formats(self, result: ValidationResult):
        """Validate ID format consistency."""
        # Sample IDs to check format
        id_query = """
        MATCH (n)
        WHERE n.id IS NOT NULL
        RETURN labels(n)[0] as node_type, n.id as id
        LIMIT 1000
        """
        
        id_samples = self.graph_provider.execute_query(id_query)
        id_formats = {}
        
        for sample in id_samples:
            node_type = sample.get("node_type")
            node_id = sample.get("id")
            
            if not node_type or not node_id:
                continue
            
            # Detect ID format
            format_type = self._detect_id_format(node_id)
            
            if node_type not in id_formats:
                id_formats[node_type] = {}
            
            if format_type not in id_formats[node_type]:
                id_formats[node_type][format_type] = 0
            
            id_formats[node_type][format_type] += 1
        
        # Check for inconsistent formats
        for node_type, formats in id_formats.items():
            if len(formats) > 1:
                result.add_error(ValidationError(
                    node_type=node_type,
                    node_id="id_format",
                    field="id",
                    error=f"Inconsistent ID formats: {list(formats.keys())}",
                    severity="warning"
                ))
        
        result.statistics["id_formats"] = id_formats
    
    def _detect_id_format(self, node_id: str) -> str:
        """Detect the format of an ID."""
        if len(node_id) == 32 and all(c in '0123456789abcdef' for c in node_id):
            return "md5"
        elif len(node_id) == 64 and all(c in '0123456789abcdef' for c in node_id):
            return "sha256"
        elif "-" in node_id and len(node_id) == 36:
            return "uuid"
        elif node_id.isdigit():
            return "numeric"
        else:
            return "other"
    
    def _validate_migration_metadata(self, result: ValidationResult):
        """Validate migration metadata after migration."""
        # Check that all nodes have migration metadata
        node_types = ["Podcast", "Episode", "Segment", "Entity", "Insight", "Quote", "Topic"]
        
        for node_type in node_types:
            query = f"""
            MATCH (n:{node_type})
            WHERE n.migrated_at IS NULL OR n.migration_version IS NULL
            RETURN count(n) as count
            """
            
            unmigrated = self.graph_provider.execute_query(query)
            if unmigrated and unmigrated[0]["count"] > 0:
                result.add_error(ValidationError(
                    node_type=node_type,
                    node_id="migration_metadata",
                    field="metadata",
                    error=f"{unmigrated[0]['count']} nodes missing migration metadata"
                ))
    
    def _validate_data_integrity(self, result: ValidationResult):
        """Validate data integrity after migration."""
        # Compare node counts before and after
        # This would require storing pre-migration counts
        
        # Check that no data was lost
        integrity_checks = [
            {
                "name": "Empty nodes",
                "query": """
                MATCH (n)
                WHERE size(keys(n)) <= 2  // Only id and label
                RETURN labels(n)[0] as node_type, count(n) as count
                """
            },
            {
                "name": "Broken relationships",
                "query": """
                MATCH (n)-[r]->(m)
                WHERE n IS NULL OR m IS NULL
                RETURN count(r) as count
                """
            }
        ]
        
        for check in integrity_checks:
            result_data = self.graph_provider.execute_query(check["query"])
            if result_data:
                for row in result_data:
                    if row.get("count", 0) > 0:
                        result.add_error(ValidationError(
                            node_type="Integrity",
                            node_id=check["name"],
                            field="integrity",
                            error=f"{check['name']}: {row}"
                        ))
    
    def _validate_migration_completeness(self, result: ValidationResult):
        """Validate that migration is complete."""
        # Check schema version
        version_query = """
        MATCH (v:SchemaVersion)
        RETURN v.version as version
        ORDER BY v.applied_at DESC
        LIMIT 1
        """
        
        version_result = self.graph_provider.execute_query(version_query)
        if not version_result or version_result[0]["version"] != "1.1.0":
            result.add_error(ValidationError(
                node_type="Schema",
                node_id="version",
                field="version",
                error="Schema not at expected version"
            ))
    
    def _get_constraints(self) -> List[Dict[str, Any]]:
        """Get database constraints."""
        try:
            return self.graph_provider.execute_query("SHOW CONSTRAINTS")
        except:
            return []
    
    def _get_indexes(self) -> List[Dict[str, Any]]:
        """Get database indexes."""
        try:
            return self.graph_provider.execute_query("SHOW INDEXES")
        except:
            return []
    
    def compare_before_after(
        self,
        before_stats: Dict[str, Any],
        after_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compare statistics before and after migration.
        
        Args:
            before_stats: Statistics before migration
            after_stats: Statistics after migration
            
        Returns:
            Comparison results
        """
        comparison = {
            "data_loss": False,
            "differences": {},
            "summary": ""
        }
        
        # Compare node counts
        for node_type in ["Podcast", "Episode", "Segment", "Entity", "Insight", "Quote", "Topic"]:
            before_count = before_stats.get(f"{node_type}_count", 0)
            after_count = after_stats.get(f"{node_type}_count", 0)
            
            if before_count != after_count:
                comparison["differences"][node_type] = {
                    "before": before_count,
                    "after": after_count,
                    "difference": after_count - before_count
                }
                
                if after_count < before_count:
                    comparison["data_loss"] = True
        
        if comparison["data_loss"]:
            comparison["summary"] = "WARNING: Potential data loss detected"
        elif comparison["differences"]:
            comparison["summary"] = "Node counts differ but no data loss"
        else:
            comparison["summary"] = "Migration completed successfully with no data loss"
        
        return comparison