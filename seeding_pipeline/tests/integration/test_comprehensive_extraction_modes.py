"""Comprehensive integration tests for all extraction modes.

These tests document and validate the behavior of:
- Fixed schema extraction
- Schemaless extraction  
- Dual-mode (migration) extraction
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json
import os
import tempfile

import pytest

from src.core.config import Config
from src.core.exceptions import PodcastKGError
from src.seeding.orchestrator import PodcastKnowledgePipeline
class TestExtractionModes:
    """Test all extraction modes end-to-end."""
    
    @pytest.fixture
    def test_config(self):
        """Create test configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config()
            config.checkpoint_dir = tmpdir
            config.audio_dir = tmpdir
            config.log_file = os.path.join(tmpdir, 'test.log')
            config.delete_audio_after_processing = True
            config.checkpoint_enabled = True
            config.batch_size = 2
            config.max_workers = 1
            yield config
    
    @pytest.fixture
    def mock_audio_provider(self):
        """Mock audio provider."""
        provider = Mock()
        provider.health_check.return_value = {'status': 'healthy'}
        provider.transcribe.return_value = """
        Welcome to the tech podcast. Today we're discussing artificial intelligence
        with our guest Dr. Sarah Johnson who is the CTO of TechCorp.
        She has been working on machine learning for over 10 years.
        """
        provider.diarize.return_value = [
            {'speaker': 'Speaker 1', 'start': 0.0, 'end': 5.0},
            {'speaker': 'Speaker 2', 'start': 5.0, 'end': 15.0}
        ]
        return provider
    
    @pytest.fixture
    def mock_llm_provider(self):
        """Mock LLM provider for fixed schema."""
        provider = Mock()
        provider.health_check.return_value = {'status': 'healthy'}
        provider.generate.return_value = json.dumps({
            "insights": [
                {
                    "content": "AI is transforming technology",
                    "speaker": "Dr. Sarah Johnson",
                    "confidence": 0.9
                }
            ],
            "entities": [
                {
                    "name": "Dr. Sarah Johnson",
                    "type": "Person",
                    "description": "CTO of TechCorp"
                },
                {
                    "name": "TechCorp",
                    "type": "Organization",
                    "description": "Technology company"
                }
            ],
            "relationships": [
                {
                    "source": "Dr. Sarah Johnson",
                    "target": "TechCorp",
                    "type": "WORKS_FOR"
                }
            ],
            "themes": ["artificial intelligence", "machine learning"],
            "topics": ["AI transformation", "ML applications"]
        })
        return provider
    
    @pytest.fixture
    def mock_schemaless_llm_provider(self):
        """Mock LLM provider for schemaless extraction."""
        provider = Mock()
        provider.health_check.return_value = {'status': 'healthy'}
        provider.generate.return_value = json.dumps({
            "entities": [
                {
                    "name": "Dr. Sarah Johnson",
                    "type": "Expert",
                    "description": "AI researcher and CTO"
                },
                {
                    "name": "TechCorp",
                    "type": "Company",
                    "description": "Leading tech company"
                },
                {
                    "name": "Machine Learning",
                    "type": "Technology",
                    "description": "AI subfield"
                }
            ],
            "relationships": [
                {
                    "source": "Dr. Sarah Johnson",
                    "target": "TechCorp",
                    "type": "LEADS_TECHNOLOGY_AT"
                },
                {
                    "source": "Dr. Sarah Johnson",
                    "target": "Machine Learning",
                    "type": "SPECIALIZES_IN"
                }
            ]
        })
        return provider
    
    @pytest.fixture
    def mock_graph_provider(self):
        """Mock graph provider."""
        provider = Mock()
        provider.health_check.return_value = {'status': 'healthy'}
        provider.create_node.return_value = True
        provider.create_relationship.return_value = True
        provider.update_node.return_value = True
        provider.find_node.return_value = None
        provider.query.return_value = []
        return provider
    
    @pytest.fixture
    def mock_embedding_provider(self):
        """Mock embedding provider."""
        provider = Mock()
        provider.health_check.return_value = {'status': 'healthy'}
        provider.embed.return_value = [0.1] * 384
        return provider
    
    @pytest.fixture
    def sample_rss_feed(self):
        """Sample RSS feed data."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Tech Podcast</title>
                <link>https://example.com</link>
                <description>A podcast about technology</description>
                <item>
                    <title>Episode 1: AI Discussion</title>
                    <link>https://example.com/episode1</link>
                    <description>Discussion about AI with Dr. Sarah Johnson</description>
                    <enclosure url="https://example.com/episode1.mp3" type="audio/mpeg"/>
                    <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
                </item>
                <item>
                    <title>Episode 2: Machine Learning Deep Dive</title>
                    <link>https://example.com/episode2</link>
                    <description>Deep dive into ML applications</description>
                    <enclosure url="https://example.com/episode2.mp3" type="audio/mpeg"/>
                    <pubDate>Mon, 08 Jan 2024 00:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>
        """
    
    @pytest.mark.integration
    def test_fixed_schema_extraction_end_to_end(
        self, test_config, mock_audio_provider, mock_llm_provider,
        mock_graph_provider, mock_embedding_provider, sample_rss_feed
    ):
        """Test fixed schema extraction end-to-end."""
        # Configure for fixed schema
        test_config.use_schemaless_extraction = False
        test_config.migration_mode = False
        
        with patch('src.factories.provider_factory.ProviderFactory.create_audio_provider', return_value=mock_audio_provider), \
             patch('src.factories.provider_factory.ProviderFactory.create_llm_provider', return_value=mock_llm_provider), \
             patch('src.factories.provider_factory.ProviderFactory.create_graph_provider', return_value=mock_graph_provider), \
             patch('src.factories.provider_factory.ProviderFactory.create_embedding_provider', return_value=mock_embedding_provider), \
             patch('requests.get') as mock_get:
            
            # Mock RSS feed response
            mock_response = Mock()
            mock_response.text = sample_rss_feed
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Create pipeline
            pipeline = PodcastKnowledgePipeline(test_config)
            
            # Process podcast
            result = pipeline.process_podcast(
                podcast_url="https://example.com/feed.xml",
                podcast_name="Test Tech Podcast",
                max_episodes=2
            )
            
            # Verify results
            assert result['episodes_processed'] == 2
            assert result['episodes_failed'] == 0
            assert result['extraction_mode'] == 'fixed'
            
            # Verify entities were extracted (fixed schema types)
            entity_calls = [call for call in mock_graph_provider.create_node.call_args_list
                          if call[1]['node_type'] in ['Person', 'Organization']]
            assert len(entity_calls) >= 2
            
            # Verify relationships were created
            assert mock_graph_provider.create_relationship.called
            
            # Verify insights were extracted (fixed schema feature)
            insight_calls = [call for call in mock_graph_provider.create_node.call_args_list
                           if call[1].get('node_type') == 'Insight']
            assert len(insight_calls) >= 1
    
    @pytest.mark.integration
    def test_schemaless_extraction_end_to_end(
        self, test_config, mock_audio_provider, mock_schemaless_llm_provider,
        mock_graph_provider, mock_embedding_provider, sample_rss_feed
    ):
        """Test schemaless extraction end-to-end."""
        # Configure for schemaless
        test_config.use_schemaless_extraction = True
        test_config.migration_mode = False
        
        with patch('src.factories.provider_factory.ProviderFactory.create_audio_provider', return_value=mock_audio_provider), \
             patch('src.factories.provider_factory.ProviderFactory.create_llm_provider', return_value=mock_schemaless_llm_provider), \
             patch('src.factories.provider_factory.ProviderFactory.create_graph_provider', return_value=mock_graph_provider), \
             patch('src.factories.provider_factory.ProviderFactory.create_embedding_provider', return_value=mock_embedding_provider), \
             patch('requests.get') as mock_get:
            
            # Mock RSS feed response
            mock_response = Mock()
            mock_response.text = sample_rss_feed
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Create pipeline
            pipeline = PodcastKnowledgePipeline(test_config)
            
            # Process podcast
            result = pipeline.process_podcast(
                podcast_url="https://example.com/feed.xml",
                podcast_name="Test Tech Podcast",
                max_episodes=2
            )
            
            # Verify results
            assert result['episodes_processed'] == 2
            assert result['episodes_failed'] == 0
            assert result['extraction_mode'] == 'schemaless'
            
            # Verify discovered entity types
            assert 'discovered_types' in result
            assert 'Expert' in result['discovered_types']
            assert 'Company' in result['discovered_types']
            assert 'Technology' in result['discovered_types']
            
            # Verify entities were extracted (schemaless types)
            entity_calls = [call for call in mock_graph_provider.create_node.call_args_list
                          if call[1]['node_type'] in ['Expert', 'Company', 'Technology']]
            assert len(entity_calls) >= 3
            
            # Verify relationships were created with custom types
            rel_calls = mock_graph_provider.create_relationship.call_args_list
            rel_types = [call[1]['rel_type'] for call in rel_calls]
            assert 'LEADS_TECHNOLOGY_AT' in rel_types or 'SPECIALIZES_IN' in rel_types
    
    @pytest.mark.integration
    def test_dual_mode_migration_extraction(
        self, test_config, mock_audio_provider, mock_llm_provider,
        mock_schemaless_llm_provider, mock_graph_provider, 
        mock_embedding_provider, sample_rss_feed
    ):
        """Test dual-mode (migration) extraction."""
        # Configure for migration mode
        test_config.use_schemaless_extraction = False
        test_config.migration_mode = True
        
        # Track which mode is being called
        extraction_modes = []
        
        def llm_generate(*args, **kwargs):
            # Return different results based on prompt content
            prompt = args[0] if args else kwargs.get('prompt', '')
            if 'schemaless' in prompt.lower() or 'discover' in prompt.lower():
                extraction_modes.append('schemaless')
                return mock_schemaless_llm_provider.generate()
            else:
                extraction_modes.append('fixed')
                return mock_llm_provider.generate()
        
        combined_llm = Mock()
        combined_llm.health_check.return_value = {'status': 'healthy'}
        combined_llm.generate.side_effect = llm_generate
        
        with patch('src.factories.provider_factory.ProviderFactory.create_audio_provider', return_value=mock_audio_provider), \
             patch('src.factories.provider_factory.ProviderFactory.create_llm_provider', return_value=combined_llm), \
             patch('src.factories.provider_factory.ProviderFactory.create_graph_provider', return_value=mock_graph_provider), \
             patch('src.factories.provider_factory.ProviderFactory.create_embedding_provider', return_value=mock_embedding_provider), \
             patch('requests.get') as mock_get:
            
            # Mock RSS feed response
            mock_response = Mock()
            mock_response.text = sample_rss_feed
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Create pipeline
            pipeline = PodcastKnowledgePipeline(test_config)
            
            # Process podcast
            result = pipeline.process_podcast(
                podcast_url="https://example.com/feed.xml",
                podcast_name="Test Tech Podcast",
                max_episodes=1  # Process just one episode for clarity
            )
            
            # Verify results
            assert result['episodes_processed'] == 1
            assert result['episodes_failed'] == 0
            assert result['extraction_mode'] == 'migration'
            
            # Verify both extraction modes were used
            assert 'fixed' in extraction_modes
            assert 'schemaless' in extraction_modes
            
            # Verify entities from both modes were extracted
            all_entity_types = set()
            for call in mock_graph_provider.create_node.call_args_list:
                if 'node_type' in call[1]:
                    all_entity_types.add(call[1]['node_type'])
            
            # Should have both fixed schema types and schemaless types
            fixed_types = {'Person', 'Organization'}
            schemaless_types = {'Expert', 'Company', 'Technology'}
            
            assert len(all_entity_types.intersection(fixed_types)) > 0
            assert len(all_entity_types.intersection(schemaless_types)) > 0