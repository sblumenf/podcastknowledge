#!/usr/bin/env python3
"""Check if indexes were created in the database."""

from neo4j import GraphDatabase
import os

# Connect to database
uri = "bolt://localhost:7687"
username = "neo4j"
password = os.environ.get("NEO4J_PASSWORD", "password")

driver = GraphDatabase.driver(uri, auth=(username, password))

try:
    with driver.session(database="neo4j") as session:
        # Check indexes
        indexes = session.run("SHOW INDEXES").data()
        print(f"\n=== INDEXES ({len(indexes)} total) ===")
        for idx in indexes:
            print(f"- {idx['name']} on {idx['labelsOrTypes']} ({idx['properties']})")
            
        # Check constraints
        constraints = session.run("SHOW CONSTRAINTS").data()
        print(f"\n=== CONSTRAINTS ({len(constraints)} total) ===")
        for const in constraints:
            print(f"- {const['name']} on {const['labelsOrTypes']}")
            
except Exception as e:
    print(f"Error: {e}")
finally:
    driver.close()