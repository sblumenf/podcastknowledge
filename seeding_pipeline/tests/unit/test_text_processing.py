"""Unit tests for text processing utilities."""

from unittest.mock import patch
import re

import pytest
import unicodedata

from src.utils.text_processing import (
    extract_urls,
    extract_email_addresses,
    split_into_sentences,
    truncate_text,
    calculate_text_statistics,
    clean_quote_text,
    extract_timestamps,
    extract_metadata_markers,
    is_question,
    extract_speaker_turns,
    normalize_entity_name,
    calculate_name_similarity
)


class TestExtractUrls:
    """Test extract_urls function."""
    
    def test_extract_basic_urls(self):
        """Test extracting basic URLs."""
        text = "Check out https://example.com and http://test.org for more info."
        urls = extract_urls(text)
        assert len(urls) == 2
        assert "https://example.com" in urls
        assert "http://test.org" in urls
    
    def test_extract_complex_urls(self):
        """Test extracting complex URLs with paths and parameters."""
        text = "Visit https://api.example.com/v1/users?id=123&format=json"
        urls = extract_urls(text)
        assert len(urls) == 1
        assert urls[0] == "https://api.example.com/v1/users?id=123&format=json"
    
    def test_extract_urls_with_subdomains(self):
        """Test extracting URLs with subdomains."""
        text = "Access https://blog.example.co.uk and http://api.test.com"
        urls = extract_urls(text)
        assert len(urls) == 2
        assert "https://blog.example.co.uk" in urls
        assert "http://api.test.com" in urls
    
    def test_no_urls(self):
        """Test with text containing no URLs."""
        text = "This text has no URLs at all."
        urls = extract_urls(text)
        assert urls == []
    
    def test_empty_text(self):
        """Test with empty text."""
        assert extract_urls("") == []
        assert extract_urls(None) == []


class TestExtractEmailAddresses:
    """Test extract_email_addresses function."""
    
    def test_extract_basic_emails(self):
        """Test extracting basic email addresses."""
        text = "Contact us at info@example.com or support@test.org"
        emails = extract_email_addresses(text)
        assert len(emails) == 2
        assert "info@example.com" in emails
        assert "support@test.org" in emails
    
    def test_extract_complex_emails(self):
        """Test extracting complex email addresses."""
        text = "Email john.doe+filter@company.co.uk or test_user123@sub.domain.com"
        emails = extract_email_addresses(text)
        assert len(emails) == 2
        assert "john.doe+filter@company.co.uk" in emails
        assert "test_user123@sub.domain.com" in emails
    
    def test_no_emails(self):
        """Test with text containing no emails."""
        text = "No email addresses here @ all"
        emails = extract_email_addresses(text)
        assert emails == []
    
    def test_empty_text(self):
        """Test with empty text."""
        assert extract_email_addresses("") == []
        assert extract_email_addresses(None) == []


class TestSplitIntoSentences:
    """Test split_into_sentences function."""
    
    def test_basic_sentence_split(self):
        """Test basic sentence splitting."""
        text = "This is sentence one. This is sentence two! And sentence three?"
        sentences = split_into_sentences(text)
        assert len(sentences) == 3
        assert "This is sentence one" in sentences
        assert "This is sentence two" in sentences
        assert "And sentence three" in sentences
    
    def test_filter_short_sentences(self):
        """Test that very short sentences are filtered."""
        text = "Valid sentence here. Hi. This is another valid sentence."
        sentences = split_into_sentences(text)
        assert len(sentences) == 2
        assert "Valid sentence here" in sentences
        assert "This is another valid sentence" in sentences
        assert "Hi" not in sentences  # Too short
    
    def test_multiple_punctuation(self):
        """Test handling of multiple punctuation marks."""
        text = "Really?! Yes... This is great!!"
        sentences = split_into_sentences(text)
        assert len(sentences) == 2
        # Check that the sentences contain the expected content
        assert any("Really" in s for s in sentences)
        assert any("This is great" in s for s in sentences)
    
    def test_empty_text(self):
        """Test with empty text."""
        assert split_into_sentences("") == []
        assert split_into_sentences(None) == []


