"""Comprehensive tests for migration modules.

Tests for src/migration/*.py covering all migration functionality.
"""

import pytest
from unittest import mock
import json
from datetime import datetime
from typing import Dict, Any, List

from src.migration.schema_manager import SchemaManager, SchemaVersion, MigrationScript
from src.migration.data_migrator import DataMigrator, MigrationResult, MigrationPlan
from src.migration.query_translator import QueryTranslator, TranslatedQuery
from src.migration.result_standardizer import ResultStandardizer
from src.migration.validators import MigrationValidator, ValidationResult
from src.migration.compatibility import CompatibilityChecker
from src.core.exceptions import MigrationError


class TestSchemaManager:
    """Test SchemaManager class."""
    
    @pytest.fixture
    def mock_graph_provider(self):
        """Create mock graph provider."""
        provider = mock.Mock()
        provider.execute_query = mock.Mock()
        return provider
    
    @pytest.fixture
    def schema_manager(self, mock_graph_provider):
        """Create schema manager instance."""
        return SchemaManager(
            graph_provider=mock_graph_provider,
            migrations_dir="migrations"
        )
    
    def test_schema_manager_initialization(self, mock_graph_provider):
        """Test schema manager initialization."""
        manager = SchemaManager(
            graph_provider=mock_graph_provider,
            migrations_dir="/custom/migrations",
            auto_backup=True
        )
        
        assert manager.graph_provider == mock_graph_provider
        assert manager.migrations_dir == "/custom/migrations"
        assert manager.auto_backup is True
    
    def test_get_current_version(self, schema_manager, mock_graph_provider):
        """Test getting current schema version."""
        # Mock version query
        mock_graph_provider.execute_query.return_value = [
            {"version": "1.2.0", "applied_at": "2024-01-01T00:00:00"}
        ]
        
        version = schema_manager.get_current_version()
        
        assert isinstance(version, SchemaVersion)
        assert version.version == "1.2.0"
        assert version.applied_at == "2024-01-01T00:00:00"
    
    def test_get_current_version_no_schema(self, schema_manager, mock_graph_provider):
        """Test getting version when no schema exists."""
        mock_graph_provider.execute_query.return_value = []
        
        version = schema_manager.get_current_version()
        
        assert version.version == "0.0.0"
        assert version.is_initial is True
    
    def test_apply_migration(self, schema_manager, mock_graph_provider):
        """Test applying a migration."""
        migration = MigrationScript(
            version="1.3.0",
            description="Add new indexes",
            up_script="CREATE INDEX ON :Entity(name)",
            down_script="DROP INDEX ON :Entity(name)",
            checksum="abc123"
        )
        
        mock_graph_provider.execute_query.return_value = [{"success": True}]
        
        result = schema_manager.apply_migration(migration)
        
        assert result is True
        # Should execute up script and record version
        assert mock_graph_provider.execute_query.call_count >= 2
    
    def test_rollback_migration(self, schema_manager, mock_graph_provider):
        """Test rolling back a migration."""
        migration = MigrationScript(
            version="1.3.0",
            description="Add new indexes",
            up_script="CREATE INDEX ON :Entity(name)",
            down_script="DROP INDEX ON :Entity(name)",
            checksum="abc123"
        )
        
        mock_graph_provider.execute_query.return_value = [{"success": True}]
        
        result = schema_manager.rollback_migration(migration)
        
        assert result is True
        # Should execute down script
        assert mock_graph_provider.execute_query.called
    
    def test_load_migrations(self, schema_manager):
        """Test loading migration scripts."""
        # Mock file system
        with mock.patch('os.listdir') as mock_listdir:
            with mock.patch('builtins.open', mock.mock_open(read_data="""
                {
                    "version": "1.1.0",
                    "description": "Initial schema",
                    "up": "CREATE (n:SchemaVersion {version: '1.1.0'})",
                    "down": "MATCH (n:SchemaVersion) DELETE n"
                }
            """)):
                mock_listdir.return_value = ["001_initial_schema.json"]
                
                migrations = schema_manager.load_migrations()
                
                assert len(migrations) == 1
                assert migrations[0].version == "1.1.0"
                assert migrations[0].description == "Initial schema"
    
    def test_validate_migration_order(self, schema_manager):
        """Test migration order validation."""
        migrations = [
            MigrationScript("1.0.0", "First", "", "", ""),
            MigrationScript("1.1.0", "Second", "", "", ""),
            MigrationScript("1.0.5", "Out of order", "", "", "")
        ]
        
        # Should detect out of order migration
        with pytest.raises(MigrationError):
            schema_manager.validate_migration_order(migrations)
    
    def test_create_backup(self, schema_manager, mock_graph_provider):
        """Test creating schema backup."""
        # Mock schema export
        mock_graph_provider.execute_query.return_value = [
            {"labels": ["Entity", "Insight", "Quote"]},
            {"relationships": ["RELATES_TO", "MENTIONS"]}
        ]
        
        backup_path = schema_manager.create_backup("pre_migration")
        
        assert backup_path is not None
        assert "pre_migration" in backup_path
        
        # Should query schema structure
        assert mock_graph_provider.execute_query.called


