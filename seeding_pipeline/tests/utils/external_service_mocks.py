"""
Mock implementations for external services.

This module provides mocks for LLMs, embedding services, and other external APIs
to enable testing without real service connections.
"""

from typing import Dict, List, Any, Optional, Union
from unittest.mock import MagicMock, Mock
import json
import random

import pytest
class MockLLMResponse:
    """Mock LLM response object."""
    def __init__(self, text: str):
        self.text = text
        self.usage = {
            "prompt_tokens": random.randint(50, 200),
            "completion_tokens": random.randint(100, 500),
            "total_tokens": random.randint(150, 700)
        }


class MockGeminiModel:
    """Mock Google Gemini model."""
    
    def __init__(self, model_name: str = "gemini-pro"):
        self.model_name = model_name
        self._responses = {
            "extract_entities": self._generate_entity_response,
            "extract_insights": self._generate_insight_response,
            "extract_quotes": self._generate_quote_response,
            "default": self._generate_default_response
        }
    
    def generate_content(self, prompt: Union[str, List[str]], **kwargs):
        """Generate mock content based on prompt."""
        if isinstance(prompt, list):
            prompt = " ".join(prompt)
        
        # Determine response type based on prompt content
        if "entities" in prompt.lower() or "entity" in prompt.lower():
            response_text = self._responses["extract_entities"](prompt)
        elif "insights" in prompt.lower() or "key points" in prompt.lower():
            response_text = self._responses["extract_insights"](prompt)
        elif "quotes" in prompt.lower() or "quotations" in prompt.lower():
            response_text = self._responses["extract_quotes"](prompt)
        else:
            response_text = self._responses["default"](prompt)
        
        return MockLLMResponse(response_text)
    
    def _generate_entity_response(self, prompt: str) -> str:
        """Generate mock entity extraction response."""
        return json.dumps({
            "entities": [
                {
                    "name": "Test Person",
                    "type": "person",
                    "description": "A person mentioned in the test",
                    "confidence": 0.9
                },
                {
                    "name": "Test Company",
                    "type": "organization",
                    "description": "A company mentioned in the test",
                    "confidence": 0.85
                },
                {
                    "name": "Machine Learning",
                    "type": "concept",
                    "description": "A technical concept discussed",
                    "confidence": 0.95
                }
            ],
            "relationships": [
                {
                    "source": "Test Person",
                    "target": "Test Company",
                    "type": "works_for",
                    "confidence": 0.8
                }
            ]
        })
    
    def _generate_insight_response(self, prompt: str) -> str:
        """Generate mock insight extraction response."""
        return json.dumps({
            "insights": [
                {
                    "type": "key_point",
                    "content": "This is a key point from the discussion",
                    "importance": 0.8,
                    "evidence": "Based on the speaker's emphasis"
                },
                {
                    "type": "summary",
                    "content": "The discussion covered important topics",
                    "importance": 0.7,
                    "evidence": "Overall theme of the conversation"
                }
            ]
        })
    
    def _generate_quote_response(self, prompt: str) -> str:
        """Generate mock quote extraction response."""
        return json.dumps({
            "quotes": [
                {
                    "text": "This is a notable quote from the test",
                    "speaker": "Test Speaker",
                    "context": "During discussion about testing",
                    "type": "notable"
                }
            ]
        })
    
    def _generate_default_response(self, prompt: str) -> str:
        """Generate default mock response."""
        return "This is a mock response for testing purposes."


class MockEmbeddingModel:
    """Mock sentence transformer embedding model."""
    
    def __init__(self, model_name: str = "models/text-embedding-004"):
        self.model_name = model_name
        self.embedding_size = 768  # Gemini text-embedding-004 size
    
    def encode(self, texts: Union[str, List[str]], **kwargs) -> Union[List[float], List[List[float]]]:
        """Generate mock embeddings."""
        if isinstance(texts, str):
            # Single text - return single embedding
            return self._generate_embedding()
        else:
            # Multiple texts - return list of embeddings
            return [self._generate_embedding() for _ in texts]
    
    def _generate_embedding(self) -> List[float]:
        """Generate a mock embedding vector."""
        # Create a deterministic but varying embedding
        base = [0.1 * i for i in range(self.embedding_size)]
        # Add some random variation
        return [v + random.uniform(-0.05, 0.05) for v in base]


