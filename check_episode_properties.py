#!/usr/bin/env python3
"""
Check what properties are actually available on Episode nodes in the database.
"""

import os
from neo4j import GraphDatabase

# Database connection
uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
username = os.getenv("NEO4J_USERNAME", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password")
database = os.getenv("NEO4J_DATABASE", "neo4j")

driver = GraphDatabase.driver(uri, auth=(username, password))

try:
    with driver.session(database=database) as session:
        # Get all properties from Episode nodes
        result = session.run("""
            MATCH (e:Episode)
            WITH e LIMIT 1
            RETURN keys(e) as properties
        """)
        
        record = result.single()
        if record:
            properties = record["properties"]
            print("Episode node properties:")
            for prop in sorted(properties):
                print(f"  - {prop}")
        
        # Get sample episode data
        print("\nSample episode data:")
        sample_result = session.run("""
            MATCH (e:Episode)
            RETURN e
            LIMIT 1
        """)
        
        sample = sample_result.single()
        if sample:
            episode = sample["e"]
            print("\nFull episode node:")
            for key, value in episode.items():
                if key == "description" and value and len(value) > 100:
                    print(f"  {key}: {value[:100]}...")
                else:
                    print(f"  {key}: {value}")
                    
finally:
    driver.close()