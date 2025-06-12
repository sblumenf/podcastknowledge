#!/usr/bin/env python3
"""
Validate environment setup for VTT Pipeline.

This script checks:
1. Python version compatibility
2. Required environment variables
3. Optional environment variables and their defaults
4. Database connectivity (if credentials provided)
5. API key validity (if provided)
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to import env_config, but handle missing dependencies
try:
    from src.core.env_config import EnvironmentConfig, env_config
    ENV_CONFIG_AVAILABLE = True
except ImportError as e:
    ENV_CONFIG_AVAILABLE = False
    ENV_CONFIG_ERROR = str(e)


def check_python_version() -> Tuple[bool, str]:
    """Check if Python version meets requirements."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        return False, f"Python 3.11+ required, found {version.major}.{version.minor}.{version.micro}"
    return True, f"Python {version.major}.{version.minor}.{version.micro} ✓"


def check_env_file() -> Tuple[bool, str]:
    """Check if .env file exists."""
    env_path = Path('.env')
    if env_path.exists():
        return True, f".env file found at {env_path.absolute()} ✓"
    else:
        template_path = Path('.env.template')
        if template_path.exists():
            return False, ".env file not found. Copy .env.template to .env and update values"
        else:
            return False, ".env file not found and .env.template is missing"


def check_required_vars() -> Tuple[bool, List[str]]:
    """Check required environment variables for basic operation."""
    required_for_operation = [
        ("NEO4J_PASSWORD", "Neo4j database password"),
        ("GOOGLE_API_KEY", "Google API key for LLM processing")
    ]
    
    missing = []
    for var, description in required_for_operation:
        if not os.getenv(var):
            missing.append(f"  - {var}: {description}")
    
    return len(missing) == 0, missing


def check_neo4j_connection() -> Tuple[bool, str]:
    """Test Neo4j connection if credentials are provided."""
    if not ENV_CONFIG_AVAILABLE:
        return False, "Cannot check Neo4j connection (env_config not available)"
    
    try:
        # Get connection details
        uri = env_config.get_optional("NEO4J_URI", "bolt://localhost:7687")
        username = env_config.get_optional("NEO4J_USERNAME", "neo4j") 
        password = env_config.get_optional("NEO4J_PASSWORD")
        
        if not password:
            return False, "Neo4j password not set, cannot test connection"
        
        # Try to import and connect
        try:
            from neo4j import GraphDatabase
        except ImportError:
            return False, "neo4j package not installed. Run: pip install neo4j"
        
        # Attempt connection
        driver = None
        try:
            driver = GraphDatabase.driver(uri, auth=(username, password))
            with driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()
            return True, f"Neo4j connection successful to {uri} ✓"
        except Exception as e:
            return False, f"Neo4j connection failed: {str(e)}"
        finally:
            if driver:
                driver.close()
                
    except Exception as e:
        return False, f"Error checking Neo4j: {str(e)}"


def check_google_api_key() -> Tuple[bool, str]:
    """Validate Google API key if provided."""
    if not ENV_CONFIG_AVAILABLE:
        api_key = os.getenv("GOOGLE_API_KEY")
    else:
        api_key = env_config.get_optional("GOOGLE_API_KEY")
    
    if not api_key:
        return False, "Google API key not set"
    
    # Basic validation - check length and format
    if len(api_key) < 30:
        return False, "Google API key appears to be invalid (too short)"
    
    # Could do actual API test here if needed
    return True, "Google API key configured ✓"


def check_directories() -> List[Tuple[str, bool, str]]:
    """Check required directories exist or can be created."""
    if not ENV_CONFIG_AVAILABLE:
        directories = [
            (os.getenv("CHECKPOINT_DIR", "checkpoints"), "Checkpoint directory"),
            (os.getenv("OUTPUT_DIR", "output"), "Output directory"),
        ]
    else:
        directories = [
            (env_config.get_optional("CHECKPOINT_DIR", "checkpoints"), "Checkpoint directory"),
            (env_config.get_optional("OUTPUT_DIR", "output"), "Output directory"),
        ]
    
    results = []
    for dir_path, description in directories:
        path = Path(dir_path)
        if path.exists():
            results.append((description, True, f"{dir_path} exists ✓"))
        else:
            try:
                path.mkdir(parents=True, exist_ok=True)
                results.append((description, True, f"{dir_path} created ✓"))
            except Exception as e:
                results.append((description, False, f"{dir_path} cannot be created: {e}"))
    
    return results


