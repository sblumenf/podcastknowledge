#!/usr/bin/env python3
"""Diagnostic script to test conversation analyzer with the Mohnish Pabrai episode."""

import sys
import os
import json
import logging
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.vtt.vtt_parser import VTTParser
from src.services.conversation_analyzer import ConversationAnalyzer
from src.services.llm_factory import LLMServiceFactory
from src.core.config import Config

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # Path to the episode
    vtt_path = "/home/sergeblumenfeld/podcastknowledge/data/transcripts/My_First_Million/2025-05-09_Asking_a_Billionaire_Investor_How_to_Turn_$10,000_into_$1M_ft._Mohnish_Pabrai.vtt"
    
    if not os.path.exists(vtt_path):
        logger.error(f"VTT file not found: {vtt_path}")
        return
    
    try:
        # Parse VTT file
        logger.info("Parsing VTT file...")
        parser = VTTParser()
        segments = parser.parse_file(Path(vtt_path))
        logger.info(f"Parsed {len(segments)} segments")
        
        # Calculate total duration
        if segments:
            total_duration = segments[-1]['end_time'] - segments[0]['start_time']
            logger.info(f"Total duration: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
        
        # Initialize LLM service
        logger.info("Initializing LLM service...")
        config = Config()
        llm_service = LLMServiceFactory.create_service()
        
        # Create conversation analyzer
        logger.info("Creating conversation analyzer...")
        analyzer = ConversationAnalyzer(llm_service)
        
        # Test with a small subset first
        logger.info("\n=== Testing with first 50 segments ===")
        test_segments = segments[:50]
        
        try:
            structure = analyzer.analyze_structure(test_segments)
            logger.info(f"SUCCESS: Created {len(structure.units)} units from {len(test_segments)} segments")
            for i, unit in enumerate(structure.units):
                logger.info(f"  Unit {i}: segments {unit.start_index}-{unit.end_index}, {unit.description[:50]}...")
        except Exception as e:
            logger.error(f"FAILED with subset: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Now test with full episode
        logger.info("\n=== Testing with full episode (313 segments) ===")
        
        try:
            # Patch the analyzer to capture the raw LLM response
            original_complete = analyzer.llm_service.complete_with_options
            raw_response = None
            
            def capture_response(*args, **kwargs):
                nonlocal raw_response
                result = original_complete(*args, **kwargs)
                raw_response = result
                logger.info(f"LLM Response type: {type(result)}")
                logger.info(f"LLM Response keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
                if isinstance(result, dict) and 'content' in result:
                    content = result['content']
                    logger.info(f"Content type: {type(content)}")
                    if isinstance(content, str):
                        logger.info(f"Content length: {len(content)} characters")
                        logger.info(f"First 500 chars: {content[:500]}")
                    elif isinstance(content, dict):
                        logger.info(f"Content keys: {content.keys()}")
                return result
            
            analyzer.llm_service.complete_with_options = capture_response
            
            structure = analyzer.analyze_structure(segments)
            
            # Check if fallback was used
            if len(structure.units) == 1 and "fallback" in structure.units[0].description.lower():
                logger.warning("FALLBACK STRUCTURE WAS USED!")
                logger.info(f"Raw LLM response: {raw_response}")
            else:
                logger.info(f"SUCCESS: Created {len(structure.units)} units from {len(segments)} segments")
                
            # Show structure summary
            logger.info("\n=== Structure Summary ===")
            logger.info(f"Units: {len(structure.units)}")
            logger.info(f"Themes: {len(structure.themes)}")
            logger.info(f"Boundaries: {len(structure.boundaries)}")
            logger.info(f"Overall coherence: {structure.insights.overall_coherence}")
            
            # Save the raw response for analysis
            if raw_response:
                output_file = "conversation_analyzer_diagnostic.json"
                with open(output_file, 'w') as f:
                    json.dump({
                        'episode': os.path.basename(vtt_path),
                        'segments_count': len(segments),
                        'raw_llm_response': raw_response,
                        'structure_created': {
                            'units': len(structure.units),
                            'is_fallback': len(structure.units) == 1 and "fallback" in structure.units[0].description.lower()
                        }
                    }, f, indent=2)
                logger.info(f"\nDiagnostic data saved to: {output_file}")
            
        except Exception as e:
            logger.error(f"FAILED with full episode: {str(e)}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()