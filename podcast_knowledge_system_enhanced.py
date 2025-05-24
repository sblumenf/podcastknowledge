#!/usr/bin/env python3
# Podcast Knowledge System Complete Implementation

"""
Podcast Knowledge System - Single File Implementation for Colab

This file contains a complete podcast processing pipeline for knowledge extraction,
designed to be easily converted to a Colab notebook.

TABLE OF CONTENTS:
1. IMPORTS AND ENVIRONMENT SETUP (lines ~50-150)
2. CONFIGURATION AND SETTINGS (lines ~150-300)
3. DATABASE OPERATIONS (lines ~300-1000)
4. AUDIO PROCESSING (lines ~1000-1600)
5. KNOWLEDGE EXTRACTION (lines ~1600-2800)
6. VISUALIZATION AND REPORTING (lines ~2800-3500)
7. PIPELINE ORCHESTRATION (lines ~3500-3900)
8. COMMAND LINE INTERFACE (lines ~3900-4028)

USAGE:
- For Colab: Copy sections into notebook cells as needed
- For CLI: Run directly with python script.py
- For testing: Use --episodes 1 flag to process single episode

CONFIGURATION FLAGS:
- ENABLE_AUDIO_PROCESSING: Enable/disable transcription and diarization
- ENABLE_KNOWLEDGE_EXTRACTION: Enable/disable LLM-based extraction
- ENABLE_GRAPH_ENHANCEMENTS: Enable/disable advanced graph operations
- ENABLE_VISUALIZATION: Enable/disable chart generation
- ENABLE_SPEAKER_DIARIZATION: Enable/disable speaker identification

KEY CLASSES:
- PodcastConfig: Central configuration management
- AudioProcessor: Handles transcription and diarization
- KnowledgeExtractor: LLM-based insight and entity extraction
- GraphOperations: Neo4j database operations
- Visualizer: Chart and graph visualization
- PodcastKnowledgePipeline: Master orchestrator

NOTE: This file is structured for easy conversion to Colab notebooks.
Each section can be copied into separate notebook cells.

BATCH SEEDING MODE:
This version has been optimized for knowledge graph seeding with:
- BATCH_MODE flag for unattended processing
- Minimal logging (errors only by default)
- Removed visualization and interactive features
- Streamlined seed_podcasts() function for batch processing
- Optimized for GPU transcription and embedding generation
- Checkpoint support for resuming interrupted processing

To use for seeding:
1. Set environment variables (NEO4J_PASSWORD, GOOGLE_API_KEY, etc.)
2. Call seed_single_podcast() or seed_podcasts()
3. Monitor progress via returned summary statistics
"""

# ============================================================================
# SECTION 1: IMPORTS AND ENVIRONMENT SETUP
# ============================================================================

# Standard Library Imports
import os
import re
import json
import time
import hashlib
import urllib.request
from datetime import datetime
from collections import defaultdict
import argparse
import gc
import logging
import sys
import difflib  # Added for fuzzy matching in entity resolution
from itertools import combinations
import math

# Core Dependencies
try:
    import torch
except ImportError:
    print("Warning: PyTorch not available. Some features may be limited.")
    torch = None

try:
    from neo4j import GraphDatabase
except ImportError:
    raise ImportError("Neo4j driver required. Install with: pip install neo4j")

try:
    from dotenv import load_dotenv
except ImportError:
    print("Warning: python-dotenv not available. Using environment variables directly.")
    load_dotenv = lambda: None

# Scientific Computing Dependencies
try:
    import numpy as np
except ImportError:
    print("Warning: NumPy not available. Install with: pip install numpy")
    np = None

try:
    from scipy.stats import entropy
except ImportError:
    print("Warning: SciPy not available. Install with: pip install scipy")
    entropy = None

try:
    import networkx as nx
    from networkx.algorithms import community
except ImportError:
    print("Warning: NetworkX not available. Install with: pip install networkx")
    nx = None
    community = None

# LLM and AI Dependencies
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    print("Warning: Google Generative AI not available. Install with: pip install langchain-google-genai")
    ChatGoogleGenerativeAI = None

try:
    from langchain.prompts import ChatPromptTemplate
except ImportError:
    print("Warning: LangChain not available. Install with: pip install langchain")
    ChatPromptTemplate = None

try:
    from openai import OpenAI
except ImportError:
    print("Warning: OpenAI not available. Install with: pip install openai")
    OpenAI = None

# Audio Processing Dependencies
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("Warning: faster-whisper not available. Install with: pip install faster-whisper")
    WhisperModel = None

try:
    import whisper
except ImportError:
    print("Warning: whisper not available. Install with: pip install openai-whisper")
    whisper = None

try:
    from pyannote.audio import Pipeline
except ImportError:
    print("Warning: pyannote.audio not available. Install with: pip install pyannote-audio")
    Pipeline = None

# Data Processing Dependencies
try:
    import feedparser
except ImportError:
    print("Warning: feedparser not available. Install with: pip install feedparser")
    feedparser = None

# Visualization Dependencies
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.colors import LinearSegmentedColormap
except ImportError:
    print("Warning: matplotlib not available. Visualization features disabled.")
    plt = None
    patches = None
    LinearSegmentedColormap = None

# Progress Tracking (for notebook conversion)
try:
    from tqdm import tqdm
