"""
Pytest configuration and shared fixtures.
"""

from pathlib import Path
from unittest.mock import patch, Mock
import os
import tempfile

import pytest

from tests.utils.external_service_mocks import patch_external_services_for_tests
from tests.utils.neo4j_mocks import create_mock_neo4j_driver, patch_neo4j_for_tests

# Import fixtures for tests
pytest_plugins = [
    'tests.fixtures.neo4j_fixture',
    'tests.fixtures.vtt_fixtures'
]
@pytest.fixture(scope="session")
def project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_env():
    """Set up test environment variables."""
    original_env = os.environ.copy()
    
    # Set test environment variables
    os.environ["NEO4J_URI"] = "bolt://localhost:7688"
    os.environ["NEO4J_USERNAME"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "testpassword"
    os.environ["NEO4J_DATABASE"] = "test"
    os.environ["GOOGLE_API_KEY"] = "test_google_key"
    os.environ["OPENAI_API_KEY"] = "test_openai_key"
    os.environ["HF_TOKEN"] = "test_hf_token"
    os.environ["LOG_LEVEL"] = "ERROR"  # Quiet logs during tests
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_neo4j_driver(mocker):
    """Mock Neo4j driver for unit tests."""
    mock_driver = mocker.Mock()
    mock_session = mocker.Mock()
    mock_driver.session.return_value.__enter__.return_value = mock_session
    mock_driver.session.return_value.__exit__.return_value = None
    return mock_driver


@pytest.fixture(autouse=True)
def auto_mock_neo4j(request, monkeypatch):
    """Automatically mock Neo4j for tests unless they have the 'requires_neo4j' marker."""
    # Skip mocking if test requires real Neo4j
    if 'requires_neo4j' in request.keywords:
        return
    
    # Apply Neo4j mocks
    patch_neo4j_for_tests(monkeypatch)


@pytest.fixture(autouse=True)
def auto_mock_external_services(request, monkeypatch):
    """Automatically mock external services unless test has 'requires_external_services' marker."""
    # Skip mocking if test requires real external services
    if 'requires_external_services' in request.keywords:
        return
    
    # Apply external service mocks
    patch_external_services_for_tests(monkeypatch)
    
    # Also mock HTTP requests
    # Note: The mock_external_requests fixture code is duplicated here since we can't call fixtures directly
    def mock_get(url, *args, **kwargs):
        """Mock requests.get."""
        response = Mock()
        response.status_code = 200
        
        if "rss" in url or "feed" in url or ".xml" in url:
            from tests.utils.external_service_mocks import mock_rss_feed_response
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


# Register custom markers
def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "requires_neo4j: mark test as requiring a real Neo4j instance"
    )
    config.addinivalue_line(
        "markers", "requires_external_services: mark test as requiring real external services"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )


@pytest.fixture
def mock_llm_client(mocker):
    """Mock LLM client for unit tests."""
    mock_client = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.content = "Test LLM response"
    mock_client.invoke.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_llm_provider(mocker):
    """Mock LLM provider for unit tests - alias for mock_llm_client."""
    return mock_llm_client(mocker)


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "requires_neo4j: Tests that require Neo4j")
    config.addinivalue_line("markers", "requires_gpu: Tests that require GPU")
    config.addinivalue_line("markers", "requires_api_keys: Tests that require external API keys")
    config.addinivalue_line("markers", "requires_docker: Tests that require Docker")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "benchmark: Benchmark tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on test file location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.slow)
            
        # Mark tests that import neo4j
        if "neo4j" in item.fixturenames:
            item.add_marker(pytest.mark.requires_neo4j)


@pytest.fixture(scope="session")
def test_data_dir():
    """Provide test data directory."""
    return Path(__file__).parent / "fixtures" / "vtt_samples"


@pytest.fixture(scope="function")
def temp_dir():
    """Provide temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)