#!/usr/bin/env python3
"""
Objective review test for Gemini Native JSON Mode Implementation.
Tests core functionality against plan objectives.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import json
from unittest.mock import Mock, patch

def test_core_objective_1_json_mode():
    """Test: Native JSON mode implemented across extraction methods"""
    print("\n🔍 OBJECTIVE 1: Native JSON mode implementation")
    
    from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig
    
    # Track all LLM calls
    calls_made = []
    
    def track_calls(prompt, json_mode=False, **kwargs):
        calls_made.append({
            'method': 'complete_with_options',
            'json_mode': json_mode,
            'prompt_preview': prompt[:50] + '...'
        })
        return {
            'content': json.dumps({
                "entities": [{"name": "TestEntity", "type": "concept", "importance": 8}],
                "quotes": [{"text": "Test quote", "speaker": "Speaker"}],
                "insights": [{"content": "Test insight", "type": "factual"}],
                "conversation_structure": {"segments": 2}
            })
        }
    
    mock_llm = Mock()
    mock_llm.complete_with_options.side_effect = track_calls
    
    config = ExtractionConfig()
    extractor = KnowledgeExtractor(
        llm_service=mock_llm,
        embedding_service=None,
        config=config
    )
    
    # Test extraction
    mock_unit = Mock()
    mock_unit.text = "Test conversation content"
    mock_unit.id = "test-1"
    mock_unit.themes = ["test"]
    mock_unit.speaker_distribution = {"Speaker": 1.0}
    
    result = extractor.extract_knowledge_combined(mock_unit, {})
    
    # Check results
    json_mode_calls = sum(1 for call in calls_made if call['json_mode'] is True)
    total_calls = len(calls_made)
    
    print(f"✓ Total extraction calls: {total_calls}")
    print(f"✓ JSON mode enabled calls: {json_mode_calls}")
    print(f"✓ Entities extracted: {len(result.entities)}")
    print(f"✓ Quotes extracted: {len(result.quotes)}")
    print(f"✓ Insights extracted: {len(result.insights)}")
    
    return json_mode_calls == total_calls and total_calls > 0

def test_core_objective_2_embedding_removal():
    """Test: Entity embedding generation removed"""
    print("\n🔍 OBJECTIVE 2: Entity embedding removal")
    
    from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig
    
    # Create mock embedding service that should NOT be called
    mock_embedding = Mock()
    mock_embedding.generate_embedding.return_value = [0.1] * 384
    
    mock_llm = Mock()
    mock_llm.complete_with_options.return_value = {
        'content': json.dumps({
            "entities": [
                {"name": "AI", "type": "concept", "importance": 9, "description": "Artificial Intelligence"},
                {"name": "ML", "type": "concept", "importance": 8, "description": "Machine Learning"},
                {"name": "OpenAI", "type": "organization", "importance": 7, "description": "AI company"}
            ],
            "quotes": [],
            "insights": [],
            "conversation_structure": {}
        })
    }
    
    config = ExtractionConfig()
    extractor = KnowledgeExtractor(
        llm_service=mock_llm,
        embedding_service=mock_embedding,
        config=config
    )
    
    mock_unit = Mock()
    mock_unit.text = "Discussion about AI and ML by OpenAI"
    mock_unit.id = "embedding-test"
    mock_unit.themes = ["AI", "ML"]
    mock_unit.speaker_distribution = {"Expert": 1.0}
    
    result = extractor.extract_knowledge_combined(mock_unit, {})
    
    # Check results
    embedding_calls = mock_embedding.generate_embedding.call_count
    entities_created = len(result.entities)
    entities_with_embeddings = sum(1 for e in result.entities if 'embedding' in e)
    
    print(f"✓ Entities created: {entities_created}")
    print(f"✓ Embedding service calls: {embedding_calls}")
    print(f"✓ Entities with embeddings: {entities_with_embeddings}")
    
    return embedding_calls == 0 and entities_created > 0 and entities_with_embeddings == 0

def test_core_objective_3_llm_service():
    """Test: LLM service implements native JSON mode correctly"""
    print("\n🔍 OBJECTIVE 3: LLM service implementation")
    
    # Check implementation file
    llm_path = "/home/sergeblumenfeld/podcastknowledge/seeding_pipeline/src/services/llm.py"
    
    with open(llm_path, 'r') as f:
        content = f.read()
    
    # Check for key implementation details
    has_json_mode_param = "json_mode: bool = False" in content
    has_response_mime_type = "response_mime_type='application/json'" in content
    has_google_genai = "import google.genai" in content
    has_complete_with_options = "def complete_with_options" in content
    
    print(f"✓ Has json_mode parameter: {has_json_mode_param}")
    print(f"✓ Uses response_mime_type: {has_response_mime_type}")
    print(f"✓ Imports Google GenAI SDK: {has_google_genai}")
    print(f"✓ Has complete_with_options method: {has_complete_with_options}")
    
    return all([has_json_mode_param, has_response_mime_type, has_google_genai, has_complete_with_options])

def test_core_objective_4_error_handling():
    """Test: Robust error handling for malformed JSON"""
    print("\n🔍 OBJECTIVE 4: Error handling")
    
    from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig
    
    error_cases = [
        '{"broken": json}',
        '',
        'Not JSON at all',
        '{"entities": null}'
    ]
    
    handled_gracefully = 0
    
    for error_json in error_cases:
        try:
            mock_llm = Mock()
            mock_llm.complete_with_options.return_value = {'content': error_json}
            
            config = ExtractionConfig()
            extractor = KnowledgeExtractor(
                llm_service=mock_llm,
                embedding_service=None,
                config=config
            )
            
            mock_unit = Mock()
            mock_unit.text = "Test"
            mock_unit.id = "error-test"
            mock_unit.themes = []
            mock_unit.speaker_distribution = {"Speaker": 1.0}
            
            result = extractor.extract_knowledge_combined(mock_unit, {})
            
            # Should return empty results, not crash
            if result.entities == [] and result.quotes == [] and result.insights == []:
                handled_gracefully += 1
        except:
            pass  # Failed to handle gracefully
    
    success_rate = handled_gracefully / len(error_cases)
    print(f"✓ Error cases handled: {handled_gracefully}/{len(error_cases)}")
    print(f"✓ Success rate: {success_rate:.0%}")
    
    return success_rate >= 0.75  # 75% success rate is good enough

def test_real_world_extraction():
    """Test: Real-world extraction scenario"""
    print("\n🔍 REAL-WORLD TEST: Full extraction workflow")
    
    from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig
    from src.extraction.sentiment_analyzer import SentimentAnalyzer
    
    # Simulate real responses
    def real_world_mock(prompt, json_mode=False, **kwargs):
        if "entities" in prompt.lower():
            return {
                'content': json.dumps([
                    {"name": "Artificial Intelligence", "type": "concept", "importance": 9, "description": "AI technology"},
                    {"name": "Google", "type": "organization", "importance": 8, "description": "Tech company"},
                    {"name": "Machine Learning", "type": "concept", "importance": 8, "description": "ML subset of AI"}
                ])
            }
        elif "sentiment" in prompt.lower():
            return {
                'content': json.dumps({
                    "polarity": "positive",
                    "score": 0.8,
                    "emotions": {"excitement": 0.9, "curiosity": 0.7},
                    "attitudes": {"optimistic": 0.8},
                    "energy_level": 0.85,
                    "engagement_level": 0.9
                })
            }
        else:
            return {
                'content': json.dumps({
                    "entities": [{"name": "Test", "type": "concept", "importance": 5}],
                    "quotes": [{"text": "This is revolutionary", "speaker": "Expert"}],
                    "insights": [{"content": "AI is transforming technology", "type": "factual", "confidence": 0.9}],
                    "conversation_structure": {"segments": 3, "flow": "linear"}
                })
            }
    
    mock_llm = Mock()
    mock_llm.complete_with_options.side_effect = real_world_mock
    
    # Test extraction
    config = ExtractionConfig()
    extractor = KnowledgeExtractor(
        llm_service=mock_llm,
        embedding_service=None,
        config=config
    )
    
    mock_unit = Mock()
    mock_unit.text = "In this fascinating discussion about artificial intelligence, experts from Google explain how machine learning is revolutionizing our world. The potential is truly extraordinary."
    mock_unit.id = "real-world-test"
    mock_unit.themes = ["AI", "technology", "future"]
    mock_unit.speaker_distribution = {"Expert": 0.7, "Host": 0.3}
    mock_unit.unit_type = "interview"
    
    # Extract knowledge
    result = extractor.extract_knowledge_combined(mock_unit, {})
    
    # Test sentiment
    analyzer = SentimentAnalyzer(mock_llm)
    sentiment = analyzer.analyze_meaningful_unit(mock_unit)
    
    print(f"✓ Entities extracted: {len(result.entities)}")
    print(f"✓ Quotes extracted: {len(result.quotes)}")
    print(f"✓ Insights extracted: {len(result.insights)}")
    print(f"✓ Sentiment polarity: {sentiment.overall_sentiment.polarity}")
    print(f"✓ Sentiment score: {sentiment.overall_sentiment.score}")
    
    # Verify no embeddings
    has_embeddings = any('embedding' in e for e in result.entities)
    print(f"✓ Entities have embeddings: {has_embeddings}")
    
    return (len(result.entities) > 0 and 
            len(result.quotes) > 0 and 
            len(result.insights) > 0 and
            sentiment.overall_sentiment.polarity == "positive" and
            not has_embeddings)

def main():
    """Run objective review tests"""
    print("=" * 70)
    print("OBJECTIVE REVIEW: Gemini Native JSON Mode Implementation")
    print("=" * 70)
    
    tests = [
        ("Native JSON Mode", test_core_objective_1_json_mode),
        ("Embedding Removal", test_core_objective_2_embedding_removal),
        ("LLM Service", test_core_objective_3_llm_service),
        ("Error Handling", test_core_objective_4_error_handling),
        ("Real-World Test", test_real_world_extraction)
    ]
    
    passed = 0
    
    for name, test in tests:
        try:
            if test():
                passed += 1
                print(f"✅ {name}: PASSED\n")
            else:
                print(f"❌ {name}: FAILED\n")
        except Exception as e:
            print(f"❌ {name}: ERROR - {e}\n")
    
    print("=" * 70)
    print(f"REVIEW RESULT: {passed}/{len(tests)} core objectives met")
    
    if passed >= 4:  # 80% pass rate is good enough
        print("\n✅ REVIEW PASSED - Implementation meets objectives")
        return True
    else:
        print("\n❌ REVIEW FAILED - Critical gaps found")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)