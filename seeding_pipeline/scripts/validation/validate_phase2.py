#!/usr/bin/env python3
"""Phase 2 Validation Script - VTT Knowledge Seeding Refactor

This script validates that Phase 2 has been properly completed:
1. Audio/RSS components removed
2. VTT processing components created
3. Configuration simplified
"""

import os
import sys
from pathlib import Path
import subprocess
import json
from typing import List, Dict, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class Phase2Validator:
    def __init__(self):
        self.project_root = project_root
        self.errors = []
        self.warnings = []
        self.successes = []
        
    def validate(self) -> bool:
        """Run all Phase 2 validations."""
        print("=" * 80)
        print("Phase 2 Validation - VTT Knowledge Seeding Refactor")
        print("=" * 80)
        
        # Phase 2.1: Remove Audio/RSS Components
        print("\n## Phase 2.1: Remove Audio/RSS Components")
        self._validate_audio_removal()
        
        # Phase 2.2: Create VTT Processing Components
        print("\n## Phase 2.2: Create VTT Processing Components")
        self._validate_vtt_components()
        
        # Phase 2.3: Simplify Configuration
        print("\n## Phase 2.3: Simplify Configuration")
        self._validate_configuration()
        
        # Summary
        self._print_summary()
        
        return len(self.errors) == 0
    
    def _validate_audio_removal(self):
        """Validate that all audio/RSS components have been removed."""
        # Check that audio provider directory is gone
        audio_dir = self.project_root / "src" / "providers" / "audio"
        if audio_dir.exists():
            self.errors.append(f"Audio provider directory still exists: {audio_dir}")
        else:
            self.successes.append("✓ Audio provider directory removed")
        
        # Check that feed processing is gone
        feed_processing = self.project_root / "src" / "utils" / "feed_processing.py"
        if feed_processing.exists():
            self.errors.append(f"Feed processing still exists: {feed_processing}")
        else:
            self.successes.append("✓ Feed processing removed")
        
        # Check for audio imports
        print("\nChecking for remaining audio imports...")
        audio_import_patterns = [
            "from src.providers.audio",
            "import AudioProvider",
            "from src.utils.feed_processing",
            "import feed_processing",
            "AudioProvider"
        ]
        
        files_with_audio_imports = []
        for py_file in self.project_root.glob("**/*.py"):
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue
            if py_file.name == "validate_phase2.py":
                continue
                
            try:
                content = py_file.read_text()
                for pattern in audio_import_patterns:
                    if pattern in content:
                        files_with_audio_imports.append((py_file, pattern))
                        break
            except:
                pass
        
        if files_with_audio_imports:
            self.errors.append(f"Found {len(files_with_audio_imports)} files with audio imports:")
            for file, pattern in files_with_audio_imports[:5]:  # Show first 5
                self.errors.append(f"  - {file.relative_to(self.project_root)}: '{pattern}'")
            if len(files_with_audio_imports) > 5:
                self.errors.append(f"  ... and {len(files_with_audio_imports) - 5} more")
        else:
            self.successes.append("✓ No audio imports found in source code")
        
        # Check requirements.txt
        req_file = self.project_root / "requirements.txt"
        if req_file.exists():
            content = req_file.read_text()
            audio_deps = ["torch", "whisper", "pyannote", "feedparser"]
            found_deps = [dep for dep in audio_deps if dep in content]
            
            if found_deps:
                self.errors.append(f"Audio dependencies still in requirements.txt: {found_deps}")
            else:
                self.successes.append("✓ Audio dependencies removed from requirements.txt")
        
        # Check for orphaned test files
        test_files = [
            "tests/unit/test_audio_providers.py",
            "tests/integration/test_audio_integration.py",
            "tests/providers/test_audio_providers.py"
        ]
        
        orphaned_tests = []
        for test_file in test_files:
            full_path = self.project_root / test_file
            if full_path.exists():
                orphaned_tests.append(test_file)
        
        if orphaned_tests:
            self.errors.append(f"Found {len(orphaned_tests)} orphaned audio test files:")
            for test in orphaned_tests:
                self.errors.append(f"  - {test}")
        else:
            self.successes.append("✓ No orphaned audio test files")
    
    def _validate_vtt_components(self):
        """Validate that VTT processing components have been created."""
        # Check VTT parser
        vtt_parser = self.project_root / "src" / "processing" / "vtt_parser.py"
        if not vtt_parser.exists():
            self.errors.append("VTT parser not found at src/processing/vtt_parser.py")
        else:
            self.successes.append("✓ VTT parser created")
            
            # Validate VTT parser implementation
            content = vtt_parser.read_text()
            required_elements = [
                "class VTTParser",
                "parse_file",
                "TIMESTAMP_PATTERN",
                "SPEAKER_PATTERN",
                "TranscriptSegment"
            ]
            
            missing = [elem for elem in required_elements if elem not in content]
            if missing:
                self.warnings.append(f"VTT parser missing elements: {missing}")
            else:
                self.successes.append("✓ VTT parser implementation complete")
        
        # Check transcript ingestion
        ingestion = self.project_root / "src" / "seeding" / "transcript_ingestion.py"
        if not ingestion.exists():
            self.errors.append("Transcript ingestion not found at src/seeding/transcript_ingestion.py")
        else:
            self.successes.append("✓ Transcript ingestion created")
            
            # Validate ingestion implementation
            content = ingestion.read_text()
            required_elements = [
                "class TranscriptIngestion",
                "process_directory",
                "process_file",
                "_compute_file_hash",
                "VTTParser"
            ]
            
            missing = [elem for elem in required_elements if elem not in content]
            if missing:
                self.warnings.append(f"Transcript ingestion missing elements: {missing}")
            else:
                self.successes.append("✓ Transcript ingestion implementation complete")
        
        # Check pipeline executor updates
        executor = self.project_root / "src" / "seeding" / "components" / "pipeline_executor.py"
        if executor.exists():
            content = executor.read_text()
            if "process_vtt_segments" in content:
                self.successes.append("✓ Pipeline executor has process_vtt_segments method")
            else:
                self.errors.append("Pipeline executor missing process_vtt_segments method")
        else:
            # Try alternative location
            executor = self.project_root / "src" / "seeding" / "pipeline_executor.py"
            if executor.exists():
                content = executor.read_text()
                if "process_vtt_segments" in content:
                    self.successes.append("✓ Pipeline executor has process_vtt_segments method")
                else:
                    self.errors.append("Pipeline executor missing process_vtt_segments method")
            else:
                self.errors.append("Pipeline executor not found")
    
    def _validate_configuration(self):
        """Validate that configuration has been simplified."""
        # Check VTT config
        vtt_config = self.project_root / "config" / "vtt_config.example.yml"
        if not vtt_config.exists():
            self.errors.append("VTT config example not found at config/vtt_config.example.yml")
        else:
            self.successes.append("✓ VTT config example created")
            
            # Validate config content
            content = vtt_config.read_text()
            if "audio" in content.lower() or "whisper" in content.lower():
                self.warnings.append("VTT config still contains audio references")
            if "vtt" in content.lower() or "transcript" in content.lower():
                self.successes.append("✓ VTT config contains VTT/transcript settings")
            else:
                self.warnings.append("VTT config missing VTT/transcript settings")
        
        # Check env example
        env_example = self.project_root / ".env.vtt.example"
        if not env_example.exists():
            self.errors.append("VTT env example not found at .env.vtt.example")
        else:
            self.successes.append("✓ VTT env example created")
            
            # Validate env content
            content = env_example.read_text()
            audio_vars = ["WHISPER", "AUDIO", "PYANNOTE"]
            found_audio = [var for var in audio_vars if var in content.upper()]
            
            if found_audio:
                self.warnings.append(f"VTT env still contains audio variables: {found_audio}")
            else:
                self.successes.append("✓ VTT env has no audio variables")
    
    def _print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        
        if self.successes:
            print(f"\n✓ Successes ({len(self.successes)}):")
            for success in self.successes:
                print(f"  {success}")
        
        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  {error}")
        
        print("\n" + "=" * 80)
        if not self.errors:
            print("✅ PHASE 2 VALIDATION PASSED!")
        else:
            print("❌ PHASE 2 VALIDATION FAILED!")
            print(f"   Found {len(self.errors)} errors that must be fixed")
        print("=" * 80)


if __name__ == "__main__":
    validator = Phase2Validator()
    success = validator.validate()
    sys.exit(0 if success else 1)