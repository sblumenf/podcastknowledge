"""Tests for text processing utilities."""

from typing import List, Dict

import pytest

from src.utils.text_processing import (
    clean_segment_text,
    normalize_entity_name,
    calculate_name_similarity,
    extract_key_phrases,
    split_into_sentences,
    remove_filler_words,
    normalize_whitespace,
    is_valid_sentence,
    merge_text_segments,
    truncate_text,
    count_tokens_approximate,
    detect_language,
    remove_urls,
    extract_urls,
    capitalize_sentences,
    normalize_punctuation,
    split_into_paragraphs,
    extract_quoted_text,
    remove_special_characters,
    convert_numbers_to_words,
)


class TestCleanSegmentText:
    """Test clean_segment_text function."""
    
    def test_basic_cleaning(self):
        """Test basic text cleaning."""
        text = "  Hello   World!  \n\n  This is   a test.  "
        result = clean_segment_text(text)
        assert result == "Hello World! This is a test."
    
    def test_empty_text(self):
        """Test cleaning empty text."""
        assert clean_segment_text("") == ""
        assert clean_segment_text(None) == ""
        assert clean_segment_text("   ") == ""
    
    def test_remove_filler_words(self):
        """Test removal of filler words."""
        text = "So um this is uh like a uhm test"
        result = clean_segment_text(text)
        assert "um" not in result
        assert "uh" not in result
        assert "uhm" not in result
        assert "this is like a test" in result
    
    def test_control_characters(self):
        """Test removal of control characters."""
        text = "Hello\x00World\x1fTest\x7f"
        result = clean_segment_text(text)
        assert result == "HelloWorldTest"
    
    def test_multiple_spaces(self):
        """Test handling of multiple spaces."""
        text = "This  has   multiple    spaces"
        result = clean_segment_text(text)
        assert result == "This has multiple spaces"


class TestNormalizeEntityName:
    """Test normalize_entity_name function."""
    
    def test_basic_normalization(self):
        """Test basic name normalization."""
        assert normalize_entity_name("John Doe") == "john doe"
        assert normalize_entity_name("OPENAI") == "openai"
        assert normalize_entity_name("  Trimmed  ") == "trimmed"
    
    def test_special_characters(self):
        """Test handling of special characters."""
        assert normalize_entity_name("O'Brien") == "o'brien"
        assert normalize_entity_name("Jean-Pierre") == "jean-pierre"
        assert normalize_entity_name("AT&T") == "at&t"
    
    def test_unicode_normalization(self):
        """Test Unicode normalization."""
        assert normalize_entity_name("Café") == "café"
        assert normalize_entity_name("naïve") == "naïve"
    
    def test_company_suffixes(self):
        """Test handling of company suffixes."""
        assert normalize_entity_name("Apple Inc.") == "apple inc"
        assert normalize_entity_name("Google LLC") == "google llc"
        assert normalize_entity_name("Microsoft Corporation") == "microsoft corporation"
    
    def test_empty_name(self):
        """Test empty name handling."""
        assert normalize_entity_name("") == ""
        assert normalize_entity_name("   ") == ""


class TestCalculateNameSimilarity:
    """Test calculate_name_similarity function."""
    
    def test_identical_names(self):
        """Test similarity of identical names."""
        assert calculate_name_similarity("John Doe", "John Doe") == 1.0
        assert calculate_name_similarity("OpenAI", "OpenAI") == 1.0
    
    def test_case_insensitive(self):
        """Test case-insensitive similarity."""
        assert calculate_name_similarity("john doe", "JOHN DOE") > 0.9
        assert calculate_name_similarity("OpenAI", "openai") > 0.9
    
    def test_similar_names(self):
        """Test similarity of similar names."""
        # Close variations
        assert calculate_name_similarity("John Doe", "Jon Doe") > 0.8
        assert calculate_name_similarity("Microsoft", "Microsft") > 0.8
        
        # Different but related
        assert calculate_name_similarity("Robert", "Bob") < 0.5
        assert calculate_name_similarity("William", "Bill") < 0.5
    
    def test_completely_different(self):
        """Test similarity of completely different names."""
        assert calculate_name_similarity("Apple", "Microsoft") < 0.3
        assert calculate_name_similarity("John", "Jane") < 0.5
    
    def test_empty_names(self):
        """Test handling of empty names."""
        assert calculate_name_similarity("", "") == 1.0
        assert calculate_name_similarity("John", "") == 0.0
        assert calculate_name_similarity("", "John") == 0.0


