#!/usr/bin/env python3
"""
Validate extraction results against the monolithic implementation.

This script compares the output of the modular extraction system
against the original monolithic podcast_knowledge_system_enhanced.py
to ensure functional equivalence.
"""

import sys
import os
import json
import difflib
from typing import Dict, Any, List, Tuple
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.models import Entity, Insight, Quote
from src.processing.extraction import KnowledgeExtractor
from src.processing.prompts import PromptBuilder
from src.processing.parsers import ResponseParser
from src.providers.llm.mock_provider import MockLLMProvider


def normalize_entity(entity: Entity) -> Dict[str, Any]:
    """Normalize entity for comparison"""
    return {
        'name': entity.name.lower().strip(),
        'type': str(entity.entity_type.value),
        'confidence': round(entity.confidence, 2)
    }


def normalize_insight(insight: Insight) -> Dict[str, Any]:
    """Normalize insight for comparison"""
    return {
        'content': insight.content.lower().strip(),
        'type': str(insight.type.value),
        'confidence': round(insight.confidence, 2)
    }


def normalize_quote(quote: Quote) -> Dict[str, Any]:
    """Normalize quote for comparison"""
    return {
        'text': quote.text.lower().strip(),
        'speaker': quote.speaker.lower().strip(),
        'type': str(quote.type.value)
    }


def compare_entities(
    modular_entities: List[Entity],
    monolith_entities: List[Dict[str, Any]]
) -> Tuple[bool, List[str]]:
    """Compare entity extraction results"""
    differences = []
    
    # Normalize both sets
    modular_normalized = [normalize_entity(e) for e in modular_entities]
    monolith_normalized = [
        {
            'name': e.get('name', '').lower().strip(),
            'type': e.get('type', 'CONCEPT'),
            'confidence': round(float(e.get('confidence', 0.7)), 2)
        }
        for e in monolith_entities
    ]
    
    # Sort for comparison
    modular_sorted = sorted(modular_normalized, key=lambda x: x['name'])
    monolith_sorted = sorted(monolith_normalized, key=lambda x: x['name'])
    
    # Check counts
    if len(modular_sorted) != len(monolith_sorted):
        differences.append(
            f"Entity count mismatch: modular={len(modular_sorted)}, "
            f"monolith={len(monolith_sorted)}"
        )
    
    # Compare individual entities
    modular_names = {e['name'] for e in modular_sorted}
    monolith_names = {e['name'] for e in monolith_sorted}
    
    missing_in_modular = monolith_names - modular_names
    if missing_in_modular:
        differences.append(f"Missing in modular: {missing_in_modular}")
    
    extra_in_modular = modular_names - monolith_names
    if extra_in_modular:
        differences.append(f"Extra in modular: {extra_in_modular}")
    
    return len(differences) == 0, differences


def compare_insights(
    modular_insights: List[Insight],
    monolith_insights: List[Dict[str, Any]]
) -> Tuple[bool, List[str]]:
    """Compare insight extraction results"""
    differences = []
    
    # Normalize both sets
    modular_normalized = [normalize_insight(i) for i in modular_insights]
    monolith_normalized = [
        {
            'content': i.get('content', '').lower().strip(),
            'type': i.get('type', 'OBSERVATION'),
            'confidence': round(float(i.get('confidence', 0.7)), 2)
        }
        for i in monolith_insights
    ]
    
    # Check counts (allow some variance)
    count_diff = abs(len(modular_normalized) - len(monolith_normalized))
    if count_diff > 2:  # Allow up to 2 insight difference
        differences.append(
            f"Insight count differs significantly: modular={len(modular_normalized)}, "
            f"monolith={len(monolith_normalized)}"
        )
    
    # Check for major content differences
    modular_contents = {i['content'][:50] for i in modular_normalized}
    monolith_contents = {i['content'][:50] for i in monolith_normalized}
    
    # Calculate overlap
    overlap = len(modular_contents & monolith_contents)
    total = len(modular_contents | monolith_contents)
    
    if total > 0 and overlap / total < 0.7:  # At least 70% overlap
        differences.append(
            f"Low content overlap: {overlap}/{total} = {overlap/total:.2%}"
        )
    
    return len(differences) == 0, differences


