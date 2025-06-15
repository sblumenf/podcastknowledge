#!/usr/bin/env python3
"""Process a single VTT file through the knowledge extraction pipeline.

This module provides a real implementation of episode processing that:
1. Parses VTT transcripts into segments
2. Analyzes conversation structure using AI
3. Groups segments into meaningful semantic units
4. Extracts entities, quotes, insights, and relationships
5. Resolves entities across the episode
6. Stores everything in Neo4j with rich relationships
"""

import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import logging
import argparse

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)

def process_episode(vtt_file_path: Path, podcast_name: str, episode_title: str) -> Dict[str, Any]:
    """
    Process a single episode through the knowledge extraction pipeline.
    
    This function implements the full semantic knowledge extraction pipeline:
    1. Parse VTT file into transcript segments
    2. Analyze conversation structure to identify themes and flow
    3. Regroup segments into meaningful semantic units (topics, Q&A pairs, stories)
    4. Extract entities, quotes, insights, and relationships from each unit
    5. Resolve entities across units to create canonical entities
    6. Store everything in Neo4j graph database with rich relationships
    
    Args:
        vtt_file_path: Path to the VTT transcript file
        podcast_name: Name of the podcast
        episode_title: Title of the episode
        
    Returns:
        Dictionary containing processing results and statistics
    """
    from src.seeding.multi_podcast_orchestrator import MultiPodcastVTTKnowledgeExtractor
    from src.core.config import SeedingConfig
    from src.seeding.transcript_ingestion import VTTFile
    import hashlib
    
    # Initialize configuration
    config = SeedingConfig()
    
    # Create pipeline instance using the actual working orchestrator
    pipeline = MultiPodcastVTTKnowledgeExtractor(config=config)
    
    # Initialize pipeline components
    if not pipeline.initialize_components(use_large_context=True):
        raise RuntimeError("Failed to initialize pipeline components")
    
    # Create VTTFile object
    file_hash = hashlib.sha256(vtt_file_path.read_bytes()).hexdigest()
    
    vtt_file = VTTFile(
        path=vtt_file_path,
        podcast_name=podcast_name,
        episode_title=episode_title,
        file_hash=file_hash,
        size_bytes=vtt_file_path.stat().st_size,
        created_at=datetime.fromtimestamp(vtt_file_path.stat().st_ctime)
    )
    
    try:
        # Process the VTT file through the pipeline
        results = pipeline.process_vtt_files([vtt_file], use_large_context=True)
        
        # Extract detailed statistics from results
        if results and 'episodes_processed' in results and results['episodes_processed'] > 0:
            # Get the first (and only) episode's detailed results
            episode_results = results.get('episode_details', [{}])[0]
            
            return {
                'status': 'success',
                'processing_type': episode_results.get('processing_type', 'semantic'),
                'segments_processed': episode_results.get('total_segments', 0),
                'meaningful_units': episode_results.get('meaningful_units', 0),
                'entities_extracted': episode_results.get('entities', 0),
                'quotes_extracted': episode_results.get('quotes', 0),
                'insights_extracted': episode_results.get('insights', 0),
                'relationships_discovered': episode_results.get('relationships', 0),
                'themes_identified': episode_results.get('extraction_metadata', {}).get('themes', []),
                'processing_time': episode_results.get('processing_time', 0),
                'graph_nodes_created': episode_results.get('graph_nodes', 0),
                'graph_relationships_created': episode_results.get('graph_relationships', 0),
                'file_hash': file_hash,
                'episode_id': episode_results.get('episode_id'),
                'conversation_structure': {
                    'narrative_arc': episode_results.get('narrative_arc'),
                    'coherence_score': episode_results.get('coherence_score'),
                    'unit_statistics': episode_results.get('unit_statistics', {})
                }
            }
        else:
            # Return minimal success result if no detailed stats
            return {
                'status': 'success',
                'processing_type': 'semantic',
                'segments_processed': results.get('total_segments', 0),
                'entities_extracted': results.get('total_entities', 0),
                'quotes_extracted': results.get('total_quotes', 0),
                'file_hash': file_hash,
                'message': 'Processing completed successfully'
            }
            
    except Exception as e:
        logging.error(f"Error processing episode: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'file_hash': file_hash
        }
    finally:
        # Clean up resources
        pipeline.cleanup()


def main():
    parser = argparse.ArgumentParser(
        description="Process a single VTT file through the knowledge extraction pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s /path/to/transcript.vtt --podcast "My Podcast" --title "Episode Title"
  %(prog)s transcript.vtt -p "Tech Talk" -t "AI Discussion"
"""
    )
    parser.add_argument(
        "vtt_file",
        type=Path,
        help="Path to the VTT transcript file"
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
    
    args = parser.parse_args()
    
    vtt_path = args.vtt_file
    if not vtt_path.exists():
        print(f"Error: VTT file not found at {vtt_path}")
        sys.exit(1)
    
    try:
        print(f"Processing {vtt_path.name}...")
        results = process_episode(
            vtt_file_path=vtt_path,
            podcast_name=args.podcast,
            episode_title=args.title
        )
        
        print(f"\nProcessing Status: {results['status']}")
        
        if results['status'] == 'success':
            print(f"Processing Type: {results.get('processing_type', 'unknown')}")
            print(f"Segments Processed: {results.get('segments_processed', 0)}")
            print(f"Meaningful Units Created: {results.get('meaningful_units', 0)}")
            print(f"Entities Extracted: {results.get('entities_extracted', 0)}")
            print(f"Quotes Extracted: {results.get('quotes_extracted', 0)}")
            print(f"Insights Extracted: {results.get('insights_extracted', 0)}")
            print(f"Relationships Discovered: {results.get('relationships_discovered', 0)}")
            
            if 'themes_identified' in results and results['themes_identified']:
                print(f"Themes Identified: {', '.join(results['themes_identified'])}")
                
            if 'conversation_structure' in results:
                structure = results['conversation_structure']
                if structure.get('narrative_arc'):
                    print(f"Narrative Arc: {structure['narrative_arc']}")
                if structure.get('coherence_score') is not None:
                    print(f"Coherence Score: {structure['coherence_score']:.2f}")
                    
            print(f"Processing Time: {results.get('processing_time', 0):.2f}s")
            print(f"Graph Nodes Created: {results.get('graph_nodes_created', 0)}")
            print(f"Graph Relationships Created: {results.get('graph_relationships_created', 0)}")
        else:
            print(f"Error: {results.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()