class TestExtractKeyPhrases:
    """Test extract_key_phrases function."""
    
    def test_basic_extraction(self):
        """Test basic key phrase extraction."""
        text = "Machine learning is transforming artificial intelligence applications"
        phrases = extract_key_phrases(text)
        
        assert "machine learning" in phrases
        assert "artificial intelligence" in phrases
        assert len(phrases) >= 2
    
    def test_max_phrases_limit(self):
        """Test limiting number of phrases."""
        text = """Natural language processing enables computers to understand 
                  human language through machine learning algorithms and 
                  deep neural networks"""
        
        phrases = extract_key_phrases(text, max_phrases=3)
        assert len(phrases) <= 3
    
    def test_min_phrase_length(self):
        """Test minimum phrase length filter."""
        text = "AI and ML are key technologies for NLP tasks"
        phrases = extract_key_phrases(text, min_length=3)
        
        # Should filter out "AI" and "ML"
        assert "AI" not in phrases
        assert "ML" not in phrases
        assert "key technologies" in phrases or "NLP tasks" in phrases
    
    def test_empty_text(self):
        """Test extraction from empty text."""
        assert extract_key_phrases("") == []
        assert extract_key_phrases("   ") == []


class TestSplitIntoSentences:
    """Test split_into_sentences function."""
    
    def test_basic_splitting(self):
        """Test basic sentence splitting."""
        text = "This is sentence one. This is sentence two! Is this sentence three?"
        sentences = split_into_sentences(text)
        
        assert len(sentences) == 3
        assert sentences[0] == "This is sentence one."
        assert sentences[1] == "This is sentence two!"
        assert sentences[2] == "Is this sentence three?"
    
    def test_abbreviations(self):
        """Test handling of abbreviations."""
        text = "Dr. Smith works at OpenAI Inc. He is a Ph.D. in computer science."
        sentences = split_into_sentences(text)
        
        assert len(sentences) == 2
        assert "Dr. Smith" in sentences[0]
        assert "Ph.D." in sentences[1]
    
    def test_ellipsis(self):
        """Test handling of ellipsis."""
        text = "Well... I don't know... Maybe we should try?"
        sentences = split_into_sentences(text)
        
        assert len(sentences) == 3
        assert sentences[0] == "Well..."
        assert sentences[1] == "I don't know..."
        assert sentences[2] == "Maybe we should try?"
    
    def test_newlines(self):
        """Test handling of newlines."""
        text = "First sentence.\nSecond sentence.\n\nThird sentence."
        sentences = split_into_sentences(text)
        
        assert len(sentences) == 3
        assert all('\n' not in s for s in sentences)
    
    def test_empty_text(self):
        """Test splitting empty text."""
        assert split_into_sentences("") == []
        assert split_into_sentences("   ") == []


class TestRemoveFillerWords:
    """Test remove_filler_words function."""
    
    def test_common_fillers(self):
        """Test removal of common filler words."""
        text = "So, um, like, you know, it's basically, uh, very important"
        result = remove_filler_words(text)
        
        assert "um" not in result
        assert "uh" not in result
        assert "you know" not in result
        assert "basically" not in result
        assert "important" in result
    
    def test_preserve_sentence_structure(self):
        """Test that sentence structure is preserved."""
        text = "Um, the project is, like, almost complete"
        result = remove_filler_words(text)
        
        assert result == "The project is almost complete"
    
    def test_multiple_fillers(self):
        """Test removal of multiple consecutive fillers."""
        text = "It's um uh like you know basically done"
        result = remove_filler_words(text)
        
        assert result == "It's done"
    
    def test_case_insensitive(self):
        """Test case-insensitive filler removal."""
        text = "So UM this is LIKE important"
        result = remove_filler_words(text)
        
        assert "UM" not in result
        assert "LIKE" not in result
        assert "important" in result


class TestNormalizeWhitespace:
    """Test normalize_whitespace function."""
    
    def test_multiple_spaces(self):
        """Test normalization of multiple spaces."""
        text = "This  has   multiple    spaces"
        result = normalize_whitespace(text)
        assert result == "This has multiple spaces"
    
    def test_tabs_and_newlines(self):
        """Test handling of tabs and newlines."""
        text = "This\thas\ttabs\nand\nnewlines"
        result = normalize_whitespace(text)
        assert result == "This has tabs and newlines"
    
    def test_leading_trailing_whitespace(self):
        """Test removal of leading/trailing whitespace."""
        text = "  \t  Trimmed text  \n  "
        result = normalize_whitespace(text)
        assert result == "Trimmed text"
    
    def test_preserve_single_spaces(self):
        """Test that single spaces are preserved."""
        text = "This is normal text"
        result = normalize_whitespace(text)
        assert result == "This is normal text"


class TestIsValidSentence:
    """Test is_valid_sentence function."""
    
    def test_valid_sentences(self):
        """Test validation of valid sentences."""
        assert is_valid_sentence("This is a valid sentence.")
        assert is_valid_sentence("Is this valid?")
        assert is_valid_sentence("Yes, it is!")
        assert is_valid_sentence("The AI model achieved 95% accuracy")
    
    def test_invalid_sentences(self):
        """Test validation of invalid sentences."""
        assert not is_valid_sentence("")
        assert not is_valid_sentence("   ")
        assert not is_valid_sentence("...")
        assert not is_valid_sentence("Too short")  # Less than min length
        assert not is_valid_sentence("no capital letter.")
        assert not is_valid_sentence("No ending punctuation")
    
    def test_min_length_parameter(self):
        """Test minimum length parameter."""
        assert is_valid_sentence("Valid.", min_length=5)
        assert not is_valid_sentence("Bad.", min_length=5)
    
    def test_special_cases(self):
        """Test special sentence cases."""
        assert is_valid_sentence("Dr. Smith said hello.")
        assert is_valid_sentence("The price is $99.99.")
        assert is_valid_sentence("Visit example.com today!")