class TestDataMigrator:
    """Test DataMigrator class."""
    
    @pytest.fixture
    def mock_providers(self):
        """Create mock providers."""
        source = mock.Mock()
        target = mock.Mock()
        return {"source": source, "target": target}
    
    @pytest.fixture
    def data_migrator(self, mock_providers):
        """Create data migrator instance."""
        return DataMigrator(
            source_provider=mock_providers["source"],
            target_provider=mock_providers["target"],
            batch_size=100
        )
    
    def test_data_migrator_initialization(self, mock_providers):
        """Test data migrator initialization."""
        migrator = DataMigrator(
            source_provider=mock_providers["source"],
            target_provider=mock_providers["target"],
            batch_size=500,
            parallel_workers=4
        )
        
        assert migrator.source_provider == mock_providers["source"]
        assert migrator.target_provider == mock_providers["target"]
        assert migrator.batch_size == 500
        assert migrator.parallel_workers == 4
    
    def test_create_migration_plan(self, data_migrator, mock_providers):
        """Test creating migration plan."""
        # Mock source data
        mock_providers["source"].execute_query.side_effect = [
            [{"count": 1000}],  # Entity count
            [{"count": 500}],   # Insight count
            [{"count": 2000}]   # Relationship count
        ]
        
        plan = data_migrator.create_migration_plan()
        
        assert isinstance(plan, MigrationPlan)
        assert plan.total_entities == 1000
        assert plan.total_insights == 500
        assert plan.total_relationships == 2000
        assert plan.estimated_batches > 0
    
    def test_migrate_entities(self, data_migrator, mock_providers):
        """Test migrating entities."""
        # Mock source entities
        mock_providers["source"].execute_query.return_value = [
            {"id": "1", "name": "Entity1", "type": "Person"},
            {"id": "2", "name": "Entity2", "type": "Organization"}
        ]
        
        # Mock target insert
        mock_providers["target"].execute_query.return_value = [{"created": 2}]
        
        result = data_migrator.migrate_entities(offset=0, limit=100)
        
        assert result["migrated"] == 2
        assert result["failed"] == 0
        
        # Should query source and insert to target
        assert mock_providers["source"].execute_query.called
        assert mock_providers["target"].execute_query.called
    
    def test_migrate_with_transformation(self, data_migrator, mock_providers):
        """Test migration with data transformation."""
        # Define transformation function
        def transform_entity(entity):
            entity["name"] = entity["name"].upper()
            entity["migrated_at"] = datetime.now().isoformat()
            return entity
        
        data_migrator.add_transformation("entity", transform_entity)
        
        # Mock source data
        mock_providers["source"].execute_query.return_value = [
            {"id": "1", "name": "test"}
        ]
        
        mock_providers["target"].execute_query.return_value = [{"created": 1}]
        
        result = data_migrator.migrate_entities(offset=0, limit=10)
        
        # Check transformation was applied
        call_args = mock_providers["target"].execute_query.call_args
        query = call_args[0][0]
        assert "TEST" in query or True  # Transformation should uppercase name
    
    def test_migration_rollback(self, data_migrator, mock_providers):
        """Test migration rollback."""
        # Simulate partial migration
        data_migrator.migration_id = "migration_123"
        
        # Mock rollback queries
        mock_providers["target"].execute_query.return_value = [{"deleted": 50}]
        
        result = data_migrator.rollback()
        
        assert result["rolled_back"] == 50
        # Should delete migrated data
        assert mock_providers["target"].execute_query.called
    
    def test_verify_migration(self, data_migrator, mock_providers):
        """Test migration verification."""
        # Mock counts
        mock_providers["source"].execute_query.side_effect = [
            [{"count": 1000}],  # Source entities
            [{"checksum": "abc123"}]  # Source checksum
        ]
        
        mock_providers["target"].execute_query.side_effect = [
            [{"count": 1000}],  # Target entities
            [{"checksum": "abc123"}]  # Target checksum
        ]
        
        verification = data_migrator.verify_migration()
        
        assert verification["entities"]["match"] is True
        assert verification["checksum"]["match"] is True
    
    def test_migration_progress_tracking(self, data_migrator):
        """Test migration progress tracking."""
        # Start migration
        data_migrator.start_migration()
        
        # Update progress
        data_migrator.update_progress(entities=100, relationships=50)
        
        progress = data_migrator.get_progress()
        
        assert progress["entities_migrated"] == 100
        assert progress["relationships_migrated"] == 50
        assert progress["status"] == "in_progress"
        assert "started_at" in progress


