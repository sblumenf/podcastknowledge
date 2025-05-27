"""
Central constants for the Podcast Knowledge Graph Pipeline.

This module consolidates all hardcoded values from across the codebase
to improve maintainability and configurability.
"""

# Timeout Constants (in seconds)
DEFAULT_REQUEST_TIMEOUT = 300  # 5 minutes - used for HTTP requests
NEO4J_CONNECTION_TIMEOUT = 30.0  # Neo4j connection acquisition timeout
THREAD_JOIN_TIMEOUT = 5.0  # Thread join timeout for graceful shutdown
RETRY_TIMEOUT = 30.0  # Default retry timeout
QUEUE_GET_TIMEOUT = 1.0  # Queue get operation timeout
BATCH_QUEUE_TIMEOUT = 0.1  # Batch processor queue timeout

# Batch Size Constants
DEFAULT_BATCH_SIZE = 10  # Default processing batch size
EMBEDDING_BATCH_SIZE = 50  # Batch size for embedding operations
MEMORY_BATCH_SIZE = 100  # Batch size for memory-intensive operations
MIGRATION_BATCH_SIZE = 100  # Batch size for data migration
VALIDATION_BATCH_SIZE = 1000  # Batch size for validation operations
TRACING_EXPORT_BATCH_SIZE = 512  # Max export batch size for tracing

# Confidence Thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.9  # High confidence threshold
MEDIUM_CONFIDENCE_THRESHOLD = 0.7  # Medium confidence threshold
DEFAULT_RELATIONSHIP_CONFIDENCE = 0.75  # Default confidence for relationships
BASE_ENRICHMENT_CONFIDENCE = 0.8  # Base confidence for enrichment
DEFAULT_ENTITY_CONFIDENCE = 0.8  # Default confidence for entities

# Model Parameters
DEFAULT_TEMPERATURE = 0.3  # Default temperature for LLM generation
DEFAULT_MAX_TOKENS = 2000  # Default max tokens for LLM response

# Connection Pool Sizes
DEFAULT_CONNECTION_POOL_SIZE = 10  # Default connection pool size
MAX_CONNECTION_POOL_SIZE = 50  # Maximum connection pool size

# Memory and Resource Limits
MAX_MEMORY_USAGE_MB = 1024  # Maximum memory usage in MB
MEMORY_WARNING_THRESHOLD_MB = 768  # Memory warning threshold in MB
CLEANUP_INTERVAL_SECONDS = 300  # Cleanup interval for resources

# Retry Configuration
MAX_RETRY_ATTEMPTS = 3  # Maximum number of retry attempts
RETRY_BACKOFF_FACTOR = 2.0  # Exponential backoff factor
INITIAL_RETRY_DELAY = 1.0  # Initial retry delay in seconds

# Processing Limits
MAX_SEGMENT_LENGTH = 1000  # Maximum segment length in characters
MIN_SEGMENT_LENGTH = 50  # Minimum segment length in characters
MAX_ENTITIES_PER_SEGMENT = 20  # Maximum entities to extract per segment
MAX_RELATIONSHIPS_PER_SEGMENT = 15  # Maximum relationships per segment

# Audio Processing
DEFAULT_AUDIO_SAMPLE_RATE = 16000  # Default audio sample rate
AUDIO_CHUNK_DURATION = 30  # Audio chunk duration in seconds

# Graph Database
NEO4J_MAX_TRANSACTION_RETRY_TIME = 30.0  # Max transaction retry time
NEO4J_CONNECTION_ACQUISITION_TIMEOUT = 30.0  # Connection acquisition timeout
NEO4J_MAX_CONNECTION_LIFETIME = 3600  # Max connection lifetime in seconds

# Logging and Monitoring
LOG_ROTATION_SIZE_MB = 100  # Log file rotation size
LOG_RETENTION_DAYS = 30  # Log retention period
METRICS_COLLECTION_INTERVAL = 60  # Metrics collection interval in seconds

# API Rate Limiting
DEFAULT_RATE_LIMIT_REQUESTS = 60  # Requests per minute
DEFAULT_RATE_LIMIT_WINDOW = 60  # Rate limit window in seconds
BURST_RATE_LIMIT_REQUESTS = 100  # Burst rate limit

# File Processing
MAX_FILE_SIZE_MB = 500  # Maximum file size for processing
CHUNK_SIZE_BYTES = 8192  # File read chunk size

# Checkpoint Configuration
CHECKPOINT_SAVE_INTERVAL = 300  # Checkpoint save interval in seconds
CHECKPOINT_RETENTION_DAYS = 7  # Checkpoint retention period

# Performance Thresholds
SLOW_QUERY_THRESHOLD_MS = 100  # Slow query threshold in milliseconds
MEMORY_LEAK_THRESHOLD_MB = 50  # Memory leak detection threshold