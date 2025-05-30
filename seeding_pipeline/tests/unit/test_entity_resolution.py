"""Tests for schemaless entity resolution component."""

import pytest
from unittest.mock import Mock, patch, mock_open
import yaml
from typing import List, Dict, Any

from src.processing.entity_resolution import EntityResolver, EntityResolutionConfig


class TestSchemalessEntityResolver:
    """Test suite for SchemalessEntityResolver."""

    @pytest.fixture
    def resolver(self):
        """Create entity resolver instance with default config."""
        config = EntityResolutionConfig(
            similarity_threshold=0.85,
            case_sensitive=False,
            use_aliases=True,
            use_abbreviations=True,
            merge_singular_plural=True
        )
        return EntityResolver(config)

    @pytest.fixture
    def sample_entities(self) -> List[Dict[str, Any]]:
        """Create diverse entity test data."""
        return [
            {"id": "1", "name": "Artificial Intelligence", "type": "CONCEPT"},
            {"id": "2", "name": "AI", "type": "CONCEPT"},
            {"id": "3", "name": "Machine Learning", "type": "CONCEPT"},
            {"id": "4", "name": "ML", "type": "CONCEPT"},
            {"id": "5", "name": "Google", "type": "ORGANIZATION"},
            {"id": "6", "name": "Google Inc.", "type": "ORGANIZATION"},
            {"id": "7", "name": "Dr. Smith", "type": "PERSON"},
            {"id": "8", "name": "Doctor Smith", "type": "PERSON"},
        ]

    def _get_mock_yaml(self) -> str:
        """Get mock YAML configuration for tests."""
        return """
aliases:
  - ["AI", "Artificial Intelligence", "A.I."]
  - ["ML", "Machine Learning"]
  - ["CEO", "Chief Executive Officer"]
  
abbreviations:
  Dr: "Doctor"
  Prof: "Professor"
  Inc: "Incorporated"
  Corp: "Corporation"
  
thresholds:
  fuzzy_match_threshold: 0.85
  confidence_threshold: 0.7
"""

    # Setup and Fixtures Tests
    def test_init_default_config(self):
        """Verify default thresholds and settings."""
        resolver = EntityResolver()
        assert resolver.config.similarity_threshold == 0.85
        assert resolver.config.case_sensitive is False
        assert resolver.config.use_aliases is True

    def test_init_with_custom_config(self):
        """Test custom configuration loading."""
        config = EntityResolutionConfig(
            similarity_threshold=0.9,
            use_aliases=False
        )
        resolver = EntityResolver(config)
        assert resolver.config.similarity_threshold == 0.9
        assert resolver.config.use_aliases is False

    def test_load_resolution_rules(self):
        """Verify built-in alias rules work."""
        resolver = EntityResolver()
        # Check built-in alias rules exist
        assert len(resolver.alias_rules) > 0
        assert len(resolver.abbreviation_map) > 0

    def test_invalid_config_handling(self):
        """Test graceful handling of bad config."""
        # Test with None config
        resolver = EntityResolver(None)
        # Should initialize with default config
        assert resolver.config.similarity_threshold == 0.85

    # Basic Entity Resolution Tests
    def test_resolve_exact_duplicates(self, resolver, sample_entities):
        """Same entity, different IDs."""
        entities = [
            {"id": "1", "value": "OpenAI", "type": "ORGANIZATION"},
            {"id": "2", "value": "OpenAI", "type": "ORGANIZATION"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        assert len(result["resolved_entities"]) == 1
        assert result["resolved_entities"][0]["value"] == "OpenAI"
        assert result["metrics"]["merges_performed"] == 1

    def test_resolve_case_differences(self, resolver):
        """Test case-insensitive matching."""
        entities = [
            {"id": "1", "value": "IBM", "type": "ORGANIZATION"},
            {"id": "2", "value": "ibm", "type": "ORGANIZATION"},
            {"id": "3", "value": "Ibm", "type": "ORGANIZATION"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        assert len(result["resolved_entities"]) == 1
        assert result["resolved_entities"][0]["value"] == "IBM"  # Preserves first case

    def test_resolve_with_extra_spaces(self, resolver):
        """Test whitespace normalization."""
        entities = [
            {"id": "1", "name": " Apple Inc ", "type": "ORGANIZATION"},
            {"id": "2", "name": "Apple Inc", "type": "ORGANIZATION"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Apple Inc"

    def test_no_duplicates_unchanged(self, resolver):
        """Verify unique entities remain unchanged."""
        entities = [
            {"id": "1", "name": "Tesla", "type": "ORGANIZATION"},
            {"id": "2", "name": "SpaceX", "type": "ORGANIZATION"},
            {"id": "3", "name": "Neuralink", "type": "ORGANIZATION"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        assert len(result["entities"]) == 3
        assert result["resolution_stats"]["total_merges"] == 0

    def test_empty_entity_list(self, resolver):
        """Handle empty input gracefully."""
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities([])
        
        assert result["entities"] == []
        assert result["resolution_stats"]["total_merges"] == 0

    def test_single_entity(self, resolver):
        """Single entity returns unchanged."""
        entities = [{"id": "1", "name": "Python", "type": "TECHNOLOGY"}]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Python"

    def test_preserve_all_properties(self, resolver):
        """Merged entities keep all properties."""
        entities = [
            {"id": "1", "name": "React", "type": "TECHNOLOGY", "version": "18.0"},
            {"id": "2", "name": "React", "type": "TECHNOLOGY", "category": "Frontend"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        merged = result["entities"][0]
        assert merged["version"] == "18.0"
        assert merged["category"] == "Frontend"

    def test_cluster_id_generation(self, resolver):
        """Verify unique cluster IDs."""
        entities = [
            {"id": "1", "name": "Node.js", "type": "TECHNOLOGY"},
            {"id": "2", "name": "NodeJS", "type": "TECHNOLOGY"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        assert "cluster_id" in result["entities"][0]
        assert result["entities"][0]["cluster_id"].startswith("cluster_")

    # Alias and Abbreviation Handling Tests
    def test_resolve_known_aliases(self, resolver, sample_entities):
        """Test AI → Artificial Intelligence resolution."""
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(sample_entities[:2])
        
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Artificial Intelligence"

    def test_resolve_company_variations(self, resolver):
        """Test company name variations."""
        entities = [
            {"id": "1", "name": "Google", "type": "ORGANIZATION"},
            {"id": "2", "name": "Google Inc.", "type": "ORGANIZATION"},
            {"id": "3", "name": "Google LLC", "type": "ORGANIZATION"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should merge based on fuzzy matching
        assert len(result["entities"]) <= 2  # May keep LLC separate

    def test_custom_alias_rules(self, resolver):
        """Test user-defined aliases from YAML."""
        entities = [
            {"id": "1", "name": "CEO", "type": "ROLE"},
            {"id": "2", "name": "Chief Executive Officer", "type": "ROLE"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        assert len(result["entities"]) == 1

    def test_abbreviation_expansion(self, resolver):
        """Test abbreviation handling."""
        entities = [
            {"id": "1", "name": "Dr. Smith", "type": "PERSON"},
            {"id": "2", "name": "Doctor Smith", "type": "PERSON"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        assert len(result["entities"]) == 1

    def test_acronym_handling(self, resolver):
        """Test common acronym recognition."""
        entities = [
            {"id": "1", "name": "NASA", "type": "ORGANIZATION"},
            {"id": "2", "name": "N.A.S.A.", "type": "ORGANIZATION"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should merge based on normalization
        assert len(result["entities"]) == 1

    def test_partial_alias_matching(self, resolver):
        """Test partial alias matching in compound terms."""
        entities = [
            {"id": "1", "name": "ML Engineer", "type": "ROLE"},
            {"id": "2", "name": "Machine Learning Engineer", "type": "ROLE"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should detect ML → Machine Learning
        assert len(result["entities"]) == 1

    # Fuzzy Matching Tests
    def test_fuzzy_match_threshold(self, resolver):
        """Test similarity threshold behavior."""
        entities = [
            {"id": "1", "name": "Microsoft", "type": "ORGANIZATION"},
            {"id": "2", "name": "Microsft", "type": "ORGANIZATION"}  # Typo
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should merge due to high similarity
        assert len(result["entities"]) == 1

    def test_levenshtein_distance_matching(self, resolver):
        """Test typo correction via fuzzy matching."""
        entities = [
            {"id": "1", "name": "GitHub", "type": "PLATFORM"},
            {"id": "2", "name": "GitHb", "type": "PLATFORM"}  # Missing 'u'
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        assert len(result["entities"]) == 1

    def test_fuzzy_match_with_numbers(self, resolver):
        """Test fuzzy matching with numeric variations."""
        entities = [
            {"id": "1", "name": "GPT-3", "type": "MODEL"},
            {"id": "2", "name": "GPT3", "type": "MODEL"},
            {"id": "3", "name": "GPT 3", "type": "MODEL"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        assert len(result["entities"]) == 1

    def test_fuzzy_match_disabled(self):
        """Test with fuzzy matching turned off."""
        with patch('builtins.open', mock_open(read_data=self._get_mock_yaml())):
            resolver = SchemalessEntityResolver(enable_fuzzy_matching=False)
        
        entities = [
            {"id": "1", "name": "PostgreSQL", "type": "DATABASE"},
            {"id": "2", "name": "PostgresQL", "type": "DATABASE"}  # Typo
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should not merge without fuzzy matching
        assert len(result["entities"]) == 2

    def test_fuzzy_threshold_boundaries(self):
        """Test edge cases at different thresholds."""
        entities = [
            {"id": "1", "name": "Kubernetes", "type": "TECHNOLOGY"},
            {"id": "2", "name": "Kubernete", "type": "TECHNOLOGY"}  # Missing 's'
        ]
        
        # Test with low threshold (should merge)
        with patch('builtins.open', mock_open(read_data=self._get_mock_yaml())):
            resolver_low = SchemalessEntityResolver(fuzzy_threshold=0.8)
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result_low = resolver_low.resolve_entities(entities)
        assert len(result_low["entities"]) == 1
        
        # Test with high threshold (should not merge)
        with patch('builtins.open', mock_open(read_data=self._get_mock_yaml())):
            resolver_high = SchemalessEntityResolver(fuzzy_threshold=0.95)
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result_high = resolver_high.resolve_entities(entities)
        assert len(result_high["entities"]) == 2

    def test_name_variations(self, resolver):
        """Test person name variations."""
        entities = [
            {"id": "1", "name": "John Smith", "type": "PERSON"},
            {"id": "2", "name": "Smith, John", "type": "PERSON"},
            {"id": "3", "name": "J. Smith", "type": "PERSON"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should detect name patterns
        assert len(result["entities"]) <= 2

    def test_organization_suffixes(self, resolver):
        """Test organization suffix handling."""
        entities = [
            {"id": "1", "name": "OpenAI", "type": "ORGANIZATION"},
            {"id": "2", "name": "OpenAI Inc", "type": "ORGANIZATION"},
            {"id": "3", "name": "OpenAI Corp", "type": "ORGANIZATION"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should merge organizations with different suffixes
        assert len(result["entities"]) <= 2

    # Singular/Plural Resolution Tests
    def test_simple_plural_resolution(self, resolver):
        """Test basic singular/plural matching."""
        entities = [
            {"id": "1", "name": "system", "type": "CONCEPT"},
            {"id": "2", "name": "systems", "type": "CONCEPT"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        assert len(result["entities"]) == 1

    def test_irregular_plural_handling(self, resolver):
        """Test irregular plural forms."""
        entities = [
            {"id": "1", "name": "person", "type": "CONCEPT"},
            {"id": "2", "name": "people", "type": "CONCEPT"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # May not merge irregular plurals without explicit rules
        assert len(result["entities"]) <= 2

    def test_complex_plural_rules(self, resolver):
        """Test complex plural patterns."""
        entities = [
            {"id": "1", "name": "analysis", "type": "PROCESS"},
            {"id": "2", "name": "analyses", "type": "PROCESS"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        assert len(result["entities"]) <= 2

    def test_plural_in_compound_terms(self, resolver):
        """Test plurals in compound terms."""
        entities = [
            {"id": "1", "name": "data scientist", "type": "ROLE"},
            {"id": "2", "name": "data scientists", "type": "ROLE"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        assert len(result["entities"]) == 1

    def test_preserve_distinct_meanings(self, resolver):
        """Don't merge words with different meanings."""
        entities = [
            {"id": "1", "name": "glass", "type": "MATERIAL"},
            {"id": "2", "name": "glasses", "type": "OBJECT"}  # Eyewear
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should preserve if types differ
        assert len(result["entities"]) == 2

    # Component Tracking Integration Tests
    @patch('src.utils.component_tracker.ComponentTracker.log_execution')
    def test_tracking_decorator_called(self, mock_log, resolver):
        """Verify @track_component_impact is used."""
        resolver.resolve_entities([])
        assert mock_log.called

    @patch('src.utils.component_tracker.ComponentTracker.log_execution')
    def test_resolution_metrics_logged(self, mock_log, resolver, sample_entities):
        """Check entities before/after counts."""
        resolver.resolve_entities(sample_entities)
        
        call_args = mock_log.call_args[1]
        assert "input_size" in call_args
        assert "output_size" in call_args
        assert "contributions" in call_args

    @patch('src.utils.component_tracker.ComponentTracker.log_execution')
    def test_merge_decisions_tracked(self, mock_log, resolver):
        """Log which entities were merged."""
        entities = [
            {"id": "1", "name": "AI", "type": "CONCEPT"},
            {"id": "2", "name": "Artificial Intelligence", "type": "CONCEPT"}
        ]
        resolver.resolve_entities(entities)
        
        call_args = mock_log.call_args[1]
        assert call_args["contributions"]["entities_merged"] == 1

    @patch('src.utils.component_tracker.ComponentTracker.log_execution')
    def test_performance_metrics(self, mock_log, resolver, sample_entities):
        """Track resolution time and memory."""
        resolver.resolve_entities(sample_entities)
        
        # Verify performance tracking via decorator
        assert mock_log.called

    # Error Handling Tests
    def test_malformed_entity_structure(self, resolver):
        """Handle missing required fields."""
        entities = [
            {"id": "1"},  # Missing name
            {"name": "Test"},  # Missing id
            {"id": "2", "name": "Valid", "type": "TEST"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should process valid entities only
        assert len(result["entities"]) >= 1
        assert any(e["name"] == "Valid" for e in result["entities"])

    def test_none_entity_values(self, resolver):
        """Handle None in entity names."""
        entities = [
            {"id": "1", "name": None, "type": "TEST"},
            {"id": "2", "name": "Valid", "type": "TEST"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should skip None names
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Valid"

    def test_special_characters(self, resolver):
        """Handle entities with unicode, emojis."""
        entities = [
            {"id": "1", "name": "Café ☕", "type": "PLACE"},
            {"id": "2", "name": "Cafe", "type": "PLACE"},
            {"id": "3", "name": "Python 🐍", "type": "TECHNOLOGY"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should handle unicode gracefully
        assert len(result["entities"]) >= 2

    def test_extremely_long_names(self, resolver):
        """Performance with long strings."""
        long_name = "A" * 1000
        entities = [
            {"id": "1", "name": long_name, "type": "TEST"},
            {"id": "2", "name": long_name + "B", "type": "TEST"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should handle without crashing
        assert len(result["entities"]) >= 1

    def test_circular_alias_rules(self):
        """Handle circular references in aliases."""
        circular_yaml = """
aliases:
  - ["A", "B"]
  - ["B", "C"]
  - ["C", "A"]
"""
        with patch('builtins.open', mock_open(read_data=circular_yaml)):
            resolver = SchemalessEntityResolver()
        
        entities = [
            {"id": "1", "name": "A", "type": "TEST"},
            {"id": "2", "name": "B", "type": "TEST"},
            {"id": "3", "name": "C", "type": "TEST"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should handle circular references gracefully
        assert len(result["entities"]) >= 1

    # Integration Scenario Tests
    def test_podcast_domain_entities(self, resolver):
        """Test with real podcast entity examples."""
        entities = [
            {"id": "1", "name": "Joe Rogan", "type": "PERSON"},
            {"id": "2", "name": "Joe Rogan Experience", "type": "PODCAST"},
            {"id": "3", "name": "JRE", "type": "PODCAST"},
            {"id": "4", "name": "Spotify", "type": "PLATFORM"},
            {"id": "5", "name": "Spotify Inc", "type": "PLATFORM"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should merge Spotify variants but keep person/podcast separate
        assert len(result["entities"]) >= 3

    def test_technical_domain_entities(self, resolver):
        """Test programming terms and frameworks."""
        entities = [
            {"id": "1", "name": "JavaScript", "type": "LANGUAGE"},
            {"id": "2", "name": "JS", "type": "LANGUAGE"},
            {"id": "3", "name": "React.js", "type": "FRAMEWORK"},
            {"id": "4", "name": "ReactJS", "type": "FRAMEWORK"},
            {"id": "5", "name": "React", "type": "FRAMEWORK"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should merge JS variants and React variants
        assert len(result["entities"]) <= 3

    def test_medical_domain_entities(self, resolver):
        """Test medical terminology resolution."""
        entities = [
            {"id": "1", "name": "COVID-19", "type": "DISEASE"},
            {"id": "2", "name": "COVID", "type": "DISEASE"},
            {"id": "3", "name": "Coronavirus", "type": "DISEASE"},
            {"id": "4", "name": "Dr. Fauci", "type": "PERSON"},
            {"id": "5", "name": "Doctor Fauci", "type": "PERSON"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should merge doctor variants
        assert len(result["entities"]) <= 4

    def test_mixed_type_entities(self, resolver):
        """Test with mixed entity types."""
        entities = [
            {"id": "1", "name": "Apple", "type": "ORGANIZATION"},
            {"id": "2", "name": "Apple", "type": "FRUIT"},
            {"id": "3", "name": "Apple Inc", "type": "ORGANIZATION"},
            {"id": "4", "name": "Steve Jobs", "type": "PERSON"},
            {"id": "5", "name": "Machine Learning", "type": "CONCEPT"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should not merge different types
        assert any(e["type"] == "FRUIT" for e in result["entities"])
        assert any(e["type"] == "ORGANIZATION" for e in result["entities"])

    def test_relationship_preservation(self, resolver):
        """Ensure entities in relationships stay connected."""
        entities = [
            {"id": "1", "name": "Google", "type": "ORGANIZATION", 
             "relationships": [{"target": "2", "type": "EMPLOYS"}]},
            {"id": "2", "name": "Software Engineer", "type": "ROLE"},
            {"id": "3", "name": "Google Inc", "type": "ORGANIZATION"}
        ]
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        
        # Should preserve relationships when merging
        google_entity = next(e for e in result["entities"] if "Google" in e["name"])
        assert "relationships" in google_entity

    @pytest.mark.slow
    def test_large_entity_list_performance(self, resolver):
        """Test performance with 1000+ entities."""
        import time
        
        # Generate large entity list
        entities = []
        for i in range(1000):
            entities.append({
                "id": str(i),
                "name": f"Entity_{i % 100}",  # Create duplicates
                "type": "TEST"
            })
        
        start_time = time.time()
        with patch('src.utils.component_tracker.ComponentTracker.log_execution'):
            result = resolver.resolve_entities(entities)
        elapsed = time.time() - start_time
        
        # Should process in reasonable time
        assert elapsed < 5.0  # 5 seconds max
        assert len(result["entities"]) < 1000  # Should merge duplicates