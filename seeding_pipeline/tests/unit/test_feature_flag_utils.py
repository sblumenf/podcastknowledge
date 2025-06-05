"""Unit tests for feature flag utilities."""

from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock
import json
import os
import sys

import pytest
import yaml

from src.core.feature_flags import FeatureFlag
from src.utils.feature_flag_utils import (
    print_feature_flags,
    export_feature_flags,
    generate_env_template,
    validate_feature_flags,
    set_feature_flag_from_env,
    feature_flag_cli_handler
)


class TestPrintFeatureFlags:
    """Test print_feature_flags function."""
    
    @patch('src.utils.feature_flag_utils.get_all_flags')
    @patch('builtins.print')
    def test_print_feature_flags(self, mock_print, mock_get_flags):
        """Test printing feature flags."""
        mock_get_flags.return_value = {
            'ENABLE_SCHEMALESS_EXTRACTION': {
                'current': True,
                'default': False,
                'description': 'Enable schemaless mode',
                'env_var': 'ENABLE_SCHEMALESS_EXTRACTION'
            },
            'ENABLE_ENTITY_RESOLUTION_V2': {
                'current': False,
                'default': False,
                'description': 'Enable entity resolution v2',
                'env_var': 'ENABLE_ENTITY_RESOLUTION_V2'
            },
            'ENABLE_QUOTE_ENHANCEMENT': {
                'current': True,
                'default': True,
                'description': 'Enable quote enhancement',
                'env_var': 'ENABLE_QUOTE_ENHANCEMENT'
            }
        }
        
        print_feature_flags()
        
        # Check that headers were printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any("Feature Flags Status" in call for call in print_calls)
        assert any("Schemaless Extraction Flags:" in call for call in print_calls)
        assert any("Component Enhancement Flags:" in call for call in print_calls)
        
        # Check flags were printed with status
        assert any("ENABLE_SCHEMALESS_EXTRACTION" in call and "✓ ENABLED" in call 
                  for call in print_calls)
        assert any("ENABLE_ENTITY_RESOLUTION_V2" in call and "✗ DISABLED" in call 
                  for call in print_calls)
    
    @patch('src.utils.feature_flag_utils.get_all_flags')
    @patch('builtins.print')
    def test_print_empty_flags(self, mock_print, mock_get_flags):
        """Test printing when no flags exist."""
        mock_get_flags.return_value = {}
        
        print_feature_flags()
        
        # Should still print headers
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any("Feature Flags Status" in call for call in print_calls)


class TestExportFeatureFlags:
    """Test export_feature_flags function."""
    
    @patch('src.utils.feature_flag_utils.get_all_flags')
    def test_export_to_dict(self, mock_get_flags):
        """Test exporting flags to dictionary without file."""
        mock_get_flags.return_value = {
            'TEST_FLAG': {
                'current': True,
                'default': False,
                'description': 'Test flag',
                'env_var': 'TEST_FLAG_ENV'
            }
        }
        
        result = export_feature_flags()
        
        assert 'feature_flags' in result
        assert 'environment_variables' in result
        assert result['feature_flags']['TEST_FLAG']['enabled'] is True
        assert result['feature_flags']['TEST_FLAG']['description'] == 'Test flag'
        assert result['environment_variables']['TEST_FLAG_ENV'] == 'true'
    
    @patch('src.utils.feature_flag_utils.get_all_flags')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_export_to_json_file(self, mock_mkdir, mock_file, mock_get_flags):
        """Test exporting flags to JSON file."""
        mock_get_flags.return_value = {
            'FLAG1': {
                'current': True,
                'default': False,
                'description': 'Flag 1',
                'env_var': 'FLAG1_ENV'
            }
        }
        
        output_path = Path("/tmp/flags.json")
        result = export_feature_flags(output_path, format="json")
        
        # Check file operations
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_file.assert_called_once_with(output_path, 'w')
        
        # Check JSON was written
        write_calls = mock_file().write.call_args_list
        written_content = ''.join([call[0][0] for call in write_calls])
        
        # Should be valid JSON
        data = json.loads(written_content)
        assert data['feature_flags']['FLAG1']['enabled'] is True
    
    @patch('src.utils.feature_flag_utils.get_all_flags')
    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.mkdir')
    def test_export_to_yaml_file(self, mock_mkdir, mock_file, mock_get_flags):
        """Test exporting flags to YAML file."""
        mock_get_flags.return_value = {
            'FLAG1': {
                'current': False,
                'default': True,
                'description': 'Flag 1',
                'env_var': 'FLAG1_ENV'
            }
        }
        
        output_path = Path("/tmp/flags.yaml")
        result = export_feature_flags(output_path, format="yaml")
        
        mock_file.assert_called_once_with(output_path, 'w')
        
        # Check that yaml.dump was called on the file handle
        handle = mock_file()
        assert handle.write.called or handle.__enter__().write.called
    
    @patch('src.utils.feature_flag_utils.get_all_flags')
    def test_export_invalid_format(self, mock_get_flags):
        """Test exporting with invalid format."""
        mock_get_flags.return_value = {}
        
        with pytest.raises(ValueError, match="Unsupported format: xml"):
            export_feature_flags(Path("/tmp/flags.xml"), format="xml")


