#!/usr/bin/env python3
"""
Detailed analysis of synchronization between VTT files and Neo4j database
"""

import os
from typing import List, Set, Dict, Any
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from datetime import datetime
import re

def get_vtt_files(directory: str) -> Dict[str, str]:
    """Get all VTT files from the specified directory with normalized titles"""
    vtt_files = {}
    for filename in os.listdir(directory):
        if filename.endswith('.vtt'):
            # Extract title from filename (remove date prefix and .vtt extension)
            # Pattern: YYYY-MM-DD_Title_Here.vtt
            match = re.match(r'^\d{4}-\d{2}-\d{2}_(.+)\.vtt$', filename)
            if match:
                title = match.group(1).replace('_', ' ')
                # Handle special characters
                title = title.replace('&', 'and')
                vtt_files[filename] = title
    return vtt_files

def get_episode_schema(driver) -> Dict[str, int]:
    """Get the schema of Episode nodes - what properties they have"""
    query = """
    MATCH (e:Episode)
    WITH e, keys(e) as props
    UNWIND props as prop
    RETURN DISTINCT prop, count(*) as count
    ORDER BY prop
    """
    try:
        with driver.session() as session:
            result = session.run(query)
            schema = {}
            for record in result:
                schema[record['prop']] = record['count']
            return schema
    except ServiceUnavailable as e:
        print(f"Database error: {e}")
        return {}

def get_episodes_detailed(driver) -> List[dict]:
    """Query Neo4j for all episodes with all available properties"""
    query = """
    MATCH (e:Episode)
    RETURN e
    ORDER BY e.title
    """
    try:
        with driver.session() as session:
            result = session.run(query)
            episodes = []
            for record in result:
                episode_node = record['e']
                episode_dict = dict(episode_node)
                episodes.append(episode_dict)
            return episodes
    except ServiceUnavailable as e:
        print(f"Database error: {e}")
        return []

def get_duplicate_episodes(driver) -> List[dict]:
    """Find duplicate episodes by title"""
    query = """
    MATCH (e:Episode)
    WITH e.title as title, collect(e) as episodes, count(e) as count
    WHERE count > 1
    RETURN title, count, [ep in episodes | id(ep)] as node_ids
    ORDER BY count DESC, title
    """
    try:
        with driver.session() as session:
            result = session.run(query)
            duplicates = []
            for record in result:
                duplicates.append({
                    'title': record['title'],
                    'count': record['count'],
                    'node_ids': record['node_ids']
                })
            return duplicates
    except ServiceUnavailable as e:
        print(f"Database error: {e}")
        return []

def normalize_title(title: str) -> str:
    """Normalize a title for comparison"""
    # Convert to lowercase and remove extra spaces
    normalized = title.lower().strip()
    # Replace common variations
    normalized = normalized.replace('&', 'and')
    normalized = normalized.replace(':', '')
    normalized = normalized.replace('  ', ' ')
    return normalized

def find_title_matches(vtt_files: Dict[str, str], episodes: List[dict]) -> Dict[str, List[str]]:
    """Find matches between VTT files and episodes by normalized title"""
    matches = {}
    
    # Create normalized title maps
    vtt_normalized = {filename: normalize_title(title) for filename, title in vtt_files.items()}
    
    for episode in episodes:
        if 'title' in episode and episode['title']:
            episode_normalized = normalize_title(episode['title'])
            
            # Find matching VTT files
            matching_files = []
            for filename, vtt_norm_title in vtt_normalized.items():
                if episode_normalized == vtt_norm_title:
                    matching_files.append(filename)
            
            if matching_files:
                matches[episode['title']] = matching_files
    
    return matches

def generate_detailed_report(vtt_files: Dict[str, str], episodes: List[dict], 
                           schema: Dict[str, int], duplicates: List[dict],
                           title_matches: Dict[str, List[str]]) -> None:
    """Generate a comprehensive synchronization report"""
    
    print("=" * 80)
    print("DETAILED VTT FILES AND NEO4J DATABASE SYNCHRONIZATION REPORT")
    print("=" * 80)
    print(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("SUMMARY")
    print("-" * 40)
    print(f"Total VTT files on disk: {len(vtt_files)}")
    print(f"Total episodes in Neo4j: {len(episodes)}")
    print(f"Duplicate episodes in database: {sum(d['count'] - 1 for d in duplicates)}")
    print(f"Episodes with title matches to VTT files: {len(title_matches)}")
    print()
    
    print("EPISODE NODE SCHEMA (Properties and their occurrence)")
    print("-" * 40)
    if schema:
        for prop, count in sorted(schema.items()):
            print(f"  {prop}: {count} episodes")
    else:
        print("  No schema information available")
    print()
    
    print("VTT FILES ON DISK")
    print("-" * 40)
    for filename, title in sorted(vtt_files.items()):
        print(f"  File: {filename}")
        print(f"    Title: {title}")
    print()
    
    print("EPISODES IN DATABASE")
    print("-" * 40)
    if episodes:
        for i, episode in enumerate(episodes, 1):
            print(f"  Episode {i}:")
            for key, value in sorted(episode.items()):
                if value is not None:
                    print(f"    {key}: {value}")
            print()
    else:
        print("  No episodes found")
    print()
    
    print("DUPLICATE EPISODES IN DATABASE")
    print("-" * 40)
    if duplicates:
        for dup in duplicates:
            print(f"  Title: {dup['title']}")
            print(f"    Count: {dup['count']} instances")
            print(f"    Node IDs: {dup['node_ids']}")
    else:
        print("  No duplicates found")
    print()
    
    print("TITLE-BASED MATCHES (Episodes that match VTT files by title)")
    print("-" * 40)
    if title_matches:
        for episode_title, vtt_files_list in sorted(title_matches.items()):
            print(f"  Episode: {episode_title}")
            for vtt_file in vtt_files_list:
                print(f"    ✓ Matches: {vtt_file}")
    else:
        print("  No title matches found")
    print()
    
    # Find unmatched VTT files
    matched_vtt_files = set()
    for vtt_list in title_matches.values():
        matched_vtt_files.update(vtt_list)
    
    unmatched_vtt = set(vtt_files.keys()) - matched_vtt_files
    
    print("VTT FILES WITHOUT DATABASE MATCH")
    print("-" * 40)
    if unmatched_vtt:
        for filename in sorted(unmatched_vtt):
            print(f"  ⚠ {filename}")
            print(f"     Expected title: {vtt_files[filename]}")
    else:
        print("  All VTT files have matching episodes")
    print()
    
    print("RECOMMENDATIONS")
    print("-" * 40)
    print("1. Episodes in the database are missing 'filename' and 'date' properties")
    print("2. There are duplicate episodes that should be deduplicated")
    print("3. Some VTT files don't match any episodes - verify title normalization")
    print("4. Consider adding episode_id and filename properties during ingestion")

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
        
        # Get episode schema
        print("Analyzing episode schema...")
        schema = get_episode_schema(driver)
        
        # Get episodes from database
        print("Querying episodes from database...")
        episodes = get_episodes_detailed(driver)
        
        # Find duplicates
        print("Checking for duplicate episodes...")
        duplicates = get_duplicate_episodes(driver)
        
        # Find title matches
        print("Matching VTT files to episodes by title...")
        title_matches = find_title_matches(vtt_files, episodes)
        
        # Generate report
        generate_detailed_report(vtt_files, episodes, schema, duplicates, title_matches)
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure Neo4j is running and credentials are correct.")
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    main()