def create_mock_llm_service():
    """Create a mock LLM service."""
    mock_service = Mock()
    mock_service.model = MockGeminiModel()
    mock_service.generate = mock_service.model.generate_content
    return mock_service


def create_mock_embedding_service():
    """Create a mock embedding service."""
    mock_service = Mock()
    mock_service.model = MockEmbeddingModel()
    mock_service.encode = mock_service.model.encode
    mock_service.get_embedding = lambda text: mock_service.model.encode(text)
    mock_service.get_embeddings = lambda texts: mock_service.model.encode(texts)
    return mock_service


def mock_rss_feed_response(url: str) -> str:
    """Generate mock RSS feed content."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Mock Podcast Feed</title>
        <link>{url}</link>
        <description>A mock podcast feed for testing</description>
        <language>en-us</language>
        <item>
            <title>Episode 1: Introduction to Testing</title>
            <description>This is a test episode about testing</description>
            <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
            <enclosure url="{url}/episode1.mp3" length="12345678" type="audio/mpeg"/>
            <guid isPermaLink="false">episode-1-guid</guid>
        </item>
        <item>
            <title>Episode 2: Advanced Testing Techniques</title>
            <description>This episode covers advanced testing techniques</description>
            <pubDate>Mon, 08 Jan 2024 00:00:00 GMT</pubDate>
            <enclosure url="{url}/episode2.mp3" length="23456789" type="audio/mpeg"/>
            <guid isPermaLink="false">episode-2-guid</guid>
        </item>
    </channel>
</rss>"""


@pytest.fixture
def mock_llm_service():
    """Pytest fixture for mock LLM service."""
    return create_mock_llm_service()


@pytest.fixture
def mock_embedding_service():
    """Pytest fixture for mock embedding service."""
    return create_mock_embedding_service()


@pytest.fixture
def mock_external_requests(monkeypatch):
    """Mock all external HTTP requests."""
    def mock_get(url, *args, **kwargs):
        """Mock requests.get."""
        response = Mock()
        response.status_code = 200
        
        if "rss" in url or "feed" in url or ".xml" in url:
            response.text = mock_rss_feed_response(url)
            response.content = response.text.encode('utf-8')
        else:
            response.text = '{"status": "ok"}'
            response.json.return_value = {"status": "ok"}
        
        return response
    
    def mock_post(url, *args, **kwargs):
        """Mock requests.post."""
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"status": "ok", "result": "mocked"}
        return response
    
    # Patch various request libraries
    monkeypatch.setattr("requests.get", mock_get, raising=False)
    monkeypatch.setattr("requests.post", mock_post, raising=False)
    monkeypatch.setattr("urllib.request.urlopen", Mock(return_value=Mock(read=lambda: b'{"status": "ok"}')), raising=False)


def patch_external_services_for_tests(monkeypatch):
    """Patch all external services for testing."""
    # Patch Google Gemini - avoid importing to prevent IPython dependency issues
    try:
        mock_model = MockGeminiModel()
        monkeypatch.setattr("google.generativeai.GenerativeModel", lambda model_name: mock_model)
        monkeypatch.setattr("google.generativeai.configure", lambda api_key: None)
    except (ImportError, AttributeError):
        pass
    
    # Patch sentence transformers - avoid importing to prevent dependency issues  
    try:
        mock_embedding = MockEmbeddingModel()
        monkeypatch.setattr("sentence_transformers.SentenceTransformer", lambda model_name: mock_embedding)
    except (ImportError, AttributeError):
        pass
    
    # Patch common LLM providers
    try:
        monkeypatch.setattr("src.services.llm.GoogleGeminiProvider", create_mock_llm_service)
    except (ImportError, AttributeError):
        pass
    try:
        monkeypatch.setattr("src.services.embeddings.EmbeddingService", create_mock_embedding_service)
    except (ImportError, AttributeError):
        pass