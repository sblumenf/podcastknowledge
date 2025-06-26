#!/usr/bin/env python3
"""Check if the Mel Robbins database has content."""

from neo4j import GraphDatabase
import os

# Connect to Mel Robbins database
uri = "bolt://localhost:7687"
username = "neo4j"
password = os.environ.get("NEO4J_PASSWORD", "password")
database = "mel_robbins_podcast"

driver = GraphDatabase.driver(uri, auth=(username, password))

try:
    with driver.session(database=database) as session:
        # Count all nodes
        result = session.run("MATCH (n) RETURN labels(n) as labels, count(n) as count")
        
        print(f"=== MEL ROBBINS DATABASE CONTENT (database: {database}) ===\n")
        
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
    print(f"Error connecting to database: {e}")
    print(f"URI: {uri}, Database: {database}")
    
finally:
    driver.close()