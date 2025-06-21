"""Unit tests for field consistency validation.

These tests ensure that all data structures use the correct field names
and that validation functions work as expected.
"""

import pytest
from src.core.validation import (
    validate_entity,
    validate_quote,
    validate_insight,
    validate_relationship,
    normalize_entity_fields,
    normalize_insight_for_storage,
    validate_and_filter_entities,
    validate_and_filter_quotes,
    validate_and_filter_insights,
    validate_and_filter_relationships
)


class TestEntityValidation:
    """Test entity field validation and normalization."""
    
    def test_valid_entity(self):
        """Test validation of a correctly structured entity."""
        entity = {
            'value': 'Elon Musk',
            'type': 'PERSON',
            'confidence': 0.95
        }
        is_valid, error = validate_entity(entity)
        assert is_valid is True
        assert error == ""
    
    def test_entity_missing_value_field(self):
        """Test validation fails when entity missing 'value' field."""
        entity = {
            'type': 'PERSON',
            'confidence': 0.95
        }
        is_valid, error = validate_entity(entity)
        assert is_valid is False
        assert "missing required field: 'value'" in error
    
    def test_entity_missing_type_field(self):
        """Test validation fails when entity missing 'type' field."""
        entity = {
            'value': 'Elon Musk',
            'confidence': 0.95
        }
        is_valid, error = validate_entity(entity)
        assert is_valid is False
        assert "missing required field: 'type'" in error
    
    def test_entity_empty_value(self):
        """Test validation fails when entity value is empty."""
        entity = {
            'value': '',
            'type': 'PERSON'
        }
        is_valid, error = validate_entity(entity)
        assert is_valid is False
        assert "'value' cannot be empty" in error
    
    def test_entity_empty_type(self):
        """Test validation fails when entity type is empty."""
        entity = {
            'value': 'Elon Musk',
            'type': ''
        }
        is_valid, error = validate_entity(entity)
        assert is_valid is False
        assert "'type' cannot be empty" in error
    
    def test_normalize_entity_name_to_value(self):
        """Test normalization of 'name' field to 'value'."""
        entity = {
            'name': 'Elon Musk',
            'type': 'PERSON'
        }
        normalized = normalize_entity_fields(entity)
        assert 'value' in normalized
        assert normalized['value'] == 'Elon Musk'
        assert 'name' not in normalized
    
    def test_normalize_entity_already_has_value(self):
        """Test normalization when entity already has 'value' field."""
        entity = {
            'value': 'Elon Musk',
            'type': 'PERSON'
        }
        normalized = normalize_entity_fields(entity)
        assert normalized['value'] == 'Elon Musk'
    
    def test_validate_and_filter_entities(self):
        """Test batch validation and filtering of entities."""
        entities = [
            {'value': 'Valid Entity', 'type': 'PERSON'},
            {'name': 'Needs Normalization', 'type': 'ORGANIZATION'},
            {'type': 'INVALID'},  # Missing value
            {'value': '', 'type': 'EMPTY'},  # Empty value
            {'value': 'Another Valid', 'type': 'TECHNOLOGY'}
        ]
        
        valid_entities = validate_and_filter_entities(entities)
        assert len(valid_entities) == 3
        assert valid_entities[0]['value'] == 'Valid Entity'
        assert valid_entities[1]['value'] == 'Needs Normalization'
        assert valid_entities[2]['value'] == 'Another Valid'


class TestQuoteValidation:
    """Test quote field validation."""
    
    def test_valid_quote(self):
        """Test validation of a correctly structured quote."""
        quote = {
            'text': 'The future is going to be wild.',
            'speaker': 'Elon Musk',
            'importance': 0.8
        }
        is_valid, error = validate_quote(quote)
        assert is_valid is True
        assert error == ""
    
    def test_quote_missing_text_field(self):
        """Test validation fails when quote missing 'text' field."""
        quote = {
            'speaker': 'Elon Musk',
            'importance': 0.8
        }
        is_valid, error = validate_quote(quote)
        assert is_valid is False
        assert "missing required field: 'text'" in error
    
    def test_quote_empty_text(self):
        """Test validation fails when quote text is empty."""
        quote = {
            'text': '',
            'speaker': 'Elon Musk'
        }
        is_valid, error = validate_quote(quote)
        assert is_valid is False
        assert "'text' cannot be empty" in error


