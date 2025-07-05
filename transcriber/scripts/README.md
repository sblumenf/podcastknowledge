# Transcriber Scripts

This directory contains utility scripts for the transcriber module.

## Directory Structure

### setup/
Environment and configuration setup:
- `setup_test_env.sh` - Setup test environment

### maintenance/
System maintenance and migration:
- `audit_imports.py` - Audit and analyze imports
- `migrate_existing_transcriptions.py` - Migrate existing transcription data

### utilities/
Utility scripts for transcription management:
- `check_transcribed.py` - Check which episodes have been transcribed
- `find_next_episodes.py` - Find next episodes to transcribe

### examples/
Example and demo scripts (located in ../examples/):
- `file_organizer_with_config.py` - Demo file organization with config
- `youtube_search_demo.py` - YouTube search API demo

## Usage

Run scripts from the transcriber directory:
```bash
python scripts/utilities/check_transcribed.py
python scripts/maintenance/audit_imports.py
```