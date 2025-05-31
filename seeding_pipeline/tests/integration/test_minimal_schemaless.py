"""Minimal integration test for schemaless mode functionality."""

from unittest.mock import Mock, patch, MagicMock

import pytest

from src.core.config import Config
from src.factories.provider_factory import ProviderFactory
from src.providers.embeddings.base import BaseEmbeddingProvider
from src.providers.graph.schemaless_neo4j import SchemalessNeo4jProvider
from src.providers.llm.base import BaseLLMProvider
class TestMinimalSchemaless:
    """Test basic schemaless mode functionality end-to-end."""
    
    @pytest.fixture
    def schemaless_config(self):
        """Create configuration with schemaless mode enabled."""
        return {
            'use_schemaless_extraction': True,
            'schemaless_confidence_threshold': 0.7,
            'entity_resolution_threshold': 0.85,
            'max_properties_per_node': 50,
            'relationship_normalization': True,
            'providers': {
                'graph': {
                    'provider': 'neo4j',  # Will be overridden to schemaless
                    'config': {
                        'uri': 'bolt://localhost:7687',
                        'username': 'neo4j',
                        'password': 'password'
                    }
                },
                'llm': {
                    'provider': 'mock',
                    'config': {}
                },
                'embeddings': {
                    'provider': 'mock',
                    'config': {}
                }
            }
        }
    
    @pytest.fixture
    def mock_llm_provider(self):
        """Create a mock LLM provider."""
        provider = Mock(spec=BaseLLMProvider)
        provider.generate.return_value = "Test response"
        return provider
    
    @pytest.fixture
    def mock_embedding_provider(self):
        """Create a mock embedding provider."""
        provider = Mock(spec=BaseEmbeddingProvider)
        provider.embed_texts.return_value = [[0.1, 0.2, 0.3]]
        provider.embed_query.return_value = [0.1, 0.2, 0.3]
        return provider
    
    def test_provider_factory_creates_schemaless(self, schemaless_config):
        """Test that provider factory creates schemaless provider when config enables it."""
        factory = ProviderFactory(schemaless_config)
        
        # Mock the neo4j-graphrag dependency
        with patch('src.providers.graph.schemaless_neo4j.SimpleKGPipeline') as mock_pipeline:
            # Create mock components
            mock_llm_adapter = MagicMock()
            mock_embedding_adapter = MagicMock()
            
            with patch('src.providers.graph.schemaless_neo4j.LLMAdapter', return_value=mock_llm_adapter), \
                 patch('src.providers.graph.schemaless_neo4j.EmbeddingAdapter', return_value=mock_embedding_adapter):
                
                provider = factory.create_provider('graph')
                
                # Verify we got a schemaless provider
                assert isinstance(provider, SchemalessNeo4jProvider)
                assert provider.config['use_schemaless_extraction'] is True
    
    def test_schemaless_provider_processes_segment(self, schemaless_config, mock_llm_provider, mock_embedding_provider):
        """Test that schemaless provider can process a segment through the pipeline."""
        # Create test segment
        test_segment = {
            'content': 'John Doe is the CEO of TechCorp. He founded the company in 2020.',
            'metadata': {
                'segment_id': 'test_001',
                'timestamp': '2024-01-01T00:00:00Z'
            }
        }
        
        # Mock neo4j-graphrag components
        mock_pipeline = MagicMock()
        mock_pipeline.process_text.return_value = {
            'entities': [
                {
                    'id': 'john_doe',
                    'type': 'Person',
                    'properties': {'name': 'John Doe', 'role': 'CEO'},
                    'confidence': 0.9
                },
                {
                    'id': 'techcorp',
                    'type': 'Organization',
                    'properties': {'name': 'TechCorp', 'founded': '2020'},
                    'confidence': 0.85
                }
            ],
            'relationships': [
                {
                    'source': 'john_doe',
                    'target': 'techcorp',
                    'type': 'CEO_OF',
                    'properties': {},
                    'confidence': 0.8
                },
                {
                    'source': 'john_doe',
                    'target': 'techcorp',
                    'type': 'FOUNDED',
                    'properties': {'year': '2020'},
                    'confidence': 0.75
                }
            ]
        }
        
        with patch('src.providers.graph.schemaless_neo4j.SimpleKGPipeline', return_value=mock_pipeline), \
             patch('src.providers.graph.schemaless_neo4j.LLMAdapter'), \
             patch('src.providers.graph.schemaless_neo4j.EmbeddingAdapter'), \
             patch('src.providers.graph.schemaless_neo4j.EntityResolver') as mock_resolver, \
             patch('src.providers.graph.schemaless_neo4j.MetadataEnricher') as mock_enricher:
            
            # Configure mocks
            mock_resolver.return_value.resolve.return_value = None  # No resolution needed
            mock_enricher.return_value.enrich.return_value = {}  # No additional metadata
            
            # Create provider
            factory = ProviderFactory(schemaless_config)
            factory._providers['llm'] = mock_llm_provider
            factory._providers['embeddings'] = mock_embedding_provider
            
            provider = factory.create_provider('graph')
            
            # Process segment
            result = provider.add_segment(test_segment)
            
            # Verify pipeline was called
            mock_pipeline.process_text.assert_called_once_with(test_segment['content'])
            
            # Verify components were used
            assert mock_resolver.called
            assert mock_enricher.called
            
            # Verify result structure
            assert 'entities' in result
            assert 'relationships' in result
            assert len(result['entities']) == 2
            assert len(result['relationships']) == 2
    
    def test_confidence_threshold_filtering(self, schemaless_config):
        """Test that entities below confidence threshold are filtered out."""
        test_segment = {
            'content': 'Test content',
            'metadata': {'segment_id': 'test_002'}
        }
        
        # Mock pipeline with mixed confidence entities
        mock_pipeline = MagicMock()
        mock_pipeline.process_text.return_value = {
            'entities': [
                {'id': 'high_conf', 'type': 'Person', 'confidence': 0.9},
                {'id': 'low_conf', 'type': 'Person', 'confidence': 0.5},  # Below threshold
                {'id': 'medium_conf', 'type': 'Person', 'confidence': 0.75}
            ],
            'relationships': []
        }
        
        with patch('src.providers.graph.schemaless_neo4j.SimpleKGPipeline', return_value=mock_pipeline), \
             patch('src.providers.graph.schemaless_neo4j.LLMAdapter'), \
             patch('src.providers.graph.schemaless_neo4j.EmbeddingAdapter'), \
             patch('src.providers.graph.schemaless_neo4j.EntityResolver'), \
             patch('src.providers.graph.schemaless_neo4j.MetadataEnricher'):
            
            factory = ProviderFactory(schemaless_config)
            provider = factory.create_provider('graph')
            
            result = provider.add_segment(test_segment)
            
            # Verify only entities above threshold are included
            assert len(result['entities']) == 2
            entity_ids = [e['id'] for e in result['entities']]
            assert 'high_conf' in entity_ids
            assert 'medium_conf' in entity_ids
            assert 'low_conf' not in entity_ids
    
    def test_property_limit_enforcement(self, schemaless_config):
        """Test that property limits are enforced."""
        # Set a low limit for testing
        schemaless_config['max_properties_per_node'] = 3
        
        test_segment = {
            'content': 'Test content',
            'metadata': {'segment_id': 'test_003'}
        }
        
        # Mock pipeline with entity having many properties
        mock_pipeline = MagicMock()
        mock_pipeline.process_text.return_value = {
            'entities': [
                {
                    'id': 'test_entity',
                    'type': 'Person',
                    'properties': {
                        'prop1': 'value1',
                        'prop2': 'value2',
                        'prop3': 'value3',
                        'prop4': 'value4',  # Should be removed
                        'prop5': 'value5'   # Should be removed
                    },
                    'confidence': 0.9
                }
            ],
            'relationships': []
        }
        
        with patch('src.providers.graph.schemaless_neo4j.SimpleKGPipeline', return_value=mock_pipeline), \
             patch('src.providers.graph.schemaless_neo4j.LLMAdapter'), \
             patch('src.providers.graph.schemaless_neo4j.EmbeddingAdapter'), \
             patch('src.providers.graph.schemaless_neo4j.EntityResolver'), \
             patch('src.providers.graph.schemaless_neo4j.MetadataEnricher'):
            
            factory = ProviderFactory(schemaless_config)
            provider = factory.create_provider('graph')
            
            result = provider.add_segment(test_segment)
            
            # Verify property limit is enforced
            entity = result['entities'][0]
            assert len(entity['properties']) <= 3
    
    def test_relationship_normalization(self, schemaless_config):
        """Test that relationship types are normalized when enabled."""
        test_segment = {
            'content': 'Test content',
            'metadata': {'segment_id': 'test_004'}
        }
        
        # Mock pipeline with various relationship types
        mock_pipeline = MagicMock()
        mock_pipeline.process_text.return_value = {
            'entities': [],
            'relationships': [
                {'source': 'a', 'target': 'b', 'type': 'works_for', 'confidence': 0.8},
                {'source': 'c', 'target': 'd', 'type': 'Works For', 'confidence': 0.8},
                {'source': 'e', 'target': 'f', 'type': 'WORKS-FOR', 'confidence': 0.8}
            ]
        }
        
        with patch('src.providers.graph.schemaless_neo4j.SimpleKGPipeline', return_value=mock_pipeline), \
             patch('src.providers.graph.schemaless_neo4j.LLMAdapter'), \
             patch('src.providers.graph.schemaless_neo4j.EmbeddingAdapter'), \
             patch('src.providers.graph.schemaless_neo4j.EntityResolver'), \
             patch('src.providers.graph.schemaless_neo4j.MetadataEnricher'):
            
            factory = ProviderFactory(schemaless_config)
            provider = factory.create_provider('graph')
            
            result = provider.add_segment(test_segment)
            
            # Verify all relationship types are normalized
            rel_types = [r['type'] for r in result['relationships']]
            assert all(t == 'WORKS_FOR' for t in rel_types)
    
    def test_component_integration(self, schemaless_config):
        """Test that all components work together in the pipeline."""
        test_segment = {
            'content': 'Alice works at BigCorp. Bob also works at BigCorp.',
            'metadata': {'segment_id': 'test_005'}
        }
        
        # Mock pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.process_text.return_value = {
            'entities': [
                {'id': 'alice', 'type': 'Person', 'properties': {'name': 'Alice'}, 'confidence': 0.9},
                {'id': 'bigcorp1', 'type': 'Organization', 'properties': {'name': 'BigCorp'}, 'confidence': 0.85},
                {'id': 'bob', 'type': 'Person', 'properties': {'name': 'Bob'}, 'confidence': 0.9},
                {'id': 'bigcorp2', 'type': 'Organization', 'properties': {'name': 'BigCorp'}, 'confidence': 0.85}
            ],
            'relationships': [
                {'source': 'alice', 'target': 'bigcorp1', 'type': 'WORKS_AT', 'confidence': 0.8},
                {'source': 'bob', 'target': 'bigcorp2', 'type': 'WORKS_AT', 'confidence': 0.8}
            ]
        }
        
        # Mock entity resolver to merge BigCorp entities
        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = lambda entity, entities: 'bigcorp1' if entity['id'] == 'bigcorp2' else None
        
        # Mock metadata enricher
        mock_enricher = MagicMock()
        mock_enricher.enrich.return_value = {'industry': 'Technology'}
        
        with patch('src.providers.graph.schemaless_neo4j.SimpleKGPipeline', return_value=mock_pipeline), \
             patch('src.providers.graph.schemaless_neo4j.LLMAdapter'), \
             patch('src.providers.graph.schemaless_neo4j.EmbeddingAdapter'), \
             patch('src.providers.graph.schemaless_neo4j.EntityResolver', return_value=mock_resolver), \
             patch('src.providers.graph.schemaless_neo4j.MetadataEnricher', return_value=mock_enricher):
            
            factory = ProviderFactory(schemaless_config)
            provider = factory.create_provider('graph')
            
            result = provider.add_segment(test_segment)
            
            # Verify entity resolution worked (should have 3 entities, not 4)
            assert len(result['entities']) == 3
            entity_ids = [e['id'] for e in result['entities']]
            assert 'alice' in entity_ids
            assert 'bob' in entity_ids
            assert 'bigcorp1' in entity_ids
            assert 'bigcorp2' not in entity_ids
            
            # Verify relationships were updated to use resolved entity
            for rel in result['relationships']:
                assert rel['target'] == 'bigcorp1'
            
            # Verify metadata enrichment
            bigcorp = next(e for e in result['entities'] if e['id'] == 'bigcorp1')
            assert 'industry' in bigcorp['properties']