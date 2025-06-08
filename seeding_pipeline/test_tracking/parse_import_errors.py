#!/usr/bin/env python3
"""Parse import_errors.txt and create JSON inventory."""

import json
import re

def parse_import_errors(file_path):
    """Parse import errors from pytest output."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    errors = {}
    current_test = None
    
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for test file collection error
        if "ERROR collecting" in line:
            match = re.search(r'ERROR collecting (tests/.*?\.py)', line)
            if match:
                current_test = match.group(1)
                errors[current_test] = {
                    'test_file': current_test,
                    'errors': []
                }
        
        # Look for ImportError details
        elif current_test and "ImportError: cannot import name" in line:
            # Extract the missing import and source module
            match = re.search(r"cannot import name '([^']+)' from '([^']+)'", line)
            if match:
                missing_import = match.group(1)
                source_module = match.group(2)
                
                # Look back to find the full import statement
                j = i - 1
                while j >= 0:
                    if "from" in lines[j] and "import" in lines[j]:
                        import_line = lines[j].strip()
                        # Extract all imports from this line
                        import_match = re.search(r'from\s+[\w.]+\s+import\s+(.+)', import_line)
                        if import_match:
                            all_imports = [imp.strip() for imp in import_match.group(1).split(',')]
                            errors[current_test]['errors'].append({
                                'missing_import': missing_import,
                                'source_module': source_module,
                                'all_imports_attempted': all_imports,
                                'import_line': import_line
                            })
                        break
                    j -= 1
        
        # Look for SyntaxError
        elif current_test and "SyntaxError: invalid syntax" in line:
            errors[current_test]['errors'].append({
                'error_type': 'SyntaxError',
                'message': 'invalid syntax'
            })
        
        # Look for import file mismatch
        elif current_test and "import file mismatch" in line:
            errors[current_test]['errors'].append({
                'error_type': 'import file mismatch',
                'message': 'HINT: remove __pycache__ / .pyc files and/or use a unique basename'
            })
        
        i += 1
    
    return errors

def main():
    """Main function."""
    errors = parse_import_errors('/home/sergeblumenfeld/podcastknowledge/seeding_pipeline/import_errors.txt')
    
    # Create summary
    summary = {
        'total_failing_tests': len(errors),
        'error_types': {
            'ImportError': 0,
            'SyntaxError': 0,
            'import file mismatch': 0
        },
        'unique_missing_imports': set(),
        'unique_source_modules': set(),
        'errors_by_test': errors
    }
    
    # Count error types and collect unique items
    for test_file, test_data in errors.items():
        for error in test_data['errors']:
            if 'error_type' in error:
                summary['error_types'][error['error_type']] += 1
            else:
                summary['error_types']['ImportError'] += 1
                summary['unique_missing_imports'].add(error['missing_import'])
                summary['unique_source_modules'].add(error['source_module'])
    
    # Convert sets to lists for JSON serialization
    summary['unique_missing_imports'] = sorted(list(summary['unique_missing_imports']))
    summary['unique_source_modules'] = sorted(list(summary['unique_source_modules']))
    
    # Save to JSON
    with open('/home/sergeblumenfeld/podcastknowledge/seeding_pipeline/test_tracking/import_error_inventory.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Parsed {summary['total_failing_tests']} failing tests")
    print(f"Found {len(summary['unique_missing_imports'])} unique missing imports")
    print(f"Error types: {summary['error_types']}")

if __name__ == '__main__':
    main()