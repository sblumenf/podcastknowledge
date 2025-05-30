"""
Tests for knowledge extraction functionality
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import List

from src.core.models import Entity, Insight, Quote, EntityType, InsightType, QuoteType
from src.core.interfaces import LLMProvider
from src.processing.extraction import KnowledgeExtractor


class TestKnowledgeExtractor:
    """Test suite for KnowledgeExtractor class"""
    
    @pytest.fixture
    def mock_llm_provider(self):
        """Create mock LLM provider"""
        provider = Mock(spec=LLMProvider)
        return provider
    
    @pytest.fixture
    def extractor(self, mock_llm_provider):
        """Create KnowledgeExtractor instance"""
        return KnowledgeExtractor(
            llm_provider=mock_llm_provider,
            use_large_context=True,
            max_retries=2
        )
    
    @pytest.fixture
    def sample_text(self):
        """Sample transcript text"""
        return """
        Host: Today we're discussing artificial intelligence with Dr. Jane Smith.
        Dr. Smith: AI is transforming healthcare in remarkable ways. Machine learning 
        algorithms can now diagnose diseases with 95% accuracy.
        Host: That's incredible! What about ethical concerns?
        Dr. Smith: We must ensure AI systems are transparent and unbiased.
        """
    
    def test_extract_entities_success(self, extractor, mock_llm_provider, sample_text):
        """Test successful entity extraction"""
        # Mock LLM response
        mock_response = """
        Entities found:
        1. **Dr. Jane Smith** - Type: PERSON - Expert in AI discussing healthcare applications
        2. **artificial intelligence** - Type: TECHNOLOGY - Main topic of discussion
        3. **Machine learning** - Type: TECHNOLOGY - Subset of AI used for diagnosis
        4. **healthcare** - Type: CONCEPT - Industry being transformed by AI
        """
        mock_llm_provider.complete.return_value = mock_response
        
        entities = extractor.extract_entities(sample_text)
        
        assert len(entities) == 4
        assert all(isinstance(e, Entity) for e in entities)
        assert any(e.name == "Dr. Jane Smith" and e.entity_type == EntityType.PERSON for e in entities)
        assert any(e.name == "artificial intelligence" and e.entity_type == EntityType.TECHNOLOGY for e in entities)
        
        # Verify prompt was called
        mock_llm_provider.complete.assert_called_once()
        call_args = mock_llm_provider.complete.call_args[0][0]
        assert "Extract named entities" in call_args
        assert sample_text in call_args
    
    def test_extract_entities_with_retry(self, extractor, mock_llm_provider, sample_text):
        """Test entity extraction with retry on failure"""
        # First call fails, second succeeds
        mock_llm_provider.complete.side_effect = [
            Exception("API error"),
            "1. **AI** - Type: TECHNOLOGY - Artificial intelligence"
        ]
        
        entities = extractor.extract_entities(sample_text)
        
        assert len(entities) == 1
        assert entities[0].name == "AI"
        assert mock_llm_provider.complete.call_count == 2
    
    def test_extract_entities_max_retries_exceeded(self, extractor, mock_llm_provider, sample_text):
        """Test entity extraction fails after max retries"""
        mock_llm_provider.complete.side_effect = Exception("API error")
        
        entities = extractor.extract_entities(sample_text)
        
        assert entities == []
        assert mock_llm_provider.complete.call_count == 2  # max_retries
    
    def test_extract_insights_success(self, extractor, mock_llm_provider, sample_text):
        """Test successful insight extraction"""
        sample_entities = [
            Entity(name="AI", entity_type=EntityType.TECHNOLOGY, confidence=0.9),
            Entity(name="healthcare", entity_type=EntityType.CONCEPT, confidence=0.8)
        ]
        
        mock_response = """
        Key Insights:
        1. **AI is transforming healthcare** - AI technology is revolutionizing medical diagnosis
        2. **95% accuracy in diagnosis** - Machine learning achieves high accuracy in disease detection
        3. **Ethical concerns exist** - Need for transparency and unbiased AI systems
        """
        mock_llm_provider.complete.return_value = mock_response
        
        insights = extractor.extract_insights(sample_text, sample_entities)
        
        assert len(insights) == 3
        assert all(isinstance(i, Insight) for i in insights)
        assert any("transforming healthcare" in i.content for i in insights)
        assert any("95% accuracy" in i.content for i in insights)
    
    def test_extract_quotes_success(self, extractor, mock_llm_provider, sample_text):
        """Test successful quote extraction"""
        mock_response = """
        Notable Quotes:
        1. "AI is transforming healthcare in remarkable ways" - Dr. Smith
           Context: Discussing AI impact
           Type: INSIGHT
           
        2. "Machine learning algorithms can now diagnose diseases with 95% accuracy" - Dr. Smith
           Context: Specific capability
           Type: FACT
        """
        mock_llm_provider.complete.return_value = mock_response
        
        quotes = extractor.extract_quotes(sample_text)
        
        assert len(quotes) == 2
        assert all(isinstance(q, Quote) for q in quotes)
        assert quotes[0].speaker == "Dr. Smith"
        assert quotes[0].type == QuoteType.INSIGHT
        assert quotes[1].type == QuoteType.FACT
    
    def test_extract_topics_success(self, extractor, mock_llm_provider, sample_text):
        """Test successful topic extraction"""
        sample_entities = [Entity(name="AI", entity_type=EntityType.TECHNOLOGY, confidence=0.9)]
        sample_insights = [Insight(content="AI transforms healthcare", type=InsightType.TREND, confidence=0.8)]
        
        mock_response = """
        Main Topics:
        1. AI in Healthcare - Discussion of artificial intelligence applications in medical field
        2. Machine Learning Diagnosis - How ML algorithms achieve high accuracy
        3. AI Ethics - Concerns about transparency and bias
        """
        mock_llm_provider.complete.return_value = mock_response
        
        topics = extractor.extract_topics(sample_text, sample_entities, sample_insights)
        
        assert len(topics) == 3
        assert all(isinstance(t, dict) for t in topics)
        assert any("AI in Healthcare" in t.get('name', '') for t in topics)
    
    def test_extract_all(self, extractor, mock_llm_provider, sample_text):
        """Test extract_all method"""
        # Mock all extraction responses
        mock_llm_provider.complete.side_effect = [
            # Entities response
            "1. **AI** - Type: TECHNOLOGY - Artificial intelligence",
            # Insights response
            "1. **AI transforms healthcare** - Revolutionary impact on medical field",
            # Quotes response
            '"AI is transforming healthcare" - Dr. Smith\nContext: Main thesis\nType: INSIGHT',
            # Topics response
            "1. AI in Healthcare - Main discussion topic"
        ]
        
        result = extractor.extract_all(sample_text)
        
        assert 'entities' in result
        assert 'insights' in result
        assert 'quotes' in result
        assert 'topics' in result
        
        assert len(result['entities']) == 1
        assert len(result['insights']) == 1
        assert len(result['quotes']) == 1
        assert len(result['topics']) == 1
        
        assert mock_llm_provider.complete.call_count == 4
    
    def test_use_small_context(self, mock_llm_provider):
        """Test extractor with small context window"""
        extractor = KnowledgeExtractor(
            llm_provider=mock_llm_provider,
            use_large_context=False
        )
        
        # Should use different prompt format
        mock_llm_provider.complete.return_value = "1. **Entity** - Type: CONCEPT"
        
        entities = extractor.extract_entities("Test text")
        
        # Check that small context prompt is used
        call_args = mock_llm_provider.complete.call_args[0][0]
        assert "smaller context window" in call_args or "Focus on" in call_args
    
    def test_parse_entity_response_variations(self, extractor, mock_llm_provider):
        """Test parsing various entity response formats"""
        test_cases = [
            # Format 1: Numbered list with descriptions
            """
            1. Apple Inc. - Type: COMPANY - Technology company
            2. Tim Cook - Type: PERSON - CEO of Apple
            """,
            # Format 2: Bullet points
            """
            - Apple Inc. (COMPANY): Technology company
            - Tim Cook (PERSON): CEO of Apple
            """,
            # Format 3: JSON-like
            """
            Entities:
            - Name: Apple Inc., Type: COMPANY, Description: Technology company
            - Name: Tim Cook, Type: PERSON, Description: CEO of Apple
            """
        ]
        
        for response in test_cases:
            mock_llm_provider.complete.return_value = response
            entities = extractor.extract_entities("Apple CEO Tim Cook announced...")
            
            assert len(entities) >= 2
            assert any(e.name == "Apple Inc." or e.name == "Apple" for e in entities)
            assert any(e.name == "Tim Cook" for e in entities)
    
    def test_confidence_assignment(self, extractor, mock_llm_provider):
        """Test confidence score assignment"""
        mock_response = """
        1. **Quantum Computing** - Type: TECHNOLOGY - Mentioned frequently (5 times)
        2. **John Doe** - Type: PERSON - Mentioned once briefly
        """
        mock_llm_provider.complete.return_value = mock_response
        
        entities = extractor.extract_entities("Discussion about quantum computing...")
        
        # Entity mentioned more should have higher confidence
        quantum = next((e for e in entities if "Quantum" in e.name), None)
        john = next((e for e in entities if "John" in e.name), None)
        
        assert quantum is not None
        assert john is not None
        assert quantum.confidence > john.confidence
    
    def test_empty_text_handling(self, extractor, mock_llm_provider):
        """Test handling of empty text"""
        entities = extractor.extract_entities("")
        assert entities == []
        
        insights = extractor.extract_insights("", [])
        assert insights == []
        
        quotes = extractor.extract_quotes("")
        assert quotes == []
        
        topics = extractor.extract_topics("", [], [])
        assert topics == []
    
    def test_prompt_building_methods(self, extractor, sample_text):
        """Test prompt building methods"""
        # Test entity prompt
        entity_prompt = extractor._build_entity_prompt(sample_text)
        assert "Extract named entities" in entity_prompt
        assert sample_text in entity_prompt
        assert "Entity Types to Extract" in entity_prompt
        
        # Test insight prompt
        entities = [Entity(name="AI", entity_type=EntityType.TECHNOLOGY, confidence=0.9)]
        insight_prompt = extractor._build_insight_prompt(sample_text, entities)
        assert "extract key insights" in insight_prompt
        assert "AI" in insight_prompt
        
        # Test quote prompt
        quote_prompt = extractor._build_quote_prompt(sample_text)
        assert "Extract notable quotes" in quote_prompt
        
        # Test topic prompt
        insights = [Insight(content="Test insight", type=InsightType.TREND, confidence=0.8)]
        topic_prompt = extractor._build_topic_prompt(sample_text, entities, insights)
        assert "identify the main topics" in topic_prompt
    
    def test_parsing_methods(self, extractor):
        """Test individual parsing methods"""
        # Test entity parsing
        entity_response = "1. **Test Entity** - Type: CONCEPT - A test entity"
        entities = extractor._parse_entity_response(entity_response)
        assert len(entities) == 1
        assert entities[0].name == "Test Entity"
        assert entities[0].entity_type == EntityType.CONCEPT
        
        # Test insight parsing
        insight_response = "1. **Key insight** - This is an important finding"
        insights = extractor._parse_insight_response(insight_response, [])
        assert len(insights) == 1
        assert "Key insight" in insights[0].content
        
        # Test quote parsing
        quote_response = '"Important quote" - Speaker\nContext: Test\nType: INSIGHT'
        quotes = extractor._parse_quote_response(quote_response)
        assert len(quotes) == 1
        assert quotes[0].text == "Important quote"
        assert quotes[0].speaker == "Speaker"
        
        # Test topic parsing
        topic_response = "1. Main Topic - Description of the topic"
        topics = extractor._parse_topic_response(topic_response)
        assert len(topics) == 1
        assert topics[0]['name'] == "Main Topic"