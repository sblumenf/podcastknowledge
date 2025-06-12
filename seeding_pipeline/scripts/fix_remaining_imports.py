#!/usr/bin/env python3
"""
Fix remaining import errors in test files.

This script updates test files to use correct import paths and removes
references to deleted classes.
"""

import os
import re
from pathlib import Path


def fix_import_errors_in_file(file_path: Path) -> int:
    """Fix import errors in a single file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        changes = 0
        
        # Fix 1: StructuredLogger -> StructuredFormatter
        if 'StructuredLogger' in content:
            content = content.replace('StructuredLogger', 'StructuredFormatter')
            changes += content.count('StructuredFormatter') - original_content.count('StructuredFormatter')
            print(f"  Replaced StructuredLogger with StructuredFormatter")
        
        # Fix 2: Import PodcastKnowledgePipeline from correct location
        if 'from src.seeding import PodcastKnowledgePipeline' in content:
            content = content.replace(
                'from src.seeding import PodcastKnowledgePipeline',
                'from src.api.v1 import VTTKnowledgeExtractor as PodcastKnowledgePipeline'
            )
            changes += 1
            print(f"  Fixed PodcastKnowledgePipeline import path")
        
        # Fix 3: Import seed_podcast from correct location
        if re.search(r'from src\.api\.v1 import.*seed_podcast', content) and 'podcast_api' not in content:
            # The functions are in podcast_api submodule
            content = re.sub(
                r'from src\.api\.v1 import (.*seed_podcast.*)',
                r'from src.api.v1.podcast_api import \1',
                content
            )
            changes += 1
            print(f"  Fixed seed_podcast import path")
        
        # Fix 4: Import seed_podcasts from correct location
        if re.search(r'from src\.api\.v1 import.*seed_podcasts', content) and 'podcast_api' not in content:
            content = re.sub(
                r'from src\.api\.v1 import (.*seed_podcasts.*)',
                r'from src.api.v1.podcast_api import \1',
                content
            )
            changes += 1
            print(f"  Fixed seed_podcasts import path")
        
        # Fix 5: Import ComponentHealth - it's already in health.py
        if 'from src.api.health import' in content and 'ComponentHealth' not in content:
            # Make sure ComponentHealth is imported
            content = re.sub(
                r'from src\.api\.health import ([^,\n]+)',
                r'from src.api.health import \1, ComponentHealth',
                content
            )
            changes += 1
            print(f"  Added ComponentHealth to imports")
        
        # Fix 6: Remove tests for non-existent classes
        if 'class TestStructuredLogger' in content:
            # Comment out the entire test class for StructuredLogger
            lines = content.split('\n')
            new_lines = []
            in_test_class = False
            indent_level = 0
            
            for line in lines:
                if 'class TestStructuredLogger' in line:
                    in_test_class = True
                    indent_level = len(line) - len(line.lstrip())
                    new_lines.append(f"{' ' * indent_level}# Commented out - StructuredLogger no longer exists")
                    new_lines.append(f"{' ' * indent_level}# {line}")
                    continue
                
                if in_test_class:
                    # Check if we're still in the class
                    if line.strip() and not line.startswith(' '):
                        # New top-level definition, we're out of the class
                        in_test_class = False
                    elif line.strip() and len(line) - len(line.lstrip()) <= indent_level:
                        # New class or function at same or lower indent
                        in_test_class = False
                    
                    if in_test_class:
                        new_lines.append(f"# {line}")
                        continue
                
                new_lines.append(line)
            
            content = '\n'.join(new_lines)
            changes += 1
            print(f"  Commented out TestStructuredLogger class")
        
        # Write back if changes made
        if content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
        
        return changes
        
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return 0


def main():
    """Fix remaining import errors."""
    test_dir = Path(__file__).parent.parent / 'tests'
    total_changes = 0
    files_modified = 0
    
    print("Fixing remaining import errors...")
    print("=" * 60)
    
    # Files with known import errors
    files_to_fix = [
        'unit/test_logging.py',
        'test_component_baselines.py',
        'api/test_v1_api.py',
        'e2e/test_e2e_scenarios.py',
        'api/test_health.py',
    ]
    
    for file_path in files_to_fix:
        full_path = test_dir / file_path
        if not full_path.exists():
            print(f"⚠️  Skipping {file_path} - file not found")
            continue
            
        changes = fix_import_errors_in_file(full_path)
        if changes > 0:
            print(f"✅ Fixed {file_path}")
            total_changes += changes
            files_modified += 1
    
    print("=" * 60)
    print(f"Summary:")
    print(f"  Files modified: {files_modified}")
    print(f"  Total fixes: {total_changes}")
    
    if files_modified > 0:
        print("\n✅ Import errors fixed!")
        print("Note: Some tests may still fail if system dependencies are missing")
        print("Install missing dependencies with: pip install -r requirements.txt")
    else:
        print("\n✅ No import errors found to fix")


if __name__ == "__main__":
    main()
