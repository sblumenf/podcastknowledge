"""Golden output tests for validating extraction consistency."""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch
import json
import os
import tempfile

import pytest

from src.core.config import Config
from src.extraction.extraction import KnowledgeExtractor
from src.seeding.orchestrator import VTTKnowledgeExtractor
class TestGoldenOutputs:
    """Test extraction outputs against golden reference data."""
    
    @pytest.fixture
    def golden_outputs_dir(self):
        """Directory for golden output files."""
        golden_dir = Path(__file__).parent.parent / "fixtures" / "golden_outputs"
        golden_dir.mkdir(exist_ok=True, parents=True)
        return golden_dir
    
    @pytest.fixture
    def sample_segments(self):
        """Sample transcript segments for testing."""
        return [
            {
                "text": "Welcome to the AI podcast. I'm your host John Smith, and today we're joined by Dr. Sarah Johnson, who is the Chief Technology Officer at TechCorp. Sarah has been working in artificial intelligence for over 15 years.",
                "start": 0.0,
                "end": 15.0,
                "speaker": "Host"
            },
            {
                "text": "Thanks for having me, John. I'm excited to discuss how machine learning is transforming the healthcare industry. At TechCorp, we've developed several AI models that can predict patient outcomes with 95% accuracy.",
                "start": 15.0,
                "end": 30.0,
                "speaker": "Guest"
            },
            {
                "text": "That's fascinating. Can you tell us about some specific applications? I understand you've been working with Stanford Medical Center on a groundbreaking project.",
                "start": 30.0,
                "end": 40.0,
                "speaker": "Host"
            },
            {
                "text": "Absolutely. We partnered with Stanford Medical Center last year to deploy our diagnostic AI system. The system analyzes medical imaging data and can detect early signs of cancer that human doctors might miss. It's been incredibly successful.",
                "start": 40.0,
                "end": 55.0,
                "speaker": "Guest"
            },
            {
                "text": "What about the ethical considerations? How do you ensure patient privacy while training these models?",
                "start": 55.0,
                "end": 65.0,
                "speaker": "Host"
            }
        ]
    
    @pytest.fixture
    def mock_llm_fixed_response(self):
        """Mock LLM response for fixed schema extraction."""
        return json.dumps({
            "insights": [
                {
                    "content": "Machine learning models at TechCorp achieve 95% accuracy in predicting patient outcomes",
                    "speaker": "Dr. Sarah Johnson",
                    "confidence": 0.9
                },
                {
                    "content": "AI system can detect early signs of cancer that human doctors might miss",
                    "speaker": "Dr. Sarah Johnson",
                    "confidence": 0.85
                }
            ],
            "entities": [
                {
                    "name": "John Smith",
                    "type": "Person",
                    "description": "Host of the AI podcast"
                },
                {
                    "name": "Dr. Sarah Johnson",
                    "type": "Person",
                    "description": "Chief Technology Officer at TechCorp"
                },
                {
                    "name": "TechCorp",
                    "type": "Organization",
                    "description": "Technology company specializing in AI"
                },
                {
                    "name": "Stanford Medical Center",
                    "type": "Organization",
                    "description": "Medical institution partnering with TechCorp"
                }
            ],
            "relationships": [
                {
                    "source": "Dr. Sarah Johnson",
                    "target": "TechCorp",
                    "type": "WORKS_FOR"
                },
                {
                    "source": "TechCorp",
                    "target": "Stanford Medical Center",
                    "type": "PARTNERS_WITH"
                }
            ],
            "themes": ["artificial intelligence", "healthcare", "machine learning", "medical diagnostics"],
            "topics": ["AI in healthcare", "cancer detection", "medical imaging", "patient privacy"]
        })
    
    @pytest.fixture
    def mock_llm_schemaless_response(self):
        """Mock LLM response for schemaless extraction."""
        return json.dumps({
            "entities": [
                {
                    "name": "John Smith",
                    "type": "Podcast Host",
                    "description": "Host of the AI-focused podcast"
                },
                {
                    "name": "Dr. Sarah Johnson", 
                    "type": "AI Expert",
                    "description": "CTO with 15 years of AI experience"
                },
                {
                    "name": "TechCorp",
                    "type": "AI Company",
                    "description": "Company developing healthcare AI models"
                },
                {
                    "name": "Stanford Medical Center",
                    "type": "Medical Institution",
                    "description": "Healthcare partner for AI deployment"
                },
                {
                    "name": "Diagnostic AI System",
                    "type": "AI Technology",
                    "description": "System for analyzing medical imaging and detecting cancer"
                },
                {
                    "name": "95% Accuracy",
                    "type": "Performance Metric",
                    "description": "Accuracy rate of patient outcome predictions"
                }
            ],
            "relationships": [
                {
                    "source": "Dr. Sarah Johnson",
                    "target": "TechCorp",
                    "type": "LEADS_AI_AT"
                },
                {
                    "source": "TechCorp",
                    "target": "Diagnostic AI System",
                    "type": "DEVELOPED"
                },
                {
                    "source": "Diagnostic AI System",
                    "target": "Stanford Medical Center",
                    "type": "DEPLOYED_AT"
                },
                {
                    "source": "Dr. Sarah Johnson",
                    "target": "AI Expert",
                    "type": "HAS_EXPERTISE_IN",
                    "properties": {"years": 15}
                }
            ]
        })
    
    def test_create_golden_output_fixed_schema(
        self, golden_outputs_dir, sample_segments, mock_llm_fixed_response
    ):
        """Create golden output for fixed schema extraction."""
        config = Config()
        config.use_schemaless_extraction = False
        
        with patch('src.providers.llm.base.BaseLLMProvider.generate',
                  return_value=mock_llm_fixed_response):
            
            extractor = KnowledgeExtractor(
                llm_provider=Mock(),
                embedding_provider=Mock()
            )
            
            # Process each segment
            all_results = []
            for segment in sample_segments:
                result = extractor.extract_knowledge(segment)
                all_results.append({
                    'segment': segment,
                    'extraction': result
                })
            
            # Save golden output
            golden_file = golden_outputs_dir / "fixed_schema_golden.json"
            with open(golden_file, 'w') as f:
                json.dump({
                    'extraction_mode': 'fixed',
                    'created_at': datetime.now().isoformat(),
                    'segments_count': len(sample_segments),
                    'results': all_results
                }, f, indent=2)
            
            # Validate structure
            assert len(all_results) == 5
            for result in all_results:
                assert 'segment' in result
                assert 'extraction' in result
                extraction = result['extraction']
                assert 'insights' in extraction
                assert 'entities' in extraction
                assert 'relationships' in extraction
                assert 'themes' in extraction
                assert 'topics' in extraction
    
    @pytest.mark.integration
    def test_create_golden_output_schemaless(
        self, golden_outputs_dir, sample_segments, mock_llm_schemaless_response
    ):
        """Create golden output for schemaless extraction."""
        config = Config()
        config.use_schemaless_extraction = True
        
        with patch('src.providers.llm.base.BaseLLMProvider.generate',
                  return_value=mock_llm_schemaless_response):
            
            # Mock schemaless extractor
            all_results = []
            for segment in sample_segments:
                # Simulate schemaless extraction
                parsed = json.loads(mock_llm_schemaless_response)
                result = {
                    'entities': parsed['entities'],
                    'relationships': parsed['relationships'],
                    'discovered_types': list(set(e['type'] for e in parsed['entities']))
                }
                all_results.append({
                    'segment': segment,
                    'extraction': result
                })
            
            # Save golden output
            golden_file = golden_outputs_dir / "schemaless_golden.json"
            with open(golden_file, 'w') as f:
                json.dump({
                    'extraction_mode': 'schemaless',
                    'created_at': datetime.now().isoformat(),
                    'segments_count': len(sample_segments),
                    'discovered_types': [
                        "Podcast Host", "AI Expert", "AI Company", 
                        "Medical Institution", "AI Technology", "Performance Metric"
                    ],
                    'results': all_results
                }, f, indent=2)
            
            # Validate structure
            assert len(all_results) == 5
            for result in all_results:
                extraction = result['extraction']
                assert 'entities' in extraction
                assert 'relationships' in extraction
                assert 'discovered_types' in extraction
    
    def test_compare_with_golden_output_fixed_schema(
        self, golden_outputs_dir, sample_segments, mock_llm_fixed_response
    ):
        """Compare current extraction with golden output for fixed schema."""
        golden_file = golden_outputs_dir / "fixed_schema_golden.json"
        
        # Skip if golden file doesn't exist
        if not golden_file.exists():
            pytest.skip("Golden output file not found. Run test_create_golden_output_fixed_schema first.")
        
        # Load golden output
        with open(golden_file, 'r') as f:
            golden_data = json.load(f)
        
        config = Config()
        config.use_schemaless_extraction = False
        
        with patch('src.providers.llm.base.BaseLLMProvider.generate',
                  return_value=mock_llm_fixed_response):
            
            extractor = KnowledgeExtractor(
                llm_provider=Mock(),
                embedding_provider=Mock()
            )
            
            # Process segments and compare
            for i, segment in enumerate(sample_segments):
                result = extractor.extract_knowledge(segment)
                golden_result = golden_data['results'][i]['extraction']
                
                # Compare entity types
                current_entity_types = set(e['type'] for e in result['entities'])
                golden_entity_types = set(e['type'] for e in golden_result['entities'])
                assert current_entity_types == golden_entity_types, \
                    f"Entity types mismatch in segment {i}"
                
                # Compare relationship types
                current_rel_types = set(r['type'] for r in result['relationships'])
                golden_rel_types = set(r['type'] for r in golden_result['relationships'])
                assert current_rel_types == golden_rel_types, \
                    f"Relationship types mismatch in segment {i}"
                
                # Compare themes and topics presence
                assert 'themes' in result and 'themes' in golden_result
                assert 'topics' in result and 'topics' in golden_result
    
    @pytest.mark.integration
    def test_document_expected_entity_types(self, golden_outputs_dir):
        """Document expected entity types and relationships."""
        expected_types = {
            "fixed_schema": {
                "entity_types": [
                    "Person",
                    "Organization", 
                    "Location",
                    "Event",
                    "Technology",
                    "Concept"
                ],
                "relationship_types": [
                    "WORKS_FOR",
                    "PARTNERS_WITH",
                    "LOCATED_IN",
                    "PARTICIPATES_IN",
                    "DEVELOPS",
                    "USES"
                ],
                "special_nodes": [
                    "Podcast",
                    "Episode",
                    "Insight",
                    "Quote"
                ]
            },
            "schemaless": {
                "discovered_entity_types_examples": [
                    "Podcast Host",
                    "AI Expert",
                    "AI Company",
                    "Medical Institution",
                    "AI Technology",
                    "Performance Metric",
                    "Research Project",
                    "Academic Institution",
                    "Government Agency",
                    "Industry Standard"
                ],
                "discovered_relationship_types_examples": [
                    "LEADS_AI_AT",
                    "DEVELOPED",
                    "DEPLOYED_AT",
                    "HAS_EXPERTISE_IN",
                    "COLLABORATES_WITH",
                    "FUNDED_BY",
                    "RESEARCHES",
                    "REGULATES"
                ]
            }
        }
        
        # Save documentation
        doc_file = golden_outputs_dir / "expected_types_documentation.json"
        with open(doc_file, 'w') as f:
            json.dump(expected_types, f, indent=2)
        
        # Validate documentation was created
        assert doc_file.exists()
        
        # Load and verify
        with open(doc_file, 'r') as f:
            loaded = json.load(f)
        
        assert 'fixed_schema' in loaded
        assert 'schemaless' in loaded
        assert len(loaded['fixed_schema']['entity_types']) == 6
        assert len(loaded['fixed_schema']['relationship_types']) == 6
    
    def test_migration_mode_golden_output(
        self, golden_outputs_dir, sample_segments, 
        mock_llm_fixed_response, mock_llm_schemaless_response
    ):
        """Create golden output for migration mode (dual extraction)."""
        all_results = []
        
        for segment in sample_segments:
            # Simulate both extractions
            fixed_result = json.loads(mock_llm_fixed_response)
            schemaless_result = json.loads(mock_llm_schemaless_response)
            
            migration_result = {
                'segment': segment,
                'fixed_extraction': fixed_result,
                'schemaless_extraction': schemaless_result,
                'comparison': {
                    'fixed_entity_count': len(fixed_result['entities']),
                    'schemaless_entity_count': len(schemaless_result['entities']),
                    'new_entity_types': list(set(
                        e['type'] for e in schemaless_result['entities']
                    ) - set(['Person', 'Organization']))
                }
            }
            all_results.append(migration_result)
        
        # Save migration mode golden output
        golden_file = golden_outputs_dir / "migration_mode_golden.json"
        with open(golden_file, 'w') as f:
            json.dump({
                'extraction_mode': 'migration',
                'created_at': datetime.now().isoformat(),
                'segments_count': len(sample_segments),
                'results': all_results
            }, f, indent=2)
        
        # Validate both extraction results are present
        for result in all_results:
            assert 'fixed_extraction' in result
            assert 'schemaless_extraction' in result
            assert 'comparison' in result
            assert result['comparison']['new_entity_types']  # Should discover new types