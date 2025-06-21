"""Simple validation functions for data structures.

This module provides lightweight validation for the knowledge extraction
pipeline data structures. Following KISS principles, we only check for
required fields and basic validity.
"""

from typing import Dict, Any, Tuple, List
import logging

logger = logging.getLogger(__name__)


def validate_entity(entity: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate entity data structure.
    
    Args:
        entity: Entity dictionary to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        If valid, error_message is empty string
    """
    if not isinstance(entity, dict):
        return False, "Entity must be a dictionary"
    
    # Check required fields
    if 'value' not in entity:
        return False, "Entity missing required field: 'value'"
    
    if 'type' not in entity:
        return False, "Entity missing required field: 'type'"
    
    # Validate field content
    if not entity['value'] or not str(entity['value']).strip():
        return False, "Entity 'value' cannot be empty"
    
    if not entity['type'] or not str(entity['type']).strip():
        return False, "Entity 'type' cannot be empty"
    
    return True, ""


def validate_quote(quote: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate quote data structure.
    
    Args:
        quote: Quote dictionary to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(quote, dict):
        return False, "Quote must be a dictionary"
    
    # Check required field
    if 'text' not in quote:
        return False, "Quote missing required field: 'text'"
    
    # Validate field content
    if not quote['text'] or not str(quote['text']).strip():
        return False, "Quote 'text' cannot be empty"
    
    return True, ""


def validate_insight(insight: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate insight data structure.
    
    Args:
        insight: Insight dictionary to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(insight, dict):
        return False, "Insight must be a dictionary"
    
    # Check required fields
    if 'title' not in insight:
        return False, "Insight missing required field: 'title'"
    
    if 'description' not in insight:
        return False, "Insight missing required field: 'description'"
    
    # Validate field content
    if not insight['title'] or not str(insight['title']).strip():
        return False, "Insight 'title' cannot be empty"
    
    if not insight['description'] or not str(insight['description']).strip():
        return False, "Insight 'description' cannot be empty"
    
    return True, ""


def validate_relationship(relationship: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate relationship data structure.
    
    Args:
        relationship: Relationship dictionary to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(relationship, dict):
        return False, "Relationship must be a dictionary"
    
    # Check required fields
    if 'source' not in relationship:
        return False, "Relationship missing required field: 'source'"
    
    if 'target' not in relationship:
        return False, "Relationship missing required field: 'target'"
    
    if 'type' not in relationship:
        return False, "Relationship missing required field: 'type'"
    
    # Validate field content
    if not relationship['source'] or not str(relationship['source']).strip():
        return False, "Relationship 'source' cannot be empty"
    
    if not relationship['target'] or not str(relationship['target']).strip():
        return False, "Relationship 'target' cannot be empty"
    
    if not relationship['type'] or not str(relationship['type']).strip():
        return False, "Relationship 'type' cannot be empty"
    
    return True, ""


def validate_extraction_result(result: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate complete extraction result.
    
    Args:
        result: Extraction result dictionary to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(result, dict):
        return False, "Extraction result must be a dictionary"
    
    # Check required top-level fields
    required_fields = ['entities', 'quotes', 'insights', 'relationships']
    for field in required_fields:
        if field not in result:
            return False, f"Extraction result missing required field: '{field}'"
        
        if not isinstance(result[field], list):
            return False, f"Extraction result field '{field}' must be a list"
    
    return True, ""


def normalize_entity_fields(entity: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize entity fields during transition period.
    
    Maps 'name' to 'value' if needed to support legacy code.
    
    Args:
        entity: Entity dictionary to normalize
        
    Returns:
        Normalized entity dictionary
    """
    if 'name' in entity and 'value' not in entity:
        entity['value'] = entity['name']
        del entity['name']
        logger.debug("Normalized entity field: 'name' -> 'value'")
    
    return entity


def normalize_insight_for_storage(insight: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize insight fields for storage.
    
    Maps 'title' and 'description' to 'text' as expected by storage layer.
    
    Args:
        insight: Insight dictionary to normalize
        
    Returns:
        Normalized insight dictionary for storage
    """
    # Create a copy to avoid modifying the original
    storage_insight = insight.copy()
    
    # If insight has title and description but no text, create text field
    if 'title' in insight and 'description' in insight and 'text' not in insight:
        # Combine title and description into text
        storage_insight['text'] = f"{insight['title']}: {insight['description']}"
        logger.debug("Created insight 'text' field from title and description")
    
    return storage_insight


def validate_and_filter_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and filter a list of entities.
    
    Args:
        entities: List of entity dictionaries
        
    Returns:
        List of valid entities (invalid ones are filtered out)
    """
    valid_entities = []
    
    for i, entity in enumerate(entities):
        # Normalize first
        entity = normalize_entity_fields(entity)
        
        # Then validate
        is_valid, error_msg = validate_entity(entity)
        if is_valid:
            valid_entities.append(entity)
        else:
            logger.warning(f"Invalid entity at index {i} skipped: {error_msg}")
    
    return valid_entities


def validate_and_filter_quotes(quotes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and filter a list of quotes.
    
    Args:
        quotes: List of quote dictionaries
        
    Returns:
        List of valid quotes (invalid ones are filtered out)
    """
    valid_quotes = []
    
    for i, quote in enumerate(quotes):
        is_valid, error_msg = validate_quote(quote)
        if is_valid:
            valid_quotes.append(quote)
        else:
            logger.warning(f"Invalid quote at index {i} skipped: {error_msg}")
    
    return valid_quotes


def validate_and_filter_insights(insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and filter a list of insights.
    
    Args:
        insights: List of insight dictionaries
        
    Returns:
        List of valid insights (invalid ones are filtered out)
    """
    valid_insights = []
    
    for i, insight in enumerate(insights):
        is_valid, error_msg = validate_insight(insight)
        if is_valid:
            valid_insights.append(insight)
        else:
            logger.warning(f"Invalid insight at index {i} skipped: {error_msg}")
    
    return valid_insights


def validate_and_filter_relationships(relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and filter a list of relationships.
    
    Args:
        relationships: List of relationship dictionaries
        
    Returns:
        List of valid relationships (invalid ones are filtered out)
    """
    valid_relationships = []
    
    for i, relationship in enumerate(relationships):
        is_valid, error_msg = validate_relationship(relationship)
        if is_valid:
            valid_relationships.append(relationship)
        else:
            logger.warning(f"Invalid relationship at index {i} skipped: {error_msg}")
    
    return valid_relationships