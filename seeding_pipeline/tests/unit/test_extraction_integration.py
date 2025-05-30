"""Integration tests for knowledge extraction module.

Tests for src/processing/extraction.py focusing on integration
with real components and end-to-end scenarios.
"""

import pytest
from unittest import mock
import json
from datetime import datetime
from typing import Dict, Any, List

from src.processing.extraction import (
    KnowledgeExtractor, ExtractionResult, create_extractor
)
from src.core.models import (
    Entity, EntityType, Insight, InsightType, Quote, QuoteType, Segment,
    SpeakerRole, ComplexityLevel
)
from src.core.exceptions import ExtractionError
from src.processing.prompts import PromptBuilder
from src.processing.parsers import ResponseParser
from src.processing.importance_scoring import ImportanceScorer


class TestIntegratedExtraction:
    """Test extraction with integrated components."""
    
    @pytest.fixture
    def mock_llm_with_responses(self):
        """Create mock LLM that returns realistic responses."""
        provider = mock.Mock()
        
        # Define responses for different prompts
        def complete_side_effect(prompt):
            if "Extract named entities" in prompt:
                return json.dumps([
                    {
                        "name": "OpenAI",
                        "type": "Company",
                        "description": "AI research company",
                        "frequency": 5,
                        "importance": 9,
                        "has_citation": False,
                        "context_type": "general"
                    },
                    {
                        "name": "GPT-4",
                        "type": "Technology",
                        "description": "Large language model",
                        "frequency": 8,
                        "importance": 10,
                        "has_citation": True,
                        "context_type": "research"
                    }
                ])
            elif "Extract key insights" in prompt:
                return json.dumps([
                    {
                        "content": "Large language models are transforming how we interact with computers",
                        "type": "conceptual",
                        "confidence": 0.9,
                        "evidence": "Multiple examples discussed",
                        "related_entities": ["GPT-4", "OpenAI"]
                    }
                ])
            elif "Extract memorable" in prompt:
                return json.dumps([
                    {
                        "text": "AI is not just a tool, it's a new form of intelligence",
                        "speaker": "Sam Altman",
                        "type": "memorable",
                        "context": "Discussing the future of AI"
                    }
                ])
            elif "Identify the main topics" in prompt:
                return json.dumps([
                    {
                        "name": "AI Development",
                        "description": "Discussion of AI research and development",
                        "relevance": 0.95,
                        "subtopics": ["Language Models", "Safety", "Applications"]
                    }
                ])
            else:
                # For combined extraction
                return json.dumps({
                    "entities": [
                        {"name": "OpenAI", "type": "Company", "description": "AI company", "importance": 9}
                    ],
                    "insights": [
                        {"content": "AI safety is crucial", "type": "recommendation", "confidence": 0.85}
                    ],
                    "quotes": [
                        {"text": "The future is now", "speaker": "Expert", "type": "insightful"}
                    ]
                })
        
        provider.complete.side_effect = complete_side_effect
        return provider
    
    @pytest.fixture
    def extractor_with_mocked_llm(self, mock_llm_with_responses):
        """Create extractor with mocked LLM."""
        return KnowledgeExtractor(
            llm_provider=mock_llm_with_responses,
            use_large_context=True,
            max_retries=3,
            enable_cache=True
        )
    
    def test_full_extraction_pipeline(self, extractor_with_mocked_llm):
        """Test complete extraction pipeline."""
        text = """
        In this episode, we discuss how OpenAI's GPT-4 is revolutionizing AI.
        Sam Altman said "AI is not just a tool, it's a new form of intelligence".
        The implications for society are profound.
        """
        
        result = extractor_with_mocked_llm.extract_all(text)
        
        # Verify all components were extracted
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 2
        assert len(result.insights) == 1
        assert len(result.quotes) == 1
        assert len(result.topics) == 1
        
        # Verify entity details
        openai_entity = next(e for e in result.entities if e.name == "OpenAI")
        assert openai_entity.entity_type == EntityType.ORGANIZATION
        assert openai_entity.mention_count == 5
        
        # Verify insight details
        assert result.insights[0].insight_type == InsightType.CONCEPTUAL
        assert result.insights[0].confidence_score == 0.9
        
        # Verify quote details
        assert "Sam Altman" in result.quotes[0].speaker
        assert result.quotes[0].quote_type == QuoteType.MEMORABLE
        
        # Verify metadata
        assert result.metadata['text_length'] == len(text)
        assert 'extraction_timestamp' in result.metadata
    
    def test_prompt_builder_integration(self, mock_llm_with_responses):
        """Test integration with PromptBuilder."""
        extractor = KnowledgeExtractor(
            llm_provider=mock_llm_with_responses,
            use_large_context=True
        )
        
        # The extractor should use PromptBuilder for combined extraction
        result = extractor.extract_combined(
            "Test text about AI",
            podcast_name="AI Podcast",
            episode_title="Future of AI"
        )
        
        assert result.metadata['podcast_name'] == "AI Podcast"
        assert result.metadata['episode_title'] == "Future of AI"
        assert result.metadata['method'] == 'combined'
    
    def test_response_parser_integration(self, mock_llm_with_responses):
        """Test integration with ResponseParser."""
        extractor = KnowledgeExtractor(
            llm_provider=mock_llm_with_responses,
            use_large_context=True
        )
        
        # The parser should handle the JSON response
        result = extractor.extract_combined("Test text")
        
        # Should successfully parse the mocked response
        assert len(result.entities) > 0
        assert len(result.insights) > 0
        assert len(result.quotes) > 0
    
    def test_importance_scorer_integration(self, extractor_with_mocked_llm):
        """Test integration with ImportanceScorer."""
        segments = [
            {
                "text": "OpenAI created GPT-4",
                "start_time": 0,
                "end_time": 10,
                "speaker": "Host"
            },
            {
                "text": "GPT-4 is revolutionary",
                "start_time": 10,
                "end_time": 20,
                "speaker": "Guest"
            },
            {
                "text": "OpenAI continues to innovate",
                "start_time": 20,
                "end_time": 30,
                "speaker": "Host"
            }
        ]
        
        result = extractor_with_mocked_llm.extract_from_segments(
            segments,
            podcast_name="Tech Talk",
            episode_title="AI Revolution"
        )
        
        # Check that importance scoring was applied
        assert result['metadata']['importance_scoring_applied'] is True
        
        # Entities should have importance scores
        for entity in result['entities']:
            assert hasattr(entity, 'importance_score')
            assert hasattr(entity, 'importance_factors')
            assert 0 <= entity.importance_score <= 1
            
            # Check importance factors
            if entity.importance_factors:
                assert 'frequency' in entity.importance_factors
                assert 'semantic_centrality' in entity.importance_factors
                assert 'cross_reference' in entity.importance_factors
    
    def test_segment_processing_workflow(self, extractor_with_mocked_llm):
        """Test complete segment processing workflow."""
        # Create segments with entities appearing across multiple segments
        segments = [
            {
                "text": "Welcome to our show about OpenAI and their latest model GPT-4.",
                "start_time": 0,
                "end_time": 15,
                "speaker": "Host"
            },
            {
                "text": "GPT-4 represents a significant advancement in AI technology.",
                "start_time": 15,
                "end_time": 30,
                "speaker": "Expert"
            },
            {
                "text": "OpenAI has been at the forefront of AI research for years.",
                "start_time": 30,
                "end_time": 45,
                "speaker": "Host"
            }
        ]
        
        result = extractor_with_mocked_llm.extract_from_segments(segments)
        
        # Verify segment objects were created
        assert result['segments'] == 3
        assert result['metadata']['segments_processed'] == 3
        assert result['metadata']['total_duration'] == 45
        
        # Entities should be deduplicated
        entity_names = [e.name for e in result['entities']]
        assert len(entity_names) == len(set(entity_names))  # No duplicates
        
        # Entities should be sorted by importance
        importance_scores = [e.importance_score for e in result['entities']]
        assert importance_scores == sorted(importance_scores, reverse=True)
    
    def test_entity_merging_workflow(self, extractor_with_mocked_llm):
        """Test entity merging across segments."""
        # Mock responses that return same entity with variations
        def complete_with_variations(prompt):
            if "Welcome" in prompt:
                return json.dumps({
                    "entities": [{"name": "OpenAI", "type": "Company", "description": "AI research company"}],
                    "insights": [],
                    "quotes": []
                })
            elif "subsidiary" in prompt:
                return json.dumps({
                    "entities": [{"name": "openai", "type": "Organization", "description": "Microsoft subsidiary"}],
                    "insights": [],
                    "quotes": []
                })
            else:
                return json.dumps({"entities": [], "insights": [], "quotes": []})
        
        extractor_with_mocked_llm.llm_provider.complete.side_effect = complete_with_variations
        
        segments = [
            {"text": "Welcome to discuss OpenAI", "start_time": 0, "end_time": 10, "speaker": "Host"},
            {"text": "openai is now a subsidiary", "start_time": 10, "end_time": 20, "speaker": "Guest"}
        ]
        
        result = extractor_with_mocked_llm.extract_from_segments(segments)
        
        # Should merge variations of OpenAI
        entities = result['entities']
        openai_entities = [e for e in entities if 'openai' in e.name.lower()]
        assert len(openai_entities) == 1
        
        # Merged entity should have combined information
        merged_entity = openai_entities[0]
        assert merged_entity.mention_count == 2  # Appeared in both segments
        assert "AI research company" in merged_entity.description
        assert "Microsoft subsidiary" in merged_entity.description


