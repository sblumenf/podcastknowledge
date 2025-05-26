"""
Migration module for the podcast knowledge pipeline.

This module provides tools and utilities for migrating from the monolithic
podcast knowledge system to the modular architecture, including:

- Schema evolution support for Neo4j
- Data migration utilities
- Compatibility checks
- Migration progress tracking
- Rollback capabilities
"""

from .schema_manager import SchemaManager, SchemaVersion
from .data_migrator import DataMigrator, MigrationStatus
from .compatibility import CompatibilityChecker, CompatibilityReport
from .validators import MigrationValidator, ValidationResult

__all__ = [
    "SchemaManager",
    "SchemaVersion",
    "DataMigrator",
    "MigrationStatus",
    "CompatibilityChecker",
    "CompatibilityReport",
    "MigrationValidator",
    "ValidationResult",
]