#!/usr/bin/env python3
"""Fix remaining import errors in test files."""

import os
import re
from pathlib import Path

def comment_out_missing_imports(file_path):
    """Comment out imports for modules that don't exist."""
    
    # List of modules that don't exist
    missing_modules = [
        'src.api.v1.seeding',
        'src.core.error_budget',
        'src.factories',
        'src.processing.complexity_analysis',
        'src.processing.discourse_flow',
        'src.processing.emergent_themes',
        'src.processing.entity_resolution',
        'src.processing.extraction',
        'src.processing.graph_analysis',
        'src.processing.importance_scoring',
        'src.processing.parsers',
        'src.processing.preprocessor',
        'src.processing.prompts',
        'src.processing.vtt_parser',
        'src.providers',
    ]
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    modified = False
    new_lines = []
    
    for line in lines:
        # Check if line contains import from missing module
        should_comment = False
        for module in missing_modules:
            if f'from {module} import' in line or f'import {module}' in line:
                should_comment = True
                break
        
        if should_comment and not line.strip().startswith('#'):
            new_lines.append(f'# FIXME: Module not found - {line}')
            modified = True
        else:
            new_lines.append(line)
    
    if modified:
        with open(file_path, 'w') as f:
            f.writelines(new_lines)
        return True
    
    return False

def main():
    """Fix remaining import errors."""
    test_dir = Path('tests')
    fixed_count = 0
    
    # Process all Python test files
    for test_file in test_dir.rglob('*.py'):
        if test_file.name == '__init__.py':
            continue
            
        if comment_out_missing_imports(test_file):
            print(f"Fixed imports in: {test_file}")
            fixed_count += 1
    
    print(f"\nFixed {fixed_count} files")
    print("\nNote: These tests will need to be rewritten or removed")
    print("since they depend on modules that no longer exist.")

if __name__ == "__main__":
    main()