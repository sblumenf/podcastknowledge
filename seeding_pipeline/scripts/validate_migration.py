#!/usr/bin/env python3
"""
Migration validation script for the podcast knowledge pipeline.

This script validates the migration from monolithic to modular system
and generates a comprehensive report using the new migration module.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
import json
import argparse
from typing import Dict, Any, Optional

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.config import get_config
from src.providers.graph.neo4j import Neo4jProvider
from src.migration.schema_manager import SchemaManager
from src.migration.data_migrator import DataMigrator
from src.migration.compatibility import CompatibilityChecker
from src.migration.validators import MigrationValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationValidationRunner:
    """Runs comprehensive migration validation."""
    
    def __init__(self, config_path: str = "config/config.yml"):
        """Initialize validation runner."""
        self.config = get_config(config_path)
        self.graph_provider = self._init_graph_provider()
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "config_path": config_path,
            "results": {}
        }
    
    def _init_graph_provider(self) -> Neo4jProvider:
        """Initialize graph provider."""
        graph_config = self.config["providers"]["graph"]
        return Neo4jProvider(
            uri=graph_config["uri"],
            username=graph_config["username"],
            password=graph_config["password"]
        )
    
    def run_all_validations(self, monolithic_path: Optional[Path] = None) -> Dict[str, Any]:
        """Run all validation checks."""
        logger.info("Starting comprehensive migration validation")
        
        # 1. Check compatibility
        self._check_compatibility(monolithic_path)
        
        # 2. Validate schema
        self._validate_schema()
        
        # 3. Validate data integrity
        self._validate_data_integrity()
        
        # 4. Check migration readiness
        self._check_migration_readiness()
        
        # 5. Generate summary
        self._generate_summary()
        
        return self.report
    
    def _check_compatibility(self, monolithic_path: Optional[Path]):
        """Check compatibility between systems."""
        logger.info("Checking compatibility...")
        
        try:
            checker = CompatibilityChecker(self.graph_provider, monolithic_path)
            compat_report = checker.check_all()
            
            self.report["results"]["compatibility"] = {
                "compatible": compat_report.compatible,
                "issues": len(compat_report.issues),
                "errors": len([i for i in compat_report.issues if i.severity == "error"]),
                "warnings": len([i for i in compat_report.issues if i.severity == "warning"]),
                "statistics": compat_report.statistics,
                "top_issues": [
                    {
                        "severity": i.severity,
                        "category": i.category,
                        "message": i.message,
                        "resolution": i.resolution
                    }
                    for i in compat_report.issues[:10]
                ]
            }
            
            logger.info(f"Compatibility check complete. Compatible: {compat_report.compatible}")
            
        except Exception as e:
            logger.error(f"Compatibility check failed: {e}")
            self.report["results"]["compatibility"] = {
                "error": str(e),
                "compatible": False
            }
    
    def _validate_schema(self):
        """Validate database schema."""
        logger.info("Validating schema...")
        
        try:
            schema_manager = SchemaManager(self.graph_provider)
            
            # Get current version
            current_version = schema_manager.get_current_version()
            
            # Validate schema
            validation = schema_manager.validate_schema()
            
            self.report["results"]["schema"] = {
                "current_version": current_version.version if current_version else "unknown",
                "valid": validation["valid"],
                "node_types": validation["node_types"],
                "relationship_types": validation["relationship_types"],
                "constraint_count": len(validation.get("constraints", [])),
                "index_count": len(validation.get("indexes", [])),
                "errors": validation.get("errors", []),
                "warnings": validation.get("warnings", [])
            }
            
            logger.info(f"Schema validation complete. Version: {current_version.version if current_version else 'unknown'}")
            
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            self.report["results"]["schema"] = {
                "error": str(e),
                "valid": False
            }
    
    def _validate_data_integrity(self):
        """Validate data integrity."""
        logger.info("Validating data integrity...")
        
        try:
            validator = MigrationValidator(self.graph_provider)
            
            # Run pre-migration validation
            validation_result = validator.validate_pre_migration()
            
            self.report["results"]["data_integrity"] = {
                "valid": validation_result.valid,
                "total_checked": validation_result.total_checked,
                "error_count": len(validation_result.errors),
                "warning_count": len(validation_result.warnings),
                "statistics": validation_result.statistics,
                "sample_errors": [
                    {
                        "node_type": e.node_type,
                        "node_id": e.node_id,
                        "field": e.field,
                        "error": e.error
                    }
                    for e in validation_result.errors[:10]
                ]
            }
            
            # Additional integrity checks
            self._check_specific_integrity_rules()
            
            logger.info(f"Data integrity validation complete. Valid: {validation_result.valid}")
            
        except Exception as e:
            logger.error(f"Data integrity validation failed: {e}")
            self.report["results"]["data_integrity"] = {
                "error": str(e),
                "valid": False
            }
    
    def _check_specific_integrity_rules(self):
        """Check specific integrity rules."""
        integrity_checks = []
        
        # Check 1: All episodes have podcasts
        query1 = """
        MATCH (e:Episode)
        OPTIONAL MATCH (p:Podcast)-[:HAS_EPISODE]->(e)
        WITH count(e) as total, count(p) as with_podcast
        RETURN total, with_podcast, total - with_podcast as orphaned
        """
        
        result1 = self.graph_provider.execute_query(query1)
        if result1:
            integrity_checks.append({
                "rule": "Episodes have podcasts",
                "total": result1[0]["total"],
                "valid": result1[0]["with_podcast"],
                "invalid": result1[0]["orphaned"],
                "passed": result1[0]["orphaned"] == 0
            })
        
        # Check 2: All segments have valid timestamps
        query2 = """
        MATCH (s:Segment)
        WHERE s.start_time >= 0 AND s.end_time > s.start_time
        WITH count(s) as valid_timestamps
        MATCH (s:Segment)
        WITH valid_timestamps, count(s) as total
        RETURN total, valid_timestamps, total - valid_timestamps as invalid
        """
        
        result2 = self.graph_provider.execute_query(query2)
        if result2:
            integrity_checks.append({
                "rule": "Segments have valid timestamps",
                "total": result2[0]["total"],
                "valid": result2[0]["valid_timestamps"],
                "invalid": result2[0]["invalid"],
                "passed": result2[0]["invalid"] == 0
            })
        
        # Check 3: Entity types are valid
        query3 = """
        MATCH (e:Entity)
        WHERE e.type IN ['person', 'organization', 'product', 'concept', 
                        'technology', 'location', 'event', 'other']
        WITH count(e) as valid_types
        MATCH (e:Entity)
        WITH valid_types, count(e) as total
        RETURN total, valid_types, total - valid_types as invalid
        """
        
        result3 = self.graph_provider.execute_query(query3)
        if result3:
            integrity_checks.append({
                "rule": "Entities have valid types",
                "total": result3[0]["total"],
                "valid": result3[0]["valid_types"],
                "invalid": result3[0]["invalid"],
                "passed": result3[0]["invalid"] == 0
            })
        
        self.report["results"]["data_integrity"]["specific_checks"] = integrity_checks
    
    def _check_migration_readiness(self):
        """Check if system is ready for migration."""
        logger.info("Checking migration readiness...")
        
        readiness = {
            "ready": True,
            "checks": [],
            "blockers": [],
            "warnings": []
        }
        
        # Check 1: Compatibility
        if "compatibility" in self.report["results"]:
            compat_ready = self.report["results"]["compatibility"].get("compatible", False)
            readiness["checks"].append({
                "name": "Compatibility",
                "passed": compat_ready,
                "details": f"{self.report['results']['compatibility'].get('errors', 0)} errors"
            })
            if not compat_ready:
                readiness["blockers"].append("System compatibility issues must be resolved")
                readiness["ready"] = False
        
        # Check 2: Schema validity
        if "schema" in self.report["results"]:
            schema_valid = self.report["results"]["schema"].get("valid", False)
            readiness["checks"].append({
                "name": "Schema Validity",
                "passed": schema_valid,
                "details": f"Version: {self.report['results']['schema'].get('current_version', 'unknown')}"
            })
            if not schema_valid:
                readiness["warnings"].append("Schema validation issues found")
        
        # Check 3: Data integrity
        if "data_integrity" in self.report["results"]:
            data_valid = self.report["results"]["data_integrity"].get("valid", False)
            readiness["checks"].append({
                "name": "Data Integrity",
                "passed": data_valid,
                "details": f"{self.report['results']['data_integrity'].get('error_count', 0)} errors"
            })
            if not data_valid:
                readiness["blockers"].append("Data integrity issues must be resolved")
                readiness["ready"] = False
        
        # Check 4: Database size
        size_query = """
        MATCH (n)
        WITH count(n) as node_count
        MATCH ()-[r]->()
        WITH node_count, count(r) as rel_count
        RETURN node_count, rel_count, node_count + rel_count as total
        """
        
        size_result = self.graph_provider.execute_query(size_query)
        if size_result:
            total_size = size_result[0]["total"]
            readiness["checks"].append({
                "name": "Database Size",
                "passed": True,
                "details": f"{size_result[0]['node_count']:,} nodes, {size_result[0]['rel_count']:,} relationships"
            })
            
            if total_size > 1000000:
                readiness["warnings"].append("Large database - consider migrating during off-peak hours")
        
        self.report["results"]["migration_readiness"] = readiness
        logger.info(f"Migration readiness check complete. Ready: {readiness['ready']}")
    
    def _generate_summary(self):
        """Generate summary of validation results."""
        summary = {
            "overall_status": "READY",
            "can_proceed": True,
            "action_items": [],
            "recommendations": []
        }
        
        # Check compatibility
        if "compatibility" in self.report["results"]:
            if not self.report["results"]["compatibility"].get("compatible", False):
                summary["overall_status"] = "NOT READY"
                summary["can_proceed"] = False
                summary["action_items"].append("Resolve compatibility issues")
        
        # Check data integrity
        if "data_integrity" in self.report["results"]:
            error_count = self.report["results"]["data_integrity"].get("error_count", 0)
            if error_count > 0:
                summary["overall_status"] = "NEEDS ATTENTION"
                if error_count > 100:
                    summary["can_proceed"] = False
                summary["action_items"].append(f"Fix {error_count} data integrity errors")
        
        # Check migration readiness
        if "migration_readiness" in self.report["results"]:
            if not self.report["results"]["migration_readiness"].get("ready", False):
                summary["overall_status"] = "NOT READY"
                summary["can_proceed"] = False
                blockers = self.report["results"]["migration_readiness"].get("blockers", [])
                summary["action_items"].extend(blockers)
        
        # Add recommendations
        summary["recommendations"] = [
            "Create a full database backup before migration",
            "Run migration during off-peak hours",
            "Monitor system resources during migration",
            "Have a rollback plan ready",
            "Test in a staging environment first"
        ]
        
        self.report["summary"] = summary


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Validate migration readiness for podcast knowledge pipeline"
    )
    parser.add_argument(
        "--config",
        default="config/config.yml",
        help="Path to config file"
    )
    parser.add_argument(
        "--monolithic-path",
        help="Path to monolithic system for compatibility check"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file for report (default: migration_validation_TIMESTAMP.json)"
    )
    
    args = parser.parse_args()
    
    # Run validation
    runner = MigrationValidationRunner(args.config)
    
    monolithic_path = Path(args.monolithic_path) if args.monolithic_path else None
    report = runner.run_all_validations(monolithic_path)
    
    # Save report
    if args.output:
        output_file = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"migration_validation_{timestamp}.json"
    
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print("\n" + "="*60)
    print("MIGRATION VALIDATION SUMMARY")
    print("="*60)
    
    summary = report.get("summary", {})
    
    # Color codes for terminal
    if summary["overall_status"] == "READY":
        status_color = "\033[92m"  # Green
    elif summary["overall_status"] == "NEEDS ATTENTION":
        status_color = "\033[93m"  # Yellow
    else:
        status_color = "\033[91m"  # Red
    
    reset_color = "\033[0m"
    
    print(f"\nOverall Status: {status_color}{summary['overall_status']}{reset_color}")
    print(f"Can Proceed: {'Yes' if summary['can_proceed'] else 'No'}")
    
    if summary.get("action_items"):
        print("\nAction Items:")
        for item in summary["action_items"]:
            print(f"  - {item}")
    
    if summary.get("recommendations"):
        print("\nRecommendations:")
        for rec in summary["recommendations"][:3]:
            print(f"  - {rec}")
    
    print(f"\nFull report saved to: {output_file}")
    
    # Exit with appropriate code
    sys.exit(0 if summary["can_proceed"] else 1)


if __name__ == "__main__":
    main()