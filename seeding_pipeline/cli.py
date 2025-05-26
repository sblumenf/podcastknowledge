#!/usr/bin/env python3
"""Command Line Interface for Podcast Knowledge Graph Pipeline.

This CLI provides batch processing commands for seeding podcast knowledge graphs.
No interactive prompts - all parameters must be provided via command line.
"""

import argparse
import json
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.seeding import PodcastKnowledgePipeline
from src.core.config import Config
from src.core.exceptions import PodcastKGError
from src.utils.logging import setup_logging as setup_structured_logging, get_logger


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """Set up structured logging configuration."""
    level = "DEBUG" if verbose else os.environ.get("PODCAST_KG_LOG_LEVEL", "INFO")
    
    # Create logs directory if needed
    if log_file:
        log_dir = Path(log_file).parent
        log_dir.mkdir(exist_ok=True, parents=True)
    
    setup_structured_logging(
        level=level,
        log_file=log_file,
        json_format=os.environ.get("PODCAST_KG_LOG_FORMAT", "json").lower() == "json",
        add_context=True,
        add_performance=verbose
    )


def load_podcast_configs(config_path: Path) -> List[Dict[str, Any]]:
    """Load podcast configurations from JSON file.
    
    Expected format:
    [
        {
            "name": "Podcast Name",
            "rss_url": "https://example.com/feed.xml",
            "category": "Technology"
        },
        ...
    ]
    """
    try:
        with open(config_path, 'r') as f:
            configs = json.load(f)
        
        if not isinstance(configs, list):
            configs = [configs]
        
        # Validate each config has required fields
        for config in configs:
            if 'rss_url' not in config:
                raise ValueError(f"Missing 'rss_url' in config: {config}")
        
        return configs
    except Exception as e:
        raise ValueError(f"Failed to load podcast configs: {e}")


