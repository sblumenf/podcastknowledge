Comprehensive tests for text processing utilities.

from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import re

import pytest
import unicodedata

from src.utils.text_processing import (
    # Text cleaning
    clean_text,
    normalize_whitespace,
    remove_control_characters,
    fix_encoding,
    standardize_quotes,
    remove_html_tags,
    unescape_html,
    
    # Text transformation
    to_snake_case,
    to_camel_case,
    to_pascal_case,
    to_kebab_case,
    to_title_case,
    to_sentence_case,
    
    # Text analysis
    count_words,
    count_sentences,
    count_paragraphs,
    extract_sentences,
    extract_words,
    extract_paragraphs,
    calculate_readability,
    
    # Text validation
    is_valid_email,
    is_valid_url,
    is_valid_phone,
    is_valid_credit_card,
    contains_profanity,
    
    # Text manipulation
    truncate_text,
    wrap_text,
    indent_text,
    dedent_text,
    align_text,
    
    # Text extraction
    extract_emails,
    extract_urls,
    extract_phones,
    extract_hashtags,
    extract_mentions,
    extract_numbers,
    extract_dates,
    
    # Text comparison
    calculate_similarity,
    find_differences,
    fuzzy_match,
    longest_common_substring,
    
    # Text generation
    generate_slug,
    generate_excerpt,
    generate_summary,
    
    # Unicode handling
    remove_accents,
    transliterate,
    normalize_unicode,
    
    # Constants
    PUNCTUATION_MARKS,
    STOP_WORDS,
    PROFANITY_LIST,
)


class TestTextCleaning:
    Test text cleaning functions.
    
    def test_clean_text_basic(self):
        Test basic text cleaning.
        text =   Hello   World!  \n\n  How are   you?  
        cleaned = clean_text(text)
        assert cleaned == Hello World! How are you?
    
    def test_clean_text_with_options(self):
        Test text cleaning with options.
        text = <p>Hello <b>World</b>!</p>\n\nEmail: test@example.com
        
        # Remove HTML
        cleaned = clean_text(text, remove_html=True)
        assert <p> not in cleaned
        assert Hello World! in cleaned
        
        # Lowercase
        cleaned = clean_text(text, lowercase=True)
        assert hello in cleaned
        
        # Remove punctuation
        cleaned = clean_text(Hello, World!, remove_punctuation=True)
        assert cleaned == Hello World
    
    def test_normalize_whitespace(self):
        Test whitespace normalization.
        text = Hello   \t\n  World  \r\n  Test
        normalized = normalize_whitespace(text)
        assert normalized == Hello World Test
        
        # Preserve single newlines
        text = Line 1\nLine 2\n\nLine 3
        normalized = normalize_whitespace(text, preserve_newlines=True)
        assert normalized == Line 1\nLine 2\nLine 3
    
    def test_remove_control_characters(self):
        Test removing control characters.
        text = Hello\x00World\x01Test\x1f
        cleaned = remove_control_characters(text)
        assert cleaned == HelloWorldTest
        
        # Keep newlines and tabs
        text = Hello\tWorld\nTest
        cleaned = remove_control_characters(text, keep_newlines=True, keep_tabs=True)
        assert cleaned == Hello\tWorld\nTest
    
    def test_fix_encoding(self):
        Test fixing text encoding issues.
        # Common encoding issues
        text = Itâ€™s a nice day  # Mojibake
        fixed = fix_encoding(text)
        assert fixed == It's a nice day
        
        text = café  # Already correct
        fixed = fix_encoding(text)
        assert fixed == café
    
    def test_standardize_quotes(self):
        Test quote standardization.
        text = 'Hello \'World\' «Test»'
        standardized = standardize_quotes(text)
        assert standardized == 'Hello \'World\' Test'
        
        # Smart quotes to straight
        text = It's a \test\ of 'quotes'
        standardized = standardize_quotes(text, style=straight)
        assert standardized == It's a \test\ of 'quotes'
    
    def test_remove_html_tags(self):
        Test HTML tag removal.
        html = <p>Hello <b>World</b>!</p><script>alert('test')</script>
        text = remove_html_tags(html)
        assert text == Hello World!
        
        # Keep specific tags
        html = <p>Hello <b>World</b> <i>Test</i>!</p>
        text = remove_html_tags(html, keep_tags=[b])
        assert text == Hello <b>World</b> Test!
    
    def test_unescape_html(self):
        Test HTML entity unescaping.
        text = &lt;Hello &amp; World&gt; &quot;Test&quot; &nbsp;
        unescaped = unescape_html(text)
        assert unescaped == '<Hello & World> Test  '


