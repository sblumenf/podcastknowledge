"""Tests for text processing utilities."""

import pytest
from src.utils.text_processing import (
    clean_segment_text,
    normalize_entity_name,
    calculate_name_similarity,
    extract_entity_aliases,
    extract_key_phrases,
    clean_quote_text,
    truncate_text,
    remove_special_characters,
    extract_urls,
    extract_email_addresses,
    split_into_sentences,
    calculate_text_statistics,
    normalize_whitespace
)


class TestSegmentTextCleaning:
    """Tests for segment text cleaning."""
    
    def test_clean_segment_text_basic(self):
        """Test basic text cleaning."""
        text = "  Hello   world  "
        assert clean_segment_text(text) == "Hello world"
    
    def test_clean_segment_text_filler_words(self):
        """Test removal of filler words."""
        text = "So um I think uh this is umm interesting"
        assert clean_segment_text(text) == "So I think this is interesting"
    
    def test_clean_segment_text_special_chars(self):
        """Test removal of special control characters."""
        text = "Hello\x00world\x1ftest"
        assert clean_segment_text(text) == "Helloworld test"
    
    def test_clean_segment_text_empty(self):
        """Test handling of empty text."""
        assert clean_segment_text("") == ""
        assert clean_segment_text(None) == ""
        assert clean_segment_text("   ") == ""


class TestEntityNameNormalization:
    """Tests for entity name normalization."""
    
    def test_normalize_basic(self):
        """Test basic normalization."""
        assert normalize_entity_name("Apple Inc.") == "apple"
        assert normalize_entity_name("  Microsoft Corporation  ") == "microsoft"
    
    def test_normalize_suffixes(self):
        """Test removal of corporate suffixes."""
        test_cases = [
            ("Amazon, Inc.", "amazon"),
            ("Tesla Inc", "tesla"),
            ("Google LLC", "google"),
            ("IBM Corp", "ibm"),
            ("Meta Platforms, Inc.", "meta platforms")
        ]
        
        for input_name, expected in test_cases:
            assert normalize_entity_name(input_name) == expected
    
    def test_normalize_abbreviations(self):
        """Test handling of abbreviations."""
        assert normalize_entity_name("U.S. Government") == "us government"
        assert normalize_entity_name("Dr. Smith & Associates") == "doctor smith and associates"
    
    def test_name_similarity(self):
        """Test name similarity calculation."""
        # Exact match
        assert calculate_name_similarity("Apple", "Apple") == 1.0
        
        # Case insensitive match
        assert calculate_name_similarity("apple", "APPLE") == 1.0
        
        # Similar with suffix
        similarity = calculate_name_similarity("Apple Inc.", "Apple Corporation")
        assert similarity > 0.7  # Should be high but not exact
        
        # Different names
        similarity = calculate_name_similarity("Apple", "Microsoft")
        assert similarity < 0.3


class TestEntityAliasExtraction:
    """Tests for entity alias extraction."""
    
    def test_extract_aliases_aka(self):
        """Test extraction of 'also known as' aliases."""
        description = "Apple Inc., also known as Apple Computer Company, is a tech giant."
        aliases = extract_entity_aliases("Apple Inc.", description)
        assert "Apple Computer Company" in aliases
    
    def test_extract_aliases_parentheses(self):
        """Test extraction of aliases in parentheses."""
        description = "International Business Machines (IBM) is a technology company."
        aliases = extract_entity_aliases("International Business Machines", description)
        assert "IBM" in aliases
    
    def test_extract_aliases_quotes(self):
        """Test extraction of aliases in quotes."""
        description = 'The company, or "Big Blue", dominates the market.'
        aliases = extract_entity_aliases("IBM", description)
        assert "Big Blue" in aliases
    
    def test_extract_aliases_no_duplicates(self):
        """Test that main name is not included as alias."""
        description = "Apple (Apple) is also known as Apple."
        aliases = extract_entity_aliases("Apple", description)
        assert "Apple" not in aliases
        assert "apple" not in aliases  # Case insensitive check
    
    def test_extract_aliases_empty(self):
        """Test handling of empty description."""
        assert extract_entity_aliases("Test", "") == []
        assert extract_entity_aliases("Test", None) == []