def seed_podcasts(args: argparse.Namespace) -> int:
    """Seed knowledge graph with podcasts.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Load configuration
        config = None
        if args.config:
            config = Config.from_file(args.config)
        else:
            config = Config()
        
        # Apply extraction mode from CLI
        if args.extraction_mode == 'schemaless':
            config.use_schemaless_extraction = True
        else:
            config.use_schemaless_extraction = False
            
        # Apply migration mode
        if args.migration_mode:
            config.migration_mode = True
            print("Migration mode enabled: will process with both fixed and schemaless extraction")
        
        # Initialize pipeline
        pipeline = PodcastKnowledgePipeline(config)
        
        # Load podcast configurations
        if args.podcast_config:
            podcast_configs = load_podcast_configs(Path(args.podcast_config))
        elif args.rss_url:
            # Single podcast from command line
            podcast_configs = [{
                'name': args.name or 'Unnamed Podcast',
                'rss_url': args.rss_url,
                'category': args.category or 'General'
            }]
        else:
            raise ValueError("Either --podcast-config or --rss-url must be provided")
        
        # Process podcasts
        print(f"Starting knowledge graph seeding for {len(podcast_configs)} podcast(s)...")
        
        result = pipeline.seed_podcasts(
            podcast_configs=podcast_configs,
            max_episodes_each=args.max_episodes,
            use_large_context=args.large_context
        )
        
        # Print summary
        print("\nSeeding Summary:")
        print(f"  Start time: {result['start_time']}")
        print(f"  End time: {result['end_time']}")
        print(f"  Extraction mode: {result.get('extraction_mode', 'fixed')}")
        print(f"  Podcasts processed: {result['podcasts_processed']}")
        print(f"  Episodes processed: {result['episodes_processed']}")
        print(f"  Episodes failed: {result['episodes_failed']}")
        
        # Add schemaless-specific metrics if available
        if result.get('extraction_mode') == 'schemaless':
            print(f"  Total entities: {result.get('total_entities', 0)}")
            print(f"  Total relationships: {result.get('total_relationships', 0)}")
            if result.get('discovered_types'):
                print(f"  Discovered entity types: {len(result['discovered_types'])}")
        
        # Calculate processing time
        from datetime import datetime
        start = datetime.fromisoformat(result['start_time'])
        end = datetime.fromisoformat(result['end_time'])
        processing_time = (end - start).total_seconds()
        print(f"  Processing time: {processing_time:.2f} seconds")
        
        # Show discovered schema if requested
        if args.schema_discovery and result.get('discovered_types'):
            print("\nDiscovered Entity Types:")
            for entity_type in sorted(result['discovered_types']):
                print(f"  - {entity_type}")
        
        # Check for failures
        if result['episodes_failed'] > 0:
            print("\nWarning: Some episodes failed to process. Check logs for details.")
            return 1 if result['episodes_processed'] == 0 else 0
        
        print("\nKnowledge graph seeding completed successfully!")
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    finally:
        # Cleanup
        if 'pipeline' in locals():
            pipeline.cleanup()


def health_check(args: argparse.Namespace) -> int:
    """Check health of all pipeline components.
    
    Returns:
        Exit code (0 for healthy, 1 for unhealthy)
    """
    try:
        # Load configuration
        config = None
        if args.config:
            config = Config.from_file(args.config)
        else:
            config = Config()
        
        # Initialize pipeline
        pipeline = PodcastKnowledgePipeline(config)
        
        print("Checking pipeline component health...")
        
        # Initialize components
        if not pipeline.initialize_components(use_large_context=args.large_context):
            print("Failed to initialize components", file=sys.stderr)
            return 1
        
        print("\nAll components are healthy!")
        return 0
        
    except Exception as e:
        print(f"Health check failed: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    finally:
        # Cleanup
        if 'pipeline' in locals():
            pipeline.cleanup()


def validate_config(args: argparse.Namespace) -> int:
    """Validate configuration file.
    
    Returns:
        Exit code (0 for valid, 1 for invalid)
    """
    try:
        config = Config.from_file(args.config)
        
        print(f"Configuration loaded from: {args.config}")
        print("\nConfiguration summary:")
        print(f"  Neo4j URI: {config.neo4j_uri}")
        print(f"  Model name: {config.model_name}")
        print(f"  Batch size: {config.batch_size}")
        print(f"  Max workers: {config.max_workers}")
        print(f"  Checkpoint enabled: {config.checkpoint_enabled}")
        
        print("\nConfiguration is valid!")
        return 0
        
    except Exception as e:
        print(f"Configuration validation failed: {e}", file=sys.stderr)
        return 1


def schema_stats(args: argparse.Namespace) -> int:
    """Show schema statistics from schemaless extraction.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from src.seeding.checkpoint import ProgressCheckpoint
        
        # Initialize checkpoint reader
        checkpoint = ProgressCheckpoint(
            checkpoint_dir=args.checkpoint_dir,
            extraction_mode='schemaless'
        )
        
        # Get schema statistics
        stats = checkpoint.get_schema_statistics()
        
        if stats.get('message'):
            print(stats['message'])
            return 1
        
        print("Schema Discovery Statistics:")
        print(f"  Total entity types discovered: {stats['total_types_discovered']}")
        print(f"  Evolution entries: {stats['evolution_entries']}")
        
        if stats['first_discovery']:
            print(f"  First discovery: {stats['first_discovery']}")
        if stats['latest_discovery']:
            print(f"  Latest discovery: {stats['latest_discovery']}")
        
        if stats['entity_types']:
            print("\nEntity Types:")
            for entity_type in stats['entity_types']:
                print(f"  - {entity_type}")
        
        if stats['discovery_timeline']:
            print("\nRecent Discoveries:")
            for entry in stats['discovery_timeline']:
                print(f"  {entry['date']} - Episode {entry['episode']} - {entry['count']} new types")
                for new_type in entry['new_types']:
                    print(f"    - {new_type}")
        
        return 0
        
    except Exception as e:
        print(f"Failed to get schema statistics: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Podcast Knowledge Graph Pipeline - Batch Processing CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Seed a single podcast with fixed schema
  %(prog)s seed --rss-url https://example.com/feed.xml --max-episodes 5
  
  # Seed with schemaless extraction
  %(prog)s seed --rss-url https://example.com/feed.xml --extraction-mode schemaless --schema-discovery
  
  # Seed multiple podcasts from config file
  %(prog)s seed --podcast-config podcasts.json --max-episodes 10
  
  # Migration mode - process with both fixed and schemaless
  %(prog)s seed --podcast-config podcasts.json --migration-mode
  
  # Use custom configuration
  %(prog)s seed --config config/prod.yml --podcast-config podcasts.json
  
  # Check component health
  %(prog)s health --config config/prod.yml
  
  # Validate configuration
  %(prog)s validate-config --config config/prod.yml
  
  # View schema discovery statistics
  %(prog)s schema-stats --checkpoint-dir checkpoints
        """
    )
    
    # Global options
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '-c', '--config',
        type=str,
        help='Path to configuration file (YAML)'
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands'
    )
    
    # Seed command
    seed_parser = subparsers.add_parser(
        'seed',
        help='Seed knowledge graph with podcasts'
    )
    
    # Input options (mutually exclusive)
    input_group = seed_parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--podcast-config',
        type=str,
        help='Path to JSON file with podcast configurations'
    )
    input_group.add_argument(
        '--rss-url',
        type=str,
        help='RSS URL for a single podcast'
    )
    
    # Additional options for single podcast
    seed_parser.add_argument(
        '--name',
        type=str,
        help='Podcast name (used with --rss-url)'
    )
    seed_parser.add_argument(
        '--category',
        type=str,
        help='Podcast category (used with --rss-url)'
    )
    
    # Processing options
    seed_parser.add_argument(
        '--max-episodes',
        type=int,
        default=10,
        help='Maximum episodes to process per podcast (default: 10)'
    )
    seed_parser.add_argument(
        '--large-context',
        action='store_true',
        help='Use large context models (more accurate but slower)'
    )
    
    # Schemaless extraction options
    seed_parser.add_argument(
        '--extraction-mode',
        type=str,
        choices=['fixed', 'schemaless'],
        default='fixed',
        help='Extraction mode: fixed schema or schemaless (default: fixed)'
    )
    seed_parser.add_argument(
        '--schema-discovery',
        action='store_true',
        help='Show discovered entity types after processing (schemaless mode only)'
    )
    seed_parser.add_argument(
        '--migration-mode',
        action='store_true',
        help='Enable dual processing mode for migration (processes with both fixed and schemaless)'
    )
    
    # Health command
    health_parser = subparsers.add_parser(
        'health',
        help='Check health of pipeline components'
    )
    health_parser.add_argument(
        '--large-context',
        action='store_true',
        help='Check large context model availability'
    )
    
    # Validate config command
    validate_parser = subparsers.add_parser(
        'validate-config',
        help='Validate configuration file'
    )
    validate_parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to configuration file to validate'
    )
    
    # Schema statistics command
    schema_parser = subparsers.add_parser(
        'schema-stats',
        help='Show schema statistics from schemaless extraction'
    )
    schema_parser.add_argument(
        '--checkpoint-dir',
        type=str,
        default='checkpoints',
        help='Directory containing checkpoint files (default: checkpoints)'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Validate flag combinations
    if hasattr(args, 'migration_mode') and hasattr(args, 'extraction_mode'):
        if args.migration_mode and args.extraction_mode != 'fixed':
            parser.error("--migration-mode requires --extraction-mode to be 'fixed' or omitted")
    
    if hasattr(args, 'schema_discovery') and hasattr(args, 'extraction_mode'):
        if args.schema_discovery and args.extraction_mode == 'fixed':
            parser.error("--schema-discovery only works with --extraction-mode schemaless")
    
    # Set up logging
    setup_logging(args.verbose)
    
    # Execute command
    if args.command == 'seed':
        return seed_podcasts(args)
    elif args.command == 'health':
        return health_check(args)
    elif args.command == 'validate-config':
        return validate_config(args)
    elif args.command == 'schema-stats':
        return schema_stats(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())