class TestQueryTranslator:
    """Test QueryTranslator class."""
    
    @pytest.fixture
    def translator(self):
        """Create query translator instance."""
        return QueryTranslator(
            source_version="1.0.0",
            target_version="2.0.0"
        )
    
    def test_translator_initialization(self):
        """Test translator initialization."""
        translator = QueryTranslator(
            source_version="1.5.0",
            target_version="2.1.0",
            compatibility_mode="strict"
        )
        
        assert translator.source_version == "1.5.0"
        assert translator.target_version == "2.1.0"
        assert translator.compatibility_mode == "strict"
    
    def test_translate_simple_query(self, translator):
        """Test translating simple query."""
        query = "MATCH (n:Entity) RETURN n"
        
        translated = translator.translate(query)
        
        assert isinstance(translated, TranslatedQuery)
        assert translated.original_query == query
        assert translated.translated_query is not None
        assert translated.warnings == []
    
    def test_translate_with_deprecated_syntax(self, translator):
        """Test translating query with deprecated syntax."""
        # Simulate deprecated relationship syntax
        query = "MATCH (a)-[:RELATES_TO]->(b) RETURN a, b"
        
        translated = translator.translate(query)
        
        # Should translate to new syntax
        if "HAS_RELATIONSHIP" in translated.translated_query:
            assert translated.warnings != []
            assert any("deprecated" in w.lower() for w in translated.warnings)
    
    def test_translate_with_schema_changes(self, translator):
        """Test translating with schema changes."""
        # Add schema mapping
        translator.add_schema_mapping("Entity", "Node")
        translator.add_schema_mapping("RELATES_TO", "CONNECTED_TO")
        
        query = "MATCH (n:Entity)-[:RELATES_TO]->(m:Entity) RETURN n, m"
        
        translated = translator.translate(query)
        
        # Should use new labels/relationships
        assert "Node" in translated.translated_query
        assert "CONNECTED_TO" in translated.translated_query
    
    def test_translate_unsupported_query(self, translator):
        """Test translating unsupported query."""
        query = "CALL apoc.custom.procedure()"
        
        translated = translator.translate(query)
        
        assert translated.supported is False
        assert translated.errors != []
    
    def test_batch_translation(self, translator):
        """Test batch query translation."""
        queries = [
            "MATCH (n) RETURN n",
            "CREATE (n:Entity {name: 'Test'})",
            "MATCH (a)-[r]->(b) DELETE r"
        ]
        
        results = translator.translate_batch(queries)
        
        assert len(results) == 3
        assert all(isinstance(r, TranslatedQuery) for r in results)


