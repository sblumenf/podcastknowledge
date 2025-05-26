#!/usr/bin/env python3
"""
Generate dependency graph for the podcast knowledge system refactoring.
This script analyzes the monolithic script and visualizes dependencies between classes and functions.
"""

import re
import ast
from collections import defaultdict
from pathlib import Path
import json


class DependencyAnalyzer:
    """Analyze dependencies in Python source code."""
    
    def __init__(self, source_file: Path):
        self.source_file = source_file
        self.classes = {}
        self.functions = {}
        self.imports = []
        self.dependencies = defaultdict(set)
        self.external_deps = set()
        
    def analyze(self):
        """Perform complete dependency analysis."""
        with open(self.source_file, 'r') as f:
            source = f.read()
            
        # Parse AST
        tree = ast.parse(source)
        
        # Extract imports
        self._extract_imports(tree)
        
        # Extract classes and functions
        self._extract_definitions(tree)
        
        # Analyze dependencies
        self._analyze_dependencies(source)
        
        return self.generate_report()
        
    def _extract_imports(self, tree):
        """Extract all import statements."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.imports.append(alias.name)
                    self.external_deps.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    self.imports.append(f"{module}.{alias.name}")
                    self.external_deps.add(module.split('.')[0])
                    
    def _extract_definitions(self, tree):
        """Extract class and function definitions."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self.classes[node.name] = {
                    'line': node.lineno,
                    'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
                    'bases': [base.id for base in node.bases if isinstance(base, ast.Name)]
                }
            elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
                self.functions[node.name] = {
                    'line': node.lineno,
                    'args': [arg.arg for arg in node.args.args]
                }
                
    def _analyze_dependencies(self, source):
        """Analyze dependencies between classes."""
        lines = source.split('\n')
        
        for class_name, class_info in self.classes.items():
            # Find class definition
            start_line = class_info['line'] - 1
            end_line = start_line
            
            # Find end of class
            indent_level = len(lines[start_line]) - len(lines[start_line].lstrip())
            for i in range(start_line + 1, len(lines)):
                if lines[i].strip() and not lines[i].startswith(' '):
                    end_line = i
                    break
                elif lines[i].strip() and len(lines[i]) - len(lines[i].lstrip()) <= indent_level:
                    end_line = i
                    break
            else:
                end_line = len(lines)
                
            # Extract class body
            class_body = '\n'.join(lines[start_line:end_line])
            
            # Find dependencies
            for other_class in self.classes:
                if other_class != class_name and other_class in class_body:
                    self.dependencies[class_name].add(other_class)
                    
    def generate_report(self):
        """Generate dependency analysis report."""
        report = {
            'summary': {
                'total_classes': len(self.classes),
                'total_functions': len(self.functions),
                'external_dependencies': len(self.external_deps),
                'internal_dependencies': sum(len(deps) for deps in self.dependencies.values())
            },
            'external_dependencies': sorted(self.external_deps),
            'classes': self.classes,
            'functions': self.functions,
            'class_dependencies': {k: sorted(v) for k, v in self.dependencies.items()},
            'proposed_modules': self._propose_modules()
        }
        
        return report
        
    def _propose_modules(self):
        """Propose module structure based on analysis."""
        modules = {
            'core': {
                'description': 'Core interfaces and models',
                'classes': ['PodcastConfig', 'SeedingConfig'],
                'reasons': ['Configuration classes', 'No external dependencies']
            },
            'exceptions': {
                'description': 'Custom exception hierarchy',
                'classes': ['PodcastProcessingError', 'DatabaseConnectionError', 
                           'AudioProcessingError', 'LLMProcessingError', 'ConfigurationError'],
                'reasons': ['Exception classes', 'Independent of other classes']
            },
            'providers': {
                'audio': {
                    'description': 'Audio processing providers',
                    'classes': ['AudioProcessor'],
                    'reasons': ['Handles transcription and diarization', 'Uses Whisper/PyAnnote']
                },
                'graph': {
                    'description': 'Graph database providers',
                    'classes': ['Neo4jManager', 'GraphOperations'],
                    'reasons': ['Database operations', 'Neo4j specific']
                },
                'llm': {
                    'description': 'LLM providers',
                    'classes': ['TaskRouter'],
                    'reasons': ['LLM routing and management']
                }
            },
            'processing': {
                'segmentation': {
                    'description': 'Text segmentation',
                    'classes': ['EnhancedPodcastSegmenter'],
                    'reasons': ['Segment management', 'Text processing']
                },
                'extraction': {
                    'description': 'Knowledge extraction',
                    'classes': ['RelationshipExtractor', 'ExtractionValidator'],
                    'reasons': ['Extract insights and entities', 'LLM-based processing']
                },
                'entity_resolution': {
                    'description': 'Entity matching and resolution',
                    'classes': ['VectorEntityMatcher'],
                    'reasons': ['Entity deduplication', 'Vector similarity']
                }
            },
            'utils': {
                'patterns': {
                    'description': 'Pattern matching utilities',
                    'classes': ['OptimizedPatternMatcher'],
                    'reasons': ['Regex optimization', 'Pattern caching']
                },
                'rate_limiting': {
                    'description': 'Rate limiting utilities',
                    'classes': ['HybridRateLimiter'],
                    'reasons': ['API rate management', 'Token counting']
                }
            },
            'seeding': {
                'checkpoint': {
                    'description': 'Checkpoint management',
                    'classes': ['ProgressCheckpoint'],
                    'reasons': ['Progress tracking', 'Recovery support']
                },
                'orchestrator': {
                    'description': 'Pipeline orchestration',
                    'classes': ['PodcastKnowledgePipeline'],
                    'reasons': ['Main orchestrator', 'Coordinates all components']
                }
            }
        }
        
        return modules
        
    def identify_circular_dependencies(self):
        """Identify potential circular dependencies."""
        circular = []
        
        for class_a in self.dependencies:
            for class_b in self.dependencies[class_a]:
                if class_a in self.dependencies.get(class_b, set()):
                    pair = tuple(sorted([class_a, class_b]))
                    if pair not in circular:
                        circular.append(pair)
                        
        return circular


