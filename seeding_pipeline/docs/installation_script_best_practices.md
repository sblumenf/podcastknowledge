# Installation Script Best Practices for AI Agents

This guide provides foolproof patterns for creating cross-platform installation scripts that work reliably with AI agents.

## Table of Contents
1. [Virtual Environment Detection](#virtual-environment-detection)
2. [Cross-Platform Compatibility](#cross-platform-compatibility)
3. [Error Handling](#error-handling)
4. [Progress Indicators](#progress-indicators)
5. [Complete Example Script](#complete-example-script)

## Virtual Environment Detection

### The Foolproof Method

```python
import sys
import os

def detect_virtual_environment():
    """Comprehensive virtual environment detection that works in all scenarios."""
    
    # Method 1: Most reliable - compare sys.prefix with base_prefix
    def get_base_prefix_compat():
        """Get base/real prefix, or sys.prefix if there is none."""
        return (
            getattr(sys, "base_prefix", None) or  # Python 3.3+ venv
            getattr(sys, "real_prefix", None) or  # virtualenv
            sys.prefix
        )
    
    base_prefix = get_base_prefix_compat()
    in_venv = sys.prefix != base_prefix
    
    # Method 2: Check VIRTUAL_ENV environment variable (less reliable)
    virtual_env_path = os.getenv('VIRTUAL_ENV')
    
    # Method 3: Check if we're in a conda environment
    conda_prefix = os.getenv('CONDA_PREFIX')
    
    return {
        'is_virtual': in_venv or bool(virtual_env_path) or bool(conda_prefix),
        'type': 'conda' if conda_prefix else ('venv' if in_venv else None),
        'path': conda_prefix or virtual_env_path or (sys.prefix if in_venv else None),
        'python_executable': sys.executable,
        'sys_prefix': sys.prefix,
        'base_prefix': base_prefix
    }
```

### Key Points
- **Don't rely solely on VIRTUAL_ENV**: It's only set when using `activate` script
- **Direct execution works**: Running `venv/bin/python` directly is valid
- **Always use sys.executable**: Ensures correct Python interpreter

## Cross-Platform Compatibility

### Platform Detection

```python
import platform
import os

def get_platform_info():
    """Get comprehensive platform information."""
    return {
        'system': platform.system(),  # 'Windows', 'Linux', 'Darwin'
        'is_windows': platform.system() == 'Windows',
        'is_linux': platform.system() == 'Linux',
        'is_macos': platform.system() == 'Darwin',
        'python_version': platform.python_version(),
        'architecture': platform.machine(),
        'path_separator': os.pathsep,
        'dir_separator': os.sep,
        'shell': os.environ.get('SHELL', 'Unknown')
    }

def get_command_for_platform(base_command):
    """Adapt commands for different platforms."""
    platform_info = get_platform_info()
    
    if platform_info['is_windows']:
        # Windows-specific adaptations
        if base_command == 'clear':
            return 'cls'
        elif base_command == 'rm -rf':
            return 'rmdir /s /q'
    
    return base_command
```

### Path Handling

```python
import os
from pathlib import Path

def get_safe_path(path_str):
    """Convert path to platform-appropriate format."""
    return str(Path(path_str).resolve())

def ensure_directory(path):
    """Create directory if it doesn't exist (cross-platform)."""
    Path(path).mkdir(parents=True, exist_ok=True)
```

## Error Handling

### Comprehensive Error Handling Pattern

```python
import sys
import traceback
from typing import Optional, Dict, Any

class InstallationError(Exception):
    """Custom exception for installation errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}

def safe_install(func):
    """Decorator for safe execution with detailed error reporting."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            print("\n❌ Installation cancelled by user", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            error_info = {
                'function': func.__name__,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'traceback': traceback.format_exc()
            }
            
            # AI-friendly error output
            print(f"\n❌ Error in {func.__name__}: {type(e).__name__}", file=sys.stderr)
            print(f"   Message: {str(e)}", file=sys.stderr)
            
            if hasattr(e, 'details'):
                for key, value in e.details.items():
                    print(f"   {key}: {value}", file=sys.stderr)
            
            # Option to show full traceback
            if os.getenv('VERBOSE_ERRORS', '').lower() in ('1', 'true', 'yes'):
                print("\nFull traceback:", file=sys.stderr)
                print(error_info['traceback'], file=sys.stderr)
            
            raise InstallationError(f"Failed in {func.__name__}", error_info)
    
    return wrapper
```

### Retry Logic

```python
import time
from typing import Callable, Any

def retry_with_backoff(
    func: Callable,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Any:
    """Retry function with exponential backoff."""
    
    for attempt in range(max_attempts):
        try:
            return func()
        except exceptions as e:
            if attempt == max_attempts - 1:
                raise
            
            delay = initial_delay * (backoff_factor ** attempt)
            print(f"⚠️  Attempt {attempt + 1} failed: {str(e)}")
            print(f"   Retrying in {delay:.1f} seconds...")
            time.sleep(delay)
```

## Progress Indicators

### AI-Friendly Progress Bar Implementation

```python
import sys
import os
from typing import List, Optional
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

class AIFriendlyProgress:
    """Progress indicator that works well with AI agents and CI/CD systems."""
    
    def __init__(self, total: int, description: str = "Progress"):
        self.total = total
        self.current = 0
        self.description = description
        self.is_tty = sys.stdout.isatty()
        self.use_tqdm = TQDM_AVAILABLE and self.is_tty and not os.getenv('CI')
        
        if self.use_tqdm:
            self.pbar = tqdm(
                total=total,
                desc=description,
                file=sys.stderr,  # Don't interfere with stdout
                ascii=True,       # Better compatibility
                disable=None,     # Auto-disable in non-TTY
                mininterval=1.0   # Update at most once per second
            )
        else:
            # Simple progress for non-TTY environments
            print(f"🚀 Starting: {description} (0/{total})")
    
    def update(self, n: int = 1, message: Optional[str] = None):
        """Update progress bar."""
        self.current += n
        
        if self.use_tqdm:
            self.pbar.update(n)
            if message:
                tqdm.write(message)
        else:
            # Simple progress output for AI agents
            percent = (self.current / self.total) * 100
            status = "✓" if self.current == self.total else "→"
            print(f"{status} {self.description}: {self.current}/{self.total} ({percent:.0f}%)")
            if message:
                print(f"   {message}")
    
    def close(self):
        """Clean up progress bar."""
        if self.use_tqdm and hasattr(self, 'pbar'):
            self.pbar.close()
        else:
            print(f"✅ Completed: {self.description}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
```

### Usage Example

```python
def install_packages(packages: List[str]):
    """Install packages with progress indication."""
    
    with AIFriendlyProgress(len(packages), "Installing packages") as progress:
        for package in packages:
            try:
                # Actual installation logic here
                subprocess.check_call(
                    [sys.executable, '-m', 'pip', 'install', package],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                progress.update(1, f"✓ Installed {package}")
            except subprocess.CalledProcessError as e:
                progress.update(1, f"✗ Failed to install {package}")
                raise InstallationError(f"Failed to install {package}", {
                    'package': package,
                    'error': e.stderr.decode() if e.stderr else 'Unknown error'
                })
```

## Complete Example Script

Here's a complete installation script that incorporates all best practices:

```python
#!/usr/bin/env python3
"""
Foolproof installation script with AI-agent friendly output.
"""

import sys
import os
import subprocess
import platform
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
import time

# Constants
REQUIRED_PYTHON_VERSION = (3, 8)
DEFAULT_PACKAGES = ['requests', 'tqdm', 'rich']

class InstallationManager:
    """Manages the installation process with comprehensive error handling."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.env_info = self._detect_environment()
        self.platform_info = self._get_platform_info()
        self.errors: List[Dict[str, Any]] = []
        self.successful_installs: List[str] = []
    
    def _detect_environment(self) -> Dict[str, Any]:
        """Detect virtual environment and Python configuration."""
        base_prefix = (
            getattr(sys, "base_prefix", None) or
            getattr(sys, "real_prefix", None) or
            sys.prefix
        )
        
        in_venv = sys.prefix != base_prefix
        virtual_env_path = os.getenv('VIRTUAL_ENV')
        conda_prefix = os.getenv('CONDA_PREFIX')
        
        return {
            'python_version': sys.version,
            'python_executable': sys.executable,
            'is_virtual': in_venv or bool(virtual_env_path) or bool(conda_prefix),
            'venv_type': 'conda' if conda_prefix else ('venv' if in_venv else None),
            'venv_path': conda_prefix or virtual_env_path or (sys.prefix if in_venv else None),
            'sys_prefix': sys.prefix,
            'base_prefix': base_prefix
        }
    
    def _get_platform_info(self) -> Dict[str, Any]:
        """Get platform-specific information."""
        return {
            'system': platform.system(),
            'version': platform.version(),
            'machine': platform.machine(),
            'python_implementation': platform.python_implementation(),
            'is_windows': platform.system() == 'Windows',
            'is_linux': platform.system() == 'Linux',
            'is_macos': platform.system() == 'Darwin'
        }
    
    def print_status(self, message: str, status: str = "INFO"):
        """Print status message with appropriate formatting."""
        symbols = {
            'INFO': 'ℹ️ ',
            'SUCCESS': '✅',
            'WARNING': '⚠️ ',
            'ERROR': '❌',
            'PROGRESS': '→'
        }
        
        symbol = symbols.get(status, '')
        print(f"{symbol} {message}")
        
        if self.verbose and status == 'ERROR':
            print(f"   Platform: {self.platform_info['system']}")
            print(f"   Python: {sys.version.split()[0]}")
            print(f"   Virtual Env: {self.env_info['is_virtual']}")
    
    def check_python_version(self) -> bool:
        """Check if Python version meets requirements."""
        current_version = sys.version_info[:2]
        
        if current_version < REQUIRED_PYTHON_VERSION:
            self.print_status(
                f"Python {REQUIRED_PYTHON_VERSION[0]}.{REQUIRED_PYTHON_VERSION[1]}+ required, "
                f"but {current_version[0]}.{current_version[1]} found",
                "ERROR"
            )
            return False
        
        self.print_status(
            f"Python version check passed: {current_version[0]}.{current_version[1]}",
            "SUCCESS"
        )
        return True
    
    def check_virtual_environment(self) -> bool:
        """Check and report virtual environment status."""
        if not self.env_info['is_virtual']:
            self.print_status(
                "Not running in a virtual environment. It's recommended to use one.",
                "WARNING"
            )
            
            # Provide helpful instructions
            print("\nTo create a virtual environment:")
            if self.platform_info['is_windows']:
                print("  python -m venv venv")
                print("  .\\venv\\Scripts\\activate")
            else:
                print("  python3 -m venv venv")
                print("  source venv/bin/activate")
            
            # Ask for confirmation
            response = input("\nContinue without virtual environment? [y/N]: ")
            return response.lower() == 'y'
        
        self.print_status(
            f"Running in {self.env_info['venv_type']} virtual environment",
            "SUCCESS"
        )
        return True
    
    def install_package(self, package: str) -> bool:
        """Install a single package with error handling."""
        try:
            # Use the current Python executable
            cmd = [sys.executable, '-m', 'pip', 'install', package]
            
            # Add verbosity if requested
            if self.verbose:
                cmd.append('-v')
            
            # Run installation
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            self.successful_installs.append(package)
            return True
            
        except subprocess.CalledProcessError as e:
            error_info = {
                'package': package,
                'return_code': e.returncode,
                'stdout': e.stdout,
                'stderr': e.stderr
            }
            self.errors.append(error_info)
            
            # Extract meaningful error message
            if "No matching distribution" in e.stderr:
                self.print_status(f"Package '{package}' not found in PyPI", "ERROR")
            elif "Permission denied" in e.stderr:
                self.print_status(f"Permission denied installing '{package}'", "ERROR")
            else:
                self.print_status(f"Failed to install '{package}'", "ERROR")
                if self.verbose:
                    print(f"   Error: {e.stderr.strip()}")
            
            return False
    
    def install_packages(self, packages: List[str]) -> bool:
        """Install multiple packages with progress tracking."""
        self.print_status(f"Installing {len(packages)} packages...", "INFO")
        
        # Check if we can import tqdm for nice progress bars
        try:
            from tqdm import tqdm
            use_tqdm = sys.stdout.isatty() and not os.getenv('CI')
        except ImportError:
            use_tqdm = False
        
        if use_tqdm:
            # Use tqdm progress bar
            from tqdm import tqdm
            with tqdm(packages, desc="Installing", file=sys.stderr) as pbar:
                for package in pbar:
                    pbar.set_description(f"Installing {package}")
                    success = self.install_package(package)
                    if success:
                        tqdm.write(f"✅ {package}")
                    else:
                        tqdm.write(f"❌ {package}")
        else:
            # Simple progress for CI/CD environments
            for i, package in enumerate(packages, 1):
                self.print_status(
                    f"Installing {package} ({i}/{len(packages)})",
                    "PROGRESS"
                )
                success = self.install_package(package)
                if success:
                    self.print_status(f"Installed {package}", "SUCCESS")
        
        # Summary
        total = len(packages)
        successful = len(self.successful_installs)
        failed = len(self.errors)
        
        print(f"\n📊 Installation Summary:")
        print(f"   Total packages: {total}")
        print(f"   ✅ Successful: {successful}")
        print(f"   ❌ Failed: {failed}")
        
        return failed == 0
    
    def save_report(self, filepath: str = "installation_report.json"):
        """Save detailed installation report for debugging."""
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'environment': self.env_info,
            'platform': self.platform_info,
            'successful_installs': self.successful_installs,
            'errors': self.errors
        }
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.print_status(f"Detailed report saved to {filepath}", "INFO")

def main():
    """Main installation function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Foolproof installation script with AI-friendly output"
    )
    parser.add_argument(
        'packages',
        nargs='*',
        default=DEFAULT_PACKAGES,
        help='Packages to install'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--report',
        default='installation_report.json',
        help='Path to save installation report'
    )
    
    args = parser.parse_args()
    
    # Initialize installation manager
    installer = InstallationManager(verbose=args.verbose)
    
    print("🚀 Starting installation process...\n")
    
    # Pre-flight checks
    if not installer.check_python_version():
        sys.exit(1)
    
    if not installer.check_virtual_environment():
        sys.exit(1)
    
    # Install packages
    success = installer.install_packages(args.packages)
    
    # Save report
    if installer.errors:
        installer.save_report(args.report)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
```

## Key Takeaways for AI Agents

1. **Always detect environment properly**: Use multiple methods, don't rely on VIRTUAL_ENV alone
2. **Use stderr for progress**: Keeps stdout clean for actual output
3. **Provide clear error messages**: Include actionable information
4. **Support non-TTY environments**: Detect and adapt for CI/CD systems
5. **Save detailed reports**: JSON reports help with debugging
6. **Use exit codes**: 0 for success, non-zero for failure
7. **Handle interrupts gracefully**: Catch KeyboardInterrupt
8. **Platform-specific adaptations**: Test for Windows, Linux, and macOS

This approach ensures installation scripts work reliably across all environments and provide clear, parseable output for AI agents.