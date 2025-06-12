#!/usr/bin/env python3
"""
Apply Neo4j mocking to E2E test files.

This script updates E2E test files to use mocked Neo4j connections
instead of real ones.
"""

import os
import re
from pathlib import Path


def update_e2e_test_file(file_path: Path) -> int:
    """Update E2E test file to use Neo4j mocks."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        changes = 0
        
        # Add necessary imports at the top
        if 'from neo4j import GraphDatabase' in content and 'neo4j_mocks' not in content:
            # Find the imports section
            import_section_end = content.find('\n\n')
            if import_section_end > 0:
                new_imports = "\nfrom tests.utils.neo4j_mocks import create_mock_neo4j_driver"
                content = content[:import_section_end] + new_imports + content[import_section_end:]
                changes += 1
                print(f"  Added neo4j_mocks import")
        
        # Replace GraphDatabase.driver with mock
        if 'GraphDatabase.driver(' in content:
            # Pattern to match GraphDatabase.driver calls
            pattern = r'GraphDatabase\.driver\('
            replacement = 'create_mock_neo4j_driver('
            
            occurrences = len(re.findall(pattern, content))
            if occurrences > 0:
                content = re.sub(pattern, replacement, content)
                changes += occurrences
                print(f"  Replaced {occurrences} GraphDatabase.driver calls with mock")
        
        # Add pytest marker for tests that should still use real Neo4j
        if '@pytest.mark.e2e' not in content and 'class Test' in content:
            # Add marker imports if not present
            if 'import pytest' not in content:
                content = "import pytest\n" + content
                changes += 1
            
            # Add e2e marker to test classes
            content = re.sub(
                r'(class Test\w+)',
                r'@pytest.mark.e2e\n\1',
                content
            )
            changes += 1
            print(f"  Added @pytest.mark.e2e markers")
        
        # Write back if changes were made
        if content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
        
        return changes
        
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return 0


def main():
    """Apply Neo4j mocking to E2E test files."""
    test_dir = Path(__file__).parent.parent / 'tests'
    total_changes = 0
    files_modified = 0
    
    print("Applying Neo4j mocks to E2E test files...")
    print("=" * 60)
    
    # E2E test files to update
    e2e_files = [
        'e2e/test_vtt_pipeline_e2e.py',
        'e2e/test_e2e_scenarios.py',
        'integration/test_golden_outputs.py',
    ]
    
    for file_path in e2e_files:
        full_path = test_dir / file_path
        if not full_path.exists():
            print(f"⚠️  Skipping {file_path} - file not found")
            continue
            
        changes = update_e2e_test_file(full_path)
        if changes > 0:
            print(f"✅ Updated {file_path} with {changes} changes")
            total_changes += changes
            files_modified += 1
    
    print("=" * 60)
    print(f"Summary:")
    print(f"  Files modified: {files_modified}")
    print(f"  Total changes: {total_changes}")
    
    if files_modified > 0:
        print("\n✅ Neo4j mocking applied successfully!")
        print("Next steps:")
        print("  1. Run E2E tests to verify mocking works")
        print("  2. Add @pytest.mark.requires_neo4j to tests that need real Neo4j")
        print("  3. Commit changes")
    else:
        print("\n✅ No changes needed - E2E tests already mocked or not found")


if __name__ == "__main__":
    main()