except ImportError:
    print("Warning: tqdm not available. Install with: pip install tqdm")
    # Fallback progress tracker
    class tqdm:
        def __init__(self, iterable=None, desc="", total=None):
            self.iterable = iterable
            self.desc = desc
            self.total = total or (len(iterable) if iterable else 0)
            self.current = 0
            
        def __iter__(self):
            for item in self.iterable:
                yield item
                self.current += 1
                if self.current % max(1, self.total // 10) == 0:
                    print(f"{self.desc}: {self.current}/{self.total}")
                    
        def update(self, n=1):
            self.current += n
            if self.current % max(1, self.total // 10) == 0:
                print(f"{self.desc}: {self.current}/{self.total}")

# Load environment variables
load_dotenv()

# ============================================================================
# SECTION 2: CONFIGURATION AND SETTINGS
# ============================================================================

# Batch mode flag for streamlined processing
BATCH_MODE = True  # Set to True for unattended knowledge seeding

# Set up logging
logging.basicConfig(
    level=logging.INFO if not BATCH_MODE else logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Feature flags for optional functionality
# These can be modified at runtime to disable specific features
ENABLE_AUDIO_PROCESSING = True
ENABLE_KNOWLEDGE_EXTRACTION = True
ENABLE_GRAPH_ENHANCEMENTS = True
ENABLE_VISUALIZATION = False  # Disabled for batch seeding
ENABLE_SPEAKER_DIARIZATION = True

# Quick access to feature flags for easy modification
FEATURE_FLAGS = {
    'audio': lambda x: globals().update({'ENABLE_AUDIO_PROCESSING': x}),
    'extraction': lambda x: globals().update({'ENABLE_KNOWLEDGE_EXTRACTION': x}),
    'enhancements': lambda x: globals().update({'ENABLE_GRAPH_ENHANCEMENTS': x}),
    'visualization': lambda x: globals().update({'ENABLE_VISUALIZATION': x}),
    'diarization': lambda x: globals().update({'ENABLE_SPEAKER_DIARIZATION': x})
}

class PodcastConfig:
    """Centralized configuration for podcast processing system."""
    
    # Audio Processing Settings
    MIN_SEGMENT_TOKENS = 150
    MAX_SEGMENT_TOKENS = 800
    WHISPER_MODEL_SIZE = "large-v3"
    USE_FASTER_WHISPER = True
    
    # Speaker Diarization
    MIN_SPEAKERS = 1
    MAX_SPEAKERS = 10
    
    # Neo4j Database Settings
    NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")
    NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    # Embedding Settings
    EMBEDDING_DIMENSIONS = 1536
    EMBEDDING_SIMILARITY = 'cosine'
    
    # File Paths (Colab-ready)
    BASE_DIR = "/content/drive/MyDrive" if os.path.exists("/content") else "."
    AUDIO_DIR = f"{BASE_DIR}/podcast_audio"
    OUTPUT_DIR = f"{BASE_DIR}/processed_podcasts"
    CHECKPOINT_DIR = f"{BASE_DIR}/checkpoints"
    
    # Processing Settings
    MAX_EPISODES = 1
    USE_LARGE_CONTEXT = True
    ENABLE_GRAPH_ENHANCEMENTS = True
    
    # GPU and Memory Settings
    USE_GPU = True
    ENABLE_AD_DETECTION = True
    USE_SEMANTIC_BOUNDARIES = True
    
    # Progress and Monitoring
    CHECKPOINT_INTERVAL = 1  # Save after each episode
    MEMORY_CLEANUP_INTERVAL = 1  # Cleanup after each episode

class SeedingConfig(PodcastConfig):
    """Configuration optimized for batch knowledge seeding."""
    
    # Logging configuration for batch mode
    LOG_LEVEL = "ERROR"  # Only log errors in batch mode
    SAVE_CHECKPOINTS = True
    CHECKPOINT_EVERY_N = 5  # Episodes
    EMBEDDING_BATCH_SIZE = 50  # For batch embedding generation
    ENABLE_PROGRESS_BAR = True  # Simple progress only
    
    # Disable interactive features
    INTERACTIVE_MODE = False
    SAVE_VISUALIZATIONS = False
    GENERATE_REPORTS = False
    VERBOSE_LOGGING = False
    
    @classmethod
    def get_segmenter_config(cls):
        """Get configuration for the podcast segmenter."""
        return {
            'min_segment_tokens': cls.MIN_SEGMENT_TOKENS,
            'max_segment_tokens': cls.MAX_SEGMENT_TOKENS,
            'use_gpu': cls.USE_GPU,
            'ad_detection_enabled': cls.ENABLE_AD_DETECTION,
            'use_semantic_boundaries': cls.USE_SEMANTIC_BOUNDARIES,
            'min_speakers': cls.MIN_SPEAKERS,
            'max_speakers': cls.MAX_SPEAKERS
        }
    
    @classmethod
    def validate_dependencies(cls):
        """Validate that required dependencies are available."""
        missing = []
        
        if ChatGoogleGenerativeAI is None:
            missing.append("langchain-google-genai")
        if OpenAI is None:
            missing.append("openai")
        if WhisperModel is None and whisper is None:
            missing.append("faster-whisper or openai-whisper")
        if feedparser is None:
            missing.append("feedparser")
            
        if missing:
            print(f"Missing dependencies: {', '.join(missing)}")
            print("Some features may not work properly.")
            return False
        return True
    
    @classmethod
    def setup_directories(cls):
        """Ensure all required directories exist."""
        for directory in [cls.AUDIO_DIR, cls.OUTPUT_DIR, cls.CHECKPOINT_DIR]:
            os.makedirs(directory, exist_ok=True)
            print(f"Directory ready: {directory}")

# ============================================================================
# SECTION 2.1: CUSTOM EXCEPTIONS FOR BETTER ERROR HANDLING
# ============================================================================

class PodcastProcessingError(Exception):
    """Base exception for podcast processing errors."""
    pass

class DatabaseConnectionError(PodcastProcessingError):
    """Raised when Neo4j connection fails."""
    pass

class AudioProcessingError(PodcastProcessingError):
    """Raised when audio transcription or diarization fails."""
    pass

class LLMProcessingError(PodcastProcessingError):
    """Raised when LLM processing fails."""
    pass

class ConfigurationError(PodcastProcessingError):
    """Raised when configuration is invalid."""
    pass

# ============================================================================
# SECTION 2.2: RESOURCE MANAGEMENT UTILITIES
# ============================================================================

class Neo4jManager:
    """Context manager for Neo4j connections."""
    
    def __init__(self, config=None):
        self.config = config or PodcastConfig
        self.driver = None
        
    def __enter__(self):
        try:
            self.driver = GraphDatabase.driver(
                self.config.NEO4J_URI,
                auth=(self.config.NEO4J_USERNAME, self.config.NEO4J_PASSWORD)
            )
            
            # Verify connection
            with self.driver.session(database=self.config.NEO4J_DATABASE) as session:
                result = session.run("RETURN 'Connection Successful' AS result")
                message = result.single()["result"]
                print(f"Neo4j connection: {message}")
                
            return self.driver
            
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to connect to Neo4j: {e}")
            
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            try:
                self.driver.close()
                print("Neo4j connection closed")
            except Exception as e:
                print(f"Warning: Error closing Neo4j connection: {e}")

def cleanup_memory():
    """Clean up memory after processing operations."""
    gc.collect()
    if torch and torch.cuda.is_available():
        torch.cuda.empty_cache()
        print("GPU memory cleared")
    
    # Clear matplotlib figures if available
    if plt:
        plt.close('all')
        
    # Force garbage collection
    gc.collect()

def monitor_memory():
    """Monitor current memory usage."""
    try:
        import psutil
        memory = psutil.virtual_memory()
        print(f"Memory usage: {memory.percent:.1f}% ({memory.used // (1024**3):.1f}GB / {memory.total // (1024**3):.1f}GB)")
        
        # GPU memory monitoring
        if torch and torch.cuda.is_available():
            gpu_memory = torch.cuda.memory_allocated() / (1024**3)
            gpu_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            print(f"GPU usage: {gpu_memory:.1f}GB / {gpu_total:.1f}GB")
            
    except ImportError:
        print("psutil not available for memory monitoring")
    except Exception as e:
        print(f"Error monitoring memory: {e}")

# ============================================================================
# PHASE 1: MULTI-MODEL RATE LIMITING
# ============================================================================

class HybridRateLimiter:
    """
    Model-specific rate limiter for Gemini models.
    Tracks usage per model independently with smart routing.
    """
    def __init__(self):
        import time
        from collections import deque
        
        # Rate limits per model
        self.limits = {
            'gemini-2.5-flash': {
                'rpm': 10,     # Requests per minute
                'tpm': 250000, # Tokens per minute  
                'rpd': 500     # Requests per day
            },
            'gemini-2.0-flash': {
                'rpm': 15,
                'tpm': 1000000,
                'rpd': 1500
            }
        }
        
        # Track usage per model
        self.requests = {
            'gemini-2.5-flash': {
                'minute': deque(),
                'day': deque(),
                'tokens_minute': deque()
            },
            'gemini-2.0-flash': {
                'minute': deque(),
                'day': deque(),
                'tokens_minute': deque()
            }
        }
        
        # Track errors and fallbacks
        self.error_counts = defaultdict(int)
        self.fallback_counts = defaultdict(int)
        
    def can_use_model(self, model_name, estimated_tokens=0):
        """Check if model is available within rate limits."""
        import time
        current_time = time.time()
        
        if model_name not in self.limits:
            return False
            
        limits = self.limits[model_name]
        usage = self.requests[model_name]
        
        # Clean old entries
        self._clean_old_entries(usage, current_time)
        
        # Check RPM
        rpm_count = len(usage['minute'])
        if rpm_count >= limits['rpm']:
            return False
            
        # Check TPM
        tokens_used = sum(t[1] for t in usage['tokens_minute'])
        if tokens_used + estimated_tokens > limits['tpm']:
            return False
            
        # Check RPD
        rpd_count = len(usage['day'])
        if rpd_count >= limits['rpd']:
            return False
            
        return True
    
    def _clean_old_entries(self, usage, current_time):
        """Remove entries older than rate limit windows."""
        # Clean minute window (60 seconds)
        while usage['minute'] and usage['minute'][0] < current_time - 60:
            usage['minute'].popleft()
            
        while usage['tokens_minute'] and usage['tokens_minute'][0][0] < current_time - 60:
            usage['tokens_minute'].popleft()
            
        # Clean day window (24 hours)
        while usage['day'] and usage['day'][0] < current_time - 86400:
            usage['day'].popleft()
    
    def record_request(self, model_name, tokens_used):
        """Record a successful request."""
        import time
        current_time = time.time()
        
        if model_name in self.requests:
            usage = self.requests[model_name]
            usage['minute'].append(current_time)
            usage['day'].append(current_time)
            usage['tokens_minute'].append((current_time, tokens_used))
    
    def record_error(self, model_name, error_type):
        """Record an error for monitoring."""
        self.error_counts[f"{model_name}:{error_type}"] += 1
    
    def record_fallback(self, from_model, to_model):
        """Record when we fall back to another model."""
        self.fallback_counts[f"{from_model}->{to_model}"] += 1
    
    def get_status(self):
        """Get current usage status for all models."""
        import time
        current_time = time.time()
        status = {}
        
        for model_name in self.limits:
            usage = self.requests[model_name]
            self._clean_old_entries(usage, current_time)
            
            rpm_used = len(usage['minute'])
            rpd_used = len(usage['day'])
            tpm_used = sum(t[1] for t in usage['tokens_minute'])
            
            status[model_name] = {
                'rpm': f"{rpm_used}/{self.limits[model_name]['rpm']}",
                'tpm': f"{tpm_used}/{self.limits[model_name]['tpm']}",
                'rpd': f"{rpd_used}/{self.limits[model_name]['rpd']}",
                'available': self.can_use_model(model_name)
            }
            
        return status
    
    def wait_time_for_model(self, model_name):
        """Calculate wait time until model is available."""
        import time
        current_time = time.time()
        
        if model_name not in self.requests:
            return 0
            
        usage = self.requests[model_name]
        self._clean_old_entries(usage, current_time)
        
        # Check RPM limit
        if len(usage['minute']) >= self.limits[model_name]['rpm']:
            oldest_minute = usage['minute'][0]
            wait_time = max(0, 60 - (current_time - oldest_minute))
            return wait_time
            
        return 0

# ============================================================================
# PHASE 3: INTELLIGENT TASK ROUTER
# ============================================================================

class TaskRouter:
    """
    Intelligent task distribution system for hybrid LLM processing.
    Routes tasks to appropriate models based on availability and task type.
    """
    def __init__(self, rate_limiter=None):
        self.rate_limiter = rate_limiter or HybridRateLimiter()
        self.model_configs = {
            'gemini-2.5-flash': {
                'model_name': 'gemini-2.5-flash-preview-04-17',  # Correct 2.5 Flash model name
                'priority_tasks': ['insights', 'entities', 'key_quotes'],
                'temperature': 0.2
            },
            'gemini-2.0-flash': {
                'model_name': 'gemini-2.0-flash-exp',  # Correct 2.0 Flash model name
                'fallback_tasks': ['complexity', 'density', 'best_of'],
                'temperature': 0.3
            }
        }
        
        # Task token estimates
        self.task_token_estimates = {
            'insights': 150000,      # Full transcript analysis
            'entities': 150000,      # Full transcript analysis
            'key_quotes': 100000,    # Quote extraction
            'complexity': 5000,      # Per segment
            'density': 5000,         # Per segment
            'best_of': 5000         # Per segment
        }
        
        # Initialize clients
        self.clients = {}
        self._initialize_clients()
        
    def _initialize_clients(self):
        """Initialize all model clients."""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            
            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                logger.error("GOOGLE_API_KEY not found")
                return
                
            # Initialize Gemini 2.5 Flash
            self.clients['gemini-2.5-flash'] = ChatGoogleGenerativeAI(
                model=self.model_configs['gemini-2.5-flash']['model_name'],
                google_api_key=api_key,
                temperature=self.model_configs['gemini-2.5-flash']['temperature'],
                convert_system_message_to_human=True
            )
            
            # Initialize Gemini 2.0 Flash  
            self.clients['gemini-2.0-flash'] = ChatGoogleGenerativeAI(
                model=self.model_configs['gemini-2.0-flash']['model_name'],
                google_api_key=api_key,
                temperature=self.model_configs['gemini-2.0-flash']['temperature'],
                convert_system_message_to_human=True
            )
            
            logger.info("Initialized multi-model clients")
            
        except Exception as e:
            logger.error(f"Failed to initialize model clients: {e}")
    
    def route_request(self, task_type, content, retry_count=0):
        """
        Route request to appropriate model based on task type and availability.
        
        Args:
            task_type: Type of task (insights, entities, complexity, etc.)
            content: Content to process
            retry_count: Number of retries attempted
            
        Returns:
            Dict with response and metadata
        """
        # Estimate tokens
        estimated_tokens = self.task_token_estimates.get(task_type, 10000)
        
        # Determine primary model for task
        primary_model = None
        fallback_model = None
        
        if task_type in self.model_configs['gemini-2.5-flash']['priority_tasks']:
            primary_model = 'gemini-2.5-flash'
            fallback_model = 'gemini-2.0-flash'
        else:
            primary_model = 'gemini-2.0-flash'
            fallback_model = None  # No fallback for lower priority tasks
            
        # Try primary model
        if self.rate_limiter.can_use_model(primary_model, estimated_tokens):
            try:
                response = self._call_model(primary_model, task_type, content)
                self.rate_limiter.record_request(primary_model, estimated_tokens)
                return {
                    'response': response,
                    'model_used': primary_model,
                    'fallback': False
                }
            except Exception as e:
                self.rate_limiter.record_error(primary_model, str(type(e).__name__))
                logger.warning(f"Primary model {primary_model} failed: {e}")
                
        # Try fallback if available
        if fallback_model and self.rate_limiter.can_use_model(fallback_model, estimated_tokens):
            try:
                self.rate_limiter.record_fallback(primary_model, fallback_model)
                response = self._call_model(fallback_model, task_type, content)
                self.rate_limiter.record_request(fallback_model, estimated_tokens)
                return {
                    'response': response,
                    'model_used': fallback_model,
                    'fallback': True
                }
            except Exception as e:
                self.rate_limiter.record_error(fallback_model, str(type(e).__name__))
                logger.warning(f"Fallback model {fallback_model} failed: {e}")
                
        # If both models unavailable, wait or use rule-based
        if task_type in ['complexity', 'density', 'quotability']:
            # These can fall back to rule-based processing
            return {
                'response': None,
                'model_used': 'rule-based',
                'fallback': True
            }
            
        # For critical tasks, wait and retry
        if retry_count < 3:
            wait_time = min(
                self.rate_limiter.wait_time_for_model(primary_model),
                self.rate_limiter.wait_time_for_model(fallback_model) if fallback_model else float('inf')
            )
            if wait_time > 0:
                logger.info(f"Rate limited. Waiting {wait_time:.1f}s before retry...")
                time.sleep(wait_time + 1)  # Add 1s buffer
                return self.route_request(task_type, content, retry_count + 1)
                
        raise Exception(f"All models unavailable for task {task_type}")
        
    def _call_model(self, model_name, task_type, content):
        """Call specific model with task-appropriate prompt."""
        if model_name not in self.clients:
            raise ValueError(f"Model {model_name} not initialized")
            
        client = self.clients[model_name]
        
        # Route to appropriate prompt builder
        if task_type == 'insights':
            prompt = self._build_insight_prompt(content)
        elif task_type == 'entities':
            prompt = self._build_entity_prompt(content)
        elif task_type == 'key_quotes':
            prompt = self._build_quote_prompt(content)
        elif task_type == 'complexity':
            prompt = self._build_complexity_prompt(content)
        else:
            prompt = content  # Pass through for custom prompts
            
        response = client.invoke(prompt)
        return response.content
        
    def _build_insight_prompt(self, content):
        """Build insight extraction prompt - reuses existing combined prompt."""
        # For backward compatibility with existing functions
        return content
        
    def _build_entity_prompt(self, content):
        """Build entity extraction prompt - reuses existing combined prompt."""
        return content
        
    def _build_quote_prompt(self, content):
        """Build quote extraction prompt - reuses existing combined prompt."""
        return content
        
    def _build_complexity_prompt(self, content):
        """Build complexity analysis prompt."""
        return f"""
Analyze the technical complexity of this text segment.

TEXT:
{content}

Identify:
1. Technical terms and jargon
2. Average sentence complexity
3. Required background knowledge
4. Target audience level

Classify as: layperson, intermediate, or expert

Return JSON: {{"classification": "...", "technical_density": 0.0-1.0, "explanation": "..."}}
"""
        
    def get_usage_report(self):
        """Get detailed usage report."""
        status = self.rate_limiter.get_status()
        errors = dict(self.rate_limiter.error_counts)
        fallbacks = dict(self.rate_limiter.fallback_counts)
        
        return {
            'model_status': status,
            'errors': errors,
            'fallbacks': fallbacks
        }

# ============================================================================
# SECTION 2.3: ENTITY RESOLUTION UTILITIES
# ============================================================================

def normalize_entity_name(name):
    """
    Normalize entity name for comparison and deduplication.
    
    Args:
        name: Entity name to normalize
        
    Returns:
        Normalized name (lowercase, stripped, common variations handled)
    """
    if not name:
        return ""
    
    # Convert to lowercase and strip
    normalized = name.lower().strip()
    
    # Remove common suffixes
    suffixes_to_remove = [
        ", inc.", ", inc", " inc.", " inc",
        ", llc", " llc",
        ", ltd", " ltd",
        ", corp", " corp",
        " corporation",
        " company",
        " & co",
        " co."
    ]
    
    for suffix in suffixes_to_remove:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)].strip()
    
    # Handle common abbreviations
    abbreviations = {
        "&": "and",
        "u.s.": "us",
        "u.k.": "uk",
        "dr.": "doctor",
        "mr.": "mister",
        "ms.": "miss",
        "prof.": "professor"
    }
    
    for abbr, full in abbreviations.items():
        normalized = normalized.replace(abbr, full)
    
    # Remove extra whitespace
    normalized = " ".join(normalized.split())
    
    return normalized

def calculate_name_similarity(name1, name2):
    """
    Calculate similarity between two entity names.
    
    Args:
        name1: First entity name
        name2: Second entity name
        
    Returns:
        Similarity score between 0 and 1
    """
    # Normalize both names
    norm1 = normalize_entity_name(name1)
    norm2 = normalize_entity_name(name2)
    
    # Use sequence matcher for fuzzy matching
    return difflib.SequenceMatcher(None, norm1, norm2).ratio()

def extract_entity_aliases(entity_name, entity_description):
    """
    Extract potential aliases from entity description.
    
    Args:
        entity_name: Main entity name
        entity_description: Entity description that might contain aliases
        
    Returns:
        List of potential aliases
    """
    aliases = []
    
    if not entity_description:
        return aliases
    
    # Common patterns for aliases
    alias_patterns = [
        r'also known as ([^,\.]+)',
        r'formerly ([^,\.]+)',
        r'aka ([^,\.]+)',
        r'\(([^)]+)\)',  # Names in parentheses
        r'or "([^"]+)"',  # Names in quotes
        r"or '([^']+)'",  # Names in single quotes
    ]
    
    for pattern in alias_patterns:
        matches = re.findall(pattern, entity_description, re.IGNORECASE)
        aliases.extend(matches)
    
    # Clean up aliases
    cleaned_aliases = []
    for alias in aliases:
        alias = alias.strip()
        # Don't include the main name as an alias
        if alias.lower() != entity_name.lower() and alias:
            cleaned_aliases.append(alias)
    
    return cleaned_aliases

def find_existing_entity(session, new_entity_name, new_entity_type, similarity_threshold=0.85):
    """
    Find existing entities that might be duplicates of the new entity.
    
    Args:
        session: Neo4j session
        new_entity_name: Name of the new entity
        new_entity_type: Type of the new entity
        similarity_threshold: Minimum similarity score to consider a match
        
    Returns:
        List of potential duplicate entities with their similarity scores
    """
    # Normalize the new entity name
    normalized_new_name = normalize_entity_name(new_entity_name)
    
    # Query for entities of the same type
    result = session.run("""
    MATCH (e:Entity {type: $type})
    RETURN e.id as id, e.name as name, e.normalized_name as normalized_name, 
           e.aliases as aliases
    """, {"type": new_entity_type})
    
    potential_matches = []
    
    for record in result:
        existing_name = record["name"]
        existing_normalized = record.get("normalized_name", normalize_entity_name(existing_name))
        existing_aliases = record.get("aliases", [])
        
        # Check exact match on normalized names
        if normalized_new_name == existing_normalized:
            potential_matches.append({
                "id": record["id"],
                "name": existing_name,
                "similarity": 1.0,
                "match_type": "exact_normalized"
            })
            continue
        
        # Check if new name matches any aliases
        if existing_aliases and normalized_new_name in [normalize_entity_name(alias) for alias in existing_aliases]:
            potential_matches.append({
                "id": record["id"],
                "name": existing_name,
                "similarity": 0.95,
                "match_type": "alias_match"
            })
            continue
        
        # Calculate fuzzy similarity
        similarity = calculate_name_similarity(new_entity_name, existing_name)
        if similarity >= similarity_threshold:
            potential_matches.append({
                "id": record["id"],
                "name": existing_name,
                "similarity": similarity,
                "match_type": "fuzzy_match"
            })
    
    # Sort by similarity score
    potential_matches.sort(key=lambda x: x["similarity"], reverse=True)
    
    return potential_matches

def clean_segment_text_for_embedding(text):
    """
    Clean segment text for better embedding quality.
    
    Args:
        text: Raw segment text
        
    Returns:
        Cleaned text optimized for embedding
    """
    # Remove common filler words and sounds
    filler_patterns = [
        r'\b(um+|uh+|ah+|er+|hmm+)\b',
        r'\b(like)\b(?=\s+(you know|I mean|so))',
        r'\byou know\b',
        r'\bI mean\b',
        r'\b(basically|actually|literally|honestly)\b',
        r'\.\.\.',  # Ellipses
        r'\s+',  # Multiple spaces
    ]
    
    cleaned = text.lower()
    for pattern in filler_patterns:
        cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
    
    # Clean up whitespace
    cleaned = ' '.join(cleaned.split())
    
    # Truncate to reasonable length for embedding (keep first 1000 chars)
    if len(cleaned) > 1000:
        cleaned = cleaned[:1000] + '...'
    
    return cleaned

# ============================================================================
# SECTION 2.4: KNOWLEDGE ENHANCEMENT UTILITIES
# ============================================================================

def generate_stable_segment_id(episode_id, segment_text, start_time, speaker=None):
    """
    Generate stable segment ID based on content and metadata.
    
    Args:
        episode_id: Episode identifier
        segment_text: Text content of segment
        start_time: Start timestamp
        speaker: Optional speaker identifier
        
    Returns:
        Stable segment ID
    """
    # Create a content fingerprint
    # Use first 100 chars + last 100 chars to handle minor edits
    text_sample = segment_text[:100] + segment_text[-100:] if len(segment_text) > 200 else segment_text
    
    # Include speaker if available for better uniqueness
    content_string = f"{episode_id}_{start_time}_{text_sample}_{speaker or 'unknown'}"
    
    # Generate hash
    content_hash = hashlib.sha256(content_string.encode('utf-8')).hexdigest()[:12]
    
    # Create readable ID
    return f"seg_{episode_id}_{int(start_time)}_{content_hash}"

def extract_notable_quotes(segment_text, speaker, start_time, end_time, llm_client):
    """
    Extract memorable quotes as first-class entities.
    
    Args:
        segment_text: Text to extract quotes from
        speaker: Speaker name
        start_time: Segment start timestamp
        end_time: Segment end timestamp
        llm_client: LLM client or TaskRouter for extraction
        
    Returns:
        List of quote dictionaries
    """
    prompt = f"""
    Extract 0-3 highly quotable statements from this podcast segment.
    
    Criteria for a good quote:
    - Self-contained and meaningful without context
    - 10-40 words long
    - Memorable, insightful, or impactful
    - Actually said by the speaker (not paraphrased)
    
    Segment:
    Speaker: {speaker}
    Text: {segment_text}
    
    Return JSON with this exact format:
    {{
        "quotes": [
            {{
                "text": "exact quote from the segment",
                "impact_score": 7,  // 1-10 score
                "quote_type": "insight"  // insight, humor, wisdom, controversial, prediction
            }}
        ]
    }}
    
    If no quotable content, return {{"quotes": []}}
    """
    
    try:
        # Handle both llm_client and TaskRouter
        if hasattr(llm_client, 'route_request'):
            # It's a TaskRouter
            result = llm_client.route_request('quotes', prompt)
            response_content = result['response']
        else:
            # It's a regular LLM client
            response = llm_client.invoke(prompt)
            response_content = response.content
        
        quotes_data = json.loads(response_content)
        
        quotes = []
        for quote in quotes_data.get("quotes", []):
            # Verify quote actually exists in segment
            if quote["text"].lower() in segment_text.lower():
                # Find exact position in segment
                quote_start = segment_text.lower().find(quote["text"].lower())
                quote_length = len(quote["text"])
                
                # Estimate timestamp within segment
                segment_length = len(segment_text)
                time_ratio = quote_start / segment_length if segment_length > 0 else 0
                quote_timestamp = start_time + (time_ratio * (end_time - start_time))
                
                quotes.append({
                    "text": quote["text"],
                    "speaker": speaker,
                    "impact_score": quote.get("impact_score", 5),
                    "quote_type": quote.get("quote_type", "general"),
                    "segment_start": start_time,
                    "segment_end": end_time,
                    "estimated_timestamp": quote_timestamp,
                    "word_count": len(quote["text"].split())
                })
        
        return quotes
        
    except Exception as e:
        print(f"Error extracting quotes: {e}")
        return []

def extract_episode_topics(insights, entities, segments, llm_client=None):
    """
    Generate topic tags for an episode based on insights, entities, and content.
    
    Args:
        insights: List of insights extracted from episode
        entities: List of entities mentioned in episode
        segments: List of transcript segments
        llm_client: Optional LLM client for advanced topic generation
        
    Returns:
        List of topic dictionaries with scores
    """
    topic_scores = defaultdict(float)
    topic_evidence = defaultdict(list)
    
    # 1. Extract topics from insight categories
    insight_categories = defaultdict(int)
    for insight in insights:
        category = insight.get('insight_type', 'general')
        insight_categories[category] += 1
        topic_scores[category] += insight.get('confidence', 5) / 10.0
        topic_evidence[category].append(f"insight: {insight.get('title', '')[:50]}")
    
    # 2. Extract topics from high-importance entities
    entity_topics = defaultdict(float)
    for entity in entities:
        if entity.get('importance', 0) >= 7:
            entity_type = entity['type'].lower().replace('_', ' ')
            
            # Map entity types to topics
            topic_mappings = {
                'person': 'personalities',
                'company': 'business',
                'technology': 'tech',
                'framework': 'methodologies',
                'product': 'products',
                'book': 'literature',
                'concept': 'ideas',
                'medical_device': 'health tech',
                'medication': 'healthcare',
                'biological_process': 'science',
                'investment': 'finance',
                'startup': 'entrepreneurship'
            }
            
            topic = topic_mappings.get(entity_type, entity_type)
            entity_topics[topic] += entity.get('importance', 5) / 10.0
            topic_evidence[topic].append(f"entity: {entity['name']}")
    
    # Merge entity topics into main scores
    for topic, score in entity_topics.items():
        topic_scores[topic] += score
    
    # 3. Extract topics from segment content patterns
    content_patterns = {
        'entrepreneurship': [r'\bstartup\b', r'\bfounder\b', r'\bVC\b', r'\bfunding\b', r'\braise\b'],
        'technology': [r'\bAI\b', r'\bML\b', r'\bsoftware\b', r'\bapp\b', r'\btech\b'],
        'business': [r'\brevenue\b', r'\bprofit\b', r'\bbusiness model\b', r'\bmarket\b'],
        'health': [r'\bhealth\b', r'\bwellness\b', r'\bfitness\b', r'\bmedical\b'],
        'science': [r'\bresearch\b', r'\bstudy\b', r'\bscientific\b', r'\bdata\b'],
        'psychology': [r'\bmindset\b', r'\bmental\b', r'\bbehavior\b', r'\bhabit\b'],
        'productivity': [r'\bproductiv\b', r'\befficiency\b', r'\bworkflow\b', r'\btime management\b'],
        'finance': [r'\binvest\b', r'\bmoney\b', r'\bfinancial\b', r'\bstock\b', r'\bcrypto\b'],
        'marketing': [r'\bmarketing\b', r'\bgrowth\b', r'\bcustomer\b', r'\bbrand\b'],
        'leadership': [r'\bleader\b', r'\bmanage\b', r'\bteam\b', r'\bculture\b']
    }
    
    # Analyze first 10 segments for topic patterns
    sample_text = ' '.join([seg.get('text', '')[:200] for seg in segments[:10]]).lower()
    
    for topic, patterns in content_patterns.items():
        matches = sum(1 for pattern in patterns if re.search(pattern, sample_text, re.IGNORECASE))
        if matches > 0:
            topic_scores[topic] += matches * 0.2
            topic_evidence[topic].append(f"pattern matches: {matches}")
    
    # 4. Use LLM for advanced topic extraction (optional)
    if llm_client and len(segments) > 0:
        # Sample content for LLM analysis
        sample_insights = [f"- {i.get('title', '')}" for i in insights[:5]]
        sample_entities = [f"- {e['name']} ({e['type']})" for e in sorted(entities, key=lambda x: x.get('importance', 0), reverse=True)[:10]]
        
        prompt = f"""
        Based on these insights and entities from a podcast episode, identify 3-5 main topics/themes.
        
        Key Insights:
        {chr(10).join(sample_insights)}
        
        Key Entities:
        {chr(10).join(sample_entities)}
        
        Return JSON with exactly this format:
        {{
            "topics": [
                {{"name": "topic name", "confidence": 0.8, "reason": "brief explanation"}}
            ]
        }}
        
        Focus on broad, searchable topics (e.g., "entrepreneurship", "artificial intelligence", "health optimization")
        """
        
        try:
            # Handle both llm_client and TaskRouter
            if hasattr(llm_client, 'route_request'):
                # It's a TaskRouter
                result = llm_client.route_request('topics', prompt)
                response_content = result['response']
            else:
                # It's a regular LLM client
                response = llm_client.invoke(prompt)
                response_content = response.content
            
            llm_topics = json.loads(response_content)
            
            for topic_data in llm_topics.get('topics', []):
                topic_name = topic_data['name'].lower()
                topic_scores[topic_name] += topic_data['confidence']
                topic_evidence[topic_name].append(f"LLM: {topic_data['reason'][:50]}")
                
        except Exception as e:
            print(f"LLM topic extraction failed: {e}")
    
    # 5. Normalize and rank topics
    topics = []
    for topic, score in topic_scores.items():
        # Skip very generic topics
        if topic in ['general', 'other', 'unknown']:
            continue
            
        normalized_score = min(score / max(topic_scores.values()) if topic_scores else 0, 1.0)
        
        topics.append({
            'name': topic,
            'score': normalized_score,
            'raw_score': score,
            'evidence': topic_evidence[topic][:3]  # Keep top 3 evidence items
        })
    
    # Sort by score and return top topics
    topics.sort(key=lambda x: x['score'], reverse=True)
    
    return topics[:7]  # Return top 7 topics

# ============================================================================
# SECTION 2.5: GRAPH ANALYSIS UTILITIES
# ============================================================================

def extract_weighted_co_occurrences(entities, segments, window_size=50):
    """
    Extract weighted co-occurrence relationships between entities based on proximity.
    
    Args:
        entities: List of entities with their positions in the transcript
        segments: List of transcript segments
        window_size: Word window for considering co-occurrence
        
    Returns:
        List of co-occurrence relationships with weights
    """
    co_occurrences = defaultdict(lambda: {'weight': 0, 'contexts': []})
    
    # Build a map of entity positions in the full transcript
    entity_positions = defaultdict(list)
    
    for segment in segments:
        segment_text = segment['text'].lower()
        words = segment_text.split()
        
        # Find all entity occurrences in this segment
        for idx, entity in enumerate(entities):
            entity_name = entity.get('name', '').strip().lower()
            if not entity_name:  # Skip empty entity names
                continue
            entity_words = entity_name.split()
            if not entity_words:  # Skip if no words after splitting
                continue
            
            # Use entity ID if available, otherwise generate one
            entity_id = entity.get('id', f"temp_entity_{idx}_{entity['name']}_{entity.get('type', 'unknown')}")
            
            # Find positions where entity appears
            for i in range(len(words) - len(entity_words) + 1):
                if words[i:i+len(entity_words)] == entity_words:
                    position = {
                        'segment_id': segment.get('id', segment.get('start', 0)),
                        'word_position': i,
                        'segment_text': segment_text,
                        'speaker': segment.get('speaker', 'Unknown')
                    }
                    entity_positions[entity_id].append(position)
    
    # Calculate co-occurrences with proximity weights
    entity_ids = list(entity_positions.keys())
    for i, entity1_id in enumerate(entity_ids):
        for entity2_id in entity_ids[i+1:]:
            
            # Check each occurrence pair
            for pos1 in entity_positions[entity1_id]:
                for pos2 in entity_positions[entity2_id]:
                    
                    # Same segment
                    if pos1['segment_id'] == pos2['segment_id']:
                        word_distance = abs(pos1['word_position'] - pos2['word_position'])
                        
                        if word_distance <= window_size:
                            # Calculate weight based on proximity
                            if word_distance <= 10:  # Same sentence (approximately)
                                weight = 10
                                proximity_type = 'sentence'
                            elif word_distance <= 30:  # Same paragraph (approximately)
                                weight = 5
                                proximity_type = 'paragraph'
                            else:  # Same segment
                                weight = 1
                                proximity_type = 'segment'
                            
                            key = tuple(sorted([entity1_id, entity2_id]))
                            co_occurrences[key]['weight'] += weight
                            co_occurrences[key]['contexts'].append({
                                'proximity_type': proximity_type,
                                'distance': word_distance,
                                'segment_id': pos1['segment_id'],
                                'speaker': pos1['speaker']
                            })
    
    # Convert to list format
    result = []
    for (entity1_id, entity2_id), data in co_occurrences.items():
        result.append({
            'entity1_id': entity1_id,
            'entity2_id': entity2_id,
            'weight': data['weight'],
            'occurrence_count': len(data['contexts']),
            'contexts': data['contexts'][:5]  # Keep top 5 contexts
        })
    
    return result

def calculate_betweenness_centrality(neo4j_session, episode_id):
    """
    Calculate betweenness centrality for all nodes in an episode to find bridge concepts.
    
    Args:
        neo4j_session: Neo4j session
        episode_id: Episode ID to analyze
        
    Returns:
        Dictionary of node IDs to centrality scores
    """
    if not nx:
        logger.warning("NetworkX not available. Skipping centrality calculation.")
        return {}
    
    try:
        # Build in-memory graph from Neo4j data
        G = nx.Graph()
        
        # Get all nodes and relationships for this episode
        result = neo4j_session.run("""
        MATCH (n)-[r]-(m)
        WHERE (n:Entity OR n:Insight) AND (m:Entity OR m:Insight)
        AND n.episode_id = $episode_id AND m.episode_id = $episode_id
        RETURN n.id as source, m.id as target, type(r) as rel_type, r.weight as weight
        """, episode_id=episode_id)
        
        # Add edges to graph
        for record in result:
            weight = record['weight'] if record['weight'] else 1
            G.add_edge(record['source'], record['target'], weight=weight)
        
        # Check if graph has nodes
        if len(G.nodes()) == 0:
            return {}
        
        # Calculate betweenness centrality
        centrality = nx.betweenness_centrality(G, weight='weight')
        
        return centrality
        
    except Exception as e:
        logger.error(f"Failed to calculate centrality: {e}")
        return {}

def detect_communities_multi_level(neo4j_session, episode_id, resolution_levels=[0.5, 1.0, 2.0]):
    """
    Detect communities at multiple resolution levels using Louvain algorithm.
    
    Args:
        neo4j_session: Neo4j session
        episode_id: Episode ID to analyze
        resolution_levels: List of resolution parameters for community detection
        
    Returns:
        Dictionary with community assignments at each level
    """
    if not nx or not community:
        logger.warning("NetworkX community detection not available.")
        return {}
    
    try:
        # Build graph
        G = nx.Graph()
        
        # Get nodes and relationships
        result = neo4j_session.run("""
        MATCH (n)-[r]-(m)
        WHERE (n:Entity OR n:Insight) AND (m:Entity OR m:Insight)
        AND n.episode_id = $episode_id AND m.episode_id = $episode_id
        RETURN n.id as source, m.id as target, n.name as source_name, m.name as target_name,
               type(r) as rel_type, r.weight as weight
        """, episode_id=episode_id)
        
        node_names = {}
        for record in result:
            weight = record['weight'] if record['weight'] else 1
            G.add_edge(record['source'], record['target'], weight=weight)
            node_names[record['source']] = record['source_name']
            node_names[record['target']] = record['target_name']
        
        # Check if graph has nodes
        if len(G.nodes()) == 0:
            return {}, {}
        
        # Detect communities at each resolution level
        community_results = {}
        for i, resolution in enumerate(resolution_levels):
            communities = community.louvain_communities(G, resolution=resolution, weight='weight')
            
            # Convert to node->community mapping
            node_communities = {}
            for comm_id, nodes in enumerate(communities):
                for node in nodes:
                    node_communities[node] = comm_id
            
            community_results[f'level_{i+1}'] = {
                'resolution': resolution,
                'communities': node_communities,
                'num_communities': len(communities)
            }
        
        return community_results, node_names
        
    except Exception as e:
        logger.error(f"Failed to detect communities: {e}")
        return {}, {}

def identify_peripheral_concepts(neo4j_session, episode_id):
    """
    Identify peripheral concepts that are mentioned but not deeply explored.
    
    Args:
        neo4j_session: Neo4j session
        episode_id: Episode ID to analyze
        
    Returns:
        List of peripheral concepts with exploration potential
    """
    try:
        # Find entities with low degree but appearing in multiple contexts
        result = neo4j_session.run("""
        MATCH (e:Entity {episode_id: $episode_id})
        OPTIONAL MATCH (e)-[r]-(other)
        WHERE other.episode_id = $episode_id
        WITH e, count(DISTINCT other) as degree, count(DISTINCT r) as rel_count
        WHERE degree < 3 AND degree > 0
        OPTIONAL MATCH (e)<-[:CONTAINS]-(s:Segment)
        WITH e, degree, rel_count, count(DISTINCT s) as segment_count
        WHERE segment_count >= 2
        RETURN e.id as id, e.name as name, e.type as type, 
               degree, segment_count,
               degree * 0.3 + segment_count * 0.7 as exploration_potential
        ORDER BY exploration_potential DESC
        LIMIT 20
        """, episode_id=episode_id)
        
        peripheral_concepts = []
        for record in result:
            peripheral_concepts.append({
                'id': record['id'],
                'name': record['name'],
                'type': record['type'],
                'degree': record['degree'],
                'segment_mentions': record['segment_count'],
                'exploration_potential': record['exploration_potential']
            })
        
        return peripheral_concepts
        
    except Exception as e:
        logger.error(f"Failed to identify peripheral concepts: {e}")
        return []

def calculate_discourse_structure(neo4j_session, episode_id, community_data):
    """
    Calculate discourse structure classification based on modularity and influence distribution.
    
    Args:
        neo4j_session: Neo4j session
        episode_id: Episode ID
        community_data: Community detection results
        
    Returns:
        Discourse structure classification and metrics
    """
    try:
        # Get influence distribution (based on degree centrality)
        result = neo4j_session.run("""
        MATCH (n {episode_id: $episode_id})
        WHERE n:Entity OR n:Insight
        OPTIONAL MATCH (n)-[r]-(m {episode_id: $episode_id})
        WHERE m:Entity OR m:Insight
        WITH n, count(DISTINCT m) as degree
        ORDER BY degree DESC
        LIMIT 20
        RETURN collect(degree) as degrees
        """, episode_id=episode_id)
        
        result_data = result.single()
        degrees = result_data['degrees'] if result_data else []
        
        # Calculate influence distribution entropy
        if degrees and entropy:
            total = sum(degrees)
            probabilities = [d/total for d in degrees]
            influence_entropy = entropy(probabilities)
        else:
            influence_entropy = 0
        
        # Get modularity from community data
        level_1_communities = community_data.get('level_1', {})
        num_communities = level_1_communities.get('num_communities', 1)
        
        # Calculate modularity proxy (simplified)
        if num_communities > 1:
            modularity_score = min(num_communities / 10, 0.8)  # Normalize to 0-0.8 range
        else:
            modularity_score = 0.1
        
        # Classify discourse structure
        if modularity_score < 0.4 and influence_entropy < 2.0:
            structure = 'biased'
            description = 'Single dominant topic'
        elif modularity_score < 0.65 and influence_entropy < 2.5:
            structure = 'focused'
            description = 'Few connected topics forming coherent clusters'
        elif modularity_score >= 0.65 and influence_entropy >= 2.5:
            structure = 'dispersed'
            description = 'Many unrelated ideas'
        else:
            structure = 'diversified'
            description = 'Multiple distinct but interconnected topic clusters'
        
        return {
            'structure': structure,
            'description': description,
            'modularity_score': modularity_score,
            'influence_entropy': influence_entropy,
            'num_communities': num_communities
        }
        
    except Exception as e:
        logger.error(f"Failed to calculate discourse structure: {e}")
        return {
            'structure': 'unknown',
            'description': 'Unable to determine discourse structure',
            'modularity_score': 0,
            'influence_entropy': 0,
            'num_communities': 0
        }

def calculate_diversity_metrics(neo4j_session, episode_id, community_data):
    """
    Calculate comprehensive diversity metrics for an episode.
    
    Args:
        neo4j_session: Neo4j session
        episode_id: Episode ID
        community_data: Community detection results
        
    Returns:
        Dictionary of diversity metrics
    """
    try:
        # Get basic statistics
        result = neo4j_session.run("""
        MATCH (n {episode_id: $episode_id})
        WHERE n:Entity OR n:Insight
        WITH count(DISTINCT n) as total_nodes
        MATCH (e:Entity {episode_id: $episode_id})
        WITH total_nodes, count(DISTINCT e) as entity_count
        MATCH (i:Insight {episode_id: $episode_id})
        WITH total_nodes, entity_count, count(DISTINCT i) as insight_count
        OPTIONAL MATCH (n {episode_id: $episode_id})-[r]-(m {episode_id: $episode_id})
        WHERE (n:Entity OR n:Insight) AND (m:Entity OR m:Insight)
        RETURN total_nodes, entity_count, insight_count, 
               count(r) as relationship_count
        """, episode_id=episode_id)
        
        stats = result.single()
        
        if not stats:
            return {
                'topic_diversity': 0,
                'connection_richness': 0,
                'concept_density': 0,
                'entity_count': 0,
                'insight_count': 0,
                'community_count': 0
            }
        
        # Calculate topic diversity
        num_communities = community_data.get('level_1', {}).get('num_communities', 1)
        topic_diversity = num_communities / max(stats['total_nodes'], 1)
        
        # Calculate connection richness
        connection_richness = stats['relationship_count'] / max(stats['total_nodes'], 1)
        
        # Get word count for concept density
        word_count_result = neo4j_session.run("""
        MATCH (s:Segment {episode_id: $episode_id})
        RETURN sum(s.word_count) as total_words
        """, episode_id=episode_id)
        
        word_result = word_count_result.single()
        total_words = (word_result['total_words'] if word_result and word_result['total_words'] else 1)
        concept_density = (stats['entity_count'] + stats['insight_count']) / (total_words / 1000)
        
        return {
            'topic_diversity': min(topic_diversity, 1.0),
            'connection_richness': connection_richness,
            'concept_density': concept_density,
            'entity_count': stats['entity_count'],
            'insight_count': stats['insight_count'],
            'community_count': num_communities
        }
        
    except Exception as e:
        logger.error(f"Failed to calculate diversity metrics: {e}")
        return {
            'topic_diversity': 0,
            'connection_richness': 0,
            'concept_density': 0,
            'entity_count': 0,
            'insight_count': 0,
            'community_count': 0
        }

def identify_structural_gaps(neo4j_session, episode_id, community_data):
    """
    Identify structural gaps between topic clusters that could be bridged.
    
    Args:
        neo4j_session: Neo4j session
        episode_id: Episode ID
        community_data: Community detection results with node names
        
    Returns:
        List of structural gaps with potential bridges
    """
    try:
        gaps = []
        
        if not community_data or (isinstance(community_data, tuple) and len(community_data) != 2):
            return gaps
            
        communities, node_names = community_data
        
        if not communities:
            return gaps
            
        level_1 = communities.get('level_1', {}).get('communities', {})
        
        # Get community pairs with few connections
        result = neo4j_session.run("""
        MATCH (n {episode_id: $episode_id})-[r]-(m {episode_id: $episode_id})
        WHERE (n:Entity OR n:Insight) AND (m:Entity OR m:Insight)
        RETURN n.id as source, m.id as target
        """, episode_id=episode_id)
        
        # Count connections between communities
        community_connections = defaultdict(int)
        for record in result:
            source_comm = level_1.get(record['source'])
            target_comm = level_1.get(record['target'])
            
            if source_comm is not None and target_comm is not None and source_comm != target_comm:
                key = tuple(sorted([source_comm, target_comm]))
                community_connections[key] += 1
        
        # Find community pairs with few connections
        all_communities = set(level_1.values())
        for comm1, comm2 in combinations(all_communities, 2):
            key = tuple(sorted([comm1, comm2]))
            connection_count = community_connections.get(key, 0)
            
            if connection_count < 3:  # Few connections indicate a gap
                # Find nodes that could bridge these communities
                nodes_comm1 = [n for n, c in level_1.items() if c == comm1]
                nodes_comm2 = [n for n, c in level_1.items() if c == comm2]
                
                # Get representative nodes from each community
                repr_nodes_1 = nodes_comm1[:3]
                repr_nodes_2 = nodes_comm2[:3]
                
                gap = {
                    'community_1': comm1,
                    'community_2': comm2,
                    'connection_count': connection_count,
                    'representative_concepts_1': [node_names.get(n, n) for n in repr_nodes_1],
                    'representative_concepts_2': [node_names.get(n, n) for n in repr_nodes_2],
                    'gap_score': 1 - (connection_count / 3)  # Higher score = bigger gap
                }
                
                gaps.append(gap)
        
        # Sort by gap score
        gaps.sort(key=lambda x: x['gap_score'], reverse=True)
        
        return gaps[:10]  # Return top 10 gaps
        
    except Exception as e:
        logger.error(f"Failed to identify structural gaps: {e}")
        return []

def create_hierarchical_topics(neo4j_session, episode_id, community_data, llm_client=None):
    """
    Create hierarchical topic structure based on multi-level community detection.
    
    Args:
        neo4j_session: Neo4j session
        episode_id: Episode ID
        community_data: Multi-level community detection results
        llm_client: Optional LLM client for generating topic names
        
    Returns:
        Created topic hierarchy
    """
    try:
        topics_created = []
        
        if not community_data or (isinstance(community_data, tuple) and len(community_data) != 2):
            return topics_created
            
        communities, node_names = community_data
        
        if not communities:
            return topics_created
        
        # Process each level
        for level_name in ['level_1', 'level_2', 'level_3']:
            level_data = communities.get(level_name, {})
            level_communities = level_data.get('communities', {})
            
            if not level_communities:
                continue
            
            # Group nodes by community
            community_nodes = defaultdict(list)
            for node_id, comm_id in level_communities.items():
                if node_id in node_names:
                    community_nodes[comm_id].append({
                        'id': node_id,
                        'name': node_names[node_id]
                    })
            
            # Create topic for each community
            for comm_id, nodes in community_nodes.items():
                # Get top concepts for naming
                top_concepts = [n['name'] for n in nodes[:5]]
                
                # Generate topic name
                if llm_client and len(top_concepts) >= 2:
                    try:
                        prompt = f"""
                        Create a concise topic name (2-3 words) for these related concepts:
                        {', '.join(top_concepts)}
                        
                        Return only the topic name, nothing else.
                        """
                        
                        if hasattr(llm_client, 'invoke'):
                            response = llm_client.invoke(prompt)
                            topic_name = response.content.strip()
                        else:
                            topic_name = f"{top_concepts[0]} & Related"
                    except:
                        topic_name = f"{top_concepts[0]} & Related"
                else:
                    topic_name = top_concepts[0] if top_concepts else f"Topic {comm_id}"
                
                # Create topic in Neo4j
                topic_id = f"{episode_id}-{level_name}-{comm_id}"
                
                neo4j_session.run("""
                MERGE (t:Topic {id: $topic_id})
                SET t.name = $name,
                    t.episode_id = $episode_id,
                    t.hierarchy_level = $level,
                    t.community_id = $comm_id,
                    t.member_count = $member_count,
                    t.top_concepts = $top_concepts
                """, {
                    'topic_id': topic_id,
                    'name': topic_name,
                    'episode_id': episode_id,
                    'level': level_name,
                    'comm_id': comm_id,
                    'member_count': len(nodes),
                    'top_concepts': top_concepts
                })
                
                # Link nodes to topic
                for node in nodes:
                    neo4j_session.run("""
                    MATCH (n {id: $node_id, episode_id: $episode_id})
                    WHERE n:Entity OR n:Insight
                    MATCH (t:Topic {id: $topic_id})
                    MERGE (n)-[:BELONGS_TO_TOPIC]->(t)
                    """, {
                        'node_id': node['id'],
                        'episode_id': episode_id,
                        'topic_id': topic_id
                    })
                
                topics_created.append({
                    'id': topic_id,
                    'name': topic_name,
                    'level': level_name,
                    'member_count': len(nodes)
                })
        
        # Create hierarchy relationships between topics
        if len(topics_created) > 1:
            # Link topics from different levels
            neo4j_session.run("""
            MATCH (t1:Topic {episode_id: $episode_id, hierarchy_level: 'level_1'})
            MATCH (t2:Topic {episode_id: $episode_id, hierarchy_level: 'level_2'})
            WHERE EXISTS {
                MATCH (t1)<-[:BELONGS_TO_TOPIC]-(n)-[:BELONGS_TO_TOPIC]->(t2)
            }
            MERGE (t1)-[:CONTAINS_TOPIC]->(t2)
            """, episode_id=episode_id)
            
            neo4j_session.run("""
            MATCH (t2:Topic {episode_id: $episode_id, hierarchy_level: 'level_2'})
            MATCH (t3:Topic {episode_id: $episode_id, hierarchy_level: 'level_3'})
            WHERE EXISTS {
                MATCH (t2)<-[:BELONGS_TO_TOPIC]-(n)-[:BELONGS_TO_TOPIC]->(t3)
            }
            MERGE (t2)-[:CONTAINS_TOPIC]->(t3)
            """, episode_id=episode_id)
        
        return topics_created
        
    except Exception as e:
        logger.error(f"Failed to create hierarchical topics: {e}")
        return []

def identify_bridge_insights(neo4j_session, episode_id, community_data):
    """
    Identify insights that bridge multiple topic communities.
    
    Args:
        neo4j_session: Neo4j session
        episode_id: Episode ID
        community_data: Community detection results
        
    Returns:
        List of bridge insights
    """
    try:
        if not community_data or (isinstance(community_data, tuple) and not community_data[0]):
            return []
            
        communities, _ = community_data
        if not communities:
            return []
            
        level_1 = communities.get('level_1', {}).get('communities', {})
        
        # Find insights connected to entities in different communities
        result = neo4j_session.run("""
        MATCH (i:Insight {episode_id: $episode_id})-[:REFERENCES]-(e:Entity {episode_id: $episode_id})
        WITH i, collect(DISTINCT e.id) as entity_ids
        WHERE size(entity_ids) >= 2
        RETURN i.id as id, i.content as content, i.key_insight as key_insight,
               entity_ids
        """, episode_id=episode_id)
        
        bridge_insights = []
        for record in result:
            # Check which communities these entities belong to
            communities_touched = set()
            for entity_id in record['entity_ids']:
                comm = level_1.get(entity_id)
                if comm is not None:
                    communities_touched.add(comm)
            
            if len(communities_touched) >= 2:
                bridge_insights.append({
                    'id': record['id'],
                    'content': record['content'],
                    'key_insight': record['key_insight'],
                    'communities_bridged': len(communities_touched),
                    'bridge_score': len(communities_touched) / max(len(record['entity_ids']), 1)
                })
        
        # Sort by bridge score
        bridge_insights.sort(key=lambda x: x['bridge_score'], reverse=True)
        
        # Update insights in Neo4j
        for insight in bridge_insights[:20]:  # Top 20 bridge insights
            neo4j_session.run("""
            MATCH (i:Insight {id: $id})
            SET i.is_bridge_insight = true,
                i.bridge_score = $bridge_score,
                i.communities_bridged = $communities_bridged
            """, {
                'id': insight['id'],
                'bridge_score': insight['bridge_score'],
                'communities_bridged': insight['communities_bridged']
            })
        
        return bridge_insights
        
    except Exception as e:
        logger.error(f"Failed to identify bridge insights: {e}")
        return []

def analyze_episode_discourse(neo4j_driver, episode_id, insights, entities, 
                            transcript_segments, llm_client=None):
    """
    Perform comprehensive discourse analysis on an episode after knowledge extraction.
    
    Args:
        neo4j_driver: Neo4j driver
        episode_id: Episode ID
        insights: List of insights
        entities: List of entities
        transcript_segments: List of transcript segments
        llm_client: Optional LLM client
        
    Returns:
        Dictionary of discourse analysis results
    """
    try:
        database = PodcastConfig.NEO4J_DATABASE
        
        with neo4j_driver.session(database=database) as session:
            
            # Step 1: Calculate betweenness centrality
            logger.info("Calculating betweenness centrality...")
            centrality_scores = calculate_betweenness_centrality(session, episode_id)
            
            # Update nodes with centrality scores
            for node_id, score in centrality_scores.items():
                session.run("""
                MATCH (n {id: $node_id, episode_id: $episode_id})
                WHERE n:Entity OR n:Insight
                SET n.bridge_score = $score
                """, node_id=node_id, episode_id=episode_id, score=score)
            
            # Step 2: Multi-level community detection
            logger.info("Detecting communities at multiple levels...")
            community_results, node_names = detect_communities_multi_level(session, episode_id)
            
            # Step 3: Create hierarchical topics
            logger.info("Creating hierarchical topic structure...")
            topics_created = create_hierarchical_topics(session, episode_id, (community_results, node_names), llm_client)
            
            # Step 4: Identify peripheral concepts
            logger.info("Identifying peripheral concepts...")
            peripheral_concepts = identify_peripheral_concepts(session, episode_id)
            
            # Mark peripheral concepts in Neo4j
            for concept in peripheral_concepts:
                session.run("""
                MATCH (e:Entity {id: $id, episode_id: $episode_id})
                SET e.is_peripheral = true,
                    e.exploration_potential = $potential
                """, id=concept['id'], episode_id=episode_id, 
                    potential=concept['exploration_potential'])
            
            # Step 5: Calculate discourse structure
            logger.info("Analyzing discourse structure...")
            discourse_structure = calculate_discourse_structure(session, episode_id, community_results)
            
            # Step 6: Calculate diversity metrics
            logger.info("Calculating diversity metrics...")
            diversity_metrics = calculate_diversity_metrics(session, episode_id, community_results)
            
            # Step 7: Identify structural gaps
            logger.info("Identifying structural gaps...")
            structural_gaps = identify_structural_gaps(session, episode_id, (community_results, node_names))
            
            # Create PotentialConnection nodes for gaps
            for gap in structural_gaps[:5]:  # Top 5 gaps
                gap_id = f"{episode_id}-gap-{gap['community_1']}-{gap['community_2']}"
                session.run("""
                CREATE (g:PotentialConnection {
                    id: $id,
                    episode_id: $episode_id,
                    community_1: $comm1,
                    community_2: $comm2,
                    connection_count: $count,
                    gap_score: $score,
                    concepts_1: $concepts1,
                    concepts_2: $concepts2
                })
                """, {
                    'id': gap_id,
                    'episode_id': episode_id,
                    'comm1': gap['community_1'],
                    'comm2': gap['community_2'],
                    'count': gap['connection_count'],
                    'score': gap['gap_score'],
                    'concepts1': gap['representative_concepts_1'],
                    'concepts2': gap['representative_concepts_2']
                })
            
            # Step 8: Identify bridge insights
            logger.info("Identifying bridge insights...")
            bridge_insights = identify_bridge_insights(session, episode_id, (community_results, node_names))
            
            # Update episode with discourse metrics
            session.run("""
            MATCH (e:Episode {id: $episode_id})
            SET e.discourse_structure = $structure,
                e.discourse_description = $description,
                e.modularity_score = $modularity,
                e.influence_entropy = $entropy,
                e.topic_diversity = $topic_diversity,
                e.connection_richness = $connection_richness,
                e.concept_density = $concept_density,
                e.num_communities = $num_communities,
                e.num_peripheral_concepts = $num_peripheral,
                e.num_structural_gaps = $num_gaps,
                e.num_bridge_insights = $num_bridges
            """, {
                'episode_id': episode_id,
                'structure': discourse_structure['structure'],
                'description': discourse_structure['description'],
                'modularity': discourse_structure['modularity_score'],
                'entropy': discourse_structure['influence_entropy'],
                'topic_diversity': diversity_metrics['topic_diversity'],
                'connection_richness': diversity_metrics['connection_richness'],
                'concept_density': diversity_metrics['concept_density'],
                'num_communities': diversity_metrics['community_count'],
                'num_peripheral': len(peripheral_concepts),
                'num_gaps': len(structural_gaps),
                'num_bridges': len(bridge_insights)
            })
            
            return {
                'discourse_structure': discourse_structure,
                'diversity_metrics': diversity_metrics,
                'topics_created': len(topics_created),
                'peripheral_concepts': len(peripheral_concepts),
                'structural_gaps': len(structural_gaps),
                'bridge_insights': len(bridge_insights),
                'nodes_with_centrality': len(centrality_scores)
            }
            
    except Exception as e:
        logger.error(f"Failed to analyze episode discourse: {e}")
        return {
            'discourse_structure': {'structure': 'unknown'},
            'diversity_metrics': {},
            'topics_created': 0,
            'peripheral_concepts': 0,
            'structural_gaps': 0,
            'bridge_insights': 0,
            'nodes_with_centrality': 0
        }

# ============================================================================
# SECTION 3: DATABASE OPERATIONS
# ============================================================================

# ============================================================================
# SECTION 3.1: NEO4J CONNECTION AND SCHEMA SETUP
# ============================================================================

def connect_to_neo4j(config=None):
    """
    Connect to Neo4j database using configuration.
    
    Args:
        config: Configuration class or instance (defaults to PodcastConfig)
        
    Returns:
        Neo4j driver
        
    Raises:
        DatabaseConnectionError: If connection fails
    """
    config = config or PodcastConfig
    
    if not config.NEO4J_PASSWORD:
        raise ConfigurationError("NEO4J_PASSWORD not found in environment variables.")
        
    try:
        driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
        )
        
        # Verify connection
        with driver.session(database=config.NEO4J_DATABASE) as session:
            result = session.run("RETURN 'Connection Successful' AS result")
            message = result.single()["result"]
            print(f"Neo4j connection: {message}")
            
        return driver
        
    except Exception as e:
        raise DatabaseConnectionError(f"Failed to connect to Neo4j: {e}")
        