def print_configuration_summary():
    """Print current configuration summary."""
    print("\n" + "="*60)
    print("CONFIGURATION SUMMARY")
    print("="*60)
    
    if not ENV_CONFIG_AVAILABLE:
        print("\nCannot display full configuration (env_config not available)")
        print(f"Error: {ENV_CONFIG_ERROR}")
        print("\nBasic environment variables:")
        for var in ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "GOOGLE_API_KEY"]:
            value = os.getenv(var)
            if any(secret in var for secret in ["PASSWORD", "KEY"]):
                display = "***" if value else "Not set"
            else:
                display = value if value else "Not set"
            print(f"  {var}: {display}")
        return
    
    config = env_config.get_all_env_vars()
    
    # Group by category
    categories = {
        "Database": ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE"],
        "API Keys": ["GOOGLE_API_KEY", "OPENAI_API_KEY", "HF_TOKEN"],
        "Performance": ["MAX_MEMORY_MB", "MAX_CONCURRENT_FILES", "BATCH_SIZE", "MAX_WORKERS"],
        "Features": ["ENABLE_ENHANCED_LOGGING", "ENABLE_METRICS", "DEBUG_MODE"],
        "Paths": ["CHECKPOINT_DIR", "OUTPUT_DIR"],
        "Logging": ["LOG_LEVEL", "LOG_FORMAT"]
    }
    
    for category, keys in categories.items():
        print(f"\n{category}:")
        for key in keys:
            if key in config:
                value = config[key]
                # Mask sensitive values
                if any(secret in key for secret in ["PASSWORD", "KEY", "TOKEN"]):
                    display_value = "***" if value else "Not set"
                else:
                    display_value = str(value) if value is not None else "Not set"
                print(f"  {key}: {display_value}")


def main():
    """Run all environment validation checks."""
    print("VTT Pipeline Environment Validation")
    print("="*60)
    
    all_passed = True
    
    # Check if dependencies are available
    if not ENV_CONFIG_AVAILABLE:
        print("\n⚠️  WARNING: Some Python dependencies are not installed")
        print(f"   Error: {ENV_CONFIG_ERROR}")
        print("\n   This is expected if you haven't set up the virtual environment yet.")
        print("   To install dependencies:")
        print("   $ python3 -m venv venv")
        print("   $ source venv/bin/activate")
        print("   $ pip install -r requirements-core.txt")
        print("\n   Continuing with basic checks...")
        print()
    
    # 1. Python version
    print("\n1. Python Version Check:")
    passed, message = check_python_version()
    print(f"   {message}")
    all_passed &= passed
    
    # 2. .env file
    print("\n2. Environment File Check:")
    passed, message = check_env_file()
    print(f"   {message}")
    if not passed:
        print("\n   To create .env file:")
        print("   $ cp .env.template .env")
        print("   $ nano .env  # Edit with your values")
    all_passed &= passed
    
    # 3. Required variables
    print("\n3. Required Environment Variables:")
    passed, missing = check_required_vars()
    if passed:
        print("   All required variables set ✓")
    else:
        print("   Missing required variables:")
        for var in missing:
            print(var)
    all_passed &= passed
    
    # 4. Directories
    print("\n4. Directory Check:")
    dir_results = check_directories()
    for desc, passed, message in dir_results:
        print(f"   {message}")
        all_passed &= passed
    
    # 5. Neo4j connection
    print("\n5. Database Connection:")
    passed, message = check_neo4j_connection()
    print(f"   {message}")
    # Don't fail overall if Neo4j isn't running
    
    # 6. Google API key
    print("\n6. API Key Validation:")
    passed, message = check_google_api_key()
    print(f"   {message}")
    # Don't fail overall if API key validation fails
    
    # 7. Configuration summary
    print_configuration_summary()
    
    # Final result
    print("\n" + "="*60)
    if all_passed:
        print("✅ ENVIRONMENT VALIDATION PASSED")
        print("\nYour environment is ready for VTT pipeline processing!")
        print("\nTo start processing:")
        print("  $ python -m src.cli.cli process <vtt_file>")
        return 0
    else:
        print("❌ ENVIRONMENT VALIDATION FAILED")
        print("\nPlease fix the issues above before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())