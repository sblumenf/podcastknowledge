# Podcast Transcription Pipeline

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A streamlined command-line tool for transcribing podcast episodes from RSS feeds using Deepgram's speech-to-text API. The tool generates WebVTT (VTT) format transcripts with automatic speaker identification.

## Features

- 🎙️ **Automatic RSS Feed Processing**: Parse and transcribe entire podcast catalogs
- 🗣️ **Smart Speaker Identification**: Automatically identifies Host vs Guests based on speaking patterns
- 📝 **WebVTT Output**: Industry-standard subtitle format with speaker labels
- 🚀 **Simple Architecture**: No complex state management or checkpointing
- 🧪 **Mock Testing Support**: Develop and test without API calls
- 📊 **Clear Progress Reporting**: Track transcription status and results

## Prerequisites

- Python 3.8 or higher
- Deepgram API key - [Get yours here](https://console.deepgram.com/)
- Internet connection for API access

## Installation

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
export DEEPGRAM_API_KEY="your-deepgram-api-key"
export TRANSCRIPT_OUTPUT_DIR="output/transcripts"
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Deepgram API Configuration
DEEPGRAM_API_KEY=your-deepgram-api-key-here
DEEPGRAM_MODEL=nova-2  # Options: nova-2, nova-1, enhanced, base

# Output Configuration
TRANSCRIPT_OUTPUT_DIR=output/transcripts
SPEAKER_MAPPING_ENABLED=true

# Logging
LOG_LEVEL=INFO
```

### Available Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `DEEPGRAM_API_KEY` | Your Deepgram API key | Required |
| `DEEPGRAM_MODEL` | Deepgram model to use | nova-2 |
| `TRANSCRIPT_OUTPUT_DIR` | Where to save VTT files | output/transcripts |
| `SPEAKER_MAPPING_ENABLED` | Enable automatic speaker naming | true |
| `LOG_LEVEL` | Logging verbosity | INFO |

## Usage

### Basic Commands

```bash
# Transcribe all episodes from a podcast
python -m src.cli transcribe --feed-url https://example.com/podcast.rss

# Transcribe only the first 5 episodes
python -m src.cli transcribe --feed-url https://example.com/podcast.rss --max-episodes 5

# Use mock responses for testing (no API calls)
python -m src.cli transcribe --feed-url https://example.com/podcast.rss --mock

# Validate an RSS feed
python -m src.cli validate-feed --feed-url https://example.com/podcast.rss
```

### Output Structure

Transcripts are organized by podcast name and episode:

```
output/transcripts/
├── The_Tech_Podcast/
│   ├── 2024-06-09_Episode_1_AI_and_Society.vtt
│   ├── 2024-06-08_Episode_2_Future_of_Work.vtt
│   └── ...
└── Another_Podcast/
    └── ...
```

### VTT Format

Generated VTT files include speaker identification:

```vtt
WEBVTT
NOTE Transcription powered by Deepgram

1
00:00:00.000 --> 00:00:04.900
<v Host>Welcome everyone to today's episode.</v>

2
00:00:05.500 --> 00:00:08.500
<v Guest>Thank you so much for having me on the show.</v>
```

## Speaker Identification

The system automatically identifies speakers based on:
- **Speaking order**: First speaker is typically the host
- **Speaking patterns**: Hosts usually introduce the show and guests
- **Labels applied**: Host, Guest, Guest 2, Guest 3, etc.

## Development

### Running Tests

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run integration tests only
pytest tests/test_deepgram_integration.py
```

### Mock Mode

Use `--mock` flag to test without making actual API calls:

```bash
python -m src.cli transcribe --feed-url https://example.com/podcast.rss --mock
```

## Deepgram Pricing

- **Pre-recorded audio**: $0.0043/minute (~$0.26/hour)
- **New users**: $200 free credits
- **Billing**: Per-second billing (no rounding up)

For a typical 60-minute podcast episode, transcription costs approximately $0.26.

## Troubleshooting

### Common Issues

1. **"DEEPGRAM_API_KEY environment variable is required"**
   - Ensure you've set your API key in the environment or .env file

2. **Output files not where expected**
   - Check `TRANSCRIPT_OUTPUT_DIR` environment variable
   - Verify directory permissions

3. **Speaker identification seems wrong**
   - The system assumes the first speaker is the host
   - For podcasts with non-standard formats, speaker mapping may need adjustment

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
python -m src.cli transcribe --feed-url https://example.com/podcast.rss -v
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details