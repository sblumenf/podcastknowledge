#!/usr/bin/env python3
"""Analyze which tests have real import issues vs other problems."""

import json
import subprocess
import sys

def test_single_file(test_path):
    """Test if a file has real import issues."""
    cmd = [
        sys.executable, '-m', 'pytest', 
        test_path, 
        '--collect-only',
        '-q'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if "ImportError" in result.stderr:
        # Extract the specific import error
        lines = result.stderr.split('\n')
        for i, line in enumerate(lines):
            if "ImportError: cannot import name" in line:
                return "import_error", line.strip()
    elif "SyntaxError" in result.stderr:
        return "syntax_error", "SyntaxError in file"
    elif result.returncode == 0:
        return "ok", "No import issues"
    else:
        return "other_error", result.stderr.split('\n')[0] if result.stderr else "Unknown error"

def main():
    """Main function."""
    # Load the test action plan
    with open('test_action_plan.json', 'r') as f:
        action_plan = json.load(f)
    
    real_issues = {
        'import_errors': [],
        'syntax_errors': [],
        'no_issues': [],
        'other_errors': [],
        'missing_files': []
    }
    
    # Test each file
    for test_file in action_plan['test_details']:
        print(f"Testing {test_file}...")
        
        # Check if file exists
        try:
            with open(f"../{test_file}", 'r'):
                pass
        except FileNotFoundError:
            real_issues['missing_files'].append(test_file)
            continue
        
        status, message = test_single_file(f"../{test_file}")
        
        if status == "import_error":
            real_issues['import_errors'].append({
                'file': test_file,
                'error': message
            })
        elif status == "syntax_error":
            real_issues['syntax_errors'].append(test_file)
        elif status == "ok":
            real_issues['no_issues'].append(test_file)
        else:
            real_issues['other_errors'].append({
                'file': test_file,
                'error': message
            })
    
    # Save results
    with open('real_import_issues.json', 'w') as f:
        json.dump(real_issues, f, indent=2)
    
    # Print summary
    print(f"\nSummary:")
    print(f"  Files with real import errors: {len(real_issues['import_errors'])}")
    print(f"  Files with syntax errors: {len(real_issues['syntax_errors'])}")
    print(f"  Files with no issues: {len(real_issues['no_issues'])}")
    print(f"  Files with other errors: {len(real_issues['other_errors'])}")
    print(f"  Missing files: {len(real_issues['missing_files'])}")

if __name__ == '__main__':
    main()