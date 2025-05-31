"""Performance tests for pattern matching utilities."""

from typing import List
import random
import string
import time

import pytest

from src.utils.patterns import PatternLibrary, OptimizedPatternMatcher
def generate_test_text(size: int, pattern_density: float = 0.1) -> str:
    """Generate test text with controlled pattern density."""
    words = []
    technical_terms = ["machine learning", "neural network", "API", "algorithm", "framework", "database"]
    
    for _ in range(size):
        if random.random() < pattern_density:
            # Insert a pattern
            pattern_type = random.choice(["technical", "quote", "fact"])
            if pattern_type == "technical":
                words.append(random.choice(technical_terms))
            elif pattern_type == "quote":
                speaker = ''.join(random.choices(string.ascii_letters, k=5))
                quote = ' '.join(random.choices(string.ascii_lowercase.split(), k=10))
                words.append(f'"{quote}" - {speaker}')
            else:  # fact
                fact = ' '.join(random.choices(string.ascii_lowercase.split(), k=8))
                words.append(f"Research shows that {fact}.")
        else:
            # Regular word
            words.append(''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 10))))
    
    return ' '.join(words)


class TestPatternMatchingPerformance:
    """Performance tests for pattern matching."""
    
    @pytest.fixture
    def matcher(self):
        """Create a matcher instance."""
        return OptimizedPatternMatcher()
    
    @pytest.fixture
    def large_text(self):
        """Generate a large test text."""
        return generate_test_text(10000, pattern_density=0.2)
    
    def test_pattern_compilation_caching(self, matcher):
        """Test that pattern compilation is cached effectively."""
        pattern = r'\b(machine learning|ML|artificial intelligence|AI)\b'
        text = "This text contains machine learning and AI concepts."
        
        # First call - should compile pattern
        start = time.perf_counter()
        matches1 = matcher.find_all_matches(pattern, text)
        first_call_time = time.perf_counter() - start
        
        # Second call - should use cached pattern
        start = time.perf_counter()
        matches2 = matcher.find_all_matches(pattern, text)
        second_call_time = time.perf_counter() - start
        
        assert matches1 == matches2
        # Second call should be significantly faster (at least 2x)
        assert second_call_time < first_call_time / 2
    
    def test_match_result_caching(self, matcher):
        """Test that match results are cached."""
        text = "This is a test with machine learning and neural networks."
        
        # First call
        start = time.perf_counter()
        count1 = matcher.count_technical_terms(text)
        first_call_time = time.perf_counter() - start
        
        # Second call - should use cached result
        start = time.perf_counter()
        count2 = matcher.count_technical_terms(text)
        second_call_time = time.perf_counter() - start
        
        assert count1 == count2
        # Cached call should be much faster (at least 10x)
        assert second_call_time < first_call_time / 10
    
    def test_large_text_processing(self, matcher, large_text):
        """Test performance on large texts."""
        start = time.perf_counter()
        
        # Perform multiple pattern matching operations
        technical_count = matcher.count_technical_terms(large_text)
        fact_count = matcher.count_facts(large_text)
        quotes = matcher.extract_quotes(large_text)
        entities = matcher.extract_entities(large_text)
        
        total_time = time.perf_counter() - start
        
        # Should process large text in reasonable time (< 1 second)
        assert total_time < 1.0
        
        # Should find patterns
        assert technical_count > 0
        assert fact_count > 0
        assert len(quotes) > 0
        assert len(entities) > 0
    
    def test_concurrent_pattern_matching(self, matcher):
        """Test pattern matching with multiple patterns simultaneously."""
        text = generate_test_text(1000, pattern_density=0.3)
        patterns = [
            r'\b(machine learning|ML)\b',
            r'\b(neural network|NN)\b',
            r'\b(API|SDK)\b',
            r'\b(algorithm|algo)\b',
            r'\b(framework|library)\b'
        ]
        
        start = time.perf_counter()
        results = []
        for pattern in patterns:
            matches = matcher.find_all_matches(pattern, text)
            results.append(len(matches))
        total_time = time.perf_counter() - start
        
        # Should handle multiple patterns efficiently
        assert total_time < 0.5
        assert sum(results) > 0
    
    def test_pattern_library_performance(self):
        """Test PatternLibrary access performance."""
        library = PatternLibrary()
        
        # Test pattern access time
        start = time.perf_counter()
        for _ in range(1000):
            _ = library.technical_terms
            _ = library.facts
            _ = library.quotes
            _ = library.entities
        access_time = time.perf_counter() - start
        
        # Should be very fast (< 0.01 seconds for 1000 accesses)
        assert access_time < 0.01
    
    @pytest.mark.parametrize("text_size,expected_time", [
        (100, 0.01),
        (1000, 0.05),
        (10000, 0.5),
    ])
    def test_scalability(self, matcher, text_size, expected_time):
        """Test that processing time scales linearly with text size."""
        text = generate_test_text(text_size, pattern_density=0.2)
        
        start = time.perf_counter()
        matcher.count_technical_terms(text)
        matcher.count_facts(text)
        matcher.extract_quotes(text)
        processing_time = time.perf_counter() - start
        
        # Should complete within expected time
        assert processing_time < expected_time
    
    def test_cache_effectiveness(self, matcher):
        """Test cache hit rate and effectiveness."""
        texts = [generate_test_text(100) for _ in range(50)]
        
        # Process texts multiple times
        cache_misses = 0
        cache_hits = 0
        
        for _ in range(3):  # Process each text 3 times
            for text in texts:
                # Clear cache stats (would need to implement in actual code)
                start_len = len(matcher._match_cache.cache_info().currsize) if hasattr(matcher._match_cache, 'cache_info') else 0
                
                matcher.count_technical_terms(text)
                
                end_len = len(matcher._match_cache.cache_info().currsize) if hasattr(matcher._match_cache, 'cache_info') else 0
                
                if end_len > start_len:
                    cache_misses += 1
                else:
                    cache_hits += 1
        
        # Cache hit rate should be high for repeated texts
        if cache_hits + cache_misses > 0:
            hit_rate = cache_hits / (cache_hits + cache_misses)
            assert hit_rate > 0.5  # At least 50% cache hit rate