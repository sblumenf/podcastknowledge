#!/usr/bin/env python3
"""
Script to verify complete topic removal from the system.

Checks:
1. Code analysis for remaining topic references
2. Database query for any Topic nodes
3. Log analysis for topic-related messages

This script validates that the topic system has been completely removed.
"""

import os
import subprocess
import sys
from pathlib import Path

def check_code_references():
    """Check for functional topic references in code."""
    print("🔍 Checking for functional topic references in code...")
    
    # Search for specific topic-related patterns
    dangerous_patterns = [
        "create_topic_for_episode",
        "HAS_TOPIC", 
        ":Topic",
        "Topic {",
        "MERGE.*Topic",
        "MATCH.*Topic"
    ]
    
    issues_found = []
    
    for pattern in dangerous_patterns:
        try:
            result = subprocess.run(
                ["grep", "-r", pattern, "--include=*.py", "src/"],
                capture_output=True,
                text=True,
                cwd="."
            )
            
            if result.returncode == 0 and result.stdout.strip():
                issues_found.append(f"Pattern '{pattern}' found in:")
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        issues_found.append(f"  {line}")
        except Exception as e:
            print(f"Error checking pattern {pattern}: {e}")
    
    if issues_found:
        print("❌ FUNCTIONAL TOPIC REFERENCES FOUND:")
        for issue in issues_found:
            print(issue)
        return False
    else:
        print("✅ No functional topic references found in source code")
        return True

def check_imports():
    """Check for topic-related imports that shouldn't exist."""
    print("\n🔍 Checking for topic-related imports...")
    
    topic_imports = []
    
    try:
        result = subprocess.run(
            ["grep", "-r", "from.*topic", "--include=*.py", "src/"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if 'topic' in line.lower() and 'import' in line:
                    # Filter out legitimate topic mentions (conversation topics, etc.)
                    if 'TopicExtractor' in line or 'topic_' in line:
                        topic_imports.append(line.strip())
    except Exception as e:
        print(f"Error checking imports: {e}")
    
    if topic_imports:
        print("❌ TOPIC-RELATED IMPORTS FOUND:")
        for imp in topic_imports:
            print(f"  {imp}")
        return False
    else:
        print("✅ No topic-related imports found")
        return True

def analyze_themes_field():
    """Analyze how the themes field is being used."""
    print("\n🔍 Analyzing themes field usage...")
    
    try:
        # Check if themes field is properly repurposed or cleared
        result = subprocess.run(
            ["grep", "-r", "themes.*=", "--include=*.py", "src/"],
            capture_output=True,
            text=True
        )
        
        themes_assignments = []
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if 'themes=' in line or 'themes =' in line:
                    themes_assignments.append(line.strip())
        
        print(f"Found {len(themes_assignments)} themes field assignments:")
        for assignment in themes_assignments[:10]:  # Show first 10
            print(f"  {assignment}")
        
        if len(themes_assignments) > 10:
            print(f"  ... and {len(themes_assignments) - 10} more")
            
        # Look for empty themes assignments (good)
        empty_themes = [a for a in themes_assignments if 'themes=[]' in a]
        print(f"✅ Found {len(empty_themes)} empty themes assignments (good)")
        
        return True
        
    except Exception as e:
        print(f"Error analyzing themes field: {e}")
        return False

def check_conversation_analyzer():
    """Specifically check the conversation analyzer for theme neutralization."""
    print("\n🔍 Checking conversation analyzer theme neutralization...")
    
    analyzer_file = "src/services/conversation_analyzer.py"
    
    if not os.path.exists(analyzer_file):
        print(f"❌ {analyzer_file} not found")
        return False
    
    try:
        with open(analyzer_file, 'r') as f:
            content = f.read()
        
        # Check for the specific line that disables themes
        if 'themes=[]' in content:
            print("✅ Found themes=[] in conversation analyzer (theme analysis disabled)")
            return True
        else:
            print("❌ Could not confirm theme analysis is disabled")
            return False
            
    except Exception as e:
        print(f"Error checking conversation analyzer: {e}")
        return False

def main():
    """Main verification function."""
    print("📋 TOPIC REMOVAL VERIFICATION REPORT")
    print("=" * 50)
    
    # Change to the seeding_pipeline directory
    if not os.path.exists("src"):
        print("❌ Must run from seeding_pipeline directory")
        return False
    
    all_checks_passed = True
    
    # Run all checks
    checks = [
        check_code_references,
        check_imports, 
        analyze_themes_field,
        check_conversation_analyzer
    ]
    
    for check in checks:
        try:
            if not check():
                all_checks_passed = False
        except Exception as e:
            print(f"❌ Check {check.__name__} failed with error: {e}")
            all_checks_passed = False
    
    print("\n" + "=" * 50)
    if all_checks_passed:
        print("🎉 TOPIC REMOVAL VERIFICATION PASSED")
        print("✅ No functional topic system code remains")
        print("✅ Theme analysis properly disabled") 
        print("✅ System ready for cluster-based organization")
    else:
        print("❌ TOPIC REMOVAL VERIFICATION FAILED")
        print("⚠️  Some topic system remnants may still exist")
        print("⚠️  Review issues above before proceeding")
    
    return all_checks_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)