def setup_neo4j_schema(neo4j_driver):
    """
    Set up Neo4j schema with constraints and indexes.
    
    Args:
        neo4j_driver: Neo4j driver
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot set up schema.")
        return
        
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        with neo4j_driver.session(database=database) as session:
            # Create constraints for node uniqueness
            session.run("CREATE CONSTRAINT podcast_id IF NOT EXISTS FOR (p:Podcast) REQUIRE p.id IS UNIQUE")
            session.run("CREATE CONSTRAINT episode_id IF NOT EXISTS FOR (e:Episode) REQUIRE e.id IS UNIQUE")
            session.run("CREATE CONSTRAINT segment_id IF NOT EXISTS FOR (s:Segment) REQUIRE s.id IS UNIQUE")
            session.run("CREATE CONSTRAINT insight_id IF NOT EXISTS FOR (i:Insight) REQUIRE i.id IS UNIQUE")
            session.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE")
            session.run("CREATE CONSTRAINT quote_id IF NOT EXISTS FOR (q:Quote) REQUIRE q.id IS UNIQUE")
            session.run("CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE")
            session.run("CREATE CONSTRAINT potential_connection_id IF NOT EXISTS FOR (p:PotentialConnection) REQUIRE p.id IS UNIQUE")
            
            # Create indexes for common lookups
            session.run("CREATE INDEX podcast_name IF NOT EXISTS FOR (p:Podcast) ON (p.name)")
            session.run("CREATE INDEX episode_title IF NOT EXISTS FOR (e:Episode) ON (e.title)")
            session.run("CREATE INDEX segment_text IF NOT EXISTS FOR (s:Segment) ON (s.text)")
            session.run("CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)")
            session.run("CREATE INDEX insight_type IF NOT EXISTS FOR (i:Insight) ON (i.insight_type)")
            session.run("CREATE INDEX quote_type IF NOT EXISTS FOR (q:Quote) ON (q.quote_type)")
            session.run("CREATE INDEX quote_speaker IF NOT EXISTS FOR (q:Quote) ON (q.speaker)")
            session.run("CREATE INDEX topic_name IF NOT EXISTS FOR (t:Topic) ON (t.name)")
            session.run("CREATE INDEX topic_trend IF NOT EXISTS FOR (t:Topic) ON (t.trend)")
            
            # Create indexes for discourse analysis features
            session.run("CREATE INDEX entity_bridge_score IF NOT EXISTS FOR (e:Entity) ON (e.bridge_score)")
            session.run("CREATE INDEX entity_peripheral IF NOT EXISTS FOR (e:Entity) ON (e.is_peripheral)")
            session.run("CREATE INDEX insight_bridge IF NOT EXISTS FOR (i:Insight) ON (i.is_bridge_insight)")
            session.run("CREATE INDEX episode_discourse IF NOT EXISTS FOR (e:Episode) ON (e.discourse_structure)")
            session.run("CREATE INDEX topic_hierarchy IF NOT EXISTS FOR (t:Topic) ON (t.hierarchy_level)")
            session.run("CREATE INDEX potential_connection_id IF NOT EXISTS FOR (p:PotentialConnection) ON (p.id)")
            
            # Create full-text search indexes
            session.run("""
            CREATE FULLTEXT INDEX segment_fulltext IF NOT EXISTS 
            FOR (s:Segment) ON EACH [s.text]
            """)
            
            session.run("""
            CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS 
            FOR (e:Entity) ON EACH [e.name, e.description]
            """)
            
            session.run("""
            CREATE FULLTEXT INDEX quote_fulltext IF NOT EXISTS 
            FOR (q:Quote) ON EACH [q.text]
            """)
            
            session.run("""
            CREATE FULLTEXT INDEX topic_fulltext IF NOT EXISTS 
            FOR (t:Topic) ON EACH [t.name]
            """)
            
            # Create vector index for embeddings (if Neo4j version supports it)
            try:
                session.run("""
                CREATE VECTOR INDEX segment_embedding IF NOT EXISTS 
                FOR (s:Segment) ON (s.embedding)
                OPTIONS {
                  indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                  }
                }
                """)
                
                session.run("""
                CREATE VECTOR INDEX insight_embedding IF NOT EXISTS 
                FOR (i:Insight) ON (i.embedding)
                OPTIONS {
                  indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                  }
                }
                """)
                
                print("Successfully created vector indexes for embeddings")
                
            except Exception as vector_error:
                print(f"Note: Vector indexes not created - this may be expected if using Neo4j < 5.7: {vector_error}")
                
            print("Successfully set up Neo4j schema with constraints and indexes")
            
    except DatabaseConnectionError:
        raise
    except Exception as e:
        raise DatabaseConnectionError(f"Failed to set up Neo4j schema: {e}")

# ============================================================================
# SECTION 4: AUDIO PROCESSING
# ============================================================================

class AudioProcessor:
    """Handles all audio processing operations including transcription and diarization."""
    
    def __init__(self, config=None):
        """Initialize audio processor with configuration."""
        self.config = config or PodcastConfig
        self.enable_processing = ENABLE_AUDIO_PROCESSING
        self.enable_diarization = ENABLE_SPEAKER_DIARIZATION
        
    def transcribe_audio(self, audio_path, use_faster_whisper=True, whisper_model_size="large-v3"):
        """Transcribe audio using Whisper."""
        if not self.enable_processing:
            print("Audio processing disabled. Returning empty transcript.")
            return []
            
        return transcribe_audio(audio_path, use_faster_whisper, whisper_model_size)
        
    def diarize_speakers(self, audio_path, min_speakers=1, max_speakers=10):
        """Perform speaker diarization on audio."""
        if not self.enable_diarization:
            print("Speaker diarization disabled. Returning empty speaker map.")
            return {}
            
        return diarize_speakers(audio_path, min_speakers, max_speakers)
        
    def align_transcript_with_diarization(self, transcript_segments, speaker_map):
        """Align transcript segments with speaker diarization results."""
        return align_transcript_with_diarization(transcript_segments, speaker_map)

# Legacy class name for compatibility
class EnhancedPodcastSegmenter:
    """Enhanced podcast segmenter with advanced features."""
    
    def __init__(self, config=None):
        """
        Initialize podcast segmenter with configuration.
        
        Args:
            config: Configuration dictionary with parameters
        """
        # Default configuration
        default_config = {
            'min_segment_tokens': 150,
            'max_segment_tokens': 800,
            'use_gpu': True,
            'ad_detection_enabled': True,
            'use_semantic_boundaries': True,
            'min_speakers': 1,
            'max_speakers': 10
        }
        
        # Update with provided config
        self.config = default_config.copy()
        if config:
            self.config.update(config)
            
        print(f"Initialized EnhancedPodcastSegmenter with config: {self.config}")
            
    def process_audio(self, audio_path):
        """
        Process audio file through transcription and diarization.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Dictionary with processing results
        """
        # Transcribe audio
        print(f"Transcribing audio: {audio_path}")
        transcript_segments = transcribe_audio(
            audio_path, 
            use_faster_whisper=True, 
            whisper_model_size="large-v3"
        )
        
        if not transcript_segments:
            logger.error("Transcription failed. Unable to process audio.")
            return {"transcript": [], "diarization": {}}
        
        # Perform speaker diarization
        print("Performing speaker diarization...")
        speaker_map = diarize_speakers(
            audio_path,
            min_speakers=self.config['min_speakers'],
            max_speakers=self.config['max_speakers']
        )
        
        # Align transcript with diarization
        if speaker_map:
            print("Aligning transcript with speaker diarization...")
            transcript_segments = align_transcript_with_diarization(
                transcript_segments, 
                speaker_map
            )
            
        # Post-process segments
        print("Post-processing segments...")
        transcript_segments = self._post_process_segments(transcript_segments)
        
        return {
            "transcript": transcript_segments,
            "diarization": speaker_map
        }
        
    def _post_process_segments(self, segments):
        """
        Post-process segments for better quality.
        
        Args:
            segments: List of transcript segments
            
        Returns:
            Processed segments
        """
        processed_segments = []
        
        # Process each segment
        for i, segment in enumerate(segments):
            # Skip empty segments
            if not segment.get('text', '').strip():
                continue
                
            # Detect advertisements
            is_ad = self._detect_advertisement(segment)
            segment['is_advertisement'] = is_ad
            
            # Add segment sentiment
            segment['sentiment'] = self._analyze_segment_sentiment(segment['text'])
            
            # Add segment index
            segment['segment_index'] = i
            
            processed_segments.append(segment)
            
        return processed_segments
        
    def _detect_advertisement(self, segment):
        """
        Detect if a segment is an advertisement.
        
        Args:
            segment: Transcript segment
            
        Returns:
            Boolean indicating if segment is an advertisement
        """
        if not self.config['ad_detection_enabled']:
            return False
            
        # Check for common ad markers
        text = segment['text'].lower()
        ad_markers = [
            "sponsor", "sponsored by", "brought to you by", "discount code",
            "promo code", "offer code", "special offer", "limited time offer"
        ]
        
        for marker in ad_markers:
            if marker in text:
                return True
                
        return False
        
    def _analyze_segment_sentiment(self, text):
        """
        Analyze segment sentiment (basic implementation).
        
        Args:
            text: Segment text
            
        Returns:
            Dictionary with sentiment analysis results
        """
        # Simple lexicon-based sentiment analysis
        positive_words = ["good", "great", "excellent", "amazing", "love", "best", "positive",
                         "happy", "excited", "wonderful", "fantastic", "superior", "beneficial"]
        negative_words = ["bad", "terrible", "awful", "hate", "worst", "negative", "poor",
                         "horrible", "failure", "inadequate", "disappointing", "problem"]
        
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        
        # Count sentiment words
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        # Calculate sentiment score (-1 to 1)
        total = positive_count + negative_count
        if total == 0:
            score = 0  # neutral
        else:
            score = (positive_count - negative_count) / total
            
        # Determine polarity
        if score > 0.2:
            polarity = "positive"
        elif score < -0.2:
            polarity = "negative"
        else:
            polarity = "neutral"
            
        return {
            "score": score,
            "polarity": polarity,
            "positive_count": positive_count,
            "negative_count": negative_count
        }
        
    # Visualization removed for batch seeding mode
    # Use ENABLE_VISUALIZATION = True to restore this functionality

# ============================================================================
# SECTION 3.2: ENHANCED KNOWLEDGE GRAPH OPERATIONS
# ============================================================================

class GraphOperations:
    """Handles all Neo4j graph operations."""
    
    def __init__(self, neo4j_driver):
        """Initialize with Neo4j driver."""
        self.driver = neo4j_driver
        self.database = os.environ.get("NEO4J_DATABASE", "neo4j")
        self.enable_enhancements = ENABLE_GRAPH_ENHANCEMENTS
        
    def add_sentiment_to_knowledge_graph(self, episode_id):
        """Add sentiment information to knowledge graph."""
        if not self.enable_enhancements:
            print("Graph enhancements disabled. Skipping sentiment addition.")
            return
            
        return add_sentiment_to_knowledge_graph(self.driver, episode_id)
        
    def enhance_speaker_information(self, episode_id):
        """Enhance speaker information in the knowledge graph."""
        if not self.enable_enhancements:
            print("Graph enhancements disabled. Skipping speaker enhancement.")
            return
            
        return enhance_speaker_information(self.driver, episode_id)
        
    def improve_embeddings(self, episode_id, embedding_client):
        """Improve embeddings for knowledge graph nodes."""
        if not self.enable_enhancements:
            print("Graph enhancements disabled. Skipping embedding improvement.")
            return
            
        return improve_embeddings(self.driver, episode_id, embedding_client)
        
    def enrich_metadata(self, episode_id):
        """Enrich metadata for knowledge graph nodes."""
        if not self.enable_enhancements:
            print("Graph enhancements disabled. Skipping metadata enrichment.")
            return
            
        return enrich_metadata(self.driver, episode_id)
        
    def establish_entity_relationships(self, episode_id):
        """Establish entity-to-entity relationships in the knowledge graph."""
        if not self.enable_enhancements:
            print("Graph enhancements disabled. Skipping entity relationships.")
            return
            
        return establish_entity_relationships(self.driver, episode_id)

# Legacy function for compatibility
def add_sentiment_to_knowledge_graph(neo4j_driver, episode_id):
    """
    Add sentiment information to knowledge graph.
    
    Args:
        neo4j_driver: Neo4j driver
        episode_id: Episode ID
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot add sentiment.")
        return
        
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        with neo4j_driver.session(database=database) as session:
            # Aggregate sentiment by entity
            session.run("""
            MATCH (ep:Episode {id: $episode_id})-[:HAS_SEGMENT]->(s:Segment)
            WHERE s.sentiment IS NOT NULL
            MATCH (e:Entity)-[:MENTIONED_IN]->(ep)
            WITH e, ep, 
                 collect(s) as segments,
                 avg(s.sentiment.score) as avg_sentiment
            WHERE size(segments) > 0
            MERGE (e)-[r:HAS_SENTIMENT]->(ep)
            SET r.score = avg_sentiment,
                r.polarity = CASE
                    WHEN avg_sentiment > 0.2 THEN 'positive'
                    WHEN avg_sentiment < -0.2 THEN 'negative'
                    ELSE 'neutral'
                END
            """, {"episode_id": episode_id})
            
            # Create episode sentiment evolution
            session.run("""
            MATCH (ep:Episode {id: $episode_id})-[:HAS_SEGMENT]->(s:Segment)
            WHERE s.sentiment IS NOT NULL
            WITH ep, s
            ORDER BY s.start_time
            WITH ep, collect({
                time: s.start_time,
                score: s.sentiment.score,
                polarity: s.sentiment.polarity
            }) as sentiment_points
            SET ep.sentiment_evolution = sentiment_points
            """, {"episode_id": episode_id})
            
            print(f"Added sentiment information for episode {episode_id}")
            
    except Exception as e:
        print(f"Error adding sentiment to knowledge graph: {e}")

def enhance_speaker_information(neo4j_driver, episode_id):
    """
    Enhance speaker information in the knowledge graph.
    
    Args:
        neo4j_driver: Neo4j driver
        episode_id: Episode ID
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot enhance speaker information.")
        return
        
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        with neo4j_driver.session(database=database) as session:
            # Create Speaker nodes
            session.run("""
            MATCH (ep:Episode {id: $episode_id})-[:HAS_SEGMENT]->(s:Segment)
            WHERE s.speaker IS NOT NULL
            WITH ep, collect(DISTINCT s.speaker) as speakers
            UNWIND speakers as speaker_name
            MERGE (sp:Speaker {name: speaker_name})
            ON CREATE SET 
                sp.created_timestamp = datetime(),
                sp.id = 'speaker_' + apoc.text.md5(speaker_name)
            WITH ep, sp
            MERGE (sp)-[:SPEAKS_IN]->(ep)
            """, {"episode_id": episode_id})
            
            # Link speakers to segments
            session.run("""
            MATCH (ep:Episode {id: $episode_id})-[:HAS_SEGMENT]->(s:Segment)
            WHERE s.speaker IS NOT NULL
            MATCH (sp:Speaker {name: s.speaker})
            MERGE (sp)-[:SPEAKS]->(s)
            """, {"episode_id": episode_id})
            
            # Track speaker-entity relationships
            session.run("""
            MATCH (sp:Speaker)-[:SPEAKS]->(s:Segment)
            MATCH (e:Entity)
            WHERE toLower(s.text) CONTAINS toLower(e.name)
            MERGE (sp)-[r:DISCUSSES]->(e)
            ON CREATE SET r.count = 1
            ON MATCH SET r.count = r.count + 1
            """)
            
            # Classify speakers as hosts or guests
            session.run("""
            MATCH (p:Podcast)-[:HAS_EPISODE]->(ep:Episode {id: $episode_id})
            MATCH (sp:Speaker)-[:SPEAKS_IN]->(ep)
            // Host logic: either matches known host names or appears in many episodes
            WITH p, sp, count(DISTINCT ep) as episode_count,
                 p.hosts as podcast_hosts
            SET sp.role = CASE
                WHEN any(host IN podcast_hosts WHERE toLower(host) CONTAINS toLower(sp.name) 
                          OR toLower(sp.name) CONTAINS toLower(host)) 
                    THEN 'host'
                WHEN episode_count > 1 
                    THEN 'recurring' 
                ELSE 'guest'
            END
            """, {"episode_id": episode_id})
            
            print(f"Enhanced speaker information for episode {episode_id}")
            
    except Exception as e:
        print(f"Error enhancing speaker information: {e}")

def improve_embeddings(neo4j_driver, episode_id, embedding_client):
    """
    Improve embeddings for knowledge graph nodes.
    
    Args:
        neo4j_driver: Neo4j driver
        episode_id: Episode ID
        embedding_client: OpenAI client for embeddings
    """
    if not neo4j_driver or not embedding_client:
        print("Neo4j driver or embedding client not available. Cannot improve embeddings.")
        return
        
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        with neo4j_driver.session(database=database) as session:
            # Get segments without embeddings
            result = session.run("""
            MATCH (ep:Episode {id: $episode_id})-[:HAS_SEGMENT]->(s:Segment)
            WHERE s.embedding IS NULL
            RETURN s.id as id, s.text as text
            """, {"episode_id": episode_id})
            
            for record in result:
                segment_id = record["id"]
                text = record["text"]
                
                # Generate embedding
                embedding = generate_embeddings(text, embedding_client)
                
                if embedding:
                    # Update segment with embedding
                    session.run("""
                    MATCH (s:Segment {id: $segment_id})
                    SET s.embedding = $embedding,
                        s.embedding_model = 'text-embedding-3-small'
                    """, {"segment_id": segment_id, "embedding": embedding})
            
            # Get insights without embeddings
            result = session.run("""
            MATCH (ep:Episode {id: $episode_id})-[:HAS_INSIGHT]->(i:Insight)
            WHERE i.embedding IS NULL
            RETURN i.id as id, i.title as title, i.description as description
            """, {"episode_id": episode_id})
            
            for record in result:
                insight_id = record["id"]
                text = f"{record['title']} {record['description']}"
                
                # Generate embedding
                embedding = generate_embeddings(text, embedding_client)
                
                if embedding:
                    # Update insight with embedding
                    session.run("""
                    MATCH (i:Insight {id: $insight_id})
                    SET i.embedding = $embedding,
                        i.embedding_model = 'text-embedding-3-small'
                    """, {"insight_id": insight_id, "embedding": embedding})
            
            # Get entities without embeddings
            result = session.run("""
            MATCH (e:Entity)-[:MENTIONED_IN]->(ep:Episode {id: $episode_id})
            WHERE e.embedding IS NULL
            RETURN e.id as id, e.name as name, e.description as description
            """, {"episode_id": episode_id})
            
            for record in result:
                entity_id = record["id"]
                text = f"{record['name']} {record['description']}"
                
                # Generate embedding
                embedding = generate_embeddings(text, embedding_client)
                
                if embedding:
                    # Update entity with embedding
                    session.run("""
                    MATCH (e:Entity {id: $entity_id})
                    SET e.embedding = $embedding,
                        e.embedding_model = 'text-embedding-3-small'
                    """, {"entity_id": entity_id, "embedding": embedding})
            
            print(f"Improved embeddings for episode {episode_id}")
            
    except Exception as e:
        print(f"Error improving embeddings: {e}")

def enrich_metadata(neo4j_driver, episode_id):
    """
    Enrich metadata for knowledge graph nodes.
    
    Args:
        neo4j_driver: Neo4j driver
        episode_id: Episode ID
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot enrich metadata.")
        return
        
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        with neo4j_driver.session(database=database) as session:
            # Add segment timestamps in readable format
            session.run("""
            MATCH (ep:Episode {id: $episode_id})-[:HAS_SEGMENT]->(s:Segment)
            SET s.formatted_start_time = apoc.temporal.format(duration.inSeconds(s.start_time).seconds, 'HH:mm:ss'),
                s.formatted_end_time = apoc.temporal.format(duration.inSeconds(s.end_time).seconds, 'HH:mm:ss')
            """, {"episode_id": episode_id})
            
            # Set entity confidence scores
            session.run("""
            MATCH (e:Entity)-[:MENTIONED_IN]->(ep:Episode {id: $episode_id})
            SET e.confidence = CASE
                WHEN e.frequency IS NOT NULL AND e.frequency > 5 THEN 0.9
                WHEN e.frequency IS NOT NULL AND e.frequency > 2 THEN 0.8
                ELSE 0.7
            END
            """, {"episode_id": episode_id})
            
            # Skip domain-specific categorization for schema-less approach
            
            # Add publication date as proper datetime
            session.run("""
            MATCH (ep:Episode {id: $episode_id})
            WHERE ep.published_date IS NOT NULL
            SET ep.published_datetime = datetime(ep.published_date)
            """, {"episode_id": episode_id})
            
            print(f"Enriched metadata for episode {episode_id}")
            
    except Exception as e:
        print(f"Error enriching metadata: {e}")

def establish_entity_relationships(neo4j_driver, episode_id):
    """
    Establish entity-to-entity relationships in the knowledge graph.
    
    Args:
        neo4j_driver: Neo4j driver
        episode_id: Episode ID
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot establish entity relationships.")
        return
        
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        with neo4j_driver.session(database=database) as session:
            # Create co-occurrence relationships between entities
            session.run("""
            MATCH (ep:Episode {id: $episode_id})-[:HAS_SEGMENT]->(s:Segment)
            MATCH (e1:Entity)-[:MENTIONED_IN]->(ep)
            MATCH (e2:Entity)-[:MENTIONED_IN]->(ep)
            WHERE e1 <> e2 
              AND toLower(s.text) CONTAINS toLower(e1.name)
              AND toLower(s.text) CONTAINS toLower(e2.name)
            MERGE (e1)-[r:CO_OCCURS_WITH]->(e2)
            ON CREATE SET r.count = 1, r.episodes = [$episode_id]
            ON MATCH SET r.count = r.count + 1,
                         r.episodes = CASE 
                             WHEN $episode_id IN r.episodes THEN r.episodes
                             ELSE r.episodes + $episode_id
                         END
            """, {"episode_id": episode_id})
            
            # Calculate entity centrality within the episode
            session.run("""
            MATCH (ep:Episode {id: $episode_id})
            MATCH (e:Entity)-[:MENTIONED_IN]->(ep)
            OPTIONAL MATCH (e)-[r:CO_OCCURS_WITH]-()
            WITH e, count(r) as degree
            SET e.centrality = degree
            """, {"episode_id": episode_id})
            
            # Track entity mentions across episodes
            session.run("""
            MATCH (e:Entity)-[:MENTIONED_IN]->(ep:Episode {id: $episode_id})
            SET e.episode_count = CASE
                WHEN e.episode_count IS NULL THEN 1
                ELSE e.episode_count + 1
            END
            """, {"episode_id": episode_id})
            
            # Create entity-insight relationships
            session.run("""
            MATCH (ep:Episode {id: $episode_id})-[:HAS_INSIGHT]->(i:Insight)
            MATCH (e:Entity)-[:MENTIONED_IN]->(ep)
            WHERE toLower(i.title + ' ' + i.description) CONTAINS toLower(e.name)
            MERGE (e)-[:CONTRIBUTES_TO]->(i)
            """, {"episode_id": episode_id})
            
            print(f"Established entity relationships for episode {episode_id}")
            
    except Exception as e:
        print(f"Error establishing entity relationships: {e}")

def enhance_episode_knowledge(podcast_info, episode, neo4j_driver, embedding_client):
    """
    Apply knowledge enhancements to a processed episode.
    
    Args:
        podcast_info: Podcast information
        episode: Episode information
        neo4j_driver: Neo4j driver
        embedding_client: OpenAI client for embeddings
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot enhance episode knowledge.")
        return
        
    try:
        # Apply each enhancement
        print(f"\nEnhancing knowledge for episode: {episode['title']}")
        
        # 1. Add sentiment information
        add_sentiment_to_knowledge_graph(neo4j_driver, episode['id'])
        
        # 2. Enhance speaker information
        enhance_speaker_information(neo4j_driver, episode['id'])
        
        # 3. Improve embeddings
        if embedding_client:
            improve_embeddings(neo4j_driver, episode['id'], embedding_client)
            
        # 4. Enrich metadata
        enrich_metadata(neo4j_driver, episode['id'])
        
        # 5. Establish entity relationships
        establish_entity_relationships(neo4j_driver, episode['id'])
        
        print(f"Successfully enhanced knowledge for episode: {episode['title']}")
        
    except Exception as e:
        print(f"Error enhancing episode knowledge: {e}")

# 5. Podcast Knowledge Pipeline and Functions
def enhance_graph_all_episodes(neo4j_driver, llm_client, embedding_client):
    """
    Apply knowledge enhancements to all episodes in the graph.
    
    Args:
        neo4j_driver: Neo4j driver
        llm_client: LLM client
        embedding_client: OpenAI client for embeddings
        
    Returns:
        True if successful, False otherwise
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot enhance graph for all episodes.")
        return False
        
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        with neo4j_driver.session(database=database) as session:
            # Get all podcast-episode pairs
            result = session.run("""
            MATCH (p:Podcast)-[:HAS_EPISODE]->(e:Episode)
            RETURN p.id as podcast_id, p.name as podcast_name, 
                   e.id as episode_id, e.title as episode_title
            """)
            
            for record in result:
                podcast_info = {
                    "id": record["podcast_id"],
                    "title": record["podcast_name"]
                }
                
                episode = {
                    "id": record["episode_id"],
                    "title": record["episode_title"]
                }
                
                enhance_episode_knowledge(podcast_info, episode, neo4j_driver, embedding_client)
                
            # After enhancing individual episodes, apply global enhancements
            enhance_knowledge_graph({}, [], neo4j_driver, llm_client, embedding_client)
            
            return True
            
    except Exception as e:
        print(f"Error enhancing graph for all episodes: {e}")
        return False

# 6. Gemini LLM Integration for Knowledge Extraction
def initialize_gemini_client(enable_large_context=True):
    """
    Initialize the Gemini LLM client for knowledge extraction.
    
    Args:
        enable_large_context: Whether to enable 1M token context window optimizations
        
    Returns:
        LLM client or None if initialization fails
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("GOOGLE_API_KEY not found in environment variables.")
            return None
        
        gemini_model_name = "gemini-2.5-flash-preview-04-17"
        gemini_llm_client = ChatGoogleGenerativeAI(
            model=gemini_model_name,
            google_api_key=api_key,
            temperature=0.2,
            convert_system_message_to_human=True,
            # Enable thinking capabilities for improved reasoning with large contexts
            thinking_budget=1024 if enable_large_context else 0
        )
        print(f"Successfully initialized Gemini LLM client with model: {gemini_model_name}")
        print(f"Large context optimization: {'Enabled' if enable_large_context else 'Disabled'}")
        return gemini_llm_client
        
    except Exception as e:
        print(f"Error initializing Gemini LLM client: {e}. LLM-dependent features will not work.")
        return None

def initialize_embedding_model():
    """
    Initialize the OpenAI embedding model for generating embeddings.
    
    Returns:
        OpenAI client or None if initialization fails
    """
    try:
        from openai import OpenAI
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("OPENAI_API_KEY not found in environment variables.")
            return None
        
        client = OpenAI(api_key=api_key)
        print("Successfully initialized OpenAI client for embeddings.")
        return client
        
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}. Embedding features will not work.")
        return None

def generate_embeddings(text, openai_client):
    """
    Generate embeddings for a text using OpenAI's text-embedding-3-small model.
    
    Args:
        text: Text to generate embeddings for
        openai_client: OpenAI client
        
    Returns:
        Embedding vector or None if generation fails
    """
    if not openai_client:
        print("OpenAI client not available. Cannot generate embeddings.")
        return None
    
    try:
        text = text.replace("\n", " ").strip()
        if not text:
            return None
            
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            dimensions=1536
        )
        
        embedding = response.data[0].embedding
        return embedding
        
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

# 7. Podcast Feed Processing Functions
def fetch_podcast_feed(podcast_config, max_episodes=1):
    """
    Fetch podcast feed and episode information.
    
    Args:
        podcast_config: Dictionary with podcast configuration
        max_episodes: Maximum number of episodes to fetch
        
    Returns:
        Dictionary with podcast and episode information
    """
    import feedparser
    
    print(f"Fetching RSS feed: {podcast_config['rss_url']}")
    
    feed = feedparser.parse(podcast_config['rss_url'])
    if feed.bozo:
        print(f"Warning: RSS feed may be malformed. Bozo bit set: {feed.bozo_exception}")
    
    podcast_info = {
        "id": podcast_config["id"],
        "title": feed.feed.get("title", podcast_config["name"]),
        "description": feed.feed.get("subtitle", feed.feed.get("description", podcast_config["description"])),
        "link": feed.feed.get("link", ""),
        "image": feed.feed.get("image", {}).get("href", ""),
        "episodes": []
    }
    
    # Process episodes
    episode_count = 0
    for entry in feed.entries:
        if max_episodes > 0 and episode_count >= max_episodes:
            break
            
        # Find audio URL
        audio_url = None
        if hasattr(entry, 'links'):
            for link in entry.links:
                if hasattr(link, "type") and "audio" in link.type.lower():
                    audio_url = link.href
                    break
                    
        if not audio_url and hasattr(entry, "enclosures") and entry.enclosures:
            for enclosure in entry.enclosures:
                if hasattr(enclosure, "type") and "audio" in enclosure.type.lower():
                    audio_url = enclosure.href
                    break
                    
        if not audio_url:
            audio_extensions = ['.mp3', '.m4a', '.wav', '.ogg', '.aac']
            if hasattr(entry, 'links'):
                for link in entry.links:
                    if any(ext in link.href.lower() for ext in audio_extensions):
                        audio_url = link.href
                        break
                        
            if not audio_url and hasattr(entry, 'enclosures') and entry.enclosures:
                for enclosure in entry.enclosures:
                    if any(ext in enclosure.href.lower() for ext in audio_extensions):
                        audio_url = enclosure.href
                        break
                        
        if not audio_url:
            print(f"Warning: Could not find audio URL for episode: {entry.get('title', 'Unknown Title')}")
            continue
        
        # Generate unique episode ID
        episode_id_base = entry.get("id", entry.get("guid", None))
        if not episode_id_base:
            title_for_id = entry.get("title", f"untitled_episode_{time.time()}")
            link_for_id = entry.get("link", audio_url)
            episode_id_base = f"{title_for_id}_{link_for_id}"
            
        episode_id = hashlib.sha256(episode_id_base.encode()).hexdigest()[:32]
        
        # Create episode object
        episode = {
            "id": episode_id,
            "title": entry.get("title", "Untitled Episode"),
            "description": entry.get("summary", entry.get("description", "")),
            "published_date": entry.get("published", entry.get("updated", "")),
            "audio_url": audio_url,
            "duration": entry.get("itunes_duration", "")
        }
        
        podcast_info["episodes"].append(episode)
        episode_count += 1
    
    print(f"Found {len(podcast_info['episodes'])} episodes for '{podcast_info['title']}'")
    return podcast_info