class TestTruncateText:
    """Test truncate_text function."""
    
    def test_no_truncation_needed(self):
        """Test text that doesn't need truncation."""
        text = "Short text"
        result = truncate_text(text, 20)
        assert result == "Short text"
    
    def test_truncate_at_word_boundary(self):
        """Test truncation at word boundary."""
        text = "This is a very long sentence that needs truncation"
        result = truncate_text(text, 30)
        assert result == "This is a very long..."
        assert len(result) <= 30
    
    def test_truncate_with_custom_suffix(self):
        """Test truncation with custom suffix."""
        text = "This text will be truncated here"
        result = truncate_text(text, 20, suffix=" [...]")
        assert result.endswith(" [...]")
        assert len(result) <= 20
    
    def test_no_word_boundary(self):
        """Test truncation when no word boundary exists."""
        text = "verylongwordwithoutspaces"
        result = truncate_text(text, 10)
        assert result == "verylon..."
        assert len(result) == 10
    
    def test_empty_text(self):
        """Test with empty text."""
        assert truncate_text("", 10) == ""
        assert truncate_text(None, 10) == None


class TestCalculateTextStatistics:
    """Test calculate_text_statistics function."""
    
    def test_basic_statistics(self):
        """Test basic text statistics calculation."""
        text = "This is a test. It has two sentences."
        stats = calculate_text_statistics(text)
        
        assert stats['character_count'] == len(text)
        assert stats['word_count'] == 8
        assert stats['sentence_count'] == 2
        assert stats['average_word_length'] > 0
        assert stats['average_sentence_length'] == 4.0
        assert stats['unique_word_count'] == 8  # All words are unique
        assert stats['lexical_diversity'] == 1.0
    
    def test_repeated_words(self):
        """Test statistics with repeated words."""
        text = "The cat and the dog and the bird."
        stats = calculate_text_statistics(text)
        
        assert stats['word_count'] == 8
        assert stats['unique_word_count'] == 5  # the(3), and(2), cat, dog, bird
        assert 0 < stats['lexical_diversity'] < 1.0
    
    def test_empty_text(self):
        """Test with empty text."""
        stats = calculate_text_statistics("")
        
        assert stats['character_count'] == 0
        assert stats['word_count'] == 0
        assert stats['sentence_count'] == 0
        assert stats['average_word_length'] == 0
        assert stats['average_sentence_length'] == 0
        assert stats['unique_word_count'] == 0
        assert stats['lexical_diversity'] == 0


class TestCleanQuoteText:
    """Test clean_quote_text function."""
    
    def test_add_quotes(self):
        """Test adding quotes to unquoted text."""
        text = "This is a quote"
        result = clean_quote_text(text)
        assert result == '"This is a quote"'
    
    def test_preserve_existing_quotes(self):
        """Test preserving existing quotes."""
        text = '"Already quoted"'
        result = clean_quote_text(text)
        assert result == '"Already quoted"'
        
        text = "'Single quoted'"
        result = clean_quote_text(text)
        assert result == "'Single quoted'"
    
    def test_fix_mismatched_quotes(self):
        """Test fixing mismatched quotes."""
        text = '"Mismatched quote'
        result = clean_quote_text(text)
        assert result == 'Mismatched quote"'
    
    def test_clean_whitespace(self):
        """Test cleaning extra whitespace."""
        text = "  This   has    extra   spaces  "
        result = clean_quote_text(text)
        assert result == '"This has extra spaces"'
    
    def test_empty_quote(self):
        """Test with empty text."""
        assert clean_quote_text("") == ""
        assert clean_quote_text(None) == ""


class TestExtractTimestamps:
    """Test extract_timestamps function."""
    
    def test_extract_mm_ss_format(self):
        """Test extracting MM:SS format timestamps."""
        text = "The key point is at 12:34 in the video"
        timestamps = extract_timestamps(text)
        assert len(timestamps) == 1
        assert timestamps[0] == 754.0  # 12*60 + 34
    
    def test_extract_hh_mm_ss_format(self):
        """Test extracting HH:MM:SS format timestamps."""
        text = "Watch from 1:23:45 to see the demo"
        timestamps = extract_timestamps(text)
        assert len(timestamps) == 1
        assert timestamps[0] == 5025.0  # 1*3600 + 23*60 + 45
    
    def test_extract_seconds_format(self):
        """Test extracting seconds format."""
        text = "Skip to 45s or wait 120 seconds"
        timestamps = extract_timestamps(text)
        assert len(timestamps) == 2
        assert 45.0 in timestamps
        assert 120.0 in timestamps
    
    def test_extract_minutes_format(self):
        """Test extracting minutes format."""
        text = "This takes about 5 minutes to explain"
        timestamps = extract_timestamps(text)
        assert len(timestamps) == 1
        assert timestamps[0] == 300.0  # 5 * 60
    
    def test_multiple_timestamps(self):
        """Test extracting multiple timestamps."""
        text = "See 1:30, then 2:45, and finally 10:00"
        timestamps = extract_timestamps(text)
        assert len(timestamps) == 3
        assert 90.0 in timestamps   # 1:30
        assert 165.0 in timestamps  # 2:45
        assert 600.0 in timestamps  # 10:00
    
    def test_no_timestamps(self):
        """Test with no timestamps."""
        text = "This text has no time references"
        timestamps = extract_timestamps(text)
        assert timestamps == []
    
    def test_empty_text(self):
        """Test with empty text."""
        assert extract_timestamps("") == []
        assert extract_timestamps(None) == []