def main():
    """Main entry point."""
    source_file = Path(__file__).parent.parent.parent / "podcast_knowledge_system_enhanced.py"
    
    if not source_file.exists():
        print(f"Error: Source file not found at {source_file}")
        return
        
    analyzer = DependencyAnalyzer(source_file)
    report = analyzer.analyze()
    
    # Save report
    output_file = Path(__file__).parent.parent / "dependency_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
        
    # Print summary
    print("Dependency Analysis Complete")
    print("=" * 50)
    print(f"Total Classes: {report['summary']['total_classes']}")
    print(f"Total Functions: {report['summary']['total_functions']}")
    print(f"External Dependencies: {report['summary']['external_dependencies']}")
    print(f"Internal Dependencies: {report['summary']['internal_dependencies']}")
    print()
    print("External Dependencies:")
    for dep in sorted(report['external_dependencies'])[:10]:
        print(f"  - {dep}")
    if len(report['external_dependencies']) > 10:
        print(f"  ... and {len(report['external_dependencies']) - 10} more")
    print()
    print("Circular Dependencies:")
    circular = analyzer.identify_circular_dependencies()
    if circular:
        for a, b in circular:
            print(f"  - {a} <-> {b}")
    else:
        print("  None found")
    print()
    print(f"Full report saved to: {output_file}")
    
    # Generate visual graph if graphviz available
    try:
        import graphviz
        generate_visual_graph(report, Path(__file__).parent.parent / "dependency_graph.png")
        print("Visual dependency graph saved to: dependency_graph.png")
    except ImportError:
        print("Install graphviz for visual dependency graph: pip install graphviz")


def generate_visual_graph(report, output_path):
    """Generate visual dependency graph using graphviz."""
    import graphviz
    
    dot = graphviz.Digraph(comment='Podcast Knowledge System Dependencies')
    dot.attr(rankdir='TB')
    
    # Add nodes for each class
    for class_name in report['classes']:
        dot.node(class_name, class_name)
        
    # Add edges for dependencies
    for class_name, deps in report['class_dependencies'].items():
        for dep in deps:
            dot.edge(class_name, dep)
            
    # Render graph
    dot.render(output_path.stem, output_path.parent, format='png', cleanup=True)


if __name__ == "__main__":
    main()