def download_episode_audio(episode, podcast_id, output_dir="audio_files"):
    """
    Download episode audio file.
    
    Args:
        episode: Dictionary with episode information
        podcast_id: Podcast ID
        output_dir: Directory to save audio files
        
    Returns:
        Path to downloaded audio file or None if download fails
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Create safe filename
    safe_podcast_id = re.sub(r'[^\w\-_\.]', '_', str(podcast_id))
    filename = f"{safe_podcast_id}_{episode['id']}.mp3"
    output_path = os.path.join(output_dir, filename)
    
    # Check if file already exists
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
        print(f"File already exists and is non-empty: {output_path}")
        return output_path
    
    # Download file
    print(f"Downloading: {episode['title']} (ID: {episode['id']})")
    try:
        req = urllib.request.Request(
            episode['audio_url'],
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req) as response, open(output_path, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
            
        print(f"Downloaded to {output_path}")
        
        if os.path.getsize(output_path) == 0:
            print(f"Warning: Downloaded file {output_path} is empty.")
            return None
            
        return output_path
        
    except Exception as e:
        print(f"Error downloading {episode['title']}: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return None

# 8. Transcription and Processing Functions
def transcribe_audio(audio_path, use_faster_whisper=True, whisper_model_size="large-v3"):
    """
    Transcribe audio using Whisper.
    
    Args:
        audio_path: Path to audio file
        use_faster_whisper: Whether to use faster-whisper
        whisper_model_size: Whisper model size
        
    Returns:
        Dictionary with transcription segments
    """
    # Determine device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using {device} for transcription")
    
    transcript_segments = []
    
    try:
        if use_faster_whisper:
            # Try faster-whisper first
            from faster_whisper import WhisperModel
            
            compute_type = "float16" if device == "cuda" else "int8"
            model = WhisperModel(whisper_model_size, device=device, compute_type=compute_type)
            
            # Transcribe
            print(f"Transcribing with faster-whisper model {whisper_model_size}...")
            segments, info = model.transcribe(
                audio_path,
                beam_size=5,
                vad_filter=True,
                word_timestamps=True
            )
            
            # Process segments
            for segment in segments:
                segment_dict = {
                    "text": segment.text.strip(),
                    "start": segment.start,
                    "end": segment.end,
                    "words": [{"word": w.word, "start": w.start, "end": w.end} for w in segment.words]
                }
                transcript_segments.append(segment_dict)
                
        else:
            # Fall back to regular whisper
            import whisper
            
            model = whisper.load_model(whisper_model_size, device=device)
            
            # Transcribe
            print(f"Transcribing with whisper model {whisper_model_size}...")
            result = model.transcribe(audio_path, word_timestamps=True)
            
            # Process segments
            for segment in result["segments"]:
                segment_dict = {
                    "text": segment["text"].strip(),
                    "start": segment["start"],
                    "end": segment["end"],
                    "words": [{"word": w["word"], "start": w["start"], "end": w["end"]} 
                              for w in segment.get("words", [])]
                }
                transcript_segments.append(segment_dict)
        
        print(f"Transcription completed with {len(transcript_segments)} segments")
        
    except Exception as e:
        print(f"Error during transcription: {e}")
        
    return transcript_segments

def diarize_speakers(audio_path, min_speakers=1, max_speakers=10):
    """
    Perform speaker diarization on audio.
    
    Args:
        audio_path: Path to audio file
        min_speakers: Minimum number of speakers
        max_speakers: Maximum number of speakers
        
    Returns:
        Dictionary mapping timestamps to speaker IDs
    """
    # Check if HF_TOKEN is available
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("No Hugging Face token. Skipping diarization.")
        return {}
    
    try:
        from pyannote.audio import Pipeline
        
        # Initialize diarization pipeline
        device = "cuda" if torch.cuda.is_available() else "cpu"
        diarization_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )
        
        if device == "cuda":
            diarization_pipeline = diarization_pipeline.to(torch.device("cuda"))
        
        # Run diarization
        print("Running speaker diarization...")
        diarization = diarization_pipeline(
            audio_path,
            min_speakers=min_speakers,
            max_speakers=max_speakers
        )
        
        # Create speaker map
        speaker_map = {}
        
        # Process diarization results
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            # Add each speech turn to our map with start/end times
            start_time = turn.start
            end_time = turn.end
            
            # Add entries at small intervals for better alignment
            step = 0.1  # 100ms steps
            current_time = start_time
            while current_time <= end_time:
                speaker_map[current_time] = speaker
                current_time += step
        
        print(f"Diarization completed with {len(set(speaker_map.values()))} speakers")
        return speaker_map
        
    except Exception as e:
        print(f"Error during diarization: {e}")
        return {}

def align_transcript_with_diarization(transcript_segments, speaker_map):
    """
    Align transcript segments with speaker diarization results.
    
    Args:
        transcript_segments: List of transcript segments
        speaker_map: Dictionary mapping timestamps to speaker IDs
        
    Returns:
        Updated transcript segments with speaker information
    """
    if not speaker_map:
        print("No speaker map provided. Returning transcript without speaker information.")
        return transcript_segments
    
    # Align speakers with transcript segments
    for segment in transcript_segments:
        start = segment.get('start', 0)
        end = segment.get('end', 0)
        
        # Find the most frequent speaker in this time range
        speaker_counts = defaultdict(int)
        
        # Check several points within the segment
        segment_duration = end - start
        check_points = 10  # number of points to check
        
        for i in range(check_points):
            check_time = start + (segment_duration * i / check_points)
            # Find the closest key in speaker_map
            closest_time = min(speaker_map.keys(), key=lambda k: abs(k - check_time), default=None)
            
            if closest_time is not None and abs(closest_time - check_time) < 1.0:  # within 1 second
                speaker_counts[speaker_map[closest_time]] += 1
        
        # Assign the most common speaker
        if speaker_counts:
            most_common_speaker = max(speaker_counts.items(), key=lambda x: x[1])[0]
            segment['speaker'] = f"Speaker_{most_common_speaker}"
        else:
            segment['speaker'] = "Unknown"
    
    return transcript_segments

# 9. Knowledge Extraction and Graph Construction
def convert_transcript_for_llm(transcript_segments):
    """
    Convert transcript segments to a format suitable for LLM processing.
    
    Args:
        transcript_segments: List of transcript segments
        
    Returns:
        Formatted transcript string with speaker information
    """
    formatted_lines = []
    
    for segment in transcript_segments:
        speaker = segment.get('speaker', 'Speaker')
        text = segment.get('text', '').strip()
        start_time = segment.get('start', 0)
        end_time = segment.get('end', 0)
        
        # Format time as MM:SS
        start_formatted = f"{int(start_time // 60):02d}:{int(start_time % 60):02d}"
        end_formatted = f"{int(end_time // 60):02d}:{int(end_time % 60):02d}"
        
        # Format line
        line = f"[{start_formatted}-{end_formatted}] {speaker}: {text}"
        formatted_lines.append(line)
    
    return "\n".join(formatted_lines)

# ============================================================================
# INSIGHT EXTRACTION - DECOMPOSED FUNCTIONS  
# ============================================================================

def build_insight_extraction_prompt(podcast_name, episode_title, use_large_context=True):
    """Build the appropriate prompt template for insight extraction."""
    if not ChatPromptTemplate:
        raise LLMProcessingError("LangChain ChatPromptTemplate not available")
    
    if use_large_context:
        # Enhanced prompt for large context window models
        prompt_template = """
        You are a knowledge extraction system analyzing an entire podcast episode.
        
        PODCAST: {podcast_name}
        EPISODE: {episode_title}
        
        Your task is to extract structured insights from the complete podcast transcript below.
        Take advantage of your 1M token context window to identify themes, patterns, and valuable insights
        that span across the entire conversation. Look for connections between different parts of the episode.
        
        Focus on the most valuable and non-obvious information. Consider how ideas evolve throughout the conversation.
        
        FULL TRANSCRIPT:
        {segment_text}
        
        Extract 5-15 valuable insights from this episode. For each insight:
        1. Give it a concise, informative title that captures the core idea
        2. Write a brief but clear description (1-3 sentences) that explains the insight
        3. Classify the insight_type as one of:
           - 'actionable' (practical advice, steps to take, recommendations)
           - 'conceptual' (explanations, theory, background information)
           - 'experiential' (personal stories, examples, case studies)
        4. Include a confidence score (1-10) indicating how strongly this insight is supported in the transcript
        
        Format your response as a valid JSON array of objects with these fields:
        - title (string): Concise, informative title
        - description (string): Clear, accurate description of the insight
        - insight_type (string): One of 'actionable', 'conceptual', or 'experiential'
        - confidence (number): Confidence score from 1-10
        - references (array): Array of brief quotes from the transcript that support this insight
        
        Look for insights that span across different segments of the conversation, noting how ideas evolve
        or are reinforced throughout the episode. Pay special attention to recurring themes.
        
        If the transcript is primarily advertisements or irrelevant content, return a smaller number of insights.
        
        JSON RESPONSE:
        """
        system_message = "You are a knowledgeable assistant that extracts structured insights from podcast transcripts. You excel at analyzing long-form content and identifying connections across an entire conversation."
    else:
        # Original prompt for segment-based processing
        prompt_template = """
        You are a knowledge extraction system analyzing a podcast segment.
        
        PODCAST: {podcast_name}
        EPISODE: {episode_title}
        
        Your task is to extract structured insights from the podcast segment below.
        Focus on the most valuable and non-obvious information.
        
        SEGMENT TEXT:
        {segment_text}
        
        Extract 1-3 valuable insights from this segment. For each insight:
        1. Give it a concise, informative title that captures the core idea
        2. Write a brief but clear description (1-3 sentences) that explains the insight
        3. Classify the insight_type as one of:
           - 'actionable' (practical advice, steps to take, recommendations)
           - 'conceptual' (explanations, theory, background information)
           - 'experiential' (personal stories, examples, case studies)
        
        Format your response as a valid JSON array of objects with these fields:
        - title (string): Concise, informative title
        - description (string): Clear, accurate description of the insight
        - insight_type (string): One of 'actionable', 'conceptual', or 'experiential'
        
        If the segment doesn't contain any valuable insights (e.g., it's an advertisement, 
        introduction, pleasantries, or irrelevant content), return an empty array [].
        
        JSON RESPONSE:
        """
        system_message = "You are a knowledgeable assistant that extracts structured insights from podcast transcripts."
    
    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", prompt_template)
    ])

def call_llm_for_insights(prompt, llm_client, podcast_name, episode_title, segment_text):
    """Call the LLM to extract insights."""
    try:
        # Format prompt
        formatted_prompt = prompt.format(
            podcast_name=podcast_name,
            episode_title=episode_title,
            segment_text=segment_text
        )
        
        # Get response from LLM
        response = llm_client.invoke(formatted_prompt)
        return response.content
        
    except Exception as e:
        raise LLMProcessingError(f"Failed to get insights from LLM: {e}")

def parse_insight_response(response_text):
    """Parse the LLM response to extract structured insights."""
    try:
        # Clean up response to extract JSON
        response_lines = response_text.strip().split('\n')
        json_lines = []
        in_json = False
        
        for line in response_lines:
            if line.strip() == "```json" or line.strip() == "```":
                in_json = not in_json
                continue
            if in_json or "[" in line or "{" in line:
                json_lines.append(line)
        
        clean_json = '\n'.join(json_lines)
        
        if not clean_json.strip():
            print("Warning: Empty JSON response from LLM")
            return []
            
        insights = json.loads(clean_json)
        
        # Validate that we got a list
        if not isinstance(insights, list):
            raise ValueError("Expected a list of insights")
            
        return insights
        
    except json.JSONDecodeError as e:
        raise LLMProcessingError(f"Failed to parse JSON response: {e}")
    except Exception as e:
        raise LLMProcessingError(f"Failed to parse insight response: {e}")

def validate_and_enhance_insights(insights, use_large_context=True):
    """Validate and enhance the extracted insights."""
    validated_insights = []
    
    for insight in insights:
        try:
            # Ensure required fields exist
            if not all(field in insight for field in ["title", "description", "insight_type"]):
                print(f"Warning: Skipping invalid insight missing required fields: {insight}")
                continue
            
            # Add default values for optional fields
            if use_large_context:
                if "confidence" not in insight:
                    insight["confidence"] = 7  # Default mid-high confidence
                if "references" not in insight:
                    insight["references"] = []
            
            # Validate insight_type
            valid_types = ["actionable", "conceptual", "experiential"]
            if insight["insight_type"] not in valid_types:
                insight["insight_type"] = "conceptual"  # Default type
            
            # Ensure strings are not empty
            if not insight["title"].strip() or not insight["description"].strip():
                print(f"Warning: Skipping insight with empty title or description")
                continue
                
            validated_insights.append(insight)
            
        except Exception as e:
            print(f"Warning: Error validating insight: {e}")
            continue
    
    return validated_insights

def extract_structured_insights(transcript_text, segment_text, llm_client, podcast_name, episode_title, use_large_context=True):
    """
    Extract structured insights from a transcript segment using decomposed LLM processing.
    
    Args:
        transcript_text: Full transcript text (legacy parameter, not used in current implementation)
        segment_text: Current segment text (can be the full transcript in large context mode)
        llm_client: LLM client
        podcast_name: Name of the podcast
        episode_title: Title of the episode
        use_large_context: Whether to use prompts optimized for 1M token context
        
    Returns:
        List of structured insights
        
    Raises:
        LLMProcessingError: If LLM processing fails
        ConfigurationError: If required components are missing
    """
    if not llm_client:
        raise ConfigurationError("LLM client not available. Cannot extract insights.")
    
    try:
        print(f"Extracting insights using {'large context' if use_large_context else 'segment-based'} mode...")
        
        # Build appropriate prompt
        prompt = build_insight_extraction_prompt(podcast_name, episode_title, use_large_context)
        
        # Call LLM for insights
        response_text = call_llm_for_insights(prompt, llm_client, podcast_name, episode_title, segment_text)
        
        # Parse the response
        insights = parse_insight_response(response_text)
        
        # Validate and enhance insights
        validated_insights = validate_and_enhance_insights(insights, use_large_context)
        
        print(f"Successfully extracted {len(validated_insights)} insights")
        return validated_insights
        
    except (LLMProcessingError, ConfigurationError):
        raise
    except Exception as e:
        raise LLMProcessingError(f"Unexpected error during insight extraction: {e}")

def detect_entities_with_gemini(text, llm_client, use_large_context=True):
    """
    Detect entities in text using Gemini LLM.
    
    Args:
        text: Text to analyze (can be the full transcript in large context mode)
        llm_client: LLM client
        use_large_context: Whether to use prompts optimized for 1M token context
        
    Returns:
        List of detected entities
    """
    if not llm_client:
        print("LLM client not available. Cannot detect entities.")
        return []
    
    from langchain.prompts import ChatPromptTemplate
    
    # Create prompt for entity extraction based on context size
    if use_large_context:
        # Enhanced prompt for large context window models with science/health entities
        prompt_template = """
        Extract named entities from the following podcast transcript. With your 1M token context window,
        look for all key entities throughout the entire conversation.
        
        Entity Types to Extract:
        - General: Person, Company, Product, Technology, Concept, Book, Framework, Method, Location
        - Research: Study, Institution, Researcher, Journal, Theory, Research_Method
        - Medical: Medication, Condition, Treatment, Symptom, Biological_Process, Medical_Device
        - Science: Chemical, Scientific_Theory, Laboratory, Experiment, Discovery
        
        TRANSCRIPT:
        {text}
        
        For each entity, provide:
        1. The entity name as it appears in the text
        2. The entity type from the categories above
        3. A brief one-sentence description synthesizing all mentions of this entity
        4. A frequency count indicating how many times this entity is mentioned
        5. Whether it's mentioned with scientific evidence or citations
        6. Context type: research, clinical, anecdotal, or general
        
        Pay special attention to:
        - Scientific studies and their findings
        - Medical conditions and treatments discussed
        - Research institutions and researchers mentioned
        - Biological processes and mechanisms explained
        - Citations or references to scientific literature
        
        Format your response as a valid JSON list of objects with these fields:
        - name (string): The entity name
        - type (string): The entity type from the list above
        - description (string): Brief description synthesizing all mentions
        - frequency (number): Approximate number of mentions
        - importance (number): Importance score 1-10 based on discussion depth
        - has_citation (boolean): Whether mentioned with studies/evidence
        - context_type (string): research, clinical, anecdotal, or general
        
        Only include entities that are clearly mentioned. Consolidate variants of the same entity.
        
        JSON RESPONSE:
        """
    else:
        # Prompt for segment-based processing with science/health entities
        prompt_template = """
        Extract named entities from the following text.
        
        Entity Types: Person, Company, Product, Technology, Concept, Book, Framework, Method,
        Study, Institution, Researcher, Journal, Medication, Condition, Treatment, Symptom,
        Biological_Process, Chemical, Scientific_Theory, Medical_Device
        
        TEXT:
        {text}
        
        For each entity, provide:
        1. The entity name as it appears in the text
        2. The entity type from the list above
        3. A brief one-sentence description if possible
        4. Whether it includes a citation or evidence reference
        
        Format your response as valid JSON list of objects with these fields:
        - name (string): The entity name
        - type (string): The entity type
        - description (string): Brief description if known
        - has_citation (boolean): Whether mentioned with evidence
        
        Only include entities that are clearly mentioned in the text.
        
        JSON RESPONSE:
        """
    
    # Create prompt with appropriate system message
    system_message = "You are a precise entity extraction system."
    if use_large_context:
        system_message += " You excel at identifying and consolidating entity mentions across long-form content."
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", prompt_template)
    ])
    
    # Format prompt
    formatted_prompt = prompt.format(text=text)
    
    try:
        # Get response from LLM
        response = llm_client.invoke(formatted_prompt)
        response_text = response.content
        
        # Parse JSON
        import json
        
        # Clean up response to extract JSON
        response_lines = response_text.strip().split('\n')
        json_lines = []
        in_json = False
        
        for line in response_lines:
            if line.strip() == "```json" or line.strip() == "```":
                in_json = not in_json
                continue
            if in_json or "[" in line or "{" in line:
                json_lines.append(line)
        
        clean_json = '\n'.join(json_lines)
        entities = json.loads(clean_json)
        
        # If using large context, ensure entities have consistent fields
        if use_large_context:
            for entity in entities:
                # Ensure all required fields exist
                if "frequency" not in entity:
                    entity["frequency"] = 1
                if "importance" not in entity:
                    entity["importance"] = 5
        
        return entities
        
    except Exception as e:
        print(f"Error detecting entities: {e}")
        return []

# ============================================================================
# Technical Complexity Scoring
# ============================================================================

def analyze_vocabulary_complexity(text):
    """
    Analyze vocabulary complexity of text.
    
    Returns:
        Dict with complexity metrics
    """
    from collections import Counter
    import re
    
    # Basic tokenization
    words = re.findall(r'\b[a-z]+\b', text.lower())
    if not words:
        return {
            'avg_word_length': 0,
            'unique_ratio': 0,
            'syllable_complexity': 0,
            'technical_density': 0
        }
    
    # Calculate basic metrics
    avg_word_length = sum(len(word) for word in words) / len(words)
    unique_words = set(words)
    unique_ratio = len(unique_words) / len(words)
    
    # Estimate syllable complexity (simple heuristic)
    def count_syllables(word):
        vowels = 'aeiouAEIOU'
        count = 0
        previous_was_vowel = False
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not previous_was_vowel:
                count += 1
            previous_was_vowel = is_vowel
        return max(1, count)
    
    total_syllables = sum(count_syllables(word) for word in words)
    avg_syllables = total_syllables / len(words)
    
    # Use optimized pattern matcher
    technical_count = pattern_matcher.count_technical_terms(text)
    technical_density = technical_count / len(words) if words else 0
    
    return {
        'avg_word_length': avg_word_length,
        'unique_ratio': unique_ratio,
        'syllable_complexity': avg_syllables,
        'technical_density': technical_density
    }

def classify_segment_complexity(text, entities=None):
    """
    Classify segment complexity as layperson, intermediate, or expert.
    
    Args:
        text: Segment text
        entities: Optional list of detected entities
        
    Returns:
        Dict with complexity classification and scores
    """
    # Get vocabulary metrics
    vocab_metrics = analyze_vocabulary_complexity(text)
    
    # Count technical entities if provided
    technical_entity_types = {
        'Study', 'Institution', 'Researcher', 'Journal', 'Theory', 'Research_Method',
        'Medication', 'Condition', 'Treatment', 'Symptom', 'Biological_Process',
        'Medical_Device', 'Chemical', 'Scientific_Theory', 'Laboratory', 'Experiment',
        'Discovery'
    }
    
    technical_entity_count = 0
    if entities:
        for entity in entities:
            if entity.get('type') in technical_entity_types:
                technical_entity_count += 1
    
    # Calculate composite score
    complexity_score = (
        vocab_metrics['avg_word_length'] * 0.2 +
        (1 - vocab_metrics['unique_ratio']) * 0.2 +  # Lower unique ratio = more repetition = easier
        vocab_metrics['syllable_complexity'] * 0.3 +
        vocab_metrics['technical_density'] * 100 * 0.3  # Scale technical density
    )
    
    # Add entity contribution
    if entities and len(entities) > 0:
        entity_ratio = technical_entity_count / len(entities)
        complexity_score += entity_ratio * 2
    
    # Classify based on score
    if complexity_score < 3:
        classification = 'layperson'
    elif complexity_score < 5:
        classification = 'intermediate'
    else:
        classification = 'expert'
    
    # Check for specific markers that might override classification
    if vocab_metrics['technical_density'] > 0.1:  # >10% technical terms
        classification = 'expert'
    elif vocab_metrics['technical_density'] > 0.05 and classification == 'layperson':
        classification = 'intermediate'
    
    return {
        'classification': classification,
        'complexity_score': complexity_score,
        'vocab_metrics': vocab_metrics,
        'technical_entity_count': technical_entity_count,
        'technical_density': vocab_metrics['technical_density']
    }

def calculate_episode_complexity(segments_complexity):
    """
    Calculate overall episode complexity from segment complexities.
    
    Args:
        segments_complexity: List of segment complexity dicts
        
    Returns:
        Dict with episode-level complexity metrics
    """
    if not segments_complexity:
        return {
            'average_complexity': 0,
            'dominant_level': 'unknown',
            'complexity_distribution': {},
            'technical_density': 0,
            'complexity_variance': 0
        }
    
    # Calculate average complexity score
    scores = [seg['complexity_score'] for seg in segments_complexity]
    avg_score = sum(scores) / len(scores)
    
    # Calculate variance to measure consistency
    variance = sum((score - avg_score) ** 2 for score in scores) / len(scores)
    
    # Count distribution of complexity levels
    distribution = {'layperson': 0, 'intermediate': 0, 'expert': 0}
    for seg in segments_complexity:
        distribution[seg['classification']] += 1
    
    # Determine dominant level
    dominant_level = max(distribution.items(), key=lambda x: x[1])[0]
    
    # Calculate average technical density
    tech_densities = [seg['technical_density'] for seg in segments_complexity]
    avg_tech_density = sum(tech_densities) / len(tech_densities)
    
    # Normalize distribution to percentages
    total_segments = len(segments_complexity)
    distribution_pct = {
        level: (count / total_segments) * 100 
        for level, count in distribution.items()
    }
    
    return {
        'average_complexity': avg_score,
        'dominant_level': dominant_level,
        'complexity_distribution': distribution_pct,
        'technical_density': avg_tech_density,
        'complexity_variance': variance,
        'is_mixed_complexity': variance > 1.5,  # High variance indicates mixed audience
        'is_technical': avg_tech_density > 0.05  # >5% technical terms
    }

# ============================================================================
# Information Density & Accessibility Scoring
# ============================================================================

def calculate_information_density(text, insights=None, entities=None):
    """
    Calculate information density metrics for a text segment.
    
    Args:
        text: Segment text
        insights: Optional list of insights extracted
        entities: Optional list of entities detected
        
    Returns:
        Dict with information density metrics
    """
    import re
    
    # Basic text metrics
    words = text.split()
    word_count = len(words)
    char_count = len(text)
    
    if word_count == 0:
        return {
            'insight_density': 0,
            'entity_density': 0,
            'fact_density': 0,
            'information_score': 0,
            'words_per_minute': 0
        }
    
    # Calculate densities
    insight_density = len(insights) / word_count * 100 if insights else 0
    entity_density = len(entities) / word_count * 100 if entities else 0
    
    # Use optimized pattern matcher for fact counting
    fact_count = pattern_matcher.count_facts(text)
    fact_density = fact_count / word_count * 100
    
    # Calculate composite information score
    information_score = (
        insight_density * 0.4 +
        entity_density * 0.3 +
        fact_density * 0.3
    )
    
    # Estimate words per minute (assuming average speaking rate of 150 wpm)
    avg_wpm = 150
    duration_estimate = word_count / avg_wpm
    
    return {
        'insight_density': insight_density,
        'entity_density': entity_density,
        'fact_density': fact_density,
        'information_score': information_score,
        'word_count': word_count,
        'duration_minutes': duration_estimate,
        'insights_per_minute': (len(insights) / duration_estimate) if insights and duration_estimate > 0 else 0,
        'entities_per_minute': (len(entities) / duration_estimate) if entities and duration_estimate > 0 else 0
    }

def calculate_accessibility_score(text, complexity_score):
    """
    Calculate accessibility score based on various readability metrics.
    
    Args:
        text: Text to analyze
        complexity_score: Complexity score from classify_segment_complexity
        
    Returns:
        Dict with accessibility metrics
    """
    import re
    
    # Split into sentences and words
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    words = text.split()
    
    if not sentences or not words:
        return {
            'accessibility_score': 0,
            'avg_sentence_length': 0,
            'jargon_percentage': 0,
            'explanation_quality': 0
        }
    
    # Average sentence length
    avg_sentence_length = len(words) / len(sentences)
    
    # Check for jargon and explanations
    jargon_patterns = [
        r'\b[A-Z]{3,}\b',  # Acronyms
        r'\b\w+(?:ology|itis|osis|ase|ine)\b',  # Technical suffixes
        r'\b(?:neuro|cardio|hypo|anti|meta|poly)\w+\b',  # Technical prefixes
    ]
    
    explanation_patterns = [
        r'\b(?:which means|in other words|that is|i\.e\.|for example|such as)\b',
        r'\b(?:basically|simply put|essentially|in simple terms)\b',
        r'\b(?:imagine|think of it as|like a?|similar to)\b',  # Analogies
        r'\([^)]+\)',  # Parenthetical explanations
    ]
    
    jargon_count = 0
    for pattern in jargon_patterns:
        jargon_count += len(re.findall(pattern, text, re.IGNORECASE))
    
    explanation_count = 0
    for pattern in explanation_patterns:
        explanation_count += len(re.findall(pattern, text, re.IGNORECASE))
    
    jargon_percentage = (jargon_count / len(words)) * 100 if words else 0
    explanation_quality = min(100, (explanation_count / max(1, jargon_count)) * 100)
    
    # Calculate accessibility score (inverse of complexity with adjustments)
    accessibility_score = 100 - (complexity_score * 10)  # Base from complexity
    
    # Adjust for sentence length (longer sentences = less accessible)
    if avg_sentence_length > 20:
        accessibility_score -= (avg_sentence_length - 20) * 2
    
    # Adjust for jargon vs explanations
    accessibility_score -= jargon_percentage * 0.5
    accessibility_score += explanation_quality * 0.3
    
    # Ensure score is between 0 and 100
    accessibility_score = max(0, min(100, accessibility_score))
    
    return {
        'accessibility_score': accessibility_score,
        'avg_sentence_length': avg_sentence_length,
        'jargon_percentage': jargon_percentage,
        'explanation_quality': explanation_quality,
        'has_analogies': bool(re.search(r'\b(?:like a?|similar to|imagine|think of it as)\b', text, re.IGNORECASE)),
        'has_examples': bool(re.search(r'\b(?:for example|such as|instance)\b', text, re.IGNORECASE))
    }

def aggregate_episode_metrics(segments_info_density, segments_accessibility):
    """
    Aggregate segment-level metrics to episode level.
    
    Args:
        segments_info_density: List of information density dicts
        segments_accessibility: List of accessibility dicts
        
    Returns:
        Dict with episode-level aggregated metrics
    """
    if not segments_info_density:
        return {
            'avg_information_score': 0,
            'total_insights': 0,
            'total_entities': 0,
            'avg_accessibility': 0,
            'information_variance': 0
        }
    
    # Information density aggregation
    info_scores = [seg['information_score'] for seg in segments_info_density]
    avg_info_score = sum(info_scores) / len(info_scores)
    
    # Calculate variance to identify episodes with uneven information distribution
    info_variance = sum((score - avg_info_score) ** 2 for score in info_scores) / len(info_scores)
    
    # Total insights and entities
    total_insights = sum(seg['insight_density'] * seg['word_count'] / 100 for seg in segments_info_density)
    total_entities = sum(seg['entity_density'] * seg['word_count'] / 100 for seg in segments_info_density)
    
    # Accessibility aggregation
    accessibility_scores = [seg['accessibility_score'] for seg in segments_accessibility] if segments_accessibility else []
    avg_accessibility = sum(accessibility_scores) / len(accessibility_scores) if accessibility_scores else 0
    
    # Find high-value segments (top 20% by information score)
    sorted_segments = sorted(enumerate(info_scores), key=lambda x: x[1], reverse=True)
    top_20_percent = int(len(sorted_segments) * 0.2) or 1
    high_value_segments = [idx for idx, _ in sorted_segments[:top_20_percent]]
    
    return {
        'avg_information_score': avg_info_score,
        'total_insights': int(total_insights),
        'total_entities': int(total_entities),
        'avg_accessibility': avg_accessibility,
        'information_variance': info_variance,
        'has_consistent_density': info_variance < 10,  # Low variance = consistent
        'high_value_segment_indices': high_value_segments
    }

# ============================================================================
# Quotability & Best-Of Detection
# ============================================================================

def calculate_quotability_score(text, speaker=None):
    """
    Calculate how quotable a text segment is.
    
    Args:
        text: Text to analyze
        speaker: Optional speaker name
        
    Returns:
        Dict with quotability metrics
    """
    import re
    
    # Check text length (ideal quotes are 10-30 words)
    words = text.split()
    word_count = len(words)
    
    if word_count < 5 or word_count > 100:
        length_score = 0
    elif 10 <= word_count <= 30:
        length_score = 100
    else:
        # Gradual decrease for longer quotes
        length_score = max(0, 100 - (word_count - 30) * 2)
    
    # Use optimized pattern matcher for quotability
    pattern_matches = pattern_matcher.get_quotability_matches(text)
    pattern_score = min(100, pattern_matches * 15)
    
    # Check for memorable phrasing
    memorable_indicators = [
        r'\b(?:imagine|picture|think about)\b',  # Vivid imagery
        r'\b\w+\s+(?:is|are)\s+like\b',  # Analogies
        r'\b(?:not|n\'t).*but\b',  # Contrasts
        r'[!?]',  # Emotional punctuation
        r'\b(?:I|we)\s+(?:learned|discovered|realized)\b',  # Personal insights
    ]
    
    memorable_score = 0
    for indicator in memorable_indicators:
        if re.search(indicator, text, re.IGNORECASE):
            memorable_score += 20
    memorable_score = min(100, memorable_score)
    
    # Check for self-contained meaning (doesn't rely on context)
    context_dependent_words = ['this', 'that', 'these', 'those', 'it', 'they', 'them', 'here', 'there']
    context_dependency = sum(1 for word in context_dependent_words if word in text.lower().split())
    self_contained_score = max(0, 100 - (context_dependency * 20))
    
    # Calculate composite score
    quotability_score = (
        length_score * 0.3 +
        pattern_score * 0.25 +
        memorable_score * 0.25 +
        self_contained_score * 0.2
    )
    
    # Boost score for known speakers (if provided)
    if speaker and speaker.lower() != 'unknown':
        quotability_score = min(100, quotability_score * 1.1)
    
    return {
        'quotability_score': quotability_score,
        'is_highly_quotable': quotability_score >= 70,
        'length_score': length_score,
        'pattern_score': pattern_score,
        'memorable_score': memorable_score,
        'self_contained_score': self_contained_score,
        'word_count': word_count
    }

def detect_best_of_markers(text, insights=None):
    """
    Detect if a segment contains "best of" worthy content.
    
    Args:
        text: Segment text
        insights: Optional insights extracted from segment
        
    Returns:
        Dict with best-of detection results
    """
    import re
    
    # Patterns indicating highlight-worthy content
    highlight_patterns = [
        # Key moments
        r'\b(?:breakthrough|turning point|pivotal|game.?changer)\b',
        r'\b(?:aha|eureka|lightbulb) moment\b',
        r'\b(?:changed everything|life.?changing|transformative)\b',
        
        # Valuable insights
        r'\b(?:most important|biggest|key) (?:lesson|insight|takeaway)\b',
        r'\b(?:secret|trick|hack) (?:to|is|for)\b',
        r'\bhere\'s (?:the|what|how)\b',
        
        # Strong statements
        r'\b(?:controversial|unpopular) opinion\b',
        r'\b(?:truth is|fact is|reality is)\b',
        r'\bmyth about\b',
        
        # Expertise markers
        r'\b(?:spent|invested) \d+ (?:years|months|hours)\b',
        r'\b(?:learned|discovered) (?:that|how)\b',
        r'\bafter (?:years|decades) of\b',
        
        # Actionable advice
        r'\b(?:step.?by.?step|framework|process|method)\b',
        r'\b\d+\s+(?:tips|ways|steps|strategies)\b',
        r'\b(?:how to|guide to|formula for)\b'
    ]
    
    pattern_matches = 0
    matched_patterns = []
    for pattern in highlight_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            pattern_matches += 1
            matched_patterns.append(pattern)
    
    # Check insight quality if available
    high_value_insights = 0
    if insights:
        for insight in insights:
            # Assuming insights have confidence scores
            if insight.get('confidence', 0) >= 8:
                high_value_insights += 1
    
    # Calculate best-of score
    pattern_score = min(100, pattern_matches * 25)
    insight_score = min(100, high_value_insights * 30)
    
    best_of_score = (pattern_score * 0.6 + insight_score * 0.4)
    
    # Determine category
    if best_of_score >= 80:
        category = 'must_include'
    elif best_of_score >= 60:
        category = 'highly_recommended'
    elif best_of_score >= 40:
        category = 'consider'
    else:
        category = 'regular'
    
    return {
        'best_of_score': best_of_score,
        'category': category,
        'pattern_matches': pattern_matches,
        'high_value_insights': high_value_insights,
        'is_best_of': best_of_score >= 60,
        'matched_patterns': matched_patterns[:3]  # Top 3 patterns for reference
    }

def extract_key_quotes(segments, quotability_scores):
    """
    Extract the most quotable segments from an episode.
    
    Args:
        segments: List of transcript segments
        quotability_scores: List of quotability score dicts
        
    Returns:
        List of key quotes with metadata
    """
    if not segments or not quotability_scores:
        return []
    
    # Combine segments with their scores
    segment_quotes = []
    for i, (segment, score) in enumerate(zip(segments, quotability_scores)):
        if score['is_highly_quotable']:
            segment_quotes.append({
                'text': segment['text'],
                'speaker': segment.get('speaker', 'Unknown'),
                'start_time': segment['start'],
                'end_time': segment['end'],
                'segment_index': i,
                'quotability_score': score['quotability_score'],
                'word_count': score['word_count']
            })
    
    # Sort by quotability score
    segment_quotes.sort(key=lambda x: x['quotability_score'], reverse=True)
    
    # Return top quotes (max 10)
    return segment_quotes[:10]

# ============================================================================
# PHASE 3: OPTIMIZED LLM PROMPT BUILDERS
# ============================================================================

def build_combined_extraction_prompt(podcast_name, episode_title, transcript, use_large_context=True):
    """
    Build a combined prompt for extracting insights, entities, and quotes in a single call.
    Optimized for token efficiency.
    """
    if use_large_context:
        prompt = f"""