class TestInsightValidation:
    """Test insight field validation."""
    
    def test_valid_insight(self):
        """Test validation of a correctly structured insight."""
        insight = {
            'title': 'AI Revolution',
            'description': 'Artificial intelligence will transform society',
            'type': 'conceptual'
        }
        is_valid, error = validate_insight(insight)
        assert is_valid is True
        assert error == ""
    
    def test_insight_missing_title(self):
        """Test validation fails when insight missing 'title' field."""
        insight = {
            'description': 'Artificial intelligence will transform society',
            'type': 'conceptual'
        }
        is_valid, error = validate_insight(insight)
        assert is_valid is False
        assert "missing required field: 'title'" in error
    
    def test_insight_missing_description(self):
        """Test validation fails when insight missing 'description' field."""
        insight = {
            'title': 'AI Revolution',
            'type': 'conceptual'
        }
        is_valid, error = validate_insight(insight)
        assert is_valid is False
        assert "missing required field: 'description'" in error
    
    def test_normalize_insight_for_storage(self):
        """Test normalization of insight for storage layer."""
        insight = {
            'title': 'AI Revolution',
            'description': 'Artificial intelligence will transform society',
            'type': 'conceptual'
        }
        storage_insight = normalize_insight_for_storage(insight)
        assert 'text' in storage_insight
        assert storage_insight['text'] == 'AI Revolution: Artificial intelligence will transform society'
        # Original fields should still be present
        assert storage_insight['title'] == 'AI Revolution'
        assert storage_insight['description'] == 'Artificial intelligence will transform society'


class TestRelationshipValidation:
    """Test relationship field validation."""
    
    def test_valid_relationship(self):
        """Test validation of a correctly structured relationship."""
        relationship = {
            'source': 'Elon Musk',
            'target': 'Tesla',
            'type': 'FOUNDED',
            'confidence': 0.9
        }
        is_valid, error = validate_relationship(relationship)
        assert is_valid is True
        assert error == ""
    
    def test_relationship_missing_source(self):
        """Test validation fails when relationship missing 'source' field."""
        relationship = {
            'target': 'Tesla',
            'type': 'FOUNDED'
        }
        is_valid, error = validate_relationship(relationship)
        assert is_valid is False
        assert "missing required field: 'source'" in error
    
    def test_relationship_missing_target(self):
        """Test validation fails when relationship missing 'target' field."""
        relationship = {
            'source': 'Elon Musk',
            'type': 'FOUNDED'
        }
        is_valid, error = validate_relationship(relationship)
        assert is_valid is False
        assert "missing required field: 'target'" in error
    
    def test_relationship_missing_type(self):
        """Test validation fails when relationship missing 'type' field."""
        relationship = {
            'source': 'Elon Musk',
            'target': 'Tesla'
        }
        is_valid, error = validate_relationship(relationship)
        assert is_valid is False
        assert "missing required field: 'type'" in error


class TestFieldConsistencyRegression:
    """Tests to prevent regression of field naming issues."""
    
    def test_entity_uses_value_not_name(self):
        """Ensure entities use 'value' field, not 'name'."""
        # This would have been the old way
        old_entity = {'name': 'Test', 'type': 'PERSON'}
        
        # Normalize should fix it
        normalized = normalize_entity_fields(old_entity)
        assert 'value' in normalized
        assert 'name' not in normalized
        
        # Validation should pass after normalization
        is_valid, _ = validate_entity(normalized)
        assert is_valid is True
    
    def test_quote_uses_text_not_value(self):
        """Ensure quotes use 'text' field, not 'value'."""
        # Correct way
        quote = {'text': 'Test quote', 'speaker': 'Someone'}
        is_valid, _ = validate_quote(quote)
        assert is_valid is True
        
        # Wrong way (should fail)
        wrong_quote = {'value': 'Test quote', 'speaker': 'Someone'}
        is_valid, error = validate_quote(wrong_quote)
        assert is_valid is False
        assert 'text' in error
    
    def test_insight_normalization_for_storage(self):
        """Ensure insights are normalized for storage with 'text' field."""
        # Extraction creates this format
        insight = {
            'title': 'Test Insight',
            'description': 'This is a test insight description'
        }
        
        # Storage needs 'text' field
        storage_insight = normalize_insight_for_storage(insight)
        assert 'text' in storage_insight
        assert 'Test Insight: This is a test insight description' == storage_insight['text']