class TestGenerateEnvTemplate:
    """Test generate_env_template function."""
    
    @patch('src.utils.feature_flag_utils.get_all_flags')
    def test_generate_template_string(self, mock_get_flags):
        """Test generating environment template as string."""
        mock_get_flags.return_value = {
            'ENABLE_SCHEMALESS_EXTRACTION': {
                'current': True,
                'default': False,
                'description': 'Enable schemaless extraction',
                'env_var': 'ENABLE_SCHEMALESS_EXTRACTION'
            },
            'ENABLE_SPEAKER_ENHANCEMENT': {
                'current': False,
                'default': True,
                'description': 'Enable speaker enhancement',
                'env_var': 'ENABLE_SPEAKER_ENHANCEMENT'
            }
        }
        
        template = generate_env_template()
        
        # Check template structure
        assert "# Feature Flags for Podcast Knowledge Pipeline" in template
        assert "# Generated template" in template
        
        # Check flags are included
        assert "# Enable schemaless extraction" in template
        assert "# ENABLE_SCHEMALESS_EXTRACTION=false" in template
        assert "# Enable speaker enhancement" in template
        assert "# ENABLE_SPEAKER_ENHANCEMENT=true" in template
        
        # Check sections
        assert "# Schemaless Extraction Flags" in template
        assert "# Component Enhancement Flags" in template
    
    @patch('src.utils.feature_flag_utils.get_all_flags')
    @patch('pathlib.Path.write_text')
    @patch('pathlib.Path.mkdir')
    def test_generate_template_to_file(self, mock_mkdir, mock_write_text, mock_get_flags):
        """Test writing environment template to file."""
        mock_get_flags.return_value = {
            'TEST_FLAG': {
                'current': True,
                'default': False,
                'description': 'Test flag',
                'env_var': 'TEST_FLAG'
            }
        }
        
        output_path = Path("/tmp/.env.template")
        template = generate_env_template(output_path)
        
        # Check file operations
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_write_text.assert_called_once()
        
        # Check template content
        written_template = mock_write_text.call_args[0][0]
        assert "# Test flag" in written_template
        assert "# TEST_FLAG=false" in written_template


class TestValidateFeatureFlags:
    """Test validate_feature_flags function."""
    
    @patch('src.utils.feature_flag_utils.get_feature_flag_manager')
    @patch('src.utils.feature_flag_utils.logger')
    def test_valid_flags(self, mock_logger, mock_get_manager):
        """Test validation with valid flag combinations."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        # All flags disabled - valid
        mock_manager.is_enabled.return_value = False
        
        result = validate_feature_flags()
        assert result is True
        mock_logger.info.assert_called_with("Feature flag validation passed")
    
    @patch('src.utils.feature_flag_utils.get_feature_flag_manager')
    @patch('src.utils.feature_flag_utils.logger')
    def test_migration_mode_requires_schemaless(self, mock_logger, mock_get_manager):
        """Test that migration mode requires schemaless extraction."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        # Configure manager to return specific values for each flag
        def is_enabled_side_effect(flag):
            if flag == FeatureFlag.SCHEMALESS_MIGRATION_MODE:
                return True
            elif flag == FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION:
                return False
            return False
        
        mock_manager.is_enabled.side_effect = is_enabled_side_effect
        
        result = validate_feature_flags()
        assert result is False
        
        # Check error was logged
        error_calls = mock_logger.error.call_args_list
        assert any("SCHEMALESS_MIGRATION_MODE requires ENABLE_SCHEMALESS_EXTRACTION" 
                  in str(call) for call in error_calls)
    
    @patch('src.utils.feature_flag_utils.get_feature_flag_manager')
    @patch('src.utils.feature_flag_utils.logger')
    def test_entity_resolution_v2_requires_schemaless(self, mock_logger, mock_get_manager):
        """Test that entity resolution v2 requires schemaless extraction."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        def is_enabled_side_effect(flag):
            if flag == FeatureFlag.ENABLE_ENTITY_RESOLUTION_V2:
                return True
            elif flag == FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION:
                return False
            return False
        
        mock_manager.is_enabled.side_effect = is_enabled_side_effect
        
        result = validate_feature_flags()
        assert result is False
        
        error_calls = mock_logger.error.call_args_list
        assert any("ENABLE_ENTITY_RESOLUTION_V2 requires ENABLE_SCHEMALESS_EXTRACTION" 
                  in str(call) for call in error_calls)
    
    @patch('src.utils.feature_flag_utils.get_feature_flag_manager')
    @patch('src.utils.feature_flag_utils.logger')
    def test_multiple_validation_errors(self, mock_logger, mock_get_manager):
        """Test multiple validation errors."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        def is_enabled_side_effect(flag):
            if flag in (FeatureFlag.SCHEMALESS_MIGRATION_MODE, 
                       FeatureFlag.ENABLE_ENTITY_RESOLUTION_V2):
                return True
            elif flag == FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION:
                return False
            return False
        
        mock_manager.is_enabled.side_effect = is_enabled_side_effect
        
        result = validate_feature_flags()
        assert result is False
        
        # Should log both errors
        error_messages = [str(call) for call in mock_logger.error.call_args_list]
        assert any("SCHEMALESS_MIGRATION_MODE" in msg for msg in error_messages)
        assert any("ENABLE_ENTITY_RESOLUTION_V2" in msg for msg in error_messages)


