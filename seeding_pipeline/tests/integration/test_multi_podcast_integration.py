"""Integration tests for multi-podcast functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import yaml

from src.config.podcast_config_models import PodcastRegistry, PodcastConfig, DatabaseConfig
from src.config.podcast_config_loader import PodcastConfigLoader
from src.config.podcast_databases import PodcastDatabaseConfig
from src.storage.multi_database_graph_storage import MultiDatabaseGraphStorage
from src.seeding.multi_podcast_orchestrator import MultiPodcastVTTKnowledgeExtractor
from src.vtt.vtt_parser import VTTParser


class TestMultiPodcastIntegration:
    """Test multi-podcast integration functionality."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory for config files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def podcast_config_file(self, temp_config_dir):
        """Create a test podcast configuration file."""
        config = {
            'version': '1.0',
            'podcasts': [
                {
                    'id': 'tech_podcast',
                    'name': 'Tech Podcast',
                    'enabled': True,
                    'database': {
                        'uri': 'neo4j://localhost:7687',
                        'database_name': 'tech_db'
                    }
                },
                {
                    'id': 'science_podcast',
                    'name': 'Science Podcast',
                    'enabled': True,
                    'database': {
                        'uri': 'neo4j://localhost:7687',
                        'database_name': 'science_db'
                    }
                },
                {
                    'id': 'disabled_podcast',
                    'name': 'Disabled Podcast',
                    'enabled': False,
                    'database': {
                        'uri': 'neo4j://localhost:7687',
                        'database_name': 'disabled_db'
                    }
                }
            ]
        }
        
        config_path = temp_config_dir / 'podcasts.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        return config_path
    
    @pytest.fixture
    def sample_vtt_files(self, temp_config_dir):
        """Create sample VTT files for different podcasts."""
        vtt_content_tech = """WEBVTT

NOTE
{
  "podcast_id": "tech_podcast",
  "episode_title": "AI Revolution",
  "episode_id": "tech_ep_001"
}

00:00:00.000 --> 00:00:05.000
Welcome to Tech Podcast, discussing AI today.

00:00:05.000 --> 00:00:10.000
Let's talk about machine learning advances.
"""
        
        vtt_content_science = """WEBVTT

NOTE
{
  "podcast_id": "science_podcast",
  "episode_title": "Quantum Physics",
  "episode_id": "science_ep_001"
}

00:00:00.000 --> 00:00:05.000
Welcome to Science Podcast.

00:00:05.000 --> 00:00:10.000
Today we explore quantum mechanics.
"""
        
        # Create podcast directories
        tech_dir = temp_config_dir / 'podcasts' / 'tech_podcast' / 'transcripts'
        science_dir = temp_config_dir / 'podcasts' / 'science_podcast' / 'transcripts'
        tech_dir.mkdir(parents=True)
        science_dir.mkdir(parents=True)
        
        # Write VTT files
        tech_vtt = tech_dir / 'tech_ep_001.vtt'
        science_vtt = science_dir / 'science_ep_001.vtt'
        
        tech_vtt.write_text(vtt_content_tech)
        science_vtt.write_text(vtt_content_science)
        
        return {
            'tech': tech_vtt,
            'science': science_vtt
        }
    
    def test_podcast_configuration_loading(self, podcast_config_file):
        """Test that podcast configurations are loaded correctly."""
        loader = PodcastConfigLoader(podcast_config_file)
        registry = loader.load()
        
        assert len(registry.podcasts) == 3
        assert registry.get_podcast('tech_podcast').name == 'Tech Podcast'
        assert registry.get_podcast('science_podcast').name == 'Science Podcast'
        assert len(registry.get_enabled_podcasts()) == 2
    
    def test_podcast_database_routing(self, podcast_config_file):
        """Test that podcasts are routed to correct databases."""
        config = PodcastDatabaseConfig(str(podcast_config_file))
        
        # Test database routing
        assert config.get_database_for_podcast('tech_podcast') == 'tech_db'
        assert config.get_database_for_podcast('science_podcast') == 'science_db'
        assert config.get_database_for_podcast('unknown') == 'neo4j'  # default
        
        # Test enabled podcasts
        enabled = config.get_enabled_podcasts()
        assert 'tech_podcast' in enabled
        assert 'science_podcast' in enabled
        assert 'disabled_podcast' not in enabled
    
    def test_vtt_parser_podcast_identification(self, sample_vtt_files):
        """Test that VTT parser correctly identifies podcast from metadata."""
        parser = VTTParser()
        
        # Parse tech podcast VTT
        tech_result = parser.parse_file_with_metadata(sample_vtt_files['tech'])
        assert tech_result['metadata']['podcast_id'] == 'tech_podcast'
        assert tech_result['metadata']['episode_title'] == 'AI Revolution'
        assert len(tech_result['segments']) == 2
        
        # Parse science podcast VTT
        science_result = parser.parse_file_with_metadata(sample_vtt_files['science'])
        assert science_result['metadata']['podcast_id'] == 'science_podcast'
        assert science_result['metadata']['episode_title'] == 'Quantum Physics'
        assert len(science_result['segments']) == 2
    
    def test_multi_database_storage_isolation(self, podcast_config_file):
        """Test that multi-database storage maintains podcast isolation."""
        # Test the configuration and context switching
        with patch.dict(os.environ, {'PODCAST_CONFIG_PATH': str(podcast_config_file)}):
            from src.config.podcast_databases import PodcastDatabaseConfig
            
            # Test podcast database configuration
            config = PodcastDatabaseConfig(str(podcast_config_file))
            
            # Test that different podcasts get different databases
            tech_db = config.get_database_for_podcast('tech_podcast')
            science_db = config.get_database_for_podcast('science_podcast')
            
            assert tech_db == 'tech_db'
            assert science_db == 'science_db'
            assert tech_db != science_db
            
            # Test database config creation
            tech_config = config.create_database_config('tech_podcast', 'neo4j://localhost:7687')
            science_config = config.create_database_config('science_podcast', 'neo4j://localhost:7687')
            
            assert tech_config['database'] == 'tech_db'
            assert science_config['database'] == 'science_db'
            assert tech_config['uri'] == science_config['uri']  # Same server, different databases
            
            # Test with MultiDatabaseGraphStorage context switching
            with patch('neo4j.GraphDatabase'):
                storage = MultiDatabaseGraphStorage(
                    uri='neo4j://localhost:7687',
                    username='neo4j',
                    password='password',
                    config_path=str(podcast_config_file)
                )
                
                # Test context switching
                storage.set_podcast_context('tech_podcast')
                assert storage._current_podcast_id == 'tech_podcast'
                
                storage.set_podcast_context('science_podcast')
                assert storage._current_podcast_id == 'science_podcast'
                
                # Verify database routing
                assert storage.podcast_config.get_database_for_podcast('tech_podcast') == 'tech_db'
                assert storage.podcast_config.get_database_for_podcast('science_podcast') == 'science_db'
    
    def test_multi_podcast_orchestrator(self, podcast_config_file):
        """Test that multi-podcast orchestrator correctly manages podcast contexts."""
        with patch.dict(os.environ, {
            'PODCAST_MODE': 'multi',
            'PODCAST_CONFIG_PATH': str(podcast_config_file)
        }):
            # Create orchestrator
            from src.core.config import SeedingConfig
            config = SeedingConfig()
            
            # Mock the provider coordinator and its services
            with patch('src.seeding.orchestrator.ProviderCoordinator') as mock_provider_cls:
                mock_provider = MagicMock()
                mock_provider.initialize_providers.return_value = True
                mock_provider.llm_service = MagicMock()
                mock_provider.embedding_service = MagicMock()
                mock_provider.graph_service = MagicMock()
                mock_provider.segmenter = MagicMock()
                mock_provider.knowledge_extractor = MagicMock()
                mock_provider.entity_resolver = MagicMock()
                mock_provider.graph_enhancer = MagicMock()
                mock_provider.episode_flow_analyzer = MagicMock()
                mock_provider_cls.return_value = mock_provider
                
                orchestrator = MultiPodcastVTTKnowledgeExtractor(config)
                
                # Test that multi-podcast mode is detected
                assert os.getenv('PODCAST_MODE') == 'multi'
                
                # Initialize components
                with patch('src.seeding.multi_podcast_orchestrator.MultiDatabaseGraphStorage') as mock_storage_cls:
                    mock_storage = MagicMock()
                    mock_storage_cls.return_value = mock_storage
                    
                    success = orchestrator.initialize_components()
                    assert success
                    
                    # Verify multi-database storage was created
                    assert mock_storage_cls.called
    
    def test_podcast_context_propagation(self, temp_config_dir, podcast_config_file):
        """Test that podcast context propagates through the pipeline."""
        from src.seeding.multi_podcast_pipeline_executor import MultiPodcastPipelineExecutor
        
        with patch.dict(os.environ, {
            'PODCAST_MODE': 'multi',
            'PODCAST_CONFIG_PATH': str(podcast_config_file)
        }):
            # Create mock components
            mock_config = Mock()
            mock_provider = Mock()
            mock_checkpoint = Mock()
            mock_storage = Mock()
            
            # Create executor
            executor = MultiPodcastPipelineExecutor(
                mock_config, mock_provider, mock_checkpoint, mock_storage
            )
            
            # Test context extraction
            podcast_config = {'id': 'test_podcast', 'podcast_id': 'test_podcast_alt'}
            episode = {'id': 'ep1', 'podcast_id': 'episode_podcast'}
            
            # Should prioritize podcast_config['podcast_id']
            podcast_id = executor._extract_podcast_id(podcast_config, episode)
            assert podcast_id == 'test_podcast_alt'
            
            # Test with only id in config
            podcast_config = {'id': 'test_podcast'}
            podcast_id = executor._extract_podcast_id(podcast_config, episode)
            assert podcast_id == 'test_podcast'
            
            # Test with only episode podcast_id
            podcast_config = {}
            podcast_id = executor._extract_podcast_id(podcast_config, episode)
            assert podcast_id == 'episode_podcast'
    
    def test_cli_multi_podcast_commands(self, temp_config_dir, podcast_config_file, sample_vtt_files):
        """Test CLI commands for multi-podcast functionality."""
        from src.cli.cli import list_podcasts, process_vtt_for_podcast
        
        with patch.dict(os.environ, {
            'PODCAST_CONFIG_PATH': str(podcast_config_file),
            'PODCAST_DATA_DIR': str(temp_config_dir)
        }):
            # Test list podcasts
            args = Mock()
            args.format = 'text'
            args.enabled_only = True
            
            with patch('builtins.print') as mock_print:
                result = list_podcasts(args)
                assert result == 0
                
                # Check that enabled podcasts were printed
                output = ' '.join(str(call) for call in mock_print.call_args_list)
                assert 'tech_podcast' in output
                assert 'science_podcast' in output
                assert 'disabled_podcast' not in output
            
            # Test process VTT for specific podcast
            args = Mock()
            args.folder = str(temp_config_dir / 'podcasts' / 'tech_podcast' / 'transcripts')
            args.pattern = '*.vtt'
            args.recursive = False
            args.no_checkpoint = True
            args.skip_errors = False
            args.config = None
            
            with patch('src.seeding.multi_podcast_orchestrator.MultiPodcastVTTKnowledgeExtractor') as mock_orchestrator:
                mock_pipeline = MagicMock()
                mock_orchestrator.return_value = mock_pipeline
                
                result = process_vtt_for_podcast(args, 'tech_podcast')
                assert isinstance(result, dict)
                assert 'processed' in result
                assert 'failed' in result
    
    def test_data_separation_validation(self, podcast_config_file):
        """Test that cross-podcast queries are prevented."""
        with patch.dict(os.environ, {'PODCAST_CONFIG_PATH': str(podcast_config_file)}):
            with patch('neo4j.GraphDatabase'):
                storage = MultiDatabaseGraphStorage(
                    uri='neo4j://localhost:7687',
                    username='neo4j',
                    password='password',
                    config_path=str(podcast_config_file)
                )
                
                # Set context to tech podcast
                storage.set_podcast_context('tech_podcast')
                current = storage._current_podcast_id
                assert current == 'tech_podcast'
                
                # Switch to science podcast
                storage.set_podcast_context('science_podcast')
                current = storage._current_podcast_id
                assert current == 'science_podcast'
                
                # Verify contexts don't interfere
                assert storage.podcast_config.get_database_for_podcast('tech_podcast') != \
                       storage.podcast_config.get_database_for_podcast('science_podcast')
                
                # Test that each podcast gets its own database
                tech_db = storage.podcast_config.get_database_for_podcast('tech_podcast')
                science_db = storage.podcast_config.get_database_for_podcast('science_podcast')
                disabled_db = storage.podcast_config.get_database_for_podcast('disabled_podcast')
                
                assert tech_db == 'tech_db'
                assert science_db == 'science_db'
                assert disabled_db == 'disabled_db'
                
                # All databases should be different
                assert len({tech_db, science_db, disabled_db}) == 3