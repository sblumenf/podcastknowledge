#!/usr/bin/env python3
"""Analyze test imports and map to current code structure."""

import ast
import json
from pathlib import Path
from collections import defaultdict

class ImportAnalyzer(ast.NodeVisitor):
    """AST visitor to extract imports from Python files."""
    
    def __init__(self):
        self.imports = []
        self.from_imports = []
    
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        if node.module:
            for alias in node.names:
                self.from_imports.append({
                    'module': node.module,
                    'name': alias.name,
                    'full': f"{node.module}.{alias.name}"
                })
        self.generic_visit(node)

def analyze_file_imports(file_path):
    """Extract all imports from a Python file."""
    try:
        with open(file_path, 'r') as f:
            tree = ast.parse(f.read())
        
        analyzer = ImportAnalyzer()
        analyzer.visit(tree)
        return analyzer.imports, analyzer.from_imports
    except Exception as e:
        return [], []

def check_module_exists(module_path):
    """Check if a module exists in the src directory."""
    # Convert module path to file path
    parts = module_path.split('.')
    if parts[0] == 'src':
        # Check both as package (__init__.py) and as module (.py)
        base_path = Path('src') / Path(*parts[1:])
        return (base_path / '__init__.py').exists() or (base_path.with_suffix('.py')).exists()
    return False

def check_class_exists(module_path, class_name):
    """Check if a class exists in a module."""
    parts = module_path.split('.')
    if parts[0] == 'src':
        base_path = Path('src') / Path(*parts[1:])
        
        # Try both package and module
        for path in [base_path / '__init__.py', base_path.with_suffix('.py')]:
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        tree = ast.parse(f.read())
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef) and node.name == class_name:
                            return True
                except:
                    pass
    return False

def find_alternative_location(class_name):
    """Search for a class in the entire src directory."""
    src_path = Path('src')
    for py_file in src_path.rglob('*.py'):
        try:
            with open(py_file, 'r') as f:
                tree = ast.parse(f.read())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    # Convert file path back to module path
                    rel_path = py_file.relative_to(src_path).with_suffix('')
                    module_path = 'src.' + str(rel_path).replace('/', '.')
                    return module_path
        except:
            pass
    return None

def map_old_to_new():
    """Known mappings based on architecture changes."""
    return {
        # Module renames
        'cli': 'src.cli.cli',
        'src.processing.extraction': 'src.extraction.extraction',
        'src.processing.parsers': 'src.extraction.parsers',
        'src.processing.preprocessor': 'src.extraction.preprocessor',
        'src.processing.prompts': 'src.extraction.prompts',
        'src.processing.complexity_analysis': 'src.extraction.complexity_analysis',
        'src.processing.entity_resolution': 'src.extraction.entity_resolution',
        'src.processing.importance_scoring': 'src.extraction.importance_scoring',
        'src.processing.vtt_parser': 'src.vtt.vtt_parser',
        
        # Deleted modules
        'src.providers': None,
        'src.factories': None,
        'src.api.v1.seeding': None,
        'src.core.error_budget': None,
        'src.processing.discourse_flow': None,
        'src.processing.emergent_themes': None,
        'src.processing.graph_analysis': None,
        
        # Class renames
        'PodcastKnowledgePipeline': 'VTTKnowledgeExtractor',
        'AudioProvider': None,  # Deleted
        'ComponentHealth': 'HealthStatus',  # Possibly renamed
        'EnhancedPodcastSegmenter': 'VTTSegmenter',  # Possibly renamed
    }

def main():
    # Get all test files
    test_files = list(Path('tests').rglob('*.py'))
    
    mapping = {
        'total_test_files': len(test_files),
        'import_analysis': {},
        'module_mappings': map_old_to_new(),
        'missing_imports': defaultdict(list),
        'found_alternatives': {},
        'recommendations': []
    }
    
    for test_file in test_files:
        if test_file.name == '__init__.py':
            continue
        
        imports, from_imports = analyze_file_imports(test_file)
        
        file_analysis = {
            'imports': imports,
            'from_imports': [],
            'missing': [],
            'found': []
        }
        
        # Analyze from imports
        for imp in from_imports:
            module = imp['module']
            name = imp['name']
            
            # Check if module exists
            if module.startswith('src.') or module == 'cli':
                exists = check_module_exists(module)
                mapped_module = map_old_to_new().get(module, module)
                
                if not exists and mapped_module is None:
                    # Module was deleted
                    file_analysis['missing'].append({
                        'type': 'deleted_module',
                        'module': module,
                        'name': name
                    })
                    mapping['missing_imports'][module].append(str(test_file))
                elif not exists and mapped_module:
                    # Module was moved/renamed
                    file_analysis['missing'].append({
                        'type': 'moved_module',
                        'old': module,
                        'new': mapped_module,
                        'name': name
                    })
                elif exists:
                    # Check if class/function exists
                    if name and not check_class_exists(module, name):
                        # Try to find alternative location
                        alt_location = find_alternative_location(name)
                        if alt_location:
                            file_analysis['missing'].append({
                                'type': 'moved_class',
                                'old': f"{module}.{name}",
                                'new': f"{alt_location}.{name}"
                            })
                            mapping['found_alternatives'][name] = alt_location
                        else:
                            # Check if it's a known rename
                            new_name = map_old_to_new().get(name)
                            if new_name:
                                file_analysis['missing'].append({
                                    'type': 'renamed_class',
                                    'old': name,
                                    'new': new_name
                                })
                            else:
                                file_analysis['missing'].append({
                                    'type': 'missing_class',
                                    'module': module,
                                    'name': name
                                })
                
                file_analysis['from_imports'].append(imp)
        
        if file_analysis['missing']:
            mapping['import_analysis'][str(test_file)] = file_analysis
    
    # Generate recommendations
    if mapping['missing_imports']:
        mapping['recommendations'].append({
            'action': 'delete_tests',
            'reason': 'Tests for deleted modules',
            'modules': list(mapping['missing_imports'].keys())
        })
    
    if mapping['found_alternatives']:
        mapping['recommendations'].append({
            'action': 'update_imports',
            'reason': 'Classes found in different locations',
            'mappings': mapping['found_alternatives']
        })
    
    # Save mapping
    output_file = Path('test_tracking/import_mapping.json')
    with open(output_file, 'w') as f:
        json.dump(mapping, f, indent=2)
    
    # Print summary
    print(f"Analyzed {len(test_files)} test files")
    print(f"Found {len(mapping['import_analysis'])} files with import issues")
    print(f"\nMissing modules:")
    for module, files in mapping['missing_imports'].items():
        print(f"  - {module} (used in {len(files)} files)")
    print(f"\nFound alternatives for {len(mapping['found_alternatives'])} classes")
    print(f"\nMapping saved to: {output_file}")

if __name__ == "__main__":
    main()