"""Simple API key management utility."""

import os
from typing import Optional


def get_gemini_api_key() -> str:
    """Get Gemini API key from environment.
    
    Checks in order:
    1. GEMINI_API_KEY
    2. GOOGLE_API_KEY (backward compatibility)
    
    Returns:
        API key string
        
    Raises:
        ValueError: If no API key is found
    """
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        raise ValueError(
            "No API key found. Please set GEMINI_API_KEY or GOOGLE_API_KEY "
            "environment variable with your paid tier API key."
        )
    
    return api_key