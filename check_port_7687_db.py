#!/usr/bin/env python3
"""Check database content on port 7687."""

from neo4j import GraphDatabase
import os

# Connect to database on port 7687
uri = "bolt://localhost:7687"
username = "neo4j"
password = os.environ.get("NEO4J_PASSWORD", "password")

driver = GraphDatabase.driver(uri, auth=(username, password))

try:
    # Check default database
    with driver.session(database="neo4j") as session:
        # Count all nodes by label
        result = session.run("""
            MATCH (n) 
            RETURN labels(n)[0] as label, count(n) as count 
            ORDER BY count DESC
        """)
        
        print(f"=== DATABASE CONTENT ON PORT 7687 ===\n")
        
        total_nodes = 0
        node_counts = []
        for record in result:
            if record["label"]:
                label = record["label"]
                count = record["count"]
                node_counts.append((label, count))
                total_nodes += count
        
        if total_nodes == 0:
            print("Database is EMPTY - no nodes found")
        else:
            for label, count in node_counts:
                print(f"{label}: {count}")
            print(f"\nTotal nodes: {total_nodes}")
            
            # Get sample episodes if they exist
            episodes = session.run("MATCH (e:Episode) RETURN e.title as title, e.id as id LIMIT 5").data()
            if episodes:
                print("\nSample episodes:")
                for ep in episodes:
                    print(f"  - {ep['title']} (ID: {ep['id'][:50]}...)")
                    
            # Get sample podcasts if they exist
            podcasts = session.run("MATCH (p:Podcast) RETURN p.title as title, p.id as id").data()
            if podcasts:
                print("\nPodcasts:")
                for p in podcasts:
                    print(f"  - {p['title']} (ID: {p['id']})")
                    
except Exception as e:
    print(f"Error connecting to database on port 7687: {e}")
    
finally:
    driver.close()