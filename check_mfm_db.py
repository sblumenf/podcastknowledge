#!/usr/bin/env python3
"""Check if the My First Million database has content."""

from neo4j import GraphDatabase
import os

# Connect to My First Million database
uri = "bolt://localhost:7688"
username = "neo4j"
password = os.environ.get("NEO4J_PASSWORD", "password")
database = "my_first_million"

driver = GraphDatabase.driver(uri, auth=(username, password))

try:
    # First try the specific database name
    with driver.session(database=database) as session:
        # Count all nodes
        result = session.run("MATCH (n) RETURN labels(n) as labels, count(n) as count")
        
        print(f"=== MY FIRST MILLION DATABASE CONTENT (database: {database}) ===\n")
        
        total_nodes = 0
        for record in result:
            labels = record["labels"]
            count = record["count"]
            if labels:
                label = labels[0]
                print(f"{label}: {count}")
                total_nodes += count
        
        if total_nodes == 0:
            print("Database is EMPTY - no nodes found")
        else:
            print(f"\nTotal nodes: {total_nodes}")
            
            # Get some sample episodes if they exist
            episodes = session.run("MATCH (e:Episode) RETURN e.title as title LIMIT 5").data()
            if episodes:
                print("\nSample episodes:")
                for ep in episodes:
                    print(f"  - {ep['title']}")
                    
except Exception as e:
    print(f"Error with database '{database}': {e}")
    print(f"\nTrying default database...")
    
    try:
        # Try default database
        with driver.session(database="neo4j") as session:
            # List databases first
            with driver.session(database="system") as sys_session:
                dbs = sys_session.run("SHOW DATABASES").data()
                print("\nAvailable databases on port 7688:")
                for db in dbs:
                    print(f"  - {db['name']} (status: {db.get('currentStatus', 'unknown')})")
            
            # Check default database content
            result = session.run("MATCH (n) RETURN labels(n)[0] as label, count(n) as count")
            
            print(f"\n=== DEFAULT DATABASE CONTENT (port 7688) ===\n")
            
            total = 0
            for record in result:
                if record["label"]:
                    print(f"{record['label']}: {record['count']}")
                    total += record["count"]
                    
            if total == 0:
                print("Default database is EMPTY")
            else:
                print(f"\nTotal nodes: {total}")
                
    except Exception as e2:
        print(f"Error connecting to port 7688: {e2}")
        
finally:
    driver.close()