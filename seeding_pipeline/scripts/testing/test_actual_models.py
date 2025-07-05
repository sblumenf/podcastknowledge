#!/usr/bin/env python3
"""Test if the configured models actually work with the Gemini API."""

import os
import sys
sys.path.insert(0, '.')

from src.core.env_config import EnvironmentConfig
from src.services.llm import LLMService

def test_model_with_api(model_name: str, model_type: str):
    """Test if a model works with actual API call."""
    api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        print(f"⚠️  Cannot test {model_type} model - no API key found")
        return None
        
    print(f"\nTesting {model_type} model: {model_name}")
    
    try:
        # Create service
        service = LLMService(api_key=api_key, model_name=model_name)
        
        # Try a simple completion
        response = service.complete("Say 'hello' in one word")
        
        if response:
            print(f"✅ {model_type} model WORKS! Response: {response[:50]}")
            return True
        else:
            print(f"❌ {model_type} model returned empty response")
            return False
            
    except Exception as e:
        error_msg = str(e)
        if '404' in error_msg or 'not found' in error_msg:
            print(f"❌ {model_type} model NOT FOUND (404 error)")
        else:
            print(f"❌ {model_type} model error: {error_msg[:100]}")
        return False

def main():
    print("Testing configured default models with actual API calls...")
    print("=" * 60)
    
    # Get configured models
    flash_model = EnvironmentConfig.get_flash_model()
    pro_model = EnvironmentConfig.get_pro_model()
    
    # Test each model
    flash_works = test_model_with_api(flash_model, "Flash")
    pro_works = test_model_with_api(pro_model, "Pro")
    
    print("\n" + "=" * 60)
    print("RESULTS:")
    
    if flash_works is None and pro_works is None:
        print("⚠️  No API key available - cannot verify if models actually work")
        print("Set GOOGLE_API_KEY or GEMINI_API_KEY to test actual API calls")
    else:
        if flash_works:
            print(f"✅ Flash model ({flash_model}) is WORKING")
        else:
            print(f"❌ Flash model ({flash_model}) is NOT WORKING")
            
        if pro_works:
            print(f"✅ Pro model ({pro_model}) is WORKING")
        else:
            print(f"❌ Pro model ({pro_model}) is NOT WORKING")

if __name__ == "__main__":
    main()