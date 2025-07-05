#!/usr/bin/env python3
"""Script to fix and organize imports in Python files."""

import ast
import os
from pathlib import Path
from typing import List, Set, Dict, Tuple

def organize_imports(file_path: Path) -> bool:
    """Organize imports in a Python file following PEP8."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        # Find import section
        import_start = None
        import_end = None
        imports = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ')) and import_start is None:
                import_start = i
            
            if import_start is not None:
                if stripped.startswith(('import ', 'from ')):
                    imports.append(line)
                    import_end = i
                elif stripped == '' and import_end is not None:
                    # Allow blank lines in imports
                    imports.append(line)
                    import_end = i
                elif stripped and not stripped.startswith('#'):
                    # End of imports
                    break
        
        if not imports:
            return False
        
        # Categorize imports
        stdlib = []
        third_party = []
        local = []
        
        stdlib_modules = {
            'abc', 'argparse', 'ast', 'asyncio', 'base64', 'collections', 
            'concurrent', 'contextlib', 'copy', 'dataclasses', 'datetime', 
            'decimal', 'enum', 'functools', 'gc', 'glob', 'hashlib', 'io', 
            'itertools', 'json', 'logging', 'math', 'multiprocessing', 'os', 
            'pathlib', 'pickle', 'platform', 'queue', 'random', 're', 'shutil', 
            'signal', 'socket', 'sqlite3', 'string', 'subprocess', 'sys', 
            'tempfile', 'threading', 'time', 'traceback', 'typing', 'unittest', 
            'urllib', 'uuid', 'warnings', 'weakref'
        }
        
        for imp in imports:
            if not imp.strip():
                continue
                
            # Extract module name
            if imp.strip().startswith('import '):
                module = imp.strip().split()[1].split('.')[0]
            elif imp.strip().startswith('from '):
                module = imp.strip().split()[1].split('.')[0]
            else:
                continue
            
            if module in stdlib_modules:
                stdlib.append(imp)
            elif module.startswith(('src', 'tests')):
                local.append(imp)
            else:
                third_party.append(imp)
        
        # Sort each category
        stdlib.sort()
        third_party.sort()
        local.sort()
        
        # Build new import section
        new_imports = []
        if stdlib:
            new_imports.extend(stdlib)
        if third_party:
            if new_imports:
                new_imports.append('')
            new_imports.extend(third_party)
        if local:
            if new_imports:
                new_imports.append('')
            new_imports.extend(local)
        
        # Replace imports in file
        new_lines = lines[:import_start] + new_imports + lines[import_end+1:]
        new_content = '\n'.join(new_lines)
        
        # Only write if changed
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        return False
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Organize imports in all Python files."""
    root_dir = Path(".")
    src_dir = root_dir / "src"
    tests_dir = root_dir / "tests"
    
    print("=== Organizing Imports ===\n")
    
    # Process Python files
    all_py_files = list(src_dir.rglob("*.py")) + list(tests_dir.rglob("*.py"))
    
    fixed_count = 0
    for py_file in all_py_files:
        # Skip __pycache__ and other generated files
        if '__pycache__' in str(py_file):
            continue
        
        if organize_imports(py_file):
            print(f"Fixed imports in: {py_file}")
            fixed_count += 1
    
    print(f"\nTotal files with imports organized: {fixed_count}")

if __name__ == "__main__":
    main()