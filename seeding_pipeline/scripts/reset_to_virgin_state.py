#!/usr/bin/env python3
"""Reset the entire system to virgin state - clear all databases, caches, and usage stats."""

import sys
import shutil
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig

def reset_to_virgin_state():
    """Reset the entire system to virgin state."""
    
    print("=== RESETTING SYSTEM TO VIRGIN STATE ===\n")
    
    # Get project root
    project_root = Path(__file__).parent.parent
    
    # 1. Clear Neo4j Database
    print("1. Clearing Neo4j database...")
    try:
        config = PipelineConfig()
        storage = GraphStorageService(
            uri=config.neo4j_uri,
            username=config.neo4j_username,
            password=config.neo4j_password
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
    
    # 2. Clear Speaker Cache
    print("\n2. Clearing speaker cache...")
    speaker_cache_dir = project_root / "speaker_cache"
    if speaker_cache_dir.exists():
        cache_files = list(speaker_cache_dir.glob("*.json"))
        if cache_files:
            for file in cache_files:
                file.unlink()
                print(f"   Deleted: {file.name}")
            print(f"   ✓ Cleared {len(cache_files)} speaker cache files")
        else:
            print("   ✓ Speaker cache already empty")
    else:
        print("   ✓ No speaker cache directory found")
    
    # 3. Clear Checkpoints
    print("\n3. Clearing checkpoints...")
    checkpoints_dir = project_root / "checkpoints"
    if checkpoints_dir.exists():
        checkpoint_dirs = [d for d in checkpoints_dir.iterdir() if d.is_dir()]
        if checkpoint_dirs:
            for checkpoint_dir in checkpoint_dirs:
                shutil.rmtree(checkpoint_dir)
                print(f"   Deleted: {checkpoint_dir.name}")
            print(f"   ✓ Cleared {len(checkpoint_dirs)} checkpoint directories")
        else:
            print("   ✓ Checkpoints directory already empty")
    else:
        print("   ✓ No checkpoints directory found")
    
    # 4. Clear Test Results and Metrics
    print("\n4. Clearing test results and metrics...")
    test_results_dir = project_root / "test_results"
    if test_results_dir.exists():
        result_files = list(test_results_dir.glob("*.json"))
        if result_files:
            for file in result_files:
                file.unlink()
                print(f"   Deleted: {file.name}")
            print(f"   ✓ Cleared {len(result_files)} test result files")
        else:
            print("   ✓ Test results directory already empty")
    else:
        print("   ✓ No test results directory found")
    
    # 5. Clear Benchmark Files
    print("\n5. Clearing benchmark files...")
    benchmarks_dir = project_root / "tests" / "benchmarks"
    if benchmarks_dir.exists():
        benchmark_files = list(benchmarks_dir.glob("neo4j_benchmark_*.json"))
        if benchmark_files:
            for file in benchmark_files:
                file.unlink()
                print(f"   Deleted: {file.name}")
            print(f"   ✓ Cleared {len(benchmark_files)} benchmark files")
        else:
            print("   ✓ Benchmarks directory already empty")
    else:
        print("   ✓ No benchmarks directory found")
    
    # 6. Clear any cached prompt files
    print("\n6. Clearing cached prompts...")
    cache_files_found = False
    for cache_file in project_root.rglob("*.cache"):
        cache_file.unlink()
        print(f"   Deleted: {cache_file.relative_to(project_root)}")
        cache_files_found = True
    
    if cache_files_found:
        print("   ✓ Cleared cached prompt files")
    else:
        print("   ✓ No cached prompt files found")
    
    # 7. Clear temporary analysis files
    print("\n7. Clearing temporary analysis files...")
    temp_files = [
        project_root.parent / "analyze_db.py",
        project_root.parent / "db_analysis.txt"
    ]
    
    temp_files_deleted = 0
    for temp_file in temp_files:
        if temp_file.exists():
            temp_file.unlink()
            print(f"   Deleted: {temp_file.name}")
            temp_files_deleted += 1
    
    if temp_files_deleted > 0:
        print(f"   ✓ Cleared {temp_files_deleted} temporary analysis files")
    else:
        print("   ✓ No temporary analysis files found")
    
    print("\n=== SYSTEM RESET COMPLETE ===")
    print("\nThe system is now in virgin state:")
    print("✓ Neo4j database is empty")
    print("✓ All caches have been cleared")
    print("✓ All checkpoints have been removed")
    print("✓ All metrics and benchmarks have been deleted")
    print("✓ All temporary files have been cleaned up")
    print("\nYou can now start fresh with a clean system!")

if __name__ == "__main__":
    # Confirm before proceeding
    print("WARNING: This will delete ALL data from the system!")
    print("This includes:")
    print("- All Neo4j database content")
    print("- All speaker caches")
    print("- All processing checkpoints")
    print("- All test results and benchmarks")
    print("- All temporary files")
    print()
    
    response = input("Are you sure you want to continue? (yes/no): ")
    if response.lower() == "yes":
        reset_to_virgin_state()
    else:
        print("\nOperation cancelled.")