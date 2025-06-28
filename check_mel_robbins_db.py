#!/usr/bin/env python3
"""Check if the Mel Robbins database has content."""

from neo4j import GraphDatabase
import os

# Connect to Mel Robbins database
uri = "bolt://localhost:7687"
username = "neo4j"
password = os.environ.get("NEO4J_PASSWORD", "changeme")
database = "neo4j"

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
            episodes = session.run("MATCH (e:Episode) RETURN e.title as title, e.youtube_url as youtube_url LIMIT 5").data()
            if episodes:
                print("\nSample episodes:")
                for ep in episodes:
                    youtube_status = " (No YouTube URL)" if not ep.get('youtube_url') else ""
                    print(f"  - {ep['title']}{youtube_status}")

            # Check for episodes missing youtube_url
            missing_youtube_episodes_count = session.run("MATCH (e:Episode) WHERE NOT EXISTS(e.youtube_url) RETURN count(e) as count").single()["count"]
            if missing_youtube_episodes_count > 0:
                print(f"\nWARNING: {missing_youtube_episodes_count} episodes are missing a YouTube URL.")
                sample_missing = session.run("MATCH (e:Episode) WHERE NOT EXISTS(e.youtube_url) RETURN e.title as title LIMIT 3").data()
                if sample_missing:
                    print("Sample episodes missing YouTube URL:")
                    for ep in sample_missing:
                        print(f"  - {ep['title']}")
            else:
                print("\nAll episodes have a YouTube URL.")
                    
except Exception as e:
    print(f"Error connecting to database: {e}")
    print(f"URI: {uri}, Database: {database}")
    
finally:
    driver.close()