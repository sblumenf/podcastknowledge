"""Unit tests for configuration management."""

import pytest
import os
from pathlib import Path
import tempfile
import yaml

from src.core import (
    PipelineConfig,
    SeedingConfig,
    load_config,
    get_neo4j_config,
    get_llm_config,
    ConfigurationError,
)


class TestPipelineConfig:
    """Test PipelineConfig class."""
    
    def test_default_config(self, monkeypatch):
        """Test default configuration values."""
        # Set required environment variables
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "test")
        monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
        
        config = PipelineConfig()
        
        # Check defaults
        assert config.min_segment_tokens == 150
        assert config.max_segment_tokens == 800
        assert config.whisper_model_size == "large-v3"
        assert config.use_faster_whisper is True
        assert config.embedding_dimensions == 1536
        assert config.use_gpu is True
        
    def test_environment_override(self, monkeypatch):
        """Test that environment variables override defaults."""
        monkeypatch.setenv("NEO4J_URI", "bolt://test:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "testuser")
        monkeypatch.setenv("NEO4J_PASSWORD", "testpass")
        monkeypatch.setenv("GOOGLE_API_KEY", "test_google_key")
        
        config = PipelineConfig()
        
        assert config.neo4j_uri == "bolt://test:7687"
        assert config.neo4j_username == "testuser"
        assert config.neo4j_password == "testpass"
        assert config.google_api_key == "test_google_key"
        
    def test_path_resolution(self, monkeypatch):
        """Test that paths are resolved correctly."""
        # Set required environment variables
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "test")
        monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
        
        config = PipelineConfig(
            base_dir="/tmp/test",
            audio_dir="audio",
            output_dir="output"
        )
        
        assert config.base_dir == Path("/tmp/test")
        assert config.audio_dir == Path("/tmp/test/audio")
        assert config.output_dir == Path("/tmp/test/output")
        
    def test_absolute_paths(self, monkeypatch, tmp_path):
        """Test that absolute paths are preserved."""
        # Set required environment variables
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "test")
        monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
        
        # Create temporary absolute paths
        audio_dir = tmp_path / "absolute_audio"
        output_dir = tmp_path / "absolute_output"
        
        config = PipelineConfig(
            base_dir="/tmp/test",
            audio_dir=str(audio_dir),
            output_dir=str(output_dir)
        )
        
        assert config.audio_dir == audio_dir
        assert config.output_dir == output_dir
        
    def test_config_validation_errors(self):
        """Test configuration validation errors."""
        # Test invalid segment tokens
        with pytest.raises(ConfigurationError) as exc_info:
            PipelineConfig(
                min_segment_tokens=800,
                max_segment_tokens=150  # Invalid: min > max
            )
        assert "min_segment_tokens must be less than max_segment_tokens" in str(exc_info.value)
        
        # Test invalid GPU memory fraction
        with pytest.raises(ConfigurationError) as exc_info:
            PipelineConfig(gpu_memory_fraction=1.5)  # Invalid: > 1
        assert "gpu_memory_fraction must be between 0 and 1" in str(exc_info.value)
        
    def test_to_dict_hides_secrets(self):
        """Test that to_dict hides sensitive information."""
        config = PipelineConfig(
            neo4j_password="secret123",
            google_api_key="google_secret",
            openai_api_key="openai_secret"
        )
        
        data = config.to_dict()
        
        assert data["neo4j_password"] == "***"
        assert data["google_api_key"] == "***"
        assert data["openai_api_key"] == "***"
        
    def test_missing_required_env_vars(self, monkeypatch):
        """Test validation when required environment variables are missing."""
        # Clear environment variables
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        
        with pytest.raises(ConfigurationError) as exc_info:
            PipelineConfig()
        
        errors = exc_info.value.details["errors"]
        assert any("NEO4J_PASSWORD" in e for e in errors)
        assert any("GOOGLE_API_KEY or OPENAI_API_KEY" in e for e in errors)


