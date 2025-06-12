#!/usr/bin/env python3
"""Create test action plan based on import resolution mapping."""

import json

def create_action_plan():
    """Create action plan for each test file."""
    # Load the import error inventory
    with open('import_error_inventory.json', 'r') as f:
        inventory = json.load(f)
    
    # Load the import resolution mapping
    with open('import_resolution_mapping.json', 'r') as f:
        resolution = json.load(f)
    
    action_plan = {
        'categories': {
            'SIMPLE_FIX': [],  # Just update import path
            'RENAME_FIX': [],  # Update to new function/class name
            'REFACTOR_NEEDED': [],  # Test needs significant updates
            'DELETE_CANDIDATE': []  # Functionality no longer exists
        },
        'test_details': {}
    }
    
    # Analyze each test file
    for test_file, test_data in inventory['errors_by_test'].items():
        test_info = {
            'test_file': test_file,
            'errors': test_data['errors'],
            'action': None,
            'reason': None,
            'fixes_needed': []
        }
        
        # Handle SyntaxError tests
        if any(error.get('error_type') == 'SyntaxError' for error in test_data['errors']):
            test_info['action'] = 'REFACTOR_NEEDED'
            test_info['reason'] = 'SyntaxError in test file - needs debugging'
            action_plan['categories']['REFACTOR_NEEDED'].append(test_file)
        
        # Handle import file mismatch
        elif any(error.get('error_type') == 'import file mismatch' for error in test_data['errors']):
            test_info['action'] = 'SIMPLE_FIX'
            test_info['reason'] = 'Import file mismatch - clear pycache'
            test_info['fixes_needed'].append('Clear __pycache__ directories')
            action_plan['categories']['SIMPLE_FIX'].append(test_file)
        
        # Handle ImportError tests
        else:
            # Check all imports for this test
            all_simple = True
            has_moved = False
            has_builtin = False
            
            for error in test_data['errors']:
                if 'missing_import' in error:
                    import_name = error['missing_import']
                    if import_name in resolution['import_status']:
                        status = resolution['import_status'][import_name]
                        
                        if status['status'] == 'exists' and status['action'] == 'none':
                            # This is weird - import exists but fails
                            test_info['fixes_needed'].append(f"Investigate why {import_name} import fails")
                            all_simple = False
                        elif status['status'] == 'moved':
                            has_moved = True
                            test_info['fixes_needed'].append(f"Update import: {import_name} from {status['new_location']}")
                        elif status['status'] == 'builtin':
                            has_builtin = True
                            test_info['fixes_needed'].append(f"Remove import of {import_name} (use Python builtin)")
                        elif status['action'] == 'update_import':
                            has_moved = True
                            test_info['fixes_needed'].append(f"Update import path for {import_name}")
            
            # Determine category
            if has_moved or has_builtin:
                test_info['action'] = 'RENAME_FIX'
                test_info['reason'] = 'Imports need path updates or removal'
                action_plan['categories']['RENAME_FIX'].append(test_file)
            elif all_simple:
                test_info['action'] = 'REFACTOR_NEEDED'
                test_info['reason'] = 'Imports exist but test fails - needs investigation'
                action_plan['categories']['REFACTOR_NEEDED'].append(test_file)
        
        action_plan['test_details'][test_file] = test_info
    
    # Add summary
    action_plan['summary'] = {
        'total_tests': len(action_plan['test_details']),
        'simple_fixes': len(action_plan['categories']['SIMPLE_FIX']),
        'rename_fixes': len(action_plan['categories']['RENAME_FIX']),
        'refactor_needed': len(action_plan['categories']['REFACTOR_NEEDED']),
        'delete_candidates': len(action_plan['categories']['DELETE_CANDIDATE'])
    }
    
    return action_plan

def main():
    """Main function."""
    action_plan = create_action_plan()
    
    # Save the action plan
    with open('test_action_plan.json', 'w') as f:
        json.dump(action_plan, f, indent=2)
    
    # Print summary
    print(f"Created action plan for {action_plan['summary']['total_tests']} tests:")
    print(f"  Simple fixes: {action_plan['summary']['simple_fixes']}")
    print(f"  Rename fixes: {action_plan['summary']['rename_fixes']}")
    print(f"  Refactor needed: {action_plan['summary']['refactor_needed']}")
    print(f"  Delete candidates: {action_plan['summary']['delete_candidates']}")

if __name__ == '__main__':
    main()