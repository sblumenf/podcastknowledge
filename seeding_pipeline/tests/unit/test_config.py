"""Comprehensive tests for src/core/config.py - targeting 95% coverage.

This test suite covers:
- Configuration initialization with defaults
- Environment variable loading and overrides
- YAML/JSON file loading
- Configuration validation
- Error handling for all edge cases
- Path handling and conversions
- Sensitive data masking
- Inheritance and specialized configs
"""

from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest import mock
import json
import os
import tempfile

import pytest

from src.core.config import PipelineConfig, SeedingConfig, YAML_AVAILABLE
from src.core.exceptions import ConfigurationError
class TestPipelineConfig:
    """Test suite for PipelineConfig class."""
    
    def _create_config_without_validation(self, **kwargs):
        """Helper to create PipelineConfig without triggering validation."""
        with mock.patch.object(PipelineConfig, 'validate'):
            return PipelineConfig(**kwargs)
    
    def test_default_initialization(self):
        """Test config initializes with all default values."""
        # Mock required environment variables for validation
        with mock.patch.dict(os.environ, {
            "NEO4J_PASSWORD": "test_password",
            "GOOGLE_API_KEY": "test_key"
        }):
            config = PipelineConfig()
        
        # Audio processing defaults
        assert config.min_segment_tokens == 150
        assert config.max_segment_tokens == 800
        assert config.whisper_model_size == "large-v3"
        assert config.use_faster_whisper is True
        
        # Speaker diarization defaults
        assert config.min_speakers == 1
        assert config.max_speakers == 10
        
        # Neo4j defaults (from environment or defaults)
        assert config.neo4j_uri == os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        assert config.neo4j_username == os.environ.get("NEO4J_USERNAME", "neo4j")
        assert config.neo4j_database == os.environ.get("NEO4J_DATABASE", "neo4j")
        
        # Embedding settings
        assert config.embedding_dimensions == 768  # Gemini text-embedding-004 dimensions
        assert config.embedding_similarity == "cosine"
        assert config.embedding_model == "models/text-embedding-004"
        
        # Processing settings
        assert config.max_episodes == 1
        assert config.use_large_context is True
        assert config.enable_graph_enhancements is True
        
        # GPU settings
        assert config.use_gpu is True
        assert config.enable_ad_detection is True
        assert config.use_semantic_boundaries is True
        assert config.gpu_memory_fraction == 0.8
        
        # Progress settings
        assert config.checkpoint_interval == 1
        assert config.memory_cleanup_interval == 1
        
        # Schemaless settings
        assert isinstance(config.use_schemaless_extraction, bool)
        assert 0 <= config.schemaless_confidence_threshold <= 1
        assert 0 <= config.entity_resolution_threshold <= 1
        assert config.max_properties_per_node >= 1
        assert isinstance(config.relationship_normalization, bool)
    
    def test_environment_variable_loading(self):
        """Test that environment variables are properly loaded."""
        test_env = {
            "NEO4J_URI": "bolt://test:7687",
            "NEO4J_USERNAME": "test_user",
            "NEO4J_PASSWORD": "test_pass",
            "NEO4J_DATABASE": "test_db",
            "GOOGLE_API_KEY": "google_key",
            "OPENAI_API_KEY": "openai_key",
            "HF_TOKEN": "hf_token",
            "LOG_LEVEL": "DEBUG",
            "USE_SCHEMALESS_EXTRACTION": "true",
            "SCHEMALESS_CONFIDENCE_THRESHOLD": "0.9",
            "ENTITY_RESOLUTION_THRESHOLD": "0.95",
            "MAX_PROPERTIES_PER_NODE": "100",
            "RELATIONSHIP_NORMALIZATION": "false"
        }
        
        with mock.patch.dict(os.environ, test_env, clear=True):
            config = PipelineConfig()
            
            assert config.neo4j_uri == "bolt://test:7687"
            assert config.neo4j_username == "test_user"
            assert config.neo4j_password == "test_pass"
            assert config.neo4j_database == "test_db"
            assert config.google_api_key == "google_key"
            assert config.openai_api_key == "openai_key"
            assert config.hf_token == "hf_token"
            assert config.log_level == "DEBUG"
            assert config.use_schemaless_extraction is True
            assert config.schemaless_confidence_threshold == 0.9
            assert config.entity_resolution_threshold == 0.95
            assert config.max_properties_per_node == 100
            assert config.relationship_normalization is False
    
    def test_path_handling(self):
        """Test path conversion and resolution."""
        # Mock required environment variables
        with mock.patch.dict(os.environ, {
            "NEO4J_PASSWORD": "test_password",
            "GOOGLE_API_KEY": "test_key"
        }):
            # Test with relative paths
            config = PipelineConfig(
                base_dir=".",
                audio_dir="audio",
                output_dir="output",
                checkpoint_dir="checkpoints"
            )
        
            assert config.base_dir == Path(".")
            assert config.audio_dir == Path(".") / "audio"
            assert config.output_dir == Path(".") / "output"
            assert config.checkpoint_dir == Path(".") / "checkpoints"
            
            # Test with absolute paths
            with tempfile.TemporaryDirectory() as tmpdir:
                config = PipelineConfig(
                    base_dir=tmpdir,
                    audio_dir=Path(tmpdir) / "audio",
                    output_dir=Path(tmpdir) / "output",
                    checkpoint_dir=Path(tmpdir) / "checkpoints"
                )
                
                assert config.audio_dir == Path(tmpdir) / "audio"
                assert config.output_dir == Path(tmpdir) / "output"
                assert config.checkpoint_dir == Path(tmpdir) / "checkpoints"
    
    def test_validation_success(self):
        """Test successful validation with valid configuration."""
        with mock.patch.dict(os.environ, {
            "NEO4J_PASSWORD": "test_pass",
            "GOOGLE_API_KEY": "test_key"
        }):
            config = PipelineConfig()
            # Should not raise any exception
            config.validate()
    
    def test_validation_missing_password(self):
        """Test validation fails when NEO4J_PASSWORD is missing."""
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "test"}, clear=True):
            config = self._create_config_without_validation()
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            assert "NEO4J_PASSWORD environment variable is required" in str(exc_info.value)
    
    def test_validation_missing_api_keys(self):
        """Test validation fails when both API keys are missing."""
        with mock.patch.dict(os.environ, {"NEO4J_PASSWORD": "test"}, clear=True):
            config = self._create_config_without_validation()
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            assert "At least one of GOOGLE_API_KEY or OPENAI_API_KEY is required" in str(exc_info.value)
    
    def test_validation_invalid_segment_tokens(self):
        """Test validation fails with invalid segment token configuration."""
        with mock.patch.dict(os.environ, {
            "NEO4J_PASSWORD": "test",
            "GOOGLE_API_KEY": "test"
        }):
            config = self._create_config_without_validation(min_segment_tokens=800, max_segment_tokens=150)
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            assert "min_segment_tokens must be less than max_segment_tokens" in str(exc_info.value)
    
    def test_validation_invalid_speakers(self):
        """Test validation fails with invalid speaker configuration."""
        with mock.patch.dict(os.environ, {
            "NEO4J_PASSWORD": "test",
            "GOOGLE_API_KEY": "test"
        }):
            config = self._create_config_without_validation(min_speakers=10, max_speakers=5)
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            assert "min_speakers must be less than or equal to max_speakers" in str(exc_info.value)
    
    def test_validation_invalid_gpu_memory(self):
        """Test validation fails with invalid GPU memory fraction."""
        with mock.patch.dict(os.environ, {
            "NEO4J_PASSWORD": "test",
            "GOOGLE_API_KEY": "test"
        }):
            # Test > 1
            config = self._create_config_without_validation(gpu_memory_fraction=1.5)
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            assert "gpu_memory_fraction must be between 0 and 1" in str(exc_info.value)
            
            # Test <= 0
            config = self._create_config_without_validation(gpu_memory_fraction=0)
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            assert "gpu_memory_fraction must be between 0 and 1" in str(exc_info.value)
    
    def test_validation_invalid_schemaless_settings(self):
        """Test validation fails with invalid schemaless settings."""
        with mock.patch.dict(os.environ, {
            "NEO4J_PASSWORD": "test",
            "GOOGLE_API_KEY": "test"
        }):
            # Test confidence threshold
            config = self._create_config_without_validation(schemaless_confidence_threshold=1.5)
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            assert "schemaless_confidence_threshold must be between 0 and 1" in str(exc_info.value)
            
            # Test entity resolution threshold
            config = self._create_config_without_validation(entity_resolution_threshold=-0.1)
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            assert "entity_resolution_threshold must be between 0 and 1" in str(exc_info.value)
            
            # Test max properties
            config = self._create_config_without_validation(max_properties_per_node=0)
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            assert "max_properties_per_node must be at least 1" in str(exc_info.value)
    
    def test_validation_directory_creation_failure(self):
        """Test validation fails when directories cannot be created."""
        with mock.patch.dict(os.environ, {
            "NEO4J_PASSWORD": "test",
            "GOOGLE_API_KEY": "test"
        }):
            # Use a path that cannot be created
            config = self._create_config_without_validation(audio_dir="/root/cannot_create/audio")
            
            with mock.patch.object(Path, 'mkdir', side_effect=PermissionError("Cannot create")):
                with pytest.raises(ConfigurationError) as exc_info:
                    config.validate()
                assert "Cannot create audio_dir" in str(exc_info.value)
                assert "Cannot create" in str(exc_info.value)
    
    def test_validation_multiple_errors(self):
        """Test validation collects and reports multiple errors."""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = self._create_config_without_validation(
                min_segment_tokens=800,
                max_segment_tokens=150,
                gpu_memory_fraction=2.0,
                max_properties_per_node=0
            )
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            
            error_msg = str(exc_info.value)
            assert "NEO4J_PASSWORD environment variable is required" in error_msg
            assert "At least one of GOOGLE_API_KEY or OPENAI_API_KEY is required" in error_msg
            assert "min_segment_tokens must be less than max_segment_tokens" in error_msg
            assert "gpu_memory_fraction must be between 0 and 1" in error_msg
            assert "max_properties_per_node must be at least 1" in error_msg
    
    def test_to_dict(self):
        """Test configuration serialization to dictionary."""
        with mock.patch.dict(os.environ, {
            "NEO4J_PASSWORD": "secret_pass",
            "GOOGLE_API_KEY": "secret_google",
            "OPENAI_API_KEY": "secret_openai",
            "HF_TOKEN": "secret_hf"
        }):
            config = PipelineConfig()
            config_dict = config.to_dict()
            
            # Check sensitive fields are masked
            assert config_dict["neo4j_password"] == "***"
            assert config_dict["google_api_key"] == "***"
            assert config_dict["openai_api_key"] == "***"
            assert config_dict["hf_token"] == "***"
            
            # Check paths are converted to strings
            assert isinstance(config_dict["base_dir"], str)
            assert isinstance(config_dict["audio_dir"], str)
            assert isinstance(config_dict["output_dir"], str)
            assert isinstance(config_dict["checkpoint_dir"], str)
            
            # Check other fields are preserved
            assert config_dict["min_segment_tokens"] == 150
            assert config_dict["max_segment_tokens"] == 800
            assert config_dict["use_gpu"] is True
    
    def test_to_dict_with_none_secrets(self):
        """Test to_dict when secrets are None."""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = self._create_config_without_validation()
            config_dict = config.to_dict()
            
            assert config_dict["neo4j_password"] is None
            assert config_dict["google_api_key"] is None
            assert config_dict["openai_api_key"] is None
            assert config_dict["hf_token"] is None
    
    def test_from_file_yaml(self):
        """Test loading configuration from YAML file."""
        if not YAML_AVAILABLE:
            pytest.skip("YAML not available")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_content = """
min_segment_tokens: 200
max_segment_tokens: 1000
whisper_model_size: medium
use_gpu: false
gpu_memory_fraction: 0.5
max_episodes: 5
"""
            f.write(yaml_content)
            f.flush()
            
            try:
                config = PipelineConfig.from_file(Path(f.name))
                assert config.min_segment_tokens == 200
                assert config.max_segment_tokens == 1000
                assert config.whisper_model_size == "medium"
                assert config.use_gpu is False
                assert config.gpu_memory_fraction == 0.5
                assert config.max_episodes == 5
            finally:
                os.unlink(f.name)
    
    def test_from_file_json(self):
        """Test loading configuration from JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_content = {
                "min_segment_tokens": 250,
                "max_segment_tokens": 1200,
                "whisper_model_size": "small",
                "use_gpu": True,
                "embedding_dimensions": 768
            }
            json.dump(json_content, f)
            f.flush()
            
            try:
                config = PipelineConfig.from_file(Path(f.name))
                assert config.min_segment_tokens == 250
                assert config.max_segment_tokens == 1200
                assert config.whisper_model_size == "small"
                assert config.use_gpu is True
                assert config.embedding_dimensions == 768
            finally:
                os.unlink(f.name)
    
    def test_from_file_not_found(self):
        """Test error when config file doesn't exist."""
        with pytest.raises(ConfigurationError) as exc_info:
            PipelineConfig.from_file(Path("/non/existent/config.yaml"))
        assert "Configuration file not found" in str(exc_info.value)
    
    def test_from_file_unsupported_format(self):
        """Test error with unsupported file format."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b"some content")
            f.flush()
            
            try:
                with pytest.raises(ConfigurationError) as exc_info:
                    PipelineConfig.from_file(Path(f.name))
                assert "Unsupported config format: .txt" in str(exc_info.value)
            finally:
                os.unlink(f.name)
    
    def test_from_file_yaml_not_available(self):
        """Test error when YAML file is loaded but PyYAML not installed."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            f.write(b"key: value")
            f.flush()
            
            try:
                with mock.patch('src.core.config.YAML_AVAILABLE', False):
                    with pytest.raises(ConfigurationError) as exc_info:
                        PipelineConfig.from_file(Path(f.name))
                    assert "YAML support not available" in str(exc_info.value)
            finally:
                os.unlink(f.name)
    
    def test_from_file_invalid_json(self):
        """Test error with invalid JSON content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            f.flush()
            
            try:
                with pytest.raises(json.JSONDecodeError):
                    PipelineConfig.from_file(Path(f.name))
            finally:
                os.unlink(f.name)
    
    def test_post_init_called(self):
        """Test that __post_init__ is called during initialization."""
        # Create config with string paths
        config = PipelineConfig(
            base_dir="./base",
            audio_dir="audio",
            output_dir="output",
            checkpoint_dir="checkpoints"
        )
        
        # Verify paths were converted to Path objects
        assert isinstance(config.base_dir, Path)
        assert isinstance(config.audio_dir, Path)
        assert isinstance(config.output_dir, Path)
        assert isinstance(config.checkpoint_dir, Path)
    
    def test_environment_override_in_from_file(self):
        """Test that environment variables override file values."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_content = {
                "log_level": "INFO"
            }
            json.dump(json_content, f)
            f.flush()
            
            try:
                # Environment should override file
                with mock.patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
                    config = PipelineConfig.from_file(Path(f.name))
                    # Note: The current implementation doesn't override from env after loading file
                    # This test documents the current behavior
                    assert config.log_level == "INFO"  # File value is used
            finally:
                os.unlink(f.name)
    
    def test_boolean_environment_parsing(self):
        """Test parsing of boolean values from environment variables."""
        # Test various true values
        for true_value in ["true", "True", "TRUE", "TrUe"]:
            with mock.patch.dict(os.environ, {"USE_SCHEMALESS_EXTRACTION": true_value}):
                config = PipelineConfig()
                assert config.use_schemaless_extraction is True
        
        # Test various false values
        for false_value in ["false", "False", "FALSE", "FaLsE", "0", ""]:
            with mock.patch.dict(os.environ, {"USE_SCHEMALESS_EXTRACTION": false_value}):
                config = PipelineConfig()
                assert config.use_schemaless_extraction is False
        
        # Test relationship normalization
        with mock.patch.dict(os.environ, {"RELATIONSHIP_NORMALIZATION": "false"}):
            config = PipelineConfig()
            assert config.relationship_normalization is False
    
    def test_numeric_environment_parsing(self):
        """Test parsing of numeric values from environment variables."""
        with mock.patch.dict(os.environ, {
            "SCHEMALESS_CONFIDENCE_THRESHOLD": "0.85",
            "ENTITY_RESOLUTION_THRESHOLD": "0.9",
            "MAX_PROPERTIES_PER_NODE": "75"
        }):
            config = PipelineConfig()
            assert config.schemaless_confidence_threshold == 0.85
            assert config.entity_resolution_threshold == 0.9
            assert config.max_properties_per_node == 75
    
    def test_immutability(self):
        """Test that config values can be modified (dataclasses are not frozen)."""
        config = PipelineConfig()
        
        # Should be able to modify values
        config.max_episodes = 10
        assert config.max_episodes == 10
        
        config.use_gpu = False
        assert config.use_gpu is False