class TestSeedingConfig:
    """Test SeedingConfig class."""
    
    def test_seeding_defaults(self, monkeypatch):
        """Test seeding configuration defaults."""
        # Set required environment variables
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "test")
        monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
        
        config = SeedingConfig()
        
        # Check seeding-specific defaults
        assert config.batch_size == 10
        assert config.embedding_batch_size == 50
        assert config.save_checkpoints is True
        assert config.checkpoint_every_n == 5
        assert config.interactive_mode is False
        assert config.save_visualizations is False
        
    def test_batch_mode_logging(self, monkeypatch):
        """Test that batch mode sets appropriate logging."""
        # Set required environment variables
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "test")
        monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
        
        config = SeedingConfig(verbose_logging=False)
        assert config.log_level == "ERROR"
        
        config = SeedingConfig(verbose_logging=True)
        assert config.log_level != "ERROR"
        
    def test_get_segmenter_config(self, monkeypatch):
        """Test segmenter configuration generation."""
        # Set required environment variables
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "test")
        monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
        
        config = SeedingConfig(
            min_segment_tokens=100,
            max_segment_tokens=500,
            batch_size=20
        )
        
        segmenter_config = config.get_segmenter_config()
        
        assert segmenter_config["min_segment_tokens"] == 100
        assert segmenter_config["max_segment_tokens"] == 500
        assert segmenter_config["batch_size"] == 20
        assert segmenter_config["use_gpu"] is True
        
    def test_get_rate_limits(self, monkeypatch):
        """Test rate limit configuration."""
        # Set required environment variables
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "test")
        monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
        
        config = SeedingConfig(
            llm_requests_per_minute=30,
            llm_tokens_per_minute=100000
        )
        
        rate_limits = config.get_rate_limits()
        
        assert rate_limits["llm_rpm"] == 30
        assert rate_limits["llm_tpm"] == 100000
        
    def test_validate_dependencies(self, monkeypatch):
        """Test dependency validation."""
        # Set required environment variables
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "test")
        monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
        
        config = SeedingConfig()
        
        # This will check which dependencies are actually installed
        missing = config.validate_dependencies()
        
        # The test should pass regardless of what's installed
        assert isinstance(missing, list)


class TestConfigLoading:
    """Test configuration loading functions."""
    
    def test_load_config_defaults(self, monkeypatch):
        """Test loading configuration with defaults."""
        # Set required environment variables
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "test")
        monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
        
        config = load_config(config_type="pipeline")
        assert isinstance(config, PipelineConfig)
        
        config = load_config(config_type="seeding")
        assert isinstance(config, SeedingConfig)
        
    def test_load_config_from_yaml(self, monkeypatch):
        """Test loading configuration from YAML file."""
        # Set required environment variables
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "test")
        monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                'min_segment_tokens': 200,
                'max_segment_tokens': 1000,
                'batch_size': 25,
                'use_gpu': False
            }, f)
            temp_path = f.name
            
        try:
            config = load_config(Path(temp_path), config_type="seeding")
            
            assert config.min_segment_tokens == 200
            assert config.max_segment_tokens == 1000
            assert config.batch_size == 25
            assert config.use_gpu is False
        finally:
            os.unlink(temp_path)
            
    def test_get_neo4j_config(self, monkeypatch):
        """Test Neo4j configuration extraction."""
        # Set required environment variables
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "test")
        monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
        
        config = PipelineConfig(
            neo4j_uri="bolt://localhost:7687",
            neo4j_username="neo4j",
            neo4j_password="password",
            neo4j_database="test"
        )
        
        neo4j_config = get_neo4j_config(config)
        
        assert neo4j_config["uri"] == "bolt://localhost:7687"
        assert neo4j_config["auth"] == ("neo4j", "password")
        assert neo4j_config["database"] == "test"
        
    def test_get_llm_config(self, monkeypatch):
        """Test LLM configuration extraction."""
        # Set required environment variables
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "test")
        monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
        
        config = PipelineConfig(
            google_api_key="google_key",
            openai_api_key="openai_key",
            whisper_model_size="large-v3",
            use_faster_whisper=True
        )
        
        llm_config = get_llm_config(config)
        
        assert llm_config["google_api_key"] == "google_key"
        assert llm_config["openai_api_key"] == "openai_key"
        assert llm_config["whisper_model"] == "large-v3"
        assert llm_config["use_faster_whisper"] is True


class TestConfigFromFile:
    """Test loading configuration from files."""
    
    def test_from_yaml_file(self, monkeypatch):
        """Test loading from YAML file."""
        # Set required environment variables
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "test")
        monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                'min_segment_tokens': 250,
                'use_gpu': False,
                'batch_size': 15
            }, f)
            temp_path = Path(f.name)
            
        try:
            config = SeedingConfig.from_file(temp_path)
            
            assert config.min_segment_tokens == 250
            assert config.use_gpu is False
            assert config.batch_size == 15
        finally:
            temp_path.unlink()
            
    def test_from_nonexistent_file(self):
        """Test loading from nonexistent file."""
        with pytest.raises(ConfigurationError) as exc_info:
            PipelineConfig.from_file(Path("/nonexistent/config.yaml"))
        assert "not found" in str(exc_info.value)
        
    def test_from_unsupported_format(self):
        """Test loading from unsupported file format."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            temp_path = Path(f.name)
            
        try:
            with pytest.raises(ConfigurationError) as exc_info:
                PipelineConfig.from_file(temp_path)
            assert "Unsupported config format" in str(exc_info.value)
        finally:
            temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])