#!/usr/bin/env python3
"""Delete a single episode and all its associated data from Neo4j and filesystem."""

import sys
import shutil
from pathlib import Path
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig

def delete_episode(episode_id: str, dry_run: bool = False):
    """Delete a single episode and all its associated data.
    
    Args:
        episode_id: The episode ID to delete
        dry_run: If True, only show what would be deleted without actually deleting
    """
    
    # Determine which database to use based on episode ID
    if "My_First_Million" in episode_id:
        storage = GraphStorageService(
            uri="neo4j://localhost:7688",
            username="neo4j",
            password="password"
        )
        print(f"Using MFM database (port 7688)")
    else:
        storage = GraphStorageService(
            uri="neo4j://localhost:7687", 
            username="neo4j",
            password="password"
        )
        print(f"Using Mel Robbins database (port 7687)")
    
    try:
        # Connect to database
        storage.connect()
        print(f"Connected to Neo4j database")
        print(f"{'DRY RUN - ' if dry_run else ''}Deleting episode: {episode_id}")
        
        # Find all related data
        print("\n=== FINDING RELATED DATA ===")
        
        with storage.session() as session:
            # Count nodes to be deleted
            result = session.run("""
                MATCH (e:Episode {episode_id: $episode_id})
                OPTIONAL MATCH (e)-[:HAS_SEGMENT]->(s:Segment)
                OPTIONAL MATCH (e)-[:HAS_UNIT]->(u:MeaningfulUnit)
                OPTIONAL MATCH (u)-[:HAS_ENTITY]->(ent:Entity)
                OPTIONAL MATCH (u)-[:HAS_QUOTE]->(q:Quote)
                OPTIONAL MATCH (u)-[:HAS_INSIGHT]->(i:Insight)
                WITH e, count(DISTINCT s) as segments, count(DISTINCT u) as units,
                     count(DISTINCT ent) as entities, count(DISTINCT q) as quotes,
                     count(DISTINCT i) as insights
                RETURN e.episode_id as episode_id, segments, units, entities, quotes, insights
            """, episode_id=episode_id)
            
            record = result.single()
            if not record:
                print(f"Episode '{episode_id}' not found in database!")
                return
            
            print(f"Found episode: {record['episode_id']}")
            print(f"  Segments: {record['segments']}")
            print(f"  Meaningful Units: {record['units']}")
            print(f"  Entities: {record['entities']}")
            print(f"  Quotes: {record['quotes']}")
            print(f"  Insights: {record['insights']}")
        
        if not dry_run:
            print("\n=== DELETING FROM DATABASE ===")
            
            with storage.session() as session:
                # Delete all relationships and nodes related to this episode
                # This query deletes everything connected to the episode
                result = session.run("""
                    MATCH (e:Episode {episode_id: $episode_id})
                    OPTIONAL MATCH (e)-[:HAS_SEGMENT]->(s:Segment)
                    OPTIONAL MATCH (e)-[:HAS_UNIT]->(u:MeaningfulUnit)
                    OPTIONAL MATCH (u)-[:HAS_ENTITY]->(ent:Entity)
                    OPTIONAL MATCH (u)-[:HAS_QUOTE]->(q:Quote)
                    OPTIONAL MATCH (u)-[:HAS_INSIGHT]->(i:Insight)
                    OPTIONAL MATCH (u)-[r1]-()
                    OPTIONAL MATCH (e)-[r2]-()
                    OPTIONAL MATCH (s)-[r3]-()
                    DELETE r1, r2, r3, ent, q, i, u, s, e
                    RETURN count(*) as deleted_count
                """, episode_id=episode_id)
                
                deleted = result.single()['deleted_count']
                print(f"Deleted {deleted} graph elements")
        
        # Find and delete checkpoint files
        print("\n=== FINDING CHECKPOINT FILES ===")
        checkpoint_dir = Path(__file__).parent.parent / "checkpoints"
        if checkpoint_dir.exists():
            # Look for directories containing the episode ID
            checkpoints_found = []
            for checkpoint in checkpoint_dir.iterdir():
                if checkpoint.is_dir() and episode_id.replace('/', '_').replace(':', '_') in checkpoint.name:
                    checkpoints_found.append(checkpoint)
                    print(f"Found checkpoint: {checkpoint.name}")
            
            if checkpoints_found and not dry_run:
                print("\n=== DELETING CHECKPOINT FILES ===")
                for checkpoint in checkpoints_found:
                    shutil.rmtree(checkpoint)
                    print(f"Deleted: {checkpoint}")
        
        # Find and delete performance reports
        print("\n=== FINDING PERFORMANCE REPORTS ===")
        perf_dir = Path(__file__).parent.parent / "performance_reports"
        if perf_dir.exists():
            reports_found = []
            for report in perf_dir.glob("*.json"):
                if episode_id.replace('/', '_').replace(':', '_') in report.name:
                    reports_found.append(report)
                    print(f"Found report: {report.name}")
            
            if reports_found and not dry_run:
                print("\n=== DELETING PERFORMANCE REPORTS ===")
                for report in reports_found:
                    report.unlink()
                    print(f"Deleted: {report}")
        
        # Check processed directory
        print("\n=== CHECKING PROCESSED FILES ===")
        processed_dir = Path(__file__).parent.parent.parent / "data" / "processed"
        if processed_dir.exists():
            # This would contain any processed output files
            print(f"Check {processed_dir} for any files related to this episode")
        
        if dry_run:
            print("\n=== DRY RUN COMPLETE ===")
            print("No data was actually deleted. Remove --dry-run to perform deletion.")
        else:
            print("\n=== DELETION COMPLETE ===")
            print(f"Episode '{episode_id}' and all associated data have been removed.")
        
    except Exception as e:
        print(f"Error deleting episode: {e}")
        import traceback
        traceback.print_exc()
    finally:
        storage.disconnect()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete a single episode from the database and filesystem")
    parser.add_argument("episode_id", help="The episode ID to delete")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
    
    args = parser.parse_args()
    
    # Confirm deletion unless dry run
    if not args.dry_run:
        print(f"WARNING: This will permanently delete episode '{args.episode_id}' and all its data!")
        response = input("Are you sure? (yes/no): ")
        if response.lower() != 'yes':
            print("Deletion cancelled.")
            sys.exit(0)
    
    delete_episode(args.episode_id, args.dry_run)