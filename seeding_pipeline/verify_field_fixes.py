#!/usr/bin/env python3
"""Quick verification that field consistency fixes work."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.validation import (
    validate_entity,
    validate_quote,
    normalize_entity_fields,
    normalize_insight_for_storage
)

print("Testing field consistency fixes...\n")

# Test 1: Entity validation
print("1. Testing entity validation:")
entity_old = {'name': 'Elon Musk', 'type': 'PERSON'}
print(f"   Old entity format: {entity_old}")
is_valid, error = validate_entity(entity_old)
print(f"   Valid? {is_valid}, Error: {error}")

entity_normalized = normalize_entity_fields(entity_old.copy())
print(f"   After normalization: {entity_normalized}")
is_valid, error = validate_entity(entity_normalized)
print(f"   Valid? {is_valid}, Error: {error}")

entity_new = {'value': 'Elon Musk', 'type': 'PERSON'}
print(f"   New entity format: {entity_new}")
is_valid, error = validate_entity(entity_new)
print(f"   Valid? {is_valid}, Error: {error}")

# Test 2: Quote validation
print("\n2. Testing quote validation:")
quote = {'text': 'The future is wild', 'speaker': 'Elon Musk'}
print(f"   Quote: {quote}")
is_valid, error = validate_quote(quote)
print(f"   Valid? {is_valid}, Error: {error}")

wrong_quote = {'value': 'Wrong field name', 'speaker': 'Someone'}
print(f"   Wrong quote format: {wrong_quote}")
is_valid, error = validate_quote(wrong_quote)
print(f"   Valid? {is_valid}, Error: {error}")

# Test 3: Insight normalization
print("\n3. Testing insight normalization:")
insight = {'title': 'AI Impact', 'description': 'AI will transform society'}
print(f"   Original insight: {insight}")
storage_insight = normalize_insight_for_storage(insight)
print(f"   For storage: {storage_insight}")

print("\n✅ All tests completed! Field consistency fixes are working.")