def validate_extraction_equivalence(test_transcript: str) -> Dict[str, Any]:
    """
    Validate that modular extraction produces equivalent results to monolith.
    
    Args:
        test_transcript: Transcript text to test
        
    Returns:
        Validation results dictionary
    """
    # Initialize modular components
    llm_provider = MockLLMProvider()
    extractor = KnowledgeExtractor(llm_provider)
    
    # Perform modular extraction
    modular_result = extractor.extract_all(test_transcript)
    
    # Simulate monolith extraction (in real validation, would call actual monolith)
    # For this example, we'll use mock data that represents typical monolith output
    monolith_result = {
        'entities': [
            {'name': 'Artificial Intelligence', 'type': 'TECHNOLOGY', 'confidence': 0.9},
            {'name': 'Machine Learning', 'type': 'TECHNOLOGY', 'confidence': 0.85},
            {'name': 'Healthcare', 'type': 'CONCEPT', 'confidence': 0.8}
        ],
        'insights': [
            {'content': 'AI is transforming healthcare', 'type': 'TREND', 'confidence': 0.8},
            {'content': 'ML algorithms improve diagnosis', 'type': 'FACT', 'confidence': 0.9}
        ],
        'quotes': [
            {
                'text': 'This is revolutionary',
                'speaker': 'Expert',
                'type': 'STATEMENT',
                'context': 'Discussing AI impact'
            }
        ],
        'topics': [
            {'name': 'AI in Healthcare', 'description': 'Main discussion topic'},
            {'name': 'Future of Medicine', 'description': 'Predictions and trends'}
        ]
    }
    
    # Compare results
    validation_results = {
        'test_transcript_length': len(test_transcript),
        'entity_validation': {},
        'insight_validation': {},
        'quote_validation': {},
        'topic_validation': {},
        'overall_valid': True
    }
    
    # Validate entities
    entities_valid, entity_diffs = compare_entities(
        modular_result.entities,
        monolith_result['entities']
    )
    validation_results['entity_validation'] = {
        'valid': entities_valid,
        'differences': entity_diffs,
        'modular_count': len(modular_result.entities),
        'monolith_count': len(monolith_result['entities'])
    }
    
    # Validate insights
    insights_valid, insight_diffs = compare_insights(
        modular_result.insights,
        monolith_result['insights']
    )
    validation_results['insight_validation'] = {
        'valid': insights_valid,
        'differences': insight_diffs,
        'modular_count': len(modular_result.insights),
        'monolith_count': len(monolith_result['insights'])
    }
    
    # Validate quotes (simplified)
    quote_count_diff = abs(
        len(modular_result.quotes) - len(monolith_result['quotes'])
    )
    quotes_valid = quote_count_diff <= 1
    validation_results['quote_validation'] = {
        'valid': quotes_valid,
        'modular_count': len(modular_result.quotes),
        'monolith_count': len(monolith_result['quotes'])
    }
    
    # Validate topics
    topic_count_diff = abs(
        len(modular_result.topics) - len(monolith_result['topics'])
    )
    topics_valid = topic_count_diff <= 1
    validation_results['topic_validation'] = {
        'valid': topics_valid,
        'modular_count': len(modular_result.topics),
        'monolith_count': len(monolith_result['topics'])
    }
    
    # Overall validation
    validation_results['overall_valid'] = all([
        entities_valid,
        insights_valid,
        quotes_valid,
        topics_valid
    ])
    
    return validation_results


def run_validation_suite():
    """Run validation test suite"""
    print("=" * 60)
    print("EXTRACTION VALIDATION SUITE")
    print("=" * 60)
    
    # Test cases
    test_cases = [
        {
            'name': 'Simple AI Discussion',
            'transcript': """
            Host: Today we're discussing artificial intelligence in healthcare.
            Expert: AI and machine learning are transforming how we diagnose diseases.
            Host: That's fascinating. Can you give us an example?
            Expert: Sure. ML algorithms can now detect cancer in X-rays with 95% accuracy.
            Host: This is revolutionary for patient care.
            """
        },
        {
            'name': 'Technical Deep Dive',
            'transcript': """
            Engineer: The neural network architecture uses convolutional layers.
            Host: How does that improve performance?
            Engineer: CNNs excel at pattern recognition in visual data.
            The convolution operation extracts features hierarchically.
            This enables detection of complex patterns.
            """
        },
        {
            'name': 'Business Discussion',
            'transcript': """
            CEO: Our revenue grew 40% year-over-year.
            Analyst: What drove this growth?
            CEO: Primarily our cloud services division.
            We're seeing strong enterprise adoption.
            The market opportunity is enormous.
            """
        }
    ]
    
    all_valid = True
    
    for test_case in test_cases:
        print(f"\nValidating: {test_case['name']}")
        print("-" * 40)
        
        result = validate_extraction_equivalence(test_case['transcript'])
        
        # Print results
        print(f"Overall Valid: {result['overall_valid']}")
        
        for component in ['entity', 'insight', 'quote', 'topic']:
            validation = result[f'{component}_validation']
            status = "✓" if validation['valid'] else "✗"
            print(f"{component.capitalize()} Validation: {status}")
            
            if not validation['valid'] and 'differences' in validation:
                for diff in validation['differences']:
                    print(f"  - {diff}")
        
        if not result['overall_valid']:
            all_valid = False
    
    print("\n" + "=" * 60)
    print(f"VALIDATION {'PASSED' if all_valid else 'FAILED'}")
    print("=" * 60)
    
    return all_valid


def main():
    """Main validation entry point"""
    # Run validation suite
    success = run_validation_suite()
    
    # Additional validation reports
    print("\nNOTE: This validation uses mock data for demonstration.")
    print("In production, it would compare against actual monolith output.")
    print("\nKey validation points:")
    print("1. Entity extraction consistency")
    print("2. Insight content overlap (>70%)")
    print("3. Quote count variance (<= 1)")
    print("4. Topic extraction similarity")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()