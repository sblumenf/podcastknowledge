"""Comprehensive tests for text processing utilities."""

from typing import List, Dict, Any
from unittest.mock import patch, MagicMock
import re

import pytest

from src.utils.text_processing import (
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


class TestCleanSegmentText:
    """Test suite for function."""
    
    def test_basic_cleaning(self):
        """Test basic text cleaning."""
        assert("  Hello World  ") == "Hello World"
        assert("Multiple   spaces") == "Multiple spaces"
        assert("\n\tNewlines\r\n") == "Newlines"
    
    def test_empty_or_none(self):
        """Test handling of empty or None input."""
        assert("") == ""
        assert(None) == ""
        assert("   ") == ""
    
    def test_filler_word_removal(self):
        """Test removal of filler words."""
        assert("I um think so") == "I think so"
        assert("Well uh maybe") == "Well maybe"
        assert("It's uhm complicated") == "It's complicated"
        assert("I umm don't know") == "I don't know"
    
    def test_special_character_removal(self):
        """Test removal of control characters."""
        # Control characters
        assert("Hello\x00World") == "Hello World"
        assert("Test\x1fString") == "Test String"
        assert("Data\x7fHere") == "Data Here"
    
    def test_multiple_replacements(self):
        """Test multiple replacements in one pass."""
        text = "I um think uh this uhm is umm good"
        expected = "I think this is good"
        assert(text) == expected
    
    def test_preserve_punctuation(self):
        """Test that punctuation is preserved."""
        text = "Hello, world! How are you? I'm fine."
        assert(text) == text
        
        text_with_special = "Cost: $100.50 (approx.)"
        assert "$" not in(text_with_special)  # Control chars removed
    
    def test_unicode_handling(self):
        """Test handling of Unicode text."""
        assert("Café résumé") == "Café résumé"
        assert("Hello 🌍 World") == "Hello 🌍 World"
        assert("测试 中文") == "测试 中文"
    
    def test_whitespace_normalization(self):
        """Test comprehensive whitespace normalization."""
        text = "  Multiple\t\ttabs\nand\r\nnewlines   here  "
        expected = "Multiple tabs and newlines here"
        assert(text) == expected


class TestNormalizeEntityName:
    """Test suite for function."""
    
    def test_basic_normalization(self):
        """Test basic name normalization."""
        assert("John Doe") == "john doe"
        assert("  UPPERCASE  ") == "uppercase"
        assert("Mixed Case Name") == "mixed case name"
    
    def test_empty_or_none(self):
        """Test handling of empty or None input."""
        assert("") == ""
        assert(None) == ""
        assert("   ") == ""
    
    def test_company_suffix_removal(self):
        """Test removal of company suffixes."""
        assert("Apple Inc.") == "apple"
        assert("Google, Inc") == "google"
        assert("Microsoft Corporation") == "microsoft"
        assert("Amazon LLC") == "amazon"
        assert("Tesla, Ltd") == "tesla"
        assert("IBM Corp") == "ibm"
        assert("Smith & Company") == "smith"
        assert("Jones & Co") == "jones"
    
    def test_abbreviation_expansion(self):
        """Test expansion of common abbreviations."""
        assert("Johnson & Johnson") == "johnson and johnson"
        assert("U.S. Government") == "us government"
        assert("U.K. Parliament") == "uk parliament"
        assert("Dr. Smith") == "doctor smith"
        assert("Mr. Jones") == "mister jones"
        assert("Ms. Davis") == "miss davis"
        assert("Prof. Wilson") == "professor wilson"
    
    def test_multiple_transformations(self):
        """Test multiple transformations in one name."""
        assert("Dr. Smith & Associates, Inc.") == "doctor smith and associates"
        assert("U.S. Steel Corp") == "us steel"
        assert("Mr. Brown & Co., Ltd") == "mister brown"
    
    def test_whitespace_handling(self):
        """Test whitespace normalization."""
        assert("John    Doe") == "john doe"
        assert("\tTabbed\tName\t") == "tabbed name"
        assert("New\nLine") == "new line"
    
    def test_special_cases(self):
        """Test special edge cases."""
        assert("A") == "a"  # Single character
        assert("123") == "123"  # Numbers
        assert("Name, Inc., Inc.") == "name"  # Double suffix
        assert("& Co") == "and co"  # Just suffix
    
    def test_unicode_names(self):
        """Test Unicode name handling."""
        assert("Société Générale") == "société générale"
        assert("München AG") == "münchen ag"
        assert("北京公司") == "北京公司"


class TestCalculateNameSimilarity:
    """Test suite for calculate_name_similarity function."""
    
    def test_identical_names(self):
        """Test similarity of identical names."""
        assert calculate_name_similarity("John Doe", "John Doe") == 1.0
        assert calculate_name_similarity("Apple", "Apple") == 1.0
    
    def test_case_insensitive(self):
        """Test case-insensitive comparison."""
        assert calculate_name_similarity("john doe", "JOHN DOE") == 1.0
        assert calculate_name_similarity("Apple Inc", "apple inc") == 1.0
    
    def test_with_normalization(self):
        """Test similarity with normalization applied."""
        assert calculate_name_similarity("Apple Inc.", "Apple") == 1.0
        assert calculate_name_similarity("Dr. Smith", "Doctor Smith") == 1.0
        assert calculate_name_similarity("U.S. Government", "US Government") == 1.0
    
    def test_partial_matches(self):
        """Test partial name matches."""
        similarity = calculate_name_similarity("John Doe", "John Smith")
        assert 0 < similarity < 1
        assert similarity > 0.3  # Should have some similarity due to "John"
    
    def test_completely_different(self):
        """Test completely different names."""
        assert calculate_name_similarity("Apple", "Microsoft") < 0.3
        assert calculate_name_similarity("ABC", "XYZ") < 0.2
    
    def test_empty_names(self):
        """Test handling of empty names."""
        assert calculate_name_similarity("", "") == 1.0
        assert calculate_name_similarity("John", "") == 0.0
        assert calculate_name_similarity("", "John") == 0.0
    
    def test_typos_and_variations(self):
        """Test similarity with typos and variations."""
        # Typos should have high similarity
        assert calculate_name_similarity("Microsoft", "Microsft") > 0.8
        assert calculate_name_similarity("Google", "Googel") > 0.8
        
        # Common variations
        assert calculate_name_similarity("International Business Machines", "IBM") < 0.5
    
    @patch('difflib.SequenceMatcher')
    def test_sequence_matcher_usage(self, mock_matcher):
        """Test that SequenceMatcher is used correctly."""
        mock_instance = MagicMock()
        mock_instance.ratio.return_value = 0.75
        mock_matcher.return_value = mock_instance
        
        result = calculate_name_similarity("Name1", "Name2")
        assert result == 0.75
        mock_matcher.assert_called_once()


class TestExtractEntityAliases:
    """Test suite for extract_entity_aliases function."""
    
    def test_also_known_as_pattern(self):
        """Test extraction of 'also known as' aliases."""
        description = "Apple Inc., also known as Apple Computer, is a tech company"
        aliases = extract_entity_aliases("Apple Inc.", description)
        assert "Apple Computer" in aliases
    
    def test_formerly_pattern(self):
        """Test extraction of 'formerly' aliases."""
        description = "Meta, formerly Facebook, is a social media company"
        aliases = extract_entity_aliases("Meta", description)
        assert "Facebook" in aliases
    
    def test_aka_pattern(self):
        """Test extraction of 'aka' aliases."""
        description = "Robert Downey Jr. (aka RDJ) is an actor"
        aliases = extract_entity_aliases("Robert Downey Jr.", description)
        assert "RDJ" in aliases
    
    def test_parentheses_pattern(self):
        """Test extraction of names in parentheses."""
        description = "The National Aeronautics and Space Administration (NASA) explores space"
        aliases = extract_entity_aliases("National Aeronautics and Space Administration", description)
        assert "NASA" in aliases
    
    def test_quoted_names(self):
        """Test extraction of quoted names."""
        description = 'William Smith or "Bill" is a developer'
        aliases = extract_entity_aliases("William Smith", description)
        assert "Bill" in aliases
        
        description = "Jennifer Lopez or 'J.Lo' is a singer"
        aliases = extract_entity_aliases("Jennifer Lopez", description)
        assert "J.Lo" in aliases
    
    def test_multiple_aliases(self):
        """Test extraction of multiple aliases."""
        description = "Sean Combs, also known as Puff Daddy, formerly P. Diddy (aka Diddy)"
        aliases = extract_entity_aliases("Sean Combs", description)
        assert "Puff Daddy" in aliases
        assert "P. Diddy" in aliases
        assert "Diddy" in aliases
    
    def test_no_aliases(self):
        """Test when no aliases are found."""
        description = "John Smith is a common name"
        aliases = extract_entity_aliases("John Smith", description)
        assert aliases == []
    
    def test_empty_description(self):
        """Test handling of empty description."""
        assert extract_entity_aliases("Name", "") == []
        assert extract_entity_aliases("Name", None) == []
    
    def test_self_reference_exclusion(self):
        """Test that the main name is not included as an alias."""
        description = "Apple (Apple Inc.) is a company"
        aliases = extract_entity_aliases("Apple", description)
        assert "Apple" not in aliases
        assert "Apple Inc." in aliases
    
    def test_case_insensitive_self_exclusion(self):
        """Test case-insensitive self-reference exclusion."""
        description = "IBM (also known as IBM) was formerly something else"
        aliases = extract_entity_aliases("ibm", description)
        assert "IBM" not in aliases
        assert "ibm" not in aliases


class TestExtractKeyPhrases:
    """Test suite for extract_key_phrases function."""
    
    def test_basic_phrase_extraction(self):
        """Test basic key phrase extraction."""
        text = "Machine learning is transforming artificial intelligence. Machine learning models are powerful."
        phrases = extract_key_phrases(text)
        assert "machine learning" in phrases
        assert len(phrases) <= 10
    
    def test_empty_text(self):
        """Test handling of empty text."""
        assert extract_key_phrases("") == []
        assert extract_key_phrases(None) == []
    
    def test_stop_word_filtering(self):
        """Test that stop words are filtered out."""
        text = "The machine is learning. The model is training."
        phrases = extract_key_phrases(text)
        # Phrases starting/ending with stop words should be filtered
        for phrase in phrases:
            words = phrase.split()
            assert words[0] not in ['the', 'is', 'a', 'an']
            assert words[-1] not in ['the', 'is', 'a', 'an']
    
    def test_frequency_based_ranking(self):
        """Test that phrases are ranked by frequency."""
        text = """
        Data science is important. Data science helps businesses.
        Machine learning is part of data science. Analytics is different.
        Data science requires statistics.
        """
        phrases = extract_key_phrases(text, max_phrases=3)
        # "data science" should be first due to frequency
        assert phrases[0] == "data science"
    
    def test_max_phrases_limit(self):
        """Test max_phrases parameter."""
        text = "One two three four five six seven eight nine ten eleven twelve"
        phrases = extract_key_phrases(text, max_phrases=5)
        assert len(phrases) <= 5
    
    def test_multi_word_phrases(self):
        """Test extraction of 2-3 word phrases."""
        text = "Natural language processing is complex. Deep neural networks help."
        phrases = extract_key_phrases(text)
        
        # Check for multi-word phrases
        multi_word_phrases = [p for p in phrases if len(p.split()) > 1]
        assert len(multi_word_phrases) > 0
    
    def test_punctuation_handling(self):
        """Test handling of punctuation."""
        text = "AI, ML, and DL are acronyms. What about NLP?"
        phrases = extract_key_phrases(text)
        # Punctuation should be removed
        for phrase in phrases:
            assert ',' not in phrase
            assert '?' not in phrase
            assert '.' not in phrase
    
    def test_case_normalization(self):
        """Test that phrases are normalized to lowercase."""
        text = "MACHINE LEARNING and Machine Learning are the same"
        phrases = extract_key_phrases(text)
        # All phrases should be lowercase
        for phrase in phrases:
            assert phrase.islower()
    
    def test_hyphenated_words(self):
        """Test preservation of hyphenated words."""
        text = "State-of-the-art models use self-attention mechanisms"
        phrases = extract_key_phrases(text)
        # Hyphens should be preserved
        hyphenated = [p for p in phrases if '-' in p]
        assert len(hyphenated) > 0


class TestCleanQuoteText:
    """Test suite for clean_quote_text function."""
    
    def test_basic_cleaning(self):
        """Test basic quote cleaning."""
        assert clean_quote_text("  Hello World  ") == '"Hello World"'
        assert clean_quote_text("Already quoted") == '"Already quoted"'
    
    def test_empty_quote(self):
        """Test handling of empty quotes."""
        assert clean_quote_text("") == ""
        assert clean_quote_text(None) == ""
        assert clean_quote_text("   ") == '""'
    
    def test_existing_quotes(self):
        """Test handling of existing quote marks."""
        assert clean_quote_text('"Already quoted"') == '"Already quoted"'
        assert clean_quote_text("'Single quoted'") == "'Single quoted'"
        assert clean_quote_text('Mixed "quotes') == 'Mixed quotes"'
    
    def test_mismatched_quotes(self):
        """Test fixing of mismatched quotes."""
        assert clean_quote_text('"Mismatched') == 'Mismatched"'
        assert clean_quote_text('Three"quotes"here"') == 'Threequoteshere"'
    
    def test_whitespace_normalization(self):
        """Test whitespace normalization in quotes."""
        assert clean_quote_text("Multiple   spaces") == '"Multiple spaces"'
        assert clean_quote_text("\n\tNewlines\n") == '"Newlines"'


class TestTruncateText:
    """Test suite for truncate_text function."""
    
    def test_no_truncation_needed(self):
        """Test text that doesn't need truncation."""
        text = "Short text"
        assert truncate_text(text, 20) == text
        assert truncate_text(text, 10) == text  # Exact length
    
    def test_basic_truncation(self):
        """Test basic text truncation."""
        text = "This is a very long text that needs truncation"
        result = truncate_text(text, 20)
        assert len(result) <= 20
        assert result.endswith("...")
    
    def test_word_boundary_preservation(self):
        """Test that truncation happens at word boundaries."""
        text = "This is a test of word boundary truncation"
        result = truncate_text(text, 25)
        assert not result.endswith("boun...")  # Should not break "boundary"
        assert result.endswith("...")
    
    def test_custom_suffix(self):
        """Test custom truncation suffix."""
        text = "Long text that will be truncated"
        result = truncate_text(text, 20, suffix=" [more]")
        assert result.endswith(" [more]")
        assert len(result) <= 20
    
    def test_no_space_found(self):
        """Test truncation when no space is found."""
        text = "Verylongwordwithoutspaces"
        result = truncate_text(text, 10)
        assert len(result) == 10
        assert result == "Verylong..."
    
    def test_empty_text(self):
        """Test handling of empty text."""
        assert truncate_text("", 10) == ""
        assert truncate_text(None, 10) == None
    
    def test_exact_length_with_suffix(self):
        """Test edge case where text + suffix equals max length."""
        text = "Exactly"
        result = truncate_text(text, 10, "...")
        assert result == text  # No truncation needed


class TestRemoveSpecialCharacters:
    """Test suite for remove_special_characters function."""
    
    def test_keep_punctuation(self):
        """Test removal with punctuation preserved."""
        text = "Hello! How are you? I'm fine."
        result = remove_special_characters(text, keep_punctuation=True)
        assert result == text
        
        text_with_special = "Price: $100 @ 50% off!"
        result = remove_special_characters(text_with_special, keep_punctuation=True)
        assert "$" not in result
        assert "@" not in result
        assert "%" not in result
        assert "!" in result
    
    def test_remove_all_special(self):
        """Test removal of all special characters including punctuation."""
        text = "Hello! How are you? I'm fine."
        result = remove_special_characters(text, keep_punctuation=False)
        assert result == "Hello How are you Im fine"
        assert "!" not in result
        assert "?" not in result
        assert "'" not in result
    
    def test_unicode_handling(self):
        """Test handling of Unicode characters."""
        text = "Café costs €10"
        result = remove_special_characters(text, keep_punctuation=True)
        assert "€" not in result  # Euro sign removed
        assert "Caf" in result  # Accented e removed
    
    def test_empty_text(self):
        """Test handling of empty text."""
        assert remove_special_characters("") == ""
        assert remove_special_characters(None) == ""
    
    def test_whitespace_normalization(self):
        """Test that multiple spaces are normalized."""
        text = "Multiple   spaces   here"
        result = remove_special_characters(text)
        assert result == "Multiple spaces here"
    
    def test_allowed_characters(self):
        """Test that allowed characters are preserved."""
        text = "Test-123: Quote's \"here\" (parentheses)"
        result = remove_special_characters(text, keep_punctuation=True)
        assert "-" in result
        assert ":" in result
        assert "'" in result
        assert '"' in result
        assert "(" in result
        assert ")" in result


class TestExtractUrls:
    """Test suite for extract_urls function."""
    
    def test_basic_url_extraction(self):
        """Test extraction of basic URLs."""
        text = "Visit https://example.com for more info"
        urls = extract_urls(text)
        assert urls == ["https://example.com"]
    
    def test_multiple_urls(self):
        """Test extraction of multiple URLs."""
        text = "Check http://example.com and https://test.org"
        urls = extract_urls(text)
        assert len(urls) == 2
        assert "http://example.com" in urls
        assert "https://test.org" in urls
    
    def test_urls_with_paths(self):
        """Test extraction of URLs with paths."""
        text = "API docs at https://api.example.com/v1/docs"
        urls = extract_urls(text)
        assert urls == ["https://api.example.com/v1/docs"]
    
    def test_urls_with_parameters(self):
        """Test extraction of URLs with query parameters."""
        text = "Search: https://example.com/search?q=test&page=1"
        urls = extract_urls(text)
        assert urls == ["https://example.com/search?q=test&page=1"]
    
    def test_no_urls(self):
        """Test when no URLs are present."""
        text = "This text has no URLs"
        urls = extract_urls(text)
        assert urls == []
    
    def test_empty_text(self):
        """Test handling of empty text."""
        assert extract_urls("") == []
        assert extract_urls(None) == []
    
    def test_invalid_urls_not_extracted(self):
        """Test that invalid URLs are not extracted."""
        text = "Not a URL: htp://wrong or example.com or ftp://file.com"
        urls = extract_urls(text)
        assert len(urls) == 0  # None should match
    
    def test_urls_with_fragments(self):
        """Test URLs with fragments."""
        text = "Section at https://example.com/page#section"
        urls = extract_urls(text)
        assert "https://example.com/page#section" in urls


class TestExtractEmailAddresses:
    """Test suite for extract_email_addresses function."""
    
    def test_basic_email_extraction(self):
        """Test extraction of basic email addresses."""
        text = "Contact us at info@example.com"
        emails = extract_email_addresses(text)
        assert emails == ["info@example.com"]
    
    def test_multiple_emails(self):
        """Test extraction of multiple email addresses."""
        text = "Email john@example.com or mary@test.org"
        emails = extract_email_addresses(text)
        assert len(emails) == 2
        assert "john@example.com" in emails
        assert "mary@test.org" in emails
    
    def test_complex_emails(self):
        """Test extraction of complex email addresses."""
        text = "Send to first.last@sub.example.co.uk"
        emails = extract_email_addresses(text)
        assert emails == ["first.last@sub.example.co.uk"]
    
    def test_emails_with_special_chars(self):
        """Test emails with allowed special characters."""
        text = "Contact user+tag@example.com or test_email@domain.com"
        emails = extract_email_addresses(text)
        assert "user+tag@example.com" in emails
        assert "test_email@domain.com" in emails
    
    def test_no_emails(self):
        """Test when no emails are present."""
        text = "This text has no email addresses"
        emails = extract_email_addresses(text)
        assert emails == []
    
    def test_empty_text(self):
        """Test handling of empty text."""
        assert extract_email_addresses("") == []
        assert extract_email_addresses(None) == []
    
    def test_invalid_emails_not_extracted(self):
        """Test that invalid emails are not extracted."""
        text = "Invalid: @example.com, user@, user@@example.com"
        emails = extract_email_addresses(text)
        assert len(emails) == 0
    
    def test_case_insensitive(self):
        """Test case-insensitive email extraction."""
        text = "Email: John.Doe@Example.COM"
        emails = extract_email_addresses(text)
        assert emails == ["John.Doe@Example.COM"]


class TestSplitIntoSentences:
    """Test suite for split_into_sentences function."""
    
    def test_basic_splitting(self):
        """Test basic sentence splitting."""
        text = "First sentence. Second sentence. Third sentence."
        sentences = split_into_sentences(text)
        assert len(sentences) == 3
        assert sentences[0] == "First sentence"
        assert sentences[1] == "Second sentence"
        assert sentences[2] == "Third sentence"
    
    def test_multiple_punctuation(self):
        """Test splitting with different punctuation."""
        text = "Statement. Question? Exclamation! Another statement."
        sentences = split_into_sentences(text)
        assert len(sentences) == 4
        assert "Statement" in sentences[0]
        assert "Question" in sentences[1]
        assert "Exclamation" in sentences[2]
    
    def test_short_sentence_filtering(self):
        """Test that very short sentences are filtered."""
        text = "Good sentence here. Ok. Another good sentence."
        sentences = split_into_sentences(text)
        # "Ok" should be filtered out (less than 10 chars)
        assert len(sentences) == 2
        assert "Ok" not in sentences
    
    def test_empty_text(self):
        """Test handling of empty text."""
        assert split_into_sentences("") == []
        assert split_into_sentences(None) == []
    
    def test_no_punctuation(self):
        """Test text without sentence-ending punctuation."""
        text = "This text has no ending punctuation"
        sentences = split_into_sentences(text)
        assert len(sentences) == 1
        assert sentences[0] == text
    
    def test_multiple_punctuation_marks(self):
        """Test handling of multiple punctuation marks."""
        text = "Really?! Yes!!! Absolutely..."
        sentences = split_into_sentences(text)
        assert len(sentences) == 3
        assert sentences[0] == "Really"
        assert sentences[1] == "Yes"
        assert sentences[2] == "Absolutely"
    
    def test_whitespace_handling(self):
        """Test handling of whitespace around sentences."""
        text = "  First sentence.   Second sentence.  "
        sentences = split_into_sentences(text)
        assert sentences[0] == "First sentence"
        assert sentences[1] == "Second sentence"


class TestCalculateTextStatistics:
    """Test suite for calculate_text_statistics function."""
    
    def test_basic_statistics(self):
        """Test calculation of basic text statistics."""
        text = "This is a test. It has two sentences."
        stats = calculate_text_statistics(text)
        
        assert stats['character_count'] == len(text)
        assert stats['word_count'] == 8
        assert stats['sentence_count'] == 2
        assert stats['average_word_length'] > 0
        assert stats['average_sentence_length'] == 4.0
        assert stats['unique_word_count'] == 8  # All words unique
        assert stats['lexical_diversity'] == 1.0
    
    def test_empty_text(self):
        """Test statistics for empty text."""
        stats = calculate_text_statistics("")
        assert stats['character_count'] == 0
        assert stats['word_count'] == 0
        assert stats['sentence_count'] == 0
        assert stats['average_word_length'] == 0
        assert stats['average_sentence_length'] == 0
        assert stats['unique_word_count'] == 0
        assert stats['lexical_diversity'] == 0
    
    def test_repeated_words(self):
        """Test lexical diversity with repeated words."""
        text = "The cat and the dog and the bird."
        stats = calculate_text_statistics(text)
        
        assert stats['word_count'] == 8
        assert stats['unique_word_count'] == 5  # the(3), and(2), cat, dog, bird
        assert 0 < stats['lexical_diversity'] < 1
    
    def test_single_sentence(self):
        """Test statistics for single sentence."""
        text = "This is just one sentence without punctuation"
        stats = calculate_text_statistics(text)
        
        assert stats['sentence_count'] == 1
        assert stats['average_sentence_length'] == 7
    
    def test_unicode_text(self):
        """Test statistics for Unicode text."""
        text = "Café résumé naïve. Über große Höhe."
        stats = calculate_text_statistics(text)
        
        assert stats['character_count'] > 0
        assert stats['word_count'] == 6
        assert stats['sentence_count'] == 2
    
    def test_numeric_precision(self):
        """Test that numeric values are properly rounded."""
        text = "A BB CCC DDDD EEEEE. AA BBB CCCC."
        stats = calculate_text_statistics(text)
        
        # Check that averages are rounded to 2 decimal places
        assert isinstance(stats['average_word_length'], float)
        assert len(str(stats['average_word_length']).split('.')[-1]) <= 2
        
        # Check lexical diversity rounded to 3 decimal places
        assert isinstance(stats['lexical_diversity'], float)
        assert len(str(stats['lexical_diversity']).split('.')[-1]) <= 3


class TestNormalizeWhitespace:
    """Test suite for normalize_whitespace function."""
    
    def test_basic_normalization(self):
        """Test basic whitespace normalization."""
        assert normalize_whitespace("  Hello  World  ") == "Hello World"
        assert normalize_whitespace("Multiple   spaces") == "Multiple spaces"
    
    def test_various_whitespace_chars(self):
        """Test normalization of various whitespace characters."""
        text = "Tab\there\nNewline\rCarriage\r\nCRLF"
        expected = "Tab here Newline Carriage CRLF"
        assert normalize_whitespace(text) == expected
    
    def test_empty_text(self):
        """Test handling of empty text."""
        assert normalize_whitespace("") == ""
        assert normalize_whitespace(None) == ""
        assert normalize_whitespace("   \n\t\r   ") == ""
    
    def test_unicode_whitespace(self):
        """Test handling of Unicode whitespace."""
        text = "Non breaking\u00A0space"
        assert normalize_whitespace(text) == "Non breaking space"
    
    def test_preserve_single_spaces(self):
        """Test that single spaces are preserved."""
        text = "This has single spaces between words"
        assert normalize_whitespace(text) == text
    
    def test_leading_trailing_removal(self):
        """Test removal of leading and trailing whitespace."""
        assert normalize_whitespace("\n\nLeading") == "Leading"
        assert normalize_whitespace("Trailing\t\t") == "Trailing"
        assert normalize_whitespace("\rBoth\n") == "Both"


class TestIntegrationScenarios:
    """Integration tests for text processing utilities."""
    
    def test_full_text_processing_pipeline(self):
        """Test complete text processing pipeline."""
        # Simulate raw transcript text
        raw_text = """
        So um, I was talking to Dr. Smith from Apple Inc. and uh he mentioned 
        that machine learning is really transforming the industry. You can 
        contact him at john.smith@apple.com or visit https://apple.com/ml.
        
        He said, "AI will change everything!" which I uhm found interesting.
        
        The company (formerly Apple Computer) has been working on this for years...
        """
        
        # Clean the text
        cleaned =(raw_text)
        assert " um " not in cleaned
        assert " uh " not in cleaned
        assert " uhm " not in cleaned
        
        # Extract entities and normalize
        entities = ["Dr. Smith", "Apple Inc.", "Apple Computer"]
        normalized_entities = [(e) for e in entities]
        assert "doctor smith" in normalized_entities
        assert "apple" in normalized_entities
        
        # Extract contact info
        emails = extract_email_addresses(cleaned)
        assert "john.smith@apple.com" in emails
        
        urls = extract_urls(cleaned)
        assert "https://apple.com/ml" in urls
        
        # Extract and clean quotes
        quote = "AI will change everything!"
        cleaned_quote = clean_quote_text(quote)
        assert cleaned_quote == '"AI will change everything!"'
        
        # Calculate statistics
        stats = calculate_text_statistics(cleaned)
        assert stats['word_count'] > 0
        assert stats['sentence_count'] > 0
    
    def test_entity_resolution_workflow(self):
        """Test entity resolution workflow."""
        entities = [
            {"name": "Apple Inc.", "description": "Apple Inc. (formerly Apple Computer) makes iPhones"},
            {"name": "Dr. John Smith", "description": "Dr. Smith works at Apple"},
            {"name": "Microsoft Corp", "description": "Microsoft Corporation builds Windows"}
        ]
        
        # Normalize names for comparison
        normalized_names = {}
        for entity in entities:
            norm_name =(entity["name"])
            normalized_names[norm_name] = entity["name"]
            
            # Extract aliases
            aliases = extract_entity_aliases(entity["name"], entity["description"])
            for alias in aliases:
                norm_alias =(alias)
                normalized_names[norm_alias] = entity["name"]
        
        # Test resolution
        assert normalized_names.get("apple") == "Apple Inc."
        assert normalized_names.get("apple computer") == "Apple Inc."
        assert normalized_names.get("doctor john smith") == "Dr. John Smith"
        assert normalized_names.get("microsoft") == "Microsoft Corp"
    
    def test_text_analysis_workflow(self):
        """Test text analysis workflow."""
        document = """
        Machine learning and artificial intelligence are transforming healthcare.
        Machine learning models can now diagnose diseases with high accuracy.
        Deep learning, a subset of machine learning, is particularly effective.
        Healthcare professionals are adopting these AI tools rapidly.
        Contact info@healthcare-ai.com for more information about AI in healthcare.
        Visit https://healthcare-ai.com/resources for detailed resources.
        """
        
        # Clean and normalize
        cleaned_doc = normalize_whitespace(document)
        
        # Extract key phrases
        key_phrases = extract_key_phrases(cleaned_doc, max_phrases=5)
        assert "machine learning" in key_phrases  # Should be top phrase
        
        # Split into sentences for analysis
        sentences = split_into_sentences(cleaned_doc)
        assert len(sentences) >= 4
        
        # Extract contact information
        emails = extract_email_addresses(cleaned_doc)
        urls = extract_urls(cleaned_doc)
        assert len(emails) == 1
        assert len(urls) == 1
        
        # Calculate statistics
        stats = calculate_text_statistics(cleaned_doc)
        assert stats['lexical_diversity'] < 1.0  # Has repeated words
        
    def test_quote_extraction_workflow(self):
        """Test quote extraction and cleaning workflow."""
        text = """
        The CEO said "We need to innovate faster to stay competitive in this market."
        When asked about competition, she responded, 'Our focus is on our customers,
        not our competitors.' The analyst noted: "This is a significant strategic shift".
        """
        
        # Clean the text
        cleaned =(text)
        
        # Extract quotes (simplified - in practice would use more sophisticated methods)
        quote_patterns = [
            r'"([^"]+)"',
            r"'([^']+)'",
            r': "([^"]+)"'
        ]
        
        quotes = []
        for pattern in quote_patterns:
            matches = re.findall(pattern, cleaned)
            quotes.extend(matches)
        
        # Clean quotes
        cleaned_quotes = [clean_quote_text(q) for q in quotes]
        assert len(cleaned_quotes) >= 3
        
        # All should be properly quoted
        for quote in cleaned_quotes:
            assert quote.startswith('"') or quote.startswith("'")
            assert quote.endswith('"') or quote.endswith("'")


class TestPerformanceScenarios:
    """Test performance characteristics of text processing functions."""
    
    def test_large_text_performance(self):
        """Test performance with large text inputs."""
        # Create a large text (10,000 words)
        large_text = " ".join(["word" + str(i) for i in range(10000)])
        
        import time
        
        # Test various functions with large input
        start = time.time()
        cleaned =(large_text)
        clean_time = time.time() - start
        assert clean_time < 0.5  # Should be fast
        
        start = time.time()
        stats = calculate_text_statistics(large_text)
        stats_time = time.time() - start
        assert stats_time < 1.0  # Should complete within 1 second
        
        assert stats['word_count'] == 10000
        assert stats['unique_word_count'] == 10000
    
    def test_repeated_operations(self):
        """Test repeated operations for consistency."""
        text = "Test text for repeated operations"
        
        # Run same operation multiple times
        results = []
        for _ in range(10):
            result =(text)
            results.append(result)
        
        # All results should be identical
        assert len(set(results)) == 1
        
        # Test with statistics
        stats_results = []
        for _ in range(5):
            stats = calculate_text_statistics(text)
            stats_results.append(stats['word_count'])
        
        assert len(set(stats_results)) == 1
    
    def test_edge_case_handling(self):
        """Test handling of edge cases."""
        # Very long word
        long_word = "a" * 1000
        assert len((long_word)) == 1000
        
        # Text with only punctuation
        punct_only = "...!!!???"
        cleaned = remove_special_characters(punct_only, keep_punctuation=False)
        assert cleaned == ""
        
        # Text with only whitespace
        whitespace_only = "   \n\t\r   "
        assert normalize_whitespace(whitespace_only) == ""
        
        # Empty results
        assert extract_urls("No URLs here") == []
        assert extract_email_addresses("No emails here") == []
        assert extract_entity_aliases("Name", "No aliases") == []