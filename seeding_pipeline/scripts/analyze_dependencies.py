"""Analyze dependencies and their usage in the codebase."""
import ast
import os
from collections import defaultdict
from pathlib import Path
import json

def extract_imports(file_path):
    """Extract all imports from a Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split('.')[0])
        
        return imports
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return []

def map_dependencies_to_functionality():
    """Map each dependency to its functional area."""
    dependency_map = {
        # Audio Processing
        'torch': 'audio_processing',
        'whisper': 'audio_processing',
        'faster_whisper': 'audio_processing',
        'pyannote': 'audio_processing',
        
        # RSS/Feed
        'feedparser': 'rss_feed',
        
        # LLM and AI
            'openai': 'llm_ai',
        'google': 'llm_ai',
        
        # Embeddings
        'sentence_transformers': 'embeddings',
        
        # Database
        'neo4j': 'database',
        
        # API/Web
        'fastapi': 'api_web',
        'uvicorn': 'api_web',
        'pydantic': 'api_web',
        
        # Monitoring/Tracing
        'opentelemetry': 'monitoring',
        
        # Core utilities
        'numpy': 'core_utilities',
        'scipy': 'core_utilities',
        'networkx': 'core_utilities',
        'psutil': 'core_utilities',
        'yaml': 'core_utilities',
        'PyYAML': 'core_utilities',
        'dotenv': 'core_utilities',
        'tqdm': 'core_utilities',
    }
    return dependency_map

def analyze_codebase():
    """Analyze the entire codebase for dependency usage."""
    base_path = Path.cwd()
    src_path = base_path / 'src'
    dependency_usage = defaultdict(set)
    file_imports = defaultdict(list)
    
    # Walk through all Python files
    for py_file in src_path.rglob('*.py'):
        if '__pycache__' not in str(py_file):
            imports = extract_imports(py_file)
            relative_path = str(py_file.relative_to(base_path))
            
            for imp in imports:
                dependency_usage[imp].add(relative_path)
                file_imports[relative_path].append(imp)
    
    return dependency_usage, file_imports

def categorize_dependencies(dependency_usage, dependency_map):
    """Categorize dependencies by functionality."""
    categories = defaultdict(list)
    
    for dep, files in dependency_usage.items():
        category = dependency_map.get(dep, 'other')
        categories[category].append({
            'dependency': dep,
            'used_in': list(files),
            'file_count': len(files)
        })
    
    return categories

def generate_removal_candidates():
    """Generate list of removal candidates based on functionality."""
    removal_categories = [
        'audio_processing',
        'rss_feed', 
        'monitoring'
    ]
    
    keep_categories = [
        'database',
        'llm_ai',
        'embeddings',
        'core_utilities'
    ]
    
    partial_removal = {
        'api_web': 'Keep minimal API for health checks and status'
    }
    
    return removal_categories, keep_categories, partial_removal

def main():
    """Run the dependency analysis."""
    print("Analyzing dependencies...")
    
    # Get dependency map
    dependency_map = map_dependencies_to_functionality()
    
    # Analyze codebase
    dependency_usage, file_imports = analyze_codebase()
    
    # Categorize dependencies
    categories = categorize_dependencies(dependency_usage, dependency_map)
    
    # Get removal candidates
    removal_categories, keep_categories, partial_removal = generate_removal_candidates()
    
    # Create analysis report
    report = {
        'total_dependencies': len(dependency_usage),
        'categories': dict(categories),
        'removal_candidates': {
            'full_removal': removal_categories,
            'keep': keep_categories,
            'partial_removal': partial_removal
        },
        'dependency_usage_summary': {
            dep: len(files) for dep, files in dependency_usage.items()
        }
    }
    
    # Save the report
    with open('dependency_analysis.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    # Create a markdown report
    with open('docs/analysis/dependency_analysis.md', 'w') as f:
        f.write("# Dependency Analysis Report\n\n")
        f.write(f"Total unique dependencies found: {report['total_dependencies']}\n\n")
        
        f.write("## Dependencies by Category\n\n")
        for category, deps in categories.items():
            f.write(f"### {category.replace('_', ' ').title()}\n")
            for dep_info in sorted(deps, key=lambda x: x['file_count'], reverse=True):
                f.write(f"- **{dep_info['dependency']}**: Used in {dep_info['file_count']} files\n")
            f.write("\n")
        
        f.write("## Removal Recommendations\n\n")
        f.write("### Full Removal\n")
        for cat in removal_categories:
            f.write(f"- {cat.replace('_', ' ').title()}\n")
        
        f.write("\n### Keep\n")
        for cat in keep_categories:
            f.write(f"- {cat.replace('_', ' ').title()}\n")
        
        f.write("\n### Partial Removal\n")
        for cat, note in partial_removal.items():
            f.write(f"- {cat.replace('_', ' ').title()}: {note}\n")
    
    print("Analysis complete! Check dependency_analysis.json and docs/analysis/dependency_analysis.md")

if __name__ == "__main__":
    main()