class TestSetFeatureFlagFromEnv:
    """Test set_feature_flag_from_env function."""
    
    @patch('src.utils.feature_flag_utils.get_feature_flag_manager')
    def test_set_valid_flag_true(self, mock_get_manager):
        """Test setting a valid flag to true."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        # Test various true values
        for value in ["true", "True", "TRUE", "1", "yes", "Yes", "on", "ON"]:
            result = set_feature_flag_from_env("ENABLE_SCHEMALESS_EXTRACTION", value)
            assert result is True
            
            # Check that flag was set to True
            mock_manager.set_flag.assert_called_with(
                FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION, True
            )
    
    @patch('src.utils.feature_flag_utils.get_feature_flag_manager')
    def test_set_valid_flag_false(self, mock_get_manager):
        """Test setting a valid flag to false."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        # Test various false values
        for value in ["false", "False", "FALSE", "0", "no", "No", "off", "OFF", ""]:
            result = set_feature_flag_from_env("ENABLE_SCHEMALESS_EXTRACTION", value)
            assert result is True
            
            # Check that flag was set to False
            mock_manager.set_flag.assert_called_with(
                FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION, False
            )
    
    @patch('src.utils.feature_flag_utils.logger')
    def test_set_invalid_flag_name(self, mock_logger):
        """Test setting an invalid flag name."""
        result = set_feature_flag_from_env("INVALID_FLAG_NAME", "true")
        assert result is False
        
        # Check error was logged
        mock_logger.error.assert_called_once()
        error_msg = str(mock_logger.error.call_args)
        assert "Unknown feature flag: INVALID_FLAG_NAME" in error_msg
    
    @patch('src.utils.feature_flag_utils.get_feature_flag_manager')
    @patch('src.utils.feature_flag_utils.logger')
    def test_set_flag_with_exception(self, mock_logger, mock_get_manager):
        """Test handling exceptions when setting flags."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        mock_manager.set_flag.side_effect = Exception("Test error")
        
        result = set_feature_flag_from_env("ENABLE_SCHEMALESS_EXTRACTION", "true")
        assert result is False
        
        # Check error was logged
        mock_logger.error.assert_called_once()
        error_msg = str(mock_logger.error.call_args)
        assert "Failed to set feature flag" in error_msg
        assert "Test error" in error_msg


class TestFeatureFlagCliHandler:
    """Test feature_flag_cli_handler function."""
    
    @patch('src.utils.feature_flag_utils.print_feature_flags')
    def test_list_command(self, mock_print_flags):
        """Test 'list' command."""
        args = Mock(command='list')
        result = feature_flag_cli_handler(args)
        
        assert result == 0
        mock_print_flags.assert_called_once()
    
    @patch('src.utils.feature_flag_utils.export_feature_flags')
    @patch('builtins.print')
    def test_export_command(self, mock_print, mock_export):
        """Test 'export' command."""
        args = Mock(
            command='export',
            output=Path('/tmp/flags.json'),
            format='json'
        )
        
        result = feature_flag_cli_handler(args)
        
        assert result == 0
        mock_export.assert_called_once_with(args.output, args.format)
        mock_print.assert_called_once()
        assert "exported to /tmp/flags.json" in str(mock_print.call_args)
    
    @patch('src.utils.feature_flag_utils.generate_env_template')
    @patch('builtins.print')
    def test_env_template_command(self, mock_print, mock_generate):
        """Test 'env-template' command."""
        args = Mock(
            command='env-template',
            output=Path('/tmp/.env.template')
        )
        
        result = feature_flag_cli_handler(args)
        
        assert result == 0
        mock_generate.assert_called_once_with(args.output)
        mock_print.assert_called_once()
        assert "generated at /tmp/.env.template" in str(mock_print.call_args)
    
    @patch('src.utils.feature_flag_utils.validate_feature_flags')
    @patch('builtins.print')
    def test_validate_command_success(self, mock_print, mock_validate):
        """Test 'validate' command with successful validation."""
        args = Mock(command='validate')
        mock_validate.return_value = True
        
        result = feature_flag_cli_handler(args)
        
        assert result == 0
        mock_validate.assert_called_once()
        mock_print.assert_called_once_with("✓ Feature flag validation passed")
    
    @patch('src.utils.feature_flag_utils.validate_feature_flags')
    @patch('builtins.print')
    def test_validate_command_failure(self, mock_print, mock_validate):
        """Test 'validate' command with failed validation."""
        args = Mock(command='validate')
        mock_validate.return_value = False
        
        result = feature_flag_cli_handler(args)
        
        assert result == 1
        mock_validate.assert_called_once()
        mock_print.assert_called_once_with("✗ Feature flag validation failed")


class TestIntegrationScenarios:
    """Test integration scenarios for feature flag utilities."""
    
    @patch('src.utils.feature_flag_utils.get_all_flags')
    def test_full_export_import_cycle(self, mock_get_flags):
        """Test exporting flags and using them to set environment."""
        # Initial flags
        mock_get_flags.return_value = {
            'ENABLE_FEATURE_A': {
                'current': True,
                'default': False,
                'description': 'Feature A',
                'env_var': 'ENABLE_FEATURE_A'
            },
            'ENABLE_FEATURE_B': {
                'current': False,
                'default': True,
                'description': 'Feature B',
                'env_var': 'ENABLE_FEATURE_B'
            }
        }
        
        # Export flags
        exported = export_feature_flags()
        
        # Check exported environment variables
        env_vars = exported['environment_variables']
        assert env_vars['ENABLE_FEATURE_A'] == 'true'
        assert env_vars['ENABLE_FEATURE_B'] == 'false'
        
        # Could use these to set environment in a shell script
        for env_var, value in env_vars.items():
            assert isinstance(value, str)
            assert value in ['true', 'false']
    
    @patch('src.utils.feature_flag_utils.get_all_flags')
    @patch('builtins.print')
    def test_categorization_of_flags(self, mock_print, mock_get_flags):
        """Test that flags are properly categorized."""
        mock_get_flags.return_value = {
            'ENABLE_SCHEMALESS_EXTRACTION': {
                'current': True,
                'default': False,
                'description': 'Schemaless mode',
                'env_var': 'ENABLE_SCHEMALESS_EXTRACTION'
            },
            'SCHEMALESS_MIGRATION_MODE': {
                'current': False,
                'default': False,
                'description': 'Migration mode',
                'env_var': 'SCHEMALESS_MIGRATION_MODE'
            },
            'ENABLE_ENTITY_RESOLUTION_V2': {
                'current': True,
                'default': False,
                'description': 'Entity resolution v2',
                'env_var': 'ENABLE_ENTITY_RESOLUTION_V2'
            },
            'ENABLE_TIMESTAMP_ENHANCEMENT': {
                'current': True,
                'default': True,
                'description': 'Timestamp enhancement',
                'env_var': 'ENABLE_TIMESTAMP_ENHANCEMENT'
            }
        }
        
        print_feature_flags()
        
        # Check that flags are printed in correct sections
        print_calls = [str(call) for call in mock_print.call_args_list]
        
        # Find the index of section headers
        schemaless_idx = next(i for i, call in enumerate(print_calls) 
                             if "Schemaless Extraction Flags:" in call)
        component_idx = next(i for i, call in enumerate(print_calls) 
                            if "Component Enhancement Flags:" in call)
        
        # Schemaless flags should be between the headers
        schemaless_section = print_calls[schemaless_idx:component_idx]
        assert any("ENABLE_SCHEMALESS_EXTRACTION" in call for call in schemaless_section)
        assert any("SCHEMALESS_MIGRATION_MODE" in call for call in schemaless_section)
        assert any("ENABLE_ENTITY_RESOLUTION_V2" in call for call in schemaless_section)
        
        # Component flags should be after component header
        component_section = print_calls[component_idx:]
        assert any("ENABLE_TIMESTAMP_ENHANCEMENT" in call for call in component_section)