class TestTextTransformation:
    Test text transformation functions.
    
    def test_to_snake_case(self):
        Test snake_case conversion.
        assert to_snake_case(HelloWorld) == hello_world
        assert to_snake_case(hello-world) == hello_world
        assert to_snake_case(Hello World) == hello_world
        assert to_snake_case(HTTPResponse) == http_response
        assert to_snake_case(getHTTPResponseCode) == get_http_response_code
    
    def test_to_camel_case(self):
        Test camelCase conversion.
        assert to_camel_case(hello_world) == helloWorld
        assert to_camel_case(hello-world) == helloWorld
        assert to_camel_case(Hello World) == helloWorld
        assert to_camel_case(get_http_response) == getHttpResponse
    
    def test_to_pascal_case(self):
        Test PascalCase conversion.
        assert to_pascal_case(hello_world) == HelloWorld
        assert to_pascal_case(hello-world) == HelloWorld
        assert to_pascal_case(hello world) == HelloWorld
        assert to_pascal_case(http_response) == HttpResponse
    
    def test_to_kebab_case(self):
        Test kebab-case conversion.
        assert to_kebab_case(HelloWorld) == hello-world
        assert to_kebab_case(hello_world) == hello-world
        assert to_kebab_case(Hello World) == hello-world
        assert to_kebab_case(HTTPResponse) == http-response
    
    def test_to_title_case(self):
        Test title case conversion.
        assert to_title_case(hello world) == Hello World
        assert to_title_case(the quick brown fox) == The Quick Brown Fox
        
        # With articles/prepositions handling
        text = the cat in the hat
        assert to_title_case(text, keep_small_words_lower=True) == The Cat in the Hat
    
    def test_to_sentence_case(self):
        Test sentence case conversion.
        assert to_sentence_case(hello world) == Hello world
        assert to_sentence_case(HELLO WORLD) == Hello world
        assert to_sentence_case(hello. world) == Hello. World


class TestTextAnalysis:
    Test text analysis functions.
    
    def test_count_words(self):
        Test word counting.
        text = Hello world! This is a test.
        assert count_words(text) == 6
        
        # With contractions
        text = It's a beautiful day, isn't it?
        assert count_words(text) == 7
        
        # Exclude punctuation
        text = Hello... World!!!
        assert count_words(text, exclude_punctuation=True) == 2
    
    def test_count_sentences(self):
        Test sentence counting.
        text = Hello world. This is a test! Is it working?
        assert count_sentences(text) == 3
        
        # With abbreviations
        text = Dr. Smith went to the U.S.A. He arrived at 3 p.m.
        assert count_sentences(text) == 2
        
        # With ellipsis
        text = Well... I don't know... Maybe?
        assert count_sentences(text) == 3
    
    def test_count_paragraphs(self):
        Test paragraph counting.
        text = First paragraph.\n\nSecond paragraph.\n\nThird paragraph.
        assert count_paragraphs(text) == 3
        
        # With different separators
        text = Para 1\n\n\n\nPara 2\r\n\r\nPara 3
        assert count_paragraphs(text) == 3
    
    def test_extract_sentences(self):
        Test sentence extraction.
        text = First sentence. Second sentence! Third sentence?
        sentences = extract_sentences(text)
        
        assert len(sentences) == 3
        assert sentences[0] == First sentence.
        assert sentences[1] == Second sentence!
        assert sentences[2] == Third sentence?
    
    def test_extract_words(self):
        Test word extraction.
        text = Hello, world! Test-case #123.
        words = extract_words(text)
        
        assert Hello in words
        assert world in words
        assert Test-case in words
        assert #123 not in words  # Punctuation excluded
    
    def test_extract_paragraphs(self):
        Test paragraph extraction.
        text = First paragraph here.
        Still first paragraph.
        
        Second paragraph starts here.
        Continues here.
        
        
        Third paragraph.
        
        paragraphs = extract_paragraphs(text)
        assert len(paragraphs) == 3
        assert Still first paragraph in paragraphs[0]
        assert Second paragraph in paragraphs[1]
    
    def test_calculate_readability(self):
        Test readability calculation.
        # Simple text
        simple = The cat sat on the mat. The dog ran.
        score = calculate_readability(simple)
        assert score[flesch_reading_ease] > 90  # Very easy
        
        # Complex text
        complex_text = The implementation of sophisticated algorithms 
        necessitates comprehensive understanding of theoretical foundations 
        and practical considerations.
        score = calculate_readability(complex_text)
        assert score[flesch_reading_ease] < 30  # Very difficult
        
        # Check all metrics
        assert flesch_kincaid_grade in score
        assert gunning_fog in score
        assert automated_readability_index in score


