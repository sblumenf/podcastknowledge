#!/usr/bin/env python3
"""Analyze episode segment counts and meaningful unit creation patterns."""

import sys
import os
from pathlib import Path
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig

def analyze_episodes():
    """Analyze episode segment counts and meaningful units."""
    
    # Initialize connection
    config = PipelineConfig()
    storage = GraphStorageService(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password
    )
    
    try:
        # Connect to database
        storage.connect()
        print("Connected to Neo4j database")
        print("\n" + "="*80)
        
        # Query episodes with segment counts
        with storage.session() as session:
            # Get all episodes with segment count
            result = session.run("""
                MATCH (e:Episode)
                WHERE e.segment_count IS NOT NULL
                RETURN e.id as episode_id,
                       e.title as title,
                       e.segment_count as segment_count,
                       e.duration as duration,
                       e.processing_status as status,
                       e.processed_at as processed_at
                ORDER BY e.segment_count DESC
            """)
            episodes = list(result)
            
            print(f"Found {len(episodes)} episodes with segment counts\n")
            
            # Analyze each episode
            for episode in episodes:
                episode_id = episode['episode_id']
                segment_count = episode['segment_count']
                duration = episode.get('duration', 0)
                
                # Get meaningful unit count for this episode
                unit_result = session.run("""
                    MATCH (e:Episode {id: $episode_id})-[:HAS_UNIT]->(mu:MeaningfulUnit)
                    RETURN count(mu) as unit_count
                """, episode_id=episode_id)
                unit_count = unit_result.single()['unit_count']
                
                # Get segment details if available
                seg_result = session.run("""
                    MATCH (e:Episode {id: $episode_id})-[:HAS_SEGMENT]->(s:Segment)
                    RETURN count(s) as actual_segments
                """, episode_id=episode_id)
                actual_segments = seg_result.single()['actual_segments']
                
                # Calculate duration in minutes
                duration_minutes = duration / 60 if duration else 0
                
                # Print episode info
                print(f"Episode: {episode.get('title', episode_id)[:60]}...")
                print(f"  Segment Count: {segment_count}")
                print(f"  Actual Segments in DB: {actual_segments}")
                print(f"  Duration: {duration_minutes:.1f} minutes")
                print(f"  Meaningful Units: {unit_count}")
                print(f"  Units per 10 segments: {(unit_count / segment_count * 10):.2f}" if segment_count > 0 else "  Units per 10 segments: N/A")
                print(f"  Status: {episode.get('status', 'unknown')}")
                print("-" * 80)
                
        # Summary statistics
        print("\nSUMMARY STATISTICS:")
        print("=" * 80)
        
        with storage.session() as session:
            # Get statistics
            stats_result = session.run("""
                MATCH (e:Episode)
                WHERE e.segment_count IS NOT NULL
                WITH e.segment_count as segments, 
                     e.duration/60 as duration_min,
                     e.id as episode_id
                OPTIONAL MATCH (e2:Episode {id: episode_id})-[:HAS_UNIT]->(mu:MeaningfulUnit)
                WITH segments, duration_min, count(mu) as unit_count
                RETURN 
                    avg(segments) as avg_segments,
                    min(segments) as min_segments,
                    max(segments) as max_segments,
                    avg(duration_min) as avg_duration,
                    min(duration_min) as min_duration,
                    max(duration_min) as max_duration,
                    avg(unit_count) as avg_units,
                    min(unit_count) as min_units,
                    max(unit_count) as max_units,
                    count(*) as total_episodes
            """)
            stats = stats_result.single()
            
            print(f"Total Episodes: {stats['total_episodes']}")
            print(f"\nSegment Statistics:")
            print(f"  Average: {stats['avg_segments']:.1f}")
            print(f"  Min: {stats['min_segments']}")
            print(f"  Max: {stats['max_segments']}")
            print(f"\nDuration Statistics (minutes):")
            print(f"  Average: {stats['avg_duration']:.1f}")
            print(f"  Min: {stats['min_duration']:.1f}")
            print(f"  Max: {stats['max_duration']:.1f}")
            print(f"\nMeaningful Unit Statistics:")
            print(f"  Average: {stats['avg_units']:.1f}")
            print(f"  Min: {stats['min_units']}")
            print(f"  Max: {stats['max_units']}")
            
            # Check correlation between duration and unit creation issues
            print("\n\nANALYSIS: Episodes with Low Unit Creation")
            print("=" * 80)
            
            low_unit_result = session.run("""
                MATCH (e:Episode)
                WHERE e.segment_count IS NOT NULL
                WITH e.segment_count as segments, 
                     e.duration/60 as duration_min,
                     e.id as episode_id,
                     e.title as title
                OPTIONAL MATCH (e2:Episode {id: episode_id})-[:HAS_UNIT]->(mu:MeaningfulUnit)
                WITH segments, duration_min, episode_id, title, count(mu) as unit_count
                WHERE unit_count <= 1
                RETURN episode_id, title, segments, duration_min, unit_count
                ORDER BY segments DESC
                LIMIT 20
            """)
            
            low_unit_episodes = list(low_unit_result)
            if low_unit_episodes:
                print(f"\nFound {len(low_unit_episodes)} episodes with 0-1 meaningful units:")
                for ep in low_unit_episodes:
                    print(f"\n  {ep['title'][:60]}...")
                    print(f"    Segments: {ep['segments']}, Duration: {ep['duration_min']:.1f} min, Units: {ep['unit_count']}")
                    
                # Check if there's a pattern with duration
                long_episodes = [ep for ep in low_unit_episodes if ep['duration_min'] > 60]
                if long_episodes:
                    print(f"\n  {len(long_episodes)} of these are over 60 minutes!")
                    
        print("\n" + "="*80)
        
    except Exception as e:
        print(f"Error analyzing episodes: {e}")
        import traceback
        traceback.print_exc()
    finally:
        storage.disconnect()

if __name__ == "__main__":
    analyze_episodes()