class TestExtractMetadataMarkers:
    """Test extract_metadata_markers function."""
    
    def test_extract_all_markers(self):
        """Test extracting all types of metadata markers."""
        text = ("[TIME: 10.5-15.3s] [SPEAKER: John Doe] [SEGMENT: intro-001] "
                "[EPISODE: Podcast Episode 1] This is the content.")
        
        metadata = extract_metadata_markers(text)
        
        assert metadata['start_time'] == 10.5
        assert metadata['end_time'] == 15.3
        assert metadata['speaker'] == "John Doe"
        assert metadata['segment_id'] == "intro-001"
        assert metadata['episode_title'] == "Podcast Episode 1"
        assert metadata['clean_text'] == "This is the content."
    
    def test_partial_markers(self):
        """Test with only some markers present."""
        text = "[SPEAKER: Jane] [TIME: 5.0-10.0s] Hello world"
        
        metadata = extract_metadata_markers(text)
        
        assert metadata['speaker'] == "Jane"
        assert metadata['start_time'] == 5.0
        assert metadata['end_time'] == 10.0
        assert metadata['clean_text'] == "Hello world"
        assert 'segment_id' not in metadata
        assert 'episode_title' not in metadata
    
    def test_remove_note_markers(self):
        """Test removal of note markers."""
        text = "Content here [Note: This is a note] more content"
        metadata = extract_metadata_markers(text)
        assert metadata['clean_text'] == "Content here  more content"
    
    def test_no_markers(self):
        """Test with no metadata markers."""
        text = "Plain text without any markers"
        metadata = extract_metadata_markers(text)
        assert metadata['clean_text'] == "Plain text without any markers"
        assert len(metadata) == 1  # Only clean_text


class TestIsQuestion:
    """Test is_question function."""
    
    def test_question_mark(self):
        """Test detection by question mark."""
        assert is_question("Is this a question?") is True
        assert is_question("This is not a question.") is False
    
    def test_question_words(self):
        """Test detection by question words."""
        assert is_question("What is the answer") is True
        assert is_question("When will it happen") is True
        assert is_question("Where are we going") is True
        assert is_question("Who did this") is True
        assert is_question("Why is this happening") is True
        assert is_question("How does it work") is True
    
    def test_auxiliary_verbs(self):
        """Test detection by auxiliary verbs."""
        assert is_question("Is it working") is True
        assert is_question("Are you sure") is True
        assert is_question("Was it successful") is True
        assert is_question("Do you understand") is True
        assert is_question("Can we proceed") is True
    
    def test_not_questions(self):
        """Test non-questions."""
        assert is_question("This is a statement") is False
        assert is_question("what a surprise") is False  # Exclamation, not question
        assert is_question("") is False
    
    def test_empty_text(self):
        """Test with empty text."""
        assert is_question("") is False
        assert is_question(None) is False


