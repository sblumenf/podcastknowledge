#!/usr/bin/env python3
"""
VTT Pipeline Quick Start Script (Python version).

Cross-platform quickstart for the VTT Knowledge Pipeline.
Gets you from fresh clone to working pipeline in <5 minutes.
"""

import os
import sys
import subprocess
import platform
import time
import shutil
from pathlib import Path

# ANSI color codes (with Windows support)
if platform.system() == 'Windows':
    try:
        import colorama
        colorama.init()
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        RESET = '\033[0m'
    except ImportError:
        GREEN = YELLOW = RED = RESET = ''
else:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'


class QuickStart:
    """Quick start installer for VTT Pipeline."""
    
    def __init__(self):
        self.python_cmd = sys.executable
        self.os_type = platform.system().lower()
        self.start_time = time.time()
        self.errors = []
        
    def print_header(self, message):
        """Print section header."""
        print(f"\n{GREEN}==== {message} ===={RESET}")
    
    def print_error(self, message):
        """Print error message."""
        print(f"{RED}Error: {message}{RESET}")
        self.errors.append(message)
    
    def print_warning(self, message):
        """Print warning message."""
        print(f"{YELLOW}Warning: {message}{RESET}")
    
    def print_success(self, message):
        """Print success message."""
        print(f"{GREEN}✓ {message}{RESET}")
    
    def run_command(self, cmd, shell=False, capture=True):
        """Run a command and return result."""
        try:
            if capture:
                result = subprocess.run(
                    cmd, shell=shell, capture_output=True, 
                    text=True, check=True
                )
                return result.stdout
            else:
                subprocess.run(cmd, shell=shell, check=True)
                return True
        except subprocess.CalledProcessError as e:
            return None
    
    def check_python(self):
        """Check Python version."""
        self.print_header("Checking Python Version")
        
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"
        
        if version.major < 3 or (version.major == 3 and version.minor < 11):
            self.print_error(f"Python 3.11+ required. Found: {version_str}")
            sys.exit(1)
        
        self.print_success(f"Python {version_str} detected")
    
    def setup_venv(self):
        """Create and activate virtual environment."""
        self.print_header("Setting Up Virtual Environment")
        
        venv_path = Path("venv")
        
        if venv_path.exists():
            self.print_warning("Virtual environment already exists")
        else:
            # Create virtual environment
            result = self.run_command([self.python_cmd, "-m", "venv", "venv"])
            if result is False:
                self.print_error("Failed to create virtual environment")
                sys.exit(1)
            self.print_success("Virtual environment created")
        
        # Show activation instructions
        print("\nTo activate the virtual environment:")
        if self.os_type == "windows":
            print("  venv\\Scripts\\activate")
        else:
            print("  source venv/bin/activate")
        
        # Update pip in venv
        if self.os_type == "windows":
            pip_cmd = str(venv_path / "Scripts" / "pip")
        else:
            pip_cmd = str(venv_path / "bin" / "pip")
        
        if Path(pip_cmd).exists():
            self.run_command([pip_cmd, "install", "--upgrade", "pip"], capture=False)
            self.print_success("Pip upgraded in virtual environment")
    
    def install_deps(self):
        """Install dependencies."""
        self.print_header("Installing Dependencies")
        
        # Check memory to decide which requirements to use
        try:
            import psutil
            available_mb = psutil.virtual_memory().available // (1024 * 1024)
            if available_mb < 2048:
                self.print_warning(f"Low memory detected: {available_mb}MB available")
                requirements = "requirements-core.txt"
            else:
                requirements = "requirements-core.txt"
        except:
            # Default to core requirements if can't detect
            requirements = "requirements-core.txt"
        
        if not Path(requirements).exists():
            self.print_error(f"{requirements} not found")
            sys.exit(1)
        
        # Get pip command
        venv_path = Path("venv")
        if self.os_type == "windows":
            pip_cmd = str(venv_path / "Scripts" / "pip")
        else:
            pip_cmd = str(venv_path / "bin" / "pip")
        
        if not Path(pip_cmd).exists():
            self.print_error("Virtual environment pip not found. Activate venv first.")
            return
        
        # Install requirements
        print(f"Installing from {requirements}...")
        result = self.run_command(
            [pip_cmd, "install", "-r", requirements],
            capture=False
        )
        
        if result is None:
            self.print_error("Failed to install dependencies")
            self.print_warning(f"Try manually: pip install -r {requirements}")
        else:
            self.print_success("Dependencies installed")
    
    def setup_config(self):
        """Set up configuration file."""
        self.print_header("Setting Up Configuration")
        
        env_file = Path(".env")
        template_file = Path(".env.template")
        
        if env_file.exists():
            self.print_warning(".env file already exists")
            response = input("Overwrite? (y/N): ").strip().lower()
            if response != 'y':
                self.print_success("Keeping existing .env file")
                return
        
        if not template_file.exists():
            self.print_error(".env.template not found")
            return
        
        # Copy template
        shutil.copy(template_file, env_file)
        self.print_success("Created .env from template")
        
        print("\n" + "="*50)
        self.print_warning("ACTION REQUIRED: Edit .env file with your credentials")
        print("Required settings:")
        print("  - NEO4J_PASSWORD: Your Neo4j database password")
        print("  - GOOGLE_API_KEY: Your Google API key")
        print("    Get from: https://makersuite.google.com/app/apikey")
        print("="*50 + "\n")
        
        # Offer to open in editor
        if self.os_type == "windows":
            response = input("Open .env in notepad? (y/N): ").strip().lower()
            if response == 'y':
                subprocess.run(["notepad", ".env"], shell=True)
        elif self.os_type == "darwin":  # macOS
            response = input("Open .env in default editor? (y/N): ").strip().lower()
            if response == 'y':
                subprocess.run(["open", ".env"])
        else:  # Linux
            if shutil.which("nano"):
                response = input("Open .env in nano? (y/N): ").strip().lower()
                if response == 'y':
                    subprocess.run(["nano", ".env"])
    
    def setup_directories(self):
        """Create required directories."""
        self.print_header("Creating Required Directories")
        
        dirs = ["checkpoints", "output", "logs"]
        for dir_name in dirs:
            dir_path = Path(dir_name)
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                self.print_success(f"Created {dir_name}/")
            else:
                self.print_success(f"{dir_name}/ already exists")
    
    def validate_deployment(self):
        """Run deployment validation."""
        self.print_header("Validating Deployment")
        
        validation_script = Path("scripts/validate_deployment.py")
        if validation_script.exists():
            result = self.run_command(
                [self.python_cmd, str(validation_script)],
                capture=False
            )
            if result is None:
                self.print_warning("Some validation checks failed. This is normal for first setup.")
        else:
            self.print_warning("Validation script not found")
    
    def show_next_steps(self):
        """Show next steps to user."""
        duration = int(time.time() - self.start_time)
        
        self.print_header("Setup Complete!")
        print(f"Time taken: {duration} seconds")
        
        print("\nNext steps:")
        print("1. Edit .env file with your credentials (if not done already)")
        print("2. Start Neo4j database (if using)")
        print("3. Activate virtual environment:")
        if self.os_type == "windows":
            print("   venv\\Scripts\\activate")
        else:
            print("   source venv/bin/activate")
        print("4. Test the installation:")
        print(f"   {self.python_cmd} -m src.cli.cli --help")
        print("5. Process your first VTT file:")
        print(f"   {self.python_cmd} src/cli/minimal_cli.py sample.vtt")
        
        if duration > 300:
            self.print_warning("Setup took longer than 5 minutes.")
        else:
            self.print_success("Setup completed in under 5 minutes!")
        
        if self.errors:
            print(f"\n{RED}There were errors during setup:{RESET}")
            for error in self.errors:
                print(f"  - {error}")
    
    def run(self):
        """Run the quick start process."""
        print("===================================")
        print("VTT Pipeline Quick Start")
        print("===================================")
        
        try:
            self.check_python()
            self.setup_venv()
            self.install_deps()
            self.setup_config()
            self.setup_directories()
            self.validate_deployment()
            self.show_next_steps()
            
            return 0 if not self.errors else 1
            
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Setup interrupted by user{RESET}")
            return 1
        except Exception as e:
            self.print_error(f"Unexpected error: {e}")
            return 1


def main():
    """Main entry point."""
    quickstart = QuickStart()
    return quickstart.run()


if __name__ == "__main__":
    sys.exit(main())