#!/usr/bin/env python3
"""
Security audit script for the Podcast Knowledge Graph Pipeline.

This script checks for:
1. Hardcoded secrets and API keys
2. Sensitive data in configuration files
3. Proper use of environment variables
4. Secure coding practices
"""

import os
import re
import json
from pathlib import Path
from typing import List, Tuple, Dict, Any

# Patterns that might indicate secrets
SECRET_PATTERNS = [
    # API Keys and tokens
    (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?[\w-]{20,}', 'Potential API key'),
    (r'(?i)(secret|token)\s*[:=]\s*["\']?[\w-]{20,}', 'Potential secret/token'),
    (r'(?i)bearer\s+[\w-]{20,}', 'Potential bearer token'),
    
    # Passwords
    (r'(?i)password\s*[:=]\s*["\']?(?!password|example|changeme|xxx+)[^\s"\']{8,}', 'Potential password'),
    (r'(?i)passwd\s*[:=]\s*["\']?(?!password|example|changeme|xxx+)[^\s"\']{8,}', 'Potential password'),
    
    # Private keys
    (r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----', 'Private key detected'),
    (r'(?i)private[_-]?key\s*[:=]\s*["\']?[\w/+=]{40,}', 'Potential private key'),
    
    # Database URLs with credentials
    (r'(?i)(postgres|mysql|mongodb|redis)://[^:]+:[^@]+@[^\s]+', 'Database URL with credentials'),
    
    # AWS credentials
    (r'(?i)aws[_-]?access[_-]?key[_-]?id\s*[:=]\s*["\']?[\w]{20}', 'AWS Access Key'),
    (r'(?i)aws[_-]?secret[_-]?access[_-]?key\s*[:=]\s*["\']?[\w/+=]{40}', 'AWS Secret Key'),
    
    # Google credentials
    (r'(?i)google[_-]?api[_-]?key\s*[:=]\s*["\']?AIza[\w-]{35}', 'Google API Key'),
    
    # Generic credentials
    (r'(?i)credentials?\s*[:=]\s*\{[^}]+password[^}]+\}', 'Credentials object with password'),
]

# Files/directories to skip
SKIP_PATHS = {
    '.git', '__pycache__', '.pytest_cache', 'htmlcov', 
    'node_modules', 'venv', '.venv', 'env', '.env.example',
    'test_', 'mock_', 'fake_', 'example'
}

# Safe patterns (to reduce false positives)
SAFE_PATTERNS = [
    r'(?i)password\s*[:=]\s*["\']?(password|example|changeme|xxx+|<.*?>|\$\{.*?\})',
    r'(?i)api[_-]?key\s*[:=]\s*["\']?(your[_-]?api[_-]?key|api[_-]?key[_-]?here|xxx+|\$\{.*?\})',
    r'(?i)secret\s*[:=]\s*["\']?(your[_-]?secret|secret[_-]?here|xxx+|\$\{.*?\})',
]


def should_skip_path(path: Path) -> bool:
    """Check if a path should be skipped."""
    path_str = str(path).lower()
    return any(skip in path_str for skip in SKIP_PATHS)


def is_safe_match(content: str, match_start: int, match_end: int) -> bool:
    """Check if a potential secret match is actually safe."""
    match_text = content[match_start:match_end]
    return any(re.search(pattern, match_text) for pattern in SAFE_PATTERNS)


def scan_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Scan a single file for potential secrets."""
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        for line_num, line in enumerate(content.splitlines(), 1):
            for pattern, description in SECRET_PATTERNS:
                for match in re.finditer(pattern, line):
                    if not is_safe_match(line, match.start(), match.end()):
                        issues.append((line_num, description, line.strip()))
                        
    except Exception as e:
        # Skip files that can't be read
        pass
        
    return issues


def check_env_usage(project_root: Path) -> Dict[str, Any]:
    """Check proper usage of environment variables."""
    env_issues = {
        'missing_env_example': False,
        'env_in_git': False,
        'hardcoded_in_config': [],
    }
    
    # Check for .env.example
    if not (project_root / '.env.example').exists():
        env_issues['missing_env_example'] = True
    
    # Check if .env is in git
    gitignore_path = project_root / '.gitignore'
    if gitignore_path.exists():
        with open(gitignore_path) as f:
            gitignore_content = f.read()
            if '.env' not in gitignore_content:
                env_issues['env_in_git'] = True
    
    # Check config files for hardcoded values
    config_dir = project_root / 'config'
    if config_dir.exists():
        for config_file in config_dir.glob('*.yml'):
            if 'example' not in config_file.name:
                with open(config_file) as f:
                    content = f.read()
                    if re.search(r'password:\s*[^$\s]+', content):
                        env_issues['hardcoded_in_config'].append(str(config_file))
    
    return env_issues


def audit_security(project_root: Path) -> Dict[str, Any]:
    """Run complete security audit."""
    print("🔒 Starting security audit...")
    
    results = {
        'total_files_scanned': 0,
        'files_with_issues': [],
        'total_issues': 0,
        'issues_by_type': {},
        'env_issues': {},
        'critical_issues': []
    }
    
    # Scan all Python and configuration files
    patterns = ['**/*.py', '**/*.yml', '**/*.yaml', '**/*.json', '**/*.env', '**/*.sh']
    
    for pattern in patterns:
        for file_path in project_root.glob(pattern):
            if should_skip_path(file_path):
                continue
                
            results['total_files_scanned'] += 1
            issues = scan_file(file_path)
            
            if issues:
                results['files_with_issues'].append({
                    'path': str(file_path.relative_to(project_root)),
                    'issues': issues
                })
                results['total_issues'] += len(issues)
                
                for _, issue_type, _ in issues:
                    results['issues_by_type'][issue_type] = \
                        results['issues_by_type'].get(issue_type, 0) + 1
                    
                    # Mark critical issues
                    if any(critical in issue_type.lower() 
                           for critical in ['private key', 'password', 'aws']):
                        results['critical_issues'].append(
                            f"{file_path.relative_to(project_root)}: {issue_type}"
                        )
    
    # Check environment variable usage
    results['env_issues'] = check_env_usage(project_root)
    
    return results


def generate_report(results: Dict[str, Any]) -> str:
    """Generate a security audit report."""
    report = ["# Security Audit Report", ""]
    
    # Summary
    report.append("## Summary")
    report.append(f"- Files scanned: {results['total_files_scanned']}")
    report.append(f"- Files with issues: {len(results['files_with_issues'])}")
    report.append(f"- Total potential issues: {results['total_issues']}")
    report.append(f"- Critical issues: {len(results['critical_issues'])}")
    report.append("")
    
    # Critical issues
    if results['critical_issues']:
        report.append("## 🚨 Critical Issues")
        for issue in results['critical_issues']:
            report.append(f"- {issue}")
        report.append("")
    
    # Issues by type
    if results['issues_by_type']:
        report.append("## Issues by Type")
        for issue_type, count in sorted(results['issues_by_type'].items()):
            report.append(f"- {issue_type}: {count}")
        report.append("")
    
    # Environment variable issues
    report.append("## Environment Configuration")
    env_issues = results['env_issues']
    
    if env_issues['missing_env_example']:
        report.append("- ❌ Missing .env.example file")
    else:
        report.append("- ✅ .env.example file exists")
        
    if env_issues['env_in_git']:
        report.append("- ❌ .env might be tracked in git (not in .gitignore)")
    else:
        report.append("- ✅ .env properly excluded from git")
        
    if env_issues['hardcoded_in_config']:
        report.append("- ❌ Potential hardcoded values in config files:")
        for config in env_issues['hardcoded_in_config']:
            report.append(f"  - {config}")
    else:
        report.append("- ✅ No hardcoded values in config files")
    report.append("")
    
    # Detailed findings
    if results['files_with_issues']:
        report.append("## Detailed Findings")
        for file_info in results['files_with_issues'][:10]:  # Limit to first 10
            report.append(f"\n### {file_info['path']}")
            for line_num, issue_type, line_content in file_info['issues'][:5]:
                report.append(f"- Line {line_num}: {issue_type}")
                report.append(f"  ```")
                report.append(f"  {line_content[:100]}...")
                report.append(f"  ```")
        
        if len(results['files_with_issues']) > 10:
            report.append(f"\n... and {len(results['files_with_issues']) - 10} more files")
    report.append("")
    
    # Recommendations
    report.append("## Recommendations")
    report.append("1. Review all identified potential secrets")
    report.append("2. Move any real secrets to environment variables")
    report.append("3. Ensure .env is in .gitignore")
    report.append("4. Use secret management tools in production")
    report.append("5. Rotate any exposed credentials")
    report.append("6. Set up pre-commit hooks to prevent future issues")
    
    return "\n".join(report)


def main():
    """Run the security audit."""
    project_root = Path(__file__).parent.parent
    
    # Run audit
    results = audit_security(project_root)
    
    # Generate report
    report = generate_report(results)
    
    # Save report
    report_path = project_root / "SECURITY_AUDIT_REPORT.md"
    with open(report_path, 'w') as f:
        f.write(report)
    
    # Print summary
    print(report)
    print(f"\n📄 Full report saved to: {report_path}")
    
    # Exit with error if critical issues found
    if results['critical_issues']:
        print("\n❌ Critical security issues found! Please review and fix.")
        return 1
    else:
        print("\n✅ No critical security issues found.")
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())