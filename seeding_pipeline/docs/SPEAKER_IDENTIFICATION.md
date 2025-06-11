# Speaker Identification System Documentation

## Overview

The Speaker Identification System is an LLM-based component that automatically identifies and labels speakers in VTT transcripts, replacing generic labels (Speaker 0, Speaker 1, etc.) with actual names or descriptive roles. This enhancement significantly improves the quality of knowledge extraction and relationship mapping in the knowledge graph.

## Table of Contents

1. [Architecture](#architecture)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [How It Works](#how-it-works)
5. [Performance Optimization](#performance-optimization)
6. [Monitoring and Metrics](#monitoring-and-metrics)
7. [Troubleshooting](#troubleshooting)
8. [Examples](#examples)
9. [API Reference](#api-reference)

## Architecture

### System Components

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   VTT Parser    │────▶│  VTT Segmenter   │────▶│   Knowledge     │
│                 │     │                  │     │   Extraction    │
└─────────────────┘     └──────┬───────────┘     └─────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Speaker Identifier   │
                    │                      │
                    │ ┌──────────────────┐ │
                    │ │   LLM Service    │ │
                    │ └──────────────────┘ │
                    │                      │
                    │ ┌──────────────────┐ │
                    │ │ Speaker Database │ │
                    │ └──────────────────┘ │
                    │                      │
                    │ ┌──────────────────┐ │
                    │ │  Metrics Tracker │ │
                    │ └──────────────────┘ │
                    └──────────────────────┘
```

### Key Classes

- **SpeakerIdentifier**: Main service class that orchestrates speaker identification
- **SpeakerDatabase**: Persistent cache for known speaker mappings
- **SpeakerIdentificationMetrics**: Comprehensive metrics tracking and reporting
- **VTTSegmenter**: Integration point that calls speaker identification

## Configuration

### Environment Variables

```bash
# Feature flag to enable/disable speaker identification
FF_ENABLE_SPEAKER_IDENTIFICATION=true

# Speaker identification settings
SPEAKER_DB_PATH=/path/to/speaker/cache
SPEAKER_CONFIDENCE_THRESHOLD=0.7
SPEAKER_TIMEOUT_SECONDS=30
MAX_SEGMENTS_FOR_CONTEXT=50
```

### VTT Segmenter Configuration

```python
config = {
    'speaker_db_path': './speaker_cache',
    'speaker_confidence_threshold': 0.7,
    'speaker_timeout_seconds': 30,
    'max_segments_for_context': 50,
    'ad_detection_enabled': True,
    'use_semantic_boundaries': True
}

segmenter = VTTSegmenter(config=config, llm_service=gemini_service)
```

### Feature Flag

The system respects the `ENABLE_SPEAKER_IDENTIFICATION` feature flag:

```python
from src.core.feature_flags import FeatureFlag, is_enabled

if is_enabled(FeatureFlag.ENABLE_SPEAKER_IDENTIFICATION):
    # Speaker identification will run
    pass
```

## Usage

### Basic Usage

```python
from src.vtt.vtt_segmentation import VTTSegmenter
from src.services.llm_gemini_direct import GeminiDirectService

# Initialize services
llm_service = GeminiDirectService(
    key_rotation_manager=key_manager,
    model_name='gemini-2.0-flash-001'
)

# Create segmenter with speaker identification
segmenter = VTTSegmenter(
    config={'speaker_db_path': './cache'},
    llm_service=llm_service
)

# Process segments
result = segmenter.process_segments(
    segments,
    episode_metadata={
        'podcast_name': 'Tech Talk Daily',
        'episode_title': 'AI Discussion',
        'description': 'Interview with AI expert'
    }
)

# Access speaker identification results
speaker_info = result['metadata']['speaker_identification']
print(speaker_info['speaker_mappings'])
# Output: {'Speaker 0': 'John Smith (Host)', 'Speaker 1': 'Dr. Jane Doe (Guest)'}
```

### Direct Usage of SpeakerIdentifier

```python
from src.extraction.speaker_identifier import SpeakerIdentifier

identifier = SpeakerIdentifier(
    llm_service=llm_service,
    confidence_threshold=0.8,
    speaker_db_path='./speaker_cache'
)

result = identifier.identify_speakers(
    segments, 
    metadata,
    cached_content_name='episode_12345'  # Optional
)
```

## How It Works

### 1. Statistics Calculation

The system first analyzes speaking patterns:
- Speaking time and percentage
- Turn counts and average turn length
- First appearance timing
- Word count per speaker

### 2. Context Preparation

Three types of context are prepared for the LLM:
- **Episode Metadata**: Podcast name, title, description
- **Speaker Statistics**: Formatted speaking pattern data
- **Opening Segments**: First 10 minutes of conversation

### 3. LLM Analysis

The LLM analyzes patterns to identify speakers through:
- Self-introductions ("I'm John Smith")
- Address patterns ("Welcome, Dr. Smith")
- Host/guest dynamics
- Speaking dominance patterns

### 4. Confidence Scoring

Each identification receives a confidence score (0.0-1.0):
- **High (≥0.8)**: Clear identification from multiple signals
- **Medium (0.6-0.8)**: Probable identification
- **Low (<0.6)**: Converted to descriptive roles

### 5. Fallback Strategies

For low-confidence or failed identifications:
- **Primary Speaker**: >40% speaking time
- **Co-host/Major Guest**: 20-40% speaking time
- **Guest/Contributor**: 5-20% speaking time
- **Brief Contributor**: <5% speaking time

## Performance Optimization

### 1. Episode-Level Caching

The system leverages Gemini's prompt caching:
- Full transcript cached once per episode
- 75% cost savings on cached tokens
- Shared cache across all extraction operations

### 2. Speaker Database

Known speakers are cached persistently:
- Automatic matching for recurring podcasts
- Pattern-based speaker matching
- 30-day TTL for cached entries

### 3. Batching and Timeouts

- Maximum 50 segments sent to LLM (configurable)
- 30-second timeout with graceful degradation
- Exponential backoff for retries

## Monitoring and Metrics

### Real-time Metrics

```python
# Get performance metrics
metrics = identifier.get_performance_metrics()
print(json.dumps(metrics, indent=2))
```

Output example:
```json
{
  "cache_stats": {
    "cache_hits": 45,
    "cache_attempts": 50,
    "cache_hit_rate": 0.9,
    "database_stats": {
      "podcasts_cached": 25,
      "total_speakers": 89,
      "average_confidence": 0.82
    }
  },
  "speaker_metrics": {
    "overview": {
      "total_identifications": 150,
      "success_rate": 0.94,
      "total_speakers_identified": 312
    },
    "cache_performance": {
      "cache_hit_rate": 0.9,
      "llm_calls_saved": 135
    },
    "response_times": {
      "avg_response_time_ms": 850,
      "p95_response_time_ms": 1200
    }
  }
}
```

### Metrics Report

```python
# Generate comprehensive report
report = identifier.generate_metrics_report('./reports/speaker_metrics.md')
```

## Troubleshooting

### Common Issues

#### 1. Low Confidence Identifications

**Symptoms**: Many speakers assigned descriptive roles instead of names

**Solutions**:
- Check if speakers introduce themselves clearly
- Verify episode metadata quality
- Consider lowering confidence threshold (default: 0.7)

#### 2. Timeouts

**Symptoms**: "LLM call timed out" errors

**Solutions**:
- Increase `speaker_timeout_seconds` (default: 30)
- Reduce `max_segments_for_context` (default: 50)
- Check network connectivity

#### 3. Cache Misses

**Symptoms**: Low cache hit rate, high LLM costs

**Solutions**:
- Ensure consistent podcast naming
- Check speaker database path permissions
- Verify cache TTL settings

#### 4. Incorrect Speaker Assignments

**Symptoms**: Speakers consistently misidentified

**Solutions**:
- Review and update prompt template
- Check for unusual speaking patterns
- Manually store correct mappings in database

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger('src.extraction.speaker_identifier').setLevel(logging.DEBUG)
```

## Examples

### Successful Identification

**Input Segments**:
```
Speaker 0: "Welcome to Tech Talk. I'm your host, John Smith."
Speaker 1: "Thanks John. I'm Dr. Jane Doe from AI Labs."
```

**Result**:
```json
{
  "speaker_mappings": {
    "Speaker 0": "John Smith (Host)",
    "Speaker 1": "Dr. Jane Doe (AI Labs)"
  },
  "confidence_scores": {
    "Speaker 0": 0.95,
    "Speaker 1": 0.92
  },
  "identification_methods": {
    "Speaker 0": "Self-introduction and host pattern",
    "Speaker 1": "Self-introduction with affiliation"
  }
}
```

### Fallback Identification

**Input Segments**:
```
Speaker 0: "So what do you think about this topic?"
Speaker 1: "Well, I believe it's quite interesting."
Speaker 2: "Can I add something briefly?"
```

**Result**:
```json
{
  "speaker_mappings": {
    "Speaker 0": "Primary Host (65% airtime)",
    "Speaker 1": "Main Guest (30% airtime)",
    "Speaker 2": "Brief Contributor (Speaker 2)"
  },
  "confidence_scores": {
    "Speaker 0": 0.4,
    "Speaker 1": 0.3,
    "Speaker 2": 0.2
  },
  "unresolved_speakers": ["Speaker 0", "Speaker 1", "Speaker 2"]
}
```

### Single Speaker Optimization

**Input**: Only one speaker detected

**Result**:
```json
{
  "speaker_mappings": {
    "Speaker 0": "Host/Narrator"
  },
  "confidence_scores": {
    "Speaker 0": 0.9
  },
  "identification_methods": {
    "Speaker 0": "Single speaker podcast"
  }
}
```

## API Reference

### SpeakerIdentifier

```python
class SpeakerIdentifier:
    def __init__(
        self,
        llm_service: GeminiDirectService,
        confidence_threshold: float = 0.7,
        use_large_context: bool = True,
        timeout_seconds: int = 30,
        max_segments_for_context: int = 50,
        speaker_db_path: Optional[str] = None
    )
    
    def identify_speakers(
        self,
        segments: List[TranscriptSegment],
        metadata: Dict[str, Any],
        cached_content_name: Optional[str] = None
    ) -> Dict[str, Any]
    
    def get_performance_metrics(self) -> Dict[str, Any]
    
    def generate_metrics_report(
        self,
        output_path: Optional[str] = None
    ) -> str
```

### SpeakerDatabase

```python
class SpeakerDatabase:
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl_days: int = 30
    )
    
    def get_known_speakers(
        self,
        podcast_name: str
    ) -> Optional[Dict[str, Any]]
    
    def store_speakers(
        self,
        podcast_name: str,
        speakers: Dict[str, str],
        confidence_scores: Dict[str, float],
        episode_count: int = 1
    ) -> None
    
    def match_speakers(
        self,
        podcast_name: str,
        current_stats: Dict[str, Any],
        threshold: float = 0.7
    ) -> Tuple[Dict[str, str], Dict[str, float]]
```

### SpeakerIdentificationMetrics

```python
class SpeakerIdentificationMetrics:
    def __init__(
        self,
        metrics_dir: Optional[Path] = None,
        window_size: int = 1000,
        persist_interval: int = 100
    )
    
    def record_identification(
        self,
        podcast_name: str,
        result: Dict[str, Any],
        duration: float
    ) -> None
    
    def get_summary(self) -> Dict[str, Any]
    
    def generate_report(
        self,
        output_path: Optional[Path] = None
    ) -> str
```

## Best Practices

1. **Metadata Quality**: Provide comprehensive episode metadata for better identification
2. **Prompt Engineering**: Customize the prompt template for specific podcast formats
3. **Confidence Tuning**: Adjust threshold based on your quality requirements
4. **Cache Management**: Regularly clean old cache entries to maintain performance
5. **Monitoring**: Set up alerts for low success rates or high error counts
6. **Testing**: Test with diverse podcast formats before production deployment

## Integration with Knowledge Extraction

The identified speakers enhance knowledge extraction in several ways:

1. **Quote Attribution**: Quotes are properly attributed to named speakers
2. **Entity Recognition**: Speaker names become PERSON entities
3. **Relationship Mapping**: SPEAKS and MENTIONS relationships use real names
4. **Context Understanding**: Better semantic understanding of conversations

Example knowledge graph improvement:
```
Before: [Speaker 0] --SPEAKS--> "AI is transformative"
After:  [John Smith (Host)] --SPEAKS--> "AI is transformative"
```