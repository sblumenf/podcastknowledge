#!/usr/bin/env python3
"""Script to clean up imports and find commented code."""

import ast
import os
import re
from pathlib import Path
from typing import List, Set, Tuple

def find_unused_imports(file_path: Path) -> List[str]:
    """Find potentially unused imports in a Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        # Collect all imports
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
                for alias in node.names:
                    imports.add(alias.name)
        
        # Find which imports are used in the code
        # This is simplified - a proper implementation would need to track scopes
        used = set()
        for line in content.split('\n'):
            if not line.strip().startswith(('import ', 'from ')):
                for imp in imports:
                    if imp in line:
                        used.add(imp)
        
        unused = imports - used
        return sorted(list(unused))
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return []

def find_commented_code(file_path: Path) -> List[Tuple[int, str]]:
    """Find lines that look like commented-out code."""
    commented_code = []
    
    # Patterns that indicate commented code
    code_patterns = [
        r'^\s*#\s*(import\s+|from\s+)',
        r'^\s*#\s*(def\s+|class\s+)',
        r'^\s*#\s*\w+\s*\(',  # Function calls
        r'^\s*#\s*\w+\s*=',   # Assignments
        r'^\s*#\s*(if\s+|for\s+|while\s+|return\s+|raise\s+)',
    ]
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                for pattern in code_patterns:
                    if re.match(pattern, line):
                        commented_code.append((line_num, line.strip()))
                        break
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return commented_code

def find_empty_init_files(root_dir: Path) -> List[Path]:
    """Find empty __init__.py files."""
    empty_inits = []
    
    for init_file in root_dir.rglob("__init__.py"):
        try:
            with open(init_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content or content == '""""""':
                    empty_inits.append(init_file)
        except Exception as e:
            print(f"Error reading {init_file}: {e}")
    
    return empty_inits

def main():
    """Run cleanup analysis."""
    root_dir = Path(".")
    src_dir = root_dir / "src"
    tests_dir = root_dir / "tests"
    
    print("=== Import and Code Cleanup Analysis ===\n")
    
    # Analyze Python files
    all_py_files = list(src_dir.rglob("*.py")) + list(tests_dir.rglob("*.py"))
    
    files_with_unused = []
    files_with_commented = []
    
    for py_file in all_py_files:
        # Skip __pycache__ and other generated files
        if '__pycache__' in str(py_file):
            continue
            
        # Check for unused imports
        unused = find_unused_imports(py_file)
        if unused:
            files_with_unused.append((py_file, unused))
        
        # Check for commented code
        commented = find_commented_code(py_file)
        if commented:
            files_with_commented.append((py_file, commented))
    
    # Report unused imports
    if files_with_unused:
        print(f"Files with potentially unused imports ({len(files_with_unused)}):")
        for file_path, unused in files_with_unused[:10]:  # Show first 10
            print(f"  {file_path}: {', '.join(unused)}")
        if len(files_with_unused) > 10:
            print(f"  ... and {len(files_with_unused) - 10} more files")
    else:
        print("No files with unused imports found.")
    
    print()
    
    # Report commented code
    if files_with_commented:
        print(f"\nFiles with commented-out code ({len(files_with_commented)}):")
        for file_path, commented in files_with_commented[:10]:  # Show first 10
            print(f"  {file_path}: {len(commented)} lines")
            for line_num, line in commented[:3]:  # Show first 3 lines
                print(f"    Line {line_num}: {line[:60]}...")
        if len(files_with_commented) > 10:
            print(f"  ... and {len(files_with_commented) - 10} more files")
    else:
        print("No files with commented-out code found.")
    
    print()
    
    # Find empty __init__.py files
    empty_inits = find_empty_init_files(root_dir)
    if empty_inits:
        print(f"\nEmpty __init__.py files ({len(empty_inits)}):")
        for init_file in empty_inits:
            print(f"  {init_file}")
    else:
        print("No empty __init__.py files found.")
    
    # Summary
    print(f"\n=== Summary ===")
    print(f"Total Python files analyzed: {len(all_py_files)}")
    print(f"Files with unused imports: {len(files_with_unused)}")
    print(f"Files with commented code: {len(files_with_commented)}")
    print(f"Empty __init__.py files: {len(empty_inits)}")

if __name__ == "__main__":
    main()