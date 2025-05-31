#!/usr/bin/env python3
"""
Test script to verify Neo4j connection
Run this after installing Neo4j to verify connectivity
"""

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_connection():
    """Test Neo4j database connection"""
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD')
    
    if not password:
        print("ERROR: NEO4J_PASSWORD not set in .env file")
        print("Please edit .env and add your Neo4j password")
        return False
    
    print(f"Testing connection to {uri}")
    print(f"User: {user}")
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        print("✅ Connection successful!")
        
        # Run a simple test query
        with driver.session() as session:
            result = session.run("RETURN 1 AS test")
            record = result.single()
            if record['test'] == 1:
                print("✅ Test query successful!")
        
        driver.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure Neo4j is running")
        print("2. Check that the password in .env matches your Neo4j password")
        print("3. Verify Neo4j is accessible at bolt://localhost:7687")
        return False

if __name__ == "__main__":
    test_connection()