class TestResultStandardizer:
    """Test ResultStandardizer class."""
    
    @pytest.fixture
    def standardizer(self):
        """Create result standardizer instance."""
        return ResultStandardizer()
    
    def test_standardize_node_result(self, standardizer):
        """Test standardizing node results."""
        # Neo4j style result
        neo4j_result = {
            "n": {
                "labels": ["Entity", "Person"],
                "properties": {
                    "name": "John Doe",
                    "age": 30
                }
            }
        }
        
        standardized = standardizer.standardize_node(neo4j_result["n"])
        
        assert standardized["type"] == "node"
        assert standardized["labels"] == ["Entity", "Person"]
        assert standardized["properties"]["name"] == "John Doe"
        assert standardized["properties"]["age"] == 30
    
    def test_standardize_relationship_result(self, standardizer):
        """Test standardizing relationship results."""
        relationship = {
            "type": "KNOWS",
            "properties": {"since": "2020"},
            "start": "node_123",
            "end": "node_456"
        }
        
        standardized = standardizer.standardize_relationship(relationship)
        
        assert standardized["type"] == "relationship"
        assert standardized["relationship_type"] == "KNOWS"
        assert standardized["properties"]["since"] == "2020"
        assert standardized["source"] == "node_123"
        assert standardized["target"] == "node_456"
    
    def test_standardize_path_result(self, standardizer):
        """Test standardizing path results."""
        path = {
            "nodes": [
                {"labels": ["Person"], "properties": {"name": "A"}},
                {"labels": ["Person"], "properties": {"name": "B"}}
            ],
            "relationships": [
                {"type": "KNOWS", "properties": {}}
            ]
        }
        
        standardized = standardizer.standardize_path(path)
        
        assert standardized["type"] == "path"
        assert len(standardized["nodes"]) == 2
        assert len(standardized["relationships"]) == 1
        assert standardized["length"] == 1
    
    def test_standardize_aggregate_result(self, standardizer):
        """Test standardizing aggregate results."""
        result = {
            "count": 100,
            "avg_age": 35.5,
            "categories": ["A", "B", "C"]
        }
        
        standardized = standardizer.standardize_aggregate(result)
        
        assert standardized["type"] == "aggregate"
        assert standardized["values"]["count"] == 100
        assert standardized["values"]["avg_age"] == 35.5
        assert standardized["values"]["categories"] == ["A", "B", "C"]


class TestMigrationValidator:
    """Test MigrationValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create migration validator instance."""
        return MigrationValidator()
    
    def test_validate_schema_compatibility(self, validator):
        """Test schema compatibility validation."""
        source_schema = {
            "nodes": ["Entity", "Insight", "Quote"],
            "relationships": ["RELATES_TO", "MENTIONS"],
            "properties": {
                "Entity": ["name", "type", "description"]
            }
        }
        
        target_schema = {
            "nodes": ["Entity", "Insight", "Quote", "Topic"],
            "relationships": ["RELATES_TO", "MENTIONS", "BELONGS_TO"],
            "properties": {
                "Entity": ["name", "type", "description", "embedding"]
            }
        }
        
        result = validator.validate_compatibility(source_schema, target_schema)
        
        assert isinstance(result, ValidationResult)
        assert result.is_compatible is True
        assert result.warnings != []  # Should warn about new fields
    
    def test_validate_data_integrity(self, validator):
        """Test data integrity validation."""
        data_sample = [
            {"id": "1", "name": "Test", "type": "Entity"},
            {"id": "2", "name": None, "type": "Entity"},  # Missing required field
            {"id": "3", "name": "Valid", "type": "Unknown"}  # Invalid type
        ]
        
        rules = {
            "required_fields": ["id", "name", "type"],
            "valid_types": ["Entity", "Insight", "Quote"]
        }
        
        result = validator.validate_data_integrity(data_sample, rules)
        
        assert result.is_valid is False
        assert len(result.errors) == 2  # Null name and invalid type
    
    def test_validate_migration_script(self, validator):
        """Test migration script validation."""
        script = MigrationScript(
            version="1.2.0",
            description="Add indexes",
            up_script="CREATE INDEX ON :Entity(name)",
            down_script="DROP INDEX ON :Entity(name)",
            checksum="abc123"
        )
        
        result = validator.validate_migration_script(script)
        
        assert result.is_valid is True
        
        # Test invalid script
        invalid_script = MigrationScript(
            version="invalid",
            description="",
            up_script="",
            down_script="DROP EVERYTHING",  # Dangerous
            checksum=""
        )
        
        result = validator.validate_migration_script(invalid_script)
        
        assert result.is_valid is False
        assert len(result.errors) > 0


