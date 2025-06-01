# Podcast Transcription Pipeline

A command-line tool for transcribing podcast episodes from RSS feeds using Google's Gemini 2.5 Pro Experimental API. The tool generates WebVTT (VTT) format transcripts with speaker diarization and identification.

## Features

- 🎙️ Processes podcast RSS feeds automatically
- 🗣️ Speaker diarization with contextual identification
- 📝 WebVTT format output with embedded metadata
- 🔄 Automatic API key rotation for increased quota
- 💾 Progress tracking and resume capability
- ⚡ Robust error handling with exponential backoff

## Prerequisites

- Python 3.9 or higher
- Google Gemini API key(s) - [Get yours here](https://aistudio.google.com/app/apikey)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/podcastknowledge.git
cd podcastknowledge/transcriber
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the package in development mode:
```bash
pip install -e .
```

4. Set up your environment variables:
```bash
cp .env.example .env
# Edit .env and add your Gemini API key(s)
```

## Usage

### Basic Usage

Transcribe all episodes from a podcast RSS feed:
```bash
podcast-transcriber --feed-url https://example.com/podcast.rss
```

### Advanced Options

```bash
# Limit the number of episodes to process
podcast-transcriber --feed-url https://example.com/podcast.rss --max-episodes 5

# Specify custom output directory
podcast-transcriber --feed-url https://example.com/podcast.rss --output-dir /path/to/output

# Resume from previous run
podcast-transcriber --feed-url https://example.com/podcast.rss --resume

# Dry run (see what would be processed without actually transcribing)
podcast-transcriber --feed-url https://example.com/podcast.rss --dry-run
```

## Output Structure

Transcripts are organized by podcast name and episode date:
```
data/
├── Podcast_Name/
│   ├── 2024-01-15_Episode_Title.vtt
│   ├── 2024-01-22_Another_Episode.vtt
│   └── ...
├── .progress.json  # Progress tracking file
└── index.json      # Searchable episode index
```

## API Quota Management

The tool intelligently manages Gemini API quotas:
- Rotates between multiple API keys (if provided)
- Tracks usage to avoid hitting limits
- Processes episodes sequentially to distribute load
- Automatically resumes failed episodes

With 2 API keys, you can process approximately 24-48 episodes per day.

## VTT Output Format

Generated VTT files include:
- Accurate timestamps
- Speaker identification (names when possible, roles otherwise)
- Episode metadata in NOTE blocks
- Compatible with all standard VTT players

Example:
```vtt
WEBVTT

NOTE
Podcast: Tech Insights
Host: Lisa Park
Episode: AI in Healthcare
Date: 2024-01-15
Duration: 00:45:32

00:00:00.000 --> 00:00:05.000
<v Lisa Park>Welcome to Tech Insights. I'm your host, Lisa Park.

00:00:05.000 --> 00:00:12.000
<v Lisa Park>Today we're discussing AI in healthcare with Dr. Rahman.
```

## Troubleshooting

### Common Issues

1. **"API quota exceeded"**
   - Wait until midnight UTC for quota reset
   - Add additional API keys to .env file

2. **"Failed to parse RSS feed"**
   - Verify the RSS feed URL is correct
   - Check if the feed follows standard RSS/iTunes format

3. **"Connection timeout"**
   - The tool will automatically retry with exponential backoff
   - Check your internet connection

### Logs

Detailed logs are saved in the `logs/` directory for debugging.

## Testing

### Quick Start

```bash
# Set up test environment
./scripts/setup_test_env.sh

# Run all tests
make test

# Run with coverage
make coverage
```

### Running Specific Tests

```bash
# Run unit tests only
make test-unit

# Run integration tests
make test-integration

# Run a specific test file
pytest tests/test_config.py

# Run tests matching a pattern
pytest -k "config"
```

For detailed testing documentation, see [docs/testing.md](docs/testing.md).

## Development

### Code Style

The project uses:
- Black for code formatting
- isort for import sorting
- flake8 for linting

Format code before committing:
```bash
make format
make lint
```

### Pre-commit Hooks

Install pre-commit hooks:
```bash
pre-commit install
```

## Contributing

See the main project's [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

### Development Workflow

1. Create a feature branch
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass: `make test`
5. Update documentation if needed
6. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.