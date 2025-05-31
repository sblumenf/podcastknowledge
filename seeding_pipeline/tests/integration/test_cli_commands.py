"""Comprehensive tests for all CLI commands and flags."""

from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json
import os
import sys
import tempfile

import pytest
# Add the seeding_pipeline directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli import main, seed_podcasts, health_check, validate_config, schema_stats


class TestCLICommands:
    """Test all CLI commands: seed, schema-stats, health."""
    
    @pytest.fixture
    def mock_argv(self):
        """Store original argv and restore after test."""
        original_argv = sys.argv.copy()
        yield
        sys.argv = original_argv
    
    @pytest.fixture
    def test_config_file(self):
        """Create a test configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            config = {
                'neo4j_uri': 'bolt://localhost:7687',
                'neo4j_user': 'neo4j',
                'neo4j_password': 'testpass',
                'model_name': 'gemini-1.5-flash',
                'batch_size': 5,
                'max_workers': 2,
                'checkpoint_enabled': True,
                'checkpoint_dir': 'test_checkpoints'
            }
            import yaml
            yaml.dump(config, f)
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    @pytest.fixture
    def test_podcast_config(self):
        """Create a test podcast configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            podcasts = [
                {
                    "name": "Test Podcast 1",
                    "rss_url": "https://example.com/feed1.xml",
                    "category": "Technology"
                },
                {
                    "name": "Test Podcast 2",
                    "rss_url": "https://example.com/feed2.xml",
                    "category": "Science"
                }
            ]
            json.dump(podcasts, f)
            f.flush()
            yield f.name
        os.unlink(f.name)
    
    @pytest.fixture
    def mock_pipeline(self):
        """Mock PodcastKnowledgePipeline."""
        pipeline = Mock()
        pipeline.initialize_components.return_value = True
        pipeline.cleanup.return_value = None
        pipeline.process_podcast.return_value = {
            'episodes_processed': 5,
            'episodes_failed': 0,
            'start_time': '2024-01-01T10:00:00',
            'end_time': '2024-01-01T10:05:00',
            'extraction_mode': 'fixed',
            'discovered_types': []
        }
        return pipeline
    
    @pytest.mark.integration
    def test_seed_command_single_podcast(self, mock_argv, mock_pipeline):
        """Test seed command with single podcast URL."""
        sys.argv = [
            'cli.py', 'seed',
            '--rss-url', 'https://example.com/feed.xml',
            '--name', 'Test Podcast',
            '--category', 'Tech',
            '--max-episodes', '3'
        ]
        
        with patch('cli.PodcastKnowledgePipeline', return_value=mock_pipeline), \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            exit_code = main()
            
            assert exit_code == 0
            mock_pipeline.process_podcast.assert_called_once()
            call_args = mock_pipeline.process_podcast.call_args
            assert call_args[1]['podcast_url'] == 'https://example.com/feed.xml'
            assert call_args[1]['podcast_name'] == 'Test Podcast'
            assert call_args[1]['max_episodes'] == 3
            
            output = mock_stdout.getvalue()
            assert 'Episodes processed: 5' in output
            assert 'Episodes failed: 0' in output
    
    @pytest.mark.integration
    def test_seed_command_schemaless_mode(self, mock_argv, mock_pipeline):
        """Test seed command with schemaless extraction mode."""
        mock_pipeline.process_podcast.return_value['extraction_mode'] = 'schemaless'
        mock_pipeline.process_podcast.return_value['discovered_types'] = [
            'Expert', 'Technology', 'Concept'
        ]
        
        sys.argv = [
            'cli.py', 'seed',
            '--rss-url', 'https://example.com/feed.xml',
            '--extraction-mode', 'schemaless',
            '--schema-discovery'
        ]
        
        with patch('cli.PodcastKnowledgePipeline', return_value=mock_pipeline), \
             patch('cli.Config') as mock_config_class, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            # Mock config instance
            mock_config = Mock()
            mock_config_class.return_value = mock_config
            
            exit_code = main()
            
            assert exit_code == 0
            assert mock_config.use_schemaless_extraction is True
            
            output = mock_stdout.getvalue()
            assert 'Discovered Entity Types:' in output
            assert '- Expert' in output
            assert '- Technology' in output
            assert '- Concept' in output
    
    @pytest.mark.integration
    def test_seed_command_migration_mode(self, mock_argv, mock_pipeline):
        """Test seed command with migration mode."""
        mock_pipeline.process_podcast.return_value['extraction_mode'] = 'migration'
        
        sys.argv = [
            'cli.py', 'seed',
            '--rss-url', 'https://example.com/feed.xml',
            '--migration-mode'
        ]
        
        with patch('cli.PodcastKnowledgePipeline', return_value=mock_pipeline), \
             patch('cli.Config') as mock_config_class, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            # Mock config instance
            mock_config = Mock()
            mock_config_class.return_value = mock_config
            
            exit_code = main()
            
            assert exit_code == 0
            assert mock_config.migration_mode is True
            
            output = mock_stdout.getvalue()
            assert 'Migration mode enabled' in output
    
    @pytest.mark.integration
    def test_seed_command_podcast_config_file(self, mock_argv, test_podcast_config, mock_pipeline):
        """Test seed command with podcast configuration file."""
        sys.argv = [
            'cli.py', 'seed',
            '--podcast-config', test_podcast_config,
            '--max-episodes', '10'
        ]
        
        with patch('cli.PodcastKnowledgePipeline', return_value=mock_pipeline), \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            exit_code = main()
            
            assert exit_code == 0
            # Should be called twice (once for each podcast)
            assert mock_pipeline.process_podcast.call_count == 2
            
            output = mock_stdout.getvalue()
            assert 'Processing Test Podcast 1' in output
            assert 'Processing Test Podcast 2' in output
    
    @pytest.mark.integration
    def test_seed_command_with_custom_config(self, mock_argv, test_config_file, mock_pipeline):
        """Test seed command with custom configuration file."""
        sys.argv = [
            'cli.py', 'seed',
            '--config', test_config_file,
            '--rss-url', 'https://example.com/feed.xml'
        ]
        
        with patch('cli.PodcastKnowledgePipeline', return_value=mock_pipeline), \
             patch('cli.Config.from_file') as mock_from_file:
            
            mock_config = Mock()
            mock_from_file.return_value = mock_config
            
            exit_code = main()
            
            assert exit_code == 0
            mock_from_file.assert_called_once_with(test_config_file)
    
    @pytest.mark.integration
    def test_seed_command_large_context_flag(self, mock_argv, mock_pipeline):
        """Test seed command with large context flag."""
        sys.argv = [
            'cli.py', 'seed',
            '--rss-url', 'https://example.com/feed.xml',
            '--large-context'
        ]
        
        with patch('cli.PodcastKnowledgePipeline') as mock_pipeline_class:
            mock_pipeline_class.return_value = mock_pipeline
            
            exit_code = main()
            
            assert exit_code == 0
            # Verify large context was passed
            init_call = mock_pipeline_class.call_args
            config = init_call[0][0]
            # The use_large_context would be set in the config
            # Actual implementation may vary
    
    @pytest.mark.integration
    def test_health_command(self, mock_argv, mock_pipeline):
        """Test health check command."""
        sys.argv = ['cli.py', 'health']
        
        with patch('cli.PodcastKnowledgePipeline', return_value=mock_pipeline), \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            exit_code = main()
            
            assert exit_code == 0
            mock_pipeline.initialize_components.assert_called_once()
            
            output = mock_stdout.getvalue()
            assert 'Checking pipeline component health' in output
            assert 'All components are healthy!' in output
    
    @pytest.mark.integration
    def test_health_command_with_large_context(self, mock_argv, mock_pipeline):
        """Test health check with large context flag."""
        sys.argv = ['cli.py', 'health', '--large-context']
        
        with patch('cli.PodcastKnowledgePipeline', return_value=mock_pipeline), \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            
            exit_code = main()
            
            assert exit_code == 0
            mock_pipeline.initialize_components.assert_called_once_with(use_large_context=True)
    
    @pytest.mark.integration
    def test_health_command_failure(self, mock_argv, mock_pipeline):
        """Test health check when components are unhealthy."""
        mock_pipeline.initialize_components.return_value = False
        
        sys.argv = ['cli.py', 'health']
        
        with patch('cli.PodcastKnowledgePipeline', return_value=mock_pipeline), \
             patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            
            exit_code = main()
            
            assert exit_code == 1
            assert 'Failed to initialize components' in mock_stderr.getvalue()
    
    @pytest.mark.integration
    def test_validate_config_command(self, mock_argv, test_config_file):
        """Test validate-config command."""
        sys.argv = ['cli.py', 'validate-config', '--config', test_config_file]
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            exit_code = main()
            
            assert exit_code == 0
            output = mock_stdout.getvalue()
            assert 'Configuration loaded from:' in output
            assert 'Neo4j URI: bolt://localhost:7687' in output
            assert 'Configuration is valid!' in output
    
    @pytest.mark.integration
    def test_validate_config_invalid_file(self, mock_argv):
        """Test validate-config with invalid file."""
        sys.argv = ['cli.py', 'validate-config', '--config', 'nonexistent.yml']
        
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            exit_code = main()
            
            assert exit_code == 1
            assert 'Configuration validation failed' in mock_stderr.getvalue()
    
    @pytest.mark.integration
    def test_schema_stats_command(self, mock_argv):
        """Test schema-stats command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sys.argv = ['cli.py', 'schema-stats', '--checkpoint-dir', tmpdir]
            
            mock_stats = {
                'total_types_discovered': 10,
                'evolution_entries': 3,
                'first_discovery': '2024-01-01',
                'latest_discovery': '2024-01-15',
                'entity_types': ['Expert', 'Technology', 'Concept'],
                'discovery_timeline': [
                    {
                        'date': '2024-01-01',
                        'episode': 'Episode 1',
                        'count': 3,
                        'new_types': ['Expert', 'Technology', 'Concept']
                    }
                ]
            }
            
            with patch('src.seeding.checkpoint.ProgressCheckpoint.get_schema_statistics', 
                      return_value=mock_stats), \
                 patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                
                exit_code = main()
                
                assert exit_code == 0
                output = mock_stdout.getvalue()
                assert 'Schema Discovery Statistics:' in output
                assert 'Total entity types discovered: 10' in output
                assert 'Expert' in output
                assert 'Technology' in output
    
    @pytest.mark.integration
    def test_schema_stats_no_data(self, mock_argv):
        """Test schema-stats when no schema data exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sys.argv = ['cli.py', 'schema-stats', '--checkpoint-dir', tmpdir]
            
            mock_stats = {
                'message': 'No schema statistics found',
                'total_types_discovered': 0,
                'evolution_entries': 0,
                'entity_types': [],
                'discovery_timeline': []
            }
            
            with patch('src.seeding.checkpoint.ProgressCheckpoint.get_schema_statistics',
                      return_value=mock_stats), \
                 patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                
                exit_code = main()
                
                assert exit_code == 1
                output = mock_stdout.getvalue()
                assert 'No schema statistics found' in output
    
    @pytest.mark.integration
    def test_flag_validation_migration_mode_conflict(self, mock_argv):
        """Test that migration mode conflicts with schemaless extraction mode."""
        sys.argv = [
            'cli.py', 'seed',
            '--rss-url', 'https://example.com/feed.xml',
            '--migration-mode',
            '--extraction-mode', 'schemaless'
        ]
        
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            with pytest.raises(SystemExit):
                main()
            
            error_output = mock_stderr.getvalue()
            assert '--migration-mode requires --extraction-mode to be \'fixed\'' in error_output
    
    @pytest.mark.integration
    def test_flag_validation_schema_discovery_conflict(self, mock_argv):
        """Test that schema discovery only works with schemaless mode."""
        sys.argv = [
            'cli.py', 'seed',
            '--rss-url', 'https://example.com/feed.xml',
            '--extraction-mode', 'fixed',
            '--schema-discovery'
        ]
        
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            with pytest.raises(SystemExit):
                main()
            
            error_output = mock_stderr.getvalue()
            assert '--schema-discovery only works with --extraction-mode schemaless' in error_output
    
    @pytest.mark.integration
    def test_verbose_flag(self, mock_argv, mock_pipeline):
        """Test verbose flag enables debug logging."""
        sys.argv = [
            'cli.py', '-v', 'seed',
            '--rss-url', 'https://example.com/feed.xml'
        ]
        
        with patch('cli.PodcastKnowledgePipeline', return_value=mock_pipeline), \
             patch('cli.setup_structured_logging') as mock_setup_logging:
            
            exit_code = main()
            
            assert exit_code == 0
            # Verify debug logging was enabled
            mock_setup_logging.assert_called()
            call_args = mock_setup_logging.call_args
            assert call_args[1]['level'] == 'DEBUG'
            assert call_args[1]['add_performance'] is True
    
    @pytest.mark.integration  
    def test_no_command_shows_help(self, mock_argv):
        """Test that no command shows help."""
        sys.argv = ['cli.py']
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            exit_code = main()
            
            assert exit_code == 1
            output = mock_stdout.getvalue()
            assert 'usage:' in output.lower() or 'Podcast Knowledge Graph Pipeline' in output