Analyze this podcast transcript and extract structured knowledge in ONE pass.

PODCAST: {podcast_name}
EPISODE: {episode_title}

TRANSCRIPT:
{transcript}

Extract the following in JSON format:

1. INSIGHTS: Key takeaways and learnings
   - title: Brief 3-5 word title
   - description: One sentence description
   - insight_type: actionable (practical advice)/conceptual (theory, explanations)/experiential (stories, examples)
   - confidence: 1-10 score

2. ENTITIES: Important people, companies, concepts
   - name: Entity name
   - type: Person/Company/Product/Technology/Concept/Book/Framework/Method/Location/Study/Institution/Researcher/Journal/Theory/Research_Method/Medication/Condition/Treatment/Symptom/Biological_Process/Medical_Device/Chemical/Scientific_Theory/Laboratory/Experiment/Discovery
   - description: Brief description
   - importance: 1-10 score
   - frequency: Approximate mentions
   - has_citation: true/false

3. QUOTES: Highly quotable segments (10-30 words ideal)
   - text: The exact quote
   - speaker: Who said it
   - context: Brief context

Return ONLY valid JSON:
{{
  "insights": [...],
  "entities": [...],
  "quotes": [...]
}}
"""
    else:
        # Shorter prompt for segment processing
        prompt = f"""
Extract insights, entities, and quotes from this segment.

SEGMENT:
{transcript}