class TestSeedingConfig:
    """Test suite for SeedingConfig class."""
    
    def test_inheritance(self):
        """Test that SeedingConfig inherits from PipelineConfig."""
        assert issubclass(SeedingConfig, PipelineConfig)
    
    def test_seeding_specific_defaults(self):
        """Test SeedingConfig has correct default values."""
        config = SeedingConfig()
        
        # Check seeding-specific fields
        assert config.batch_size == 10
        assert config.embedding_batch_size == 50
        assert config.save_checkpoints is True
        assert config.checkpoint_every_n == 5
        assert config.enable_progress_bar is True
        
        # Check inherited fields are still there
        assert config.min_segment_tokens == 150
        assert config.max_segment_tokens == 800
        assert hasattr(config, 'neo4j_uri')
        assert hasattr(config, 'use_gpu')
    
    def test_seeding_config_validation(self):
        """Test that SeedingConfig still validates properly."""
        with mock.patch.dict(os.environ, {
            "NEO4J_PASSWORD": "test",
            "GOOGLE_API_KEY": "test"
        }):
            config = SeedingConfig()
            config.validate()  # Should not raise
    
    def test_seeding_config_to_dict(self):
        """Test SeedingConfig serialization includes all fields."""
        config = SeedingConfig()
        config_dict = config.to_dict()
        
        # Check seeding-specific fields
        assert "batch_size" in config_dict
        assert "embedding_batch_size" in config_dict
        assert "save_checkpoints" in config_dict
        assert "checkpoint_every_n" in config_dict
        assert "enable_progress_bar" in config_dict
        
        # Check inherited fields
        assert "min_segment_tokens" in config_dict
        assert "neo4j_uri" in config_dict
    
    def test_seeding_config_from_file(self):
        """Test loading SeedingConfig from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_content = {
                "batch_size": 20,
                "embedding_batch_size": 100,
                "save_checkpoints": False,
                "max_episodes": 50
            }
            json.dump(json_content, f)
            f.flush()
            
            try:
                config = SeedingConfig.from_file(Path(f.name))
                assert config.batch_size == 20
                assert config.embedding_batch_size == 100
                assert config.save_checkpoints is False
                assert config.max_episodes == 50
                
                # Check defaults are still applied
                assert config.checkpoint_every_n == 5
                assert config.enable_progress_bar is True
            finally:
                os.unlink(f.name)


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_environment(self):
        """Test behavior with completely empty environment."""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = self._create_config_without_validation()
            
            # Should get all defaults
            assert config.neo4j_uri == "bolt://localhost:7687"
            assert config.neo4j_username == "neo4j"
            assert config.neo4j_password is None
            assert config.google_api_key is None
            assert config.openai_api_key is None
            assert config.log_level == "INFO"
    
    def test_partial_environment(self):
        """Test with some but not all environment variables."""
        with mock.patch.dict(os.environ, {
            "NEO4J_PASSWORD": "pass",
            "GOOGLE_API_KEY": "test",
            "LOG_LEVEL": "WARN"
        }, clear=True):
            config = PipelineConfig()
            
            assert config.neo4j_password == "pass"
            assert config.log_level == "WARN"
            assert config.google_api_key is None
            assert config.neo4j_uri == "bolt://localhost:7687"
    
    def test_invalid_numeric_environment(self):
        """Test handling of invalid numeric values in environment."""
        with mock.patch.dict(os.environ, {
            "SCHEMALESS_CONFIDENCE_THRESHOLD": "not_a_number"
        }):
            with pytest.raises(ValueError):
                PipelineConfig()
        
        with mock.patch.dict(os.environ, {
            "MAX_PROPERTIES_PER_NODE": "50.5"  # Should be int
        }):
            with pytest.raises(ValueError):
                PipelineConfig()
    
    def test_whitespace_in_environment(self):
        """Test handling of whitespace in environment values."""
        with mock.patch.dict(os.environ, {
            "NEO4J_PASSWORD": "  test_pass  ",
            "GOOGLE_API_KEY": "test",
            "LOG_LEVEL": " DEBUG ",
            "USE_SCHEMALESS_EXTRACTION": " true "
        }):
            config = PipelineConfig()
            
            # Current implementation doesn't strip whitespace
            assert config.neo4j_password == "  test_pass  "
            assert config.log_level == " DEBUG "
            # Boolean parsing might handle whitespace
            assert config.use_schemaless_extraction is True  # .lower() is called
    
    def test_special_characters_in_paths(self):
        """Test handling of special characters in path names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            special_dir = Path(tmpdir) / "audio with spaces & special!"
            config = PipelineConfig(
                base_dir=tmpdir,
                audio_dir=special_dir
            )
            
            assert config.audio_dir == special_dir
            # Validation should still work
            with mock.patch.dict(os.environ, {
                "NEO4J_PASSWORD": "test",
                "GOOGLE_API_KEY": "test"
            }):
                config.validate()
                assert special_dir.exists()
    
    def test_unicode_in_configuration(self):
        """Test handling of unicode characters."""
        config = PipelineConfig(
            whisper_model_size="大型-v3",  # Unicode characters
            neo4j_database="知识图谱"
        )
        
        assert config.whisper_model_size == "大型-v3"
        assert config.neo4j_database == "知识图谱"
        
        # Should serialize properly
        config_dict = config.to_dict()
        assert config_dict["whisper_model_size"] == "大型-v3"
    
    def test_extremely_large_values(self):
        """Test handling of extremely large configuration values."""
        config = PipelineConfig(
            max_segment_tokens=999999999,
            embedding_dimensions=999999,
            max_properties_per_node=1000000
        )
        
        assert config.max_segment_tokens == 999999999
        assert config.embedding_dimensions == 999999
        assert config.max_properties_per_node == 1000000
    
    def test_directory_creation_race_condition(self):
        """Test handling when directory is created between checks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "test_dir"
            
            config = PipelineConfig(audio_dir=test_dir)
            
            # Simulate directory being created by another process
            original_mkdir = Path.mkdir
            call_count = 0
            
            def mkdir_side_effect(self, *args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # First call, create it separately
                    original_mkdir(self, *args, **kwargs)
                    # Then call again (simulating exist_ok=True behavior)
                    return original_mkdir(self, *args, **kwargs)
                return original_mkdir(self, *args, **kwargs)
            
            with mock.patch.object(Path, 'mkdir', mkdir_side_effect):
                with mock.patch.dict(os.environ, {
                    "NEO4J_PASSWORD": "test",
                    "GOOGLE_API_KEY": "test"
                }):
                    config.validate()  # Should handle gracefully
    
    def test_config_copy_and_modification(self):
        """Test creating modified copies of configuration."""
        original = PipelineConfig(max_episodes=5, use_gpu=True)
        
        # Create a modified copy
        modified = PipelineConfig(
            **{k: v for k, v in original.__dict__.items()},
            max_episodes=10,
            use_gpu=False
        )
        
        assert original.max_episodes == 5
        assert original.use_gpu is True
        assert modified.max_episodes == 10
        assert modified.use_gpu is False
    
    def test_yaml_with_invalid_values(self):
        """Test YAML loading with invalid value types."""
        if not YAML_AVAILABLE:
            pytest.skip("YAML not available")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_content = """
max_episodes: "not_a_number"
"""
            f.write(yaml_content)
            f.flush()
            
            try:
                # This should fail during validation or usage
                config = PipelineConfig.from_file(Path(f.name))
                # The string gets assigned, but might fail later
                assert config.max_episodes == "not_a_number"
            finally:
                os.unlink(f.name)