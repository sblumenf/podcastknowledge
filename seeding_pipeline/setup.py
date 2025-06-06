#!/usr/bin/env python3
"""Setup script for Podcast Knowledge Graph Pipeline.

This setup.py exists for backward compatibility.
The project is primarily configured through pyproject.toml.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

# Read version from src/__version__.py
version = {}
with open(this_directory / "src" / "__version__.py") as f:
    exec(f.read(), version)

setup(
    name="podcast-kg-pipeline",
    version=version['__version__'],
    author="Podcast KG Team",
    author_email="team@example.com",
    description="Modular podcast knowledge graph seeding pipeline",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/podcast-kg-pipeline",
    packages=find_packages(exclude=["tests", "tests.*", "scripts", "scripts.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.9",
    install_requires=[
        "neo4j>=5.14.0",
        "python-dotenv>=1.0.0",
        "numpy>=1.24.3",
        "scipy>=1.11.4",
        "networkx>=3.1",
        "torch>=2.1.0",
        "openai-whisper>=20231117",
        "pyannote.audio>=3.1.1",
        "langchain>=0.1.0",
        "langchain-google-genai>=0.0.5",
        "sentence-transformers>=2.2.2",
        "feedparser>=6.0.10",
        "tqdm>=4.66.1",
        "pyyaml>=6.0.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.1",
            "pytest-mock>=3.12.0",
            "mypy>=1.7.1",
            "black>=23.11.0",
            "isort>=5.12.0",
            "flake8>=6.1.0",
            "pre-commit>=3.5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "podcast-kg=cli:main",
            "podcast-kg-seed=cli:main",  # Alias for compatibility
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yml", "*.yaml", "*.json"],
    },
)