Return JSON with insights (title, description, insight_type), entities (name, type, description), and quotes (text, speaker).
"""
    
    return prompt

def parse_combined_llm_response(response_text):
    """Parse the combined LLM response containing insights, entities, and quotes."""
    try:
        import json
        
        # Clean response
        response_lines = response_text.strip().split('\n')
        json_lines = []
        in_json = False
        
        for line in response_lines:
            if line.strip() in ["```json", "```"]:
                in_json = not in_json
                continue
            if in_json or line.strip().startswith('{') or line.strip().startswith('['):
                json_lines.append(line)
        
        clean_json = '\n'.join(json_lines)
        data = json.loads(clean_json)
        
        # Validate structure
        result = {
            'insights': data.get('insights', []),
            'entities': data.get('entities', []),
            'quotes': data.get('quotes', [])
        }
        
        # Basic validation
        for insight in result['insights']:
            if 'title' not in insight or 'description' not in insight:
                insight['title'] = insight.get('title', 'Untitled')
                insight['description'] = insight.get('description', 'No description')
                insight['category'] = insight.get('category', 'ProblemSolutionNarrative')
                
        return result
        
    except Exception as e:
        logger.error(f"Failed to parse combined response: {e}")
        return {'insights': [], 'entities': [], 'quotes': []}

# ============================================================================
# PHASE 1.2: BATCH SAVING FUNCTIONS  
# ============================================================================

def save_segment_batch_to_neo4j(neo4j_driver, episode, segments, batch_start_idx, 
                                batch_complexity, batch_info_density, batch_accessibility,
                                batch_quotability, batch_best_of, embedding_client):
    """Save a batch of segments to Neo4j to free memory."""
    database = PodcastConfig.NEO4J_DATABASE
    
    try:
        with neo4j_driver.session(database=database) as session:
            def save_batch(tx):
                for i, segment in enumerate(segments):
                    segment_idx = batch_start_idx + i
                    segment_id = generate_stable_segment_id(
                        episode['id'], 
                        segment['text'], 
                        segment['start'],
                        segment.get('speaker')
                    )
                    
                    # Generate embedding if available
                    embedding = None
                    if embedding_client:
                        try:
                            embedding = generate_embeddings(segment["text"], embedding_client)
                        except Exception as e:
                            logger.warning(f"Failed to generate embedding for segment {segment_idx}: {e}")
                    
                    # Prepare all metrics
                    query_params = {
                        "id": segment_id,
                        "text": segment["text"],
                        "start_time": segment["start"],
                        "end_time": segment["end"],
                        "speaker": segment.get("speaker", "Unknown"),
                        "episode_id": episode["id"],
                        "index": segment_idx,
                        "embedding": embedding,
                        # Additional metadata for stable IDs
                        "content_hash": segment_id.split('_')[-1],
                        "word_count": len(segment["text"].split()),
                        "duration_seconds": segment["end"] - segment["start"]
                    }
                    
                    # Add complexity metrics
                    if i < len(batch_complexity):
                        complexity = batch_complexity[i]
                        query_params.update({
                            "complexity_level": complexity.get('classification', 'unknown'),
                            "complexity_score": complexity.get('complexity_score', 0),
                            "technical_density": complexity.get('technical_density', 0)
                        })
                    
                    # Add other metrics
                    if i < len(batch_info_density):
                        query_params["information_score"] = batch_info_density[i].get('information_score', 0)
                    if i < len(batch_accessibility):
                        query_params["accessibility_score"] = batch_accessibility[i].get('accessibility_score', 0)
                    if i < len(batch_quotability):
                        query_params["quotability_score"] = batch_quotability[i].get('quotability_score', 0)
                        query_params["is_quotable"] = batch_quotability[i].get('is_highly_quotable', False)
                    if i < len(batch_best_of):
                        query_params["best_of_category"] = batch_best_of[i].get('category', 'regular')
                    
                    # Save segment
                    tx.run("""
                    MERGE (s:Segment {id: $id})
                    SET s.text = $text,
                        s.start_time = $start_time,
                        s.end_time = $end_time,
                        s.speaker = $speaker,
                        s.episode_id = $episode_id,
                        s.segment_index = $index,
                        s.embedding = $embedding,
                        s.content_hash = $content_hash,
                        s.word_count = $word_count,
                        s.duration_seconds = $duration_seconds,
                        s.complexity_level = $complexity_level,
                        s.complexity_score = $complexity_score,
                        s.technical_density = $technical_density,
                        s.information_score = $information_score,
                        s.accessibility_score = $accessibility_score,
                        s.quotability_score = $quotability_score,
                        s.is_quotable = $is_quotable,
                        s.best_of_category = $best_of_category,
                        s.batch_processed = true,
                        s.processed_timestamp = datetime()
                    WITH s
                    MATCH (e:Episode {id: $episode_id})
                    MERGE (e)-[:HAS_SEGMENT]->(s)
                    """, query_params)
                    
            session.execute_write(save_batch)
            
        if not BATCH_MODE:
            print(f"Saved batch of {len(segments)} segments to Neo4j")
            
    except Exception as e:
        logger.error(f"Failed to save segment batch: {e}")
        raise

# ============================================================================
# PHASE 2.1: INPUT VALIDATION
# ============================================================================

def validate_text_input(text, field_name="text"):
    """Validate text input is not None or empty."""
    if text is None:
        logger.warning(f"{field_name} is None, using empty string")
        return ""
    if not isinstance(text, str):
        logger.warning(f"{field_name} is not string, converting: {type(text)}")
        return str(text)
    return text.strip()

def validate_date_format(date_str):
    """Validate and normalize date format with fallbacks."""
    if not date_str:
        return datetime.now().isoformat()
    
    try:
        from dateutil.parser import parse as date_parse
        # Try parsing with dateutil (handles many formats)
        parsed = date_parse(date_str)
        return parsed.isoformat()
    except ImportError:
        logger.warning("dateutil not available, using fallback date parsing")
    except:
        # Fallback patterns
        import re
        patterns = [
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', '%Y-%m-%d'),
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', '%m/%d/%Y'),
            (r'(\d{1,2})-(\d{1,2})-(\d{4})', '%m-%d-%Y'),
        ]
        
        for pattern, fmt in patterns:
            match = re.match(pattern, date_str)
            if match:
                try:
                    return datetime.strptime(match.group(0), fmt).isoformat()
                except:
                    pass
        
        logger.warning(f"Could not parse date: {date_str}, using current date")
        return datetime.now().isoformat()

def sanitize_file_path(path):
    """Sanitize file paths to prevent injection."""
    import re
    # Remove potentially dangerous characters
    safe_path = re.sub(r'[^\w\s\-_.\/]', '', str(path))
    # Remove double dots to prevent directory traversal
    safe_path = safe_path.replace('..', '')
    return safe_path

# ============================================================================
# PHASE 2.2: SMART ERROR RECOVERY
# ============================================================================

def with_retry(func, max_retries=3, backoff_factor=2):
    """Decorator for retrying transient failures with exponential backoff."""
    def wrapper(*args, **kwargs):
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed after {max_retries} attempts: {e}")
                    raise
                
                # Check if error is retryable
                error_str = str(e).lower()
                if any(x in error_str for x in ['rate limit', '429', 'timeout', 'connection']):
                    wait_time = backoff_factor ** attempt
                    logger.warning(f"Retryable error, waiting {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    # Non-retryable error
                    raise
        
    return wrapper

# ============================================================================
# PHASE 2.3: PROGRESS PERSISTENCE
# ============================================================================

class ProgressCheckpoint:
    """Enhanced checkpoint system for resumable processing."""
    
    def __init__(self, checkpoint_dir=None):
        self.checkpoint_dir = checkpoint_dir or PodcastConfig.CHECKPOINT_DIR
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        
    def save_episode_progress(self, episode_id, stage, data):
        """Save progress checkpoint for an episode."""
        checkpoint_file = os.path.join(self.checkpoint_dir, f"episode_{episode_id}_{stage}.pkl")
        
        checkpoint_data = {
            'episode_id': episode_id,
            'stage': stage,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        
        try:
            import pickle
            with open(checkpoint_file, 'wb') as f:
                pickle.dump(checkpoint_data, f)
            logger.info(f"Saved checkpoint: {stage} for episode {episode_id}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    def load_episode_progress(self, episode_id, stage):
        """Load progress checkpoint for an episode."""
        checkpoint_file = os.path.join(self.checkpoint_dir, f"episode_{episode_id}_{stage}.pkl")
        
        if not os.path.exists(checkpoint_file):
            return None
            
        try:
            import pickle
            with open(checkpoint_file, 'rb') as f:
                checkpoint_data = pickle.load(f)
            logger.info(f"Loaded checkpoint: {stage} for episode {episode_id}")
            return checkpoint_data['data']
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def get_completed_episodes(self):
        """Get list of completed episode IDs from checkpoints."""
        completed = set()
        
        try:
            for filename in os.listdir(self.checkpoint_dir):
                if filename.startswith('episode_') and '_complete.pkl' in filename:
                    episode_id = filename.split('_')[1]
                    completed.add(episode_id)
        except Exception as e:
            logger.error(f"Failed to list checkpoints: {e}")
            
        return list(completed)
    
    def clean_episode_checkpoints(self, episode_id):
        """Clean up intermediate checkpoints after successful completion."""
        try:
            for filename in os.listdir(self.checkpoint_dir):
                if filename.startswith(f'episode_{episode_id}_') and not filename.endswith('_complete.pkl'):
                    os.remove(os.path.join(self.checkpoint_dir, filename))
            logger.info(f"Cleaned intermediate checkpoints for episode {episode_id}")
        except Exception as e:
            logger.error(f"Failed to clean checkpoints: {e}")

# ============================================================================
# PHASE 3.3: REGEX OPTIMIZATION
# ============================================================================

class OptimizedPatternMatcher:
    """Pre-compiled regex patterns for better performance."""
    
    def __init__(self):
        import re
        
        # Pre-compile all patterns
        self.technical_patterns = [
            re.compile(r'\b\w+ology\b', re.IGNORECASE),
            re.compile(r'\b\w+itis\b', re.IGNORECASE),
            re.compile(r'\b\w+osis\b', re.IGNORECASE),
            re.compile(r'\b\w+ase\b', re.IGNORECASE),
            re.compile(r'\b\w+ide\b', re.IGNORECASE),
            re.compile(r'\b\w+ine\b', re.IGNORECASE),
            re.compile(r'\bneuro\w+\b', re.IGNORECASE),
            re.compile(r'\bcardio\w+\b', re.IGNORECASE),
            re.compile(r'\bhypo\w+\b', re.IGNORECASE),
            re.compile(r'\banti\w+\b', re.IGNORECASE),
            re.compile(r'\bmeta\w+\b', re.IGNORECASE),
            re.compile(r'\bpoly\w+\b', re.IGNORECASE),
            re.compile(r'\b[A-Z]{2,}\b'),
            re.compile(r'\b\d+\s*(?:mg|ml|μg|ng|mol|mM|μM)\b'),
            re.compile(r'\bp\s*[<>=]\s*0\.\d+\b'),
            re.compile(r'\b(?:alpha|beta|gamma|delta)\b', re.IGNORECASE),
            re.compile(r'\b(?:receptor|enzyme|protein|gene|pathway|mechanism)\b', re.IGNORECASE),
            re.compile(r'\b(?:hypothesis|theory|model|analysis|correlation)\b', re.IGNORECASE),
        ]
        
        self.fact_patterns = [
            re.compile(r'\b\d+(?:\.\d+)?%\b'),
            re.compile(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b'),
            re.compile(r'\b(?:study|research|survey|report) (?:shows?|finds?|suggests?|indicates?)\b', re.IGNORECASE),
            re.compile(r'\b(?:according to|based on|as per)\b', re.IGNORECASE),
            re.compile(r'\b(?:statistic|data|evidence|finding)\b', re.IGNORECASE),
            re.compile(r'\b(?:proven|demonstrated|established)\b', re.IGNORECASE),
            re.compile(r'\b(?:conclusion|result|outcome)\b', re.IGNORECASE),
        ]
        
        self.quotable_patterns = [
            re.compile(r'\b(?:the key|the secret|the most important)\b', re.IGNORECASE),
            re.compile(r'\b(?:always|never|every|none)\b', re.IGNORECASE),
            re.compile(r'\b(?:success|failure|mistake|lesson)\b', re.IGNORECASE),
            re.compile(r'\b(?:believe|think|know|realize)\b', re.IGNORECASE),
            re.compile(r'\b(?:if you|when you|you should|you must)\b', re.IGNORECASE),
            re.compile(r'\b(?:changed my|transformed|revolutionized)\b', re.IGNORECASE),
            re.compile(r'^\s*"[^"]+"\s*$'),
            re.compile(r'\b(?:is|are|means)\s+(?:that|to)\b', re.IGNORECASE),
        ]
    
    def count_technical_terms(self, text):
        """Count technical terms using pre-compiled patterns."""
        count = 0
        for pattern in self.technical_patterns:
            count += len(pattern.findall(text))
        return count
    
    def count_facts(self, text):
        """Count factual statements using pre-compiled patterns."""
        count = 0
        for pattern in self.fact_patterns:
            count += len(pattern.findall(text))
        return count
    
    def get_quotability_matches(self, text):
        """Get quotability pattern matches."""
        matches = 0
        for pattern in self.quotable_patterns:
            if pattern.search(text):
                matches += 1
        return matches

# Global instance for reuse
pattern_matcher = OptimizedPatternMatcher()

# ============================================================================
# PHASE 3.2: EFFICIENT ENTITY MATCHING
# ============================================================================

class VectorEntityMatcher:
    """Efficient entity matching using vector similarity."""
    
    def __init__(self, embedding_client=None):
        self.embedding_client = embedding_client
        self.entity_cache = {}
        self.entity_embeddings = None
        self.entity_names = []
        
    def build_entity_index(self, entities):
        """Build vector index for entities."""
        if not self.embedding_client or not entities:
            return
            
        try:
            # Cache entity names
            self.entity_names = [e['name'] for e in entities]
            
            # Generate embeddings for all entities
            embeddings = []
            for entity in entities:
                # Check cache first
                cache_key = f"entity_{entity['name']}"
                if cache_key in self.entity_cache:
                    embeddings.append(self.entity_cache[cache_key])
                else:
                    # Generate new embedding
                    emb = generate_embeddings(entity['name'], self.embedding_client)
                    embeddings.append(emb)
                    self.entity_cache[cache_key] = emb
            
            # Convert to numpy array for efficient operations
            import numpy as np
            self.entity_embeddings = np.array(embeddings)
            
            logger.info(f"Built entity index with {len(entities)} entities")
            
        except Exception as e:
            logger.error(f"Failed to build entity index: {e}")
            # Fall back to string matching
            self.entity_embeddings = None
    
    def find_entities_in_segment(self, segment_text, threshold=0.7):
        """Find entities in segment using vector similarity."""
        if not self.entity_embeddings or not self.embedding_client:
            # Fallback to simple string matching
            return self._string_match_fallback(segment_text)
        
        try:
            # Generate embedding for segment
            segment_embedding = generate_embeddings(segment_text, self.embedding_client)
            
            # Calculate cosine similarities
            import numpy as np
            segment_emb_array = np.array(segment_embedding)
            
            # Compute similarities
            similarities = np.dot(self.entity_embeddings, segment_emb_array) / (
                np.linalg.norm(self.entity_embeddings, axis=1) * np.linalg.norm(segment_emb_array)
            )
            
            # Find entities above threshold
            matched_indices = np.where(similarities > threshold)[0]
            matched_entities = [self.entity_names[i] for i in matched_indices]
            
            return matched_entities
            
        except Exception as e:
            logger.error(f"Vector matching failed: {e}")
            return self._string_match_fallback(segment_text)
    
    def _string_match_fallback(self, segment_text):
        """Fallback to string matching if vector matching fails."""
        segment_lower = segment_text.lower()
        return [name for name in self.entity_names if name.lower() in segment_lower]

# ============================================================================
# EPISODE METRICS CALCULATION FROM DB
# ============================================================================

def calculate_episode_metrics_from_db(neo4j_driver, episode_id):
    """Calculate episode-level metrics from saved segments."""
    if not neo4j_driver:
        return None, None, []
    
    try:
        with neo4j_driver.session() as session:
            # Query segment metrics
            result = session.run("""
            MATCH (e:Episode {id: $episode_id})-[:HAS_SEGMENT]->(s:Segment)
            RETURN 
                s.complexity_level as complexity_level,
                s.complexity_score as complexity_score,
                s.information_score as info_score,
                s.accessibility_score as access_score,
                s.quotability_score as quote_score,
                s.is_quotable as is_quotable,
                s.text as text,
                s.speaker as speaker,
                s.start_time as start_time,
                s.end_time as end_time
            ORDER BY s.segment_index
            """, episode_id=episode_id)
            
            segments_data = list(result)
            if not segments_data:
                return None, None, []
            
            # Calculate episode complexity
            complexity_scores = [record['complexity_score'] for record in segments_data if record['complexity_score'] is not None]
            complexity_levels = [record['complexity_level'] for record in segments_data if record['complexity_level'] is not None]
            
            if complexity_scores:
                avg_complexity = sum(complexity_scores) / len(complexity_scores)
                level_counts = {level: complexity_levels.count(level) for level in set(complexity_levels)}
                dominant_level = max(level_counts.items(), key=lambda x: x[1])[0] if level_counts else 'unknown'
                
                episode_complexity = {
                    'average_complexity': avg_complexity,
                    'dominant_level': dominant_level,
                    'complexity_distribution': {k: (v/len(complexity_levels)*100) for k, v in level_counts.items()}
                }
            else:
                episode_complexity = None
            
            # Calculate episode metrics
            info_scores = [record['info_score'] for record in segments_data if record['info_score'] is not None]
            access_scores = [record['access_score'] for record in segments_data if record['access_score'] is not None]
            
            episode_metrics = {
                'avg_information_score': sum(info_scores) / len(info_scores) if info_scores else 0,
                'avg_accessibility': sum(access_scores) / len(access_scores) if access_scores else 0
            }
            
            # Extract key quotes
            key_quotes = []
            for record in segments_data:
                if record['is_quotable']:
                    key_quotes.append({
                        'text': record['text'],
                        'speaker': record['speaker'],
                        'start_time': record['start_time'],
                        'end_time': record['end_time'],
                        'quotability_score': record['quote_score']
                    })
            
            # Sort by score and take top 10
            key_quotes.sort(key=lambda x: x['quotability_score'], reverse=True)
            key_quotes = key_quotes[:10]
            
            return episode_complexity, episode_metrics, key_quotes
            
    except Exception as e:
        logger.error(f"Failed to calculate episode metrics from DB: {e}")
        return None, None, []

# ============================================================================
# PHASE 4: QUALITY CONTROL
# ============================================================================

class ExtractionValidator:
    """Validate and clean extracted data."""
    
    def __init__(self, max_entities_per_segment=50, confidence_threshold=3):
        self.max_entities_per_segment = max_entities_per_segment
        self.confidence_threshold = confidence_threshold
        self.validation_stats = defaultdict(int)
    
    def validate_entities(self, entities, segment_text=None):
        """Validate and deduplicate entities."""
        if not entities:
            return []
        
        # Deduplicate by name (case-insensitive)
        seen_names = {}
        validated = []
        
        for entity in entities:
            # Validate required fields
            if not entity.get('name'):
                self.validation_stats['missing_name'] += 1
                continue
                
            name_lower = entity['name'].lower().strip()
            
            # Skip if duplicate
            if name_lower in seen_names:
                self.validation_stats['duplicate'] += 1
                # Merge importance scores
                existing = seen_names[name_lower]
                existing['importance'] = max(
                    existing.get('importance', 5),
                    entity.get('importance', 5)
                )
                continue
            
            # Validate entity quality
            if len(entity['name']) < 2 or len(entity['name']) > 100:
                self.validation_stats['invalid_length'] += 1
                continue
                
            # Add default values
            entity['type'] = entity.get('type', 'Concept')
            entity['importance'] = entity.get('importance', 5)
            entity['description'] = entity.get('description', '')[:500]  # Truncate long descriptions
            
            seen_names[name_lower] = entity
            validated.append(entity)
        
        # Limit entities per segment
        if segment_text and len(validated) > self.max_entities_per_segment:
            self.validation_stats['truncated'] += 1
            # Sort by importance and take top N
            validated.sort(key=lambda x: x.get('importance', 5), reverse=True)
            validated = validated[:self.max_entities_per_segment]
        
        return validated
    
    def validate_insights(self, insights):
        """Validate insights meet quality standards."""
        if not insights:
            return []
        
        validated = []
        seen_titles = set()
        
        for insight in insights:
            # Check required fields
            if not insight.get('title') or not insight.get('description'):
                self.validation_stats['insight_missing_fields'] += 1
                continue
            
            # Check confidence threshold
            if insight.get('confidence', 10) < self.confidence_threshold:
                self.validation_stats['low_confidence'] += 1
                continue
            
            # Deduplicate by title
            title_lower = insight['title'].lower().strip()
            if title_lower in seen_titles:
                self.validation_stats['duplicate_insight'] += 1
                continue
            
            # Validate category
            valid_categories = [
                "BusinessStrategy", "Technology", "Psychology", 
                "ProductDevelopment", "Marketing", "InvestmentInsight", 
                "CareerAdvice", "ProblemSolutionNarrative"
            ]
            if insight.get('category') not in valid_categories:
                insight['category'] = "ProblemSolutionNarrative"
            
            seen_titles.add(title_lower)
            validated.append(insight)
        
        return validated
    
    def validate_metrics(self, metrics_dict):
        """Ensure all metrics are within valid ranges."""
        validated = metrics_dict.copy()
        
        # Validate score ranges (0-100)
        score_fields = [
            'complexity_score', 'information_score', 'accessibility_score',
            'quotability_score', 'best_of_score', 'avg_complexity',
            'avg_information_score', 'avg_accessibility'
        ]
        
        for field in score_fields:
            if field in validated:
                value = validated[field]
                if not isinstance(value, (int, float)):
                    validated[field] = 0
                else:
                    validated[field] = max(0, min(100, value))
        
        # Validate density ranges (0-1)
        density_fields = ['technical_density', 'unique_ratio']
        for field in density_fields:
            if field in validated:
                value = validated[field]
                if not isinstance(value, (int, float)):
                    validated[field] = 0
                else:
                    validated[field] = max(0, min(1, value))
        
        return validated
    
    def get_validation_report(self):
        """Get validation statistics."""
        return dict(self.validation_stats)

# Global validator instance
extraction_validator = ExtractionValidator()

# ============================================================================
# SAVE EPISODE-LEVEL KNOWLEDGE
# ============================================================================

def save_episode_knowledge_to_neo4j(podcast_config, episode, insights, entities,
                                   neo4j_driver, embedding_client, 
                                   episode_complexity=None, episode_metrics=None,
                                   use_large_context=True, transcript_segments=None, 
                                   llm_client=None, quotes=None, topics=None):
    """Save episode-level knowledge (insights, entities) after segments are saved."""
    if not neo4j_driver:
        return
    
    database = PodcastConfig.NEO4J_DATABASE
    
    try:
        with neo4j_driver.session(database=database) as session:
            def save_episode_data(tx):
                # Create podcast and episode nodes
                create_podcast_nodes(tx, podcast_config)
                create_episode_nodes(tx, episode, podcast_config, episode_complexity, episode_metrics)
                
                # Save insights
                if insights:
                    create_insight_nodes(tx, insights, podcast_config, episode, 
                                       embedding_client, use_large_context)
                
                # Save entities
                if entities:
                    create_entity_nodes(tx, entities, podcast_config, episode,
                                      embedding_client, use_large_context)
                
                # Create cross-references
                if insights and entities and use_large_context:
                    create_cross_references(tx, entities, insights, podcast_config, episode, use_large_context)
                
                # Extract and save quotes if not provided
                if quotes is None and transcript_segments and llm_client:
                    all_quotes = []
                    for i, segment in enumerate(transcript_segments[:20]):  # Limit to first 20 segments for performance
                        segment_id = generate_stable_segment_id(
                            episode['id'], 
                            segment['text'], 
                            segment['start'],
                            segment.get('speaker')
                        )
                        segment_quotes = extract_notable_quotes(
                            segment['text'],
                            segment.get('speaker', 'Unknown'),
                            segment['start'],
                            segment['end'],
                            llm_client
                        )
                        if segment_quotes:
                            create_quote_nodes(tx, segment_quotes, segment_id, episode['id'], embedding_client)
                            all_quotes.extend(segment_quotes)
                    logger.info(f"Extracted {len(all_quotes)} quotes")
                elif quotes:
                    # Use provided quotes from combined extraction
                    # Need to match quotes to segments based on content
                    for quote in quotes:
                        # Find the segment containing this quote
                        quote_text_lower = quote.get('text', '').lower()
                        for segment in transcript_segments:
                            if quote_text_lower in segment['text'].lower():
                                segment_id = generate_stable_segment_id(
                                    episode['id'], 
                                    segment['text'], 
                                    segment['start'],
                                    segment.get('speaker')
                                )
                                # Create quote node with proper formatting
                                formatted_quote = {
                                    'text': quote.get('text', ''),
                                    'speaker': quote.get('speaker', segment.get('speaker', 'Unknown')),
                                    'impact_score': 7,  # Default score for pre-extracted quotes
                                    'quote_type': 'insight',
                                    'segment_start': segment['start'],
                                    'segment_end': segment['end'],
                                    'estimated_timestamp': segment['start'],  # Use segment start as estimate
                                    'word_count': len(quote.get('text', '').split())
                                }
                                create_quote_nodes(tx, [formatted_quote], segment_id, episode['id'], embedding_client)
                                break
                
                # Extract and save topics if not provided
                if topics is None and insights and entities:
                    topics = extract_episode_topics(
                        insights, 
                        entities, 
                        transcript_segments[:10] if transcript_segments else [],
                        llm_client
                    )
                    if topics:
                        created_topics = create_topic_nodes(tx, topics, episode['id'], podcast_config['id'])
                        update_episode_with_topics(tx, episode['id'], topics)
                        logger.info(f"Created {len(created_topics)} topic tags")
                elif topics:
                    # Use provided topics
                    created_topics = create_topic_nodes(tx, topics, episode['id'], podcast_config['id'])
                    update_episode_with_topics(tx, episode['id'], topics)
                    
            session.execute_write(save_episode_data)
            
        logger.info(f"Saved episode knowledge: {len(insights)} insights, {len(entities)} entities")
        
        # Compute similarity relationships as a post-processing step
        if use_large_context:
            try:
                with neo4j_driver.session(database=database) as session:
                    # Compute similarities for different node types
                    compute_similarity_relationships(session, 'Insight', 0.7, 5)
                    compute_similarity_relationships(session, 'Entity', 0.75, 5)
                    # Only compute segment similarities if we have a small number
                    if transcript_segments and len(transcript_segments) < 50:
                        compute_similarity_relationships(session, 'Segment', 0.8, 3)
                    logger.info("Computed similarity relationships")
            except Exception as e:
                logger.warning(f"Failed to compute similarities: {e}")
                # Don't fail the whole process if similarity computation fails
        
        # Create weighted co-occurrence relationships
        if entities and transcript_segments:
            try:
                logger.info("Creating weighted co-occurrence relationships...")
                co_occurrences = extract_weighted_co_occurrences(entities, transcript_segments)
                
                with neo4j_driver.session(database=database) as session:
                    # Need to map temporary entity IDs to actual entity names
                    entity_name_map = {}
                    for idx, entity in enumerate(entities):
                        temp_id = f"temp_entity_{idx}_{entity['name']}_{entity.get('type', 'unknown')}"
                        entity_name_map[temp_id] = {
                            'name': entity['name'],
                            'type': entity.get('type', 'unknown')
                        }
                    
                    for co_occ in co_occurrences:
                        # Get entity details from the map
                        entity1_info = entity_name_map.get(co_occ['entity1_id'], {})
                        entity2_info = entity_name_map.get(co_occ['entity2_id'], {})
                        
                        if entity1_info and entity2_info:
                            session.run("""
                            MATCH (e1:Entity {name: $entity1_name, type: $entity1_type, episode_id: $episode_id})
                            MATCH (e2:Entity {name: $entity2_name, type: $entity2_type, episode_id: $episode_id})
                            MERGE (e1)-[r:CO_OCCURS_WITH]-(e2)
                            SET r.weight = $weight,
                                r.occurrence_count = $count,
                                r.last_updated = datetime()
                            """, {
                                'entity1_name': entity1_info['name'],
                                'entity1_type': entity1_info['type'],
                                'entity2_name': entity2_info['name'],
                                'entity2_type': entity2_info['type'],
                                'episode_id': episode["id"],
                                'weight': co_occ['weight'],
                                'count': co_occ['occurrence_count']
                            })
                    logger.info(f"Created {len(co_occurrences)} weighted co-occurrence relationships")
            except Exception as e:
                logger.warning(f"Failed to create co-occurrence relationships: {e}")
        
        # Perform discourse analysis
        if ENABLE_GRAPH_ENHANCEMENTS and entities and insights:
            try:
                logger.info("Performing discourse analysis...")
                discourse_results = analyze_episode_discourse(
                    neo4j_driver, 
                    episode["id"], 
                    insights, 
                    entities, 
                    transcript_segments,
                    llm_client
                )
                logger.info(f"Discourse analysis complete: {discourse_results}")
            except Exception as e:
                logger.warning(f"Failed to perform discourse analysis: {e}")
                # Don't fail the whole process if discourse analysis fails
        
    except Exception as e:
        logger.error(f"Failed to save episode knowledge: {e}")
        raise

# ============================================================================
# KNOWLEDGE GRAPH PERSISTENCE - DECOMPOSED FUNCTIONS
# ============================================================================

def create_podcast_nodes(session, podcast_info):
    """Create or update podcast nodes in Neo4j."""
    try:
        session.run("""
        MERGE (p:Podcast {id: $id})
        ON CREATE SET 
            p.name = $name,
            p.description = $description,
            p.rss_url = $rss_url,
            p.created_timestamp = datetime()
        ON MATCH SET 
            p.name = $name,
            p.description = $description,
            p.rss_url = $rss_url,
            p.updated_timestamp = datetime()
        """, {
            "id": podcast_info["id"],
            "name": podcast_info["title"],
            "description": podcast_info["description"],
            "rss_url": podcast_info["rss_url"]
        })
        print(f"Created/updated podcast node: {podcast_info['title']}")
    except Exception as e:
        raise DatabaseConnectionError(f"Failed to create podcast node: {e}")

def create_episode_nodes(session, episode, podcast_info, episode_complexity=None, episode_metrics=None):
    """Create or update episode nodes in Neo4j with optional complexity and information density metrics."""
    try:
        query_params = {
            "id": episode["id"],
            "title": episode["title"],
            "description": episode["description"],
            "published_date": episode["published_date"],
            "podcast_id": podcast_info["id"]
        }
        
        # Add complexity and density metrics if available
        metrics_set_clause = ""
        if episode_complexity:
            query_params.update({
                "avg_complexity": episode_complexity.get('average_complexity', 0),
                "dominant_level": episode_complexity.get('dominant_level', 'unknown'),
                "technical_density": episode_complexity.get('technical_density', 0),
                "complexity_variance": episode_complexity.get('complexity_variance', 0),
                "is_mixed_complexity": episode_complexity.get('is_mixed_complexity', False),
                "is_technical": episode_complexity.get('is_technical', False),
                "layperson_pct": episode_complexity.get('complexity_distribution', {}).get('layperson', 0),
                "intermediate_pct": episode_complexity.get('complexity_distribution', {}).get('intermediate', 0),
                "expert_pct": episode_complexity.get('complexity_distribution', {}).get('expert', 0)
            })
            metrics_set_clause = """,
            e.avg_complexity = $avg_complexity,
            e.dominant_complexity_level = $dominant_level,
            e.technical_density = $technical_density,
            e.complexity_variance = $complexity_variance,
            e.is_mixed_complexity = $is_mixed_complexity,
            e.is_technical = $is_technical,
            e.layperson_percentage = $layperson_pct,
            e.intermediate_percentage = $intermediate_pct,
            e.expert_percentage = $expert_pct"""
        
        if episode_metrics:
            query_params.update({
                "avg_information_score": episode_metrics.get('avg_information_score', 0),
                "total_insights": episode_metrics.get('total_insights', 0),
                "total_entities": episode_metrics.get('total_entities', 0),
                "avg_accessibility": episode_metrics.get('avg_accessibility', 0),
                "information_variance": episode_metrics.get('information_variance', 0),
                "has_consistent_density": episode_metrics.get('has_consistent_density', False)
            })
            metrics_set_clause += """,
            e.avg_information_score = $avg_information_score,
            e.total_insights = $total_insights,
            e.total_entities = $total_entities,
            e.avg_accessibility = $avg_accessibility,
            e.information_variance = $information_variance,
            e.has_consistent_density = $has_consistent_density"""
        
        session.run(f"""
        MERGE (e:Episode {{id: $id}})
        ON CREATE SET 
            e.title = $title,
            e.description = $description,
            e.published_date = $published_date,
            e.podcast_id = $podcast_id,
            e.created_timestamp = datetime(){metrics_set_clause}
        ON MATCH SET 
            e.title = $title,
            e.description = $description,
            e.published_date = $published_date,
            e.podcast_id = $podcast_id,
            e.updated_timestamp = datetime(){metrics_set_clause}
        WITH e
        MATCH (p:Podcast {{id: $podcast_id}})
        MERGE (p)-[:HAS_EPISODE]->(e)
        """, query_params)
        
        print(f"Created/updated episode node: {episode['title']}")
        if episode_complexity:
            print(f"  - Complexity: {episode_complexity['dominant_level']} (avg score: {episode_complexity['average_complexity']:.2f})")
    except Exception as e:
        raise DatabaseConnectionError(f"Failed to create episode node: {e}")

def create_segment_nodes(session, transcript_segments, episode, embedding_client, segments_complexity=None, segments_info_density=None, segments_accessibility=None):
    """Create segment nodes in Neo4j with progress tracking and optional analysis metrics."""
    try:
        print(f"Creating {len(transcript_segments)} segment nodes...")
        
        for i, segment in enumerate(tqdm(transcript_segments, desc="Creating segments")):
            # Generate stable segment ID
            segment_id = generate_stable_segment_id(
                episode['id'], 
                segment['text'], 
                segment['start'],
                segment.get('speaker')
            )
            
            # Check if segment is an advertisement
            is_ad = _detect_advertisement_in_segment(segment["text"])
            
            # Generate embedding
            embedding = None
            if embedding_client:
                try:
                    # Clean segment text before embedding
                    cleaned_text = clean_segment_text_for_embedding(segment["text"])
                    embedding = generate_embeddings(cleaned_text, embedding_client)
                except Exception as e:
                    print(f"Warning: Failed to generate embedding for segment {i}: {e}")
            
            # Get metrics for this segment if available
            segment_complexity = segments_complexity[i] if segments_complexity and i < len(segments_complexity) else None
            segment_density = segments_info_density[i] if segments_info_density and i < len(segments_info_density) else None
            segment_accessibility = segments_accessibility[i] if segments_accessibility and i < len(segments_accessibility) else None
            
            # Build query parameters
            query_params = {
                "id": segment_id,
                "text": segment["text"],
                "start_time": segment["start"],
                "end_time": segment["end"],
                "speaker": segment.get("speaker", "Unknown"),
                "is_ad": is_ad,
                "episode_id": episode["id"],
                "index": i,
                "embedding": embedding,
                # Additional metadata for stable IDs
                "content_hash": segment_id.split('_')[-1],
                "word_count": len(segment["text"].split()),
                "duration_seconds": segment["end"] - segment["start"]
            }
            
            # Add all metrics if available
            metrics_set_clause = ""
            if segment_complexity:
                query_params.update({
                    "complexity_level": segment_complexity.get('classification', 'unknown'),
                    "complexity_score": segment_complexity.get('complexity_score', 0),
                    "technical_density": segment_complexity.get('technical_density', 0),
                    "technical_entity_count": segment_complexity.get('technical_entity_count', 0)
                })
                metrics_set_clause = """,
                s.complexity_level = $complexity_level,
                s.complexity_score = $complexity_score,
                s.technical_density = $technical_density,
                s.technical_entity_count = $technical_entity_count"""
            
            if segment_density:
                query_params.update({
                    "information_score": segment_density.get('information_score', 0),
                    "insight_density": segment_density.get('insight_density', 0),
                    "entity_density": segment_density.get('entity_density', 0),
                    "fact_density": segment_density.get('fact_density', 0)
                })
                metrics_set_clause += """,
                s.information_score = $information_score,
                s.insight_density = $insight_density,
                s.entity_density = $entity_density,
                s.fact_density = $fact_density"""
            
            if segment_accessibility:
                query_params.update({
                    "accessibility_score": segment_accessibility.get('accessibility_score', 0),
                    "avg_sentence_length": segment_accessibility.get('avg_sentence_length', 0),
                    "jargon_percentage": segment_accessibility.get('jargon_percentage', 0),
                    "explanation_quality": segment_accessibility.get('explanation_quality', 0),
                    "has_analogies": segment_accessibility.get('has_analogies', False),
                    "has_examples": segment_accessibility.get('has_examples', False)
                })
                metrics_set_clause += """,
                s.accessibility_score = $accessibility_score,
                s.avg_sentence_length = $avg_sentence_length,
                s.jargon_percentage = $jargon_percentage,
                s.explanation_quality = $explanation_quality,
                s.has_analogies = $has_analogies,
                s.has_examples = $has_examples"""
            
            # Create segment node
            session.run(f"""
            MERGE (s:Segment {{id: $id}})
            ON CREATE SET 
                s.text = $text,
                s.start_time = $start_time,
                s.end_time = $end_time,
                s.speaker = $speaker,
                s.is_advertisement = $is_ad,
                s.episode_id = $episode_id,
                s.segment_index = $index,
                s.embedding = $embedding,
                s.content_hash = $content_hash,
                s.word_count = $word_count,
                s.duration_seconds = $duration_seconds,
                s.created_timestamp = datetime(){metrics_set_clause}
            ON MATCH SET 
                s.text = $text,
                s.start_time = $start_time,
                s.end_time = $end_time,
                s.speaker = $speaker,
                s.is_advertisement = $is_ad,
                s.episode_id = $episode_id,
                s.segment_index = $index,
                s.embedding = $embedding,
                s.content_hash = $content_hash,
                s.word_count = $word_count,
                s.duration_seconds = $duration_seconds,
                s.updated_timestamp = datetime(){metrics_set_clause}
            WITH s
            MATCH (e:Episode {{id: $episode_id}})
            MERGE (e)-[:HAS_SEGMENT]->(s)
            """, query_params)
            
        print(f"Successfully created {len(transcript_segments)} segment nodes")
    except Exception as e:
        raise DatabaseConnectionError(f"Failed to create segment nodes: {e}")

def _detect_advertisement_in_segment(text):
    """Helper function to detect if a segment contains advertisement content."""
    segment_text = text.lower()
    ad_markers = [
        "sponsor", "sponsored by", "brought to you by", "discount code",
        "promo code", "offer code", "special offer", "limited time offer"
    ]
    return any(marker in segment_text for marker in ad_markers)

def create_insight_nodes(session, insights, podcast_info, episode, embedding_client, use_large_context=True):
    """Create insight nodes in Neo4j with enhanced properties."""
    try:
        print(f"Creating {len(insights)} insight nodes...")
        
        for insight in tqdm(insights, desc="Creating insights"):
            # Generate insight ID
            insight_text_for_hash = f"{podcast_info['id']}_{episode['id']}_{insight.get('insight_type', 'conceptual')}_{insight['title']}"
            insight_id = f"insight_{hashlib.sha256(insight_text_for_hash.encode()).hexdigest()[:28]}"
            
            # Generate embedding
            embedding = None
            if embedding_client:
                try:
                    # Context-aware embedding: include insight type
                    insight_type = insight.get('insight_type', 'conceptual')
                    insight_text = f"[{insight_type}] {insight['title']}: {insight['description']}"
                    embedding = generate_embeddings(insight_text, embedding_client)
                except Exception as e:
                    print(f"Warning: Failed to generate embedding for insight: {e}")
            
            # Prepare properties
            properties = {
                "id": insight_id,
                "title": insight["title"],
                "description": insight["description"],
                "insight_type": insight.get("insight_type", "conceptual"),
                "podcast_id": podcast_info["id"],
                "episode_id": episode["id"],
                "embedding": embedding
            }
            
            # Add large context properties
            if use_large_context:
                if "confidence" in insight:
                    properties["confidence"] = insight["confidence"]
                if "references" in insight:
                    properties["references"] = json.dumps(insight["references"])
            
            # Build dynamic query
            query = _build_insight_query(use_large_context, insight)
            
            # Create insight node
            session.run(query, properties)
            
            # Create relationship with episode
            session.run("""
            MATCH (insight:Insight {id: $insight_id})
            MATCH (episode:Episode {id: $episode_id})
            MERGE (insight)-[:EXTRACTED_FROM]->(episode)
            """, {
                "insight_id": insight_id,
                "episode_id": episode["id"]
            })
            
        print(f"Successfully created {len(insights)} insight nodes")
    except Exception as e:
        raise DatabaseConnectionError(f"Failed to create insight nodes: {e}")

def _build_insight_query(use_large_context, insight):
    """Helper function to build dynamic insight query based on context mode."""
    base_fields = """
        i.title = $title,
        i.description = $description,
        i.insight_type = $insight_type,
        i.podcast_id = $podcast_id,
        i.episode_id = $episode_id,
        i.embedding = $embedding,
    """
    
    extra_fields = ""
    if use_large_context and "confidence" in insight:
        extra_fields += "i.confidence = $confidence,\n"
    if use_large_context and "references" in insight:
        extra_fields += "i.references = $references,\n"
    
    return f"""
    MERGE (i:Insight {{id: $id}})
    ON CREATE SET 
        {base_fields}
        {extra_fields}
        i.created_timestamp = datetime()
    ON MATCH SET 
        {base_fields}
        {extra_fields}
        i.updated_timestamp = datetime()
    """

def create_entity_nodes(session, entities, podcast_info, episode, embedding_client, use_large_context=True):
    """Create entity nodes in Neo4j with enhanced properties and entity resolution."""
    try:
        print(f"Processing {len(entities)} entities with deduplication...")
        
        entities_created = 0
        entities_merged = 0
        
        for entity in tqdm(entities, desc="Creating entities"):
            # Normalize entity name
            normalized_name = normalize_entity_name(entity['name'])
            
            # Check for existing similar entities
            existing_matches = find_existing_entity(session, entity['name'], entity['type'])
            
            if existing_matches and existing_matches[0]['similarity'] >= 0.85:
                # Use existing entity
                best_match = existing_matches[0]
                entity_id = best_match['id']
                entities_merged += 1
                
                # Update the existing entity with any new information
                # Add the current name as an alias if it's different
                if best_match['similarity'] < 1.0:
                    session.run("""
                    MATCH (e:Entity {id: $entity_id})
                    SET e.aliases = CASE
                        WHEN $new_name IN COALESCE(e.aliases, [])
                        THEN e.aliases
                        ELSE COALESCE(e.aliases, []) + $new_name
                    END
                    """, {"entity_id": entity_id, "new_name": entity['name']})
                
                print(f"Merged '{entity['name']}' with existing entity '{best_match['name']}' (similarity: {best_match['similarity']:.2f})")
            else:
                # Create new entity with enhanced properties
                # Generate global ID (for future federation)
                entity_type = entity['type']
                global_entity_id = f"global_entity_{hashlib.sha256(f'{normalized_name}_{entity_type}'.encode()).hexdigest()[:28]}"
                # Generate local ID (podcast-specific)
                podcast_id = podcast_info["id"]
                entity_name = entity["name"]
                entity_id = f"entity_{hashlib.sha256(f'{podcast_id}_{entity_name}_{entity_type}'.encode()).hexdigest()[:28]}"
                entities_created += 1
            
            # Extract aliases from description
            aliases = extract_entity_aliases(entity['name'], entity.get('description', ''))
            
            # Generate embedding with context-aware text
            embedding = None
            if embedding_client:
                try:
                    # Context-aware embedding: include type and description
                    entity_text = f"{entity['type']}: {entity['name']}"
                    if entity.get('description'):
                        entity_text += f", {entity['description']}"
                    embedding = generate_embeddings(entity_text, embedding_client)
                except Exception as e:
                    print(f"Warning: Failed to generate embedding for entity {entity['name']}: {e}")
            
            # Prepare properties with new fields
            properties = {
                "id": entity_id,
                "global_id": global_entity_id if 'global_entity_id' in locals() else None,
                "name": entity["name"],
                "normalized_name": normalized_name,
                "aliases": aliases,
                "type": entity["type"],
                "podcast_id": podcast_info["id"],
                "episode_id": episode["id"],
                "source_podcasts": [podcast_info["id"]],  # Track which podcasts mention this entity
                "embedding": embedding,
                "confidence": entity.get("confidence", 0.8)  # Default confidence if not provided
            }
            
            # Add optional properties
            if entity.get("description"):
                properties["description"] = entity["description"]
            if use_large_context and "frequency" in entity:
                properties["frequency"] = entity["frequency"]
            if use_large_context and "importance" in entity:
                properties["importance"] = entity["importance"]
            
            # Build dynamic query
            query = _build_entity_query(use_large_context, entity)
            
            # Create entity node
            session.run(query, properties)
            
            # Create relationship with episode
            session.run("""
            MATCH (entity:Entity {id: $entity_id})
            MATCH (episode:Episode {id: $episode_id})
            MERGE (entity)-[:MENTIONED_IN]->(episode)
            """, {
                "entity_id": entity_id,
                "episode_id": episode["id"]
            })
            
        print(f"Entity deduplication complete: {entities_created} created, {entities_merged} merged with existing")
        print(f"Successfully processed {len(entities)} entities")
    except Exception as e:
        raise DatabaseConnectionError(f"Failed to create entity nodes: {e}")

def _build_entity_query(use_large_context, entity):
    """Helper function to build dynamic entity query with enhanced fields."""
    base_fields = """
        e.name = $name,
        e.normalized_name = $normalized_name,
        e.aliases = $aliases,
        e.type = $type,
        e.podcast_id = $podcast_id,
        e.episode_id = $episode_id,
        e.embedding = $embedding,
        e.confidence = $confidence,
    """
    
    # Handle global_id only if creating new entity
    global_id_fields = """
        e.global_id = COALESCE(e.global_id, $global_id),
    """
    
    # Handle source_podcasts array - append if already exists
    source_podcast_fields = """
        e.source_podcasts = CASE
            WHEN $podcast_id IN COALESCE(e.source_podcasts, [])
            THEN e.source_podcasts
            ELSE COALESCE(e.source_podcasts, []) + $podcast_id
        END,
    """
    
    optional_fields = ""
    if entity.get("description"):
        optional_fields += "e.description = $description,\n"
    
    extra_fields = ""
    if use_large_context and "frequency" in entity:
        extra_fields += """
        e.frequency = CASE
            WHEN e.frequency IS NULL OR $frequency > e.frequency THEN $frequency
            ELSE e.frequency
        END,
        """
    if use_large_context and "importance" in entity:
        extra_fields += """
        e.importance = CASE
            WHEN e.importance IS NULL OR $importance > e.importance THEN $importance
            ELSE e.importance
        END,
        """
    
    return f"""
    MERGE (e:Entity {{id: $id}})
    ON CREATE SET 
        {base_fields}
        {global_id_fields}
        {source_podcast_fields}
        {optional_fields}
        {extra_fields}
        e.created_timestamp = datetime()
    ON MATCH SET 
        {base_fields}
        {source_podcast_fields}
        {optional_fields}
        {extra_fields}
        e.updated_timestamp = datetime()
    """

def create_cross_references(session, entities, insights, podcast_info, episode, use_large_context=True):
    """Create cross-references between entities and insights."""
    if not use_large_context:
        return
        
    try:
        print("Creating cross-references between entities and insights...")
        
        for entity in tqdm(entities, desc="Cross-referencing"):
            for insight in insights:
                # Check if entity is mentioned in insight
                insight_text = f"{insight['title']} {insight['description']}".lower()
                if entity['name'].lower() in insight_text:
                    # Use the same entity ID generation logic as in create_entity_nodes
                    normalized_name = normalize_entity_name(entity['name'])
                    podcast_id = podcast_info['id']
                    entity_name = entity['name']
                    entity_type = entity['type']
                    entity_id = f"entity_{hashlib.sha256(f'{podcast_id}_{entity_name}_{entity_type}'.encode()).hexdigest()[:28]}"
                    insight_text_for_hash = f"{podcast_info['id']}_{episode['id']}_{insight.get('insight_type', 'conceptual')}_{insight['title']}"
                    insight_id = f"insight_{hashlib.sha256(insight_text_for_hash.encode()).hexdigest()[:28]}"
                    
                    # Create relationship with relevance score
                    relevance = min(1.0, len(entity['name']) / len(insight_text) * 10)
                    
                    session.run("""
                    MATCH (entity:Entity {id: $entity_id})
                    MATCH (insight:Insight {id: $insight_id})
                    MERGE (entity)-[r:RELATED_TO]->(insight)
                    ON CREATE SET r.relevance = $relevance
                    ON MATCH SET r.relevance = CASE
                        WHEN $relevance > r.relevance THEN $relevance
                        ELSE r.relevance
                    END
                    """, {
                        "entity_id": entity_id,
                        "insight_id": insight_id,
                        "relevance": relevance
                    })
                    
        print("Successfully created cross-references")
    except Exception as e:
        raise DatabaseConnectionError(f"Failed to create cross-references: {e}")

def create_quote_nodes(session, quotes, segment_id, episode_id, embedding_client):
    """
    Create Quote nodes in Neo4j.
    
    Args:
        session: Neo4j session
        quotes: List of quote dictionaries
        segment_id: Parent segment ID
        episode_id: Parent episode ID
        embedding_client: Client for generating embeddings
    """
    for quote in quotes:
        # Generate quote ID
        quote_hash = hashlib.sha256(f"{quote['text']}_{episode_id}".encode()).hexdigest()[:16]
        quote_id = f"quote_{quote_hash}"
        
        # Generate embedding for the quote
        embedding = None
        if embedding_client:
            quote_context = f"{quote['quote_type']} quote: {quote['text']}"
            embedding = generate_embeddings(quote_context, embedding_client)
        
        # Create quote node
        session.run("""
        MERGE (q:Quote {id: $id})
        SET q.text = $text,
            q.speaker = $speaker,
            q.impact_score = $impact_score,
            q.quote_type = $quote_type,
            q.estimated_timestamp = $timestamp,
            q.word_count = $word_count,
            q.embedding = $embedding,
            q.episode_id = $episode_id
        WITH q
        MATCH (s:Segment {id: $segment_id})
        MERGE (q)-[:EXTRACTED_FROM]->(s)
        WITH q, s
        MATCH (e:Episode {id: $episode_id})
        MERGE (q)-[:QUOTED_IN]->(e)
        """, {
            "id": quote_id,
            "text": quote["text"],
            "speaker": quote["speaker"],
            "impact_score": quote["impact_score"],
            "quote_type": quote["quote_type"],
            "timestamp": quote["estimated_timestamp"],
            "word_count": quote["word_count"],
            "embedding": embedding,
            "segment_id": segment_id,
            "episode_id": episode_id
        })

def create_topic_nodes(session, topics, episode_id, podcast_id):
    """
    Create Topic nodes and relationships in Neo4j.
    
    Args:
        session: Neo4j session
        topics: List of topic dictionaries
        episode_id: Episode identifier
        podcast_id: Podcast identifier
    """
    created_topics = []
    
    for topic in topics:
        # Create topic ID (global across podcasts)
        topic_id = f"topic_{hashlib.sha256(topic['name'].encode()).hexdigest()[:16]}"
        
        # Create or update topic node
        session.run("""
        MERGE (t:Topic {id: $id})
        ON CREATE SET 
            t.name = $name,
            t.created_at = datetime(),
            t.episode_count = 0,
            t.total_score = 0
        SET t.episode_count = t.episode_count + 1,
            t.total_score = t.total_score + $score,
            t.avg_score = t.total_score / t.episode_count,
            t.last_seen = datetime()
        """, {
            "id": topic_id,
            "name": topic['name'],
            "score": topic['raw_score']
        })
        
        # Create relationship to episode
        session.run("""
        MATCH (e:Episode {id: $episode_id})
        MATCH (t:Topic {id: $topic_id})
        MERGE (e)-[r:HAS_TOPIC]->(t)
        SET r.score = $score,
            r.evidence = $evidence
        """, {
            "episode_id": episode_id,
            "topic_id": topic_id,
            "score": topic['score'],
            "evidence": topic['evidence']
        })
        
        # Create relationship to podcast
        session.run("""
        MATCH (p:Podcast {id: $podcast_id})
        MATCH (t:Topic {id: $topic_id})
        MERGE (p)-[r:COVERS_TOPIC]->(t)
        ON CREATE SET r.episode_count = 1, r.total_score = $score
        ON MATCH SET 
            r.episode_count = r.episode_count + 1,
            r.total_score = r.total_score + $score,
            r.avg_score = r.total_score / r.episode_count
        """, {
            "podcast_id": podcast_id,
            "topic_id": topic_id,
            "score": topic['raw_score']
        })
        
        created_topics.append(topic['name'])
    
    return created_topics

def update_episode_with_topics(session, episode_id, topics):
    """
    Update episode node with aggregated topic information.
    
    Args:
        session: Neo4j session
        episode_id: Episode identifier
        topics: List of topic dictionaries
    """
    # Extract primary topics (score > 0.5)
    primary_topics = [t['name'] for t in topics if t['score'] > 0.5]
    all_topic_names = [t['name'] for t in topics]
    
    # Update episode with topic metadata
    session.run("""
    MATCH (e:Episode {id: $episode_id})
    SET e.primary_topics = $primary_topics,
        e.all_topics = $all_topics,
        e.topic_count = size($all_topics),
        e.topic_diversity = size($primary_topics) * 1.0 / size($all_topics)
    """, {
        "episode_id": episode_id,
        "primary_topics": primary_topics,
        "all_topics": all_topic_names
    })

def compute_similarity_relationships(session, node_type='Insight', similarity_threshold=0.7, top_n=5):
    """
    Pre-compute similarity relationships between nodes with embeddings.
    
    Args:
        session: Neo4j session
        node_type: Type of node to compute similarities for ('Insight', 'Entity', 'Segment')
        similarity_threshold: Minimum similarity score to create relationship
        top_n: Maximum number of similar nodes to connect
    """
    print(f"Computing similarity relationships for {node_type} nodes...")
    
    # Use built-in gds.similarity.cosine if available, otherwise use custom calculation
    try:
        # Try using GDS library
        result = session.run(f"""
        MATCH (n:{node_type})
        WHERE n.embedding IS NOT NULL
        WITH n, count(*) as total
        MATCH (other:{node_type})
        WHERE other.embedding IS NOT NULL 
          AND n.id < other.id
          AND n.episode_id = other.episode_id
        WITH n, other, 
             gds.similarity.cosine(n.embedding, other.embedding) AS similarity
        WHERE similarity >= $threshold
        WITH n, other, similarity
        ORDER BY n.id, similarity DESC
        WITH n, collect({{id: other.id, similarity: similarity}})[..$top_n] as top_similar
        UNWIND top_similar as sim_node
        MATCH (target:{node_type} {{id: sim_node.id}})
        MERGE (n)-[r:SIMILAR_TO]->(target)
        SET r.score = sim_node.similarity,
            r.computed_at = datetime()
        RETURN count(r) as relationships_created
        """, {"threshold": similarity_threshold, "top_n": top_n})
        
    except:
        # Fallback to manual calculation
        print(f"GDS not available, using manual similarity calculation...")
        
        # For each node, find similar nodes
        nodes_result = session.run(f"""
        MATCH (n:{node_type})
        WHERE n.embedding IS NOT NULL
        RETURN n.id as id, n.embedding as embedding, n.episode_id as episode_id
        """)
        
        nodes = list(nodes_result)
        relationships_created = 0
        
        for i, node1 in enumerate(nodes):
            similar_nodes = []
            
            for j, node2 in enumerate(nodes):
                if i >= j or node1['episode_id'] != node2['episode_id']:
                    continue
                    
                # Calculate cosine similarity
                embedding1 = node1['embedding']
                embedding2 = node2['embedding']
                
                # Simple cosine similarity calculation
                dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
                magnitude1 = sum(a * a for a in embedding1) ** 0.5
                magnitude2 = sum(a * a for a in embedding2) ** 0.5
                
                if magnitude1 * magnitude2 > 0:
                    similarity = dot_product / (magnitude1 * magnitude2)
                    
                    if similarity >= similarity_threshold:
                        similar_nodes.append({
                            'id': node2['id'],
                            'similarity': similarity
                        })
            
            # Sort by similarity and take top N
            similar_nodes.sort(key=lambda x: x['similarity'], reverse=True)
            
            for sim_node in similar_nodes[:top_n]:
                session.run(f"""
                MATCH (n:{node_type} {{id: $id1}})
                MATCH (other:{node_type} {{id: $id2}})
                MERGE (n)-[r:SIMILAR_TO]->(other)
                SET r.score = $similarity,
                    r.computed_at = datetime()
                """, {
                    "id1": node1['id'],
                    "id2": sim_node['id'],
                    "similarity": sim_node['similarity']
                })
                relationships_created += 1
        
        result = [{'relationships_created': relationships_created}]
    
    rel_count = result[0]["relationships_created"] if result else 0
    print(f"Created {rel_count} similarity relationships for {node_type} nodes")

def save_knowledge_to_neo4j(podcast_info, episode, transcript_segments, insights, entities, neo4j_driver, embedding_client, use_large_context=True, segments_complexity=None, episode_complexity=None, segments_info_density=None, segments_accessibility=None, episode_metrics=None):
    """
    Save knowledge graph to Neo4j using decomposed functions with transaction management.
    
    Args:
        podcast_info: Podcast information
        episode: Episode information  
        transcript_segments: Transcript segments
        insights: Extracted insights
        entities: Detected entities
        neo4j_driver: Neo4j driver
        embedding_client: OpenAI client for embeddings
        use_large_context: Whether large context processing was used
        
    Raises:
        DatabaseConnectionError: If Neo4j operations fail
        ConfigurationError: If required data is missing
    """
    if not neo4j_driver:
        raise ConfigurationError("Neo4j driver not available. Cannot save knowledge graph.")
    
    # Validate required data
    if not podcast_info or not episode:
        raise ConfigurationError("Podcast info and episode data are required")
    
    database = PodcastConfig.NEO4J_DATABASE
    
    # Phase 1.3: Transaction Management Implementation
    def execute_in_transaction(tx):
        """Execute all operations in a single transaction."""
        # Log transaction start
        logger.info(f"Starting transaction for episode: {episode['title']}")
        
        try:
            # Create nodes in logical order with progress tracking
            create_podcast_nodes(tx, podcast_info)
            create_episode_nodes(tx, episode, podcast_info, episode_complexity, episode_metrics)
            
            if transcript_segments:
                create_segment_nodes(tx, transcript_segments, episode, embedding_client, 
                                   segments_complexity, segments_info_density, segments_accessibility)
            
            if insights:
                create_insight_nodes(tx, insights, podcast_info, episode, embedding_client, use_large_context)
            
            if entities:
                create_entity_nodes(tx, entities, podcast_info, episode, embedding_client, use_large_context)
                
            # Create cross-references for enhanced knowledge graph
            if insights and entities and use_large_context:
                create_cross_references(tx, entities, insights, podcast_info, episode, use_large_context)
                
            logger.info(f"Transaction successful for episode: {episode['title']}")
            return True
            
        except Exception as e:
            logger.error(f"Transaction failed for episode {episode['title']}: {e}")
            raise  # Will trigger automatic rollback
    
    try:
        print(f"Saving knowledge graph for episode: {episode['title']}")
        
        with neo4j_driver.session(database=database) as session:
            # Execute all operations in a transaction
            result = session.execute_write(execute_in_transaction)
            
        print(f"Successfully saved knowledge graph for episode: {episode['title']}")
        
        # Clean up memory after processing
        cleanup_memory()
        
    except DatabaseConnectionError:
        raise
    except Exception as e:
        raise DatabaseConnectionError(f"Failed to save knowledge graph: {e}")

# ============================================================================
# KNOWLEDGE GRAPH ENHANCEMENTS
# ============================================================================

class RelationshipExtractor:
    """
    Extracts different types of relationships from text using LLM.
    Handles relationship type detection, directional processing,
    strength assessment, and conditional relationships.
    """
    
    def __init__(self, llm_client):
        """
        Initialize relationship extractor with LLM client.
        
        Args:
            llm_client: LLM client for relationship extraction
        """
        self.llm_client = llm_client
        self.relationship_taxonomy = {
            "hierarchical": ["is-a", "has-part", "belongs-to"],
            "influential": ["causes", "enables", "prevents"],
            "comparative": ["similar-to", "different-from", "better-than"],
            "temporal": ["precedes", "follows", "during"],
            "functional": ["uses", "requires", "produces"]
        }
        
    def extract_relationships(self, text, entities):
        """
        Extract relationships from text using LLM.
        
        Args:
            text: Text to extract relationships from
            entities: List of entities to connect with relationships
            
        Returns:
            List of extracted relationships with their properties
        """
        # Skip empty text or if there are fewer than 2 entities (can't form relationships)
        if not text or len(entities) < 2:
            return []
            
        # Create a list of entity names for the prompt
        entity_names = [entity["name"] for entity in entities]
        
        # Build relationship extraction prompt
        prompt = self._build_relationship_extraction_prompt(text, entity_names)
        
        try:
            # Get response from LLM
            response = self.llm_client.invoke(prompt)
            relationships = self._parse_relationship_response(response.content, entities)
            return relationships
            
        except Exception as e:
            print(f"Error extracting relationships: {e}")
            return []
            
    def _build_relationship_extraction_prompt(self, text, entity_names):
        """
        Build prompt for relationship extraction.
        
        Args:
            text: Text to extract relationships from
            entity_names: List of entity names
            
        Returns:
            Formatted prompt for the LLM
        """
        relationship_types = ", ".join([f"{k} ({', '.join(v)})" for k, v in self.relationship_taxonomy.items()])
        
        prompt = f"""
        Extract relationships between entities in the provided text. 

        TEXT:
        {text}
        
        ENTITIES:
        {", ".join(entity_names)}
        
        RELATIONSHIP TYPES:
        {relationship_types}
        
        Instructions:
        1. Identify relationships between the listed entities in the text
        2. For each relationship, determine:
           - Subject entity (the source)
           - Object entity (the target)
           - Relationship type (from the taxonomy above)
           - Relationship direction (is it one-way or bidirectional)
           - Relationship strength (0-100%) based on certainty indicators
           - Whether the relationship is conditional (has conditions attached)
           - Any condition text if the relationship is conditional
        
        Format your response as valid JSON list of objects with these fields:
        - subject: The subject entity name (source)
        - object: The object entity name (target)
        - type: The relationship type
        - subtype: The specific subtype (e.g., "is-a" for hierarchical)
        - bidirectional: Boolean indicating if relationship goes both ways
        - strength: Number from 0-100 indicating relationship strength/certainty
        - conditional: Boolean indicating if relationship has conditions
        - condition: The condition text (only if conditional is true)
        
        Only include relationships that are clearly mentioned in the text.
        
        JSON RESPONSE:
        """
        
        return prompt
        
    def _parse_relationship_response(self, response_text, entities):
        """
        Parse LLM response into structured relationships.
        
        Args:
            response_text: LLM response text
            entities: List of entities to match with relationship subjects/objects
            
        Returns:
            List of structured relationship objects
        """
        try:
            # Clean up response to extract JSON
            response_lines = response_text.strip().split('\n')
            json_lines = []
            in_json = False
            
            for line in response_lines:
                if line.strip() == "```json" or line.strip() == "```":
                    in_json = not in_json
                    continue
                if in_json or "[" in line or "{" in line:
                    json_lines.append(line)
            
            clean_json = '\n'.join(json_lines)
            
            # Handle empty responses
            if not clean_json.strip():
                return []
                
            # Parse JSON
            relationships = json.loads(clean_json)
            
            # Post-process relationships
            processed_relationships = []
            entity_lookup = {entity["name"].lower(): entity for entity in entities}
            
            for rel in relationships:
                # Skip relationships where entities don't match our known entities
                subject_name = rel.get("subject", "").lower()
                object_name = rel.get("object", "").lower()
                
                if subject_name not in entity_lookup or object_name not in entity_lookup:
                    continue
                    
                # Get entity IDs
                subject_entity = entity_lookup[subject_name]
                object_entity = entity_lookup[object_name]
                
                # Create relationship object
                relationship = {
                    "source_id": subject_entity["id"],
                    "target_id": object_entity["id"],
                    "source_name": subject_entity["name"],
                    "target_name": object_entity["name"],
                    "type": rel.get("type", "unknown"),
                    "subtype": rel.get("subtype", ""),
                    "bidirectional": rel.get("bidirectional", False),
                    "strength": rel.get("strength", 50),  # Default to 50% if not specified
                    "conditional": rel.get("conditional", False),
                    "condition": rel.get("condition", "") if rel.get("conditional", False) else ""
                }
                
                processed_relationships.append(relationship)
                
            return processed_relationships
            
        except Exception as e:
            print(f"Error parsing relationship response: {e}")
            return []
            
    def save_relationships_to_neo4j(self, neo4j_driver, relationships):
        """
        Save extracted relationships to Neo4j.
        
        Args:
            neo4j_driver: Neo4j driver
            relationships: List of relationships to save
            
        Returns:
            Number of relationships saved
        """
        if not neo4j_driver or not relationships:
            return 0
            
        # Get database name
        database = os.environ.get("NEO4J_DATABASE", "neo4j")
        saved_count = 0
        
        try:
            with neo4j_driver.session(database=database) as session:
                for rel in relationships:
                    # Create relationship with properties
                    query = """
                    MATCH (source:Entity {id: $source_id}), (target:Entity {id: $target_id})
                    MERGE (source)-[r:`RELATIONSHIP_` + $type {subtype: $subtype}]->(target)
                    ON CREATE SET 
                        r.created_timestamp = datetime(),
                        r.bidirectional = $bidirectional,
                        r.strength = $strength,
                        r.conditional = $conditional,
                        r.condition = $condition
                    ON MATCH SET 
                        r.updated_timestamp = datetime(),
                        r.bidirectional = $bidirectional,
                        r.strength = $strength,
                        r.conditional = $conditional,
                        r.condition = $condition
                    RETURN r
                    """
                    
                    result = session.run(query, {
                        "source_id": rel["source_id"],
                        "target_id": rel["target_id"],
                        "type": rel["type"].upper(),
                        "subtype": rel["subtype"],
                        "bidirectional": rel["bidirectional"],
                        "strength": rel["strength"],
                        "conditional": rel["conditional"],
                        "condition": rel["condition"]
                    })
                    
                    if result.peek():
                        saved_count += 1
                        
                    # Create reverse relationship if bidirectional
                    if rel["bidirectional"]:
                        query = """
                        MATCH (source:Entity {id: $target_id}), (target:Entity {id: $source_id})
                        MERGE (source)-[r:`RELATIONSHIP_` + $type {subtype: $subtype}]->(target)
                        ON CREATE SET 
                            r.created_timestamp = datetime(),
                            r.bidirectional = $bidirectional,
                            r.strength = $strength,
                            r.conditional = $conditional,
                            r.condition = $condition
                        ON MATCH SET 
                            r.updated_timestamp = datetime(),
                            r.bidirectional = $bidirectional,
                            r.strength = $strength,
                            r.conditional = $conditional,
                            r.condition = $condition
                        RETURN r
                        """
                        
                        result = session.run(query, {
                            "source_id": rel["source_id"],
                            "target_id": rel["target_id"],
                            "type": rel["type"].upper(),
                            "subtype": rel["subtype"],
                            "bidirectional": rel["bidirectional"],
                            "strength": rel["strength"],
                            "conditional": rel["conditional"],
                            "condition": rel["condition"]
                        })
                        
                        if result.peek():
                            saved_count += 1
                            
            return saved_count
            
        except Exception as e:
            print(f"Error saving relationships to Neo4j: {e}")
            return 0
            
    def process_episode_relationships(self, neo4j_driver, episode_id):
        """
        Process relationships for a specific episode.
        
        Args:
            neo4j_driver: Neo4j driver
            episode_id: Episode ID
            
        Returns:
            Number of relationships extracted
        """
        if not neo4j_driver:
            print("Neo4j driver not available. Cannot process relationships.")
            return 0
            
        # Get database name
        database = os.environ.get("NEO4J_DATABASE", "neo4j")
        
        try:
            with neo4j_driver.session(database=database) as session:
                # Get segments and entities for the episode
                result = session.run("""
                MATCH (ep:Episode {id: $episode_id})-[:HAS_SEGMENT]->(s:Segment)
                MATCH (e:Entity)-[:MENTIONED_IN]->(ep)
                RETURN collect(distinct s) as segments, collect(distinct e) as entities
                """, {"episode_id": episode_id})
                
                record = result.single()
                if not record:
                    return 0
                    
                segments = record["segments"]
                entities = record["entities"]
                
                if not segments or not entities or len(entities) < 2:
                    return 0
                    
                # Process each segment for relationships
                total_relationships = []
                for segment in segments:
                    # Get entities mentioned in this segment specifically
                    segment_text = segment["text"]
                    segment_entities = []
                    
                    for entity in entities:
                        if entity["name"].lower() in segment_text.lower():
                            segment_entities.append(entity)
                            
                    # Extract relationships from segment text
                    relationships = self.extract_relationships(segment_text, segment_entities)
                    total_relationships.extend(relationships)
                    
                # Save relationships to Neo4j
                saved_count = self.save_relationships_to_neo4j(neo4j_driver, total_relationships)
                print(f"Extracted and saved {saved_count} relationships for episode {episode_id}")
                
                return saved_count
                
        except Exception as e:
            print(f"Error processing episode relationships: {e}")
            return 0

def extract_relationship_network(neo4j_driver, llm_client, podcast_id=None):
    """
    Extract and build a relationship network for all entities.
    
    Args:
        neo4j_driver: Neo4j driver
        llm_client: LLM client
        podcast_id: Optional podcast ID to limit processing scope
        
    Returns:
        Number of relationships extracted
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot extract relationships.")
        return 0
        
    try:
        # Initialize relationship extractor
        relationship_extractor = RelationshipExtractor(llm_client)
        
        # Get database name
        database = os.environ.get("NEO4J_DATABASE", "neo4j")
        
        with neo4j_driver.session(database=database) as session:
            # Get all episodes (optionally filtered by podcast)
            if podcast_id:
                query = """
                MATCH (p:Podcast {id: $podcast_id})-[:HAS_EPISODE]->(e:Episode)
                RETURN e.id as episode_id
                """
                params = {"podcast_id": podcast_id}
            else:
                query = """
                MATCH (e:Episode)
                RETURN e.id as episode_id
                """
                params = {}
                
            result = session.run(query, params)
            episodes = [record["episode_id"] for record in result]
            
            # Process each episode
            total_relationships = 0
            for episode_id in episodes:
                relationships_count = relationship_extractor.process_episode_relationships(neo4j_driver, episode_id)
                total_relationships += relationships_count
                
            print(f"Total relationships extracted: {total_relationships}")
            return total_relationships
            
    except Exception as e:
        print(f"Error extracting relationship network: {e}")
        return 0
