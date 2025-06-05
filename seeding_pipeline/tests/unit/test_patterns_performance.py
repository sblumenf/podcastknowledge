"""Comprehensive unit tests for pattern matching utilities."""

import re
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.utils.patterns import (
    PatternMatch,
    PatternLibrary,
    OptimizedPatternMatcher,
    pattern_matcher,
    create_custom_pattern_matcher
)


class TestPatternMatch:
    """Test PatternMatch dataclass."""
    
    def test_pattern_match_creation(self):
        """Test creating PatternMatch."""
        match = PatternMatch(
            pattern_name="test_pattern",
            pattern_type="technical",
            text="matched text",
            start=10,
            end=22
        )
        
        assert match.pattern_name == "test_pattern"
        assert match.pattern_type == "technical"
        assert match.text == "matched text"
        assert match.start == 10
        assert match.end == 22
        assert match.groups == ()
        assert match.metadata == {}
    
    def test_pattern_match_with_groups_and_metadata(self):
        """Test PatternMatch with groups and metadata."""
        match = PatternMatch(
            pattern_name="email",
            pattern_type="entity",
            text="user@example.com",
            start=0,
            end=16,
            groups=("user", "example.com"),
            metadata={"entity_type": "email", "confidence": 0.9}
        )
        
        assert match.groups == ("user", "example.com")
        assert match.metadata["entity_type"] == "email"
        assert match.metadata["confidence"] == 0.9


class TestPatternLibrary:
    """Test PatternLibrary class."""
    
    def test_pattern_library_technical_patterns(self):
        """Test technical patterns in library."""
        library = PatternLibrary()
        
        assert "medical_suffix" in library.TECHNICAL_PATTERNS
        assert "acronym" in library.TECHNICAL_PATTERNS
        assert "measurement" in library.TECHNICAL_PATTERNS
        assert "p_value" in library.TECHNICAL_PATTERNS
        assert "dna_sequence" in library.TECHNICAL_PATTERNS
    
    def test_pattern_library_fact_patterns(self):
        """Test fact patterns in library."""
        library = PatternLibrary()
        
        assert "percentage" in library.FACT_PATTERNS
        assert "study_findings" in library.FACT_PATTERNS
        assert "statistical" in library.FACT_PATTERNS
        assert "correlation" in library.FACT_PATTERNS
    
    def test_pattern_library_quote_patterns(self):
        """Test quote patterns in library."""
        library = PatternLibrary()
        
        assert "key_phrase" in library.QUOTE_PATTERNS
        assert "absolute_terms" in library.QUOTE_PATTERNS
        assert "advice_pattern" in library.QUOTE_PATTERNS
        assert "quoted_text" in library.QUOTE_PATTERNS
    
    def test_pattern_library_entity_patterns(self):
        """Test entity patterns in library."""
        library = PatternLibrary()
        
        assert "email" in library.ENTITY_PATTERNS
        assert "url" in library.ENTITY_PATTERNS
        assert "phone" in library.ENTITY_PATTERNS
        assert "money" in library.ENTITY_PATTERNS
        assert "person_name" in library.ENTITY_PATTERNS
    
    def test_pattern_library_domain_patterns(self):
        """Test domain-specific patterns in library."""
        library = PatternLibrary()
        
        assert "medical" in library.DOMAIN_PATTERNS
        assert "tech" in library.DOMAIN_PATTERNS
        assert "business" in library.DOMAIN_PATTERNS
        
        # Check medical patterns
        assert "diagnosis" in library.DOMAIN_PATTERNS["medical"]
        assert "symptoms" in library.DOMAIN_PATTERNS["medical"]
        assert "treatment" in library.DOMAIN_PATTERNS["medical"]
        
        # Check tech patterns
        assert "programming" in library.DOMAIN_PATTERNS["tech"]
        assert "architecture" in library.DOMAIN_PATTERNS["tech"]
        assert "version" in library.DOMAIN_PATTERNS["tech"]
        
        # Check business patterns
        assert "metrics" in library.DOMAIN_PATTERNS["business"]
        assert "finance" in library.DOMAIN_PATTERNS["business"]
        assert "growth" in library.DOMAIN_PATTERNS["business"]


