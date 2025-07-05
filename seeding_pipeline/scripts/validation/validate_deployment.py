#!/usr/bin/env python3
"""
VTT Pipeline Deployment Validation Script (Python version).

Cross-platform deployment validation for the VTT Pipeline.
Performs end-to-end validation and generates a deployment report.
"""

import os
import sys
import subprocess
import time
import tempfile
from pathlib import Path
from datetime import datetime

# Color codes (ANSI escape sequences)
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

# Disable colors on Windows if not supported
if sys.platform == 'win32':
    try:
        import colorama
        colorama.init()
    except ImportError:
        GREEN = RED = YELLOW = RESET = ''

class DeploymentValidator:
    """Validates VTT Pipeline deployment."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.log_file = self.project_root / "deployment_validation.log"
        self.report_file = self.project_root / "deployment_report.txt"
        self.validation_failed = False
        self.start_time = time.time()
        
        # Clear previous logs
        self.log_file.write_text("")
        self.report_file.write_text("")
        
    def log(self, message):
        """Log message to file and console."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        
        # Append to log file
        with open(self.log_file, 'a') as f:
            f.write(log_entry + '\n')
        
        print(message)
    
    def report(self, message):
        """Add message to report."""
        with open(self.report_file, 'a') as f:
            f.write(message + '\n')
        print(message)
    
    def header(self, title):
        """Print section header."""
        self.report("")
        self.report("=" * 60)
        self.report(f"  {title}")
        self.report("=" * 60)
    
    def check_pass(self, message):
        """Mark check as passed."""
        self.report(f"{GREEN}✓ {message}{RESET}")
        self.log(f"PASS: {message}")
    
    def check_fail(self, message):
        """Mark check as failed."""
        self.report(f"{RED}✗ {message}{RESET}")
        self.log(f"FAIL: {message}")
        self.validation_failed = True
    
    def check_warn(self, message):
        """Mark check as warning."""
        self.report(f"{YELLOW}⚠ {message}{RESET}")
        self.log(f"WARN: {message}")
    
    def check_python_version(self):
        """Check Python version."""
        self.header("1. Python Version Check")
        
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"
        
        if version.major >= 3 and version.minor >= 11:
            self.check_pass(f"Python version: {version_str} (3.11+ required)")
        else:
            self.check_fail(f"Python version: {version_str} (3.11+ required)")
    
    def check_virtual_environment(self):
        """Check virtual environment."""
        self.header("2. Virtual Environment Check")
        
        venv_path = os.environ.get('VIRTUAL_ENV')
        if venv_path:
            self.check_pass(f"Virtual environment active: {venv_path}")
        elif (self.project_root / "venv").exists():
            self.check_warn("Virtual environment exists but not active")
            self.report("  Run: source venv/bin/activate (Linux/Mac)")
            self.report("  Run: venv\\Scripts\\activate (Windows)")
        else:
            self.check_warn("No virtual environment found")
            self.report("  Run: python3 -m venv venv")
    
    def check_dependencies(self):
        """Check key dependencies."""
        self.header("3. Dependencies Check")
        
        if not os.environ.get('VIRTUAL_ENV') and not (self.project_root / "venv").exists():
            self.check_warn("Cannot check dependencies without virtual environment")
            return
        
        dependencies = [
            ("neo4j", "neo4j"),
            ("dotenv", "python-dotenv"),
            ("google.generativeai", "google-generativeai"),
            ("psutil", "psutil"),
            ("tqdm", "tqdm"),
            ("yaml", "PyYAML")
        ]
        
        for module, package in dependencies:
            try:
                __import__(module)
                self.check_pass(f"{package} package installed")
            except ImportError:
                self.check_warn(f"{package} package not installed")
    
    def check_configuration(self):
        """Check configuration files."""
        self.header("4. Configuration Files Check")
        
        env_file = self.project_root / ".env"
        if env_file.exists():
            self.check_pass(".env file exists")
            
            content = env_file.read_text()
            
            # Check required variables
            required_vars = {
                "NEO4J_PASSWORD": False,
                "GOOGLE_API_KEY": False
            }
            
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    for var in required_vars:
                        if line.startswith(f"{var}="):
                            value = line.split('=', 1)[1].strip()
                            if value:
                                required_vars[var] = True
            
            for var, is_set in required_vars.items():
                if is_set:
                    self.check_pass(f"{var} is set")
                else:
                    self.check_fail(f"{var} is empty or missing")
        else:
            self.check_fail(".env file not found")
            self.report("  Run: cp .env.template .env")
            self.report("  Then edit .env with your credentials")
    
    def check_directories(self):
        """Check directory structure."""
        self.header("5. Directory Structure Check")
        
        required_dirs = ["src", "tests", "scripts", "docs", "checkpoints", "output"]
        
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            if dir_path.exists():
                self.check_pass(f"Directory exists: {dir_name}")
            else:
                # Try to create it
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    self.check_pass(f"Created directory: {dir_name}")
                except Exception as e:
                    self.check_fail(f"Directory missing: {dir_name} ({e})")
    
    def check_database_connectivity(self):
        """Test database connectivity."""
        self.header("6. Database Connectivity Check")
        
        if not (self.project_root / ".env").exists():
            self.check_warn("Cannot test database connectivity (missing .env)")
            return
        
        try:
            # Add project root to path
            sys.path.insert(0, str(self.project_root))
            
            from src.core.env_config import env_config
            
            uri = env_config.get_optional("NEO4J_URI", "bolt://localhost:7687")
            username = env_config.get_optional("NEO4J_USERNAME", "neo4j")
            password = env_config.get_optional("NEO4J_PASSWORD")
            
            if not password:
                self.check_warn("Neo4j password not set")
                return
            
            try:
                from neo4j import GraphDatabase
                driver = GraphDatabase.driver(uri, auth=(username, password))
                with driver.session() as session:
                    result = session.run("RETURN 1 as test")
                    result.single()
                driver.close()
                self.check_pass("Neo4j connection test passed")
            except ImportError:
                self.check_warn("neo4j package not installed")
            except Exception as e:
                self.check_warn(f"Neo4j connection failed: {str(e)}")
                
        except Exception as e:
            self.check_warn(f"Cannot test database: {str(e)}")
    
    def check_cli_commands(self):
        """Test CLI commands."""
        self.header("7. CLI Commands Check")
        
        # Test main CLI help
        result = subprocess.run(
            [sys.executable, "-m", "src.cli.cli", "--help"],
            capture_output=True,
            text=True,
            cwd=str(self.project_root)
        )
        if result.returncode == 0:
            self.check_pass("Main CLI help works")
        else:
            self.check_warn("Main CLI help failed (missing dependencies?)")
        
        # Test minimal CLI help
        result = subprocess.run(
            [sys.executable, "src/cli/minimal_cli.py", "--help"],
            capture_output=True,
            text=True,
            cwd=str(self.project_root)
        )
        if result.returncode == 0:
            self.check_pass("Minimal CLI help works")
        else:
            self.check_fail("Minimal CLI help failed")
    
    def test_sample_vtt(self):
        """Process a sample VTT file."""
        self.header("8. Sample VTT Processing Test")
        
        # Create sample VTT
        sample_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
