# Deepgram Setup Guide

This guide walks you through setting up Deepgram for podcast transcription.

## Getting Your Deepgram API Key

1. **Create a Deepgram Account**
   - Visit [https://console.deepgram.com/](https://console.deepgram.com/)
   - Sign up for a free account
   - New accounts receive $200 in free credits

2. **Generate an API Key**
   - Log into your Deepgram Console
   - Navigate to "API Keys" in the left sidebar
   - Click "Create a New API Key"
   - Give your key a descriptive name (e.g., "Podcast Transcriber")
   - Copy the generated key immediately (it won't be shown again)

3. **Configure Your Environment**
   - Add the API key to your `.env` file:
     ```bash
     DEEPGRAM_API_KEY=your-api-key-here
     ```
   - Or export it as an environment variable:
     ```bash
     export DEEPGRAM_API_KEY="your-api-key-here"
     ```

## Configuration Options

### Model Selection

Deepgram offers several models with different capabilities:

| Model | Description | Best For |
|-------|-------------|----------|
| `nova-2` | Latest and most accurate | General podcast transcription (recommended) |
| `nova-1` | Previous generation | Legacy compatibility |
| `enhanced` | Optimized for uncommon words | Technical/specialized content |
| `base` | Good accuracy, lower cost | Budget-conscious projects |

Set your preferred model in `.env`:
```bash
DEEPGRAM_MODEL=nova-2
```

### Output Directory

Specify where transcripts should be saved:
```bash
TRANSCRIPT_OUTPUT_DIR=output/transcripts
```

This ensures consistent file organization:
```
output/transcripts/
├── Podcast_Name_1/
│   ├── 2024-06-09_Episode_Title.vtt
│   └── 2024-06-08_Another_Episode.vtt
└── Podcast_Name_2/
    └── 2024-06-07_Episode.vtt
```

### Speaker Mapping

Enable automatic speaker identification:
```bash
SPEAKER_MAPPING_ENABLED=true
```

When enabled:
- First speaker detected is labeled as "Host"
- Subsequent speakers are "Guest", "Guest 2", etc.
- Labels appear in VTT as `<v Host>` tags

## Usage Examples

### Basic Transcription
```bash
python -m src.cli transcribe --feed-url https://example.com/podcast.rss
```

### Limited Episodes
```bash
# Transcribe only the 3 most recent episodes
python -m src.cli transcribe --feed-url https://example.com/podcast.rss --max-episodes 3
```

### Testing with Mocks
```bash
# Test the system without using API credits
python -m src.cli transcribe --feed-url https://example.com/podcast.rss --mock
```

### Custom Output Directory
```bash
# Override the default output directory
python -m src.cli transcribe --feed-url https://example.com/podcast.rss --output-dir ./my-transcripts
```

## Cost Estimation

Deepgram pricing for pre-recorded audio (as of 2024):
- **Rate**: $0.0043 per minute
- **Billing**: Per-second (no rounding up)

Examples:
- 30-minute episode: ~$0.13
- 60-minute episode: ~$0.26
- 90-minute episode: ~$0.39

With $200 free credits, you can transcribe:
- ~46,500 minutes (775 hours) of audio
- Approximately 775-1,550 typical podcast episodes

## Monitoring Usage

Track your Deepgram usage:
1. Log into the Deepgram Console
2. Navigate to "Usage" in the sidebar
3. View credits remaining and usage history

## Best Practices

1. **Start with Mock Mode**: Test your setup using `--mock` before using credits
2. **Process in Batches**: Use `--max-episodes` to control costs
3. **Monitor Output Quality**: Review initial transcripts to ensure settings are optimal
4. **Use Appropriate Models**: nova-2 is recommended for most podcasts
5. **Set Clear Output Paths**: Use `TRANSCRIPT_OUTPUT_DIR` for consistent organization

## Troubleshooting

### API Key Issues
```
Error: DEEPGRAM_API_KEY environment variable is required
```
Solution: Ensure your API key is properly set in `.env` or environment

### Network Errors
```
Error: Failed to connect to Deepgram API
```
Solution: Check internet connection and firewall settings

### Invalid Audio Format
```
Error: Audio format not supported
```
Solution: Deepgram supports most common formats (MP3, WAV, M4A, etc.)

## Next Steps

1. Test with a single episode first
2. Review the generated VTT file for accuracy
3. Adjust speaker mapping if needed
4. Scale up to full podcast catalogs

For more information, visit the [Deepgram Documentation](https://developers.deepgram.com/docs).