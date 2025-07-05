#!/usr/bin/env python3
"""
Known Issues Management Script

Helper script for managing and updating known issues documentation.
Part of Phase 6: Test Failure Resolution

Usage:
    ./scripts/manage_known_issues.py list               # List all known issues
    ./scripts/manage_known_issues.py add                # Add new known issue
    ./scripts/manage_known_issues.py update ISSUE_ID    # Update existing issue
    ./scripts/manage_known_issues.py check              # Check if test failures match known issues
    ./scripts/manage_known_issues.py review             # Review issues for quarterly update
    ./scripts/manage_known_issues.py --help             # Show this help
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class KnownIssuesManager:
    """Manages known issues documentation and tracking."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.known_issues_file = self.project_root / "KNOWN_ISSUES.md"
        self.issues_data_file = self.project_root / "test_tracking" / "known_issues.json"
        
        # Ensure data file exists
        self.issues_data_file.parent.mkdir(exist_ok=True)
        if not self.issues_data_file.exists():
            self._save_issues_data([])
    
    def _load_issues_data(self) -> List[Dict[str, Any]]:
        """Load issues data from JSON file."""
        try:
            with open(self.issues_data_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_issues_data(self, issues: List[Dict[str, Any]]):
        """Save issues data to JSON file."""
        with open(self.issues_data_file, 'w') as f:
            json.dump(issues, f, indent=2, default=str)
    
    def list_known_issues(self):
        """List all known issues from the documentation."""
        if not self.known_issues_file.exists():
            print("📭 No known issues file found")
            return
        
        # Parse the markdown file for issues
        issues = self._parse_markdown_issues()
        
        if not issues:
            print("📭 No known issues found")
            return
        
        print(f"📋 Known Issues ({len(issues)} total):")
        print("-" * 80)
        print(f"{'ID':<3} {'Severity':<8} {'Category':<15} {'Title':<40} {'Status'}")
        print("-" * 80)
        
        for i, issue in enumerate(issues, 1):
            severity = issue.get('severity', '🟡')
            category = issue.get('category', 'Unknown')
            title = issue.get('title', 'Untitled')[:39]
            status = "Planned" if issue.get('fix_planned') else "No Fix"
            
            print(f"{i:<3} {severity:<8} {category:<15} {title:<40} {status}")
        
        print("-" * 80)
    
    def add_known_issue(self):
        """Interactively add a new known issue."""
        print("📝 Adding new known issue...")
        
        # Collect issue details
        title = input("Issue title: ").strip()
        if not title:
            print("❌ Title is required")
            return
        
        description = input("Description: ").strip()
        if not description:
            print("❌ Description is required")
            return
        
        # Severity selection
        print("\nSeverity levels:")
        severities = [
            ("🚨", "Critical", "Blocks all E2E functionality"),
            ("🔴", "High", "Blocks major functionality"),
            ("🟡", "Medium", "Impacts some functionality"),
            ("🟢", "Low", "Minor issues, workarounds available")
        ]
        
        for i, (icon, level, desc) in enumerate(severities, 1):
            print(f"  {i}. {icon} {level} - {desc}")
        
        try:
            sev_choice = int(input(f"Severity (1-{len(severities)}): "))
            severity_icon, severity_level, _ = severities[sev_choice - 1]
        except (ValueError, IndexError):
            severity_icon, severity_level = "🟡", "Medium"
            print(f"Using default: {severity_icon} {severity_level}")
        
        # Impact and workaround
        impact = input("Impact description: ").strip()
        workaround = input("Workaround (if any): ").strip()
        
        # Fix planning
        fix_planned = input("Is fix planned? (y/n): ").strip().lower() == 'y'
        timeline = ""
        if fix_planned:
            timeline = input("Fix timeline: ").strip()
        
        # Files affected
        files_affected = input("Files affected (comma-separated): ").strip()
        
        # Create issue data
        issue_data = {
            'id': f"issue_{int(datetime.now().timestamp())}",
            'title': title,
            'description': description,
            'severity_icon': severity_icon,
            'severity_level': severity_level,
            'impact': impact,
            'workaround': workaround,
            'fix_planned': fix_planned,
            'timeline': timeline,
            'files_affected': [f.strip() for f in files_affected.split(',') if f.strip()],
            'created_date': datetime.now().isoformat(),
            'category': self._determine_category(title, description)
        }
        
        # Save to data file
        issues = self._load_issues_data()
        issues.append(issue_data)
        self._save_issues_data(issues)
        
        # Update markdown file
        self._add_to_markdown(issue_data)
        
        print(f"✅ Known issue added: {issue_data['id']}")
    
    def check_test_failures(self):
        """Check if current test failures match known issues."""
        print("🔍 Checking test failures against known issues...")
        
        # This would integrate with the test failure tracking system
        try:
            from test_tracking import FailureTracker
            tracker = FailureTracker()
            active_failures = tracker.get_active_failures()
        except ImportError:
            print("❌ Cannot import failure tracker")
            return
        
        if not active_failures:
            print("✅ No active failures to check")
            return
        
        known_issues = self._load_issues_data()
        matched_issues = []
        unmatched_failures = []
        
        for failure in active_failures:
            matched = False
            for issue in known_issues:
                if self._failure_matches_issue(failure, issue):
                    matched_issues.append((failure, issue))
                    matched = True
                    break
            
            if not matched:
                unmatched_failures.append(failure)
        
        # Report results
        if matched_issues:
            print(f"\n✅ Matched {len(matched_issues)} failure(s) to known issues:")
            for failure, issue in matched_issues:
                print(f"   • {failure['test_name']} → {issue['title']}")
        
        if unmatched_failures:
            print(f"\n❓ {len(unmatched_failures)} unmatched failure(s) (may need new known issues):")
            for failure in unmatched_failures:
                print(f"   • {failure['test_name']}: {failure['metadata']['error_message'][:60]}...")
    
    def review_issues(self):
        """Review issues for quarterly update."""
        print("📅 Quarterly Known Issues Review")
        print("=" * 50)
        
        issues = self._load_issues_data()
        if not issues:
            print("📭 No issues to review")
            return
        
        # Check for stale issues
        now = datetime.now()
        stale_threshold = now - timedelta(days=90)  # 3 months
        
        stale_issues = []
        recent_issues = []
        
        for issue in issues:
            created = datetime.fromisoformat(issue['created_date'])
            if created < stale_threshold:
                stale_issues.append(issue)
            else:
                recent_issues.append(issue)
        
        print(f"📊 Review Summary:")
        print(f"   Total Issues: {len(issues)}")
        print(f"   Recent Issues (< 3 months): {len(recent_issues)}")
        print(f"   Stale Issues (> 3 months): {len(stale_issues)}")
        
        # Review stale issues
        if stale_issues:
            print(f"\n🕐 Stale Issues Requiring Review:")
            for issue in stale_issues:
                print(f"   • {issue['title']} (created {issue['created_date'][:10]})")
                if issue['fix_planned']:
                    print(f"     Timeline: {issue['timeline']}")
                else:
                    print(f"     Status: No fix planned")
        
        # Severity breakdown
        severity_counts = {}
        for issue in issues:
            severity = issue.get('severity_level', 'Unknown')
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        print(f"\n📈 Severity Breakdown:")
        for severity, count in severity_counts.items():
            print(f"   • {severity}: {count}")
        
        # Update review date
        self._update_review_date()
        print(f"\n✅ Review completed and documented")
    
    def _parse_markdown_issues(self) -> List[Dict[str, Any]]:
        """Parse issues from markdown file."""
        if not self.known_issues_file.exists():
            return []
        
        content = self.known_issues_file.read_text()
        issues = []
        
        # Simple parsing - look for issue headers and content
        sections = content.split('###')
        for section in sections[1:]:  # Skip the first split (before first ###)
            lines = section.strip().split('\n')
            if lines:
                title = lines[0].strip()
                
                # Extract severity (look for emoji)
                severity = "🟡"
                for line in lines:
                    if '**Severity**:' in line:
                        severity_match = re.search(r'(🚨|🔴|🟡|🟢)', line)
                        if severity_match:
                            severity = severity_match.group(1)
                        break
                
                # Determine category from section context
                category = "Unknown"
                if "Test Suite" in section or "test" in title.lower():
                    category = "Test Suite"
                elif "Pipeline" in section or "processing" in title.lower():
                    category = "Pipeline"
                elif "Infrastructure" in section or "database" in title.lower():
                    category = "Infrastructure"
                elif "Documentation" in section or "docs" in title.lower():
                    category = "Documentation"
                
                # Check if fix is planned
                fix_planned = "Fix Planned**: Yes" in section
                
                issues.append({
                    'title': title,
                    'severity': severity,
                    'category': category,
                    'fix_planned': fix_planned,
                    'content': section
                })
        
        return issues
    
    def _determine_category(self, title: str, description: str) -> str:
        """Determine issue category from title and description."""
        text = (title + " " + description).lower()
        
        if any(keyword in text for keyword in ['test', 'pytest', 'unittest']):
            return "Test Suite"
        elif any(keyword in text for keyword in ['vtt', 'processing', 'pipeline', 'extraction']):
            return "Pipeline"
        elif any(keyword in text for keyword in ['neo4j', 'database', 'connection', 'storage']):
            return "Infrastructure"
        elif any(keyword in text for keyword in ['docs', 'documentation', 'api']):
            return "Documentation"
        else:
            return "General"
    
    def _failure_matches_issue(self, failure: Dict[str, Any], issue: Dict[str, Any]) -> bool:
        """Check if a test failure matches a known issue."""
        # Simple matching based on keywords
        failure_text = (failure['test_name'] + " " + failure['metadata']['error_message']).lower()
        issue_text = (issue['title'] + " " + issue['description']).lower()
        
        # Look for common keywords
        keywords = issue_text.split()[:5]  # Use first 5 words as keywords
        matches = sum(1 for keyword in keywords if keyword in failure_text)
        
        # Consider it a match if at least 2 keywords match
        return matches >= 2
    
    def _add_to_markdown(self, issue_data: Dict[str, Any]):
        """Add issue to markdown file."""
        if not self.known_issues_file.exists():
            return
        
        content = self.known_issues_file.read_text()
        
        # Create new issue section
        new_section = f"""
### {issue_data['title']}

**Issue**: {issue_data['description']}  
**Severity**: {issue_data['severity_icon']} {issue_data['severity_level']}  
**Impact**: {issue_data['impact']}  
**Workaround**: {issue_data['workaround']}  
**Fix Planned**: {'Yes' if issue_data['fix_planned'] else 'No'}{' - ' + issue_data['timeline'] if issue_data['timeline'] else ''}  

**Files Affected**:
{chr(10).join(f'- `{file}`' for file in issue_data['files_affected']) if issue_data['files_affected'] else '- None specified'}

---
"""
        
        # Insert before the "## Workaround Procedures" section
        insert_point = content.find("## Workaround Procedures")
        if insert_point != -1:
            updated_content = content[:insert_point] + new_section + content[insert_point:]
            self.known_issues_file.write_text(updated_content)
    
    def _update_review_date(self):
        """Update the review date in the markdown file."""
        if not self.known_issues_file.exists():
            return
        
        content = self.known_issues_file.read_text()
        
        # Update next review date (3 months from now)
        next_review = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        
        # Replace the next review line
        updated_content = re.sub(
            r'\*\*Next Review\*\*: \d{4}-\d{2}-\d{2}',
            f'**Next Review**: {next_review}',
            content
        )
        
        self.known_issues_file.write_text(updated_content)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    
    command = sys.argv[1].lower()
    manager = KnownIssuesManager()
    
    try:
        if command == 'list':
            manager.list_known_issues()
        elif command == 'add':
            manager.add_known_issue()
        elif command == 'check':
            manager.check_test_failures()
        elif command == 'review':
            manager.review_issues()
        elif command == '--help' or command == 'help':
            print(__doc__)
        else:
            print(f"❌ Unknown command: {command}")
            print("Use --help for usage information")
            return 1
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())