def enhance_knowledge_relationships(neo4j_driver, llm_client):
    """
    Enhance knowledge relationships in the graph with semantic connections.
    
    Args:
        neo4j_driver: Neo4j driver
        llm_client: LLM client
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot enhance knowledge relationships.")
        return
        
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        with neo4j_driver.session(database=database) as session:
            # Create semantic relationships between insights
            session.run("""
            MATCH (i1:Insight), (i2:Insight)
            WHERE i1.id <> i2.id AND i1.category = i2.category
            WITH i1, i2, apoc.text.similarity(i1.title, i2.title) AS similarity
            WHERE similarity > 0.5
            MERGE (i1)-[:SIMILAR_CONCEPT {strength: similarity}]->(i2)
            """)
            
            # Add temporal relationships between episodes in a series
            session.run("""
            MATCH (e1:Episode), (e2:Episode)
            WHERE e1.podcast_id = e2.podcast_id 
              AND datetime(e1.published_date) < datetime(e2.published_date)
            WITH e1, e2, duration.between(datetime(e1.published_date), datetime(e2.published_date)) as time_between
            WHERE time_between.days < 90  // Within 3 months
            MERGE (e1)-[:PRECEDED_BY {days_apart: time_between.days}]->(e2)
            """)
            
            # Connect entities mentioned together in segments (co-occurrence)
            session.run("""
            MATCH (s:Segment)<-[:HAS_SEGMENT]-(e:Episode)
            MATCH (ent1:Entity)-[:MENTIONED_IN]->(e)
            MATCH (ent2:Entity)-[:MENTIONED_IN]->(e)
            WHERE ent1.id <> ent2.id AND toLower(s.text) CONTAINS toLower(ent1.name) 
              AND toLower(s.text) CONTAINS toLower(ent2.name)
            MERGE (ent1)-[r:MENTIONED_WITH]->(ent2)
            ON CREATE SET r.count = 1
            ON MATCH SET r.count = r.count + 1
            """)
            
            # Create LLM-inferred CONTRADICTS/SUPPORTS/EXPANDS_ON relationships (sample 100 pairs)
            result = session.run("""
            MATCH (i1:Insight), (i2:Insight)
            WHERE i1.id <> i2.id AND i1.category = i2.category
              AND NOT (i1)-[:CONTRADICTS|SUPPORTS|EXPANDS_ON]-(i2)
            RETURN i1.id as id1, i1.title as title1, i1.description as desc1,
                   i2.id as id2, i2.title as title2, i2.description as desc2
            LIMIT 100
            """)
            
            for record in result:
                prompt = f"""
                Analyze these two insights and determine their relationship:
                
                Insight 1: {record['title1']} - {record['desc1']}
                Insight 2: {record['title2']} - {record['desc2']}
                
                What is the relationship between these insights? Choose exactly one:
                - SUPPORTS (insight 2 provides evidence for or enhances insight 1)
                - CONTRADICTS (insight 2 opposes or challenges insight 1)
                - EXPANDS_ON (insight 2 adds more detail or context to insight 1)
                - UNRELATED (no significant relationship)
                
                Return only one word: SUPPORTS, CONTRADICTS, EXPANDS_ON, or UNRELATED
                """
                
                response = llm_client.invoke(prompt)
                relationship = response.content.strip().upper()
                
                if relationship in ["SUPPORTS", "CONTRADICTS", "EXPANDS_ON"]:
                    session.run(f"""
                    MATCH (i1:Insight {{id: $id1}}), (i2:Insight {{id: $id2}})
                    MERGE (i1)-[:{relationship}]->(i2)
                    """, {"id1": record["id1"], "id2": record["id2"]})
                    
            print("Enhanced knowledge relationships successfully")
            
    except Exception as e:
        print(f"Error enhancing knowledge relationships: {e}")

def expand_knowledge_graph(neo4j_driver, llm_client, embedding_client):
    """
    Expand knowledge graph with entity resolution and external knowledge.
    
    Args:
        neo4j_driver: Neo4j driver
        llm_client: LLM client
        embedding_client: OpenAI client for embeddings
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot expand knowledge graph.")
        return
        
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        # Entity resolution - merge duplicate entities across episodes
        with neo4j_driver.session(database=database) as session:
            # Find potential duplicate entities with similar names
            result = session.run("""
            MATCH (e1:Entity), (e2:Entity)
            WHERE e1.id <> e2.id AND e1.type = e2.type
              AND apoc.text.fuzzyMatch(e1.name, e2.name) > 0.8
            RETURN e1.id as id1, e1.name as name1, e2.id as id2, e2.name as name2
            """)
            
            for record in result:
                # Use LLM to confirm if entities are indeed the same
                prompt = f"""
                Are these two entities the same? 
                Entity 1: {record['name1']} ({record['id1']})
                Entity 2: {record['name2']} ({record['id2']})
                
                Answer with YES or NO only.
                """
                
                response = llm_client.invoke(prompt)
                if "YES" in response.content.upper():
                    # Merge the entities
                    session.run("""
                    MATCH (e1:Entity {id: $id1}), (e2:Entity {id: $id2})
                    CALL apoc.refactor.mergeNodes([e1, e2], {
                        properties: {
                            name: 'combine',
                            description: 'combine',
                            frequency: 'sum',
                            importance: 'max'
                        },
                        mergeRels: true
                    })
                    YIELD node
                    RETURN node
                    """, {"id1": record["id1"], "id2": record["id2"]})
            
            # Add external knowledge enrichment for key entities (top 20 by importance)
            top_entities = session.run("""
            MATCH (e:Entity)
            RETURN e.id as id, e.name as name, e.type as type
            ORDER BY e.importance DESC
            LIMIT 20
            """)
            
            for entity in top_entities:
                # Fetch external knowledge about entity
                prompt = f"""
                Give me a comprehensive but concise description of {entity['name']} ({entity['type']}).
                Include key facts, significance, and relationships to other concepts.
                Keep it under 250 words and focus on objective information.
                """
                
                enrichment = llm_client.invoke(prompt)
                
                # Update entity with enriched knowledge
                session.run("""
                MATCH (e:Entity {id: $id})
                SET e.enriched_description = $description,
                    e.knowledge_enriched = true
                """, {"id": entity["id"], "description": enrichment.content})
                
                # Generate embedding for the enriched description
                if embedding_client:
                    enriched_embedding = generate_embeddings(enrichment.content, embedding_client)
                    if enriched_embedding:
                        session.run("""
                        MATCH (e:Entity {id: $id})
                        SET e.enriched_embedding = $embedding
                        """, {"id": entity["id"], "embedding": enriched_embedding})
                        
            print("Expanded knowledge graph successfully")
            
    except Exception as e:
        print(f"Error expanding knowledge graph: {e}")

def build_cross_episode_relationships(neo4j_driver, llm_client):
    """
    Build relationships between entities and insights across episodes.
    
    Args:
        neo4j_driver: Neo4j driver
        llm_client: LLM client
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot build cross-episode relationships.")
        return
        
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        with neo4j_driver.session(database=database) as session:
            # Track topic evolution across episodes
            result = session.run("""
            MATCH (e:Entity)-[:MENTIONED_IN]->(ep:Episode)
            WITH e.name as entity_name, e.type as entity_type, 
                 collect(distinct {
                     id: ep.id,
                     title: ep.title, 
                     date: ep.published_date
                 }) ORDER BY ep.published_date as appearances
            WHERE size(appearances) > 1
            RETURN entity_name, entity_type, appearances
            ORDER BY size(appearances) DESC
            LIMIT 10
            """)
            
            for record in result:
                entity_name = record["entity_name"]
                appearances = record["appearances"]
                
                # For consecutive episode pairs, analyze how the entity's context evolved
                for i in range(len(appearances)-1):
                    ep1 = appearances[i]
                    ep2 = appearances[i+1]
                    
                    # Get contexts from both episodes
                    contexts_result = session.run("""
                    MATCH (ep1:Episode {id: $ep1_id})-[:HAS_SEGMENT]->(s1:Segment)
                    WHERE toLower(s1.text) CONTAINS toLower($entity_name)
                    WITH collect(s1.text) as context1
                    
                    MATCH (ep2:Episode {id: $ep2_id})-[:HAS_SEGMENT]->(s2:Segment)
                    WHERE toLower(s2.text) CONTAINS toLower($entity_name)
                    
                    RETURN context1, collect(s2.text) as context2
                    """, {"entity_name": entity_name, "ep1_id": ep1["id"], "ep2_id": ep2["id"]})
                    
                    if not contexts_result.peek():
                        continue
                        
                    contexts = contexts_result.single()
                    
                    # Use LLM to detect conceptual shift or evolution
                    prompt = f"""
                    Analyze how the discussion of '{entity_name}' evolved between these episodes:
                    
                    Episode 1 '{ep1["title"]}' contexts:
                    {contexts['context1']}
                    
                    Episode 2 '{ep2["title"]}' contexts:
                    {contexts['context2']}
                    
                    Did the understanding or discussion of this entity:
                    1. EVOLVE - understanding developed or expanded
                    2. SHIFT - conceptual direction changed
                    3. CONTRADICT - later episode contradicted earlier episode
                    4. CONSISTENT - no significant change in understanding
                    
                    Return only one word: EVOLVE, SHIFT, CONTRADICT, or CONSISTENT
                    """
                    
                    response = llm_client.invoke(prompt)
                    evolution_type = response.content.strip().upper()
                    
                    # Create appropriate relationship between episodes
                    if evolution_type in ["EVOLVE", "SHIFT", "CONTRADICT"]:
                        session.run(f"""
                        MATCH (ep1:Episode {{id: $ep1_id}}), (ep2:Episode {{id: $ep2_id}})
                        MERGE (ep1)-[r:TOPIC_EVOLUTION {{
                            entity: $entity_name,
                            relation_type: $evolution_type
                        }}]->(ep2)
                        """, {
                            "ep1_id": ep1["id"], 
                            "ep2_id": ep2["id"],
                            "entity_name": entity_name,
                            "evolution_type": evolution_type
                        })
            
            # Connect insights across episodes by similarity
            session.run("""
            MATCH (i1:Insight)-[:FROM_EPISODE]->(ep1:Episode)
            MATCH (i2:Insight)-[:FROM_EPISODE]->(ep2:Episode)
            WHERE ep1.id <> ep2.id AND i1.category = i2.category
            WITH i1, i2, ep1, ep2,
                 apoc.text.similarity(i1.title, i2.title) +
                 apoc.text.similarity(i1.description, i2.description) as similarity
            WHERE similarity > 1.5
            MERGE (i1)-[:SIMILAR_INSIGHT {score: similarity}]->(i2)
            """)
            
            print("Built cross-episode relationships successfully")
            
    except Exception as e:
        print(f"Error building cross-episode relationships: {e}")

def apply_graph_algorithms(neo4j_driver):
    """
    Apply graph algorithms for pattern discovery.
    
    Args:
        neo4j_driver: Neo4j driver
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot apply graph algorithms.")
        return
        
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        with neo4j_driver.session(database=database) as session:
            # Set up graph projections for algorithms
            session.run("""
            CALL gds.graph.project(
              'complete_knowledge_graph',
              ['Entity', 'Insight', 'Episode', 'Segment'],
              {
                MENTIONED_IN: {orientation: 'UNDIRECTED'},
                MENTIONED_WITH: {orientation: 'UNDIRECTED'},
                SIMILAR_CONCEPT: {orientation: 'UNDIRECTED'},
                CONTRADICTS: {orientation: 'UNDIRECTED'},
                SUPPORTS: {orientation: 'UNDIRECTED'},
                EXPANDS_ON: {orientation: 'UNDIRECTED'},
                HAS_INSIGHT: {orientation: 'UNDIRECTED'},
                HAS_SEGMENT: {orientation: 'UNDIRECTED'},
                SIMILAR_INSIGHT: {orientation: 'UNDIRECTED'},
                TOPIC_EVOLUTION: {orientation: 'NATURAL'}
              }
            )
            """)
            
            # Run PageRank to find key concepts (most influential nodes)
            session.run("""
            CALL gds.pageRank.write(
              'complete_knowledge_graph',
              {
                writeProperty: 'pagerank',
                maxIterations: 20,
                dampingFactor: 0.85
              }
            )
            """)
            
            # Run community detection to find topic clusters
            session.run("""
            CALL gds.louvain.write(
              'complete_knowledge_graph',
              {
                writeProperty: 'community',
                includeIntermediateCommunities: true
              }
            )
            """)
            
            # Find shortest paths between important concepts
            important_entities = session.run("""
            MATCH (e:Entity)
            WHERE e.pagerank > 0.01
            RETURN e.id as id, e.name as name
            ORDER BY e.pagerank DESC
            LIMIT 10
            """)
            
            entities = list(important_entities)
            
            # Find paths between top entities
            for i in range(len(entities)):
                for j in range(i+1, len(entities)):
                    source = entities[i]
                    target = entities[j]
                    
                    paths = session.run("""
                    MATCH path = shortestPath((e1:Entity {id: $source_id})-[*..5]-(e2:Entity {id: $target_id}))
                    RETURN [node IN nodes(path) | node.name] as node_names,
                           [rel IN relationships(path) | type(rel)] as rel_types
                    """, {"source_id": source["id"], "target_id": target["id"]})
                    
                    if paths.peek():
                        path_data = paths.single()
                        # Create explicit CONNECTION relationships between key concepts
                        session.run("""
                        MATCH (e1:Entity {id: $source_id}), (e2:Entity {id: $target_id})
                        MERGE (e1)-[:KEY_CONNECTION {
                            path_length: size($path_nodes) - 2,
                            path_details: $path_nodes
                        }]->(e2)
                        """, {
                            "source_id": source["id"],
                            "target_id": target["id"],
                            "path_nodes": path_data["node_names"]
                        })
                        
            print("Applied graph algorithms successfully")
            
    except Exception as e:
        print(f"Error applying graph algorithms: {e}")

def implement_semantic_clustering(neo4j_driver, llm_client=None):
    """
    Implement semantic clustering with vector embeddings.
    
    Args:
        neo4j_driver: Neo4j driver
        llm_client: LLM client (optional)
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot implement semantic clustering.")
        return
        
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        with neo4j_driver.session(database=database) as session:
            # Create vector indexes if they don't exist
            session.run("""
            CREATE VECTOR INDEX insight_vector IF NOT EXISTS
            FOR (i:Insight) ON (i.embedding)
            OPTIONS {
              indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
              }
            }
            """)
            
            session.run("""
            CREATE VECTOR INDEX entity_vector IF NOT EXISTS
            FOR (e:Entity) ON (e.embedding)
            OPTIONS {
              indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
              }
            }
            """)
            
            # Create semantic similarity connections between insights
            session.run("""
            MATCH (i1:Insight)
            WHERE i1.embedding IS NOT NULL
            CALL db.index.vector.queryNodes('insight_vector', 5, i1.embedding) 
            YIELD node as i2, score
            WHERE i1.id <> i2.id AND score > 0.8
            MERGE (i1)-[:SEMANTIC_SIMILARITY {score: score}]->(i2)
            """)
            
            # Create semantic similarity connections between entities
            session.run("""
            MATCH (e1:Entity)
            WHERE e1.embedding IS NOT NULL
            CALL db.index.vector.queryNodes('entity_vector', 5, e1.embedding) 
            YIELD node as e2, score
            WHERE e1.id <> e2.id AND score > 0.8
            MERGE (e1)-[:SEMANTIC_SIMILARITY {score: score}]->(e2)
            """)
            
            # Create topic clusters based on semantic similarity
            session.run("""
            CALL gds.graph.project(
              'semantic_graph',
              ['Insight', 'Entity'],
              {
                SEMANTIC_SIMILARITY: {
                  orientation: 'UNDIRECTED',
                  properties: ['score']
                }
              }
            )
            """)
            
            # Run label propagation to identify semantic clusters
            session.run("""
            CALL gds.labelPropagation.write(
              'semantic_graph',
              {
                writeProperty: 'semantic_cluster',
                relationshipWeightProperty: 'score'
              }
            )
            """)
            
            if llm_client:
                # Name the clusters based on common concepts
                cluster_results = session.run("""
                MATCH (n)
                WHERE n.semantic_cluster IS NOT NULL
                RETURN DISTINCT n.semantic_cluster as cluster_id, 
                       collect(n.name) as member_names,
                       collect(labels(n)[0]) as member_types
                """)
                
                for cluster in cluster_results:
                    cluster_id = cluster["cluster_id"]
                    member_names = cluster["member_names"]
                    
                    # Generate cluster name with LLM
                    prompt = f"""
                    Create a short (2-3 word) descriptive name for a topic cluster containing these concepts:
                    {', '.join(member_names[:20])}
                    
                    The name should be concise and capture the common theme.
                    Return only the name, nothing else.
                    """
                    
                    cluster_name = llm_client.invoke(prompt).content.strip()
                    
                    # Store cluster name
                    session.run("""
                    MATCH (n)
                    WHERE n.semantic_cluster = $cluster_id
                    SET n.cluster_name = $cluster_name
                    """, {"cluster_id": cluster_id, "cluster_name": cluster_name})
                    
            print("Implemented semantic clustering successfully")
            
    except Exception as e:
        print(f"Error implementing semantic clustering: {e}")

def collect_knowledge_graph_stats(neo4j_driver):
    """
    Collect statistics about the enhanced knowledge graph for verification.
    
    Args:
        neo4j_driver: Neo4j driver
        
    Returns:
        Dictionary with knowledge graph statistics
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot collect knowledge graph statistics.")
        return None
    
    stats = {}
    
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        with neo4j_driver.session(database=database) as session:
            # Get node counts by type
            result = session.run("""
            MATCH (n)
            WITH labels(n)[0] as nodeType, count(n) as count
            RETURN nodeType, count
            ORDER BY count DESC
            """)
            
            node_counts = {record["nodeType"]: record["count"] for record in result}
            stats["node_counts"] = node_counts
            stats["total_nodes"] = sum(node_counts.values())
            
            # Get relationship counts by type
            result = session.run("""
            MATCH ()-[r]->() 
            WITH type(r) as relType, count(r) as count
            RETURN relType, count
            ORDER BY count DESC
            """)
            
            rel_counts = {record["relType"]: record["count"] for record in result}
            stats["relationship_counts"] = rel_counts
            stats["total_relationships"] = sum(rel_counts.values())
            
            # Get semantic relationship counts
            semantic_rels = ["SIMILAR_CONCEPT", "CONTRADICTS", "SUPPORTS", "EXPANDS_ON", 
                            "MENTIONED_WITH", "SEMANTIC_SIMILARITY", "TOPIC_EVOLUTION", 
                            "KEY_CONNECTION"]
            
            # Include relationship types from our taxonomy
            relationship_taxonomy_types = ["RELATIONSHIP_HIERARCHICAL", "RELATIONSHIP_INFLUENTIAL", 
                                          "RELATIONSHIP_COMPARATIVE", "RELATIONSHIP_TEMPORAL", 
                                          "RELATIONSHIP_FUNCTIONAL"]
            
            semantic_rels.extend(relationship_taxonomy_types)
            
            semantic_rel_count = sum(rel_counts.get(rel, 0) for rel in semantic_rels)
            stats["semantic_relationship_count"] = semantic_rel_count
            
            # Extract relationship counts by taxonomy type
            relationship_by_type = {}
            for rel_type in relationship_taxonomy_types:
                if rel_type in rel_counts:
                    relationship_by_type[rel_type.replace("RELATIONSHIP_", "")] = rel_counts[rel_type]
                
            stats["extracted_relationship_types"] = relationship_by_type
            
            # Get cluster counts
            result = session.run("""
            MATCH (n)
            WHERE n.semantic_cluster IS NOT NULL
            RETURN count(DISTINCT n.semantic_cluster) as cluster_count
            """)
            
            if result.peek():
                stats["semantic_cluster_count"] = result.single()["cluster_count"]
            else:
                stats["semantic_cluster_count"] = 0
            
            # Get cross-episode connections
            result = session.run("""
            MATCH ()-[r:TOPIC_EVOLUTION]->()
            RETURN count(r) as count
            """)
            
            if result.peek():
                stats["cross_episode_count"] = result.single()["count"]
            else:
                stats["cross_episode_count"] = 0
            
            # Get top entities by PageRank
            result = session.run("""
            MATCH (e:Entity)
            WHERE e.pagerank IS NOT NULL
            RETURN e.name as name, e.type as type, e.pagerank as score
            ORDER BY e.pagerank DESC
            LIMIT 10
            """)
            
            stats["top_entities"] = [{
                "name": record["name"], 
                "type": record["type"], 
                "pagerank": record["score"]
            } for record in result]
            
            return stats
            
    except Exception as e:
        print(f"Error collecting knowledge graph statistics: {e}")
        return None