class TestRealWorldScenarios:
    """Test with realistic podcast transcript scenarios."""
    
    @pytest.fixture
    def realistic_llm_provider(self):
        """Create LLM provider with realistic responses."""
        provider = mock.Mock()
        
        def realistic_complete(prompt):
            # Simulate realistic extraction based on prompt content
            if "health and longevity" in prompt.lower():
                if "Extract named entities" in prompt:
                    return json.dumps([
                        {
                            "name": "Dr. Peter Attia",
                            "type": "Person",
                            "description": "Physician focused on longevity",
                            "frequency": 15,
                            "importance": 9,
                            "has_citation": False,
                            "context_type": "clinical"
                        },
                        {
                            "name": "Metformin",
                            "type": "Medication",
                            "description": "Diabetes drug studied for longevity",
                            "frequency": 8,
                            "importance": 7,
                            "has_citation": True,
                            "context_type": "research"
                        },
                        {
                            "name": "mTOR",
                            "type": "Biological_Process",
                            "description": "Cellular pathway involved in aging",
                            "frequency": 6,
                            "importance": 8,
                            "has_citation": True,
                            "context_type": "research"
                        }
                    ])
                elif "Extract key insights" in prompt:
                    return json.dumps([
                        {
                            "content": "Zone 2 cardio training improves mitochondrial function and metabolic health",
                            "type": "factual",
                            "confidence": 0.95,
                            "evidence": "Multiple studies cited",
                            "related_entities": ["Dr. Peter Attia"]
                        },
                        {
                            "content": "Continuous glucose monitoring can reveal hidden metabolic dysfunction even in healthy individuals",
                            "type": "technical",
                            "confidence": 0.85,
                            "evidence": "Clinical observations",
                            "related_entities": []
                        }
                    ])
            
            # Default response
            return json.dumps({
                "entities": [],
                "insights": [],
                "quotes": []
            })
        
        provider.complete.side_effect = realistic_complete
        return provider
    
    def test_medical_podcast_extraction(self, realistic_llm_provider):
        """Test extraction from medical/health podcast content."""
        extractor = KnowledgeExtractor(
            llm_provider=realistic_llm_provider,
            use_large_context=True
        )
        
        medical_transcript = """
        Dr. Peter Attia discusses the importance of metabolic health and longevity.
        He mentions that drugs like Metformin may have anti-aging effects by
        affecting the mTOR pathway. Regular Zone 2 cardio training can improve
        mitochondrial function.
        """
        
        result = extractor.extract_all(medical_transcript)
        
        # Verify medical entities are properly typed
        entities_by_type = {}
        for entity in result.entities:
            entity_type = entity.entity_type
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []
            entities_by_type[entity_type].append(entity)
        
        assert EntityType.PERSON in entities_by_type
        assert EntityType.MEDICAL_TERM in entities_by_type
        
        # Verify insights have proper evidence attribution
        for insight in result.insights:
            if insight.confidence_score > 0.9:
                # High confidence insights should mention evidence
                assert any(hasattr(insight, attr) for attr in ['evidence', 'supporting_entities'])
    
    def test_technical_podcast_extraction(self):
        """Test extraction from technical/programming podcast."""
        # Create specialized mock for technical content
        tech_llm = mock.Mock()
        
        def tech_complete(prompt):
            if "Extract named entities" in prompt and "kubernetes" in prompt.lower():
                return json.dumps([
                    {
                        "name": "Kubernetes",
                        "type": "Technology",
                        "description": "Container orchestration platform",
                        "frequency": 20,
                        "importance": 10
                    },
                    {
                        "name": "Docker",
                        "type": "Technology", 
                        "description": "Container platform",
                        "frequency": 15,
                        "importance": 8
                    },
                    {
                        "name": "YAML",
                        "type": "Technology",
                        "description": "Configuration language",
                        "frequency": 10,
                        "importance": 6
                    }
                ])
            elif "Extract key insights" in prompt:
                return json.dumps([
                    {
                        "content": "Kubernetes abstracts away infrastructure complexity but introduces its own complexity",
                        "type": "conceptual",
                        "confidence": 0.9,
                        "related_entities": ["Kubernetes"]
                    },
                    {
                        "content": "Use init containers for dependency management in Kubernetes pods",
                        "type": "recommendation",
                        "confidence": 0.85,
                        "related_entities": ["Kubernetes"]
                    }
                ])
            return json.dumps({"entities": [], "insights": [], "quotes": []})
        
        tech_llm.complete.side_effect = tech_complete
        
        extractor = KnowledgeExtractor(llm_provider=tech_llm)
        
        tech_transcript = """
        Today we're discussing Kubernetes best practices. Kubernetes has become
        the de facto standard for container orchestration. When working with
        Kubernetes, you'll write a lot of YAML configuration files. Docker
        containers are the building blocks of Kubernetes deployments.
        """
        
        result = extractor.extract_all(tech_transcript)
        
        # All entities should be technology type
        for entity in result.entities:
            assert entity.entity_type == EntityType.TECHNOLOGY
        
        # Should have both conceptual and recommendation insights
        insight_types = {i.insight_type for i in result.insights}
        assert InsightType.CONCEPTUAL in insight_types
        assert InsightType.RECOMMENDATION in insight_types


