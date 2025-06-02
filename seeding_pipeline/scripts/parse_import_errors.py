#!/usr/bin/env python3
"""Parse import errors from pytest output into JSON format."""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional

def parse_import_errors(file_path: str) -> List[Dict[str, str]]:
    """Parse import errors from pytest output."""
    errors = []
    current_error = None
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for ERROR collecting pattern
        if "ERROR collecting" in line:
            # Extract test file path
            match = re.search(r'ERROR collecting (.+\.py)', line)
            if match:
                test_file = match.group(1)
                current_error = {'test_file': test_file}
                
                # Look for ImportError or SyntaxError
                j = i + 1
                while j < len(lines) and j < i + 10:
                    error_line = lines[j].strip()
                    
                    if "ImportError:" in error_line or "SyntaxError:" in error_line:
                        # Handle SyntaxError
                        if "SyntaxError:" in error_line:
                            current_error['error_type'] = 'SyntaxError'
                            current_error['error_details'] = error_line
                            errors.append(current_error)
                            current_error = None
                            break
                        
                        # Look for the actual import statement
                        k = j + 1
                        while k < len(lines) and k < j + 10:
                            import_line = lines[k]
                            
                            # Look for "from X import Y" pattern
                            from_match = re.search(r'from (.+) import (.+)', import_line)
                            if from_match:
                                current_error['error_type'] = 'ImportError'
                                current_error['module'] = from_match.group(1)
                                current_error['missing_import'] = from_match.group(2)
                                
                                # Look for the actual error message
                                m = k + 1
                                if m < len(lines) and "ImportError:" in lines[m]:
                                    error_match = re.search(r"ImportError: cannot import name '(.+)' from '(.+)'", lines[m])
                                    if error_match:
                                        current_error['missing_name'] = error_match.group(1)
                                        current_error['from_module'] = error_match.group(2)
                                
                                errors.append(current_error)
                                current_error = None
                                break
                            k += 1
                        break
                    j += 1
        
        # Also handle the pattern where ImportError is on same line
        import_match = re.search(r"ImportError: cannot import name '(.+)' from '(.+)' \((.+)\)", line)
        if import_match and current_error:
            current_error['error_type'] = 'ImportError'
            current_error['missing_name'] = import_match.group(1)
            current_error['from_module'] = import_match.group(2)
            current_error['module_path'] = import_match.group(3)
            if 'module' not in current_error:
                current_error['module'] = import_match.group(2)
            errors.append(current_error)
            current_error = None
        
        i += 1
    
    return errors

def group_errors_by_module(errors: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    """Group errors by the module they're trying to import from."""
    grouped = {}
    for error in errors:
        if error.get('error_type') == 'ImportError':
            module = error.get('from_module', error.get('module', 'unknown'))
            if module not in grouped:
                grouped[module] = []
            grouped[module].append(error)
        elif error.get('error_type') == 'SyntaxError':
            if 'SyntaxError' not in grouped:
                grouped['SyntaxError'] = []
            grouped['SyntaxError'].append(error)
    return grouped

def main():
    """Main function."""
    import_errors = parse_import_errors('import_errors.txt')
    grouped_errors = group_errors_by_module(import_errors)
    
    # Create summary
    summary = {
        'total_errors': len(import_errors),
        'syntax_errors': len([e for e in import_errors if e.get('error_type') == 'SyntaxError']),
        'import_errors': len([e for e in import_errors if e.get('error_type') == 'ImportError']),
        'errors_by_module': {
            module: {
                'count': len(errors),
                'missing_imports': list(set(e.get('missing_name', '') for e in errors if e.get('missing_name')))
            }
            for module, errors in grouped_errors.items()
        },
        'all_errors': import_errors
    }
    
    # Save to JSON
    with open('import_errors_analysis.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Analyzed {len(import_errors)} import errors")
    print(f"Found {summary['syntax_errors']} syntax errors and {summary['import_errors']} import errors")
    print("\nErrors by module:")
    for module, info in summary['errors_by_module'].items():
        if module != 'SyntaxError':
            print(f"  {module}: {info['count']} errors")
            if info['missing_imports']:
                print(f"    Missing: {', '.join(info['missing_imports'])}")

if __name__ == '__main__':
    main()