def enhance_knowledge_graph(podcast_info, results, neo4j_driver, llm_client, embedding_client):
    """
    Apply advanced knowledge graph enhancements to the extracted podcast knowledge.
    
    Args:
        podcast_info: Podcast information
        results: Results from processing episodes
        neo4j_driver: Neo4j driver
        llm_client: LLM client
        embedding_client: OpenAI client for embeddings
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot enhance knowledge graph.")
        return False
        
    try:
        # Step 1: Basic knowledge is already in Neo4j from the original pipeline
        
        # Step 2: Extract relationship network from text
        print("Extracting relationship network...")
        podcast_id = podcast_info.get("id") if podcast_info else None
        relationship_count = extract_relationship_network(neo4j_driver, llm_client, podcast_id)
        print(f"Extracted {relationship_count} relationships from text")
        
        # Step 3: Enhance with semantic relationships
        print("Enhancing semantic relationships...")
        enhance_knowledge_relationships(neo4j_driver, llm_client)
        
        # Step 4: Expand knowledge and resolve duplicate entities
        print("Expanding knowledge and resolving entities...")
        expand_knowledge_graph(neo4j_driver, llm_client, embedding_client)
        
        # Step 5: Build cross-episode connections
        print("Building cross-episode relationships...")
        build_cross_episode_relationships(neo4j_driver, llm_client)
        
        # Step 6: Apply graph algorithms to discover patterns
        print("Applying graph algorithms for pattern discovery...")
        apply_graph_algorithms(neo4j_driver)
        
        # Step 7: Implement semantic clustering with vector embeddings
        print("Implementing semantic clustering...")
        implement_semantic_clustering(neo4j_driver, llm_client)
        
        # Collect and display statistics for verification
        print("Collecting knowledge graph statistics...")
        stats = collect_knowledge_graph_stats(neo4j_driver)
        if stats:
            print("\nEnhanced Knowledge Graph Statistics:")
            print(f"Total Nodes: {stats['total_nodes']}")
            print(f"Total Relationships: {stats['total_relationships']}")
            print(f"Semantic Relationships: {stats['semantic_relationship_count']}")
            print(f"Topic Clusters: {stats['semantic_cluster_count']}")
            print(f"Cross-Episode Connections: {stats['cross_episode_count']}")
            
            if "extracted_relationship_types" in stats and stats["extracted_relationship_types"]:
                print("\nExtracted Relationship Types:")
                for rel_type, count in stats["extracted_relationship_types"].items():
                    print(f"  {rel_type}: {count}")
            
            print("\nTop Entities by Influence:")
            for i, entity in enumerate(stats["top_entities"][:5], 1):
                print(f"{i}. {entity['name']} ({entity['type']}): {entity['pagerank']:.4f}")
        
        return True
        
    except Exception as e:
        print(f"Error enhancing knowledge graph: {e}")
        return False

# ============================================================================
# SECTION 6: VISUALIZATION AND REPORTING
# ============================================================================

# Visualization removed for batch seeding - returns basic stats only
def visualize_knowledge_graph(neo4j_driver):
    """
    Generate visualization data for the knowledge graph.
    
    Args:
        neo4j_driver: Neo4j driver
        
    Returns:
        Visualization data
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot visualize knowledge graph.")
        return None
    
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        with neo4j_driver.session(database=database) as session:
            # Get statistics
            result = session.run("""
            MATCH (n)
            RETURN 
                count(n) as nodeCount,
                sum(CASE WHEN labels(n)[0] = 'Podcast' THEN 1 ELSE 0 END) as podcastCount,
                sum(CASE WHEN labels(n)[0] = 'Episode' THEN 1 ELSE 0 END) as episodeCount,
                sum(CASE WHEN labels(n)[0] = 'Segment' THEN 1 ELSE 0 END) as segmentCount,
                sum(CASE WHEN labels(n)[0] = 'Insight' THEN 1 ELSE 0 END) as insightCount,
                sum(CASE WHEN labels(n)[0] = 'Entity' THEN 1 ELSE 0 END) as entityCount
            """)
            stats = result.single()
            
            # Get relationship statistics
            result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as relType, count(r) as count
            ORDER BY count DESC
            """)
            rel_stats = [dict(record) for record in result]
            
            # Get insight type distribution
            result = session.run("""
            MATCH (i:Insight)
            RETURN i.insight_type as insight_type, count(i) as count
            ORDER BY count DESC
            """)
            insight_types = [dict(record) for record in result]
            
            # Get entity type distribution
            result = session.run("""
            MATCH (e:Entity)
            RETURN e.type as type, count(e) as count
            ORDER BY count DESC
            """)
            entity_types = [dict(record) for record in result]
            
            # Get top entities
            result = session.run("""
            MATCH (e:Entity)-[r:MENTIONED_IN]->(ep:Episode)
            RETURN e.name as name, e.type as type, count(r) as mentions
            ORDER BY mentions DESC
            LIMIT 10
            """)
            top_entities = [dict(record) for record in result]
            
            # Combine all statistics
            visualization_data = {
                "stats": dict(stats),
                "relationships": rel_stats,
                "insightTypes": insight_types,
                "entityTypes": entity_types,
                "topEntities": top_entities
            }
            
            return visualization_data
            
    except Exception as e:
        print(f"Error generating visualization: {e}")
        return None

# Export functionality removed for batch seeding
# Knowledge should remain in Neo4j for RAG queries

# ============================================================================
# SECTION 7: PIPELINE ORCHESTRATION
# ============================================================================

class PodcastKnowledgePipeline:
    """Master orchestrator for the podcast knowledge extraction pipeline."""
    
    def __init__(self, config=None):
        """Initialize the pipeline with configuration."""
        self.config = config or PodcastConfig
        self.neo4j_driver = None
        self.audio_processor = None
        self.knowledge_extractor = None
        self.graph_operations = None
        self.visualizer = None
        
    def initialize_components(self, use_large_context=True):
        """Initialize all pipeline components."""
        try:
            # Initialize Neo4j
            if self.neo4j_driver is None:
                self.neo4j_driver = connect_to_neo4j(self.config)
                setup_neo4j_schema(self.neo4j_driver)
                
            # Initialize processors
            self.audio_processor = AudioProcessor(self.config)
            
            # Initialize LLM clients
            llm_client = initialize_gemini_client(enable_large_context=use_large_context)
            embedding_client = initialize_embedding_model()
            
            # Initialize knowledge extractor
            self.knowledge_extractor = KnowledgeExtractor(llm_client, embedding_client)
            
            # Initialize graph operations
            self.graph_operations = GraphOperations(self.neo4j_driver)
            
            # Visualizer removed for batch seeding
            
            print("✓ All pipeline components initialized successfully")
            return True
            
        except Exception as e:
            print(f"✗ Failed to initialize pipeline components: {e}")
            return False
            
    def cleanup(self):
        """Clean up resources and close connections."""
        if self.neo4j_driver:
            try:
                self.neo4j_driver.close()
                print("Neo4j connection closed")
            except Exception as e:
                print(f"Warning: Error closing Neo4j connection: {e}")
                
        # Clean up memory
        cleanup_memory()
        
    def process_episode(self, podcast_config, episode, segmenter_config=None, output_dir="processed_podcasts", use_large_context=True):
        """Process a single episode through the pipeline."""
        return process_podcast_episode(
            podcast_config, episode, segmenter_config, output_dir, use_large_context
        )
        
    def run_pipeline(self, podcast_config, max_episodes=1, segmenter_config=None, use_large_context=True, enhance_graph=True):
        """Run the complete pipeline."""
        return run_knowledge_graph_pipeline(
            podcast_config, max_episodes, segmenter_config, use_large_context, enhance_graph
        )

# ============================================================================
# SECTION 7.1: MAIN WORKFLOW FUNCTIONS
# ============================================================================

def process_podcast_episode(podcast_config, episode, segmenter_config=None, output_dir="processed_podcasts", use_large_context=True):
    """
    Process a podcast episode through the entire pipeline with checkpoint support.
    
    Args:
        podcast_config: Podcast configuration
        episode: Episode to process
        segmenter_config: Configuration for the segmenter
        output_dir: Output directory
        use_large_context: Whether to use 1M token window optimizations
        
    Returns:
        Processing results
    """
    if not BATCH_MODE:
        print(f"\n{'='*50}")
        print(f"PROCESSING EPISODE: {episode['title']}")
        print(f"{'='*50}\n")
    else:
        logger.info(f"Processing episode: {episode['title']}")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Phase 2.3: Initialize checkpoint system
    checkpoint = ProgressCheckpoint()
    episode_id = episode['id']
    
    # Check if episode already completed
    completed_episodes = checkpoint.get_completed_episodes()
    if episode_id in completed_episodes:
        logger.info(f"Episode {episode_id} already completed, skipping")
        return None
    
    # Initialize components
    neo4j_driver = connect_to_neo4j()
    
    # Phase 3: Use TaskRouter instead of single client
    task_router = TaskRouter()
    
    embedding_client = initialize_embedding_model()
    
    # Initialize segmenter with modified configuration if using large context
    if use_large_context and segmenter_config:
        # Allow for much larger segments if using large context models
        segmenter_config = segmenter_config.copy()
        segmenter_config['min_segment_tokens'] = segmenter_config.get('min_segment_tokens', 150)
        segmenter_config['max_segment_tokens'] = segmenter_config.get('max_segment_tokens', 800)
        print(f"Using segmenter with min_tokens={segmenter_config['min_segment_tokens']}, max_tokens={segmenter_config['max_segment_tokens']}")
    
    segmenter = EnhancedPodcastSegmenter(segmenter_config)
    
    # Download episode audio
    audio_path = download_episode_audio(episode, podcast_config["id"])
    if not audio_path:
        print(f"Failed to download audio for episode {episode['id']}")
        return None
    
    # Check for transcript checkpoint
    transcript_segments = checkpoint.load_episode_progress(episode_id, 'transcript')
    
    if transcript_segments is None:
        # Process the audio
        processing_result = segmenter.process_audio(audio_path)
        transcript_segments = processing_result['transcript']
        
        # Save transcript checkpoint
        checkpoint.save_episode_progress(episode_id, 'transcript', transcript_segments)
        
        if not BATCH_MODE:
            print(f"Created {len(transcript_segments)} segments")
        else:
            logger.info(f"Created {len(transcript_segments)} segments")
    else:
        logger.info(f"Loaded {len(transcript_segments)} segments from checkpoint")
    
    # Phase 1.2: Memory Streaming Implementation
    # Process segments in batches to avoid memory issues
    BATCH_SIZE = 20  # Process 20 segments at a time
    
    # Initialize aggregators for full episode
    all_insights = []
    all_entities = []
    episode_level_entities = []  # Store entities extracted from full transcript
    
    # Convert transcript for LLM processing
    full_transcript = convert_transcript_for_llm(transcript_segments)
    
    if use_large_context:
        # Process entire transcript at once for large context models
        if not BATCH_MODE:
            print("\nProcessing entire transcript with large context model")
        else:
            logger.info("Processing with large context model")
        
        # Phase 3: Extract insights using TaskRouter
        
        # Check for extraction checkpoint
        extraction_data = checkpoint.load_episode_progress(episode_id, 'extraction')
        
        if extraction_data is None:
            try:
                # Build combined prompt for insights + entities + quotes
                combined_prompt = build_combined_extraction_prompt(
                    podcast_config["name"], episode["title"], full_transcript, True
                )
                
                result = task_router.route_request('insights', combined_prompt)
                
                # Parse combined response
                parsed_data = parse_combined_llm_response(result['response'])
                
                # Phase 4: Validate extracted data
                insights = extraction_validator.validate_insights(parsed_data.get('insights', []))
                entities = extraction_validator.validate_entities(parsed_data.get('entities', []))
                quotes = parsed_data.get('quotes', [])
                
                # Save extraction checkpoint
                checkpoint.save_episode_progress(episode_id, 'extraction', {
                    'insights': insights,
                    'entities': entities,
                    'quotes': quotes,
                    'model_used': result['model_used']
                })
                
                if not BATCH_MODE:
                    print(f"Model used: {result['model_used']} (fallback: {result['fallback']})")
                    print(f"Extracted {len(insights)} insights, {len(entities)} entities, {len(quotes)} quotes")
                else:
                    logger.info(f"Extracted using {result['model_used']}: {len(insights)} insights, {len(entities)} entities")
                
            except Exception as e:
                logger.error(f"Failed to extract insights/entities: {e}")
                insights, entities, quotes = [], [], []
        else:
            # Load from checkpoint
            insights = extraction_data.get('insights', [])
            entities = extraction_data.get('entities', [])
            quotes = extraction_data.get('quotes', [])
            logger.info(f"Loaded extraction from checkpoint: {len(insights)} insights, {len(entities)} entities")
        
        all_insights.extend(insights)
        episode_level_entities.extend(entities)
        
        # Phase 1.2: Process segments in batches for memory efficiency
        if not BATCH_MODE:
            print("Processing segments in batches...")
            
        # Process segments in batches and save to Neo4j incrementally
        for batch_start in range(0, len(transcript_segments), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(transcript_segments))
            batch_segments = transcript_segments[batch_start:batch_end]
            
            if not BATCH_MODE:
                print(f"\nProcessing batch {batch_start//BATCH_SIZE + 1}/{(len(transcript_segments) + BATCH_SIZE - 1)//BATCH_SIZE}")
            
            # Process batch metrics
            batch_complexity = []
            batch_info_density = []
            batch_accessibility = []
            batch_quotability = []
            batch_best_of = []
            
            for i, segment in enumerate(batch_segments):
                segment_idx = batch_start + i
                
                # Get entities relevant to this segment
                segment_entities = [e for e in episode_level_entities if e['name'].lower() in segment['text'].lower()]
                
                # Calculate all metrics for segment
                complexity = extraction_validator.validate_metrics(
                    classify_segment_complexity(segment['text'], segment_entities)
                )
                info_density = extraction_validator.validate_metrics(
                    calculate_information_density(segment['text'], [], segment_entities)
                )
                accessibility = extraction_validator.validate_metrics(
                    calculate_accessibility_score(segment['text'], complexity['complexity_score'])
                )
                quotability = extraction_validator.validate_metrics(
                    calculate_quotability_score(segment['text'], segment.get('speaker'))
                )
                best_of = detect_best_of_markers(segment['text'], [])
                
                batch_complexity.append(complexity)
                batch_info_density.append(info_density)
                batch_accessibility.append(accessibility)
                batch_quotability.append(quotability)
                batch_best_of.append(best_of)
            
            # Save batch to Neo4j immediately to free memory
            if neo4j_driver:
                save_segment_batch_to_neo4j(
                    neo4j_driver, episode, batch_segments, batch_start,
                    batch_complexity, batch_info_density, batch_accessibility,
                    batch_quotability, batch_best_of, embedding_client
                )
            
            # Clear batch memory
            del batch_complexity, batch_info_density, batch_accessibility, batch_quotability, batch_best_of
            cleanup_memory()
    else:
        # Process each segment individually using traditional approach
        for i, segment in enumerate(transcript_segments):
            print(f"\nProcessing segment {i+1}/{len(transcript_segments)}")
            
            # Skip advertisements
            if segment.get('is_advertisement', False):
                print("Skipping advertisement segment")
                continue
            
            # Extract insights
            segment_text = segment['text']
            insights = extract_structured_insights(
                full_transcript, segment_text, llm_client,
                podcast_config["name"], episode["title"],
                use_large_context=False
            )
            
            if insights:
                print(f"Extracted {len(insights)} insights")
                all_insights.extend(insights)
            
            # Extract entities
            entities = detect_entities_with_gemini(segment_text, llm_client, use_large_context=False)
            
            if entities:
                print(f"Detected {len(entities)} entities")
                all_entities.extend(entities)
            
            # Calculate complexity for this segment
            complexity = classify_segment_complexity(segment_text, entities)
            segments_complexity.append(complexity)
            print(f"Complexity: {complexity['classification']} (score: {complexity['complexity_score']:.2f})")
            
            # Calculate information density
            info_density = calculate_information_density(segment_text, insights, entities)
            segments_info_density.append(info_density)
            print(f"Info density: {info_density['information_score']:.2f} (insights: {len(insights) if insights else 0}, entities: {len(entities) if entities else 0})")
            
            # Calculate accessibility
            accessibility = calculate_accessibility_score(segment_text, complexity['complexity_score'])
            segments_accessibility.append(accessibility)
            print(f"Accessibility: {accessibility['accessibility_score']:.1f}%")
            
            # Calculate quotability
            quotability = calculate_quotability_score(segment_text, segment.get('speaker'))
            segments_quotability.append(quotability)
            if quotability['is_highly_quotable']:
                print(f"Quotability: {quotability['quotability_score']:.1f} - HIGHLY QUOTABLE")
            
            # Detect best-of markers
            best_of = detect_best_of_markers(segment_text, insights)
            segments_best_of.append(best_of)
            if best_of['is_best_of']:
                print(f"Best-of: {best_of['category']} (score: {best_of['best_of_score']:.1f})")
    
    # For batch processing in large context mode, calculate episode metrics from saved data
    if use_large_context:
        # Query saved segments to calculate episode metrics
        episode_complexity, episode_metrics, key_quotes = calculate_episode_metrics_from_db(
            neo4j_driver, episode['id']
        )
    else:
        # Traditional calculation
        episode_complexity = calculate_episode_complexity(segments_complexity)
        episode_metrics = aggregate_episode_metrics(segments_info_density, segments_accessibility)
        key_quotes = extract_key_quotes(transcript_segments, segments_quotability)
    
    if not BATCH_MODE and episode_complexity:
        print(f"\nEpisode complexity: {episode_complexity.get('dominant_level', 'unknown')} "
              f"(avg score: {episode_complexity.get('average_complexity', 0):.2f})")
        print(f"Total insights: {len(all_insights)}, Total entities: {len(episode_level_entities)}")
    
    # Save remaining knowledge to Neo4j (podcast, episode, insights, entities)
    if neo4j_driver:
        save_episode_knowledge_to_neo4j(
            podcast_config, episode, all_insights, episode_level_entities,
            neo4j_driver, embedding_client, episode_complexity, episode_metrics,
            use_large_context, transcript_segments, task_router,
            quotes if 'quotes' in locals() else None,
            None  # topics will be extracted inside the function
        )
    
    # Visualization removed for batch seeding
    
    # Mark episode as complete
    checkpoint.save_episode_progress(episode_id, 'complete', {
        'completed_at': datetime.now().isoformat(),
        'insights_count': len(all_insights),
        'entities_count': len(episode_level_entities)
    })
    
    # Clean up intermediate checkpoints
    checkpoint.clean_episode_checkpoints(episode_id)
    
    # Print final report
    if not BATCH_MODE:
        print("\n" + "="*50)
        print("EPISODE PROCESSING COMPLETE")
        print("="*50)
        
        # Model usage report
        usage_report = task_router.get_usage_report()
        print("\nModel Usage:")
        for model, status in usage_report['model_status'].items():
            print(f"  {model}: RPM {status['rpm']}, TPM {status['tpm']}, RPD {status['rpd']}")
        
        # Validation report
        validation_report = extraction_validator.get_validation_report()
        if validation_report:
            print("\nValidation Report:")
            for stat, count in validation_report.items():
                print(f"  {stat}: {count}")
    else:
        logger.info(f"Completed episode {episode_id}")
    
    # Return processing results
    return {
        "podcast": podcast_config,
        "episode": episode,
        "segments": transcript_segments,
        "insights": all_insights,
        "entities": episode_level_entities,
        "large_context_used": use_large_context
    }

# ============================================================================
# SECTION 7.2: PIPELINE ORCHESTRATION - DECOMPOSED FUNCTIONS
# ============================================================================

def setup_pipeline_infrastructure(config=None):
    """Set up the infrastructure needed for pipeline processing."""
    config = config or PodcastConfig
    
    try:
        print("Setting up pipeline infrastructure...")
        
        # Validate dependencies
        config.validate_dependencies()
        
        # Setup directories
        config.setup_directories()
        
        # Initialize Neo4j
        neo4j_driver = connect_to_neo4j(config)
        if neo4j_driver:
            setup_neo4j_schema(neo4j_driver)
            return neo4j_driver
        else:
            raise DatabaseConnectionError("Failed to initialize Neo4j")
            
    except Exception as e:
        raise ConfigurationError(f"Failed to set up pipeline infrastructure: {e}")

def process_episodes_batch(podcast_info, podcast_config, segmenter_config, use_large_context=True):
    """Process a batch of episodes with progress tracking."""
    episodes = podcast_info["episodes"]
    results = []
    
    print(f"Processing {len(episodes)} episodes...")
    
    for i, episode in enumerate(tqdm(episodes, desc="Processing episodes")):
        try:
            print(f"\n--- Processing Episode {i+1}/{len(episodes)}: {episode['title']} ---")
            
            result = process_podcast_episode(
                podcast_config, 
                episode, 
                segmenter_config,
                use_large_context=use_large_context
            )
            
            if result:
                results.append(result)
                print(f"✓ Successfully processed: {episode['title']}")
            else:
                print(f"⚠ Failed to process: {episode['title']}")
            
            # Cleanup memory after each episode
            cleanup_memory()
            monitor_memory()  # Add memory monitoring
            
        except Exception as e:
            print(f"✗ Error processing episode '{episode['title']}': {e}")
            continue
    
    print(f"\nCompleted processing: {len(results)}/{len(episodes)} episodes successful")
    return results

def apply_graph_enhancements(podcast_info, results, neo4j_driver, use_large_context=True):
    """Apply advanced knowledge graph enhancements."""
    if not results:
        print("No results to enhance")
        return
        
    try:
        if not BATCH_MODE:
            print(f"\nApplying knowledge graph enhancements to {len(results)} episodes...")
        else:
            logger.info(f"Applying enhancements to {len(results)} episodes")
        
        # Initialize LLM clients
        llm_client = initialize_gemini_client(enable_large_context=use_large_context)
        embedding_client = initialize_embedding_model()
        
        # Apply enhancements
        enhance_knowledge_graph(
            podcast_info, 
            results, 
            neo4j_driver, 
            llm_client,
            embedding_client
        )
        
        if not BATCH_MODE:
            print("✓ Knowledge graph enhancements completed")
        else:
            logger.info("Knowledge graph enhancements completed")
        
    except Exception as e:
        logger.warning(f"Failed to apply graph enhancements: {e}")

# Report generation removed for batch seeding mode

def run_knowledge_graph_pipeline(podcast_config, max_episodes=1, segmenter_config=None, use_large_context=True, enhance_graph=True):
    """
    Run the complete knowledge graph pipeline with improved error handling and progress tracking.
    
    Args:
        podcast_config: Podcast configuration
        max_episodes: Maximum number of episodes to process  
        segmenter_config: Configuration for the segmenter (uses PodcastConfig defaults if None)
        use_large_context: Whether to use 1M token window optimizations
        enhance_graph: Whether to apply advanced knowledge graph enhancements
        
    Returns:
        Processing results
        
    Raises:
        ConfigurationError: If setup fails
        DatabaseConnectionError: If Neo4j connection fails
        PodcastProcessingError: If podcast processing fails
    """
    neo4j_driver = None
    
    try:
        if not BATCH_MODE:
            print("🚀 Starting Knowledge Graph Pipeline")
            print(f"Configuration: max_episodes={max_episodes}, use_large_context={use_large_context}, enhance_graph={enhance_graph}")
        else:
            logger.info(f"Starting pipeline: {podcast_config['name']}, episodes={max_episodes}")
        
        # Setup infrastructure
        neo4j_driver = setup_pipeline_infrastructure()
        
        # Fetch podcast feed
        print(f"\nFetching podcast feed: {podcast_config['name']}")
        podcast_info = fetch_podcast_feed(podcast_config, max_episodes)
        
        if not podcast_info or not podcast_info.get("episodes"):
            raise PodcastProcessingError("No episodes found to process")
        
        # Configure segmenter
        if segmenter_config is None:
            segmenter_config = PodcastConfig.get_segmenter_config()
            print(f"Using default segmenter configuration: {segmenter_config}")
        
        # Process episodes
        results = process_episodes_batch(
            podcast_info, 
            podcast_config, 
            segmenter_config, 
            use_large_context
        )
        
        if not results:
            raise PodcastProcessingError("No episodes were successfully processed")
        
        # Apply graph enhancements
        if enhance_graph and neo4j_driver:
            apply_graph_enhancements(podcast_info, results, neo4j_driver, use_large_context)
        
        # Skip report in batch mode
        if not BATCH_MODE:
            # Simple completion message
            print(f"\n✓ Pipeline completed: {len(results)} episodes processed")
        else:
            logger.info(f"Pipeline completed: {len(results)} episodes processed")
            
        return results
        
    except (ConfigurationError, DatabaseConnectionError, PodcastProcessingError):
        raise
    except Exception as e:
        raise PodcastProcessingError(f"Pipeline execution failed: {e}")
    finally:
        # Cleanup resources
        if neo4j_driver:
            try:
                neo4j_driver.close()
                print("Neo4j connection closed")
            except Exception as e:
                print(f"Warning: Error closing Neo4j connection: {e}")
        
        # Final memory cleanup
        cleanup_memory()

# 12. Example Usage
if __name__ == "__main__":
    # For batch seeding, use the seed_* functions directly
    # For interactive CLI, set BATCH_MODE = False
    
    if BATCH_MODE:
        # Example batch seeding
        print("Running in batch seeding mode")
        print("Use seed_single_podcast() or seed_podcasts() functions")
        print("Set BATCH_MODE = False for interactive CLI")
    else:
        import argparse
    
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description="PodcastKnowledge: Enhanced Knowledge Graph System")
    parser.add_argument("--podcast", "-p", type=str, default="my-first-million", 
                        help="Podcast ID to process")
    parser.add_argument("--episodes", "-e", type=int, default=1, 
                        help="Number of episodes to process")
    parser.add_argument("--large-context", "-l", action="store_true", default=True,
                        help="Use 1M token context window optimizations (default: True)")
    parser.add_argument("--disable-large-context", "-d", action="store_true",
                        help="Disable 1M token context window optimizations")
    parser.add_argument("--enhance-graph", "-g", action="store_true", default=True,
                        help="Apply advanced knowledge graph enhancements (default: True)")
    parser.add_argument("--disable-enhancements", "-n", action="store_true",
                        help="Disable advanced knowledge graph enhancements")
    parser.add_argument("--min-tokens", type=int, default=150,
                        help="Minimum tokens per segment")
    parser.add_argument("--max-tokens", type=int, default=800,
                        help="Maximum tokens per segment")
    
    args = parser.parse_args()
    
    # Override large context if explicitly disabled
    if args.disable_large_context:
        args.large_context = False
        
    # Override graph enhancements if explicitly disabled
    if args.disable_enhancements:
        args.enhance_graph = False
    
    # Example podcast configurations
    podcast_configs = {
        "my-first-million": {
            "id": "my-first-million",
            "name": "My First Million",
            "rss_url": "https://feeds.simplecast.com/4YELvXgu",
            "description": "Business ideas and frameworks from entrepreneurs",
            "hosts": ["Shaan Puri", "Sam Parr"]
        },
        "lex-fridman": {
            "id": "lex-fridman",
            "name": "Lex Fridman Podcast",
            "rss_url": "https://lexfridman.com/feed/podcast/",
            "description": "Conversations about AI, science, technology, history, philosophy and the nature of intelligence, consciousness, love, and power.",
            "hosts": ["Lex Fridman"]
        },
        "huberman-lab": {
            "id": "huberman-lab",
            "name": "Huberman Lab",
            "rss_url": "https://feeds.megaphone.fm/hubermanlab",
            "description": "Neuroscience and science-based tools for everyday life",
            "hosts": ["Andrew Huberman"]
        }
    }
    
    # Get podcast configuration
    podcast_config = podcast_configs.get(args.podcast)
    if not podcast_config:
        print(f"Unknown podcast: {args.podcast}")
        print(f"Available podcasts: {', '.join(podcast_configs.keys())}")
        exit(1)
    
    # Configure segmenter
    segmenter_config = {
        'min_segment_tokens': args.min_tokens,
        'max_segment_tokens': args.max_tokens,
        'use_gpu': True,
        'ad_detection_enabled': True,
        'use_semantic_boundaries': True
    }
    
    if not BATCH_MODE:
        # Original interactive mode
        print("\nPodcastKnowledge: Enhanced Knowledge Graph System")
        print("================================================")
        print(f"\nProcessing podcast: {podcast_config['name']} ({args.episodes} episodes)")
        print(f"Using {'large context (1M token) model' if args.large_context else 'standard segment-based processing'}")
        print(f"Segmenter configuration: min_tokens={args.min_tokens}, max_tokens={args.max_tokens}")
        
        run = input("\nRun podcast processing with these settings? (y/n): ")
        if run.lower() == 'y':
            # Process episodes
            results = run_knowledge_graph_pipeline(
                podcast_config,
                max_episodes=args.episodes,
                segmenter_config=segmenter_config,
                use_large_context=args.large_context,
                enhance_graph=args.enhance_graph
            )
            
            print(f"\nProcessed {len(results)} episodes")
            for i, result in enumerate(results):
                print(f"Episode {i+1}: {result['episode']['title']}")
                print(f"  Segments: {len(result['segments'])}")
                print(f"  Insights: {len(result['insights'])}")
                print(f"  Entities: {len(result['entities'])}")
                print(f"  Used large context: {result['large_context_used']}")
        else:
            print("Processing canceled. You can import this module and use its functions in your own code.")
            
            print("\nDone!")

# ============================================================================
# SECTION 8.1: QUICK START FUNCTIONS FOR COLAB
# ============================================================================

# Quick start function updated for batch seeding
def seed_single_podcast(podcast_name="my-first-million", max_episodes=10):
    """
    Seed knowledge graph with a single podcast.
    
    Example:
        summary = seed_single_podcast("my-first-million", max_episodes=10)
    """
    # Pre-defined podcast configurations
    podcast_configs = {
        "my-first-million": {
            "id": "my-first-million",
            "name": "My First Million",
            "rss_url": "https://feeds.simplecast.com/4YELvXgu",
            "description": "Business ideas and frameworks from entrepreneurs",
            "hosts": ["Shaan Puri", "Sam Parr"]
        },
        "lex-fridman": {
            "id": "lex-fridman",
            "name": "Lex Fridman Podcast",
            "rss_url": "https://lexfridman.com/feed/podcast/",
            "description": "Conversations about AI, science, technology, history, philosophy and the nature of intelligence, consciousness, love, and power.",
            "hosts": ["Lex Fridman"]
        },
        "huberman-lab": {
            "id": "huberman-lab",
            "name": "Huberman Lab",
            "rss_url": "https://feeds.megaphone.fm/hubermanlab",
            "description": "Neuroscience and science-based tools for everyday life",
            "hosts": ["Andrew Huberman"]
        }
    }
    
    podcast_config = podcast_configs.get(podcast_name)
    if not podcast_config:
        logger.error(f"Unknown podcast: {podcast_name}")
        logger.info(f"Available podcasts: {', '.join(podcast_configs.keys())}")
        return None
        
    return seed_podcasts([podcast_config], max_episodes_each=max_episodes)

# Test setup moved to separate utility - not needed for batch seeding

# Feature management moved to configuration flags

# ============================================================================
# BATCH SEEDING EXAMPLE USAGE
# ============================================================================

"""
EXAMPLE USAGE FOR BATCH SEEDING:

1. Basic single podcast seeding:
   summary = seed_single_podcast("my-first-million", max_episodes=10)

2. Multiple podcasts from RSS URLs:
   rss_urls = {
       "My First Million": "https://feeds.simplecast.com/4YELvXgu",
       "Lex Fridman": "https://lexfridman.com/feed/podcast/"
   }
   summary = seed_knowledge_graph_batch(rss_urls, max_episodes_each=5)

3. Custom configuration:
   podcast_configs = [
       {
           "id": "custom-podcast",
           "name": "Custom Podcast",
           "rss_url": "https://example.com/feed.xml",
           "description": "My custom podcast"
       }
   ]
   summary = seed_podcasts(podcast_configs, max_episodes_each=10)

4. Check results:
   print(f"Processed {summary['successful_episodes']} episodes")
   print(f"Total insights: {summary['total_insights']}")
   print(f"Total entities: {summary['total_entities']}")
   print(f"Duration: {summary['duration_seconds']/60:.1f} minutes")
"""

# ============================================================================
# COLAB SETUP HELPER
# ============================================================================

# ============================================================================
# SECTION 8.2: STREAMLINED BATCH SEEDING FUNCTIONS
# ============================================================================

def seed_podcasts(podcast_configs, max_episodes_each=10, neo4j_config=None):
    """
    Seed knowledge graph with podcast data.
    
    Args:
        podcast_configs: List of podcast configurations or single config dict
        max_episodes_each: Episodes to process per podcast
        neo4j_config: Override Neo4j configuration
        
    Returns:
        Summary dict with processing statistics
    """
    # Ensure podcast_configs is a list
    if isinstance(podcast_configs, dict):
        podcast_configs = [podcast_configs]
        
    # Use batch configuration
    config = SeedingConfig()
    if neo4j_config:
        config.__dict__.update(neo4j_config)
        
    # Initialize pipeline
    pipeline = PodcastKnowledgePipeline(config)
    
    # Summary statistics
    summary = {
        'total_podcasts': len(podcast_configs),
        'total_episodes': 0,
        'successful_episodes': 0,
        'failed_episodes': 0,
        'total_segments': 0,
        'total_insights': 0,
        'total_entities': 0,
        'start_time': datetime.now(),
        'errors': []
    }
    
    try:
        # Initialize components once
        if not pipeline.initialize_components(use_large_context=config.USE_LARGE_CONTEXT):
            raise ConfigurationError("Failed to initialize pipeline components")
            
        # Process each podcast
        for podcast_config in podcast_configs:
            try:
                logger.info(f"Processing podcast: {podcast_config['name']}")
                
                # Run pipeline for this podcast
                results = pipeline.run_pipeline(
                    podcast_config,
                    max_episodes=max_episodes_each,
                    use_large_context=config.USE_LARGE_CONTEXT,
                    enhance_graph=config.ENABLE_GRAPH_ENHANCEMENTS
                )
                
                # Update summary
                summary['total_episodes'] += len(results)
                summary['successful_episodes'] += len(results)
                
                for result in results:
                    summary['total_segments'] += len(result.get('segments', []))
                    summary['total_insights'] += len(result.get('insights', []))
                    summary['total_entities'] += len(result.get('entities', []))
                    
            except Exception as e:
                logger.error(f"Failed to process podcast {podcast_config['name']}: {e}")
                summary['errors'].append({
                    'podcast': podcast_config['name'],
                    'error': str(e)
                })
                
        # Calculate duration
        summary['end_time'] = datetime.now()
        summary['duration_seconds'] = (summary['end_time'] - summary['start_time']).total_seconds()
        
        # Log summary
        logger.info(f"Seeding completed: {summary['successful_episodes']} episodes processed")
        
        return summary
        
    finally:
        # Cleanup
        pipeline.cleanup()

def seed_knowledge_graph_batch(rss_urls, max_episodes_each=10):
    """
    Convenience function to seed knowledge graph from RSS URLs.
    
    Args:
        rss_urls: List of RSS feed URLs or dict mapping names to URLs
        max_episodes_each: Episodes to process per podcast
        
    Returns:
        Summary dict with processing statistics
    """
    # Convert RSS URLs to podcast configs
    podcast_configs = []
    
    if isinstance(rss_urls, dict):
        # Dict format: {"podcast_name": "rss_url"}
        for name, url in rss_urls.items():
            podcast_configs.append({
                "id": name.lower().replace(" ", "-"),
                "name": name,
                "rss_url": url,
                "description": f"Podcast: {name}"
            })
    else:
        # List format: ["url1", "url2"]
        for i, url in enumerate(rss_urls):
            podcast_configs.append({
                "id": f"podcast-{i+1}",
                "name": f"Podcast {i+1}",
                "rss_url": url,
                "description": f"Podcast from {url}"
            })
            
    return seed_podcasts(podcast_configs, max_episodes_each)

def checkpoint_recovery(checkpoint_dir="/content/drive/MyDrive/checkpoints"):
    """
    Resume seeding from checkpoints after interruption.
    
    Args:
        checkpoint_dir: Directory containing checkpoint files
        
    Returns:
        List of completed episode IDs
    """
    import glob
    import pickle
    
    completed = []
    
    try:
        checkpoint_files = glob.glob(os.path.join(checkpoint_dir, "*.pkl"))
        
        for checkpoint_file in checkpoint_files:
            try:
                with open(checkpoint_file, 'rb') as f:
                    data = pickle.load(f)
                    if 'episode_id' in data:
                        completed.append(data['episode_id'])
            except Exception as e:
                logger.error(f"Failed to load checkpoint {checkpoint_file}: {e}")
                
        logger.info(f"Found {len(completed)} completed episodes from checkpoints")
        return completed
        
    except Exception as e:
        logger.error(f"Failed to recover from checkpoints: {e}")
        return []