#!/usr/bin/env python3
"""Fix import statements in test files based on mappings."""

import re
import json
from pathlib import Path
import argparse

def load_mappings():
    """Load import mappings from analysis."""
    with open('test_tracking/import_mapping.json', 'r') as f:
        data = json.load(f)
    
    # Combine known mappings with found alternatives
    mappings = {
        # Module mappings
        'from cli import': 'from src.cli.cli import',
        'from src.processing.extraction import': 'from src.extraction.extraction import',
        'from src.processing.parsers import': 'from src.extraction.parsers import',
        'from src.processing.preprocessor import': 'from src.extraction.preprocessor import',
        'from src.processing.prompts import': 'from src.extraction.prompts import',
        'from src.processing.complexity_analysis import': 'from src.extraction.complexity_analysis import',
        'from src.processing.entity_resolution import': 'from src.extraction.entity_resolution import',
        'from src.processing.importance_scoring import': 'from src.extraction.importance_scoring import',
        'from src.processing.vtt_parser import': 'from src.vtt.vtt_parser import',
        
        # Class name mappings
        'PodcastKnowledgePipeline': 'VTTKnowledgeExtractor',
        'EnhancedPodcastSegmenter': 'VTTSegmenter',
        
        # Add found alternatives
        'from src.core.models import Relationship': 'from src.core.extraction_interface import Relationship',
        'from src.core.models import Segment': 'from src.core.extraction_interface import Segment',
        'from src.core.models import Entity': 'from src.core.extraction_interface import Entity',
        'from src.core.models import Insight': 'from src.core.extraction_interface import Insight',
        'from src.core.models import Quote': 'from src.core.extraction_interface import Quote',
    }
    
    # Add class location mappings
    for class_name, location in data.get('found_alternatives', {}).items():
        # Skip if it's already in the right place
        if class_name not in ['Relationship', 'Segment', 'Entity', 'Insight', 'Quote']:
            continue
            
    return mappings

def fix_imports_in_file(file_path, mappings, dry_run=False):
    """Fix imports in a single file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    changes_made = []
    
    # Apply module import fixes
    for old_pattern, new_pattern in mappings.items():
        if old_pattern.startswith('from '):
            # Direct replacement for from imports
            if old_pattern in content:
                content = content.replace(old_pattern, new_pattern)
                changes_made.append(f"{old_pattern} -> {new_pattern}")
        else:
            # Class name replacements
            # Be careful to only replace in appropriate contexts
            pattern = r'\b' + re.escape(old_pattern) + r'\b'
            if re.search(pattern, content):
                content = re.sub(pattern, new_pattern, content)
                changes_made.append(f"{old_pattern} -> {new_pattern}")
    
    # Special handling for common patterns
    
    # Fix: from src.seeding import PodcastKnowledgePipeline
    pattern = r'from src\.seeding import PodcastKnowledgePipeline'
    if re.search(pattern, content):
        content = re.sub(pattern, 'from src.seeding.orchestrator import VTTKnowledgeExtractor', content)
        changes_made.append("PodcastKnowledgePipeline import fixed")
    
    # Fix: from src.seeding.orchestrator import PodcastKnowledgePipeline
    pattern = r'from src\.seeding\.orchestrator import PodcastKnowledgePipeline'
    if re.search(pattern, content):
        content = re.sub(pattern, 'from src.seeding.orchestrator import VTTKnowledgeExtractor', content)
        changes_made.append("PodcastKnowledgePipeline orchestrator import fixed")
    
    # Fix: from src.api.health import ComponentHealth
    pattern = r'from src\.api\.health import ComponentHealth'
    if re.search(pattern, content):
        content = re.sub(pattern, 'from src.api.health import HealthStatus', content)
        changes_made.append("ComponentHealth -> HealthStatus")
    
    # Fix: from src.utils.logging import ContextFilter
    pattern = r'from src\.utils\.logging import .*?ContextFilter'
    if re.search(pattern, content):
        # Remove ContextFilter from imports
        content = re.sub(r',?\s*ContextFilter', '', content)
        changes_made.append("Removed ContextFilter import")
    
    # Fix: from src.utils.text_processing import clean_segment_text, normalize_entity_name
    if 'from src.utils.text_processing import' in content and ('clean_segment_text' in content or 'normalize_entity_name' in content):
        # These functions don't exist, remove them
        content = re.sub(r',?\s*clean_segment_text', '', content)
        content = re.sub(r',?\s*normalize_entity_name', '', content)
        changes_made.append("Removed non-existent text processing imports")
    
    # Fix: from src.utils.retry import retry_with_backoff, RetryError
    if 'retry_with_backoff' in content:
        content = re.sub(r'retry_with_backoff', 'retry', content)
        changes_made.append("retry_with_backoff -> retry")
    
    if 'RetryError' in content:
        # RetryError doesn't exist, use Exception instead
        content = re.sub(r'\bRetryError\b', 'Exception', content)
        changes_made.append("RetryError -> Exception")
    
    # Fix: from src.utils.rate_limiting import SlidingWindowRateLimiter
    if 'SlidingWindowRateLimiter' in content:
        content = re.sub(r'SlidingWindowRateLimiter', 'RateLimiter', content)
        changes_made.append("SlidingWindowRateLimiter -> RateLimiter")
    
    # Fix: from src.processing.segmentation import EnhancedPodcastSegmenter
    pattern = r'from src\.processing\.segmentation import EnhancedPodcastSegmenter'
    if re.search(pattern, content):
        content = re.sub(pattern, 'from src.vtt.vtt_segmentation import VTTSegmenter', content)
        changes_made.append("EnhancedPodcastSegmenter segmentation import fixed")
    
    # Fix: from src.seeding.concurrency import Priority
    if 'from src.seeding.concurrency import Priority' in content:
        # Priority enum doesn't exist, remove or replace with string
        content = content.replace('from src.seeding.concurrency import Priority', '')
        content = re.sub(r'Priority\.\w+', '"high"', content)
        changes_made.append("Removed Priority enum import")
    
    # Clean up empty imports
    content = re.sub(r'from\s+\S+\s+import\s*\n', '', content)
    content = re.sub(r'from\s+\S+\s+import\s*$', '', content, flags=re.MULTILINE)
    
    if content != original_content:
        if not dry_run:
            with open(file_path, 'w') as f:
                f.write(content)
        return changes_made
    
    return []

def main():
    parser = argparse.ArgumentParser(description='Fix test imports')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without applying')
    args = parser.parse_args()
    
    mappings = load_mappings()
    
    # Get all test files
    test_files = list(Path('tests').rglob('*.py'))
    
    fixed_count = 0
    total_changes = []
    
    for test_file in test_files:
        if test_file.name == '__init__.py':
            continue
        
        changes = fix_imports_in_file(test_file, mappings, args.dry_run)
        if changes:
            fixed_count += 1
            print(f"\n{test_file}:")
            for change in changes:
                print(f"  - {change}")
            total_changes.extend([(str(test_file), change) for change in changes])
    
    print(f"\n{'Would fix' if args.dry_run else 'Fixed'} {fixed_count} files")
    print(f"Total changes: {len(total_changes)}")
    
    if not args.dry_run:
        # Save change log
        change_log = {
            'files_fixed': fixed_count,
            'total_changes': len(total_changes),
            'changes': total_changes
        }
        with open('test_tracking/import_fixes.json', 'w') as f:
            json.dump(change_log, f, indent=2)
        print("\nChange log saved to test_tracking/import_fixes.json")

if __name__ == "__main__":
    main()