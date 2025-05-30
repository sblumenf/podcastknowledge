# Dependency Analysis Report

Total unique dependencies found: 114

## Dependencies by Category

### Other
- **typing**: Used in 95 files
- **logging**: Used in 64 files
- **src**: Used in 45 files
- **datetime**: Used in 39 files
- **dataclasses**: Used in 35 files
- **time**: Used in 22 files
- **core**: Used in 20 files
- **functools**: Used in 20 files
- **os**: Used in 18 files
- **collections**: Used in 18 files
- **json**: Used in 17 files
- **re**: Used in 17 files
- **pathlib**: Used in 16 files
- **enum**: Used in 15 files
- **contextlib**: Used in 14 files
- **utils**: Used in 12 files
- **hashlib**: Used in 8 files
- **asyncio**: Used in 7 files
- **threading**: Used in 6 files
- **api**: Used in 6 files
- **abc**: Used in 6 files
- **providers**: Used in 5 files
- **signal**: Used in 5 files
- **sys**: Used in 5 files
- **seeding**: Used in 4 files
- **math**: Used in 4 files
- **__version__**: Used in 3 files
- **warnings**: Used in 3 files
- **importlib**: Used in 3 files
- **difflib**: Used in 3 files
- **uuid**: Used in 3 files
- **gc**: Used in 3 files
- **queue**: Used in 3 files
- **tracer**: Used in 3 files
- **tracing**: Used in 2 files
- **metrics**: Used in 2 files
- **flask**: Used in 2 files
- **neo4j_graphrag**: Used in 2 files
- **exceptions**: Used in 2 files
- **langchain_google_genai**: Used in 2 files
- **inspect**: Used in 2 files
- **statistics**: Used in 2 files
- **base**: Used in 2 files
- **random**: Used in 2 files
- **multiprocessing**: Used in 2 files
- **concurrent**: Used in 2 files
- **pickle**: Used in 2 files
- **shutil**: Used in 2 files
- **tempfile**: Used in 2 files
- **middleware**: Used in 2 files
- **traceback**: Used in 2 files
- **dateutil**: Used in 2 files
- **tracemalloc**: Used in 2 files
- **health**: Used in 1 files
- **v1**: Used in 1 files
- **redis**: Used in 1 files
- **factories**: Used in 1 files
- **interfaces**: Used in 1 files
- **models**: Used in 1 files
- **config**: Used in 1 files
- **feature_flags**: Used in 1 files
- **query_translator**: Used in 1 files
- **result_standardizer**: Used in 1 files
- **segmentation**: Used in 1 files
- **strategies**: Used in 1 files
- **colorsys**: Used in 1 files
- **community**: Used in 1 files
- **itertools**: Used in 1 files
- **fixed_schema_adapter**: Used in 1 files
- **schemaless_adapter**: Used in 1 files
- **extraction**: Used in 1 files
- **audio**: Used in 1 files
- **mock**: Used in 1 files
- **nest_asyncio**: Used in 1 files
- **gzip**: Used in 1 files
- **zipfile**: Used in 1 files
- **fcntl**: Used in 1 files
- **errno**: Used in 1 files
- **orchestrator**: Used in 1 files
- **signal_manager**: Used in 1 files
- **provider_coordinator**: Used in 1 files
- **checkpoint_manager**: Used in 1 files
- **pipeline_executor**: Used in 1 files
- **storage_coordinator**: Used in 1 files
- **instrumentation**: Used in 1 files
- **urllib**: Used in 1 files
- **pythonjsonlogger**: Used in 1 files
- **contextvars**: Used in 1 files
- **matplotlib**: Used in 1 files
- **cProfile**: Used in 1 files
- **pstats**: Used in 1 files
- **io**: Used in 1 files
- **atexit**: Used in 1 files
- **weakref**: Used in 1 files
- **string**: Used in 1 files
- **unicodedata**: Used in 1 files

### Api Web
- **fastapi**: Used in 5 files
- **uvicorn**: Used in 1 files

### Database
- **neo4j**: Used in 4 files

### Core Utilities
- **psutil**: Used in 6 files
- **yaml**: Used in 6 files
- **numpy**: Used in 5 files
- **networkx**: Used in 3 files
- **scipy**: Used in 3 files
- **dotenv**: Used in 1 files

### Audio Processing
- **whisper**: Used in 4 files
- **torch**: Used in 3 files
- **pyannote**: Used in 2 files
- **faster_whisper**: Used in 2 files

### Llm Ai
- **openai**: Used in 2 files
- **langchain**: Used in 1 files

### Rss Feed
- **feedparser**: Used in 2 files

### Embeddings
- **sentence_transformers**: Used in 1 files

### Monitoring
- **opentelemetry**: Used in 3 files

## Removal Recommendations

### Full Removal
- Audio Processing
- Rss Feed
- Monitoring

### Keep
- Database
- Llm Ai
- Embeddings
- Core Utilities

### Partial Removal
- Api Web: Keep minimal API for health checks and status
