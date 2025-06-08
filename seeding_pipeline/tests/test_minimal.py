#!/usr/bin/env python3
"""
Minimal test suite for VTT Pipeline.

Uses only built-in unittest module to avoid dependencies.
Focuses on essential functionality only.
"""

import unittest
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestVTTParsing(unittest.TestCase):
    """Test VTT file parsing functionality."""
    
    def setUp(self):
        """Create temporary test directory."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_vtt_file_validation(self):
        """Test VTT file format validation."""
        # Create a valid VTT file
        valid_vtt = os.path.join(self.test_dir, "valid.vtt")
        with open(valid_vtt, 'w') as f:
            f.write("WEBVTT\n\n")
            f.write("00:00:00.000 --> 00:00:05.000\n")
            f.write("Hello, this is a test.\n")
        
        # Import minimal functionality
        try:
            from src.vtt.vtt_parser import VTTParser
            from pathlib import Path
            parser = VTTParser()
            
            # Test parsing
            segments = parser.parse_file(Path(valid_vtt))
            self.assertIsInstance(segments, list)
            self.assertGreater(len(segments), 0)
            
            # Check first segment
            segment = segments[0]
            self.assertTrue(hasattr(segment, 'text'))
            self.assertTrue(hasattr(segment, 'start_time'))
            self.assertTrue(hasattr(segment, 'end_time'))
            self.assertEqual(segment.text, "Hello, this is a test.")
            
        except ImportError as e:
            self.skipTest(f"VTT parser not available: {e}")
    
    def test_invalid_vtt_file(self):
        """Test handling of invalid VTT files."""
        # Create invalid file (no WEBVTT header)
        invalid_vtt = os.path.join(self.test_dir, "invalid.vtt")
        with open(invalid_vtt, 'w') as f:
            f.write("00:00:00.000 --> 00:00:05.000\n")
            f.write("Missing header\n")
        
        try:
            from src.vtt.vtt_parser import VTTParser
            parser = VTTParser()
            
            # Should raise or return empty
            with self.assertRaises(Exception):
                parser.parse(invalid_vtt)
                
        except ImportError as e:
            self.skipTest(f"VTT parser not available: {e}")


class TestBasicExtraction(unittest.TestCase):
    """Test basic knowledge extraction functionality."""
    
    def test_environment_config(self):
        """Test environment configuration loading."""
        try:
            from src.core.env_config import EnvironmentConfig
            config = EnvironmentConfig()
            
            # Test getting optional variables
            neo4j_uri = config.get_optional("NEO4J_URI", "bolt://localhost:7687")
            self.assertEqual(neo4j_uri, "bolt://localhost:7687")
            
            # Test boolean parsing
            debug = config.get_bool("DEBUG_MODE", False)
            self.assertIsInstance(debug, bool)
            
            # Test integer parsing
            workers = config.get_int("MAX_WORKERS", 4)
            self.assertIsInstance(workers, int)
            self.assertGreater(workers, 0)
            
        except ImportError as e:
            self.skipTest(f"Environment config not available: {e}")
    
    def test_resource_detection(self):
        """Test resource detection functionality."""
        try:
            from src.utils.resource_detection import (
                get_available_memory_mb,
                get_cpu_count,
                detect_system_resources
            )
            
            # Test memory detection
            memory = get_available_memory_mb()
            self.assertIsInstance(memory, int)
            self.assertGreater(memory, 0)
            
            # Test CPU detection
            cpus = get_cpu_count()
            self.assertIsInstance(cpus, int)
            self.assertGreater(cpus, 0)
            
            # Test resource detection
            resources = detect_system_resources()
            self.assertIsInstance(resources, dict)
            self.assertIn('memory_mb', resources)
            self.assertIn('cpu_count', resources)
            self.assertIn('is_low_resource', resources)
            self.assertIn('recommendations', resources)
            
        except ImportError as e:
            self.skipTest(f"Resource detection not available: {e}")


class TestCLICommands(unittest.TestCase):
    """Test CLI command functionality."""
    
    def test_cli_help(self):
        """Test CLI help command."""
        import subprocess
        
        # Test main help
        result = subprocess.run(
            [sys.executable, "-m", "src.cli.cli", "--help"],
            capture_output=True,
            text=True
        )
        
        # Help should succeed
        self.assertEqual(result.returncode, 0, 
                        f"CLI help failed: {result.stderr}")
        
        # Check for expected commands
        self.assertIn("process-vtt", result.stdout)
        self.assertIn("checkpoint-status", result.stdout)
        self.assertIn("health", result.stdout)
        self.assertIn("minimal", result.stdout)
    
    def test_minimal_cli_help(self):
        """Test minimal CLI help."""
        import subprocess
        
        # Test minimal CLI help
        result = subprocess.run(
            [sys.executable, "src/cli/minimal_cli.py", "--help"],
            capture_output=True,
            text=True
        )
        
        # Should work even without dependencies
        self.assertEqual(result.returncode, 0,
                        f"Minimal CLI help failed: {result.stderr}")
        self.assertIn("vtt_file", result.stdout)
        self.assertIn("--dry-run", result.stdout)
    
    def test_validation_script(self):
        """Test environment validation script."""
        import subprocess
        
        # Run validation script
        result = subprocess.run(
            [sys.executable, "scripts/validate_environment.py"],
            capture_output=True,
            text=True
        )
        
        # Should run without crashing
        self.assertIn("VTT Pipeline Environment Validation", result.stdout)
        self.assertIn("Python Version Check", result.stdout)
        self.assertIn("Environment File Check", result.stdout)
        self.assertIn("Directory Check", result.stdout)


class TestFileOperations(unittest.TestCase):
    """Test basic file operations."""
    
    def setUp(self):
        """Create test directory."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_directory_creation(self):
        """Test that required directories can be created."""
        dirs_to_test = ['checkpoints', 'output', 'logs']
        
        for dir_name in dirs_to_test:
            dir_path = os.path.join(self.test_dir, dir_name)
            os.makedirs(dir_path, exist_ok=True)
            self.assertTrue(os.path.exists(dir_path))
            self.assertTrue(os.path.isdir(dir_path))
    
    def test_env_template_exists(self):
        """Test that .env.template exists."""
        env_template = Path(".env.template")
        self.assertTrue(env_template.exists(), 
                       ".env.template file not found")
        
        # Check it contains required variables
        content = env_template.read_text()
        required_vars = [
            "NEO4J_URI",
            "NEO4J_USERNAME", 
            "NEO4J_PASSWORD",
            "GOOGLE_API_KEY"
        ]
        
        for var in required_vars:
            self.assertIn(var, content, 
                         f"Required variable {var} not in .env.template")


def run_minimal_tests():
    """Run the minimal test suite and return results."""
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add tests in order of importance
    suite.addTest(unittest.makeSuite(TestFileOperations))
    suite.addTest(unittest.makeSuite(TestCLICommands))
    suite.addTest(unittest.makeSuite(TestVTTParsing))
    suite.addTest(unittest.makeSuite(TestBasicExtraction))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    # Run all tests
    result = run_minimal_tests()
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)