class TestErrorHandlingIntegration:
    """Test error handling in integrated scenarios."""
    
    def test_llm_timeout_handling(self):
        """Test handling of LLM timeouts."""
        # Create LLM that times out
        timeout_llm = mock.Mock()
        timeout_llm.complete.side_effect = TimeoutError("LLM request timed out")
        
        extractor = KnowledgeExtractor(
            llm_provider=timeout_llm,
            max_retries=2
        )
        
        # Should handle timeout gracefully
        result = extractor.extract_entities("Test text")
        assert result == []  # Returns empty list on failure
        
        # Should have tried max_retries times
        assert timeout_llm.complete.call_count == 2
    
    def test_partial_extraction_failure(self):
        """Test when some extraction methods fail."""
        llm = mock.Mock()
        
        def partial_failure(prompt):
            if "entities" in prompt:
                return json.dumps([{"name": "Test", "type": "Concept"}])
            elif "insights" in prompt:
                raise ValueError("Invalid prompt")
            elif "quotes" in prompt:
                return json.dumps([])
            else:
                return json.dumps([])
        
        llm.complete.side_effect = partial_failure
        
        extractor = KnowledgeExtractor(llm_provider=llm)
        
        # Use mocked methods to control failures
        with mock.patch.object(extractor, 'extract_insights', side_effect=ExtractionError("insights", "Failed")):
            # Should still return partial results
            result = extractor.extract_all("Test text")
            
            assert len(result.entities) > 0  # Entities succeeded
            assert len(result.insights) == 0  # Insights failed but didn't crash
            assert isinstance(result, ExtractionResult)
    
    def test_malformed_llm_responses(self):
        """Test handling of various malformed LLM responses."""
        llm = mock.Mock()
        
        responses = [
            "This is not JSON at all",
            '{"entities": "should be array not string"}',
            '[{"name": "Missing required fields"}]',
            '{"completely": "wrong", "structure": true}'
        ]
        
        extractor = KnowledgeExtractor(llm_provider=llm)
        
        for response in responses:
            llm.complete.return_value = response
            
            # Should handle gracefully without crashing
            result = extractor.extract_entities("Test")
            assert isinstance(result, list)
            
            # Combined extraction should fall back
            result = extractor.extract_combined("Test")
            assert isinstance(result, ExtractionResult)


