"""Unit tests for title normalization utilities."""

import pytest
from src.utils.title_utils import (
    normalize_title,
    title_matches,
    extract_title_from_filename,
    make_filename_safe
)


class TestNormalizeTitle:
    """Test cases for the normalize_title function."""
    
    def test_basic_normalization(self):
        """Test basic title normalization."""
        assert normalize_title("Simple Title") == "Simple Title"
        assert normalize_title(" Trimmed ") == "Trimmed"
        assert normalize_title("") == ""
    
    def test_punctuation_removal(self):
        """Test removal of problematic punctuation."""
        # Colons should be removed
        assert normalize_title("Episode: Part 1") == "Episode Part 1"
        assert normalize_title("Finally Feel Good in Your Body: 4 Expert Steps") == "Finally Feel Good in Your Body 4 Expert Steps"
        
        # Semicolons should be removed  
        assert normalize_title("Part A; Part B") == "Part A Part B"
        
        # Quotes should be removed
        assert normalize_title('He said "Hello"') == "He said Hello"
        assert normalize_title("She said 'Hi'") == "She said Hi"
        
        # Slashes should be removed
        assert normalize_title("Part A/Part B") == "Part A Part B"
    
    def test_html_entity_handling(self):
        """Test handling of HTML entities."""
        assert normalize_title("Truth &amp; Lies") == "Truth and Lies"
        assert normalize_title("Rock &amp; Roll") == "Rock and Roll"
        assert normalize_title("&quot;Hello&quot;") == "Hello"
        assert normalize_title("&lt;tag&gt;") == "tag"
    
    def test_ampersand_replacement(self):
        """Test ampersand replacement with 'and'."""
        assert normalize_title("Rock & Roll") == "Rock and Roll"
        assert normalize_title("Fast&Furious") == "Fast and Furious"
        assert normalize_title("A & B & C") == "A and B and C"
    
    def test_whitespace_normalization(self):
        """Test whitespace normalization."""
        assert normalize_title("Multiple   spaces") == "Multiple spaces"
        assert normalize_title("Tab\tcharacters") == "Tab characters"
        assert normalize_title("New\nlines") == "New lines"
        assert normalize_title("  Leading and trailing  ") == "Leading and trailing"
    
    def test_unicode_normalization(self):
        """Test Unicode character normalization."""
        # Different dash types should be normalized
        assert normalize_title("Test — dash") == "Test - dash"
        assert normalize_title("Test – dash") == "Test - dash"
        
        # Accented characters should be handled consistently
        title_with_accents = "Café Français"
        normalized = normalize_title(title_with_accents)
        assert normalized == "Café Français"  # Should preserve but normalize form
    
    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        assert normalize_title(None) == ""
        assert normalize_title("") == ""
        assert normalize_title("   ") == ""
        assert normalize_title(123) == ""  # Non-string input
    
    def test_real_world_examples(self):
        """Test with real episode titles from the system."""
        # Examples from The Mel Robbins Podcast
        assert normalize_title("Finally Feel Good in Your Body: 4 Expert Steps to Feeling More Confident Today") == \
               "Finally Feel Good in Your Body 4 Expert Steps to Feeling More Confident Today"
        
        assert normalize_title("3 Simple Steps to Change Your Life") == \
               "3 Simple Steps to Change Your Life"
        
        assert normalize_title("This Conversation Will Change Your Life: Do This to Find Purpose & Meaning") == \
               "This Conversation Will Change Your Life Do This to Find Purpose and Meaning"


class TestTitleMatches:
    """Test cases for the title_matches function."""
    
    def test_exact_matches(self):
        """Test exact title matches."""
        assert title_matches("Same Title", "Same Title") is True
        assert title_matches("", "") is True
    
    def test_normalized_matches(self):
        """Test matches after normalization."""
        assert title_matches("Episode: Part 1", "Episode Part 1") is True
        assert title_matches("Rock & Roll", "Rock and Roll") is True
        assert title_matches("Truth &amp; Lies", "Truth and Lies") is True
        assert title_matches("  Spaced  ", "Spaced") is True
    
    def test_non_matches(self):
        """Test cases that should not match."""
        assert title_matches("Episode 1", "Episode 2") is False
        assert title_matches("Different", "Titles") is False
        assert title_matches("Something", "") is False
    
    def test_real_world_mismatches(self):
        """Test real-world cases that were causing issues."""
        # These should match after normalization
        feed_title = "Finally Feel Good in Your Body: 4 Expert Steps to Feeling More Confident Today"
        tracker_title = "Finally Feel Good in Your Body 4 Expert Steps to Feeling More Confident Today"
        assert title_matches(feed_title, tracker_title) is True