class TestExtractSpeakerTurns:
    """Test extract_speaker_turns function."""
    
    def test_bracket_format(self):
        """Test extracting speaker turns with bracket format."""
        text = "[SPEAKER: John] Hello there. [SPEAKER: Jane] Hi, how are you?"
        turns = extract_speaker_turns(text)
        
        assert len(turns) == 2
        assert turns[0]['speaker'] == "John"
        assert turns[0]['text'] == "Hello there."
        assert turns[1]['speaker'] == "Jane"
        assert turns[1]['text'] == "Hi, how are you?"
    
    def test_colon_format(self):
        """Test extracting speaker turns with colon format."""
        text = """John: Hello there.
Jane: Hi, how are you?
John: I'm doing well."""
        
        turns = extract_speaker_turns(text)
        
        assert len(turns) == 3
        assert turns[0]['speaker'] == "John"
        assert turns[0]['text'] == "Hello there."
        assert turns[1]['speaker'] == "Jane"
        assert turns[1]['text'] == "Hi, how are you?"
        assert turns[2]['speaker'] == "John"
        assert turns[2]['text'] == "I'm doing well."
    
    def test_mixed_content(self):
        """Test with mixed speaker formats."""
        text = "[SPEAKER: Host] Welcome. Guest: Thank you for having me."
        turns = extract_speaker_turns(text)
        
        # Should extract at least the bracket format
        assert any(turn['speaker'] == "Host" for turn in turns)
        assert any(turn['text'] == "Welcome." for turn in turns)
    
    def test_no_speakers(self):
        """Test with no speaker markers."""
        text = "This is just regular text without speakers."
        turns = extract_speaker_turns(text)
        assert turns == []


class TestNormalizeEntityName:
    """Test normalize_entity_name function."""
    
    def test_basic_normalization(self):
        """Test basic name normalization."""
        assert normalize_entity_name("John Doe") == "john doe"
        assert normalize_entity_name("UPPER CASE") == "upper case"
        assert normalize_entity_name("  extra   spaces  ") == "extra spaces"
    
    def test_remove_accents(self):
        """Test removal of accents."""
        assert normalize_entity_name("José García") == "jose garcia"
        assert normalize_entity_name("François Müller") == "francois muller"
        assert normalize_entity_name("Björk") == "bjork"
    
    def test_punctuation_handling(self):
        """Test handling of punctuation."""
        assert normalize_entity_name("O'Brien") == "o'brien"  # Keep apostrophe
        assert normalize_entity_name("Smith-Jones") == "smith-jones"  # Keep hyphen
        assert normalize_entity_name("A.B.C. Corp.") == "abc corporation"
        assert normalize_entity_name("Hello, World!") == "hello world"
    
    def test_abbreviation_expansion(self):
        """Test expansion of common abbreviations."""
        assert normalize_entity_name("ABC Inc.") == "abc incorporated"
        assert normalize_entity_name("XYZ Corp") == "xyz corporation"
        assert normalize_entity_name("Tech Ltd") == "tech limited"
        assert normalize_entity_name("Dr. Smith") == "doctor smith"
        assert normalize_entity_name("Mr. Jones") == "mister jones"
    
    def test_empty_name(self):
        """Test with empty name."""
        assert normalize_entity_name("") == ""
        assert normalize_entity_name(None) == ""


class TestCalculateNameSimilarity:
    """Test calculate_name_similarity function."""
    
    def test_exact_match(self):
        """Test exact name matches."""
        assert calculate_name_similarity("John Doe", "John Doe") == 1.0
        assert calculate_name_similarity("John Doe", "john doe") == 1.0  # Case insensitive
    
    def test_high_similarity(self):
        """Test high similarity scores."""
        score = calculate_name_similarity("John Smith", "John Smithe")
        assert 0.8 < score < 1.0
        
        score = calculate_name_similarity("Microsoft Corp", "Microsoft Corporation")
        assert score >= 0.8  # Subset match
    
    def test_subset_matching(self):
        """Test subset name matching."""
        score = calculate_name_similarity("Apple", "Apple Inc")
        assert score >= 0.8
        
        score = calculate_name_similarity("Google", "Google LLC")
        assert score >= 0.8
    
    def test_word_overlap(self):
        """Test word-level overlap calculation."""
        score = calculate_name_similarity("John Robert Smith", "Robert John Smith")
        assert score > 0.8  # Same words, different order
        
        score = calculate_name_similarity("New York Times", "The New York Times Company")
        assert score > 0.5  # Significant word overlap
    
    def test_low_similarity(self):
        """Test low similarity scores."""
        score = calculate_name_similarity("Apple", "Microsoft")
        assert score < 0.3
        
        score = calculate_name_similarity("John", "Jane")
        assert score <= 0.5
    
    def test_empty_names(self):
        """Test with empty names."""
        assert calculate_name_similarity("", "John") == 0.0
        assert calculate_name_similarity("John", "") == 0.0
        assert calculate_name_similarity("", "") == 0.0
        assert calculate_name_similarity(None, "John") == 0.0