"""Basic usage examples for Podcast Knowledge Graph Pipeline.

This file contains runnable examples demonstrating basic functionality.
"""

from src.api.v1 import seed_podcast, seed_podcasts
from src.core.config import Config


def example_single_podcast():
    """Example: Process a single podcast."""
    print("=== Processing Single Podcast ===")
    
    # Define podcast configuration
    podcast_config = {
        'name': 'The Daily Tech News',
        'rss_url': 'https://feeds.simplecast.com/54nAGcIl',
        'category': 'Technology'
    }
    
    # Process 5 episodes
    result = seed_podcast(podcast_config, max_episodes=5)
    
    # Display results
    print(f"Processed {result['episodes_processed']} episodes")
    print(f"Failed episodes: {result['episodes_failed']}")
    print(f"Total time: {result['processing_time_seconds']:.2f} seconds")
    
    return result


def example_multiple_podcasts():
    """Example: Process multiple podcasts in batch."""
    print("\n=== Processing Multiple Podcasts ===")
    
    # Define multiple podcasts
    podcast_list = [
        {
            'name': 'Tech Explained',
            'rss_url': 'https://example.com/tech/feed.xml',
            'category': 'Technology'
        },
        {
            'name': 'Science Weekly',
            'rss_url': 'https://example.com/science/feed.xml',
            'category': 'Science'
        },
        {
            'name': 'History Podcast',
            'rss_url': 'https://example.com/history/feed.xml',
            'category': 'Education'
        }
    ]
    
    # Process 3 episodes from each
    result = seed_podcasts(podcast_list, max_episodes_each=3)
    
    # Display aggregate results
    print(f"Processed {result['podcasts_processed']} podcasts")
    print(f"Total episodes: {result['episodes_processed']}")
    print(f"Success rate: {(result['episodes_processed'] / (result['episodes_processed'] + result['episodes_failed']) * 100):.1f}%")
    
    return result


def example_custom_configuration():
    """Example: Use custom configuration."""
    print("\n=== Custom Configuration ===")
    
    # Create custom configuration
    config = Config()
    
    # Adjust processing settings
    config.batch_size = 10  # Process 10 segments at a time
    config.max_workers = 4  # Use 4 parallel workers
    config.checkpoint_enabled = True  # Enable checkpointing
    config.checkpoint_dir = './my_checkpoints'
    
    # Adjust model settings
    config.model_name = 'gemini-1.5-flash'  # Use faster model
    config.temperature = 0.5  # More focused responses
    
    # Process with custom config
    podcast_config = {
        'name': 'Custom Config Test',
        'rss_url': 'https://example.com/podcast/feed.xml'
    }
    
    result = seed_podcast(podcast_config, max_episodes=2, config=config)
    
    print(f"Processed with batch size {config.batch_size}")
    print(f"Used {config.max_workers} workers")
    
    return result


def example_error_handling():
    """Example: Handle processing errors gracefully."""
    print("\n=== Error Handling ===")
    
    # Try to process an invalid podcast
    invalid_podcast = {
        'name': 'Invalid Podcast',
        'rss_url': 'https://this-url-does-not-exist.com/feed.xml',
        'category': 'Test'
    }
    
    try:
        result = seed_podcast(invalid_podcast, max_episodes=1)
        
        # Check for failures
        if result['episodes_failed'] > 0:
            print(f"Warning: Failed to process {result['episodes_failed']} episodes")
        
        if result['episodes_processed'] == 0:
            print("Error: No episodes were processed successfully")
        
    except Exception as e:
        print(f"Critical error: {e}")
    
    # Process continues even with some failures
    print("Processing completed with error handling")


def example_checkpoint_recovery():
    """Example: Resume from checkpoint after interruption."""
    print("\n=== Checkpoint Recovery ===")
    
    # Enable checkpointing
    config = Config()
    config.checkpoint_enabled = True
    config.checkpoint_dir = './checkpoints'
    
    podcast_config = {
        'name': 'Long Podcast',
        'rss_url': 'https://example.com/long/feed.xml'
    }
    
    # Simulate interrupted processing
    print("First run - processing 5 episodes...")
    result1 = seed_podcast(podcast_config, max_episodes=5, config=config)
    print(f"Processed {result1['episodes_processed']} episodes")
    
    # Simulate resuming later
    print("\nSecond run - resuming from checkpoint...")
    result2 = seed_podcast(podcast_config, max_episodes=10, config=config)
    print(f"Processed additional {result2['episodes_processed']} episodes")
    
    return result2


def example_filtering_episodes():
    """Example: Process only specific episodes."""
    print("\n=== Episode Filtering ===")
    
    from datetime import datetime, timedelta
    
    # Process only recent episodes
    podcast_config = {
        'name': 'News Podcast',
        'rss_url': 'https://example.com/news/feed.xml',
        'category': 'News',
        # Only episodes from last 30 days
        'start_date': (datetime.now() - timedelta(days=30)).isoformat()
    }
    
    result = seed_podcast(podcast_config, max_episodes=50)
    
    print(f"Processed {result['episodes_processed']} recent episodes")
    
    return result


def example_performance_optimization():
    """Example: Optimize for performance."""
    print("\n=== Performance Optimization ===")
    
    # Create performance-optimized config
    config = Config()
    
    # Larger batches for efficiency
    config.batch_size = 50
    
    # More parallel workers
    config.max_workers = 8
    
    # Use smaller, faster model
    config.model_name = 'gemini-1.5-flash'
    config.use_large_context = False
    
    # Disable some features for speed
    config.enable_diarization = False
    config.extract_quotes = False
    
    podcast_config = {
        'name': 'Speed Test',
        'rss_url': 'https://example.com/feed.xml'
    }
    
    import time
    start_time = time.time()
    
    result = seed_podcast(
        podcast_config, 
        max_episodes=10,
        use_large_context=False,  # Faster processing
        config=config
    )
    
    processing_time = time.time() - start_time
    episodes_per_minute = result['episodes_processed'] / (processing_time / 60)
    
    print(f"Processed {result['episodes_processed']} episodes in {processing_time:.1f} seconds")
    print(f"Rate: {episodes_per_minute:.1f} episodes/minute")
    
    return result


if __name__ == "__main__":
    """Run all examples."""
    
    # Run basic examples
    example_single_podcast()
    example_multiple_podcasts()
    example_custom_configuration()
    
    # Run advanced examples
    example_error_handling()
    example_checkpoint_recovery()
    example_filtering_episodes()
    example_performance_optimization()
    
    print("\n=== All examples completed! ===")