class TestExtractTitleFromFilename:
    """Test cases for extracting titles from filenames."""
    
    def test_standard_format(self):
        """Test standard filename format."""
        assert extract_title_from_filename("2022-10-06_Episode_Title.vtt") == "Episode Title"
        assert extract_title_from_filename("2025-06-09_Finally_Feel_Good_in_Your_Body.vtt") == "Finally Feel Good in Your Body"
    
    def test_without_extension(self):
        """Test filename without .vtt extension."""
        assert extract_title_from_filename("2022-10-06_Episode_Title") == "Episode Title"
    
    def test_complex_titles(self):
        """Test complex titles with special formatting."""
        # Triple underscores represent " / "
        assert extract_title_from_filename("2022-10-06_The_Truth___How_To_Deal.vtt") == "The Truth / How To Deal"
        
        # Ampersand handling
        assert extract_title_from_filename("2022-10-06_Rock_and_Roll.vtt") == "Rock and Roll"
    
    def test_no_date_format(self):
        """Test filenames without date prefix."""
        assert extract_title_from_filename("Episode_Title.vtt") == "Episode Title"
        assert extract_title_from_filename("Simple_Title") == "Simple Title"
    
    def test_edge_cases(self):
        """Test edge cases."""
        assert extract_title_from_filename("") is None
        assert extract_title_from_filename(None) is None
        assert extract_title_from_filename("2022-10-06_.vtt") is None
    
    def test_real_world_examples(self):
        """Test with real filenames from the system."""
        filename = "2022-10-06_3_Simple_Steps_to_Change_Your_Life.vtt"
        expected = "3 Simple Steps to Change Your Life"
        assert extract_title_from_filename(filename) == expected
        
        filename = "2025-06-05_This_Conversation_Will_Change_Your_Life_Do_This_to_Find_Purpose_&_Meaning.vtt"
        expected = "This Conversation Will Change Your Life Do This to Find Purpose & Meaning"
        assert extract_title_from_filename(filename) == expected


class TestMakeFilenameSafe:
    """Test cases for making titles filesystem-safe."""
    
    def test_basic_conversion(self):
        """Test basic title to filename conversion."""
        assert make_filename_safe("Episode Title") == "Episode_Title"
        assert make_filename_safe("Simple") == "Simple"
    
    def test_special_character_handling(self):
        """Test handling of special characters."""
        assert make_filename_safe("Episode: Part 1") == "Episode_Part_1"
        assert make_filename_safe("Rock & Roll") == "Rock_and_Roll"
        assert make_filename_safe("Part A / Part B") == "Part_A___Part_B"
    
    def test_problematic_characters(self):
        """Test removal of filesystem-problematic characters."""
        assert make_filename_safe('File"name') == "Filename"
        assert make_filename_safe("File<name>") == "Filename"
        assert make_filename_safe("File|name") == "Filename"
        assert make_filename_safe("File*name") == "Filename"
    
    def test_edge_cases(self):
        """Test edge cases."""
        assert make_filename_safe("") == "untitled"
        assert make_filename_safe("   ") == "untitled"
        assert make_filename_safe("...") == "untitled"
        assert make_filename_safe("___") == "untitled"
    
    def test_round_trip_compatibility(self):
        """Test that titles can be extracted from generated filenames."""
        original_title = "Episode Title Here"
        filename_part = make_filename_safe(original_title)
        full_filename = f"2022-10-06_{filename_part}.vtt"
        extracted = extract_title_from_filename(full_filename)
        
        # Should match after normalization
        assert title_matches(original_title, extracted) is True


class TestIntegration:
    """Integration tests combining multiple functions."""
    
    def test_full_workflow(self):
        """Test the full workflow from raw title to filename and back."""
        # Simulate the workflow:
        # 1. Raw title from RSS feed
        # 2. Normalize for storage in progress tracker
        # 3. Make filename-safe for VTT file
        # 4. Extract from filename later
        # 5. Verify all versions match
        
        raw_title = "Finally Feel Good in Your Body: 4 Expert Steps & More"
        
        # Step 1: Normalize for storage
        normalized = normalize_title(raw_title)
        assert normalized == "Finally Feel Good in Your Body 4 Expert Steps and More"
        
        # Step 2: Make filename-safe
        filename_safe = make_filename_safe(normalized)
        assert filename_safe == "Finally_Feel_Good_in_Your_Body_4_Expert_Steps_and_More"
        
        # Step 3: Extract from filename
        full_filename = f"2022-10-06_{filename_safe}.vtt"
        extracted = extract_title_from_filename(full_filename)
        
        # Step 4: Verify everything matches
        assert title_matches(raw_title, normalized) is True
        assert title_matches(normalized, extracted) is True
        assert title_matches(raw_title, extracted) is True
    
    def test_problematic_cases_from_system(self):
        """Test cases that were causing issues in the actual system."""
        # Case 1: Colon in title
        feed_title = "Finally Feel Good in Your Body: 4 Expert Steps to Feeling More Confident Today"
        tracker_title = "Finally Feel Good in Your Body 4 Expert Steps to Feeling More Confident Today"
        filename = "2025-06-09_Finally_Feel_Good_in_Your_Body_4_Expert_Steps_to_Feeling_More_Confident_Today.vtt"
        
        # All should normalize to the same thing
        assert title_matches(feed_title, tracker_title) is True
        extracted = extract_title_from_filename(filename)
        assert title_matches(feed_title, extracted) is True
        assert title_matches(tracker_title, extracted) is True
        
        # Case 2: Ampersand variations
        feed_title_2 = "This Conversation Will Change Your Life: Do This to Find Purpose & Meaning"
        tracker_title_2 = "This Conversation Will Change Your Life Do This to Find Purpose and Meaning"
        filename_2 = "2025-06-05_This_Conversation_Will_Change_Your_Life_Do_This_to_Find_Purpose_&_Meaning.vtt"
        
        assert title_matches(feed_title_2, tracker_title_2) is True
        extracted_2 = extract_title_from_filename(filename_2)
        assert title_matches(feed_title_2, extracted_2) is True