#!/usr/bin/env python3
"""
Virtual Environment Cleanup Script

Safely identifies and removes old/unused virtual environments to reclaim disk space.
Includes safety checks to prevent deletion of active environments.
"""

import os
import sys
import time
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta


def get_venv_paths(base_path="/home"):
    """Find all virtual environment directories."""
    venv_paths = []
    
    # Common venv directory names
    venv_names = ["venv", ".venv", "env", ".env"]
    
    try:
        for root, dirs, files in os.walk(base_path):
            # Skip deep nested directories and hidden system paths
            depth = root.replace(base_path, '').count(os.sep)
            if depth > 4:
                continue
                
            # Skip common non-venv directories
            if any(skip in root for skip in [".git", "node_modules", "__pycache__", ".cache"]):
                continue
                
            for dir_name in dirs:
                if dir_name in venv_names:
                    venv_path = Path(root) / dir_name
                    # Validate it's actually a virtual environment
                    if is_virtual_env(venv_path):
                        venv_paths.append(venv_path)
                        
    except PermissionError as e:
        print(f"Permission denied accessing {e.filename}, skipping...")
        
    return venv_paths


def is_virtual_env(path):
    """Check if a directory is actually a virtual environment."""
    try:
        # Check for common venv indicators
        indicators = [
            path / "bin" / "python",
            path / "Scripts" / "python.exe",  # Windows
            path / "pyvenv.cfg"
        ]
        return any(indicator.exists() for indicator in indicators)
    except:
        return False


def get_venv_age(venv_path):
    """Get the age of a virtual environment in days."""
    try:
        # Check modification time of the venv directory
        mtime = os.path.getmtime(venv_path)
        age = (time.time() - mtime) / (24 * 3600)  # Convert to days
        return age
    except:
        return 0


def is_active_venv(venv_path):
    """Check if a virtual environment is currently active."""
    try:
        # Check if current Python is from this venv
        current_python = sys.executable
        venv_python = str(venv_path / "bin" / "python")
        
        if os.path.samefile(current_python, venv_python):
            return True
            
        # Check for common process indicators
        try:
            result = subprocess.run(
                ["pgrep", "-f", str(venv_path)], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            return bool(result.stdout.strip())
        except:
            pass
            
        return False
    except:
        return False


def backup_requirements(venv_path, backup_dir):
    """Backup requirements from a virtual environment before deletion."""
    try:
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        venv_name = venv_path.name
        backup_file = backup_dir / f"{venv_name}_{timestamp}_requirements.txt"
        
        # Try to generate requirements
        python_path = venv_path / "bin" / "python"
        if python_path.exists():
            result = subprocess.run(
                [str(python_path), "-m", "pip", "freeze"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                with open(backup_file, 'w') as f:
                    f.write(f"# Backup of {venv_path} on {datetime.now()}\n")
                    f.write(result.stdout)
                print(f"  ✓ Backed up requirements to {backup_file}")
                return True
                
    except Exception as e:
        print(f"  ⚠ Could not backup requirements: {e}")
        
    return False


def get_directory_size(path):
    """Get the size of a directory in bytes."""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except:
                    pass
    except:
        pass
    return total_size


def format_size(size_bytes):
    """Format size in human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}TB"


def main():
    parser = argparse.ArgumentParser(description="Clean up old virtual environments")
    parser.add_argument("--age", type=int, default=30, 
                       help="Delete venvs older than N days (default: 30)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be deleted without actually deleting")
    parser.add_argument("--backup-dir", default="./venv_backups",
                       help="Directory to backup requirements (default: ./venv_backups)")
    parser.add_argument("--base-path", default="/home",
                       help="Base path to search for venvs (default: /home)")
    
    args = parser.parse_args()
    
    print(f"🔍 Scanning for virtual environments older than {args.age} days...")
    print(f"📁 Search path: {args.base_path}")
    
    venv_paths = get_venv_paths(args.base_path)
    print(f"Found {len(venv_paths)} virtual environments")
    
    candidates_for_deletion = []
    total_size_to_free = 0
    
    for venv_path in venv_paths:
        age = get_venv_age(venv_path)
        size = get_directory_size(venv_path)
        
        print(f"\n📦 {venv_path}")
        print(f"   Age: {age:.1f} days")
        print(f"   Size: {format_size(size)}")
        
        if age > args.age:
            if is_active_venv(venv_path):
                print(f"   ⚠ ACTIVE - Skipping")
            else:
                print(f"   🗑 Candidate for deletion")
                candidates_for_deletion.append((venv_path, size))
                total_size_to_free += size
        else:
            print(f"   ✓ Recent - Keeping")
    
    if not candidates_for_deletion:
        print(f"\n✅ No virtual environments found for cleanup!")
        return
    
    print(f"\n📊 Summary:")
    print(f"   Environments to delete: {len(candidates_for_deletion)}")
    print(f"   Disk space to free: {format_size(total_size_to_free)}")
    
    if args.dry_run:
        print(f"\n🔥 DRY RUN - Nothing will be deleted")
        for venv_path, size in candidates_for_deletion:
            print(f"   Would delete: {venv_path} ({format_size(size)})")
        return
    
    # Confirm deletion
    print(f"\n⚠ This will permanently delete {len(candidates_for_deletion)} virtual environments!")
    confirm = input("Continue? (type 'yes' to confirm): ")
    
    if confirm.lower() != 'yes':
        print("Aborted.")
        return
    
    # Perform cleanup
    deleted_count = 0
    freed_space = 0
    
    for venv_path, size in candidates_for_deletion:
        print(f"\n🗑 Deleting {venv_path}...")
        
        # Backup requirements if possible
        backup_requirements(venv_path, args.backup_dir)
        
        try:
            shutil.rmtree(venv_path)
            print(f"   ✓ Deleted successfully ({format_size(size)} freed)")
            deleted_count += 1
            freed_space += size
        except Exception as e:
            print(f"   ❌ Failed to delete: {e}")
    
    print(f"\n🎉 Cleanup complete!")
    print(f"   Deleted: {deleted_count} environments")
    print(f"   Freed: {format_size(freed_space)}")
    
    if deleted_count > 0 and Path(args.backup_dir).exists():
        print(f"   Backups saved in: {args.backup_dir}")


if __name__ == "__main__":
    main()