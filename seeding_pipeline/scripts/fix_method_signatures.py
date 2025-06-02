#!/usr/bin/env python3
"""
Fix method signature mismatches in test files.

This script updates test files to use correct method signatures.
"""

import os
import re
from pathlib import Path

def fix_file_content(content: str, file_path: Path) -> tuple[str, int]:
    """Fix method signatures in file content. Returns (new_content, num_changes)."""
    original_content = content
    changes = 0
    
    # Fix 1: seed_podcast use_large_context parameter
    if 'seed_podcast' in content and 'use_large_context' in content:
        # Remove use_large_context parameter from seed_podcast calls
        pattern = r'(seed_podcast\([^)]+),\s*use_large_context=\w+'
        new_content = re.sub(pattern, r'\1', content)
        if new_content != content:
            changes += len(re.findall(pattern, content))
            content = new_content
            print(f"  Removed use_large_context from seed_podcast calls")
    
    # Fix 2: max_episodes_each -> max_episodes_per_podcast
    if 'max_episodes_each' in content:
        content = content.replace('max_episodes_each', 'max_episodes_per_podcast')
        changes += 1
        print(f"  Changed max_episodes_each to max_episodes_per_podcast")
    
    # Fix 3: Convert Entity/Quote objects to dicts in ExtractionResult
    if 'ExtractionResult(' in content and file_path.name in ['test_extraction_unit.py', 'test_extraction.py']:
        # This is more complex - we need to convert objects to dicts
        lines = content.split('\n')
        new_lines = []
        in_extraction_result = False
        
        for i, line in enumerate(lines):
            if 'ExtractionResult(' in line:
                in_extraction_result = True
            
            # Replace insights with relationships if it's in ExtractionResult
            if in_extraction_result and 'insights=' in line:
                line = line.replace('insights=', 'relationships=')
                changes += 1
                print(f"  Changed insights= to relationships= in ExtractionResult")
            
            # Remove topics= from ExtractionResult
            if in_extraction_result and 'topics=' in line:
                # Skip this line entirely
                if line.strip().endswith(','):
                    continue
                else:
                    # Remove the topics= part but keep the closing paren
                    line = re.sub(r'topics=[^,)]+[,]?\s*', '', line)
                    changes += 1
                    print(f"  Removed topics= from ExtractionResult")
            
            new_lines.append(line)
            
            if in_extraction_result and ')' in line and not line.strip().startswith(')'):
                in_extraction_result = False
        
        content = '\n'.join(new_lines)
    
    # Fix 4: seed_podcasts use_large_context parameter
    if 'seed_podcasts' in content and 'use_large_context' in content:
        pattern = r'(seed_podcasts\([^)]+),\s*use_large_context=\w+'
        new_content = re.sub(pattern, r'\1', content)
        if new_content != content:
            changes += len(re.findall(pattern, content))
            content = new_content
            print(f"  Removed use_large_context from seed_podcasts calls")
    
    # Fix 5: Convert entity/quote lists to dict lists
    if 'entities=' in content or 'quotes=' in content:
        # Add conversion helpers at the top of test methods
        if 'def test_' in content and '[entity.to_dict()' not in content:
            # Find test methods that create ExtractionResult
            pattern = r'(def test_[^:]+:.*?)(ExtractionResult\()'
            
            def add_conversions(match):
                method_def = match.group(1)
                extraction_result = match.group(2)
                
                # Check if this method needs entity/quote conversions
                method_content = content[match.start():match.end() + 500]
                needs_conversion = False
                
                if 'entities=' in method_content and 'Entity(' in method_content:
                    needs_conversion = True
                if 'quotes=' in method_content and 'Quote(' in method_content:
                    needs_conversion = True
                
                if needs_conversion:
                    return method_def + extraction_result
                else:
                    return match.group(0)
            
            content = re.sub(pattern, add_conversions, content, flags=re.DOTALL)
    
    return content, changes

def fix_extraction_result_usage(file_path: Path) -> int:
    """Fix ExtractionResult usage to convert objects to dicts."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        changes = 0
        
        # Pattern to find ExtractionResult instantiations
        if 'ExtractionResult(' in content:
            lines = content.split('\n')
            new_lines = []
            
            for i, line in enumerate(lines):
                # Convert entities list to dict list
                if 'entities=' in line and 'Entity(' in '\n'.join(lines[max(0, i-20):i]):
                    if '[entity' in line and 'to_dict()' not in line:
                        line = re.sub(r'entities=(\w+)', r'entities=[e.to_dict() for e in \1]', line)
                        changes += 1
                        print(f"  Converted entities to dict list")
                
                # Convert quotes list to dict list
                if 'quotes=' in line and 'Quote(' in '\n'.join(lines[max(0, i-20):i]):
                    if '[quote' in line and 'to_dict()' not in line:
                        line = re.sub(r'quotes=(\w+)', r'quotes=[q.to_dict() for q in \1]', line)
                        changes += 1
                        print(f"  Converted quotes to dict list")
                
                new_lines.append(line)
            
            if changes > 0:
                content = '\n'.join(new_lines)
                with open(file_path, 'w') as f:
                    f.write(content)
        
        return changes
    
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return 0

def main():
    """Fix method signature mismatches in test files."""
    test_dir = Path(__file__).parent.parent / 'tests'
    total_changes = 0
    files_modified = 0
    
    print("Fixing method signature mismatches in test files...")
    print("=" * 60)
    
    # Specific files to fix based on the report
    files_to_fix = [
        'api/test_v1_api.py',
        'unit/test_extraction_unit.py',
        'unit/test_orchestrator_unit.py',
        'processing/test_extraction.py',
        'processing/test_vtt_extraction.py',
        'unit/test_extraction_integration.py',
    ]
    
    for file_path in files_to_fix:
        full_path = test_dir / file_path
        if not full_path.exists():
            continue
            
        try:
            with open(full_path, 'r') as f:
                content = f.read()
            
            new_content, changes = fix_file_content(content, full_path)
            
            # Apply additional extraction result fixes
            if 'extraction' in file_path:
                changes += fix_extraction_result_usage(full_path)
            
            if changes > 0:
                with open(full_path, 'w') as f:
                    f.write(new_content)
                print(f"✅ Fixed {changes} issues in {file_path}")
                total_changes += changes
                files_modified += 1
        
        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")
    
    # Also remove the report file
    report_file = Path(__file__).parent.parent / 'test_signature_mismatches.md'
    if report_file.exists():
        report_file.unlink()
        print("Removed temporary report file")
    
    print("=" * 60)
    print(f"Summary:")
    print(f"  Files modified: {files_modified}")
    print(f"  Total fixes: {total_changes}")
    
    if files_modified > 0:
        print("\n✅ Method signatures fixed successfully!")
        print("Next steps:")
        print("  1. Run tests to verify fixes")
        print("  2. Commit changes")
    else:
        print("\n✅ No method signature issues found")

if __name__ == "__main__":
    main()