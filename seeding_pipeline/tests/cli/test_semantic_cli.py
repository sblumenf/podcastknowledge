"""
Test script for semantic processing CLI functionality.

This script tests the new --semantic and --compare-methods flags.
"""

import pytest
import subprocess
import sys
from pathlib import Path
import tempfile
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def create_test_vtt_file():
    """Create a test VTT file."""
    content = """WEBVTT

NOTE
Episode: Test Episode
Guest: Test Guest

00:00:00.000 --> 00:00:05.000
<v Host>Welcome to our test podcast.

00:00:05.000 --> 00:00:10.000
<v Host>Today we're discussing AI.

00:00:10.000 --> 00:00:15.000
<v Guest>Thank you for having me.

00:00:15.000 --> 00:00:20.000
<v Guest>AI is transforming everything.

00:00:20.000 --> 00:00:25.000
<v Host>Can you give an example?

00:00:25.000 --> 00:00:30.000
<v Guest>Sure, let's talk about healthcare.
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
        f.write(content)
        return Path(f.name)


def test_semantic_flag_help():
    """Test that --semantic flag appears in help."""
    result = subprocess.run(
        [sys.executable, 'src/cli/cli.py', 'process-vtt', '--help'],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert '--semantic' in result.stdout
    assert 'conversation-aware' in result.stdout


def test_compare_methods_flag_help():
    """Test that --compare-methods flag appears in help."""
    result = subprocess.run(
        [sys.executable, 'src/cli/cli.py', 'process-vtt', '--help'],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert '--compare-methods' in result.stdout
    assert 'Compare semantic vs segment' in result.stdout


def test_semantic_processing_dry_run():
    """Test semantic processing in dry-run mode."""
    test_file = create_test_vtt_file()
    
    try:
        result = subprocess.run(
            [
                sys.executable, 'src/cli/cli.py', 
                'process-vtt',
                '--folder', str(test_file.parent),
                '--pattern', test_file.name,
                '--semantic',
                '--dry-run'
            ],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert 'DRY RUN' in result.stdout
        assert test_file.name in result.stdout
        
    finally:
        test_file.unlink()


def test_cli_import():
    """Test that CLI imports work correctly."""
    try:
        from src.cli.cli import main, process_vtt
        from src.seeding.semantic_orchestrator import SemanticVTTKnowledgeExtractor
        
        # Verify imports succeeded
        assert main is not None
        assert process_vtt is not None
        assert SemanticVTTKnowledgeExtractor is not None
        
    except ImportError as e:
        pytest.fail(f"Failed to import CLI modules: {e}")


def test_semantic_examples_in_help():
    """Test that semantic examples appear in main help."""
    result = subprocess.run(
        [sys.executable, 'src/cli/cli.py', '--help'],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert 'process-vtt --folder /path/to/vtt --semantic' in result.stdout
    assert 'compare-methods' in result.stdout


if __name__ == "__main__":
    # Run tests
    print("Testing semantic CLI functionality...")
    
    print("1. Testing --semantic flag help...")
    test_semantic_flag_help()
    print("   ✓ Passed")
    
    print("2. Testing --compare-methods flag help...")
    test_compare_methods_flag_help()
    print("   ✓ Passed")
    
    print("3. Testing semantic processing dry run...")
    test_semantic_processing_dry_run()
    print("   ✓ Passed")
    
    print("4. Testing CLI imports...")
    test_cli_import()
    print("   ✓ Passed")
    
    print("5. Testing semantic examples in help...")
    test_semantic_examples_in_help()
    print("   ✓ Passed")
    
    print("\nAll tests passed! ✓")