"""
Comprehensive Neo4j mocking utilities for tests.

This module provides mock implementations of Neo4j components to enable
testing without a real Neo4j instance.
"""

from typing import Dict, List, Any, Optional
from unittest.mock import MagicMock, Mock
import pytest


class MockNode:
    """Mock Neo4j Node."""
    def __init__(self, labels: List[str], properties: Dict[str, Any]):
        self.labels = labels
        self.properties = properties
        self.id = id(self)  # Use object id as node id
    
    def __getitem__(self, key):
        return self.properties.get(key)
    
    def get(self, key, default=None):
        return self.properties.get(key, default)


class MockRelationship:
    """Mock Neo4j Relationship."""
    def __init__(self, start_node: MockNode, end_node: MockNode, type: str, properties: Dict[str, Any]):
        self.start_node = start_node
        self.end_node = end_node
        self.type = type
        self.properties = properties
        self.id = id(self)


class MockRecord:
    """Mock Neo4j Record."""
    def __init__(self, **kwargs):
        self._data = kwargs
        
    def __getitem__(self, key):
        return self._data[key]
    
    def get(self, key, default=None):
        return self._data.get(key, default)
    
    def data(self):
        return self._data
    
    def keys(self):
        return self._data.keys()
    
    def values(self):
        return self._data.values()
    
    def items(self):
        return self._data.items()


class MockResult:
    """Mock Neo4j Result."""
    def __init__(self, records: List[MockRecord]):
        self._records = records
        self._index = 0
    
    def single(self):
        """Return single record or None."""
        if self._records:
            return self._records[0]
        return None
    
    def data(self):
        """Return all records as list of dicts."""
        return [r.data() for r in self._records]
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self._index < len(self._records):
            record = self._records[self._index]
            self._index += 1
            return record
        raise StopIteration


class MockTransaction:
    """Mock Neo4j Transaction."""
    def __init__(self):
        self.queries = []  # Store executed queries
        self._nodes = {}  # In-memory node storage
        self._relationships = []  # In-memory relationship storage
        self._node_counter = 0
    
    def run(self, query: str, parameters: Optional[Dict] = None):
        """Mock query execution."""
        self.queries.append((query, parameters))
        
        # Handle common query patterns
        if "RETURN 1" in query:
            # Health check query
            return MockResult([MockRecord(health=1)])
        
        elif "MATCH (n) DETACH DELETE n" in query:
            # Clear database
            self._nodes.clear()
            self._relationships.clear()
            return MockResult([])
        
        elif "CREATE" in query and ":Podcast" in query:
            # Create podcast node
            node = MockNode(["Podcast"], parameters or {})
            self._nodes[self._node_counter] = node
            self._node_counter += 1
            return MockResult([MockRecord(p=node)])
        
        elif "CREATE" in query and ":Episode" in query:
            # Create episode node
            node = MockNode(["Episode"], parameters or {})
            self._nodes[self._node_counter] = node
            self._node_counter += 1
            return MockResult([MockRecord(e=node)])
        
        elif "MATCH (n:Podcast)" in query and "RETURN count(n)" in query:
            # Count podcasts
            count = sum(1 for n in self._nodes.values() if "Podcast" in n.labels)
            return MockResult([MockRecord(count=count)])
        
        elif "MATCH (n:Episode)" in query and "RETURN count(n)" in query:
            # Count episodes
            count = sum(1 for n in self._nodes.values() if "Episode" in n.labels)
            return MockResult([MockRecord(count=count)])
        
        elif "MATCH (n)" in query and "RETURN count(n)" in query:
            # Count all nodes
            return MockResult([MockRecord(count=len(self._nodes))])
        
        elif "MATCH" in query and "RETURN" in query:
            # Generic match query - return empty for now
            return MockResult([])
        
        else:
            # Default: return empty result
            return MockResult([])


class MockSession:
    """Mock Neo4j Session."""
    def __init__(self):
        self._transaction = MockTransaction()
        self._closed = False
    
    def run(self, query: str, parameters: Optional[Dict] = None):
        """Run a query."""
        return self._transaction.run(query, parameters)
    
    def execute_read(self, func, *args, **kwargs):
        """Execute a read transaction."""
        return func(self._transaction, *args, **kwargs)
    
    def execute_write(self, func, *args, **kwargs):
        """Execute a write transaction."""
        return func(self._transaction, *args, **kwargs)
    
    def close(self):
        """Close the session."""
        self._closed = True
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class MockDriver:
    """Mock Neo4j Driver."""
    def __init__(self, uri: str, auth: tuple, **kwargs):
        self.uri = uri
        self.auth = auth
        self._closed = False
        self._session = None
    
    def session(self, **kwargs):
        """Create a mock session."""
        if self._closed:
            raise Exception("Driver is closed")
        self._session = MockSession()
        return self._session
    
    def close(self):
        """Close the driver."""
        self._closed = True
        if self._session:
            self._session.close()
    
    def verify_connectivity(self):
        """Mock connectivity verification."""
        if self._closed:
            raise Exception("Driver is closed")
        return None


def create_mock_neo4j_driver(uri="bolt://localhost:7687", auth=("neo4j", "password")):
    """Create a fully configured mock Neo4j driver."""
    return MockDriver(uri, auth)


@pytest.fixture
def mock_neo4j():
    """Pytest fixture for mock Neo4j driver."""
    return create_mock_neo4j_driver()


def patch_neo4j_for_tests(monkeypatch):
    """Patch Neo4j GraphDatabase to use mocks."""
    def mock_driver(uri, auth, **kwargs):
        return create_mock_neo4j_driver(uri, auth)
    
    # Try to patch neo4j if it's available
    try:
        import neo4j
        monkeypatch.setattr("neo4j.GraphDatabase.driver", mock_driver)
    except ImportError:
        pass
    
    # Also patch common import paths
    monkeypatch.setattr("src.storage.graph_storage.GraphDatabase.driver", mock_driver, raising=False)
    monkeypatch.setattr("src.api.health.GraphDatabase.driver", mock_driver, raising=False)