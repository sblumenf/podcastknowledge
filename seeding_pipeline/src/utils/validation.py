"""Validation utilities for data integrity and input sanitization."""

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Tuple
import logging
import re

from src.utils.text_processing import normalize_entity_name, calculate_name_similarity
logger = logging.getLogger(__name__)


def validate_text_input(text: Any, field_name: str = "text") -> str:
    """Validate text input is not None or empty.
    
    Args:
        text: Input text to validate
        field_name: Name of the field for logging
        
    Returns:
        Validated and cleaned text string
    """
    if text is None:
        logger.warning(f"{field_name} is None, using empty string")
        return ""
    if not isinstance(text, str):
        logger.warning(f"{field_name} is not string, converting: {type(text)}")
        return str(text)
    return text.strip()


def validate_date_format(date_str: Optional[str]) -> str:
    """Validate and normalize date format with fallbacks.
    
    Args:
        date_str: Date string to validate
        
    Returns:
        ISO format date string
    """
    if not date_str:
        return datetime.now().isoformat()
    
    try:
        # Try parsing with dateutil if available
        from dateutil.parser import parse as date_parse
        parsed = date_parse(date_str)
        return parsed.isoformat()
    except ImportError:
        logger.debug("dateutil not available, trying manual parsing")
    except Exception as e:
        logger.warning(f"Failed to parse date with dateutil: {e}")
    
    # Manual parsing fallbacks
    date_formats = [
        '%Y-%m-%d',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%Y%m%d'
    ]
    
    for fmt in date_formats:
        try:
            parsed = datetime.strptime(date_str.strip(), fmt)
            return parsed.isoformat()
        except ValueError:
            continue
    
    # If all else fails, return current datetime
    logger.warning(f"Could not parse date '{date_str}', using current time")
    return datetime.now().isoformat()


def sanitize_file_path(path: str) -> str:
    """Sanitize file paths to prevent injection attacks.
    
    Args:
        path: File path to sanitize
        
    Returns:
        Sanitized file path
    """
    # Convert to string and remove potentially dangerous characters
    # Use ASCII-only word characters to prevent unicode issues
    safe_path = re.sub(r'[^a-zA-Z0-9\s\-_.\/]', '', str(path))
    
    # Remove double dots to prevent directory traversal
    safe_path = safe_path.replace('..', '')
    
    # Remove leading slashes to prevent absolute paths
    safe_path = safe_path.lstrip('/')
    
    # Normalize path separators - replace multiple slashes with single slash
    while '//' in safe_path:
        safe_path = safe_path.replace('//', '/')
    
    return safe_path




