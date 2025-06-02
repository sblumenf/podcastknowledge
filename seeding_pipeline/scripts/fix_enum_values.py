#!/usr/bin/env python3
"""
Fix non-existent enum values in test files.

This script updates test files to use valid enum values from extraction_interface.py
"""

import os
import re
from pathlib import Path

# Define the mapping of invalid to valid enum values
ENUM_REPLACEMENTS = {
    # EntityType replacements
    'EntityType.TECHNOLOGY': 'EntityType.CONCEPT',
    'EntityType.SOFTWARE': 'EntityType.PRODUCT',
    'EntityType.HARDWARE': 'EntityType.PRODUCT',
    'EntityType.FRAMEWORK': 'EntityType.CONCEPT',
    'EntityType.METHOD': 'EntityType.CONCEPT',
    'EntityType.TOOL': 'EntityType.PRODUCT',
    'EntityType.SYSTEM': 'EntityType.CONCEPT',
    
    # InsightType replacements
    'InsightType.OBSERVATION': 'InsightType.KEY_POINT',
    'InsightType.ANALYSIS': 'InsightType.SUMMARY',
    'InsightType.FINDING': 'InsightType.FACT',
    'InsightType.DISCOVERY': 'InsightType.KEY_POINT',
    'InsightType.CONCLUSION': 'InsightType.SUMMARY',
    
    # QuoteType replacements (if any)
    'QuoteType.GENERAL': 'QuoteType.OTHER',
    
    # ComplexityLevel replacements (if any)
    'ComplexityLevel.BASIC': 'ComplexityLevel.LOW',
    'ComplexityLevel.ADVANCED': 'ComplexityLevel.HIGH',
}

def fix_enum_values_in_file(file_path: Path) -> int:
    """Fix enum values in a single file. Returns number of replacements made."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        replacements_made = 0
        
        # Apply each replacement
        for old_value, new_value in ENUM_REPLACEMENTS.items():
            if old_value in content:
                count = content.count(old_value)
                content = content.replace(old_value, new_value)
                replacements_made += count
                print(f"  Replaced {count} occurrences of {old_value} with {new_value}")
        
        # Only write if changes were made
        if content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"✅ Fixed {replacements_made} enum values in {file_path}")
        
        return replacements_made
    
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return 0

def main():
    """Fix enum values in all test files."""
    test_dir = Path(__file__).parent.parent / 'tests'
    total_replacements = 0
    files_modified = 0
    
    print("Fixing non-existent enum values in test files...")
    print("=" * 60)
    
    # Find all Python test files
    test_files = list(test_dir.rglob('test_*.py'))
    
    for test_file in test_files:
        replacements = fix_enum_values_in_file(test_file)
        if replacements > 0:
            total_replacements += replacements
            files_modified += 1
    
    print("=" * 60)
    print(f"Summary:")
    print(f"  Files scanned: {len(test_files)}")
    print(f"  Files modified: {files_modified}")
    print(f"  Total replacements: {total_replacements}")
    
    if files_modified > 0:
        print("\n✅ Enum values fixed successfully!")
        print("Next steps:")
        print("  1. Run tests to verify fixes")
        print("  2. Commit changes")
    else:
        print("\n✅ No invalid enum values found - tests already use correct values")

if __name__ == "__main__":
    main()