class TestOptimizedPatternMatcher:
    """Test OptimizedPatternMatcher class."""
    
    def test_pattern_matcher_initialization(self):
        """Test pattern matcher initialization."""
        matcher = OptimizedPatternMatcher()
        
        assert hasattr(matcher, '_pattern_cache')
        assert hasattr(matcher, '_match_cache')
        assert hasattr(matcher, '_library')
        assert hasattr(matcher, 'technical_patterns')
        assert hasattr(matcher, 'fact_patterns')
        assert hasattr(matcher, 'quotable_patterns')
        assert hasattr(matcher, 'entity_patterns')
        assert hasattr(matcher, 'domain_patterns')
    
    def test_pattern_matcher_custom_cache_size(self):
        """Test pattern matcher with custom cache size."""
        matcher = OptimizedPatternMatcher(cache_size=500)
        
        # Cache should be configured with custom size
        assert matcher._match_cache.cache_info().maxsize == 500
    
    def test_compile_pattern_success(self):
        """Test compiling a valid pattern."""
        matcher = OptimizedPatternMatcher()
        
        pattern = matcher._compile_pattern(r'\d+', 'test_digits')
        
        assert isinstance(pattern, re.Pattern)
        assert pattern.pattern == r'\d+'
        assert pattern.flags & re.IGNORECASE
    
    @patch('src.utils.patterns.logger')
    def test_compile_pattern_error(self, mock_logger):
        """Test compiling an invalid pattern."""
        matcher = OptimizedPatternMatcher()
        
        # Invalid regex pattern
        pattern = matcher._compile_pattern(r'[invalid', 'test_invalid')
        
        # Should return a never-matching pattern
        assert pattern.search("anything") is None
        mock_logger.error.assert_called_once()
    
    def test_compile_pattern_caching(self):
        """Test pattern compilation caching."""
        matcher = OptimizedPatternMatcher()
        
        # Compile same pattern twice
        pattern1 = matcher._compile_pattern(r'\d+', 'test1')
        pattern2 = matcher._compile_pattern(r'\d+', 'test1')
        
        # Should be the same object (cached)
        assert pattern1 is pattern2
    
    def test_count_technical_terms(self):
        """Test counting technical terms."""
        matcher = OptimizedPatternMatcher()
        
        text = """
        The patient was diagnosed with cardiology issues and neurology problems.
        The enzyme showed high activity. We measured 100mg of the compound.
        The p-value was p < 0.05, indicating significance.
        DNA sequence: ATCGATCG
        """
        
        count = matcher.count_technical_terms(text)
        
        assert count > 0  # Should find multiple technical terms
    
    def test_count_facts(self):
        """Test counting factual statements."""
        matcher = OptimizedPatternMatcher()
        
        text = """
        The study shows that 85% of participants improved.
        Research indicates a strong correlation with the treatment.
        According to the report, sales increased by 25%.
        The median value was 42 with a standard deviation of 5.
        """
        
        count = matcher.count_facts(text)
        
        assert count > 0  # Should find multiple facts
    
    def test_get_quotability_score(self):
        """Test calculating quotability score."""
        matcher = OptimizedPatternMatcher()
        
        # Highly quotable text
        quotable_text = """
        "The key to success is always learning." If you believe in yourself,
        you can achieve everything. This changed my life completely.
        What I learned was transformative.
        """
        
        score = matcher.get_quotability_score(quotable_text)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.3  # Should have decent quotability
        
        # Not quotable text
        plain_text = "This is just regular text with no special patterns."
        plain_score = matcher.get_quotability_score(plain_text)
        
        assert plain_score < score  # Should be less quotable
    
    def test_get_quotability_score_empty_text(self):
        """Test quotability score for empty text."""
        matcher = OptimizedPatternMatcher()
        
        assert matcher.get_quotability_score("") == 0.0
        assert matcher.get_quotability_score(None) == 0.0
    
    def test_extract_entities(self):
        """Test extracting entities from text."""
        matcher = OptimizedPatternMatcher()
        
        text = """
        Contact John Smith at john@example.com or call 555-123-4567.
        Visit our website at https://example.com.
        The project costs $10,000 and will be completed by 2023-12-25.
        """
        
        entities = matcher.extract_entities(text)
        
        # Should find various entity types
        entity_types = {e.metadata['entity_type'] for e in entities}
        
        assert 'email' in entity_types
        assert 'phone' in entity_types
        assert 'url' in entity_types
        assert 'money' in entity_types
        assert 'date' in entity_types
        assert 'person_name' in entity_types
        
        # Check specific entities
        emails = [e for e in entities if e.metadata['entity_type'] == 'email']
        assert len(emails) == 1
        assert emails[0].text == 'john@example.com'
    
    def test_analyze_domain_medical(self):
        """Test analyzing medical domain text."""
        matcher = OptimizedPatternMatcher()
        
        text = """
        The patient was diagnosed with hypertension and treated with 50mg of medication daily.
        Symptoms include headache and dizziness. The therapy showed positive results.
        """
        
        results = matcher.analyze_domain(text, 'medical')
        
        assert 'diagnosis' in results
        assert 'symptoms' in results
        assert 'treatment' in results
        assert 'dosage' in results
        
        # Check matches
        assert len(results['diagnosis']) > 0
        assert len(results['symptoms']) > 0
    
    def test_analyze_domain_tech(self):
        """Test analyzing tech domain text."""
        matcher = OptimizedPatternMatcher()
        
        text = """
        We're using a microservice architecture with the new API framework.
        The algorithm has O(n) complexity and low latency. Version 2.3.1 is stable.
        Memory usage has been optimized through caching.
        """
        
        results = matcher.analyze_domain(text, 'tech')
        
        assert 'programming' in results
        assert 'architecture' in results
        assert 'performance' in results
        assert 'version' in results
        
        # Check matches
        assert len(results['architecture']) > 0
        assert len(results['version']) > 0
    
    def test_analyze_domain_business(self):
        """Test analyzing business domain text."""
        matcher = OptimizedPatternMatcher()
        
        text = """
        Our ROI increased by 25% this quarter. The investment strategy focuses on
        equity growth. Market share has grown to capture competitive advantage.
        Revenue projection shows 30% growth potential.
        """
        
        results = matcher.analyze_domain(text, 'business')
        
        assert 'metrics' in results
        assert 'finance' in results
        assert 'strategy' in results
        assert 'growth' in results
        
        # Check matches
        assert len(results['metrics']) > 0
        assert len(results['growth']) > 0
    
    @patch('src.utils.patterns.logger')
    def test_analyze_domain_unknown(self, mock_logger):
        """Test analyzing unknown domain."""
        matcher = OptimizedPatternMatcher()
        
        results = matcher.analyze_domain("Some text", "unknown_domain")
        
        assert results == {}
        mock_logger.warning.assert_called_once()
    
    def test_find_all_patterns(self):
        """Test finding all patterns in text."""
        matcher = OptimizedPatternMatcher()
        
        text = """
        Dr. John Smith (john@example.com) published a study showing 95% success rate.
        The key finding: "Always measure twice, cut once." The p-value < 0.01
        indicates strong statistical significance. Call 555-0123 for more info.
        """
        
        results = matcher.find_all_patterns(text)
        
        assert 'technical' in results
        assert 'facts' in results
        assert 'quotes' in results
        assert 'entities' in results
        
        # Should find patterns in each category
        assert len(results['technical']) > 0
        assert len(results['facts']) > 0
        assert len(results['quotes']) > 0
        assert len(results['entities']) > 0
    
    def test_find_pattern_custom(self):
        """Test finding custom pattern."""
        matcher = OptimizedPatternMatcher()
        
        text = "Product codes: ABC-123, XYZ-789, DEF-456"
        pattern = r'[A-Z]{3}-\d{3}'
        
        matches = matcher.find_pattern(text, pattern)
        
        assert len(matches) == 3
        assert matches[0].text == "ABC-123"
        assert matches[1].text == "XYZ-789"
        assert matches[2].text == "DEF-456"
        assert all(m.pattern_name == 'custom' for m in matches)
    
    def test_find_pattern_caching(self):
        """Test pattern matching caching."""
        matcher = OptimizedPatternMatcher()
        
        text = "Test pattern 123"
        pattern = r'\d+'
        
        # First call
        matches1 = matcher.find_pattern(text, pattern)
        
        # Second call (should use cache)
        matches2 = matcher.find_pattern(text, pattern)
        
        # Results should be equivalent
        assert len(matches1) == len(matches2)
        assert matches1[0].text == matches2[0].text
        
        # Check cache was used
        cache_info = matcher._match_cache.cache_info()
        assert cache_info.hits > 0
    
    def test_get_pattern_library(self):
        """Test getting pattern library."""
        matcher = OptimizedPatternMatcher()
        
        library = matcher.get_pattern_library()
        
        assert isinstance(library, PatternLibrary)
        assert hasattr(library, 'TECHNICAL_PATTERNS')
        assert hasattr(library, 'FACT_PATTERNS')
    
    @patch('src.utils.patterns.logger')
    def test_clear_cache(self, mock_logger):
        """Test clearing caches."""
        matcher = OptimizedPatternMatcher()
        
        # Add some cached patterns
        matcher._compile_pattern(r'\d+', 'test1')
        matcher.find_pattern("123", r'\d+')
        
        # Clear caches
        matcher.clear_cache()
        
        assert len(matcher._pattern_cache) == 0
        cache_info = matcher._match_cache.cache_info()
        assert cache_info.currsize == 0
        
        mock_logger.info.assert_called_once_with("Pattern matcher caches cleared")