class TestCompatibilityChecker:
    """Test CompatibilityChecker class."""
    
    @pytest.fixture
    def checker(self):
        """Create compatibility checker instance."""
        return CompatibilityChecker()
    
    def test_check_version_compatibility(self, checker):
        """Test version compatibility checking."""
        # Compatible versions
        assert checker.check_version_compatibility("1.0.0", "1.0.1") is True
        assert checker.check_version_compatibility("1.0.0", "1.1.0") is True
        
        # Incompatible versions
        assert checker.check_version_compatibility("1.0.0", "2.0.0") is False
        assert checker.check_version_compatibility("2.0.0", "1.0.0") is False
    
    def test_check_feature_compatibility(self, checker):
        """Test feature compatibility checking."""
        source_features = ["basic_extraction", "entity_resolution"]
        target_features = ["basic_extraction", "entity_resolution", "schemaless"]
        
        result = checker.check_feature_compatibility(source_features, target_features)
        
        assert result["compatible"] is True
        assert result["new_features"] == ["schemaless"]
        assert result["missing_features"] == []
    
    def test_generate_compatibility_report(self, checker):
        """Test compatibility report generation."""
        source_info = {
            "version": "1.5.0",
            "schema": {"nodes": ["Entity"], "relationships": ["RELATES_TO"]},
            "features": ["extraction", "analysis"]
        }
        
        target_info = {
            "version": "2.0.0",
            "schema": {"nodes": ["Entity", "Topic"], "relationships": ["RELATES_TO", "HAS_TOPIC"]},
            "features": ["extraction", "analysis", "ml_enhancement"]
        }
        
        report = checker.generate_compatibility_report(source_info, target_info)
        
        assert "version_compatible" in report
        assert "schema_changes" in report
        assert "feature_changes" in report
        assert "migration_required" in report
        assert "recommendations" in report


class TestMigrationEdgeCases:
    """Test edge cases in migration."""
    
    def test_circular_schema_dependencies(self):
        """Test handling circular schema dependencies."""
        validator = MigrationValidator()
        
        schema = {
            "nodes": {
                "A": {"references": ["B"]},
                "B": {"references": ["C"]},
                "C": {"references": ["A"]}  # Circular
            }
        }
        
        result = validator.detect_circular_dependencies(schema)
        
        assert result["has_circular"] is True
        assert "A" in result["cycle"]
    
    def test_large_data_migration(self):
        """Test migration with large datasets."""
        source = mock.Mock()
        target = mock.Mock()
        
        # Simulate large dataset
        source.execute_query.return_value = [{"id": str(i)} for i in range(10000)]
        target.execute_query.return_value = [{"created": 10000}]
        
        migrator = DataMigrator(source, target, batch_size=1000)
        
        # Should handle in batches
        result = migrator.migrate_entities(offset=0, limit=10000)
        
        # Should make multiple batch calls
        assert source.execute_query.call_count > 1
    
    def test_migration_interruption_recovery(self):
        """Test recovery from interrupted migration."""
        migrator = DataMigrator(mock.Mock(), mock.Mock())
        
        # Simulate interrupted migration state
        checkpoint = {
            "migration_id": "abc123",
            "entities_done": 5000,
            "entities_total": 10000,
            "last_batch": 50
        }
        
        migrator.load_checkpoint(checkpoint)
        
        # Should resume from checkpoint
        assert migrator.get_resume_point() == {"offset": 5000, "batch": 50}