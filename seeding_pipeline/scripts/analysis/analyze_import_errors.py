#!/usr/bin/env python3
"""Analyze import errors from pytest collection output."""

import re
import json
from pathlib import Path
from collections import defaultdict

def parse_test_collection_errors(file_path):
    """Parse test collection errors and categorize them."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    errors = defaultdict(list)
    
    # Pattern to match error blocks
    error_pattern = r'ERROR collecting (.*?)\n.*?E\s+(.*?)(?=\n(?:_|=|$))'
    matches = re.findall(error_pattern, content, re.DOTALL)
    
    for test_file, error_msg in matches:
        test_file = test_file.strip()
        error_msg = error_msg.strip()
        
        # Categorize errors
        if "ModuleNotFoundError: No module named 'cli'" in error_msg:
            errors["missing_modules"].append({
                "file": test_file,
                "module": "cli",
                "error": error_msg
            })
        elif "ModuleNotFoundError: No module named" in error_msg:
            module_match = re.search(r"No module named '(.*?)'", error_msg)
            if module_match:
                errors["missing_modules"].append({
                    "file": test_file,
                    "module": module_match.group(1),
                    "error": error_msg
                })
        elif "ImportError: cannot import name" in error_msg:
            import_match = re.search(r"cannot import name '(.*?)' from '(.*?)'", error_msg)
            if import_match:
                errors["wrong_imports"].append({
                    "file": test_file,
                    "name": import_match.group(1),
                    "from": import_match.group(2),
                    "error": error_msg
                })
        elif "from src.providers" in error_msg:
            errors["missing_modules"].append({
                "file": test_file,
                "module": "src.providers",
                "error": error_msg
            })
        elif "from src.factories" in error_msg:
            errors["missing_modules"].append({
                "file": test_file,
                "module": "src.factories",
                "error": error_msg
            })
        elif "SyntaxError" in error_msg:
            errors["syntax_errors"].append({
                "file": test_file,
                "error": error_msg
            })
        else:
            errors["other_errors"].append({
                "file": test_file,
                "error": error_msg
            })
    
    # Get unique error patterns
    patterns = defaultdict(set)
    
    # Analyze missing modules
    for item in errors["missing_modules"]:
        patterns["missing_modules"].add(item["module"])
    
    # Analyze wrong imports
    for item in errors["wrong_imports"]:
        patterns["wrong_imports"].add(f"{item['name']} from {item['from']}")
    
    # Create summary
    summary = {
        "total_errors": sum(len(v) for v in errors.values()),
        "error_categories": {
            "missing_modules": len(errors["missing_modules"]),
            "wrong_imports": len(errors["wrong_imports"]),
            "syntax_errors": len(errors["syntax_errors"]),
            "other_errors": len(errors["other_errors"])
        },
        "unique_patterns": {
            "missing_modules": sorted(list(patterns["missing_modules"])),
            "wrong_imports": sorted(list(patterns["wrong_imports"]))
        },
        "errors_by_category": errors
    }
    
    return summary

def main():
    # Parse test collection errors
    test_collection_file = Path("test_collection_errors.txt")
    if not test_collection_file.exists():
        print("Error: test_collection_errors.txt not found")
        return
    
    analysis = parse_test_collection_errors(test_collection_file)
    
    # Save analysis
    output_file = Path("test_tracking/import_error_analysis.json")
    with open(output_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    # Print summary
    print(f"Total errors found: {analysis['total_errors']}")
    print("\nError categories:")
    for category, count in analysis['error_categories'].items():
        print(f"  - {category}: {count}")
    
    print("\nUnique missing modules:")
    for module in analysis['unique_patterns']['missing_modules']:
        print(f"  - {module}")
    
    print("\nUnique wrong imports:")
    for pattern in analysis['unique_patterns']['wrong_imports']:
        print(f"  - {pattern}")
    
    print(f"\nAnalysis saved to: {output_file}")

if __name__ == "__main__":
    main()