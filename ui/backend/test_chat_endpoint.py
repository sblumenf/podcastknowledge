#!/usr/bin/env python3
"""
Simple test script for the chat API endpoint.
Tests the Gemini-based neo4j-graphrag implementation.
"""

import requests
import json
import sys

# Configuration
BASE_URL = "http://localhost:8000"
PODCAST_ID = "mel_robbins_podcast"  # Change to your podcast ID

# Test query
test_query = "What is the 5 second rule?"

def test_chat_endpoint():
    """Test the chat endpoint with a simple query."""
    url = f"{BASE_URL}/api/chat/{PODCAST_ID}"
    
    payload = {
        "query": test_query
    }
    
    try:
        print(f"Testing chat endpoint for podcast: {PODCAST_ID}")
        print(f"Query: {test_query}")
        print("-" * 50)
        
        # Make the request
        response = requests.post(url, json=payload)
        
        # Check response status
        if response.status_code == 200:
            data = response.json()
            print("✅ Success!")
            print(f"Response: {data.get('response', 'No response')}")
            print(f"Podcast: {data.get('podcast_name', 'Unknown')}")
            return True
        else:
            print(f"❌ Error: Status code {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the server")
        print("Make sure the backend is running on http://localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    # Test the endpoint
    success = test_chat_endpoint()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)