class TestTextValidation:
    Test text validation functions.
    
    def test_is_valid_email(self):
        Test email validation.
        assert is_valid_email(user@example.com)
        assert is_valid_email(user.name+tag@example.co.uk)
        assert is_valid_email(user_123@sub.example.com)
        
        assert not is_valid_email(invalid.email)
        assert not is_valid_email(@example.com)
        assert not is_valid_email(user@)
        assert not is_valid_email(user space@example.com)
    
    def test_is_valid_url(self):
        Test URL validation.
        assert is_valid_url(https://example.com)
        assert is_valid_url(http://sub.example.com/path?query=1)
        assert is_valid_url(ftp://files.example.com)
        assert is_valid_url(https://example.com:8080)
        
        assert not is_valid_url(not a url)
        assert not is_valid_url(http://)
        assert not is_valid_url(example.com)  # Missing protocol
    
    def test_is_valid_phone(self):
        Test phone number validation.
        # US formats
        assert is_valid_phone(+1-555-123-4567)
        assert is_valid_phone(555-123-4567)
        assert is_valid_phone((555) 123-4567)
        assert is_valid_phone(5551234567)
        
        # International
        assert is_valid_phone(+44 20 7123 4567)
        assert is_valid_phone(+33 1 23 45 67 89)
        
        assert not is_valid_phone(123)
        assert not is_valid_phone(abc-def-ghij)
    
    def test_is_valid_credit_card(self):
        Test credit card validation.
        # Valid card numbers (test numbers)
        assert is_valid_credit_card(4111111111111111)  # Visa
        assert is_valid_credit_card(5500000000000004)  # Mastercard
        assert is_valid_credit_card(340000000000009)   # Amex
        
        # With formatting
        assert is_valid_credit_card(4111-1111-1111-1111)
        assert is_valid_credit_card(4111 1111 1111 1111)
        
        # Invalid
        assert not is_valid_credit_card(1234567890123456)
        assert not is_valid_credit_card(411111111111111)  # Wrong length
    
    def test_contains_profanity(self):
        Test profanity detection.
        assert contains_profanity(This contains damn word)
        assert contains_profanity(What the hell)
        
        assert not contains_profanity(This is clean text)
        assert not contains_profanity(Hello world)
        
        # Case insensitive
        assert contains_profanity(This contains DAMN word)


class TestTextManipulation:
    Test text manipulation functions.
    
    def test_truncate_text(self):
        Test text truncation.
        text = This is a long text that needs to be truncated
        
        # Basic truncation
        truncated = truncate_text(text, 20)
        assert len(truncated) <= 20
        assert truncated.endswith(...)
        
        # Word boundary truncation
        truncated = truncate_text(text, 20, at_word_boundary=True)
        assert not truncated[:-3].endswith( )  # Doesn't cut mid-word
        
        # Custom suffix
        truncated = truncate_text(text, 20, suffix= [more])
        assert truncated.endswith( [more])
    
    def test_wrap_text(self):
        Test text wrapping.
        text = This is a long line that needs to be wrapped at a certain width
        
        # Basic wrapping
        wrapped = wrap_text(text, width=20)
        lines = wrapped.split('\n')
        assert all(len(line) <= 20 for line in lines)
        
        # With indentation
        wrapped = wrap_text(text, width=20, indent=  )
        lines = wrapped.split('\n')
        assert all(line.startswith(  ) for line in lines)
    
    def test_indent_text(self):
        Test text indentation.
        text = Line 1\nLine 2\nLine 3
        
        # Basic indent
        indented = indent_text(text,   )
        assert indented ==   Line 1\n  Line 2\n  Line 3
        
        # First line different
        indented = indent_text(text,   , first_line_indent=* )
        assert indented.startswith(* Line 1)
        assert \n  Line 2 in indented
    
    def test_dedent_text(self):
        Test text dedentation.
        text = 
            This is indented
            text that needs
            dedenting
        
        
        dedented = dedent_text(text)
        lines = dedented.strip().split('\n')
        assert not any(line.startswith( ) for line in lines)
    
    def test_align_text(self):
        Test text alignment.
        text = Hello\nWorld\nTest
        
        # Left align (default)
        aligned = align_text(text, width=10, align=left)
        lines = aligned.split('\n')
        assert lines[0] == Hello     
        
        # Right align
        aligned = align_text(text, width=10, align=right)
        lines = aligned.split('\n')
        assert lines[0] ==      Hello
        
        # Center align
        aligned = align_text(text, width=10, align=center)
        lines = aligned.split('\n')
        assert lines[0] ==   Hello   


class TestTextExtraction:
    Test text extraction functions.
    
    def test_extract_emails(self):
        Test email extraction.
        text = 
        Contact us at info@example.com or support@example.org.
        Personal: john.doe+work@company.co.uk
        
        
        emails = extract_emails(text)
        assert info@example.com in emails
        assert support@example.org in emails
        assert john.doe+work@company.co.uk in emails
    
    def test_extract_urls(self):
        Test URL extraction.
        text = 
        Visit https://example.com for more info.
        Also check http://blog.example.org/post/123
        And ftp://files.example.com/data.zip
        
        
        urls = extract_urls(text)
        assert https://example.com in urls
        assert http://blog.example.org/post/123 in urls
        assert ftp://files.example.com/data.zip in urls
    
    def test_extract_phones(self):
        Test phone number extraction.
        text = 
        Call us at (555) 123-4567 or 555-987-6543.
        International: +1-555-111-2222
        Mobile: 555.333.4444
        
        
        phones = extract_phones(text)
        assert (555) 123-4567 in phones
        assert 555-987-6543 in phones
        assert +1-555-111-2222 in phones
        assert 555.333.4444 in phones
    
    def test_extract_hashtags(self):
        Test hashtag extraction.
        text = Check out #Python #MachineLearning and #AI_Technology!
        
        hashtags = extract_hashtags(text)
        assert #Python in hashtags
        assert #MachineLearning in hashtags
        assert #AI_Technology in hashtags
    
    def test_extract_mentions(self):
        Test mention extraction.
        text = Thanks @johndoe and @mary_jane for the help! cc @tech-team
        
        mentions = extract_mentions(text)
        assert @johndoe in mentions
        assert @mary_jane in mentions
        assert @tech-team in mentions
    
    def test_extract_numbers(self):
        Test number extraction.
        text = The price is $123.45, quantity is 50, and discount is 10.5%
        
        numbers = extract_numbers(text)
        assert 123.45 in numbers
        assert 50 in numbers
        assert 10.5 in numbers
        
        # With formatting
        text = Population: 1,234,567 Revenue: $9.99M
        numbers = extract_numbers(text, ignore_commas=True)
        assert 1234567 in numbers
    
    def test_extract_dates(self):
        Test date extraction.
        text = 
        Meeting on 2024-01-15 at 3pm.
        Deadline: January 20, 2024
        Born: 15/03/1990
        
        
        dates = extract_dates(text)
        assert any(d.year == 2024 and d.month == 1 and d.day == 15 for d in dates)
        assert any(d.year == 2024 and d.month == 1 and d.day == 20 for d in dates)
        assert any(d.year == 1990 and d.month == 3 and d.day == 15 for d in dates)


class TestTextComparison:
    Test text comparison functions.
    
    def test_calculate_similarity(self):
        Test text similarity calculation.
        text1 = The quick brown fox
        text2 = The quick brown dog
        
        # High similarity
        similarity = calculate_similarity(text1, text2)
        assert similarity > 0.7
        
        # Low similarity
        text3 = Something completely different
        similarity = calculate_similarity(text1, text3)
        assert similarity < 0.3
        
        # Identical
        similarity = calculate_similarity(text1, text1)
        assert similarity == 1.0
    
    def test_find_differences(self):
        Test finding text differences.
        text1 = The quick brown fox jumps
        text2 = The slow brown fox runs
        
        diffs = find_differences(text1, text2)
        
        assert len(diffs) > 0
        assert any(d[type] == replace and quick in d[old] for d in diffs)
        assert any(d[type] == replace and jumps in d[old] for d in diffs)
    
    def test_fuzzy_match(self):
        Test fuzzy text matching.
        text = python programming
        
        # Close matches
        assert fuzzy_match(text, python programing, threshold=0.9)
        assert fuzzy_match(text, Python Programming, threshold=0.9)
        
        # Not close enough
        assert not fuzzy_match(text, java programming, threshold=0.9)
        
        # With list of candidates
        candidates = [java programming, python development, python programming!]
        matches = fuzzy_match(text, candidates, threshold=0.8, return_scores=True)
        assert len(matches) == 2
        assert matches[0][0] == python programming!
    
    def test_longest_common_substring(self):
        Test finding longest common substring.
        text1 = The quick brown fox
        text2 = A quick brown dog
        
        lcs = longest_common_substring(text1, text2)
        assert lcs == quick brown
        
        # No common substring
        text3 = xyz
        lcs = longest_common_substring(text1, text3)
        assert lcs == 


class TestTextGeneration:
    Test text generation functions.
    
    def test_generate_slug(self):
        Test slug generation.
        # Basic slug
        title = Hello World! This is a Test
        slug = generate_slug(title)
        assert slug == hello-world-this-is-a-test
        
        # With special characters
        title = C++ Programming: A Complete Guide (2024)
        slug = generate_slug(title)
        assert slug == c-programming-a-complete-guide-2024
        
        # With max length
        title = This is a very long title that needs to be truncated
        slug = generate_slug(title, max_length=20)
        assert len(slug) <= 20
        assert not slug.endswith(-)
    
    def test_generate_excerpt(self):
        Test excerpt generation.
        text = 
        This is the first paragraph of the article. It contains
        important information that should be in the excerpt.
        
        This is the second paragraph with more details that might
        not fit in a short excerpt.
        
        And here's the third paragraph with conclusions.
        
        
        # Basic excerpt
        excerpt = generate_excerpt(text, max_length=100)
        assert len(excerpt) <= 100
        assert excerpt.endswith(...)
        assert first paragraph in excerpt
        
        # Sentence boundary
        excerpt = generate_excerpt(text, max_length=100, at_sentence_boundary=True)
        assert excerpt.endswith(.)
    
    def test_generate_summary(self):
        Test summary generation.
        text = 
        The Python programming language is widely used. It is known
        for its simplicity. Python has many applications. It is used
        in web development. It is used in data science. It is used
        in machine learning. Python has a large community. The community
        creates many libraries. These libraries make development easier.
        
        
        # Key sentences summary
        summary = generate_summary(text, max_sentences=3)
        sentences = summary.split(. )
        assert len(sentences) <= 3
        
        # Should include important sentences
        assert Python in summary
        assert widely used in summary or many applications in summary


class TestUnicodeHandling:
    Test Unicode handling functions.
    
    def test_remove_accents(self):
        Test accent removal.
        assert remove_accents(café) == cafe
        assert remove_accents(naïve) == naive
        assert remove_accents(Zürich) == Zurich
        assert remove_accents(piñata) == pinata
        
        # Keep non-Latin scripts
        assert remove_accents(café 咖啡) == cafe 咖啡
    
    def test_transliterate(self):
        Test transliteration.
        # Basic Latin
        assert transliterate(café) == cafe
        
        # Greek
        assert transliterate(Ελληνικά) == Ellinika
        
        # Cyrillic
        assert transliterate(Привет) == Privet
        
        # Mixed scripts
        assert transliterate(Hello мир) == Hello mir
    
    def test_normalize_unicode(self):
        Test Unicode normalization.
        # Composed vs decomposed
        composed = é  # Single character
        decomposed = é  # e + combining accent
        
        assert normalize_unicode(composed, form=NFC) == normalize_unicode(decomposed, form=NFC)
        
        # Different normalization forms
        text = Café
        nfc = normalize_unicode(text, form=NFC)
        nfd = normalize_unicode(text, form=NFD)
        
        assert len(nfc) < len(nfd)  # NFC is shorter
        assert nfc == Café


class TestAdvancedTextProcessing:
    Test advanced text processing scenarios.
    
    def test_multilingual_processing(self):
        Test processing multilingual text.
        text = Hello world! Bonjour le monde! 你好世界! مرحبا بالعالم!
        
        # Clean while preserving scripts
        cleaned = clean_text(text, preserve_scripts=[Han, Arabic])
        assert Hello in cleaned
        assert 你好世界 in cleaned
        assert مرحبا in cleaned
    
    def test_emoji_handling(self):
        Test emoji handling.
        text = Hello 👋 World 🌍! I love Python 🐍
        
        # Remove emojis
        no_emoji = clean_text(text, remove_emojis=True)
        assert 👋 not in no_emoji
        assert Hello World in no_emoji
        
        # Extract emojis
        emojis = extract_emojis(text)
        assert 👋 in emojis
        assert 🌍 in emojis
        assert 🐍 in emojis
        
        # Replace emojis
        replaced = replace_emojis(text, replacement=[emoji])
        assert replaced == Hello [emoji] World [emoji]! I love Python [emoji]
    
    def test_text_statistics(self):
        Test comprehensive text statistics.
        text = 
        This is a sample text. It contains multiple sentences!
        Some sentences are questions? Others are statements.
        
        This is a new paragraph. It has its own content.
        
        
        stats = calculate_text_statistics(text)
        
        assert stats[word_count] > 0
        assert stats[sentence_count] == 6
        assert stats[paragraph_count] == 2
        assert stats[average_words_per_sentence] > 0
        assert stats[unique_words] > 0
        assert stats[lexical_diversity] > 0
    
    def test_smart_truncation(self):
        Test smart text truncation.
        text = Dr. Smith went to the U.S.A. He arrived at 3 p.m. The meeting was important.
        
        # Should not break at abbreviation periods
        truncated = truncate_text(text, 50, at_sentence_boundary=True)
        assert not truncated.endswith(Dr.)
        assert not truncated.endswith(U.S.)
        assert truncated.endswith(.)
    
    def test_text_sanitization(self):
        Test text sanitization for security.
        # SQL injection attempt
        text = '; DROP TABLE users; --
        sanitized = sanitize_for_sql(text)
        assert DROP TABLE not in sanitized
        
        # XSS attempt
        text = <script>alert('xss')</script>Hello
        sanitized = sanitize_for_html(text)
        assert <script> not in sanitized
        assert Hello in sanitized
        
        # Path traversal
        text = ../../etc/passwd
        sanitized = sanitize_path(text)
        assert .. not in sanitized


class TestPerformanceOptimization:
    Test performance of text processing functions.
    
    def test_large_text_processing(self):
        Test processing large texts efficiently.
        # Generate large text
        large_text =  .join([This is sentence number {}..format(i) for i in range(10000)])
        
        # Should handle large text without issues
        start_time = datetime.now()
        words = count_words(large_text)
        sentences = count_sentences(large_text)
        duration = (datetime.now() - start_time).total_seconds()
        
        assert words > 0
        assert sentences == 10000
        assert duration < 1.0  # Should be fast
    
    def test_batch_processing(self):
        Test batch processing of multiple texts.
        texts = [fThis is text number {i}. for i in range(1000)]
        
        # Batch clean
        start_time = datetime.now()
        cleaned = batch_clean_text(texts)
        duration = (datetime.now() - start_time).total_seconds()
        
        assert len(cleaned) == 1000
        assert duration < 1.0  # Should be efficient
    
    def test_streaming_processing(self):
        Test streaming text processing.
        def text_generator():
            for i in range(1000):
                yield fLine {i}: This is a test line.\n
        
        # Process stream
        word_count = 0
        for line in stream_process_text(text_generator()):
            word_count += count_words(line)
        
        assert word_count > 0