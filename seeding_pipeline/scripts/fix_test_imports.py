#!/usr/bin/env python3
"""Fix test imports based on import_mapping.json."""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

def load_import_mapping(mapping_file: Path) -> Dict:
    """Load the import mapping from JSON file."""
    with open(mapping_file, 'r') as f:
        return json.load(f)

def fix_module_imports(content: str, mappings: List[Dict]) -> Tuple[str, int]:
    """Fix module imports based on mappings."""
    changes = 0
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        for mapping in mappings:
            if mapping['type'] == 'moved_module':
                old_module = mapping['old']
                new_module = mapping['new']
                name = mapping.get('name', '')
                
                # Fix "from old_module import name"
                pattern = f"from {re.escape(old_module)} import"
                if re.search(pattern, line):
                    lines[i] = line.replace(f"from {old_module} import", f"from {new_module} import")
                    changes += 1
                    print(f"  Fixed: {old_module} -> {new_module}")
            
            elif mapping['type'] == 'renamed_class':
                old_name = mapping['old']
                new_name = mapping['new']
                
                # Replace class name in imports and usage
                if old_name in line:
                    lines[i] = line.replace(old_name, new_name)
                    changes += 1
                    print(f"  Renamed: {old_name} -> {new_name}")
    
    return '\n'.join(lines), changes

def fix_test_file(test_file: Path, file_info: Dict) -> bool:
    """Fix imports in a single test file."""
    if not test_file.exists():
        return False
    
    print(f"\nProcessing: {test_file}")
    
    # Read file content
    with open(test_file, 'r') as f:
        content = f.read()
    
    # Apply fixes
    missing = file_info.get('missing', [])
    if not missing:
        print("  No fixes needed")
        return False
    
    new_content, changes = fix_module_imports(content, missing)
    
    # Write back if changes were made
    if changes > 0:
        with open(test_file, 'w') as f:
            f.write(new_content)
        print(f"  Applied {changes} fixes")
        return True
    
    return False

def main():
    """Main function to fix all test imports."""
    # Load import mapping
    mapping_file = Path('test_tracking/import_mapping.json')
    if not mapping_file.exists():
        print(f"Error: {mapping_file} not found")
        return
    
    mapping_data = load_import_mapping(mapping_file)
    import_analysis = mapping_data.get('import_analysis', {})
    
    # Fix each test file
    fixed_count = 0
    for test_file_str, file_info in import_analysis.items():
        test_file = Path(test_file_str)
        if fix_test_file(test_file, file_info):
            fixed_count += 1
    
    print(f"\n{'='*50}")
    print(f"Fixed {fixed_count} test files")
    
    # Additional specific fixes for common patterns
    print("\nApplying additional pattern-based fixes...")
    
    # Fix all occurrences of PodcastKnowledgePipeline -> VTTKnowledgeExtractor
    test_files = list(Path('tests').rglob('*.py'))
    pattern_fixes = 0
    
    for test_file in test_files:
        try:
            with open(test_file, 'r') as f:
                content = f.read()
            
            original_content = content
            
            # Apply common replacements
            content = content.replace('PodcastKnowledgePipeline', 'VTTKnowledgeExtractor')
            content = content.replace('ComponentHealth', 'HealthStatus')
            content = content.replace('EnhancedPodcastSegmenter', 'VTTSegmenter')
            
            # Fix module paths
            content = re.sub(r'from cli import', 'from src.cli.cli import', content)
            content = re.sub(r'from src\.processing\.extraction import', 'from src.extraction.extraction import', content)
            content = re.sub(r'from src\.processing\.entity_resolution import', 'from src.extraction.entity_resolution import', content)
            content = re.sub(r'from src\.processing\.vtt_parser import', 'from src.vtt.vtt_parser import', content)
            content = re.sub(r'from src\.processing\.parsers import', 'from src.extraction.parsers import', content)
            
            if content != original_content:
                with open(test_file, 'w') as f:
                    f.write(content)
                pattern_fixes += 1
                print(f"  Fixed patterns in: {test_file}")
                
        except Exception as e:
            print(f"  Error processing {test_file}: {e}")
    
    print(f"\nFixed patterns in {pattern_fixes} additional files")
    print("\nImport fixing complete!")

if __name__ == '__main__':
    main()