"""Memory-efficient pytest configuration and fixtures."""

import gc
import os
import pytest
import psutil
import warnings
from unittest.mock import Mock, MagicMock

# Configure memory limits
def pytest_configure(config):
    """Configure pytest for memory-efficient testing."""
    # Set memory limits
    os.environ['PYTEST_XDIST_WORKER_COUNT'] = '2'  # Limit parallel workers
    
    # Disable warnings that consume memory
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=ResourceWarning)
    
    # Configure garbage collection
    gc.set_threshold(100, 5, 5)  # More aggressive garbage collection


def pytest_runtest_setup(item):
    """Setup for each test - check memory before running."""
    gc.collect()
    memory = psutil.virtual_memory()
    if memory.percent > 80:
        pytest.skip(f"Skipping test due to high memory usage: {memory.percent}%")


def pytest_runtest_teardown(item):
    """Teardown for each test - force garbage collection."""
    gc.collect()


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Automatically cleanup after each test."""
    yield
    # Force garbage collection
    gc.collect()
    
    # Clear any caches
    import functools
    functools._lru_cache_typed_pos = {}
    
    # Close any open file handles
    import sys
    for module in list(sys.modules.values()):
        if hasattr(module, '_cleanup'):
            module._cleanup()


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver to avoid real connections."""
    driver = Mock()
    session = Mock()
    transaction = Mock()
    
    # Setup mock returns
    driver.session.return_value.__enter__ = Mock(return_value=session)
    driver.session.return_value.__exit__ = Mock(return_value=None)
    
    session.run.return_value.single.return_value = {'count': 1}
    session.execute_write.return_value = {'nodes': 1, 'relationships': 1}
    
    return driver


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider to avoid API calls."""
    provider = Mock()
    provider.generate.return_value = {
        'entities': [
            {'name': 'Test Entity', 'type': 'PERSON', 'confidence': 0.9}
        ],
        'insights': [
            {'content': 'Test insight', 'type': 'FACTUAL', 'confidence': 0.8}
        ],
        'quotes': []
    }
    return provider


@pytest.fixture
def mock_embedding_provider():
    """Mock embedding provider to avoid API calls."""
    provider = Mock()
    provider.embed.return_value = [0.1] * 768  # Gemini embedding dimensions
    provider.embed_batch.return_value = [[0.1] * 768] * 10
    return provider


@pytest.fixture(scope="session")
def temp_test_dir(tmp_path_factory):
    """Create a temporary directory for test files."""
    return tmp_path_factory.mktemp("test_data")


# Memory-efficient test markers
def pytest_collection_modifyitems(config, items):
    """Add markers to tests for better organization."""
    for item in items:
        # Mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Mark e2e tests
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        
        # Mark unit tests
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Mark slow tests
        if any(marker.name == "slow" for marker in item.iter_markers()):
            item.add_marker(pytest.mark.slow)
        
        # Mark tests that require external services
        if "neo4j" in item.name.lower() or "api" in item.name.lower():
            item.add_marker(pytest.mark.external)