class TestCachingBehavior:
    """Test caching behavior in real scenarios."""
    
    def test_cache_hit_performance(self):
        """Test that cache improves performance."""
        call_count = 0
        
        def slow_llm_complete(prompt):
            nonlocal call_count
            call_count += 1
            # Simulate slow LLM
            import time
            time.sleep(0.1)
            return json.dumps([{"name": "Test", "type": "Person"}])
        
        llm = mock.Mock()
        llm.complete.side_effect = slow_llm_complete
        
        extractor = KnowledgeExtractor(
            llm_provider=llm,
            enable_cache=True
        )
        
        # First call should be slow
        import time
        start = time.time()
        result1 = extractor.extract_entities("Same text")
        first_duration = time.time() - start
        
        # Second call should be fast (cache hit)
        start = time.time()
        result2 = extractor.extract_entities("Same text")
        second_duration = time.time() - start
        
        assert result1 == result2
        assert call_count == 1  # LLM called only once
        assert second_duration < first_duration / 2  # Much faster
    
    def test_cache_invalidation_on_different_inputs(self):
        """Test that cache correctly handles different inputs."""
        llm = mock.Mock()
        
        def dynamic_response(prompt):
            if "first text" in prompt:
                return json.dumps([{"name": "First", "type": "Concept"}])
            elif "second text" in prompt:
                return json.dumps([{"name": "Second", "type": "Concept"}])
            else:
                return json.dumps([])
        
        llm.complete.side_effect = dynamic_response
        
        extractor = KnowledgeExtractor(llm_provider=llm, enable_cache=True)
        
        result1 = extractor.extract_entities("first text")
        result2 = extractor.extract_entities("second text")
        result3 = extractor.extract_entities("first text")  # Should hit cache
        
        assert result1[0].name == "First"
        assert result2[0].name == "Second"
        assert result3[0].name == "First"
        
        # LLM should be called only twice (third call hits cache)
        assert llm.complete.call_count == 2


class TestBackwardCompatibility:
    """Test backward compatibility features."""
    
    def test_create_extractor_factory(self):
        """Test the create_extractor factory function."""
        config = {
            "llm_provider": mock.Mock(),
            "extraction": {
                "use_large_context": True,
                "max_retries": 5,
                "enable_cache": False
            }
        }
        
        # The factory should create an extractor
        # (Note: Current implementation might need adjustment)
        with mock.patch('src.processing.extraction.KnowledgeExtractor') as MockExtractor:
            extractor = create_extractor(config)
            assert MockExtractor.called
    
    def test_legacy_entity_structure(self):
        """Test compatibility with legacy entity structure."""
        llm = mock.Mock()
        llm.complete.return_value = json.dumps([
            {
                "name": "Legacy Entity",
                "type": "PERSON",  # Uppercase as in legacy
                "description": "Test",
                "frequency": 1,
                "importance": 5
            }
        ])
        
        extractor = KnowledgeExtractor(llm_provider=llm)
        entities = extractor.extract_entities("Test")
        
        # Should handle uppercase type names
        assert len(entities) == 1
        assert entities[0].entity_type == EntityType.PERSON