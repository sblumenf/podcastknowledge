"""Simple Orchestrator for Podcast Transcription.

This module provides a simplified orchestration layer without complex state management.
Direct flow: download → transcribe → map speakers → format VTT → save.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.utils.logging import get_logger
from src.deepgram_client import DeepgramClient
from src.vtt_formatter import VTTFormatter
from src.file_organizer import FileOrganizer
from src.feed_parser import Episode

logger = get_logger('simple_orchestrator')


class SimpleOrchestrator:
    """Simplified orchestrator for podcast transcription pipeline."""
    
    def __init__(self, output_dir: Optional[str] = None, mock_enabled: bool = False):
        """Initialize the simple orchestrator.
        
        Args:
            output_dir: Base directory for output files. Defaults to TRANSCRIPT_OUTPUT_DIR env var.
            mock_enabled: If True, uses mock Deepgram responses.
        """
        self.output_dir = output_dir or os.getenv('TRANSCRIPT_OUTPUT_DIR', 'output/transcripts')
        self.mock_enabled = mock_enabled
        
        # Initialize components
        self.deepgram_client = DeepgramClient(mock_enabled=mock_enabled)
        self.vtt_formatter = VTTFormatter()
        self.file_organizer = FileOrganizer(base_output_dir=self.output_dir)
        
        # Create output directory if it doesn't exist
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized SimpleOrchestrator with output_dir={self.output_dir}, mock={mock_enabled}")
    
    def process_episode(self, episode: Episode) -> Dict[str, Any]:
        """Process a single podcast episode.
        
        Args:
            episode: Episode object with metadata and audio URL.
            
        Returns:
            Dictionary with processing results.
        """
        logger.info(f"Starting processing for episode: {episode.title}")
        
        result = {
            'episode_title': episode.title,
            'episode_guid': episode.guid,
            'status': 'pending',
            'output_path': None,
            'error': None,
            'processing_time': 0.0
        }
        
        start_time = datetime.now()
        
        try:
            # Step 1: Transcribe audio
            logger.info("Step 1: Transcribing audio with Deepgram")
            deepgram_response = self.deepgram_client.transcribe_audio(episode.audio_url)
            
            # Step 2: Format as VTT (includes speaker mapping)
            logger.info("Step 2: Formatting transcript as VTT with speaker mapping")
            vtt_content = self.vtt_formatter.format_deepgram_response(deepgram_response.results)
            
            # Step 3: Validate VTT
            logger.info("Step 3: Validating VTT content")
            is_valid, error_msg = self.vtt_formatter.validate_vtt(vtt_content)
            if not is_valid:
                raise ValueError(f"Invalid VTT content: {error_msg}")
            
            # Step 4: Save VTT file
            logger.info("Step 4: Saving VTT file")
            output_path = self.file_organizer.get_output_path(episode)
            
            # Ensure directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write VTT content
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(vtt_content)
            
            logger.info(f"Successfully saved VTT to: {output_path}")
            
            # Update result
            result['status'] = 'completed'
            result['output_path'] = str(output_path)
            
        except Exception as e:
            logger.error(f"Error processing episode '{episode.title}': {str(e)}")
            result['status'] = 'failed'
            result['error'] = str(e)
        
        # Calculate processing time
        result['processing_time'] = (datetime.now() - start_time).total_seconds()
        
        logger.info(
            f"Episode processing completed: status={result['status']}, "
            f"time={result['processing_time']:.1f}s"
        )
        
        return result
    
    def process_episodes(self, episodes: List[Episode]) -> Dict[str, Any]:
        """Process multiple episodes sequentially.
        
        Args:
            episodes: List of Episode objects to process.
            
        Returns:
            Dictionary with overall results.
        """
        logger.info(f"Starting batch processing for {len(episodes)} episodes")
        
        results = {
            'total_episodes': len(episodes),
            'completed': 0,
            'failed': 0,
            'episodes': []
        }
        
        for i, episode in enumerate(episodes, 1):
            logger.info(f"Processing episode {i}/{len(episodes)}: {episode.title}")
            
            episode_result = self.process_episode(episode)
            results['episodes'].append(episode_result)
            
            if episode_result['status'] == 'completed':
                results['completed'] += 1
            else:
                results['failed'] += 1
        
        logger.info(
            f"Batch processing completed: {results['completed']}/{results['total_episodes']} successful"
        )
        
        return results
    
    def generate_summary_report(self, results: Dict[str, Any]) -> str:
        """Generate a summary report of processing results.
        
        Args:
            results: Results dictionary from process_episodes.
            
        Returns:
            Formatted summary report.
        """
        report_lines = [
            "=" * 60,
            "TRANSCRIPTION SUMMARY",
            "=" * 60,
            f"Total episodes: {results['total_episodes']}",
            f"Completed: {results['completed']}",
            f"Failed: {results['failed']}",
            ""
        ]
        
        if results['episodes']:
            report_lines.append("Episode Details:")
            for episode_result in results['episodes']:
                status_icon = "✓" if episode_result['status'] == 'completed' else "✗"
                report_lines.append(f"  {status_icon} {episode_result['episode_title']}")
                
                if episode_result['status'] == 'completed':
                    report_lines.append(f"    Output: {episode_result['output_path']}")
                else:
                    report_lines.append(f"    Error: {episode_result['error']}")
                
                report_lines.append(f"    Time: {episode_result['processing_time']:.1f}s")
        
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)