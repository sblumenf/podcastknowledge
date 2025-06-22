#!/usr/bin/env python3
"""
Analyze synchronization between VTT files on disk and episodes in Neo4j database
"""

import os
from typing import List, Set, Tuple
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from datetime import datetime

def get_vtt_files(directory: str) -> Set[str]:
    """Get all VTT files from the specified directory"""
    vtt_files = set()
    for filename in os.listdir(directory):
        if filename.endswith('.vtt'):
            vtt_files.add(filename)
    return vtt_files

def get_episodes_from_neo4j(driver) -> List[dict]:
    """Query Neo4j for all episodes"""
    query = """
    MATCH (e:Episode)
    RETURN e.title as title, 
           e.filename as filename,
           e.episode_id as episode_id,
           e.date as date,
           e.podcast_name as podcast_name
    ORDER BY e.date DESC
    """
    try:
        with driver.session() as session:
            result = session.run(query)
            episodes = []
            for record in result:
                episodes.append({
                    'title': record['title'],
                    'filename': record['filename'],
                    'episode_id': record['episode_id'],
                    'date': record['date'],
                    'podcast_name': record['podcast_name']
                })
            return episodes
    except ServiceUnavailable as e:
        print(f"Database error: {e}")
        return []

def generate_report(vtt_files: Set[str], episodes: List[dict]) -> None:
    """Generate a detailed synchronization report"""
    
    # Extract filenames from episodes
    db_filenames = set()
    for episode in episodes:
        if episode['filename']:
            # Remove .vtt extension if present for comparison
            filename = episode['filename']
            if not filename.endswith('.vtt'):
                filename += '.vtt'
            db_filenames.add(filename)
    
    # Find differences
    in_both = vtt_files & db_filenames
    only_in_filesystem = vtt_files - db_filenames
    only_in_database = db_filenames - vtt_files
    
    # Generate report
    print("=" * 80)
    print("VTT FILES AND NEO4J DATABASE SYNCHRONIZATION REPORT")
    print("=" * 80)
    print(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("SUMMARY")
    print("-" * 40)
    print(f"Total VTT files on disk: {len(vtt_files)}")
    print(f"Total episodes in Neo4j: {len(episodes)}")
    print(f"Episodes in both: {len(in_both)}")
    print(f"VTT files NOT in database: {len(only_in_filesystem)}")
    print(f"Database entries without VTT file: {len(only_in_database)}")
    print()
    
    print("EPISODES IN BOTH FILESYSTEM AND DATABASE")
    print("-" * 40)
    if in_both:
        for filename in sorted(in_both):
            print(f"  ✓ {filename}")
    else:
        print("  None")
    print()
    
    print("VTT FILES NOT IN DATABASE")
    print("-" * 40)
    if only_in_filesystem:
        for filename in sorted(only_in_filesystem):
            print(f"  ⚠ {filename}")
    else:
        print("  None - All VTT files are in the database")
    print()
    
    print("DATABASE ENTRIES WITHOUT VTT FILE")
    print("-" * 40)
    if only_in_database:
        for filename in sorted(only_in_database):
            # Find the episode details
            episode_info = next((e for e in episodes if e['filename'] and 
                               (e['filename'] == filename or e['filename'] + '.vtt' == filename)), None)
            if episode_info:
                print(f"  ⚠ {filename}")
                print(f"     Title: {episode_info['title']}")
                print(f"     Episode ID: {episode_info['episode_id']}")
                print(f"     Date: {episode_info['date']}")
    else:
        print("  None - All database entries have corresponding VTT files")
    print()
    
    print("DETAILED EPISODE LIST FROM DATABASE")
    print("-" * 40)
    if episodes:
        for episode in episodes:
            print(f"  Episode ID: {episode['episode_id']}")
            print(f"  Title: {episode['title']}")
            print(f"  Filename: {episode['filename']}")
            print(f"  Date: {episode['date']}")
            print(f"  Podcast: {episode['podcast_name']}")
            print()
    else:
        print("  No episodes found in database")

def main():
    # Configuration
    transcript_dir = "/home/sergeblumenfeld/podcastknowledge/data/transcripts/The_Mel_Robbins_Podcast/"
    neo4j_uri = "neo4j://localhost:7687"
    neo4j_user = "neo4j"
    neo4j_password = "password"
    
    # Get VTT files
    print("Scanning filesystem for VTT files...")
    vtt_files = get_vtt_files(transcript_dir)
    
    # Connect to Neo4j
    print("Connecting to Neo4j database...")
    driver = None
    try:
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
        # Test connection
        driver.verify_connectivity()
        
        # Get episodes from database
        print("Querying episodes from database...")
        episodes = get_episodes_from_neo4j(driver)
        
        # Generate report
        generate_report(vtt_files, episodes)
        
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
        print("Make sure Neo4j is running and credentials are correct.")
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    main()