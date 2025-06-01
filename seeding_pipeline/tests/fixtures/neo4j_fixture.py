"""Neo4j test container fixtures for integration testing."""

import logging
import pytest
from testcontainers.neo4j import Neo4jContainer
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def neo4j_container():
    """Provide Neo4j container for testing."""
    logger.info("Starting Neo4j test container...")
    container = Neo4jContainer("neo4j:5.14.0")
    
    try:
        container.start()
        logger.info(f"Neo4j container started at {container.get_connection_url()}")
        yield container
    except Exception as e:
        logger.error(f"Failed to start Neo4j container: {e}")
        raise
    finally:
        try:
            container.stop()
            logger.info("Neo4j container stopped")
        except Exception as e:
            logger.warning(f"Error stopping Neo4j container: {e}")


@pytest.fixture(scope="function")
def neo4j_driver(neo4j_container):
    """Provide Neo4j driver with clean database."""
    driver = None
    try:
        # Get connection details
        connection_url = neo4j_container.get_connection_url()
        username = "neo4j"
        password = neo4j_container.NEO4J_ADMIN_PASSWORD
        
        logger.debug(f"Connecting to Neo4j at {connection_url}")
        driver = GraphDatabase.driver(
            connection_url,
            auth=(username, password)
        )
        
        # Verify connection and clear database
        with driver.session() as session:
            # Test connection
            session.run("RETURN 1")
            
            # Clear database before each test
            session.run("MATCH (n) DETACH DELETE n")
            logger.debug("Cleared Neo4j database")
        
        yield driver
        
    except ServiceUnavailable as e:
        logger.error(f"Neo4j service unavailable: {e}")
        raise
    except Exception as e:
        logger.error(f"Error setting up Neo4j driver: {e}")
        raise
    finally:
        if driver:
            driver.close()
            logger.debug("Closed Neo4j driver")