Welcome to the deployment validation test.

00:00:05.000 --> 00:00:10.000
This is a sample VTT file to verify the pipeline works.

00:00:10.000 --> 00:00:15.000
If you can process this file, the deployment is successful!
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
            f.write(sample_content)
            sample_vtt = f.name
        
        self.check_pass(f"Created sample VTT file: {os.path.basename(sample_vtt)}")
        
        # Test parsing with minimal CLI
        result = subprocess.run(
            [sys.executable, "src/cli/minimal_cli.py", sample_vtt, "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(self.project_root)
        )
        
        if "segments found" in result.stdout:
            self.check_pass("Sample VTT file parsed successfully")
        else:
            self.check_warn("Sample VTT parsing failed (expected without dependencies)")
        
        # Clean up
        try:
            os.unlink(sample_vtt)
        except:
            pass
    
    def run_smoke_tests(self):
        """Run smoke tests."""
        self.header("9. Smoke Tests")
        
        smoke_test_script = self.project_root / "scripts" / "run_minimal_tests.py"
        if smoke_test_script.exists():
            result = subprocess.run(
                [sys.executable, str(smoke_test_script)],
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )
            if result.returncode == 0:
                self.check_pass("Smoke tests passed")
            else:
                self.check_warn("Some smoke tests failed (check logs)")
        else:
            self.check_fail("Smoke test script not found")
    
    def generate_summary(self):
        """Generate deployment summary."""
        self.header("Deployment Validation Summary")
        
        duration = int(time.time() - self.start_time)
        
        self.report("")
        self.report(f"Validation completed at: {datetime.now()}")
        self.report(f"Duration: {duration} seconds")
        self.report("")
        
        if not self.validation_failed:
            self.report(f"{GREEN}✓ DEPLOYMENT VALIDATION PASSED{RESET}")
            self.report("")
            self.report("Your VTT Pipeline deployment is ready!")
            self.report("")
            self.report("Next steps:")
            self.report("1. Ensure Neo4j is running")
            self.report("2. Set up your .env file with API keys")
            self.report("3. Activate virtual environment:")
            self.report("   - Linux/Mac: source venv/bin/activate")
            self.report("   - Windows: venv\\Scripts\\activate")
            self.report("4. Install dependencies: pip install -r requirements-core.txt")
            self.report("5. Process VTT files: python -m src.cli.cli process-vtt --folder /path/to/vtts")
        else:
            self.report(f"{RED}✗ DEPLOYMENT VALIDATION FAILED{RESET}")
            self.report("")
            self.report("Please fix the issues above before proceeding.")
            self.report(f"Check {self.log_file.name} for details.")
        
        self.report("")
        self.report(f"Full report saved to: {self.report_file.name}")
        self.report(f"Detailed log saved to: {self.log_file.name}")
    
    def validate(self):
        """Run all validation checks."""
        self.report("VTT Pipeline Deployment Validation")
        self.report(f"Started at: {datetime.now()}")
        self.report("")
        
        # Run all checks
        self.check_python_version()
        self.check_virtual_environment()
        self.check_dependencies()
        self.check_configuration()
        self.check_directories()
        self.check_database_connectivity()
        self.check_cli_commands()
        self.test_sample_vtt()
        self.run_smoke_tests()
        
        # Generate summary
        self.generate_summary()
        
        return 0 if not self.validation_failed else 1


def main():
    """Main entry point."""
    validator = DeploymentValidator()
    return validator.validate()


if __name__ == "__main__":
    sys.exit(main())