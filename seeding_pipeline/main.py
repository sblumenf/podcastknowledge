#!/usr/bin/env python3
"""Main entry point for the Unified Knowledge Pipeline.

This script processes VTT transcript files through the complete knowledge extraction pipeline:
1. Parse VTT files into segments
2. Identify speakers using LLM
3. Analyze conversation structure
4. Group segments into meaningful semantic units
5. Extract entities, quotes, insights, and relationships
6. Store everything in Neo4j knowledge graph
7. Run analysis components (gap detection, diversity metrics, missing links)
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import argparse
from datetime import datetime

# Load environment variables from .env file
from dotenv import load_dotenv
from pathlib import Path

# Load .env from the seeding_pipeline directory
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    # Fallback to current directory
    load_dotenv()

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import pipeline components
from src.pipeline.unified_pipeline import UnifiedKnowledgePipeline
from src.storage.graph_storage import GraphStorageService
from src.services.llm import LLMService
from src.services.embeddings import EmbeddingsService
from src.core.config import SeedingConfig
from src.core.pipeline_config import PipelineConfig
from src.core.exceptions import PipelineError
from src.core.env_config import EnvironmentConfig
from src.clustering.semantic_clustering import SemanticClusteringSystem
import yaml


async def process_vtt_file(
    vtt_path: Path,
    podcast_name: str,
    episode_title: str,
    episode_url: Optional[str] = None,
    neo4j_uri: Optional[str] = None,
    neo4j_user: Optional[str] = None,
    neo4j_password: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    resume_episode_id: Optional[str] = None
) -> Dict[str, Any]:
    """Process a single VTT file through the unified pipeline.
    
    Args:
        vtt_path: Path to VTT transcript file
        podcast_name: Name of the podcast
        episode_title: Title of the episode
        episode_url: Optional YouTube URL for the episode
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        gemini_api_key: Gemini API key
        
    Returns:
        Dictionary containing processing results
    """
    # Use environment variables if not provided
    neo4j_user = neo4j_user or os.getenv('NEO4J_USER', 'neo4j')
    neo4j_password = neo4j_password or os.getenv('NEO4J_PASSWORD', 'password')
    gemini_api_key = gemini_api_key or os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    
    # Look up Neo4j URI from podcast configuration if not provided
    if not neo4j_uri:
        try:
            import yaml
            with open(Path(__file__).parent / 'config/podcasts.yaml', 'r') as f:
                podcasts_config = yaml.safe_load(f)
            
            # Find podcast by name - try RSS title first, then display name
            for podcast in podcasts_config.get('podcasts', []):
                # Try exact match on RSS title first (most reliable)
                if podcast.get('rss_title') == podcast_name:
                    db_config = podcast.get('database', {})
                    port = db_config.get('neo4j_port', 7687)
                    neo4j_uri = f'neo4j://localhost:{port}'
                    logger.info(f"Using Neo4j port {port} for podcast '{podcast_name}' (matched RSS title)")
                    break
                # Fall back to display name match
                elif podcast.get('name') == podcast_name:
                    db_config = podcast.get('database', {})
                    port = db_config.get('neo4j_port', 7687)
                    neo4j_uri = f'neo4j://localhost:{port}'
                    logger.info(f"Using Neo4j port {port} for podcast '{podcast_name}' (matched display name)")
                    break
            else:
                # Default if podcast not found
                neo4j_uri = os.getenv('NEO4J_URI', 'neo4j://localhost:7687')
                logger.warning(f"Podcast '{podcast_name}' not found in config, using default URI")
        except Exception as e:
            logger.warning(f"Failed to read podcast config: {e}, using default URI")
            neo4j_uri = os.getenv('NEO4J_URI', 'neo4j://localhost:7687')
    
    if not gemini_api_key:
        raise ValueError("Gemini API key required. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable or pass --gemini-api-key")
    
    # Validate model configuration
    validation_result = EnvironmentConfig.validate_model_configuration()
    if not validation_result['valid']:
        error_msg = "Invalid model configuration:\n" + "\n".join(f"  - {error}" for error in validation_result['errors'])
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.info(f"✓ Model configuration validated:")
    logger.info(f"  - Flash model: {validation_result['flash_model']['name']}")
    logger.info(f"  - Pro model: {validation_result['pro_model']['name']}")
    logger.info(f"  - Embedding model: {validation_result['embedding_model']['name']}")
    
    # Model configuration for tiered approach
    MODEL_CONFIG = {
        "speaker_identification": EnvironmentConfig.get_flash_model(),
        "conversation_analysis": EnvironmentConfig.get_flash_model(), 
        "knowledge_extraction": EnvironmentConfig.get_pro_model()
    }
    
    # Initialize services
    logger.info("Initializing services...")
    
    # Load configuration
    config = SeedingConfig()
    
    # Graph storage
    graph_storage = GraphStorageService(
        uri=neo4j_uri,
        username=neo4j_user,
        password=neo4j_password
    )
    graph_storage.connect()
    
    # Create separate LLM services for different models
    llm_flash = LLMService(
        api_key=gemini_api_key,
        model_name=EnvironmentConfig.get_flash_model(),
        max_tokens=30000,  # Flash model has lower token limit
        temperature=0.1  # Low temperature for extraction tasks
    )
    
    llm_pro = LLMService(
        api_key=gemini_api_key,
        model_name=EnvironmentConfig.get_pro_model(), 
        max_tokens=65000,  # Pro model can handle larger responses
        temperature=0.1  # Low temperature for extraction tasks
    )
    
    # For now, use pro as default until we update pipeline components
    llm_service = llm_pro
    
    # Embeddings service (optional)
    embeddings_service = None
    if os.getenv('USE_EMBEDDINGS', 'false').lower() == 'true':
        embeddings_service = EmbeddingsService(api_key=gemini_api_key)
    
    # Initialize pipeline with both LLM services
    pipeline = UnifiedKnowledgePipeline(
        graph_storage=graph_storage,
        llm_service=llm_service,  # Keep for backward compatibility
        embeddings_service=embeddings_service,
        llm_flash=llm_flash,
        llm_pro=llm_pro,
        enable_speaker_mapping=True,  # Enable speaker post-processing
        config=config
    )
    
    # Extract episode date from filename
    episode_date = extract_episode_date(vtt_path.name)
    
    # Prepare episode metadata
    if resume_episode_id:
        # Use the provided episode ID for resume
        episode_metadata = {
            'episode_id': resume_episode_id,
            'podcast_name': podcast_name,
            'episode_title': episode_title,
            'title': episode_title,  # Add title field for create_episode
            'episode_url': episode_url,
            'youtube_url': episode_url,  # Map to youtube_url for create_episode
            'vtt_file_path': str(vtt_path),
            'vtt_filename': vtt_path.name,  # Add filename for duplicate checking
            'processing_timestamp': datetime.now().isoformat(),
            'published_date': episode_date  # Add extracted date
        }
    else:
        episode_metadata = {
            'episode_id': f"{podcast_name}_{episode_title}_{datetime.now().isoformat()}".replace(" ", "_"),
            'podcast_name': podcast_name,
            'episode_title': episode_title,
            'title': episode_title,  # Add title field for create_episode
            'episode_url': episode_url,
            'youtube_url': episode_url,  # Map to youtube_url for create_episode
            'vtt_file_path': str(vtt_path),
            'vtt_filename': vtt_path.name,  # Add filename for duplicate checking
            'processing_timestamp': datetime.now().isoformat(),
            'published_date': episode_date  # Add extracted date
        }
    
    try:
        # Process the VTT file with timeout
        logger.info(f"Processing VTT file: {vtt_path}")
        logger.info(f"Pipeline timeout: {PipelineConfig.PIPELINE_TIMEOUT}s ({PipelineConfig.PIPELINE_TIMEOUT / 60:.1f} minutes)")
        
        # Apply timeout to the pipeline processing
        result = await asyncio.wait_for(
            pipeline.process_vtt_file(
                vtt_path=vtt_path,
                episode_metadata=episode_metadata
            ),
            timeout=PipelineConfig.PIPELINE_TIMEOUT
        )
        
        # Close connections
        graph_storage.close()
        
        return result
        
    except asyncio.TimeoutError:
        logger.error(f"Pipeline processing timed out after {PipelineConfig.PIPELINE_TIMEOUT}s")
        graph_storage.close()
        raise PipelineError(f"Processing timed out after {PipelineConfig.PIPELINE_TIMEOUT / 60:.1f} minutes. Consider increasing PIPELINE_TIMEOUT environment variable.")
    except Exception as e:
        logger.error(f"Pipeline processing failed: {e}")
        graph_storage.close()
        raise


def extract_episode_date(filename: str) -> Optional[str]:
    """Extract episode date from VTT filename.
    
    Args:
        filename: The filename (with or without extension)
        
    Returns:
        Date string in YYYY-MM-DD format if found, None otherwise
    """
    import re
    
    # Extract just the filename without extension if needed
    if '.' in filename:
        filename = filename.rsplit('.', 1)[0]
    
    # Look for date pattern at the beginning of filename
    # Pattern matches YYYY-MM-DD format
    date_pattern = r'^(\d{4}-\d{2}-\d{2})'
    match = re.match(date_pattern, filename)
    
    if match:
        date_str = match.group(1)
        # Validate it's a reasonable date
        try:
            parts = date_str.split('-')
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])
            
            # Basic validation
            if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                return date_str
        except:
            pass
    
    return None


def extract_title_from_filename(filename: str) -> str:
    """Extract a clean title from a VTT filename.
    
    Args:
        filename: The filename without extension
        
    Returns:
        Cleaned title
    """
    # Remove date prefix if present (e.g., "2022-10-06_")
    parts = filename.split('_', 1)
    if len(parts) > 1 and parts[0].count('-') == 2:
        # Check if first part looks like a date
        try:
            # Simple date validation
            date_parts = parts[0].split('-')
            if len(date_parts) == 3 and all(p.isdigit() for p in date_parts):
                title = parts[1]
            else:
                title = filename
        except:
            title = filename
    else:
        title = filename
    
    # Replace underscores with spaces
    title = title.replace('_', ' ')
    
    # Clean up common patterns
    title = title.replace('&', 'and')
    
    return title


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Process VTT transcripts through the Unified Knowledge Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Single file
  %(prog)s transcript.vtt --podcast "My Podcast" --title "Episode 1"
  
  # Directory of files
  %(prog)s /path/to/directory/ --directory --podcast "My Podcast"
  
  # With additional options
  %(prog)s /path/to/file.vtt -p "Tech Talk" -t "AI Discussion" --url "https://youtube.com/watch?v=..."
  
Environment Variables:
  NEO4J_URI: Neo4j connection URI (default: neo4j://localhost:7687)
  NEO4J_USER: Neo4j username (default: neo4j)
  NEO4J_PASSWORD: Neo4j password (default: password)
  GEMINI_API_KEY: Gemini API key (required)
  USE_EMBEDDINGS: Enable embeddings service (default: false)
"""
    )
    
    parser.add_argument(
        "path",
        type=Path,
        help="Path to VTT transcript file or directory"
    )
    parser.add_argument(
        "--directory",
        action="store_true",
        help="Process all VTT files in the directory"
    )
    parser.add_argument(
        "-p", "--podcast",
        required=True,
        help="Name of the podcast"
    )
    parser.add_argument(
        "-t", "--title",
        required=False,  # Made optional for directory mode
        help="Episode title (required for single file, auto-generated for directory)"
    )
    parser.add_argument(
        "-u", "--url",
        help="YouTube URL for the episode"
    )
    parser.add_argument(
        "--neo4j-uri",
        help="Neo4j connection URI (overrides NEO4J_URI env var)"
    )
    parser.add_argument(
        "--neo4j-user",
        help="Neo4j username (overrides NEO4J_USER env var)"
    )
    parser.add_argument(
        "--neo4j-password",
        help="Neo4j password (overrides NEO4J_PASSWORD env var)"
    )
    parser.add_argument(
        "--gemini-api-key",
        help="Gemini API key (overrides GEMINI_API_KEY env var)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=7200,
        help="Pipeline timeout in seconds (default: 7200 = 2 hours)"
    )
    
    # Checkpoint management commands
    parser.add_argument(
        "--list-checkpoints",
        action="store_true",
        help="List all existing checkpoints and exit"
    )
    parser.add_argument(
        "--clear-checkpoint",
        metavar="EPISODE_ID",
        help="Clear checkpoint for specific episode ID and exit"
    )
    parser.add_argument(
        "--resume",
        metavar="EPISODE_ID",
        help="Force resume from checkpoint for specific episode ID"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.directory:
        if not args.path.is_dir():
            print(f"Error: {args.path} is not a directory")
            sys.exit(1)
    else:
        if args.path.is_dir():
            print(f"Error: {args.path} is a directory. Use --directory flag to process all files in a directory.")
            sys.exit(1)
        if not args.title:
            print("Error: --title is required when processing a single file")
            sys.exit(1)
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Set pipeline timeout from argument
    if args.timeout:
        os.environ['PIPELINE_TIMEOUT'] = str(args.timeout)
        logger.info(f"Set pipeline timeout to {args.timeout} seconds")

    from src.persona_creation import ensure_persona_exists
    ensure_persona_exists(args.podcast)
    
    # Handle checkpoint management commands
    if args.list_checkpoints or args.clear_checkpoint:
        # Initialize checkpoint manager
        from src.pipeline.checkpoint import CheckpointManager
        checkpoint_manager = CheckpointManager()
        
        if args.list_checkpoints:
            # List all checkpoints
            checkpoints = checkpoint_manager.list_checkpoints()
            if checkpoints:
                print("\nExisting checkpoints:")
                print("-" * 80)
                for cp in checkpoints:
                    print(f"Episode: {cp['episode_id']}")
                    print(f"  Last Phase: {cp['last_phase']}")
                    print(f"  Timestamp: {cp['timestamp']}")
                    print(f"  Age: {cp['age_hours']:.2f} hours")
                    print(f"  Path: {cp['path']}")
                    print("-" * 80)
            else:
                print("No checkpoints found.")
            sys.exit(0)
            
        elif args.clear_checkpoint:
            # Clear specific checkpoint
            if checkpoint_manager.delete_checkpoint(args.clear_checkpoint):
                print(f"Checkpoint cleared for episode: {args.clear_checkpoint}")
            else:
                print(f"Failed to clear checkpoint for episode: {args.clear_checkpoint}")
            sys.exit(0)
    
    # Process based on mode
    if args.directory:
        # Directory mode - process all VTT files
        vtt_files = sorted(args.path.glob("*.vtt"))
        
        if not vtt_files:
            print(f"No VTT files found in directory: {args.path}")
            sys.exit(0)
        
        print(f"\nProcessing directory: {args.path}")
        print(f"Found {len(vtt_files)} VTT file(s)\n")
        
        success_count = 0
        skipped_count = 0
        failed_files = []
        
        # Aggregate statistics
        total_stats = {
            'segments_parsed': 0,
            'meaningful_units_created': 0,
            'entities_extracted': 0,
            'quotes_extracted': 0,
            'insights_extracted': 0,
            'relationships_extracted': 0,
            'nodes_created': 0,
            'relationships_created': 0,
            'processing_time': 0.0
        }
        
        for idx, vtt_file in enumerate(vtt_files, 1):
            # Extract title from filename
            title = extract_title_from_filename(vtt_file.stem)
            
            print(f"[{idx}/{len(vtt_files)}] Processing: {vtt_file.name}")
            print(f"  Title: {title}")
            
            try:
                start_time = datetime.now()
                
                # Process the file
                result = asyncio.run(process_vtt_file(
                    vtt_path=vtt_file,
                    podcast_name=args.podcast,
                    episode_title=title,
                    episode_url=args.url,
                    neo4j_uri=args.neo4j_uri,
                    neo4j_user=args.neo4j_user,
                    neo4j_password=args.neo4j_password,
                    gemini_api_key=args.gemini_api_key
                ))
                
                processing_time = (datetime.now() - start_time).total_seconds()
                
                # Check if episode was skipped
                if result.get('status') == 'skipped':
                    print(f"  ⏭ Skipped: {result.get('reason', 'Already processed')} ({processing_time:.1f}s)\n")
                    skipped_count += 1
                else:
                    print(f"  ✓ Success ({processing_time:.1f}s)\n")
                    success_count += 1
                    
                    # Aggregate statistics
                    stats = result.get('stats', {})
                    total_stats['segments_parsed'] += stats.get('segments_parsed', 0)
                    total_stats['meaningful_units_created'] += stats.get('meaningful_units_created', 0)
                    total_stats['entities_extracted'] += stats.get('entities_extracted', 0)
                    total_stats['quotes_extracted'] += stats.get('quotes_extracted', 0)
                    total_stats['insights_extracted'] += stats.get('insights_extracted', 0)
                    total_stats['relationships_extracted'] += stats.get('relationships_extracted', 0)
                    total_stats['nodes_created'] += stats.get('nodes_created', 0)
                    total_stats['relationships_created'] += stats.get('relationships_created', 0)
                    total_stats['processing_time'] += result.get('total_time', 0)
                
            except KeyboardInterrupt:
                print("\n\nProcessing interrupted by user")
                break
            except Exception as e:
                print(f"  ✗ Failed: {e}\n")
                failed_files.append((vtt_file.name, str(e)))
                if not args.verbose:
                    # Continue to next file on error
                    continue
                else:
                    import traceback
                    traceback.print_exc()
        
        # Print summary
        print("\n" + "="*60)
        print("BATCH PROCESSING SUMMARY")
        print("="*60)
        print(f"Total files: {len(vtt_files)}")
        print(f"Successful: {success_count}")
        print(f"Skipped: {skipped_count}")
        print(f"Failed: {len(failed_files)}")
        
        if success_count > 0:
            print(f"\nProcessing Time: {total_stats['processing_time']:.2f} seconds ({total_stats['processing_time']/60:.1f} minutes)")
            print(f"\nAggregate Statistics:")
            print(f"  Segments Processed: {total_stats['segments_parsed']:,}")
            print(f"  Meaningful Units Created: {total_stats['meaningful_units_created']:,}")
            print(f"\n  Knowledge Extracted:")
            print(f"    - Entities: {total_stats['entities_extracted']:,}")
            print(f"    - Quotes: {total_stats['quotes_extracted']:,}")
            print(f"    - Insights: {total_stats['insights_extracted']:,}")
            print(f"    - Relationships: {total_stats['relationships_extracted']:,}")
            print(f"\n  Graph Storage:")
            print(f"    - Nodes Created: {total_stats['nodes_created']:,}")
            print(f"    - Relationships Created: {total_stats['relationships_created']:,}")
        
        if failed_files:
            print("\nFailed files:")
            for filename, error in failed_files:
                print(f"  - {filename}: {error}")
        
        # Load clustering configuration to check if automatic clustering is enabled
        clustering_config_path = Path(__file__).parent / 'config' / 'clustering_config.yaml'
        clustering_config = {}
        if clustering_config_path.exists():
            with open(clustering_config_path, 'r') as f:
                clustering_config = yaml.safe_load(f)
        
        # Check pipeline configuration for automatic clustering
        pipeline_config = clustering_config.get('pipeline', {})
        auto_clustering_enabled = pipeline_config.get('auto_clustering_enabled', True)
        min_episodes_for_clustering = pipeline_config.get('min_episodes_for_clustering', 1)
        
        # AUTOMATIC CLUSTERING TRIGGER - Runs after successful episode processing
        if auto_clustering_enabled and success_count >= min_episodes_for_clustering:
            print(f"\n{'='*60}")
            print(f"TRIGGERING SEMANTIC CLUSTERING")
            print(f"{'='*60}")
            print(f"Processing {success_count} successfully loaded episodes...")
            
            try:
                # Configuration already loaded above
                if not clustering_config:
                    # Default configuration if file doesn't exist
                    clustering_config = {
                        'clustering': {
                            'min_cluster_size_formula': 'sqrt',
                            'min_samples': 3,
                            'epsilon': 0.3
                        }
                    }
                
                # Initialize clustering system using same Neo4j connection details
                # Get Neo4j connection details for this podcast
                neo4j_uri = args.neo4j_uri
                if not neo4j_uri:
                    # Look up from podcast configuration (same logic as process_vtt_file)
                    try:
                        with open(Path(__file__).parent / 'config/podcasts.yaml', 'r') as f:
                            podcasts_config = yaml.safe_load(f)
                        
                        for podcast in podcasts_config.get('podcasts', []):
                            if podcast.get('rss_title') == args.podcast or podcast.get('name') == args.podcast:
                                db_config = podcast.get('database', {})
                                port = db_config.get('neo4j_port', 7687)
                                neo4j_uri = f'neo4j://localhost:{port}'
                                break
                        else:
                            neo4j_uri = os.getenv('NEO4J_URI', 'neo4j://localhost:7687')
                    except Exception:
                        neo4j_uri = os.getenv('NEO4J_URI', 'neo4j://localhost:7687')
                
                # Create GraphStorageService for clustering (reuse connection pattern)
                neo4j_user = args.neo4j_user or os.getenv('NEO4J_USER', 'neo4j')
                neo4j_password = args.neo4j_password or os.getenv('NEO4J_PASSWORD', 'password')
                
                graph_storage = GraphStorageService(
                    uri=neo4j_uri,
                    username=neo4j_user,
                    password=neo4j_password
                )
                
                # Initialize clustering system - need LLM service for label generation
                # Get API key and setup LLM service
                gemini_api_key = args.gemini_api_key or os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
                if not gemini_api_key:
                    print("✗ Clustering requires GEMINI_API_KEY for label generation")
                    raise ValueError("Missing GEMINI_API_KEY for clustering")
                
                llm_service = LLMService(
                    api_key=gemini_api_key,
                    model_name=EnvironmentConfig.get_pro_model(), 
                    max_tokens=65000,
                    temperature=0.3  # Higher temperature for creative labeling
                )
                
                clustering_system = SemanticClusteringSystem(graph_storage, llm_service, clustering_config)
                
                # Check for edge cases before running clustering
                should_run_clustering = True
                try:
                    # Check if units with embeddings exist
                    count_query = """
                    MATCH (m:MeaningfulUnit)
                    WHERE m.embedding IS NOT NULL
                    RETURN count(m) as units_with_embeddings
                    """
                    count_result = graph_storage.query(count_query)
                    units_with_embeddings = count_result[0]['units_with_embeddings'] if count_result else 0
                    
                    if units_with_embeddings == 0:
                        print("⚠ Skipping clustering: No units with embeddings found")
                        print("  Ensure episode processing completed successfully and embeddings were generated")
                        should_run_clustering = False
                    
                    # Check minimum cluster size requirements
                    elif units_with_embeddings > 0:
                        min_cluster_size = clustering_config.get('clustering', {}).get('min_cluster_size_fixed', 5)
                        if clustering_config.get('clustering', {}).get('min_cluster_size_formula') == 'sqrt':
                            import math
                            min_cluster_size = max(3, int(math.sqrt(units_with_embeddings) / 2))
                        
                        if units_with_embeddings < min_cluster_size * 2:  # Need at least 2 clusters worth
                            print(f"⚠ Skipping clustering: Insufficient units for clustering")
                            print(f"  Found {units_with_embeddings} units, need at least {min_cluster_size * 2} for meaningful clusters")
                            should_run_clustering = False
                        else:
                            print(f"  Found {units_with_embeddings} units with embeddings, proceeding with clustering...")
                    
                except Exception as e:
                    print(f"⚠ Skipping clustering: Failed to check data availability - {e}")
                    should_run_clustering = False
                
                # Run clustering if conditions are met
                if should_run_clustering:
                    # STEP 1: Detect and process quarter boundaries for snapshots
                    print(f"\n{'='*60}")
                    print("DETECTING QUARTER BOUNDARIES")
                    print(f"{'='*60}")
                    
                    missing_quarters = clustering_system.detect_quarter_boundaries()
                    
                    if missing_quarters:
                        print(f"Found {len(missing_quarters)} quarters needing snapshots: {missing_quarters}")
                        
                        for quarter in missing_quarters:
                            print(f"\nCreating snapshot for quarter {quarter}...")
                            snapshot_start = datetime.now()
                            
                            snapshot_result = clustering_system.process_quarter_snapshot(quarter)
                            snapshot_duration = (datetime.now() - snapshot_start).total_seconds()
                            
                            if snapshot_result['status'] == 'success':
                                print(f"✓ Snapshot created for {quarter}")
                                print(f"  Duration: {snapshot_duration:.1f}s")
                                if 'stats' in snapshot_result:
                                    stats = snapshot_result['stats']
                                    print(f"  Clusters: {stats.get('n_clusters', 'N/A')}")
                                    print(f"  Units: {stats.get('total_units', 'N/A')}")
                                    print(f"  Outliers: {stats.get('n_outliers', 'N/A')}")
                            elif snapshot_result['status'] == 'skipped':
                                print(f"⏭ Skipped {quarter}: {snapshot_result.get('message', 'No data')}")
                            else:
                                print(f"✗ Failed to create snapshot for {quarter}: {snapshot_result.get('message', 'Unknown error')}")
                    else:
                        print("All quarters already have snapshots")
                    
                    # STEP 2: Run current clustering for user-facing clusters
                    print(f"\n{'='*60}")
                    print("UPDATING CURRENT CLUSTERS")
                    print(f"{'='*60}")
                    
                    cluster_start_time = datetime.now()
                    result = clustering_system.run_clustering(mode="current")
                    cluster_duration = (datetime.now() - cluster_start_time).total_seconds()
                    
                    if result['status'] == 'success':
                        print("✓ Clustering completed successfully")
                        print(f"  Duration: {cluster_duration:.1f}s")
                        if 'stats' in result:
                            stats = result['stats']
                            print(f"  Clusters created: {stats.get('clusters_created', 'N/A')}")
                            print(f"  Units clustered: {stats.get('units_clustered', 'N/A')}")
                            print(f"  Outliers: {stats.get('outliers', 'N/A')}")
                    else:
                        print(f"⚠ Clustering completed with warnings: {result.get('message', 'Unknown issue')}")
                
                # Close clustering connection
                graph_storage.close()
                
            except Exception as e:
                print(f"✗ Clustering failed: {e}")
                logger.error(f"Clustering failed: {e}", exc_info=True)
                # Don't fail the entire pipeline if clustering fails
        
        elif success_count > 0 and not auto_clustering_enabled:
            print(f"\n{'='*60}")
            print(f"AUTOMATIC CLUSTERING DISABLED")
            print(f"{'='*60}")
            print(f"Automatic clustering is disabled in configuration.")
            print(f"To enable, set 'auto_clustering_enabled: true' in clustering_config.yaml")
        
        elif success_count > 0 and success_count < min_episodes_for_clustering:
            print(f"\n{'='*60}")
            print(f"CLUSTERING THRESHOLD NOT MET")
            print(f"{'='*60}")
            print(f"Only {success_count} episodes processed, need at least {min_episodes_for_clustering}.")
            print(f"To change threshold, update 'min_episodes_for_clustering' in clustering_config.yaml")
        
        sys.exit(1 if failed_files else 0)
    
    else:
        # Single file mode - existing behavior
        if not args.path.exists():
            print(f"Error: VTT file not found: {args.path}")
            sys.exit(1)
        
        # Run async processing
        try:
            # If --resume is specified, use that episode ID
            if args.resume:
                # Load checkpoint to get metadata
                from src.pipeline.checkpoint import CheckpointManager
                checkpoint_manager = CheckpointManager()
                checkpoint = checkpoint_manager.load_checkpoint(args.resume)
                if checkpoint:
                    # Use checkpoint metadata
                    episode_metadata = checkpoint.metadata
                    result = asyncio.run(process_vtt_file(
                        vtt_path=args.path,
                        podcast_name=episode_metadata.get('podcast_name', args.podcast),
                        episode_title=episode_metadata.get('episode_title', args.title),
                        episode_url=episode_metadata.get('episode_url', args.url),
                        neo4j_uri=args.neo4j_uri,
                        neo4j_user=args.neo4j_user,
                        neo4j_password=args.neo4j_password,
                        gemini_api_key=args.gemini_api_key,
                        resume_episode_id=args.resume
                    ))
                else:
                    print(f"Error: No checkpoint found for episode: {args.resume}")
                    sys.exit(1)
            else:
                result = asyncio.run(process_vtt_file(
                    vtt_path=args.path,
                    podcast_name=args.podcast,
                    episode_title=args.title,
                    episode_url=args.url,
                    neo4j_uri=args.neo4j_uri,
                    neo4j_user=args.neo4j_user,
                    neo4j_password=args.neo4j_password,
                    gemini_api_key=args.gemini_api_key
                ))
            
            # Print results
            print("\n" + "="*60)
            print("PROCESSING COMPLETE")
            print("="*60)
            print(f"Status: {result.get('status', 'unknown')}")
            
            # Handle skipped episodes
            if result.get('status') == 'skipped':
                print(f"Reason: {result.get('reason', 'Already processed')}")
                if result.get('existing_episode'):
                    print(f"Existing Episode: {result['existing_episode']}")
                print(f"Episode ID: {result.get('episode_id', 'N/A')}")
                sys.exit(0)
            
            print(f"Episode ID: {result.get('episode_id', 'N/A')}")
            print(f"Processing Time: {result.get('total_time', 0):.2f} seconds")
            
            # Get stats from nested dictionary or top level
            stats = result.get('stats', {})
            
            print(f"\nSegments Processed: {stats.get('segments_parsed', result.get('segments_parsed', 0))}")
            print(f"Meaningful Units Created: {stats.get('meaningful_units_created', result.get('meaningful_units_created', 0))}")
            print(f"\nKnowledge Extracted:")
            print(f"  - Entities: {stats.get('entities_extracted', result.get('entities_extracted', 0))}")
            print(f"  - Quotes: {stats.get('quotes_extracted', result.get('quotes_extracted', 0))}")
            print(f"  - Insights: {stats.get('insights_extracted', result.get('insights_extracted', 0))}")
            print(f"  - Relationships: {stats.get('relationships_extracted', result.get('relationships_extracted', 0))}")
            print(f"\nGraph Storage:")
            print(f"  - Nodes Created: {stats.get('nodes_created', result.get('nodes_created', 0))}")
            print(f"  - Relationships Created: {stats.get('relationships_created', result.get('relationships_created', 0))}")
            print(f"\nAnalysis Results:")
            # Get analysis results from stats
            analysis_results = stats.get('analysis_results', {})
            gaps = analysis_results.get('gap_detection', {}).get('gaps_detected', 0)
            missing_links = analysis_results.get('missing_links', {}).get('missing_links_found', 0)
            diversity = analysis_results.get('diversity_metrics', {}).get('diversity_score', 0.0)
            
            print(f"  - Structural Gaps: {gaps}")
            print(f"  - Missing Links: {missing_links}")
            print(f"  - Diversity Score: {diversity:.3f}")
            
            if result.get('errors'):
                print(f"\nErrors encountered: {len(result['errors'])}")
                for error in result['errors'][:5]:  # Show first 5 errors
                    print(f"  - {error}")
                    
        except KeyboardInterrupt:
            print("\nProcessing interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\nError: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()