#!/usr/bin/env python3
"""Example demonstrating FileOrganizer usage with Config injection."""

from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.file_organizer import FileOrganizer


def main():
    """Demonstrate FileOrganizer with different configuration options."""
    
    print("FileOrganizer Config Injection Example")
    print("=" * 40)
    
    # Example 1: Without config (backward compatible)
    print("\n1. Without config (uses defaults):")
    organizer1 = FileOrganizer(base_dir="/tmp/transcripts_default")
    print(f"   Base directory: {organizer1.base_dir}")
    print(f"   Max filename length: 200 (default)")
    
    # Example 2: With config
    print("\n2. With config injection:")
    config = Config(config_file="config/example.yaml")
    organizer2 = FileOrganizer(config=config)
    print(f"   Base directory: {organizer2.base_dir}")
    print(f"   Max filename length: {config.output.max_filename_length}")
    
    # Example 3: Override base directory
    print("\n3. Override base directory with config:")
    organizer3 = FileOrganizer(base_dir="/tmp/custom_transcripts", config=config)
    print(f"   Base directory: {organizer3.base_dir}")
    print(f"   Still uses config for other settings")
    
    # Example 4: Custom naming pattern
    print("\n4. Custom naming pattern from config:")
    # Modify config for demonstration
    config.output.naming_pattern = "{date}/podcasts/{podcast_name}_{episode_title}.vtt"
    organizer4 = FileOrganizer(base_dir="/tmp/pattern_test", config=config)
    
    # Generate a filename to show the pattern
    rel_path, full_path = organizer4.generate_filename(
        "Tech Talks",
        "AI Revolution",
        "2024-01-15"
    )
    print(f"   Pattern: {config.output.naming_pattern}")
    print(f"   Generated path: {rel_path}")
    
    # Example 5: Disable sanitization
    print("\n5. Disable filename sanitization:")
    config.output.sanitize_filenames = False
    organizer5 = FileOrganizer(base_dir="/tmp/no_sanitize", config=config)
    
    # Test sanitization
    original = "Episode: Special Characters!?"
    sanitized = organizer5.sanitize_filename(original)
    print(f"   Original: '{original}'")
    print(f"   Result: '{sanitized}'")
    print(f"   Sanitization disabled: {original == sanitized}")
    
    # Example 6: Filename length limits
    print("\n6. Custom filename length limit:")
    config.output.sanitize_filenames = True
    config.output.max_filename_length = 50
    organizer6 = FileOrganizer(base_dir="/tmp/length_test", config=config)
    
    long_title = "This is a very long episode title that should be truncated"
    truncated = organizer6.sanitize_filename(long_title)
    print(f"   Max length: {config.output.max_filename_length}")
    print(f"   Original length: {len(long_title)}")
    print(f"   Truncated length: {len(truncated)}")
    print(f"   Result: '{truncated}'")
    
    print("\n" + "=" * 40)
    print("Config injection allows flexible, centralized configuration")
    print("while maintaining backward compatibility!")


if __name__ == "__main__":
    main()