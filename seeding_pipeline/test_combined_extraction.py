#!/usr/bin/env python3
"""Test why extract_knowledge_combined isn't being found."""

import sys
sys.path.append('.')

from src.extraction.extraction import KnowledgeExtractor
from src.services.llm import LLMService

# Create a mock LLM service
class MockLLM:
    def complete_with_options(self, prompt, json_mode=False):
        return {'content': '{"entities": [], "quotes": [], "insights": [], "conversation_structure": {}}'}

# Initialize extractor
llm_service = MockLLM()
extractor = KnowledgeExtractor(llm_service=llm_service, embedding_service=None)

# Check if method exists
print(f"Has extract_knowledge: {hasattr(extractor, 'extract_knowledge')}")
print(f"Has extract_knowledge_combined: {hasattr(extractor, 'extract_knowledge_combined')}")

# List all methods
print("\nAll methods on KnowledgeExtractor:")
for attr in dir(extractor):
    if not attr.startswith('_') and callable(getattr(extractor, attr)):
        print(f"  - {attr}")

# Try calling the method directly
print("\nTrying to access extract_knowledge_combined directly:")
try:
    method = getattr(extractor, 'extract_knowledge_combined', None)
    print(f"Direct access result: {method}")
    if method:
        print(f"Method type: {type(method)}")
        print(f"Method docstring: {method.__doc__}")
except Exception as e:
    print(f"Error accessing method: {e}")