# Podcast Transcription Pipeline

[![Tests](https://github.com/yourusername/podcast-transcriber/actions/workflows/tests.yml/badge.svg)](https://github.com/yourusername/podcast-transcriber/actions/workflows/tests.yml)
[![Test Coverage](https://github.com/yourusername/podcast-transcriber/actions/workflows/test-coverage.yml/badge.svg)](https://github.com/yourusername/podcast-transcriber/actions/workflows/test-coverage.yml)
[![codecov](https://codecov.io/gh/yourusername/podcast-transcriber/branch/main/graph/badge.svg?token=YOUR_TOKEN)](https://codecov.io/gh/yourusername/podcast-transcriber)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A robust command-line tool for transcribing podcast episodes from RSS feeds using Google's Gemini 2.5 Pro API. The tool generates WebVTT (VTT) format transcripts with speaker diarization and contextual speaker identification.

## Features

- 🎙️ **Automatic RSS Feed Processing**: Parse and transcribe entire podcast catalogs
- 🗣️ **Speaker Diarization**: Identify different speakers with contextual name recognition
- 📝 **WebVTT Output**: Industry-standard subtitle format with embedded metadata
- 🔄 **API Key Rotation**: Distribute load across multiple Gemini API keys
- 💾 **Checkpoint Recovery**: Resume interrupted transcriptions without data loss
- ⚡ **Robust Error Handling**: Automatic retries with exponential backoff
- 📊 **Progress Tracking**: Monitor transcription status and statistics
- 🔍 **Searchable Index**: Query transcripts by speaker, date, or content
- 🛡️ **Security**: Automatic redaction of sensitive data in logs

## Prerequisites

- Python 3.8 or higher
- Google Gemini API key(s) - [Get yours here](https://aistudio.google.com/app/apikey)
- Internet connection for API access
- Sufficient disk space for transcripts (~50KB per hour of audio)

## Installation

### Quick Install

```bash
# Clone the repository
git clone https://github.com/yourusername/podcast-transcriber.git
cd podcast-transcriber

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
export GEMINI_API_KEY_1="your-first-api-key"
export GEMINI_API_KEY_2="your-second-api-key"  # Optional for rotation
```

### Development Install

For development work, testing, or contributing to the project:

```bash
# Clone the repository
git clone https://github.com/yourusername/podcast-transcriber.git
cd podcast-transcriber

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install ALL dependencies (production + development)
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Verify installation (especially important for performance tests)
python -c "import psutil; print('psutil installed successfully')"

# Install pre-commit hooks (if available)
pre-commit install 2>/dev/null || echo "pre-commit not configured"
```

**Important**: Always use `requirements-dev.txt` for development to ensure all testing and development tools are available. This includes:
- Testing frameworks (pytest, pytest-cov, pytest-mock)
- Performance testing tools (psutil)
- Code quality tools (black, flake8, mypy)
- Documentation tools (sphinx)

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GEMINI_API_KEY_1` | Primary Gemini API key | - | Yes |
| `GEMINI_API_KEY_2` | Secondary API key for rotation | - | No |
| `GEMINI_API_KEY_3` | Additional API key | - | No |
| `LOG_LEVEL` | Logging verbosity (DEBUG/INFO/WARNING/ERROR) | INFO | No |
| `LOG_MAX_SIZE_MB` | Max log file size before rotation | 10 | No |
| `OUTPUT_DIR` | Default transcript output directory | data/transcripts | No |

### Configuration File

Create `config/default.yaml` for advanced settings:

```yaml
# Output configuration
output:
  default_dir: "data/transcripts"
  file_pattern: "{date}_{title}.vtt"
  create_podcast_dirs: true
  max_filename_length: 200

# Processing settings
processing:
  checkpoint_enabled: true
  max_retries: 2
  retry_delay: 5
  max_file_size_mb: 100
  preferred_audio_formats:
    - "audio/mpeg"
    - "audio/mp4"

# API configuration
api:
  timeout: 300
  requests_per_minute: 15
  requests_per_day: 25
  validation:
    min_confidence: 0.8
    min_duration: 10
    max_duration: 7200

# Logging configuration
logging:
  level: "INFO"
  file_rotation: true
  max_file_size_mb: 10
  backup_count: 5
  
# Security settings
security:
  api_key_var_pattern: "GEMINI_API_KEY_{}"
  max_api_keys: 10
```

## Usage

### Basic Commands

```bash
# Transcribe a podcast feed
podcast-transcriber transcribe --feed-url https://example.com/podcast/feed.xml

# Resume interrupted transcription
podcast-transcriber transcribe --feed-url https://example.com/feed.xml --resume

# Limit number of episodes
podcast-transcriber transcribe --feed-url https://example.com/feed.xml --max-episodes 5

# Specify output directory
podcast-transcriber transcribe --feed-url https://example.com/feed.xml --output-dir /custom/path

# Dry run (preview without processing)
podcast-transcriber transcribe --feed-url https://example.com/feed.xml --dry-run
```

### Advanced Commands

```bash
# Check system health and API key validity
podcast-transcriber health

# View transcription statistics
podcast-transcriber stats

# Search transcripts
podcast-transcriber search --query "machine learning" --speaker "Guest"

# Export episode index
podcast-transcriber export --format csv --output episodes.csv

# Validate existing transcripts
podcast-transcriber validate --dir data/transcripts
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--feed-url` | RSS feed URL to process | Required |
| `--output-dir` | Directory for transcript files | data/transcripts |
| `--max-episodes` | Maximum episodes to process | No limit |
| `--resume` | Resume from last checkpoint | False |
| `--dry-run` | Preview without processing | False |
| `--config` | Path to configuration file | config/default.yaml |
| `--log-level` | Override log level | INFO |

## Output Format

### Directory Structure

```
data/transcripts/
├── Tech_Talk_Podcast/
│   ├── 2025-06-01_AI_Innovation_Episode.vtt
│   ├── 2025-06-08_Cloud_Computing_Deep_Dive.vtt
│   └── metadata.json
├── Another_Podcast/
│   └── ...
├── manifest.json           # Global episode manifest
└── index.json             # Searchable index
```

### VTT File Format

```vtt
WEBVTT

NOTE
Podcast: Tech Talk Podcast
Episode: AI Innovation Episode
Date: 2025-06-01
Duration: 45:32
Host: John Doe
Guests: Dr. Jane Smith, Prof. Bob Wilson
Transcribed: 2025-06-02T10:30:00

NOTE JSON Metadata
{
  "podcast": "Tech Talk Podcast",
  "episode": "AI Innovation Episode",
  "speakers": {
    "SPEAKER_1": "John Doe (Host)",
    "SPEAKER_2": "Dr. Jane Smith (Guest)"
  }
}

00:00:01.000 --> 00:00:05.000
<v John Doe (Host)>Welcome to Tech Talk Podcast.

00:00:05.000 --> 00:00:10.000
<v John Doe (Host)>Today we're discussing AI innovation
with Dr. Jane Smith.

00:00:10.000 --> 00:00:15.000
<v Dr. Jane Smith (Guest)>Thanks for having me, John.
It's great to be here.
```

## API Quota Management

### Free Tier Limits
- 2 requests per minute (RPM)
- 25 requests per day (RPD) per API key
- Audio files up to 100MB

### Optimization Strategies
1. **Key Rotation**: Automatically alternates between available API keys
2. **Daily Tracking**: Monitors usage to prevent quota exhaustion
3. **Smart Scheduling**: Distributes requests throughout the day
4. **Checkpoint Recovery**: Resumes without re-processing completed episodes

### Processing Capacity
| API Keys | Episodes/Day | Recommended Max Duration |
|----------|--------------|-------------------------|
| 1 | 12 | 60 minutes |
| 2 | 24 | 60 minutes |
| 3 | 36 | 45 minutes |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  RSS Feed   │────▶│ Feed Parser  │────▶│ Episode Queue   │
└─────────────┘     └──────────────┘     └─────────────────┘
                                                   │
                                                   ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Key Rotation│────▶│ Rate Limiter │────▶│ Gemini Client   │
│  Manager    │     │              │     │                 │
└─────────────┘     └──────────────┘     └─────────────────┘
                                                   │
                                                   ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Checkpoint  │────▶│ Transcription│────▶│ Audio Processor │
│  Manager    │     │  Processor   │     │                 │
└─────────────┘     └──────────────┘     └─────────────────┘
                                                   │
                                                   ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ VTT Output  │◀────│   Speaker    │◀────│ Raw Transcript  │
│   Files     │     │ Identifier   │     │                 │
└─────────────┘     └──────────────┘     └─────────────────┘
```

## Troubleshooting

### Common Issues

#### API Key Errors
```bash
# Verify API keys are set
echo $GEMINI_API_KEY_1

# Test API key validity
podcast-transcriber health

# Check quota status
podcast-transcriber stats --api-usage
```

#### Network Timeouts
- Increase timeout in configuration: `api.timeout: 600`
- Check audio file accessibility
- Verify internet connection stability

#### Quota Exceeded
- Wait until midnight UTC for reset
- Add additional API keys
- Reduce max episodes per day
- Process shorter episodes

#### Memory Issues
- Process fewer episodes concurrently
- Reduce `--max-episodes` value
- Monitor with: `podcast-transcriber stats --resources`

### Debug Mode

Enable verbose logging:
```bash
# Set debug level
export LOG_LEVEL=DEBUG

# Or use CLI flag
podcast-transcriber transcribe --feed-url URL --log-level DEBUG
```

Log locations:
- `logs/podcast_transcriber_YYYYMMDD.log` - All logs
- `logs/errors_YYYYMMDD.log` - Errors only

### Recovery Options

```bash
# Resume from checkpoint
podcast-transcriber transcribe --resume

# Reprocess failed episodes
podcast-transcriber retry --failed-only

# Clean corrupted checkpoints
podcast-transcriber clean --checkpoints
```

## Performance

| Metric | Typical Value | Notes |
|--------|--------------|-------|
| Processing Speed | 3-5 min/hour of audio | Depends on audio quality |
| Memory Usage | ~500MB per transcription | Scales with audio length |
| Disk Usage | ~50KB/hour of audio | VTT text format |
| API Latency | 10-30 seconds | Per API call |
| Success Rate | >95% | With retry logic |

## Development

### Running Tests

```bash
# All tests with coverage
pytest --cov=src --cov-report=html

# Unit tests only
pytest tests/ -m unit

# Integration tests
pytest tests/ -m integration

# Specific module
pytest tests/test_feed_parser.py -v
```

### Code Quality

```bash
# Type checking
mypy src/

# Linting
flake8 src/ tests/

# Format code
black src/ tests/
isort src/ tests/
```

### Adding Features

1. Create feature branch: `git checkout -b feature/new-feature`
2. Implement with tests
3. Update documentation
4. Run full test suite
5. Submit pull request

## Security Considerations

- API keys are never logged (automatic redaction)
- Sensitive URLs are masked in logs
- No personal data is stored without consent
- Secure handling of audio file downloads
- Configurable data retention policies

## Troubleshooting

### Import Errors

If you encounter import errors when running tests or the application:

1. **Missing psutil error in tests**:
   ```
   ModuleNotFoundError: No module named 'psutil'
   ```
   **Solution**: Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **General import errors**:
   - Verify you're in the correct virtual environment
   - Check all dependencies are installed:
     ```bash
     pip install -r requirements.txt
     pip install -r requirements-dev.txt  # For development/testing
     ```

3. **Import audit**:
   Run the import audit script to identify missing dependencies:
   ```bash
   python scripts/audit_imports.py
   ```

### Common Issues

- **Tests failing with import errors**: Make sure you've installed `requirements-dev.txt`
- **CI/CD import failures**: Check that workflows use `requirements-dev.txt` for test jobs
- **Package name vs import name**: Some packages have different names:
  - Install: `pip install PyYAML` → Import: `import yaml`
  - Install: `pip install google-generativeai` → Import: `import google.generativeai`

For more help, see our [Dependency Management Guide](docs/dependency-management.md).

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Areas for Contribution
- Additional language support
- Alternative transcription services
- Enhanced speaker identification
- Performance optimizations
- Documentation improvements

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Google Gemini team for the transcription API
- WebVTT specification contributors
- The open-source podcast community
- All our contributors

## Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/yourusername/podcast-transcriber/issues)
- 💬 [Discussions](https://github.com/yourusername/podcast-transcriber/discussions)
- 📧 Email: support@example.com

---

**Note**: This tool is designed for transcribing publicly available podcasts. Please respect copyright laws and obtain necessary permissions before transcribing copyrighted content.