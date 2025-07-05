#!/usr/bin/env python3
"""Reset a specific podcast to virgin state - clear its database, caches, and usage stats."""

import sys
import shutil
from pathlib import Path
import json
import argparse
import yaml
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Add shared module to path
repo_root = Path(__file__).parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig
from src.config.podcast_config_loader import get_podcast_config_loader
from shared import parse_episode_id, normalize_for_id

def reset_podcast_to_virgin_state(podcast_id, podcast_config):
    """Reset a specific podcast to virgin state.
    
    Args:
        podcast_id: ID of the podcast to reset
        podcast_config: Configuration object for the podcast
    """
    
    podcast_name = podcast_config.name
    # Normalize podcast_id for consistent comparison with episode IDs
    normalized_podcast_id = normalize_for_id(podcast_id)
    
    print(f"=== RESETTING PODCAST '{podcast_name}' TO VIRGIN STATE ===\n")
    
    # Get project root
    project_root = Path(__file__).parent.parent
    
    # 1. Clear Neo4j Database
    print(f"1. Clearing Neo4j database for {podcast_name}...")
    try:
        # Use podcast-specific database configuration
        db_config = podcast_config.database
        neo4j_uri = db_config.uri
        
        # Use environment variables for credentials if not in podcast config
        neo4j_user = getattr(db_config, 'username', None) or os.getenv('NEO4J_USER', 'neo4j')
        neo4j_password = getattr(db_config, 'password', None) or os.getenv('NEO4J_PASSWORD', 'password')
        
        print(f"   Connecting to: {neo4j_uri}")
        
        storage = GraphStorageService(
            uri=neo4j_uri,
            username=neo4j_user,
            password=neo4j_password,
            database=db_config.database_name
        )
        
        storage.connect()
        
        # Delete all relationships and nodes
        with storage.session() as session:
            # Count before
            result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = result.single()['count']
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()['count']
            
            if node_count > 0 or rel_count > 0:
                print(f"   Deleting {node_count} nodes and {rel_count} relationships...")
                session.run("MATCH ()-[r]->() DELETE r")
                session.run("MATCH (n) DELETE n")
                print("   ✓ Neo4j database cleared")
            else:
                print("   ✓ Neo4j database already empty")
        
        storage.disconnect()
    except Exception as e:
        print(f"   ✗ Error clearing Neo4j: {e}")
    
    # 2. Clear Speaker Cache (for this podcast only)
    print(f"\n2. Clearing speaker cache for {podcast_name}...")
    speaker_cache_dir = project_root / "speaker_cache"
    if speaker_cache_dir.exists():
        cache_files = list(speaker_cache_dir.glob("*.json"))
        deleted_count = 0
        
        for cache_file in cache_files:
            try:
                # Read cache file to check if it belongs to this podcast
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                # Check if this cache entry is for our podcast
                # The cache stores podcast_name in the data
                if 'podcast_name' in cache_data:
                    if cache_data['podcast_name'].lower() == podcast_name.lower():
                        cache_file.unlink()
                        print(f"   Deleted: {cache_file.name}")
                        deleted_count += 1
                else:
                    # For older cache files without podcast_name, we can't determine ownership
                    print(f"   Skipped: {cache_file.name} (unable to determine podcast)")
                    
            except Exception as e:
                print(f"   Warning: Could not process {cache_file.name}: {e}")
        
        if deleted_count > 0:
            print(f"   ✓ Cleared {deleted_count} speaker cache files for {podcast_name}")
        else:
            print(f"   ✓ No speaker cache files found for {podcast_name}")
    else:
        print("   ✓ No speaker cache directory found")
    
    # 3. Clear Component Tracking Files (for this podcast only)
    print(f"\n3. Clearing component tracking files for {podcast_name}...")
    component_tracking_dir = project_root / "component_tracking"
    if component_tracking_dir.exists():
        tracking_files = list(component_tracking_dir.glob("*.jsonl"))
        
        for tracking_file in tracking_files:
            try:
                # Read the JSONL file and filter out entries for this podcast
                remaining_lines = []
                deleted_count = 0
                
                with open(tracking_file, 'r') as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            # Check if entry has episode_id and belongs to this podcast
                            if 'episode_id' in entry:
                                entry_podcast_id, _, _ = parse_episode_id(entry['episode_id'])
                                if entry_podcast_id == normalized_podcast_id:
                                    deleted_count += 1
                                    continue  # Skip this entry
                            remaining_lines.append(line)
                        except:
                            # Keep lines we can't parse
                            remaining_lines.append(line)
                
                # If all entries were deleted, remove the file
                if not remaining_lines:
                    tracking_file.unlink()
                    print(f"   Deleted entire file: {tracking_file.name} ({deleted_count} entries)")
                # If some entries remain, rewrite the file
                elif deleted_count > 0:
                    with open(tracking_file, 'w') as f:
                        f.writelines(remaining_lines)
                    print(f"   Removed {deleted_count} entries from: {tracking_file.name}")
                    
            except Exception as e:
                print(f"   Warning: Could not process {tracking_file.name}: {e}")
        
        print(f"   ✓ Cleaned component tracking files for {podcast_name}")
    else:
        print("   ✓ No component tracking directory found")
    
    # 4. Clear Checkpoints (for this podcast only)
    print(f"\n4. Clearing checkpoints for {podcast_name}...")
    checkpoints_dir = project_root / "checkpoints"
    if checkpoints_dir.exists():
        checkpoint_dirs = [d for d in checkpoints_dir.iterdir() if d.is_dir()]
        deleted_count = 0
        
        for checkpoint_dir in checkpoint_dirs:
            try:
                # Parse the directory name as episode_id
                dir_podcast_id, _, _ = parse_episode_id(checkpoint_dir.name)
                if dir_podcast_id == normalized_podcast_id:
                    shutil.rmtree(checkpoint_dir)
                    print(f"   Deleted: {checkpoint_dir.name}")
                    deleted_count += 1
            except:
                # If we can't parse it, skip it
                print(f"   Skipped: {checkpoint_dir.name} (unable to parse episode_id)")
        
        if deleted_count > 0:
            print(f"   ✓ Cleared {deleted_count} checkpoint directories for {podcast_name}")
        else:
            print(f"   ✓ No checkpoint directories found for {podcast_name}")
    else:
        print("   ✓ No checkpoints directory found")
    
    # Skip clearing test results, benchmarks, and other shared files
    # These are not podcast-specific and should be preserved
    print("\n5. Skipping shared files (test results, benchmarks, caches)")
    print("   ℹ️  Test results, benchmarks, and prompt caches are shared across all podcasts")
    
    print(f"\n=== PODCAST RESET COMPLETE FOR '{podcast_name}' ===")
    print(f"\nThe podcast '{podcast_name}' is now in virgin state:")
    print(f"✓ Neo4j database at {neo4j_uri} is empty")
    print(f"✓ Speaker caches for {podcast_name} have been cleared")
    print(f"✓ Component tracking entries for {podcast_name} have been removed")
    print(f"✓ Checkpoints for {podcast_name} episodes have been removed")
    print(f"\nOther podcasts remain untouched.")
    print(f"\nYou can now start fresh with {podcast_name}!")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Reset a specific podcast to virgin state",
        epilog="This will only affect the selected podcast. Other podcasts remain untouched."
    )
    
    parser.add_argument("--podcast", help="Podcast ID to reset (required unless using --list)")
    parser.add_argument("--list", action="store_true", help="List all available podcasts")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    # Load podcast configuration
    try:
        config_loader = get_podcast_config_loader()
        registry = config_loader.load()
    except Exception as e:
        print(f"Error loading podcast configuration: {e}")
        sys.exit(1)
    
    # Handle --list
    if args.list:
        print("\nAvailable podcasts:")
        for podcast in registry.podcasts:
            db_info = f"(port {podcast.database.neo4j_port})" if hasattr(podcast.database, 'neo4j_port') else ""
            status = "enabled" if podcast.enabled else "disabled"
            print(f"  {podcast.id}: {podcast.name} {db_info} [{status}]")
        sys.exit(0)
    
    # Require podcast if not listing
    if not args.podcast:
        parser.error("--podcast is required unless using --list")
    
    # Find the podcast
    podcast_config = registry.get_podcast(args.podcast)
    if not podcast_config:
        print(f"\nError: Unknown podcast '{args.podcast}'")
        print("\nAvailable podcasts:")
        for p in registry.podcasts:
            print(f"  - {p.id}")
        sys.exit(1)
    
    # Show what will be affected
    db_port = getattr(podcast_config.database, 'neo4j_port', '7687')
    print(f"\nPodcast to reset: {podcast_config.name}")
    print(f"Podcast ID: {args.podcast}")
    print(f"Database: neo4j://localhost:{db_port}")
    print()
    
    # Confirm before proceeding (unless --force)
    if not args.force:
        print(f"WARNING: This will delete ALL data for podcast '{podcast_config.name}'!")
        print("This includes:")
        print(f"- Neo4j database content at port {db_port}")
        print(f"- Speaker caches for {podcast_config.name}")
        print(f"- Component tracking entries for {podcast_config.name}")
        print(f"- Processing checkpoints for {podcast_config.name} episodes")
        print()
        print("Other podcasts will NOT be affected.")
        print()
        
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != "yes":
            print("\nOperation cancelled.")
            sys.exit(0)
    
    # Execute the reset
    reset_podcast_to_virgin_state(args.podcast, podcast_config)