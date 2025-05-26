"""Podcast Knowledge Graph Pipeline - Modular Implementation.

Main API:
    - PodcastKnowledgePipeline: Main pipeline orchestrator
    - seed_podcast: Seed knowledge graph with a single podcast
    - seed_podcasts: Seed knowledge graph with multiple podcasts
"""

from .__version__ import __version__, __version_info__, __api_version__
from .seeding import PodcastKnowledgePipeline

# Convenience functions
def seed_podcast(podcast_config, max_episodes=1, use_large_context=True, config=None):
    """Seed knowledge graph with a single podcast.
    
    Args:
        podcast_config: Podcast configuration with RSS URL
        max_episodes: Maximum episodes to process
        use_large_context: Whether to use large context models
        config: Optional configuration object
    
    Returns:
        Processing summary dict
    """
    from .core.config import Config
    
    if config is None:
        config = Config()
    
    pipeline = PodcastKnowledgePipeline(config)
    try:
        return pipeline.seed_podcast(podcast_config, max_episodes, use_large_context)
    finally:
        pipeline.cleanup()


def seed_podcasts(podcast_configs, max_episodes_each=10, use_large_context=True, config=None):
    """Seed knowledge graph with multiple podcasts.
    
    Args:
        podcast_configs: List of podcast configurations
        max_episodes_each: Episodes to process per podcast
        use_large_context: Whether to use large context models
        config: Optional configuration object
    
    Returns:
        Summary dict with processing statistics
    """
    from .core.config import Config
    
    if config is None:
        config = Config()
    
    pipeline = PodcastKnowledgePipeline(config)
    try:
        return pipeline.seed_podcasts(podcast_configs, max_episodes_each, use_large_context)
    finally:
        pipeline.cleanup()


__all__ = [
    '__version__',
    '__version_info__',
    '__api_version__',
    'PodcastKnowledgePipeline',
    'seed_podcast',
    'seed_podcasts',
]