#!/usr/bin/env python3
"""
Import audit script to scan all Python files and identify external dependencies.
"""

import ast
import os
import sys
from pathlib import Path
from typing import Set, Tuple, List
import importlib.util

def get_stdlib_modules() -> Set[str]:
    """Get a set of standard library module names."""
    stdlib_modules = set(sys.builtin_module_names)
    
    # Common stdlib modules not in builtin_module_names
    additional_stdlib = {
        'asyncio', 'collections', 'concurrent', 'contextvars', 'copy', 'csv',
        'dataclasses', 'datetime', 'decimal', 'distutils', 'email', 'encodings',
        'enum', 'functools', 'hashlib', 'http', 'importlib', 'inspect', 'io',
        'json', 'logging', 'multiprocessing', 'os', 'pathlib', 'pickle', 'platform',
        'queue', 're', 'shutil', 'signal', 'socket', 'sqlite3', 'string', 'subprocess',
        'sys', 'tempfile', 'threading', 'time', 'typing', 'unittest', 'urllib',
        'uuid', 'warnings', 'weakref', 'xml', 'zipfile'
    }
    
    return stdlib_modules | additional_stdlib

def extract_imports(file_path: Path) -> Set[str]:
    """Extract all import statements from a Python file."""
    imports = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
    except Exception as e:
        print(f"Error parsing {file_path}: {e}", file=sys.stderr)
    
    return imports

def scan_directory(directory: Path) -> Tuple[Set[str], List[Tuple[Path, Set[str]]]]:
    """Scan directory for Python files and extract imports."""
    all_imports = set()
    file_imports = []
    
    for py_file in directory.rglob('*.py'):
        # Skip __pycache__ and venv directories
        if '__pycache__' in str(py_file) or 'venv' in str(py_file):
            continue
        
        imports = extract_imports(py_file)
        if imports:
            all_imports.update(imports)
            file_imports.append((py_file, imports))
    
    return all_imports, file_imports

def classify_imports(imports: Set[str]) -> Tuple[Set[str], Set[str]]:
    """Classify imports as stdlib or third-party."""
    stdlib_modules = get_stdlib_modules()
    
    stdlib_imports = set()
    third_party_imports = set()
    
    for module in imports:
        if module in stdlib_modules or module.startswith('_'):
            stdlib_imports.add(module)
        else:
            third_party_imports.add(module)
    
    return stdlib_imports, third_party_imports

def main():
    """Main function to run the import audit."""
    project_root = Path(__file__).parent.parent
    
    print("Scanning Python files for imports...")
    print("=" * 60)
    
    # Scan src and tests directories
    all_imports = set()
    all_file_imports = []
    
    for directory in ['src', 'tests']:
        dir_path = project_root / directory
        if dir_path.exists():
            imports, file_imports = scan_directory(dir_path)
            all_imports.update(imports)
            all_file_imports.extend(file_imports)
            print(f"\nScanned {len(file_imports)} files in {directory}/")
    
    # Classify imports
    stdlib_imports, third_party_imports = classify_imports(all_imports)
    
    # Output results
    print("\n" + "=" * 60)
    print("IMPORT AUDIT RESULTS")
    print("=" * 60)
    
    print(f"\nTotal unique imports: {len(all_imports)}")
    print(f"Standard library imports: {len(stdlib_imports)}")
    print(f"Third-party imports: {len(third_party_imports)}")
    
    print("\n" + "-" * 30)
    print("THIRD-PARTY DEPENDENCIES:")
    print("-" * 30)
    for module in sorted(third_party_imports):
        print(f"  {module}")
    
    # Show which files use each third-party import
    print("\n" + "-" * 30)
    print("THIRD-PARTY IMPORT USAGE:")
    print("-" * 30)
    
    for module in sorted(third_party_imports):
        print(f"\n{module}:")
        for file_path, imports in all_file_imports:
            if module in imports:
                print(f"  - {file_path.relative_to(project_root)}")

if __name__ == "__main__":
    main()