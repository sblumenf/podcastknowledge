"""Unit tests for YouTube query builder module."""

import pytest
from src.youtube_query_builder import QueryBuilder


class TestQueryBuilder:
    """Test cases for QueryBuilder class."""
    
    @pytest.fixture
    def query_builder(self):
        """Create a QueryBuilder instance for testing."""
        return QueryBuilder()
    
    def test_exact_match_query_generation(self, query_builder):
        """Test exact match query generation."""
        query = query_builder.build_exact_match_query(
            "The Tim Ferriss Show",
            "Episode 123: Jane Doe on Success"
        )
        
        assert query == '"The Tim Ferriss Show" "Episode 123: Jane Doe on Success"'
        
    def test_exact_match_query_normalization(self, query_builder):
        """Test query normalization in exact match."""
        # Test with extra spaces
        query = query_builder.build_exact_match_query(
            "  The   Tim   Ferriss   Show  ",
            "  Episode   123  "
        )
        
        assert query == '"The Tim Ferriss Show" "Episode 123"'
        
    def test_episode_number_query_generation(self, query_builder):
        """Test episode number query generation."""
        query = query_builder.build_episode_number_query(
            "The Daily",
            123
        )
        
        expected = '"The Daily" (episode 123 OR ep 123 OR #123)'
        assert query == expected
        
    def test_episode_number_query_with_title_fragment(self, query_builder):
        """Test episode number query with title fragment."""
        query = query_builder.build_episode_number_query(
            "The Daily",
            123,
            "Climate Change Crisis"
        )
        
        # Should include key terms from title
        assert '"The Daily"' in query
        assert '(episode 123 OR ep 123 OR #123)' in query
        assert 'Climate' in query or 'Change' in query or 'Crisis' in query
        
    def test_guest_name_query_generation(self, query_builder):
        """Test guest name query generation."""
        query = query_builder.build_guest_name_query(
            "The Joe Rogan Experience",
            "Elon Musk"
        )
        
        assert query == '"The Joe Rogan Experience" "Elon Musk"'
        
    def test_fuzzy_match_query_generation(self, query_builder):
        """Test fuzzy match query generation."""
        query = query_builder.build_fuzzy_match_query(
            "My Podcast",
            "artificial intelligence and the future of work"
        )
        
        assert '"My Podcast"' in query
        assert 'artificial' in query
        assert 'intelligence' in query
        assert 'future' in query
        assert 'work' in query
        # Common words should be filtered out
        assert ' and ' not in query
        assert ' the ' not in query
        assert ' of ' not in query
        
    def test_extract_episode_number(self, query_builder):
        """Test episode number extraction from various formats."""
        test_cases = [
            ("Episode 123: The Title", 123),
            ("Ep. 456 - Another Title", 456),
            ("#789 With Guest", 789),
            ("123 - Title Here", 123),
            ("123. Title Here", 123),
            ("The 1st Episode Ever", 1),
            ("The 2nd Episode", 2),
            ("The 3rd Episode", 3),
            ("The 4th Episode", 4),
            ("No Number Here", None),
            ("Year 2023 Review", None),  # Shouldn't match years
        ]
        
        for title, expected in test_cases:
            result = query_builder._extract_episode_number(title)
            assert result == expected, f"Failed for '{title}': expected {expected}, got {result}"
            
    def test_extract_guest_name(self, query_builder):
        """Test guest name extraction."""
        test_cases = [
            ("Episode 123 with John Doe", "John Doe"),
            ("Interview with Jane Smith, CEO", "Jane Smith"),
            ("Featuring Dr. Bob Johnson", "Dr. Bob Johnson"),
            ("Ft. Alice Williams", "Alice Williams"),
            ("Guest: Michael Brown", "Michael Brown"),
            ("Conversation with Sarah Davis", "Sarah Davis"),
            ("Title - Guest Name Here", "Guest Name Here"),
            ("No Guest Pattern", None),
            ("With X", None),  # Too short
        ]
        
        for title, expected in test_cases:
            result = query_builder._extract_guest_name(title)
            assert result == expected, f"Failed for '{title}': expected {expected}, got {result}"
            
    def test_clean_title(self, query_builder):
        """Test title cleaning."""
        test_cases = [
            ("Episode 123: The Title", "The Title"),
            ("Ep. 456 - Another Title", "Another Title"),
            ("#789: Title", "Title"),
            ("123. Title Here", "Title Here"),
            ("EP001: Special Characters!@#$", "Special Characters"),
            ("Multiple   Spaces   Between", "Multiple Spaces Between"),
        ]
        
        for original, expected in test_cases:
            result = query_builder._clean_title(original)
            assert result == expected, f"Failed for '{original}': expected '{expected}', got '{result}'"
            
    def test_extract_key_terms(self, query_builder):
        """Test key term extraction."""
        text = "The Quick Brown Fox Jumps Over The Lazy Dog"
        terms = query_builder._extract_key_terms(text)
        
        # Should include meaningful words
        assert "Quick" in terms
        assert "Brown" in terms
        assert "Fox" in terms
        assert "Jumps" in terms
        assert "Lazy" in terms
        assert "Dog" in terms
        
        # Should exclude stop words
        assert "The" not in terms
        assert "the" not in terms
        assert "Over" not in terms
        
    def test_normalize_query(self, query_builder):
        """Test query normalization."""
        # Test space normalization
        query = "Too    many     spaces"
        normalized = query_builder._normalize_query(query)
        assert normalized == "Too many spaces"
        
        # Test length truncation
        long_query = "a" * 150
        normalized = query_builder._normalize_query(long_query)
        assert len(normalized) <= 100
        assert normalized.endswith("...")
        
    def test_build_queries_comprehensive(self, query_builder):
        """Test comprehensive query building."""
        queries = query_builder.build_queries(
            "The Tim Ferriss Show",
            "Episode 123: Interview with Elon Musk on SpaceX and Tesla",
            episode_number=123
        )
        
        # Convert to dict for easier testing
        query_dict = {q: rank for q, rank in queries}
        
        # Should have multiple queries
        assert len(queries) >= 3
        
        # Check ranks are in order
        ranks = [rank for _, rank in queries]
        assert ranks == sorted(ranks)
        
        # Should include exact match (rank 1)
        exact_query = '"The Tim Ferriss Show" "Episode 123: Interview with Elon Musk on SpaceX and Tesla"'
        assert exact_query in query_dict
        assert query_dict[exact_query] == 1
        
        # Should include episode number query (rank 2)
        ep_queries = [q for q in query_dict if 'episode 123' in q or 'ep 123' in q]
        assert len(ep_queries) > 0
        
        # Should include guest name query (rank 3)
        guest_queries = [q for q in query_dict if 'Elon Musk' in q]
        assert len(guest_queries) > 0
        
    def test_build_queries_no_duplicates(self, query_builder):
        """Test that build_queries doesn't return duplicates."""
        queries = query_builder.build_queries(
            "Podcast",
            "Episode 1: Title",
            episode_number=1
        )
        
        query_strings = [q for q, _ in queries]
        assert len(query_strings) == len(set(query_strings)), "Found duplicate queries"
        
    @pytest.mark.parametrize("podcast,title,expected_count", [
        ("Simple Podcast", "Simple Title", 2),  # Exact + fuzzy
        ("Podcast", "Episode 123", 3),  # Exact + episode + fuzzy
        ("Show", "Interview with Guest Name", 3),  # Exact + guest + fuzzy
        ("Pod", "Ep 1: Talk with John Doe about AI", 5),  # All types
    ])
    def test_build_queries_count(self, query_builder, podcast, title, expected_count):
        """Test query count for various inputs."""
        queries = query_builder.build_queries(podcast, title)
        assert len(queries) >= expected_count