class TestMergeTextSegments:
    """Test merge_text_segments function."""
    
    def test_basic_merging(self):
        """Test basic text segment merging."""
        segments = ["Hello world.", "This is a test.", "Final segment."]
        result = merge_text_segments(segments)
        assert result == "Hello world. This is a test. Final segment."
    
    def test_custom_separator(self):
        """Test merging with custom separator."""
        segments = ["Part 1", "Part 2", "Part 3"]
        result = merge_text_segments(segments, separator="\n\n")
        assert result == "Part 1\n\nPart 2\n\nPart 3"
    
    def test_empty_segments(self):
        """Test handling of empty segments."""
        segments = ["Text", "", "More text", None, "Final"]
        result = merge_text_segments(segments)
        assert result == "Text More text Final"
    
    def test_whitespace_normalization(self):
        """Test whitespace normalization during merge."""
        segments = ["  Text 1  ", "  Text 2  ", "  Text 3  "]
        result = merge_text_segments(segments)
        assert result == "Text 1 Text 2 Text 3"


class TestTruncateText:
    """Test truncate_text function."""
    
    def test_basic_truncation(self):
        """Test basic text truncation."""
        text = "This is a long text that needs to be truncated"
        result = truncate_text(text, max_length=20)
        
        assert len(result) <= 20
        assert result.endswith("...")
    
    def test_word_boundary_truncation(self):
        """Test truncation at word boundaries."""
        text = "This is a long text that needs truncation"
        result = truncate_text(text, max_length=20, at_word_boundary=True)
        
        assert len(result) <= 20
        assert not result[:-3].endswith(" ")  # No trailing space before ellipsis
        assert result.endswith("...")
    
    def test_no_truncation_needed(self):
        """Test when text doesn't need truncation."""
        text = "Short text"
        result = truncate_text(text, max_length=20)
        assert result == "Short text"
        assert not result.endswith("...")
    
    def test_custom_ellipsis(self):
        """Test custom ellipsis string."""
        text = "This is a long text that needs to be truncated"
        result = truncate_text(text, max_length=20, ellipsis=" [...]")
        
        assert result.endswith(" [...]")
        assert len(result) <= 20


class TestCountTokensApproximate:
    """Test count_tokens_approximate function."""
    
    def test_basic_counting(self):
        """Test basic token counting."""
        text = "This is a simple test sentence."
        count = count_tokens_approximate(text)
        
        # Approximate count should be close to word count
        assert 5 <= count <= 8
    
    def test_punctuation_handling(self):
        """Test handling of punctuation in token counting."""
        text = "Hello, world! How are you?"
        count = count_tokens_approximate(text)
        
        # Punctuation might be counted as separate tokens
        assert 5 <= count <= 10
    
    def test_empty_text(self):
        """Test counting tokens in empty text."""
        assert count_tokens_approximate("") == 0
        assert count_tokens_approximate("   ") == 0
    
    def test_special_characters(self):
        """Test counting with special characters."""
        text = "Email: user@example.com, URL: https://example.com"
        count = count_tokens_approximate(text)
        
        # URLs and emails might be split into multiple tokens
        assert count >= 4


class TestUtilityFunctions:
    """Test various utility functions."""
    
    def test_remove_urls(self):
        """Test URL removal."""
        text = "Visit https://example.com or http://test.org for more info"
        result = remove_urls(text)
        
        assert "https://example.com" not in result
        assert "http://test.org" not in result
        assert "Visit" in result
        assert "for more info" in result
    
    def test_extract_urls(self):
        """Test URL extraction."""
        text = "Check https://example.com and http://test.org"
        urls = extract_urls(text)
        
        assert len(urls) == 2
        assert "https://example.com" in urls
        assert "http://test.org" in urls
    
    def test_capitalize_sentences(self):
        """Test sentence capitalization."""
        text = "this is sentence one. this is sentence two. and a third."
        result = capitalize_sentences(text)
        
        assert result == "This is sentence one. This is sentence two. And a third."
    
    def test_normalize_punctuation(self):
        """Test punctuation normalization."""
        text = "Multiple!!!  Question marks???  Ellipsis...."
        result = normalize_punctuation(text)
        
        assert "!!!" not in result
        assert "???" not in result
        assert "...." not in result
        assert result.count("!") <= 1
        assert result.count("?") <= 1
    
    def test_extract_quoted_text(self):
        """Test extraction of quoted text."""
        text = 'He said "Hello world" and she replied "Hi there".'
        quotes = extract_quoted_text(text)
        
        assert len(quotes) == 2
        assert "Hello world" in quotes
        assert "Hi there" in quotes
    
    def test_remove_special_characters(self):
        """Test removal of special characters."""
        text = "Hello@World#2024$Test%"
        result = remove_special_characters(text)
        
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result
        assert "%" not in result
        assert "HelloWorld2024Test" in result