class DataValidator:
    """Comprehensive data validation for pipeline outputs."""
    
    def __init__(self, 
                 max_entities_per_segment: int = 50,
                 confidence_threshold: int = 3,
                 min_insight_length: int = 20,
                 min_quote_length: int = 10):
        """Initialize validator with configurable thresholds.
        
        Args:
            max_entities_per_segment: Maximum entities allowed per segment
            confidence_threshold: Minimum confidence for entities
            min_insight_length: Minimum description length for insights
            min_quote_length: Minimum length for quotes
        """
        self.max_entities_per_segment = max_entities_per_segment
        self.confidence_threshold = confidence_threshold
        self.min_insight_length = min_insight_length
        self.min_quote_length = min_quote_length
        self.validation_stats = defaultdict(int)
    
    def validate_entities(self, 
                         entities: List[Dict[str, Any]], 
                         segment_text: Optional[str] = None) -> List[Dict[str, Any]]:
        """Validate and deduplicate entities.
        
        Args:
            entities: List of entity dictionaries
            segment_text: Optional segment text for context
            
        Returns:
            Validated and deduplicated entities
        """
        if not entities:
            return []
        
        # Deduplicate by normalized name
        seen_names = {}
        validated = []
        
        for entity in entities:
            # Skip if not a dictionary
            if not isinstance(entity, dict):
                self.validation_stats['missing_fields'] += 1
                continue
                
            # Validate required fields (support both 'value' and 'name' for compatibility)
            entity_value = entity.get('value', entity.get('name'))
            if not entity_value or not entity.get('type'):
                self.validation_stats['missing_fields'] += 1
                continue
            
            # Normalize name
            name = validate_text_input(entity_value)
            normalized_name = normalize_entity_name(name)
            entity_type = entity.get('type', 'UNKNOWN').upper()
            
            # Skip if name too short
            if len(name) < 2:
                self.validation_stats['name_too_short'] += 1
                continue
            
            # Check for duplicates
            key = f"{normalized_name}:{entity_type}"
            if key in seen_names:
                # Merge with existing entity
                existing = seen_names[key]
                existing['confidence'] = max(
                    existing.get('confidence', 1),
                    entity.get('confidence', 1)
                )
                self.validation_stats['duplicates_merged'] += 1
                continue
            
            # Validate confidence threshold
            # Default confidence to threshold if not specified (assume valid)
            confidence = entity.get('confidence', self.confidence_threshold)
            if confidence < self.confidence_threshold:
                self.validation_stats['low_confidence'] += 1
                # Don't skip, just log
            
            # Build validated entity
            validated_entity = {
                'value': name,  # Use 'value' as the standard field name
                'normalized_name': normalized_name,
                'type': entity_type,
                'confidence': confidence,
                'importance': entity.get('importance', 5)
            }
            
            # Add optional fields if present
            if entity.get('description'):
                validated_entity['description'] = validate_text_input(
                    entity['description'], 'entity_description'
                )
            
            seen_names[key] = validated_entity
            validated.append(validated_entity)
        
        # Sort by importance and limit if needed
        if len(validated) > self.max_entities_per_segment:
            validated.sort(key=lambda x: x.get('importance', 5), reverse=True)
            validated = validated[:self.max_entities_per_segment]
            self.validation_stats['entities_truncated'] += 1
        
        return validated
    
    def validate_insights(self, insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate insights meet quality standards.
        
        Args:
            insights: List of insight dictionaries
            
        Returns:
            Validated insights
        """
        if not insights:
            return []
        
        validated = []
        seen_titles = set()
        
        for insight in insights:
            # Check required fields
            if not insight.get('title') or not insight.get('description'):
                self.validation_stats['insight_missing_fields'] += 1
                continue
            
            # Validate text fields
            title = validate_text_input(insight['title'], 'insight_title')
            description = validate_text_input(insight['description'], 'insight_description')
            
            # Check minimum lengths
            if len(description) < self.min_insight_length:
                self.validation_stats['insight_too_short'] += 1
                continue
            
            # Check for duplicate titles
            title_lower = title.lower()
            if title_lower in seen_titles:
                self.validation_stats['duplicate_insights'] += 1
                continue
            
            # Validate insight type
            valid_types = ['observation', 'trend', 'fact', 'opinion', 'prediction', 'analysis']
            insight_type = insight.get('insight_type', 'observation').lower()
            if insight_type not in valid_types:
                insight_type = 'observation'
            
            # Build validated insight
            validated_insight = {
                'title': title,
                'description': description,
                'insight_type': insight_type,
                'confidence': insight.get('confidence', 0.8),
                'importance': insight.get('importance', 5)
            }
            
            # Add optional fields
            if insight.get('supporting_evidence'):
                validated_insight['supporting_evidence'] = validate_text_input(
                    insight['supporting_evidence'], 'supporting_evidence'
                )
            
            if insight.get('entities'):
                validated_insight['entities'] = [
                    e for e in insight['entities'] if isinstance(e, str) and e.strip()
                ]
            
            seen_titles.add(title_lower)
            validated.append(validated_insight)
        
        return validated
    
    def validate_quotes(self, quotes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate quotes for quality and completeness.
        
        Args:
            quotes: List of quote dictionaries
            
        Returns:
            Validated quotes
        """
        if not quotes:
            return []
        
        validated = []
        seen_quotes = set()
        
        for quote in quotes:
            # Check required fields
            if not quote.get('text') or not quote.get('speaker'):
                self.validation_stats['quote_missing_fields'] += 1
                continue
            
            # Validate text fields
            text = validate_text_input(quote['text'], 'quote_text')
            speaker = validate_text_input(quote['speaker'], 'quote_speaker')
            
            # Check minimum length
            if len(text) < self.min_quote_length:
                self.validation_stats['quote_too_short'] += 1
                continue
            
            # Check for duplicates (normalized)
            text_normalized = ' '.join(text.lower().split())
            if text_normalized in seen_quotes:
                self.validation_stats['duplicate_quotes'] += 1
                continue
            
            # Build validated quote
            validated_quote = {
                'text': text,
                'speaker': speaker,
                'context': quote.get('context', ''),
                'importance': quote.get('importance', 5),
                'timestamp': quote.get('timestamp')
            }
            
            seen_quotes.add(text_normalized)
            validated.append(validated_quote)
        
        return validated
    
    def validate_metrics(self, metrics_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure all metrics are within valid ranges.
        
        Args:
            metrics_dict: Dictionary of metrics to validate
            
        Returns:
            Validated metrics dictionary
        """
        validated = metrics_dict.copy()
        
        # Validate score ranges (0-100)
        score_fields = [
            'complexity_score', 'information_score', 'accessibility_score',
            'quotability_score', 'best_of_score', 'avg_complexity',
            'avg_information_score', 'avg_accessibility'
        ]
        
        for field in score_fields:
            if field in validated:
                value = validated[field]
                if isinstance(value, (int, float)):
                    validated[field] = max(0, min(100, value))
                else:
                    validated[field] = 50  # Default middle value
        
        # Validate counts (non-negative integers)
        count_fields = [
            'word_count', 'sentence_count', 'unique_words',
            'entity_count', 'fact_count', 'quote_count',
            'best_of_count'
        ]
        
        for field in count_fields:
            if field in validated:
                value = validated[field]
                if isinstance(value, (int, float)):
                    validated[field] = max(0, int(value))
                else:
                    validated[field] = 0
        
        # Validate ratios (0-1)
        ratio_fields = ['information_density', 'entity_density']
        
        for field in ratio_fields:
            if field in validated:
                value = validated[field]
                if isinstance(value, (int, float)):
                    validated[field] = max(0.0, min(1.0, value))
                else:
                    validated[field] = 0.0
        
        return validated
    
    def get_validation_report(self) -> Dict[str, int]:
        """Get validation statistics report.
        
        Returns:
            Dictionary of validation statistics
        """
        return dict(self.validation_stats)


def validate_and_enhance_insights(insights: List[Dict[str, Any]], 
                                 use_large_context: bool = True) -> List[Dict[str, Any]]:
    """Validate and enhance the extracted insights.
    
    Args:
        insights: List of raw insights
        use_large_context: Whether using large context model
        
    Returns:
        Validated and enhanced insights
    """
    validator = DataValidator()
    validated_insights = validator.validate_insights(insights)
    
    # Log validation results
    report = validator.get_validation_report()
    if report:
        logger.info(f"Insight validation report: {report}")
    
    return validated_insights


def is_valid_url(url: str) -> bool:
    """Check if a string is a valid URL.
    
    Args:
        url: URL string to validate
        
    Returns:
        True if valid URL, False otherwise
    """
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(url_pattern.match(url))


def is_valid_email(email: str) -> bool:
    """Check if a string is a valid email address.
    
    Args:
        email: Email string to validate
        
    Returns:
        True if valid email, False otherwise
    """
    email_pattern = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*\.[a-zA-Z]{2,}$'
    )
    
    return bool(email_pattern.match(email))