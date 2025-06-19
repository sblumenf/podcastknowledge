"""
Pipeline-specific configuration for timeouts and processing limits.

This module defines configurable timeouts for different pipeline stages
to prevent premature termination of long-running processes.
"""

import os
from src.core.env_config import env_config
from src.core.constants import DEFAULT_TIMEOUT

class PipelineConfig:
    """Configuration for pipeline processing timeouts and limits."""
    
    # Overall pipeline timeout (in seconds)
    # Default: 7200 seconds (2 hours) as specified in optimization plan
    PIPELINE_TIMEOUT = env_config.get_int(
        "PIPELINE_TIMEOUT",
        DEFAULT_TIMEOUT,  # 2 hours from constants.py
        "Overall pipeline processing timeout in seconds"
    )
    
    # Individual stage timeouts (in seconds)
    SPEAKER_IDENTIFICATION_TIMEOUT = env_config.get_int(
        "SPEAKER_IDENTIFICATION_TIMEOUT",
        120,  # 2 minutes
        "Timeout for speaker identification LLM calls"
    )
    
    CONVERSATION_ANALYSIS_TIMEOUT = env_config.get_int(
        "CONVERSATION_ANALYSIS_TIMEOUT",
        300,  # 5 minutes
        "Timeout for conversation structure analysis"
    )
    
    KNOWLEDGE_EXTRACTION_TIMEOUT = env_config.get_int(
        "KNOWLEDGE_EXTRACTION_TIMEOUT",
        600,  # 10 minutes per unit
        "Timeout for knowledge extraction per meaningful unit"
    )
    
    GRAPH_STORAGE_TIMEOUT = env_config.get_int(
        "GRAPH_STORAGE_TIMEOUT",
        300,  # 5 minutes
        "Timeout for Neo4j storage operations"
    )
    
    # Processing limits
    MAX_CONCURRENT_UNITS = env_config.get_int(
        "MAX_CONCURRENT_UNITS",
        5,  # Process 5 units in parallel
        "Maximum number of meaningful units to process concurrently"
    )
    
    # Retry configuration
    MAX_RETRIES = env_config.get_int(
        "MAX_RETRIES",
        3,
        "Maximum number of retries for failed operations"
    )
    
    RETRY_DELAY = env_config.get_int(
        "RETRY_DELAY",
        5,
        "Initial retry delay in seconds"
    )
    
    @classmethod
    def get_config_summary(cls) -> str:
        """Get a summary of pipeline timeout configuration."""
        return f"""
Pipeline Timeout Configuration:
  Overall Pipeline: {cls.PIPELINE_TIMEOUT}s ({cls.PIPELINE_TIMEOUT / 60:.1f} minutes)
  Speaker Identification: {cls.SPEAKER_IDENTIFICATION_TIMEOUT}s
  Conversation Analysis: {cls.CONVERSATION_ANALYSIS_TIMEOUT}s
  Knowledge Extraction: {cls.KNOWLEDGE_EXTRACTION_TIMEOUT}s per unit
  Graph Storage: {cls.GRAPH_STORAGE_TIMEOUT}s
  Max Concurrent Units: {cls.MAX_CONCURRENT_UNITS}
"""