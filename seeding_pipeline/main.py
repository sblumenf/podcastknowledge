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
    neo4j_uri = neo4j_uri or os.getenv('NEO4J_URI', 'neo4j://localhost:7687')
    neo4j_user = neo4j_user or os.getenv('NEO4J_USER', 'neo4j')
    neo4j_password = neo4j_password or os.getenv('NEO4J_PASSWORD', 'password')
    gemini_api_key = gemini_api_key or os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    
    if not gemini_api_key:
        raise ValueError("Gemini API key required. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable or pass --gemini-api-key")
    
    # Model configuration for tiered approach
    MODEL_CONFIG = {
        "speaker_identification": "gemini-2.5-flash-preview-05-20",
        "conversation_analysis": "gemini-2.5-flash-preview-05-20", 
        "knowledge_extraction": "gemini-2.5-pro-preview-06-05"
    }
    
    # Initialize services
    logger.info("Initializing services...")
    
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
        model_name='gemini-2.5-flash-preview-05-20',
        max_tokens=30000,  # Flash model has lower token limit
        temperature=0.1  # Low temperature for extraction tasks
    )
    
    llm_pro = LLMService(
        api_key=gemini_api_key,
        model_name='gemini-2.5-pro-preview-06-05', 
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
        enable_speaker_mapping=True  # Enable speaker post-processing
    )
    
    # Prepare episode metadata
    if resume_episode_id:
        # Use the provided episode ID for resume
        episode_metadata = {
            'episode_id': resume_episode_id,
            'podcast_name': podcast_name,
            'episode_title': episode_title,
            'episode_url': episode_url,
            'vtt_file_path': str(vtt_path),
            'processing_timestamp': datetime.now().isoformat()
        }
    else:
        episode_metadata = {
            'episode_id': f"{podcast_name}_{episode_title}_{datetime.now().isoformat()}".replace(" ", "_"),
            'podcast_name': podcast_name,
            'episode_title': episode_title,
            'episode_url': episode_url,
            'vtt_file_path': str(vtt_path),
            'processing_timestamp': datetime.now().isoformat()
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


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Process VTT transcripts through the Unified Knowledge Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s transcript.vtt --podcast "My Podcast" --title "Episode 1"
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
        "vtt_file",
        type=Path,
        help="Path to VTT transcript file"
    )
    parser.add_argument(
        "-p", "--podcast",
        required=True,
        help="Name of the podcast"
    )
    parser.add_argument(
        "-t", "--title",
        required=True,
        help="Episode title"
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
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Set pipeline timeout from argument
    if args.timeout:
        os.environ['PIPELINE_TIMEOUT'] = str(args.timeout)
        logger.info(f"Set pipeline timeout to {args.timeout} seconds")
    
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
    
    # Validate VTT file exists
    if not args.vtt_file.exists():
        print(f"Error: VTT file not found: {args.vtt_file}")
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
                    vtt_path=args.vtt_file,
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
                vtt_path=args.vtt_file,
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
        print(f"Episode ID: {result.get('episode_id', 'N/A')}")
        print(f"Processing Time: {result.get('processing_time', 0):.2f} seconds")
        print(f"\nSegments Processed: {result.get('segments_processed', 0)}")
        print(f"Meaningful Units Created: {result.get('meaningful_units_created', 0)}")
        print(f"\nKnowledge Extracted:")
        print(f"  - Entities: {result.get('entities_extracted', 0)}")
        print(f"  - Quotes: {result.get('quotes_extracted', 0)}")
        print(f"  - Insights: {result.get('insights_extracted', 0)}")
        print(f"  - Relationships: {result.get('relationships_extracted', 0)}")
        print(f"\nGraph Storage:")
        print(f"  - Nodes Created: {result.get('nodes_created', 0)}")
        print(f"  - Relationships Created: {result.get('relationships_created', 0)}")
        print(f"\nAnalysis Results:")
        print(f"  - Structural Gaps: {result.get('gaps_detected', 0)}")
        print(f"  - Missing Links: {result.get('missing_links_found', 0)}")
        print(f"  - Diversity Score: {result.get('diversity_score', 0):.3f}")
        
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