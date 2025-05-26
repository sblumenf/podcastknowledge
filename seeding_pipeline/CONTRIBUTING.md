# Contributing to Podcast Knowledge Graph Pipeline

Thank you for your interest in contributing to the Podcast Knowledge Graph Pipeline! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Process](#development-process)
4. [Code Style Guidelines](#code-style-guidelines)
5. [Testing Guidelines](#testing-guidelines)
6. [Documentation Guidelines](#documentation-guidelines)
7. [Submitting Changes](#submitting-changes)
8. [Provider Development](#provider-development)
9. [Reporting Issues](#reporting-issues)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please:

- Be respectful and considerate
- Welcome newcomers and help them get started
- Focus on constructive criticism
- Respect differing viewpoints and experiences

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- Neo4j 4.4+ (for integration testing)
- CUDA-capable GPU (optional, for Whisper acceleration)

### Setting Up Your Development Environment

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/podcast_kg_pipeline.git
   cd podcast_kg_pipeline
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   pip install -e .  # Install package in development mode
   ```

4. **Set up pre-commit hooks**:
   ```bash
   pre-commit install
   ```

5. **Configure your environment**:
   ```bash
   cp .env.example .env
   cp config/config.example.yml config/config.dev.yml
   # Edit .env and config.dev.yml with your settings
   ```

6. **Run tests to verify setup**:
   ```bash
   pytest tests/unit/
   ```

## Development Process

### Branch Naming Convention

- `feature/` - New features (e.g., `feature/add-openai-provider`)
- `fix/` - Bug fixes (e.g., `fix/memory-leak-audio-processing`)
- `docs/` - Documentation updates (e.g., `docs/improve-api-examples`)
- `refactor/` - Code refactoring (e.g., `refactor/simplify-extraction-logic`)
- `test/` - Test additions/improvements (e.g., `test/add-integration-tests`)

### Workflow

1. **Create an issue** for significant changes
2. **Create a feature branch** from `main`
3. **Make your changes** following our guidelines
4. **Write/update tests** for your changes
5. **Run the test suite** to ensure nothing is broken
6. **Update documentation** if needed
7. **Submit a pull request**

### Commit Message Format

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Test additions or modifications
- `chore`: Maintenance tasks

Examples:
```
feat(providers): Add OpenAI LLM provider support

Implements OpenAIProvider class with GPT-4 support for knowledge extraction.
Includes rate limiting and retry logic.

Closes #123
```

## Code Style Guidelines

### Python Style

We follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) with some modifications:

1. **Line length**: Maximum 100 characters (instead of 79)
2. **Imports**: Grouped and sorted using `isort`
3. **Type hints**: Required for all public functions
4. **Docstrings**: Google style for all public modules, classes, and functions

### Code Quality Tools

Before submitting, ensure your code passes:

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Check style
flake8 src/ tests/

# Type checking
mypy src/

# Security audit
bandit -r src/
```

### Example Code Style

```python
"""Module for handling audio transcription with various providers."""

from typing import Dict, List, Optional, Protocol
from pathlib import Path

from podcast_kg_pipeline.core.exceptions import AudioProcessingError
from podcast_kg_pipeline.providers.base import BaseProvider


class AudioTranscriber(BaseProvider):
    """Handles audio transcription using configured provider.
    
    This class provides a unified interface for audio transcription,
    supporting multiple backend providers like Whisper, Google Speech, etc.
    
    Attributes:
        provider_name: Name of the audio provider being used
        config: Provider-specific configuration
    """
    
    def __init__(self, provider_name: str, config: Dict[str, Any]) -> None:
        """Initialize the audio transcriber.
        
        Args:
            provider_name: Name of the provider to use
            config: Provider configuration dictionary
            
        Raises:
            ConfigurationError: If provider configuration is invalid
        """
        super().__init__(provider_name, config)
        self._validate_config()
    
    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Transcribe audio file to text.
        
        Args:
            audio_path: Path to the audio file
            language: Optional language code (e.g., 'en', 'es')
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Dictionary containing:
                - text: Transcribed text
                - segments: Time-aligned segments
                - confidence: Overall confidence score
                
        Raises:
            AudioProcessingError: If transcription fails
            FileNotFoundError: If audio file doesn't exist
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
        try:
            return self._provider.transcribe(
                str(audio_path),
                language=language,
                **kwargs
            )
        except Exception as e:
            raise AudioProcessingError(
                f"Transcription failed: {str(e)}"
            ) from e
```

## Testing Guidelines

### Test Structure

```
tests/
├── unit/           # Fast, isolated unit tests
├── integration/    # Tests with real dependencies
├── e2e/           # End-to-end workflow tests
├── performance/   # Performance benchmarks
└── fixtures/      # Test data and mocks
```

### Writing Tests

1. **Test naming**: Use descriptive names that explain what is being tested
   ```python
   def test_audio_transcriber_handles_missing_file():
   def test_llm_provider_retries_on_rate_limit():
   ```

2. **Test structure**: Follow the Arrange-Act-Assert pattern
   ```python
   def test_entity_resolution_merges_similar_names():
       # Arrange
       matcher = EntityMatcher(threshold=0.85)
       entities = ["John Smith", "J. Smith", "John S."]
       
       # Act
       merged = matcher.resolve_entities(entities)
       
       # Assert
       assert len(merged) == 1
       assert merged[0].canonical_name == "John Smith"
   ```

3. **Fixtures**: Use pytest fixtures for common test data
   ```python
   @pytest.fixture
   def sample_transcript():
       return {
           "text": "This is a test transcript.",
           "segments": [{"start": 0.0, "end": 2.5, "text": "This is a test transcript."}]
       }
   ```

4. **Mocking**: Mock external dependencies
   ```python
   @patch('podcast_kg_pipeline.providers.llm.gemini.genai')
   def test_gemini_provider_handles_api_error(mock_genai):
       mock_genai.generate_content.side_effect = Exception("API Error")
       # Test error handling
   ```

### Test Coverage

- Aim for >80% code coverage for new code
- Focus on testing business logic and error cases
- Don't test obvious getters/setters

Run coverage report:
```bash
pytest --cov=src --cov-report=html
# Open htmlcov/index.html to view report
```

## Documentation Guidelines

### Docstring Format

Use Google style docstrings:

```python
def process_segment(
    segment_text: str,
    context: Optional[Dict[str, Any]] = None
) -> ProcessingResult:
    """Process a single transcript segment for knowledge extraction.
    
    This function takes a segment of transcript text and extracts
    structured knowledge including entities, insights, and relationships.
    
    Args:
        segment_text: The transcript segment to process
        context: Optional context from previous segments
        
    Returns:
        ProcessingResult containing extracted knowledge
        
    Raises:
        ProcessingError: If extraction fails
        ValidationError: If segment text is invalid
        
    Example:
        >>> result = process_segment("AI will transform society")
        >>> print(result.entities)
        ['AI', 'society']
    """
```

### API Documentation

- Update `docs/api/` when adding new public APIs
- Include usage examples for all public functions
- Document breaking changes in `CHANGELOG.md`

### README Updates

Update relevant sections when:
- Adding new features
- Changing installation requirements
- Modifying configuration options
- Adding new providers

## Submitting Changes

### Pull Request Process

1. **Ensure all tests pass**:
   ```bash
   pytest
   mypy src/
   ```

2. **Update documentation** if needed

3. **Create a pull request** with:
   - Clear title describing the change
   - Description of what and why
   - Link to related issue(s)
   - Screenshots for UI changes (if any)

4. **PR Template**:
   ```markdown
   ## Description
   Brief description of changes
   
   ## Related Issue
   Fixes #(issue number)
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update
   
   ## Testing
   - [ ] Unit tests pass
   - [ ] Integration tests pass
   - [ ] Manual testing completed
   
   ## Checklist
   - [ ] Code follows style guidelines
   - [ ] Self-review completed
   - [ ] Documentation updated
   - [ ] Tests added/updated
   ```

### Code Review Process

1. All PRs require at least one review
2. Address review feedback promptly
3. Keep PRs focused and reasonably sized
4. Be open to suggestions and feedback

## Provider Development

### Creating a New Provider

1. **Implement the provider interface**:
   ```python
   from podcast_kg_pipeline.providers.llm.base import LLMProvider
   
   class MyLLMProvider(LLMProvider):
       """Custom LLM provider implementation."""
       
       def __init__(self, config: Dict[str, Any]):
           super().__init__(config)
           # Initialize your provider
       
       def generate(self, prompt: str, **kwargs) -> str:
           # Implement generation logic
           pass
       
       def health_check(self) -> Dict[str, Any]:
           # Implement health check
           return {"status": "healthy", "model": self.model_name}
   ```

2. **Register the provider**:
   ```python
   # In src/providers/llm/__init__.py
   from .my_provider import MyLLMProvider
   
   PROVIDERS = {
       "my_llm": MyLLMProvider,
       # ... other providers
   }
   ```

3. **Add tests**:
   ```python
   # tests/unit/providers/test_my_provider.py
   def test_my_provider_initialization():
       provider = MyLLMProvider({"api_key": "test"})
       assert provider.health_check()["status"] == "healthy"
   ```

4. **Document the provider**:
   - Add to `docs/providers/` 
   - Include configuration example
   - List supported features

### Provider Guidelines

- Implement all required interface methods
- Include proper error handling
- Add retry logic for network calls
- Implement health checks
- Support configuration validation
- Add comprehensive logging
- Write unit and integration tests

## Reporting Issues

### Bug Reports

Include:
1. **Environment details**:
   - Python version
   - OS and version
   - Package versions (`pip freeze`)

2. **Steps to reproduce**:
   - Minimal code example
   - Configuration used
   - Input data (if applicable)

3. **Expected vs actual behavior**

4. **Error messages and logs**

### Feature Requests

Include:
1. **Use case description**
2. **Proposed solution**
3. **Alternative solutions considered**
4. **Additional context**

### Security Issues

For security vulnerabilities:
- **DO NOT** create a public issue
- Email security concerns to: security@example.com
- Include steps to reproduce
- We'll respond within 48 hours

## Questions?

- Check existing [documentation](./docs/)
- Search [closed issues](https://github.com/YOUR_ORG/podcast_kg_pipeline/issues?q=is%3Aissue+is%3Aclosed)
- Ask in [discussions](https://github.com/YOUR_ORG/podcast_kg_pipeline/discussions)
- Join our community chat

Thank you for contributing to the Podcast Knowledge Graph Pipeline!