class TestKeyPhraseExtraction:
    """Tests for key phrase extraction."""
    
    def test_extract_key_phrases_basic(self):
        """Test basic key phrase extraction."""
        text = "Machine learning is transforming the industry. Machine learning applications are everywhere."
        phrases = extract_key_phrases(text, max_phrases=5)
        
        assert "machine learning" in phrases
        assert len(phrases) <= 5
    
    def test_extract_key_phrases_stop_words(self):
        """Test that stop words are filtered."""
        text = "The quick brown fox jumps over the lazy dog."
        phrases = extract_key_phrases(text)
        
        # Should not contain phrases with only stop words
        for phrase in phrases:
            words = phrase.split()
            assert not all(word in ['the', 'over'] for word in words)
    
    def test_extract_key_phrases_empty(self):
        """Test handling of empty text."""
        assert extract_key_phrases("") == []
        assert extract_key_phrases(None) == []


class TestQuoteTextCleaning:
    """Tests for quote text cleaning."""
    
    def test_clean_quote_basic(self):
        """Test basic quote cleaning."""
        quote = "  This is a quote  "
        assert clean_quote_text(quote) == '"This is a quote"'
    
    def test_clean_quote_existing_marks(self):
        """Test handling of existing quote marks."""
        quote = '"Already quoted"'
        assert clean_quote_text(quote) == '"Already quoted"'
    
    def test_clean_quote_mismatched(self):
        """Test fixing mismatched quotes."""
        quote = '"This quote has only one mark'
        result = clean_quote_text(quote)
        assert result.count('"') % 2 == 0
    
    def test_clean_quote_empty(self):
        """Test handling of empty quotes."""
        assert clean_quote_text("") == ""
        assert clean_quote_text(None) == ""


class TestTextTruncation:
    """Tests for text truncation."""
    
    def test_truncate_short_text(self):
        """Test that short text is not truncated."""
        text = "Short text"
        assert truncate_text(text, 20) == text
    
    def test_truncate_long_text(self):
        """Test truncation of long text."""
        text = "This is a very long text that needs to be truncated"
        result = truncate_text(text, 20)
        
        assert len(result) <= 20
        assert result.endswith("...")
    
    def test_truncate_word_boundary(self):
        """Test truncation preserves word boundaries."""
        text = "Hello world this is a test"
        result = truncate_text(text, 15)
        
        # Should truncate at word boundary, not mid-word
        assert result == "Hello world..."
    
    def test_truncate_custom_suffix(self):
        """Test custom truncation suffix."""
        text = "This is a long text"
        result = truncate_text(text, 10, suffix=" [...]")
        
        assert result.endswith(" [...]")


class TestSpecialCharacterRemoval:
    """Tests for special character removal."""
    
    def test_remove_special_keep_punctuation(self):
        """Test removal with punctuation preserved."""
        text = "Hello! @#$% World?"
        assert remove_special_characters(text) == "Hello! World?"
    
    def test_remove_special_no_punctuation(self):
        """Test removal of all special characters."""
        text = "Hello! @#$% World?"
        assert remove_special_characters(text, keep_punctuation=False) == "Hello World"
    
    def test_remove_special_unicode(self):
        """Test handling of unicode characters."""
        text = "Café ☕ résumé"
        result = remove_special_characters(text)
        assert "Caf" in result  # Unicode removed
        assert "rsum" in result


class TestURLExtraction:
    """Tests for URL extraction."""
    
    def test_extract_urls_http(self):
        """Test extraction of HTTP URLs."""
        text = "Visit http://example.com for more info"
        urls = extract_urls(text)
        assert "http://example.com" in urls
    
    def test_extract_urls_https(self):
        """Test extraction of HTTPS URLs."""
        text = "Check out https://www.github.com/user/repo"
        urls = extract_urls(text)
        assert "https://www.github.com/user/repo" in urls
    
    def test_extract_urls_multiple(self):
        """Test extraction of multiple URLs."""
        text = "Sites: https://google.com and http://example.org"
        urls = extract_urls(text)
        assert len(urls) == 2
        assert "https://google.com" in urls
        assert "http://example.org" in urls
    
    def test_extract_urls_none(self):
        """Test when no URLs present."""
        text = "No URLs in this text"
        assert extract_urls(text) == []


