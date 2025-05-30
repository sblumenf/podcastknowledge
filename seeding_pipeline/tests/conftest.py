"""
Pytest configuration and shared fixtures.
"""

import os
import pytest
from pathlib import Path


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


@pytest.fixture
def mock_llm_client(mocker):
    """Mock LLM client for unit tests."""
    mock_client = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.content = "Test LLM response"
    mock_client.invoke.return_value = mock_response
    return mock_client


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