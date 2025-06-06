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

    def __init__(
        self, start_node: MockNode, end_node: MockNode, type: str, properties: Dict[str, Any]
    ):
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

    def __init__(self, driver=None):
        self.queries = []  # Store executed queries
        self._driver = driver
        # Use driver's shared storage if available
        if driver:
            self._nodes = driver._nodes
            self._relationships = driver._relationships
        else:
            self._nodes = {}
            self._relationships = []

    def run(self, query: str, parameters: Optional[Dict] = None):
        """Mock query execution."""
        self.queries.append((query, parameters))

        # Handle common query patterns
        if "RETURN 1" in query:
            # Health check query
            return MockResult([MockRecord(health=1)])
        
        elif "CREATE (s:Segment" in query:
            # Create segment node
            node = MockNode(["Segment"], parameters or {})
            if self._driver:
                self._nodes[self._driver._node_counter] = node
                self._driver._node_counter += 1
            else:
                self._nodes[len(self._nodes)] = node
            if "RETURN s.id AS id" in query:
                return MockResult([MockRecord(id=parameters.get("id"))])
            return MockResult([MockRecord(s=node)])
        
        elif "CREATE (sp:Speaker" in query:
            # Create speaker node
            node = MockNode(["Speaker"], parameters or {})
            if self._driver:
                self._nodes[self._driver._node_counter] = node
                self._driver._node_counter += 1
            else:
                self._nodes[len(self._nodes)] = node
            return MockResult([MockRecord(sp=node)])
        
        elif "RETURN count(i) as insight_count" in query or "RETURN count(DISTINCT i) as insight_count" in query:
            # Count insights
            return MockResult([MockRecord(insight_count=10)])

        elif "MATCH (n) DETACH DELETE n" in query:
            # Clear database
            self._nodes.clear()
            self._relationships.clear()
            return MockResult([])

        elif "MATCH (v:VTTFile {id: $vtt_id})" in query:
            # Find VTT file by ID
            return MockResult([MockRecord(v=MockNode(["VTTFile"], {"id": parameters.get("vtt_id", "test_vtt_id")}))])
        
        elif "MATCH (s:Segment)-[:SPOKEN_BY]->(sp:Speaker)" in query:
            # Query segments with speakers
            segments = []
            for i in range(3):
                segment = MockNode(["Segment"], {"text": f"Segment {i}", "start_time": i * 10, "end_time": (i + 1) * 10})
                speaker = MockNode(["Speaker"], {"name": f"Speaker {i % 2}"})
                segments.append(MockRecord(s=segment, sp=speaker))
            return MockResult(segments)
        
        elif "MATCH (s:Segment) WHERE s.start_time >= $start AND s.end_time <= $end" in query:
            # Timeline query for segments within time range
            start = parameters.get("start", 0)
            end = parameters.get("end", 100)
            segments = []
            for i in range(2):
                segment = MockNode(["Segment"], {
                    "text": f"Segment in range",
                    "start_time": start + i * 10,
                    "end_time": start + (i + 1) * 10
                })
                segments.append(MockRecord(s=segment))
            return MockResult(segments)

        elif "MATCH (n:Segment)" in query and "RETURN count(n)" in query:
            # Count segments
            count = sum(1 for n in self._nodes.values() if "Segment" in n.labels)
            return MockResult([MockRecord(count=count)])
            
        elif "MATCH (n:Speaker)" in query and "RETURN count(n)" in query:
            # Count speakers
            count = sum(1 for n in self._nodes.values() if "Speaker" in n.labels)
            return MockResult([MockRecord(count=count)])

        elif "MATCH (n:VTTFile)" in query and "RETURN count(n)" in query:
            # Count VTT files
            count = sum(1 for n in self._nodes.values() if "VTTFile" in n.labels)
            return MockResult([MockRecord(count=count)])

        elif "MATCH (n)" in query and "RETURN count(n)" in query:
            # Count all nodes
            return MockResult([MockRecord(count=len(self._nodes))])

        elif "CREATE" in query and "RETURN n.id AS id" in query:
            # Generic CREATE with id return
            # Extract node type from query
            import re

            match = re.search(r"CREATE \(n:(\w+)", query)
            if match:
                node_type = match.group(1)
                node = MockNode([node_type], parameters or {})
                if self._driver:
                    self._nodes[self._driver._node_counter] = node
                    self._driver._node_counter += 1
                    self._driver._created_nodes.append(node)
                else:
                    self._nodes[len(self._nodes)] = node
                return MockResult([MockRecord(id=parameters.get("id", "generated_id"))])
            return MockResult([])

        elif "CREATE" in query and "-[r:" in query:
            # Create relationship
            rel_start = parameters.get("source_id", "unknown")
            rel_end = parameters.get("target_id", "unknown")
            # Extract relationship type
            import re

            match = re.search(r"-\[r:(\w+)", query)
            if match:
                rel_type = match.group(1)
                # Track in driver if available
                if self._driver and hasattr(self._driver, "_created_relationships"):
                    self._driver._created_relationships.append(
                        {"source": rel_start, "target": rel_end, "type": rel_type}
                    )
            return MockResult([])
        
        elif "CREATE (v:VTTFile" in query:
            # Create VTT file node
            node = MockNode(["VTTFile"], parameters or {})
            if self._driver:
                self._nodes[self._driver._node_counter] = node
                self._driver._node_counter += 1
            else:
                self._nodes[len(self._nodes)] = node
            return MockResult([MockRecord(v=node)])

        elif "shared_topic_count" in query:
            # Shared topics query - just return 0 for now (no actual shared topics in mock)
            return MockResult([MockRecord(shared_topic_count=0)])
            
        elif "RETURN count(r) as relationship_count" in query:
            # Count relationships
            return MockResult([MockRecord(relationship_count=len(self._relationships))])
        
        elif "MATCH (s:Segment) RETURN s ORDER BY s.start_time" in query:
            # Get segments ordered by time
            segments = []
            for i in range(3):
                segment = MockNode(["Segment"], {
                    "text": f"Ordered segment {i}",
                    "start_time": i * 10.0,
                    "end_time": (i + 1) * 10.0
                })
                segments.append(MockRecord(s=segment))
            return MockResult(segments)
            
        elif "MATCH" in query and "RETURN" in query:
            # Generic match query - return empty for now
            return MockResult([])

        else:
            # Default: return empty result
            return MockResult([])


class MockSession:
    """Mock Neo4j Session."""

    def __init__(self, driver=None):
        self._transaction = MockTransaction(driver)
        self._closed = False
        self._driver = driver

    def run(self, query: str, parameters: Optional[Dict] = None, **kwargs):
        """Run a query."""
        # Handle both parameters dict and kwargs
        if parameters is None and kwargs:
            parameters = kwargs
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
        # For test assertions
        self._created_nodes = []
        self._created_relationships = []
        # Shared storage across sessions
        self._nodes = {}
        self._relationships = []
        self._node_counter = 0

    def session(self, **kwargs):
        """Create a mock session."""
        if self._closed:
            raise Exception("Driver is closed")
        self._session = MockSession(driver=self)
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

    # Also patch common import paths - but only if neo4j is imported
    try:
        monkeypatch.setattr("neo4j.GraphDatabase", MockDriver)
    except:
        pass
