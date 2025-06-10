"""Response parsing utilities for LLM outputs."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Tuple
import json
import logging
import re

from src.core.models import (
    Entity, Insight, Quote, EntityType, InsightType, QuoteType
)
from src.core.exceptions import ParsingError


logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result of parsing operation."""
    success: bool
    data: Any
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
            

class ResponseParser:
    """Parser for various types of LLM responses."""
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize response parser.
        
        Args:
            strict_mode: If True, fail on any parsing errors
        """
        self.strict_mode = strict_mode
        
    def parse_json_response(
        self,
        response: str,
        expected_type: type = list
    ) -> ParseResult:
        """
        Parse JSON from LLM response.
        
        Args:
            response: Raw LLM response
            expected_type: Expected type of parsed data (list or dict)
            
        Returns:
            ParseResult with parsed data
        """
        errors = []
        warnings = []
        
        # Try to extract JSON from response
        json_str = self._extract_json_string(response)
        
        if not json_str:
            errors.append("No valid JSON found in response")
            return ParseResult(success=False, data=None, errors=errors)
            
        try:
            data = json.loads(json_str)
            
            # Check if data matches expected type
            if not isinstance(data, expected_type):
                if expected_type == list and isinstance(data, dict):
                    # Convert single dict to list
                    data = [data]
                    warnings.append("Converted single object to list")
                else:
                    errors.append(f"Expected {expected_type.__name__}, got {type(data).__name__}")
                    return ParseResult(success=False, data=None, errors=errors)
                    
            return ParseResult(
                success=True,
                data=data,
                warnings=warnings
            )
            
        except json.JSONDecodeError as e:
            errors.append(f"JSON decode error: {e}")
            
            # Try to fix common issues
            fixed_json = self._fix_common_json_errors(json_str)
            if fixed_json != json_str:
                try:
                    data = json.loads(fixed_json)
                    warnings.append("Fixed JSON formatting issues")
                    return ParseResult(
                        success=True,
                        data=data,
                        warnings=warnings
                    )
                except:
                    pass
                    
            return ParseResult(success=False, data=None, errors=errors)
            
    def parse_entities(self, response: str) -> ParseResult:
        """Parse entity extraction response."""
        # First parse as JSON
        json_result = self.parse_json_response(response, list)
        
        if not json_result.success:
            return json_result
            
        entities = []
        errors = json_result.errors
        warnings = json_result.warnings
        
        for idx, item in enumerate(json_result.data):
            try:
                entity = self._parse_entity_item(item, idx)
                entities.append(entity)
            except Exception as e:
                error_msg = f"Failed to parse entity {idx}: {e}"
                if self.strict_mode:
                    errors.append(error_msg)
                    return ParseResult(success=False, data=None, errors=errors)
                else:
                    warnings.append(error_msg)
                    
        return ParseResult(
            success=len(entities) > 0,
            data=entities,
            errors=errors,
            warnings=warnings
        )
        
    def parse_insights(self, response: str) -> ParseResult:
        """Parse insight extraction response."""
        # First parse as JSON
        json_result = self.parse_json_response(response, list)
        
        if not json_result.success:
            return json_result
            
        insights = []
        errors = json_result.errors
        warnings = json_result.warnings
        
        for idx, item in enumerate(json_result.data):
            try:
                insight = self._parse_insight_item(item, idx)
                insights.append(insight)
            except Exception as e:
                error_msg = f"Failed to parse insight {idx}: {e}"
                if self.strict_mode:
                    errors.append(error_msg)
                    return ParseResult(success=False, data=None, errors=errors)
                else:
                    warnings.append(error_msg)
                    
        return ParseResult(
            success=len(insights) > 0,
            data=insights,
            errors=errors,
            warnings=warnings
        )
        
    def parse_quotes(self, response: str) -> ParseResult:
        """Parse quote extraction response."""
        # First parse as JSON
        json_result = self.parse_json_response(response, list)
        
        if not json_result.success:
            return json_result
            
        quotes = []
        errors = json_result.errors
        warnings = json_result.warnings
        
        for idx, item in enumerate(json_result.data):
            try:
                quote = self._parse_quote_item(item, idx)
                quotes.append(quote)
            except Exception as e:
                error_msg = f"Failed to parse quote {idx}: {e}"
                if self.strict_mode:
                    errors.append(error_msg)
                    return ParseResult(success=False, data=None, errors=errors)
                else:
                    warnings.append(error_msg)
                    
        return ParseResult(
            success=len(quotes) > 0,
            data=quotes,
            errors=errors,
            warnings=warnings
        )
        
    def parse_complexity(self, response: str) -> ParseResult:
        """Parse complexity analysis response."""
        json_result = self.parse_json_response(response, dict)
        
        if not json_result.success:
            return json_result
            
        data = json_result.data
        
        # Validate required fields
        required = ['classification', 'technical_density']
        missing = [f for f in required if f not in data]
        
        if missing:
            json_result.errors.append(f"Missing required fields: {missing}")
            return ParseResult(
                success=False,
                data=None,
                errors=json_result.errors
            )
            
        # Normalize values
        data['classification'] = data['classification'].lower()
        data['technical_density'] = float(data['technical_density'])
        
        # Validate ranges
        if data['technical_density'] < 0 or data['technical_density'] > 1:
            json_result.warnings.append(
                f"Technical density {data['technical_density']} outside 0-1 range, clamping"
            )
            data['technical_density'] = max(0.0, min(1.0, data['technical_density']))
            
        return ParseResult(
            success=True,
            data=data,
            warnings=json_result.warnings
        )
        
    def parse_information_density(self, response: str) -> ParseResult:
        """Parse information density analysis response."""
        json_result = self.parse_json_response(response, dict)
        
        if not json_result.success:
            return json_result
            
        data = json_result.data
        
        # Validate required fields
        if 'density' not in data:
            json_result.errors.append("Missing required field: density")
            return ParseResult(
                success=False,
                data=None,
                errors=json_result.errors
            )
            
        # Normalize density value
        data['density'] = float(data['density'])
        
        # Validate range
        if data['density'] < 0 or data['density'] > 1:
            json_result.warnings.append(
                f"Density {data['density']} outside 0-1 range, clamping"
            )
            data['density'] = max(0.0, min(1.0, data['density']))
            
        # Add optional fields with defaults
        data.setdefault('concept_count', 0)
        data.setdefault('explanation', '')
        
        return ParseResult(
            success=True,
            data=data,
            warnings=json_result.warnings
        )
        
    def parse_sentiment(self, response: str) -> ParseResult:
        """Parse sentiment analysis response."""
        json_result = self.parse_json_response(response, dict)
        
        if not json_result.success:
            return json_result
            
        data = json_result.data
        
        # Validate required fields
        required = ['overall_sentiment', 'score']
        missing = [f for f in required if f not in data]
        
        if missing:
            json_result.errors.append(f"Missing required fields: {missing}")
            return ParseResult(
                success=False,
                data=None,
                errors=json_result.errors
            )
            
        # Normalize sentiment
        data['overall_sentiment'] = data['overall_sentiment'].lower()
        data['score'] = float(data['score'])
        
        # Validate score range
        if data['score'] < -1 or data['score'] > 1:
            json_result.warnings.append(
                f"Sentiment score {data['score']} outside -1 to 1 range, clamping"
            )
            data['score'] = max(-1.0, min(1.0, data['score']))
            
        # Add optional fields with defaults
        data.setdefault('emotions', [])
        data.setdefault('explanation', '')
        
        return ParseResult(
            success=True,
            data=data,
            warnings=json_result.warnings
        )
        
    # Helper methods
    
    def _extract_json_string(self, response: str) -> Optional[str]:
        """Extract JSON string from LLM response."""
        # Remove markdown code blocks
        response = re.sub(r'```json\s*', '', response)
        response = re.sub(r'```\s*', '', response)
        
        # Try to find the first complete JSON structure
        # Look for the first { or [ and try to find its matching } or ]
        for start_match in re.finditer(r'[\[\{]', response):
            start_pos = start_match.start()
            start_char = start_match.group()
            end_char = ']' if start_char == '[' else '}'
            
            # Simple bracket counting to find the matching end
            count = 1
            pos = start_pos + 1
            in_string = False
            escape_next = False
            
            while pos < len(response) and count > 0:
                char = response[pos]
                
                if escape_next:
                    escape_next = False
                elif char == '\\':
                    escape_next = True
                elif char == '"' and not escape_next:
                    in_string = not in_string
                elif not in_string:
                    if char == start_char:
                        count += 1
                    elif char == end_char:
                        count -= 1
                
                pos += 1
            
            if count == 0:
                # Found matching bracket
                json_str = response[start_pos:pos]
                try:
                    # Validate it's actual JSON
                    json.loads(json_str)
                    return json_str
                except json.JSONDecodeError:
                    # Keep looking
                    continue
        
        # If no valid JSON found, try the old cleaning approach
        lines = response.strip().split('\n')
        json_lines = []
        
        for line in lines:
            # Skip obvious non-JSON lines
            if line.strip() and not line.strip().startswith(('The', 'Here', 'This', '#', '//')):
                json_lines.append(line)
                
        if json_lines:
            cleaned = '\n'.join(json_lines)
            # Try to parse to validate
            try:
                json.loads(cleaned)
                return cleaned
            except json.JSONDecodeError:
                pass
            
        return None
        
    def _fix_common_json_errors(self, json_str: str) -> str:
        """Fix common JSON formatting errors."""
        # Fix trailing commas
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # Fix single quotes (convert to double quotes)
        # This is tricky - need to avoid replacing quotes inside strings
        # Simple approach: if it's clearly JSON-like
        if "'" in json_str and '"' not in json_str:
            json_str = json_str.replace("'", '"')
            
        # Fix missing quotes around keys
        json_str = re.sub(r'(\w+):', r'"\1":', json_str)
        
        # Fix Python None, True, False
        json_str = json_str.replace('None', 'null')
        json_str = json_str.replace('True', 'true')
        json_str = json_str.replace('False', 'false')
        
        return json_str
        
    def _parse_entity_item(self, item: Dict[str, Any], idx: int) -> Entity:
        """Parse a single entity item."""
        # Required fields
        name = item.get('name')
        if not name:
            raise ValueError("Entity missing required field: name")
            
        # Map entity type
        entity_type = self._map_entity_type(item.get('type', 'OTHER'))
        
        # Create entity
        entity = Entity(
            id=f"entity_{idx}_{name.lower().replace(' ', '_')}_{datetime.now().timestamp()}",
            name=name,
            entity_type=entity_type,
            description=item.get('description', ''),
            first_mentioned=None,  # Will be set later
            mention_count=item.get('frequency', 1),
            bridge_score=item.get('importance', 5) / 10.0 if 'importance' in item else 0.5,
            is_peripheral=item.get('importance', 5) < 3 if 'importance' in item else False,
            embedding=None
        )
        
        return entity
        
    def _parse_insight_item(self, item: Dict[str, Any], idx: int) -> Insight:
        """Parse a single insight item."""
        # Required fields
        content = item.get('content')
        if not content:
            raise ValueError("Insight missing required field: content")
            
        # Map insight type
        insight_type = self._map_insight_type(item.get('type', 'factual'))
        
        # Create insight
        # Split content into title and description if possible
        if ':' in content:
            title, description = content.split(':', 1)
            title = title.strip()
            description = description.strip()
        else:
            title = content[:50] + "..." if len(content) > 50 else content
            description = content
            
        insight = Insight(
            id=f"insight_{idx}_{datetime.now().timestamp()}",
            title=title,
            description=description,
            insight_type=insight_type,
            confidence_score=float(item.get('confidence', 0.7)),
            extracted_from_segment=None,  # Will be set by caller
            is_bridge_insight=False,  # Will be determined later
            timestamp=datetime.now()
        )
        
        return insight
        
    def _parse_quote_item(self, item: Dict[str, Any], idx: int) -> Quote:
        """Parse a single quote item."""
        # Required fields
        text = item.get('text')
        if not text:
            raise ValueError("Quote missing required field: text")
            
        # Map quote type
        quote_type = self._map_quote_type(item.get('type', 'general'))
        
        # Create quote
        quote = Quote(
            id=f"quote_{idx}_{datetime.now().timestamp()}",
            text=text,
            speaker=item.get('speaker', 'Unknown'),
            quote_type=quote_type,
            context=item.get('context', None),
            impact_score=0.5,  # Default impact score
            word_count=len(text.split()),
            estimated_timestamp=None,
            segment_id=None,  # Will be set by caller
            episode_id=None   # Will be set by caller
        )
        
        return quote
        
    def _map_entity_type(self, type_str: str) -> EntityType:
        """Map entity type string to enum."""
        type_mapping = {
            'person': EntityType.PERSON,
            'company': EntityType.ORGANIZATION,
            'organization': EntityType.ORGANIZATION,
            'institution': EntityType.ORGANIZATION,
            'product': EntityType.PRODUCT,
            'technology': EntityType.TECHNOLOGY,
            'concept': EntityType.CONCEPT,
            'location': EntityType.LOCATION,
            'event': EntityType.EVENT,
        }
        
        return type_mapping.get(type_str.lower(), EntityType.OTHER)
        
    def _map_insight_type(self, type_str: str) -> InsightType:
        """Map insight type string to enum."""
        type_mapping = {
            'factual': InsightType.FACTUAL,
            'conceptual': InsightType.CONCEPTUAL,
            'prediction': InsightType.PREDICTION,
            'recommendation': InsightType.RECOMMENDATION,
            'key_point': InsightType.KEY_POINT,
            'technical': InsightType.TECHNICAL,
            'methodological': InsightType.METHODOLOGICAL,
        }
        
        return type_mapping.get(type_str.lower(), InsightType.FACTUAL)
        
    def _map_quote_type(self, type_str: str) -> QuoteType:
        """Map quote type string to enum."""
        type_mapping = {
            'memorable': QuoteType.MEMORABLE,
            'controversial': QuoteType.CONTROVERSIAL,
            'humorous': QuoteType.HUMOROUS,
            'insightful': QuoteType.INSIGHTFUL,
            'technical': QuoteType.TECHNICAL,
            'general': QuoteType.GENERAL,
        }
        
        return type_mapping.get(type_str.lower(), QuoteType.GENERAL)


class ValidationUtils:
    """Utilities for validating parsed data."""
    
    @staticmethod
    def validate_entity(entity: Entity, source_text: str = None) -> List[str]:
        """Validate an entity and return any issues."""
        issues = []
        
        # Check name length
        if len(entity.name) < 2:
            issues.append("Entity name too short")
            
        # Check if entity appears in source text
        if source_text and entity.name.lower() not in source_text.lower():
            # Try partial match for multi-word entities
            words = entity.name.split()
            if len(words) > 1:
                found = any(
                    word.lower() in source_text.lower()
                    for word in words
                    if len(word) > 3
                )
                if not found:
                    issues.append("Entity not found in source text")
            else:
                issues.append("Entity not found in source text")
                
        # Validate mention count
        if entity.mention_count < 1:
            issues.append("Invalid mention count")
            
        # Validate bridge score
        if entity.bridge_score < 0 or entity.bridge_score > 1:
            issues.append("Bridge score out of range")
            
        return issues
        
    @staticmethod
    def validate_insight(insight: Insight) -> List[str]:
        """Validate an insight and return any issues."""
        issues = []
        
        # Check content length
        if len(insight.content) < 10:
            issues.append("Insight content too short")
            
        # Validate confidence score
        if insight.confidence_score < 0 or insight.confidence_score > 1:
            issues.append("Confidence score out of range")
            
        return issues
        
    @staticmethod
    def validate_quote(quote: Quote, source_text: str = None) -> List[str]:
        """Validate a quote and return any issues."""
        issues = []
        
        # Check quote length
        if len(quote.text) < 10:
            issues.append("Quote too short")
            
        # Check if quote appears in source
        if source_text:
            # Normalize whitespace for comparison
            normalized_quote = ' '.join(quote.text.split())
            normalized_source = ' '.join(source_text.split())
            
            if normalized_quote.lower() not in normalized_source.lower():
                # Check word overlap for partial matches
                quote_words = set(normalized_quote.lower().split())
                source_words = set(normalized_source.lower().split())
                
                overlap = len(quote_words & source_words) / len(quote_words)
                if overlap < 0.7:
                    issues.append("Quote not found in source text")
                    
        return issues