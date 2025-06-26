#!/usr/bin/env python3
"""List all available databases in Neo4j."""

from neo4j import GraphDatabase
import os

# Connect to Neo4j
uri = "bolt://localhost:7687"
username = "neo4j"
password = os.environ.get("NEO4J_PASSWORD", "password")

driver = GraphDatabase.driver(uri, auth=(username, password))

try:
    with driver.session(database="system") as session:
        # List all databases
        result = session.run("SHOW DATABASES")
        
        print("=== AVAILABLE NEO4J DATABASES ===\n")
        
        databases = []
        for record in result:
            name = record["name"]
            status = record.get("currentStatus", "unknown")
            default = record.get("default", False)
            databases.append((name, status, default))
            
        for name, status, default in databases:
            default_marker = " (DEFAULT)" if default else ""
            print(f"Database: {name} - Status: {status}{default_marker}")
            
        # Now check content of the default database
        print("\n=== CHECKING DEFAULT DATABASE CONTENT ===\n")
        with driver.session(database="neo4j") as session2:
            result2 = session2.run("MATCH (n) RETURN labels(n)[0] as label, count(n) as count ORDER BY label")
            
            total = 0
            for record in result2:
                if record["label"]:
                    print(f"{record['label']}: {record['count']}")
                    total += record["count"]
                    
            if total == 0:
                print("Default database is EMPTY")
            else:
                print(f"\nTotal nodes in default database: {total}")
            
except Exception as e:
    print(f"Error: {e}")
    
finally:
    driver.close()