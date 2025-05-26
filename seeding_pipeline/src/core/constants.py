"""
System constants for the podcast knowledge pipeline.

This module defines constants used throughout the system that should not be
configurable by users.
"""

# Version information
VERSION = "0.1.0"
API_VERSION = "v1"

# Model identifiers
WHISPER_MODELS = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
DEFAULT_WHISPER_MODEL = "large-v3"

GEMINI_MODELS = {
    "gemini-2.5-flash": "gemini-2.5-flash-preview-04-17",
    "gemini-2.0-flash": "gemini-2.0-flash-exp",
    "gemini-1.5-pro": "gemini-1.5-pro-latest",
}

# Embedding models
EMBEDDING_MODELS = {
    "openai": "text-embedding-ada-002",
    "sentence-transformers": "all-MiniLM-L6-v2",
}

# Processing limits
MAX_TRANSCRIPT_LENGTH = 500000  # characters
MAX_SEGMENT_LENGTH = 10000  # characters
MAX_ENTITIES_PER_EPISODE = 1000
MAX_INSIGHTS_PER_EPISODE = 500
MAX_QUOTES_PER_EPISODE = 200

# Batch processing
DEFAULT_BATCH_SIZE = 10
MAX_BATCH_SIZE = 100
DEFAULT_EMBEDDING_BATCH_SIZE = 50

# Token limits by model
TOKEN_LIMITS = {
    "gemini-2.5-flash": 1000000,  # 1M context window
    "gemini-2.0-flash": 1000000,  # 1M context window
    "gemini-1.5-pro": 2000000,    # 2M context window
    "gpt-4": 128000,              # 128k context window
    "gpt-3.5-turbo": 16385,       # 16k context window
}

# Task token estimates
TASK_TOKEN_ESTIMATES = {
    "insights": 150000,      # Full transcript analysis
    "entities": 150000,      # Full transcript analysis
    "key_quotes": 100000,    # Quote extraction
    "complexity": 5000,      # Per segment
    "density": 5000,         # Per segment
    "best_of": 5000,         # Per segment
}

# Rate limits (requests per minute)
DEFAULT_RATE_LIMITS = {
    "gemini": 60,
    "openai": 60,
    "embeddings": 500,
}

# Checkpoint settings
CHECKPOINT_VERSION = "1.0"
CHECKPOINT_COMPRESSION = "gzip"

# Neo4j schema version
SCHEMA_VERSION = "1.0.0"

# File extensions
AUDIO_EXTENSIONS = [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"]
TRANSCRIPT_EXTENSIONS = [".txt", ".vtt", ".srt", ".json"]

# Advertisement detection markers
AD_MARKERS = [
    "sponsor", "sponsored by", "brought to you by", "discount code",
    "promo code", "offer code", "special offer", "limited time offer",
    "visit", "click the link", "check out", "use code", "percent off",
    "slash", "dot com", "www", "http",
]

# Complexity thresholds
COMPLEXITY_THRESHOLDS = {
    "layperson": (0.0, 0.33),
    "intermediate": (0.33, 0.67),
    "expert": (0.67, 1.0),
}

# Sentiment thresholds
SENTIMENT_THRESHOLDS = {
    "positive": 0.2,
    "negative": -0.2,
    "neutral": (-0.2, 0.2),
}

# Graph analysis thresholds
BRIDGE_SCORE_THRESHOLD = 0.7
PERIPHERAL_SCORE_THRESHOLD = 0.3
CO_OCCURRENCE_MIN_WEIGHT = 2

# Memory thresholds (in GB)
MEMORY_WARNING_THRESHOLD = 3.5
MEMORY_CRITICAL_THRESHOLD = 4.0

# Retry settings
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_BACKOFF_FACTOR = 2.0

# Logging formats
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Progress bar settings
PROGRESS_BAR_WIDTH = 80
PROGRESS_UPDATE_INTERVAL = 0.1  # seconds

# Health check intervals (seconds)
HEALTH_CHECK_INTERVAL = 60
PROVIDER_TIMEOUT = 30

# Cache settings
CACHE_TTL = 900  # 15 minutes
MAX_CACHE_SIZE = 1000  # entries

# Validation patterns
URL_PATTERN = r"^https?://[^\s]+$"
EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
EPISODE_ID_PATTERN = r"^episode_[a-f0-9]{32}$"
ENTITY_ID_PATTERN = r"^entity_[a-f0-9]{28}$"

# Default directories (relative to base_dir)
DEFAULT_AUDIO_DIR = "podcast_audio"
DEFAULT_OUTPUT_DIR = "processed_podcasts"
DEFAULT_CHECKPOINT_DIR = "checkpoints"
DEFAULT_CACHE_DIR = "cache"

# Feature flags (compile-time constants)
ENABLE_EXPERIMENTAL_FEATURES = False
ENABLE_DEBUG_MODE = False
ENABLE_PROFILING = False