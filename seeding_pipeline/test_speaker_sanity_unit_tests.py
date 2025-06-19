#!/usr/bin/env python3
"""Unit tests for speaker sanity check functions."""

import sys
sys.path.append('/home/sergeblumenfeld/podcastknowledge/seeding_pipeline')

from src.storage.graph_storage import GraphStorageService
from src.services.llm import LLMService
from src.core.config import PipelineConfig
from src.post_processing.speaker_mapper import SpeakerMapper
from src.utils.logging import setup_logging

def test_sanity_check_functions():
    """Test individual sanity check functions."""
    # Setup
    setup_logging()
    config = PipelineConfig()
    
    # Create minimal instances for testing
    print("=== SPEAKER SANITY CHECK UNIT TESTS ===\n")
    
    # Mock storage and LLM for isolated testing
    class MockStorage:
        def query(self, query, params):
            # Return mock data for contribution check
            if "COUNT(mu)" in query:
                speaker = params.get('speaker', '').strip('"')
                if speaker == "Brief Family Member":
                    return [{'unit_count': 1, 'avg_text_length': 30, 'sample_texts': ["Hi"]}]
                else:
                    return [{'unit_count': 5, 'avg_text_length': 150, 'sample_texts': ["Sample text"]}]
            return []
    
    mock_storage = MockStorage()
    mock_llm = None  # Not needed for these tests
    speaker_mapper = SpeakerMapper(mock_storage, mock_llm, config)
    
    # Test 1: Non-name filter
    print("TEST 1: Non-Name Filter")
    print("-" * 40)
    test_cases = [
        ("Mel Robbins", True, "Valid full name"),
        ("Dr. Smith", True, "Valid name with title"),
        ("you know what", False, "Common phrase, not a name"),
        ("um", False, "Filler word"),
        ("yeah", False, "Common word"),
        ("Guest Expert", True, "Valid role name"),
        ("a", False, "Too short"),
        ("123", False, "No letters"),
        ("just saying", False, "Multi-word lowercase phrase"),
    ]
    
    for name, expected, reason in test_cases:
        result = speaker_mapper._is_valid_speaker_name(name)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{name}' -> {result} ({reason})")
    
    # Test 2: Duplicate detection
    print("\n\nTEST 2: Duplicate Detection")
    print("-" * 40)
    
    test_speaker_lists = [
        {
            'speakers': ["Brief Family Member", "Mel Robbins' Son (Introducer)", "Mel Robbins (Host)"],
            'expected': {"Brief Family Member": "Mel Robbins' Son (Introducer)"},
            'reason': "Family member variations"
        },
        {
            'speakers': ["John Smith", "John Smith (Guest)", "John Smith (Expert)"],
            'expected': {"John Smith": "John Smith (Guest)", "John Smith (Expert)": "John Smith (Guest)"},
            'reason': "Same base name, different roles"
        },
        {
            'speakers': ["Dr. Jane Doe", "Jane Doe (Psychiatrist)", "Guest Expert"],
            'expected': {"Dr. Jane Doe": "Jane Doe (Psychiatrist)"},
            'reason': "Title variations"
        }
    ]
    
    for test in test_speaker_lists:
        duplicates = speaker_mapper._find_duplicate_speakers(test['speakers'])
        print(f"\nSpeakers: {test['speakers']}")
        print(f"Expected: {test['expected']}")
        print(f"Found: {duplicates}")
        print(f"Reason: {test['reason']}")
        
        # Check if expected duplicates were found
        all_found = all(k in duplicates and duplicates[k] == v for k, v in test['expected'].items())
        print(f"Result: {'✓ PASS' if all_found else '✗ FAIL'}")
    
    # Test 3: Name and role extraction
    print("\n\nTEST 3: Name and Role Extraction")
    print("-" * 40)
    
    test_names = [
        ("Mel Robbins (Host)", ("Mel Robbins", "Host")),
        ("Dr. Smith", ("Dr. Smith", "")),
        ("Guest Expert", ("Guest Expert", "")),
        ("Jane Doe (Psychiatrist)", ("Jane Doe", "Psychiatrist")),
    ]
    
    for name, expected in test_names:
        base, role = speaker_mapper._extract_name_and_role(name)
        status = "✓" if (base, role) == expected else "✗"
        print(f"{status} '{name}' -> base: '{base}', role: '{role}'")
    
    # Test 4: Similarity detection
    print("\n\nTEST 4: Similarity Detection")
    print("-" * 40)
    
    similarity_tests = [
        ("Brief Family Member", "Mel Robbins' Son", True, "Both family references"),
        ("Guest Expert", "Dr. John Smith", False, "Different types"),
        ("John Smith", "John Smith (Host)", True, "Same base name"),
        ("Dr. Jane", "Jane (Expert)", True, "Name contains match"),
    ]
    
    for name1, name2, expected, reason in similarity_tests:
        result = speaker_mapper._are_likely_same_person(name1, name2)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{name1}' vs '{name2}' -> {result} ({reason})")
    
    # Test 5: Value contribution (using mock data)
    print("\n\nTEST 5: Value Contribution Check")
    print("-" * 40)
    
    contribution_tests = [
        ("Mel Robbins (Host)", True, "Main speaker with many units"),
        ("Brief Family Member", False, "Few units, short text"),
    ]
    
    for speaker, expected, reason in contribution_tests:
        result = speaker_mapper._has_meaningful_contribution("test_episode", speaker)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{speaker}' -> {'Has value' if result else 'Low value'} ({reason})")
    
    print("\n\n=== ALL TESTS COMPLETED ===")

if __name__ == "__main__":
    test_sanity_check_functions()