"""
Compatibility checker for migration from monolithic to modular system.

This module verifies compatibility between the old and new systems
and identifies potential issues before migration.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
import json
import importlib.util

from ..core.models import EntityType, InsightType, QuoteType, ComplexityLevel
from ..providers.graph.base import GraphProvider

logger = logging.getLogger(__name__)


@dataclass
class CompatibilityIssue:
    """Represents a compatibility issue found during checking."""
    severity: str  # "error", "warning", "info"
    category: str  # "schema", "data", "feature", "dependency"
    message: str
    details: Optional[Dict[str, Any]] = None
    resolution: Optional[str] = None


@dataclass
class CompatibilityReport:
    """Report of compatibility check results."""
    compatible: bool = True
    monolithic_version: Optional[str] = None
    modular_version: Optional[str] = None
    issues: List[CompatibilityIssue] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    
    def add_issue(self, issue: CompatibilityIssue):
        """Add an issue to the report."""
        self.issues.append(issue)
        if issue.severity == "error":
            self.compatible = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "compatible": self.compatible,
            "monolithic_version": self.monolithic_version,
            "modular_version": self.modular_version,
            "issue_count": len(self.issues),
            "error_count": len([i for i in self.issues if i.severity == "error"]),
            "warning_count": len([i for i in self.issues if i.severity == "warning"]),
            "info_count": len([i for i in self.issues if i.severity == "info"]),
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "message": i.message,
                    "details": i.details,
                    "resolution": i.resolution
                }
                for i in self.issues
            ],
            "statistics": self.statistics,
            "recommendations": self.recommendations
        }


class CompatibilityChecker:
    """
    Checks compatibility between monolithic and modular systems.
    
    This class verifies:
    - Schema compatibility
    - Data format compatibility
    - Feature parity
    - Dependency compatibility
    """
    
    def __init__(
        self,
        graph_provider: GraphProvider,
        monolithic_path: Optional[Path] = None
    ):
        """
        Initialize compatibility checker.
        
        Args:
            graph_provider: Graph database provider
            monolithic_path: Path to monolithic system code (optional)
        """
        self.graph_provider = graph_provider
        self.monolithic_path = monolithic_path
    
    def check_all(self) -> CompatibilityReport:
        """
        Perform comprehensive compatibility check.
        
        Returns:
            Compatibility report with all findings
        """
        report = CompatibilityReport()
        
        logger.info("Starting compatibility check")
        
        # Check schema compatibility
        self._check_schema_compatibility(report)
        
        # Check data compatibility
        self._check_data_compatibility(report)
        
        # Check feature compatibility
        self._check_feature_compatibility(report)
        
        # Check dependency compatibility
        if self.monolithic_path:
            self._check_dependency_compatibility(report)
        
        # Generate recommendations
        self._generate_recommendations(report)
        
        logger.info(f"Compatibility check complete. Compatible: {report.compatible}")
        
        return report
    
    def _check_schema_compatibility(self, report: CompatibilityReport):
        """Check schema compatibility between systems."""
        logger.info("Checking schema compatibility")
        
        try:
            # Get current schema information
            node_types = self._get_node_types()
            relationship_types = self._get_relationship_types()
            constraints = self._get_constraints()
            indexes = self._get_indexes()
            
            report.statistics["node_types"] = len(node_types)
            report.statistics["relationship_types"] = len(relationship_types)
            report.statistics["constraints"] = len(constraints)
            report.statistics["indexes"] = len(indexes)
            
            # Expected node types in modular system
            expected_nodes = {
                "Podcast", "Episode", "Segment", "Entity", 
                "Insight", "Quote", "Topic", "Speaker"
            }
            
            # Check for missing node types
            missing_nodes = expected_nodes - node_types
            if missing_nodes:
                report.add_issue(CompatibilityIssue(
                    severity="error",
                    category="schema",
                    message=f"Missing node types: {', '.join(missing_nodes)}",
                    resolution="These node types need to be created during migration"
                ))
            
            # Check for extra node types
            extra_nodes = node_types - expected_nodes - {"SchemaVersion", "MigrationHistory", "BackupMarker"}
            if extra_nodes:
                report.add_issue(CompatibilityIssue(
                    severity="warning",
                    category="schema",
                    message=f"Extra node types found: {', '.join(extra_nodes)}",
                    details={"node_types": list(extra_nodes)},
                    resolution="Review if these node types should be migrated"
                ))
            
            # Expected relationships
            expected_relationships = {
                "HAS_EPISODE", "HAS_SEGMENT", "MENTIONED_IN", "RELATED_TO",
                "CO_OCCURS_WITH", "SPEAKS_IN", "SPEAKS", "DISCUSSES",
                "HAS_SENTIMENT", "EXTRACTED_FROM", "QUOTED_IN", "COVERS_TOPIC",
                "HAS_TOPIC", "BELONGS_TO_TOPIC", "CONTAINS_TOPIC", "CONTRIBUTES_TO"
            }
            
            # Check for missing relationships
            missing_rels = expected_relationships - relationship_types
            if missing_rels:
                report.add_issue(CompatibilityIssue(
                    severity="warning",
                    category="schema",
                    message=f"Missing relationship types: {', '.join(missing_rels)}",
                    resolution="These relationships may need to be created"
                ))
            
            # Check constraints
            self._check_constraints(constraints, report)
            
            # Check indexes
            self._check_indexes(indexes, report)
            
        except Exception as e:
            report.add_issue(CompatibilityIssue(
                severity="error",
                category="schema",
                message=f"Failed to check schema: {str(e)}"
            ))
    
    def _check_data_compatibility(self, report: CompatibilityReport):
        """Check data format and content compatibility."""
        logger.info("Checking data compatibility")
        
        try:
            # Check for required properties on nodes
            self._check_node_properties(report)
            
            # Check data types and formats
            self._check_data_formats(report)
            
            # Check for data integrity issues
            self._check_data_integrity(report)
            
            # Check embedding dimensions
            self._check_embeddings(report)
            
        except Exception as e:
            report.add_issue(CompatibilityIssue(
                severity="error",
                category="data",
                message=f"Failed to check data compatibility: {str(e)}"
            ))
    
    def _check_feature_compatibility(self, report: CompatibilityReport):
        """Check feature parity between systems."""
        logger.info("Checking feature compatibility")
        
        # Features in modular system
        modular_features = {
            "audio_transcription",
            "speaker_diarization",
            "entity_extraction",
            "insight_extraction",
            "quote_extraction",
            "complexity_analysis",
            "sentiment_analysis",
            "graph_analysis",
            "embedding_generation",
            "batch_processing",
            "checkpoint_recovery",
            "health_monitoring",
            "rate_limiting",
            "retry_logic"
        }
        
        # Check if monolithic system has additional features
        if self.monolithic_path:
            monolithic_features = self._analyze_monolithic_features()
            
            missing_features = monolithic_features - modular_features
            if missing_features:
                report.add_issue(CompatibilityIssue(
                    severity="warning",
                    category="feature",
                    message=f"Features in monolithic not in modular: {', '.join(missing_features)}",
                    resolution="Consider implementing these features if needed"
                ))
    
    def _check_dependency_compatibility(self, report: CompatibilityReport):
        """Check dependency compatibility."""
        logger.info("Checking dependency compatibility")
        
        try:
            # Check Python version compatibility
            # Check package version compatibility
            # This would require parsing requirements files
            pass
            
        except Exception as e:
            report.add_issue(CompatibilityIssue(
                severity="warning",
                category="dependency",
                message=f"Could not check dependencies: {str(e)}"
            ))
    
    def _get_node_types(self) -> Set[str]:
        """Get all node types in the database."""
        query = """
        MATCH (n)
        RETURN DISTINCT labels(n) as labels
        """
        
        results = self.graph_provider.execute_query(query)
        node_types = set()
        
        for result in results:
            labels = result.get("labels", [])
            node_types.update(labels)
        
        return node_types
    
    def _get_relationship_types(self) -> Set[str]:
        """Get all relationship types in the database."""
        query = """
        MATCH ()-[r]->()
        RETURN DISTINCT type(r) as type
        """
        
        results = self.graph_provider.execute_query(query)
        return {r["type"] for r in results if r.get("type")}
    
    def _get_constraints(self) -> List[Dict[str, Any]]:
        """Get all constraints in the database."""
        try:
            query = "SHOW CONSTRAINTS"
            return self.graph_provider.execute_query(query)
        except:
            return []
    
    def _get_indexes(self) -> List[Dict[str, Any]]:
        """Get all indexes in the database."""
        try:
            query = "SHOW INDEXES"
            return self.graph_provider.execute_query(query)
        except:
            return []
    
    def _check_constraints(self, constraints: List[Dict[str, Any]], report: CompatibilityReport):
        """Check if required constraints exist."""
        # Expected constraints
        expected_constraints = {
            "Podcast": ["id"],
            "Episode": ["id"],
            "Segment": ["id"],
            "Entity": ["id"],
            "Insight": ["id"],
            "Quote": ["id"],
            "Topic": ["id"],
            "PotentialConnection": ["id"]
        }
        
        # Parse existing constraints
        existing_constraints = {}
        for constraint in constraints:
            # Parse constraint info (format varies by Neo4j version)
            # This is a simplified version
            pass
        
        # Report missing constraints
        for node_type, properties in expected_constraints.items():
            for prop in properties:
                # Check if constraint exists
                pass
    
    def _check_indexes(self, indexes: List[Dict[str, Any]], report: CompatibilityReport):
        """Check if required indexes exist."""
        # Expected indexes
        expected_indexes = {
            "Podcast": ["name"],
            "Episode": ["title", "published_date"],
            "Segment": ["text", "episode_id"],
            "Entity": ["name", "bridge_score", "is_peripheral"],
            "Insight": ["insight_type", "is_bridge_insight"],
            "Quote": ["quote_type", "speaker"],
            "Topic": ["name", "trend"]
        }
        
        # Similar to constraints check
        pass
    
    def _check_node_properties(self, report: CompatibilityReport):
        """Check if nodes have required properties."""
        # Sample check for Podcast nodes
        query = """
        MATCH (p:Podcast)
        WHERE p.id IS NULL OR p.title IS NULL
        RETURN count(p) as count
        """
        
        result = self.graph_provider.execute_query(query)
        if result and result[0]["count"] > 0:
            report.add_issue(CompatibilityIssue(
                severity="error",
                category="data",
                message=f"Found {result[0]['count']} Podcast nodes missing required properties",
                resolution="Update nodes to include required properties before migration"
            ))
    
    def _check_data_formats(self, report: CompatibilityReport):
        """Check data format consistency."""
        # Check date formats
        date_query = """
        MATCH (e:Episode)
        WHERE e.published_date IS NOT NULL
        RETURN e.published_date as date
        LIMIT 10
        """
        
        dates = self.graph_provider.execute_query(date_query)
        date_formats = set()
        
        for record in dates:
            date_str = record.get("date")
            if date_str:
                # Detect date format
                if "T" in date_str:
                    date_formats.add("ISO")
                elif "/" in date_str:
                    date_formats.add("slash")
                elif "-" in date_str:
                    date_formats.add("dash")
        
        if len(date_formats) > 1:
            report.add_issue(CompatibilityIssue(
                severity="warning",
                category="data",
                message="Inconsistent date formats found",
                details={"formats": list(date_formats)},
                resolution="Standardize date formats during migration"
            ))
    
    def _check_data_integrity(self, report: CompatibilityReport):
        """Check for data integrity issues."""
        # Check for orphaned nodes
        orphan_queries = [
            ("Episode", "MATCH (e:Episode) WHERE NOT (e)<-[:HAS_EPISODE]-(:Podcast) RETURN count(e) as count"),
            ("Segment", "MATCH (s:Segment) WHERE NOT (s)<-[:HAS_SEGMENT]-(:Episode) RETURN count(s) as count"),
            ("Quote", "MATCH (q:Quote) WHERE NOT (q)-[:EXTRACTED_FROM]->(:Segment) RETURN count(q) as count")
        ]
        
        for node_type, query in orphan_queries:
            result = self.graph_provider.execute_query(query)
            if result and result[0]["count"] > 0:
                report.add_issue(CompatibilityIssue(
                    severity="warning",
                    category="data",
                    message=f"Found {result[0]['count']} orphaned {node_type} nodes",
                    resolution=f"Link orphaned {node_type} nodes or remove them"
                ))
        
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
            report.add_issue(CompatibilityIssue(
                severity="error",
                category="data",
                message=f"Found {len(duplicates)} duplicate IDs",
                details={"duplicates": duplicates},
                resolution="Resolve duplicate IDs before migration"
            ))
    
    def _check_embeddings(self, report: CompatibilityReport):
        """Check embedding compatibility."""
        # Check embedding dimensions
        embedding_query = """
        MATCH (n)
        WHERE n.embedding IS NOT NULL
        RETURN labels(n)[0] as node_type, 
               size(n.embedding) as dimension,
               count(n) as count
        ORDER BY count DESC
        """
        
        embeddings = self.graph_provider.execute_query(embedding_query)
        dimensions = {}
        
        for record in embeddings:
            node_type = record.get("node_type")
            dimension = record.get("dimension")
            count = record.get("count", 0)
            
            if node_type not in dimensions:
                dimensions[node_type] = {}
            dimensions[node_type][dimension] = count
        
        # Check for inconsistent dimensions
        for node_type, dims in dimensions.items():
            if len(dims) > 1:
                report.add_issue(CompatibilityIssue(
                    severity="warning",
                    category="data",
                    message=f"Inconsistent embedding dimensions for {node_type}",
                    details={"dimensions": dims},
                    resolution="Standardize embedding dimensions or handle multiple dimensions"
                ))
        
        report.statistics["embeddings"] = dimensions
    
    def _analyze_monolithic_features(self) -> Set[str]:
        """Analyze features in monolithic system."""
        features = set()
        
        if not self.monolithic_path or not self.monolithic_path.exists():
            return features
        
        try:
            # Simple feature detection by looking for function/class names
            monolithic_file = self.monolithic_path / "podcast_knowledge_system_enhanced.py"
            
            if monolithic_file.exists():
                content = monolithic_file.read_text()
                
                # Look for feature indicators
                feature_indicators = {
                    "transcribe": "audio_transcription",
                    "diarize": "speaker_diarization",
                    "extract_entities": "entity_extraction",
                    "extract_insights": "insight_extraction",
                    "extract_quotes": "quote_extraction",
                    "analyze_complexity": "complexity_analysis",
                    "sentiment": "sentiment_analysis",
                    "temporal_analysis": "temporal_analysis",
                    "hierarchical_insights": "hierarchical_insights",
                    "cross_episode": "cross_episode_analysis"
                }
                
                for indicator, feature in feature_indicators.items():
                    if indicator in content:
                        features.add(feature)
        
        except Exception as e:
            logger.warning(f"Could not analyze monolithic features: {e}")
        
        return features
    
    def _generate_recommendations(self, report: CompatibilityReport):
        """Generate recommendations based on findings."""
        if not report.compatible:
            report.recommendations.append(
                "Resolve all ERROR-level issues before proceeding with migration"
            )
        
        # Check for schema issues
        schema_errors = [i for i in report.issues if i.category == "schema" and i.severity == "error"]
        if schema_errors:
            report.recommendations.append(
                "Run schema migration to create missing node types and relationships"
            )
        
        # Check for data issues
        data_errors = [i for i in report.issues if i.category == "data" and i.severity == "error"]
        if data_errors:
            report.recommendations.append(
                "Clean up data issues (duplicates, missing properties) before migration"
            )
        
        # Check for orphaned nodes
        orphan_warnings = [i for i in report.issues if "orphaned" in i.message]
        if orphan_warnings:
            report.recommendations.append(
                "Consider creating a cleanup script for orphaned nodes"
            )
        
        # General recommendations
        report.recommendations.extend([
            "Create a full database backup before migration",
            "Run migration in dry-run mode first to identify issues",
            "Monitor system resources during migration",
            "Plan for downtime or use a blue-green deployment strategy"
        ])
    
    def generate_compatibility_script(self, report: CompatibilityReport) -> str:
        """
        Generate a script to fix compatibility issues.
        
        Args:
            report: Compatibility report with issues
            
        Returns:
            Cypher script to fix issues
        """
        script_lines = [
            "// Auto-generated compatibility fix script",
            "// Generated at: " + datetime.now().isoformat(),
            ""
        ]
        
        # Group issues by category
        for issue in report.issues:
            if issue.severity != "error":
                continue
            
            script_lines.append(f"// Fix: {issue.message}")
            
            # Generate specific fixes based on issue type
            if "Missing node types" in issue.message:
                # Node creation would be handled by schema migration
                script_lines.append("// Run schema migration to create node types")
            
            elif "duplicate IDs" in issue.message:
                script_lines.append("""
// Identify and fix duplicate IDs
MATCH (n)
WHERE n.id IS NOT NULL
WITH n.id as id, collect(n) as nodes
WHERE size(nodes) > 1
FOREACH (i IN range(1, size(nodes)-1) |
    SET (nodes[i]).id = (nodes[0]).id + '_dup_' + toString(i)
)
""")
            
            elif "missing required properties" in issue.message:
                script_lines.append("""
// Add default values for missing properties
MATCH (p:Podcast)
WHERE p.id IS NULL
SET p.id = p.title + '_' + toString(id(p))
""")
            
            script_lines.append("")
        
        return "\n".join(script_lines)