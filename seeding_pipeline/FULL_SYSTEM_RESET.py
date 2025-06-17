#!/usr/bin/env python3
"""
FULL SYSTEM RESET - Restore to virgin state.

WARNING: This will DELETE ALL DATA from the knowledge pipeline system.
Run with caution - this action cannot be undone.
"""

import os
import sys
import shutil
import glob
from pathlib import Path
import subprocess
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemReset:
    """Complete system reset to virgin state."""
    
    def __init__(self, project_root: Path):
        """Initialize with project root directory."""
        self.project_root = project_root
        self.errors = []
        
    def confirm_reset(self) -> bool:
        """Get user confirmation before proceeding."""
        print("\n" + "="*60)
        print("FULL SYSTEM RESET - WARNING")
        print("="*60)
        print("\nThis will permanently DELETE:")
        print("  - All data in Neo4j database")
        print("  - All checkpoint files")
        print("  - All cache files")
        print("  - All speaker identification data")
        print("  - All logs and metrics")
        print("  - All temporary files")
        print("\nThis action CANNOT be undone!")
        print("="*60)
        
        response = input("\nType 'RESET EVERYTHING' to confirm: ")
        return response == "RESET EVERYTHING"
    
    def reset_neo4j(self) -> None:
        """Clear all data from Neo4j database."""
        logger.info("Resetting Neo4j database...")
        
        try:
            # Delete ALL nodes and relationships
            cmd = [
                'docker', 'exec', 'neo4j', 'cypher-shell',
                '-u', 'neo4j', '-p', 'password',
                'MATCH (n) DETACH DELETE n;'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✓ Neo4j: All nodes and relationships deleted")
            else:
                self.errors.append(f"Neo4j reset error: {result.stderr}")
            
            # Drop any indexes
            cmd_indexes = [
                'docker', 'exec', 'neo4j', 'cypher-shell',
                '-u', 'neo4j', '-p', 'password',
                'SHOW INDEXES;'
            ]
            result = subprocess.run(cmd_indexes, capture_output=True, text=True)
            
            if "no indexes" not in result.stdout.lower():
                # There are indexes to drop
                drop_cmd = [
                    'docker', 'exec', 'neo4j', 'cypher-shell',
                    '-u', 'neo4j', '-p', 'password',
                    'CALL apoc.schema.assert({}, {});'
                ]
                subprocess.run(drop_cmd, capture_output=True)
                logger.info("✓ Neo4j: All indexes dropped")
                
        except Exception as e:
            self.errors.append(f"Neo4j reset exception: {str(e)}")
    
    def clear_checkpoints(self) -> None:
        """Remove all checkpoint files."""
        logger.info("Clearing checkpoint files...")
        
        checkpoint_dir = self.project_root / "checkpoints"
        if checkpoint_dir.exists():
            try:
                # Remove all contents but keep directory
                for item in checkpoint_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                logger.info(f"✓ Cleared checkpoint directory: {checkpoint_dir}")
            except Exception as e:
                self.errors.append(f"Checkpoint clear error: {str(e)}")
    
    def clear_speaker_cache(self) -> None:
        """Remove speaker identification cache."""
        logger.info("Clearing speaker cache...")
        
        # Check multiple possible locations
        cache_locations = [
            self.project_root / "speaker_cache",
            self.project_root / "speaker_cache.db",
            self.project_root / "src" / "extraction" / "speaker_cache.db",
            self.project_root / ".speaker_cache"
        ]
        
        for cache_path in cache_locations:
            if cache_path.exists():
                try:
                    if cache_path.is_file():
                        cache_path.unlink()
                    else:
                        shutil.rmtree(cache_path)
                    logger.info(f"✓ Removed speaker cache: {cache_path}")
                except Exception as e:
                    self.errors.append(f"Speaker cache error: {str(e)}")
    
    def clear_output_directories(self) -> None:
        """Clear all output and temporary directories."""
        logger.info("Clearing output directories...")
        
        directories_to_clear = [
            "output",
            "test_data/output",
            "test_data/results",
            "test_tracking",
            "profiling_results",
            ".pytest_cache",
            "__pycache__"
        ]
        
        for dir_name in directories_to_clear:
            dir_path = self.project_root / dir_name
            if dir_path.exists():
                try:
                    shutil.rmtree(dir_path)
                    # Recreate empty directory for some
                    if dir_name in ["output", "checkpoints"]:
                        dir_path.mkdir()
                    logger.info(f"✓ Cleared directory: {dir_path}")
                except Exception as e:
                    self.errors.append(f"Directory clear error ({dir_name}): {str(e)}")
    
    def clear_cache_files(self) -> None:
        """Remove all cache and state files."""
        logger.info("Clearing cache files...")
        
        # Patterns to search for cache files
        cache_patterns = [
            "**/*.cache",
            "**/*.pickle",
            "**/*.pkl",
            "**/cache.json",
            "**/state.json",
            "**/.cache",
            "**/__pycache__",
            "**/*.pyc",
            "performance_metrics.json",
            "pipeline_state.json"
        ]
        
        for pattern in cache_patterns:
            for file_path in glob.glob(str(self.project_root / pattern), recursive=True):
                try:
                    path = Path(file_path)
                    if path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        shutil.rmtree(path)
                    logger.info(f"✓ Removed cache: {path.name}")
                except Exception as e:
                    self.errors.append(f"Cache removal error: {str(e)}")
    
    def clear_logs(self) -> None:
        """Clear all log files."""
        logger.info("Clearing log files...")
        
        log_patterns = [
            "*.log",
            "logs/*.log",
            "**/*.log",
            "error_log.txt",
            "debug.log"
        ]
        
        for pattern in log_patterns:
            for log_file in glob.glob(str(self.project_root / pattern), recursive=True):
                try:
                    Path(log_file).unlink()
                    logger.info(f"✓ Removed log: {Path(log_file).name}")
                except Exception as e:
                    self.errors.append(f"Log removal error: {str(e)}")
    
    def clear_monitoring_data(self) -> None:
        """Clear monitoring and metrics data."""
        logger.info("Clearing monitoring data...")
        
        monitoring_files = [
            "resource_usage.json",
            "api_metrics.json",
            "performance_report.json",
            "benchmark_results.json"
        ]
        
        for filename in monitoring_files:
            file_path = self.project_root / filename
            if file_path.exists():
                try:
                    file_path.unlink()
                    logger.info(f"✓ Removed monitoring file: {filename}")
                except Exception as e:
                    self.errors.append(f"Monitoring file error: {str(e)}")
    
    def verify_reset(self) -> None:
        """Verify the system is in virgin state."""
        logger.info("\nVerifying system reset...")
        
        # Check Neo4j
        try:
            cmd = [
                'docker', 'exec', 'neo4j', 'cypher-shell',
                '-u', 'neo4j', '-p', 'password',
                'MATCH (n) RETURN count(n) as count;'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if "count\n0" in result.stdout:
                logger.info("✓ Neo4j verified: 0 nodes")
            else:
                logger.warning("⚠ Neo4j may still contain data")
        except:
            logger.warning("⚠ Could not verify Neo4j state")
        
        # Check directories
        dirs_should_be_empty = ["checkpoints", "output"]
        for dir_name in dirs_should_be_empty:
            dir_path = self.project_root / dir_name
            if dir_path.exists() and any(dir_path.iterdir()):
                logger.warning(f"⚠ Directory not empty: {dir_name}")
            else:
                logger.info(f"✓ Directory verified empty: {dir_name}")
    
    def execute_reset(self) -> bool:
        """Execute the full system reset."""
        if not self.confirm_reset():
            logger.info("Reset cancelled by user")
            return False
        
        logger.info("\nStarting full system reset...")
        
        # Execute all reset operations
        self.reset_neo4j()
        self.clear_checkpoints()
        self.clear_speaker_cache()
        self.clear_output_directories()
        self.clear_cache_files()
        self.clear_logs()
        self.clear_monitoring_data()
        
        # Verify the reset
        self.verify_reset()
        
        # Report results
        print("\n" + "="*60)
        if self.errors:
            print("RESET COMPLETED WITH ERRORS:")
            for error in self.errors:
                print(f"  - {error}")
        else:
            print("RESET COMPLETED SUCCESSFULLY!")
            print("The system is now in virgin state.")
        print("="*60)
        
        return len(self.errors) == 0


def main():
    """Main entry point."""
    # Get project root
    script_path = Path(__file__)
    project_root = script_path.parent
    
    # Create and execute reset
    reset = SystemReset(project_root)
    success = reset.execute_reset()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()