class TestGlobalPatternMatcher:
    """Test global pattern_matcher instance."""
    
    def test_global_pattern_matcher_exists(self):
        """Test global pattern matcher is available."""
        assert pattern_matcher is not None
        assert isinstance(pattern_matcher, OptimizedPatternMatcher)
    
    def test_global_pattern_matcher_usage(self):
        """Test using global pattern matcher."""
        text = "Contact us at support@example.com"
        
        entities = pattern_matcher.extract_entities(text)
        
        emails = [e for e in entities if e.metadata['entity_type'] == 'email']
        assert len(emails) == 1
        assert emails[0].text == 'support@example.com'


class TestCreateCustomPatternMatcher:
    """Test create_custom_pattern_matcher function."""
    
    def test_create_custom_pattern_matcher(self):
        """Test creating custom pattern matcher."""
        custom_patterns = {
            'product_code': r'PROD-\d{4}',
            'order_id': r'ORD-[A-Z]{2}-\d{6}',
            'sku': r'SKU:\s*\w+'
        }
        
        matcher = create_custom_pattern_matcher(custom_patterns)
        
        assert isinstance(matcher, OptimizedPatternMatcher)
        assert hasattr(matcher, 'custom_patterns')
        assert 'product_code' in matcher.custom_patterns
        assert 'order_id' in matcher.custom_patterns
        assert 'sku' in matcher.custom_patterns
    
    def test_create_custom_pattern_matcher_with_flags(self):
        """Test creating custom pattern matcher with custom flags."""
        custom_patterns = {
            'case_sensitive': r'[A-Z]{3}'
        }
        
        matcher = create_custom_pattern_matcher(custom_patterns, flags=0)  # No IGNORECASE
        
        pattern = matcher.custom_patterns['case_sensitive']
        
        # Should match uppercase only
        assert pattern.search('ABC') is not None
        assert pattern.search('abc') is None
    
    def test_custom_pattern_matcher_usage(self):
        """Test using custom pattern matcher."""
        custom_patterns = {
            'ticket': r'TICKET-\d{6}',
            'reference': r'REF#\w{8}'
        }
        
        matcher = create_custom_pattern_matcher(custom_patterns)
        
        # Test with custom patterns
        text = "Please refer to TICKET-123456 and REF#ABCD1234"
        
        # Should be able to use the custom patterns
        ticket_pattern = matcher.custom_patterns['ticket']
        ticket_match = ticket_pattern.search(text)
        
        assert ticket_match is not None
        assert ticket_match.group() == 'TICKET-123456'
        
        ref_pattern = matcher.custom_patterns['reference']
        ref_match = ref_pattern.search(text)
        
        assert ref_match is not None
        assert ref_match.group() == 'REF#ABCD1234'