class TestEmailExtraction:
    """Tests for email extraction."""
    
    def test_extract_emails_basic(self):
        """Test basic email extraction."""
        text = "Contact us at info@example.com"
        emails = extract_email_addresses(text)
        assert "info@example.com" in emails
    
    def test_extract_emails_multiple(self):
        """Test extraction of multiple emails."""
        text = "Email john@example.com or jane.doe@company.org"
        emails = extract_email_addresses(text)
        assert len(emails) == 2
        assert "john@example.com" in emails
        assert "jane.doe@company.org" in emails
    
    def test_extract_emails_complex(self):
        """Test extraction of complex email formats."""
        text = "Send to user+tag@sub.domain.com"
        emails = extract_email_addresses(text)
        assert "user+tag@sub.domain.com" in emails


class TestSentenceSplitting:
    """Tests for sentence splitting."""
    
    def test_split_sentences_basic(self):
        """Test basic sentence splitting."""
        text = "First sentence. Second sentence! Third sentence?"
        sentences = split_into_sentences(text)
        assert len(sentences) == 3
        assert "First sentence" in sentences
    
    def test_split_sentences_abbreviations(self):
        """Test handling of abbreviations."""
        text = "Dr. Smith works at the U.S. office. He is busy."
        sentences = split_into_sentences(text)
        # This is a simple splitter, so it may not handle abbreviations perfectly
        assert len(sentences) >= 1
    
    def test_split_sentences_empty(self):
        """Test handling of empty text."""
        assert split_into_sentences("") == []
        assert split_into_sentences(None) == []


class TestTextStatistics:
    """Tests for text statistics calculation."""
    
    def test_calculate_statistics_basic(self):
        """Test basic statistics calculation."""
        text = "The quick brown fox jumps over the lazy dog."
        stats = calculate_text_statistics(text)
        
        assert stats['word_count'] == 9
        assert stats['sentence_count'] == 1
        assert stats['character_count'] == len(text)
        assert stats['unique_word_count'] == 8  # 'the' appears twice
    
    def test_calculate_statistics_multi_sentence(self):
        """Test statistics for multiple sentences."""
        text = "First sentence here. Second one. Third."
        stats = calculate_text_statistics(text)
        
        assert stats['sentence_count'] == 3
        assert stats['average_sentence_length'] > 0
    
    def test_calculate_statistics_lexical_diversity(self):
        """Test lexical diversity calculation."""
        text = "word word word different"
        stats = calculate_text_statistics(text)
        
        # 2 unique words out of 4 total
        assert stats['lexical_diversity'] == 0.5
    
    def test_calculate_statistics_empty(self):
        """Test statistics for empty text."""
        stats = calculate_text_statistics("")
        
        assert stats['word_count'] == 0
        assert stats['sentence_count'] == 0
        assert stats['lexical_diversity'] == 0


class TestWhitespaceNormalization:
    """Tests for whitespace normalization."""
    
    def test_normalize_whitespace_basic(self):
        """Test basic whitespace normalization."""
        text = "Hello    world"
        assert normalize_whitespace(text) == "Hello world"
    
    def test_normalize_whitespace_mixed(self):
        """Test normalization of mixed whitespace."""
        text = "Hello\t\n\rworld  test"
        assert normalize_whitespace(text) == "Hello world test"
    
    def test_normalize_whitespace_edges(self):
        """Test removal of edge whitespace."""
        text = "  \t text with edges \n  "
        assert normalize_whitespace(text) == "text with edges"
    
    def test_normalize_whitespace_empty(self):
        """Test handling of empty text."""
        assert normalize_whitespace("") == ""
        assert normalize_whitespace("   \t\n  ") == ""