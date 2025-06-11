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
from src.progress_tracker import ProgressTracker
from src.deepgram_client import DeepgramClient
from src.vtt_formatter import VTTFormatter
from src.semantic_vtt_formatter import SemanticVTTFormatter
from src.syntactic_vtt_formatter import SyntacticVTTFormatter
from src.conversational_vtt_formatter import ConversationalVTTFormatter
from src.file_organizer_simple import SimpleFileOrganizer
from src.feed_parser import Episode
from src.config import Config
from src.youtube_searcher import YouTubeSearcher

logger = get_logger('simple_orchestrator')


class SimpleOrchestrator:
    """Simplified orchestrator for podcast transcription pipeline."""
    
    def __init__(self, output_dir: Optional[str] = None, mock_enabled: bool = False, force_reprocess: bool = False):
        """Initialize the simple orchestrator.
        
        Args:
            output_dir: Base directory for output files. Defaults to TRANSCRIPT_OUTPUT_DIR env var.
            mock_enabled: If True, uses mock Deepgram responses.
            force_reprocess: If True, reprocess episodes even if already transcribed.
        """
        self.output_dir = output_dir or os.getenv('TRANSCRIPT_OUTPUT_DIR', 'output/transcripts')
        self.mock_enabled = mock_enabled
        self.force_reprocess = force_reprocess
        
        # Initialize components
        self.progress_tracker = ProgressTracker()
        self.deepgram_client = DeepgramClient(mock_enabled=mock_enabled)
        self.file_organizer = SimpleFileOrganizer(base_output_dir=self.output_dir)
        
        # Load configuration
        config = Config()
        
        # Initialize YouTube searcher if enabled
        youtube_config = config.youtube_search
        if youtube_config.enabled:
            self.youtube_searcher = YouTubeSearcher(config)
            logger.info("YouTube search enabled")
        else:
            self.youtube_searcher = None
            logger.info("YouTube search disabled")
        
        # Load VTT formatting configuration
        vtt_config = config._raw_config.get('vtt_formatting', {})
        segmentation_type = vtt_config.get('segmentation_type', 'regular')
        
        # Initialize appropriate VTT formatter based on configuration
        if segmentation_type == 'conversational':
            conv_config = vtt_config.get('conversational', {})
            self.vtt_formatter = ConversationalVTTFormatter(
                min_segment_duration=conv_config.get('min_segment_duration', 3.0),
                preferred_segment_duration=conv_config.get('preferred_segment_duration', 30.0),
                max_segment_duration=conv_config.get('max_segment_duration', 180.0),
                pause_threshold=conv_config.get('pause_threshold', 2.0),
                merge_short_interjections=conv_config.get('merge_short_interjections', True),
                respect_sentences=conv_config.get('respect_sentences', True),
                use_discourse_markers=conv_config.get('use_discourse_markers', True)
            )
            logger.info("Using conversational VTT segmentation (podcast-optimized)")
        elif segmentation_type == 'syntactic':
            self.vtt_formatter = SyntacticVTTFormatter()
            logger.info("Using syntactic VTT segmentation (research-based)")
        elif segmentation_type == 'semantic':
            semantic_config = vtt_config.get('semantic', {})
            self.vtt_formatter = SemanticVTTFormatter(
                min_cue_duration=semantic_config.get('min_cue_duration', 3.0),
                max_cue_duration=semantic_config.get('max_cue_duration', 10.0),
                prefer_sentence_breaks=semantic_config.get('prefer_sentence_breaks', True),
                allow_clause_breaks=semantic_config.get('allow_clause_breaks', True),
                max_chars_per_line=semantic_config.get('max_chars_per_line', 120)
            )
            logger.info("Using semantic VTT segmentation")
        else:
            regular_config = vtt_config.get('regular', {})
            self.vtt_formatter = VTTFormatter(
                max_cue_duration=regular_config.get('max_cue_duration', 7.0),
                max_chars_per_line=regular_config.get('max_chars_per_line', 80)
            )
            logger.info("Using regular VTT segmentation")
        
        # Create output directory if it doesn't exist
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized SimpleOrchestrator with output_dir={self.output_dir}, mock={mock_enabled}")
    
    def _parse_duration_to_seconds(self, duration_str: str) -> Optional[int]:
        """Parse duration string to seconds.
        
        Args:
            duration_str: Duration in format "HH:MM:SS" or "MM:SS" or just seconds
            
        Returns:
            Duration in seconds or None if parsing fails
        """
        if not duration_str:
            return None
            
        try:
            # If it's already a number, return it
            if duration_str.isdigit():
                return int(duration_str)
                
            # Parse HH:MM:SS or MM:SS format
            parts = duration_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            elif len(parts) == 2:
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            else:
                return int(duration_str)
        except:
            return None
    
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
        
        # Check if episode is already transcribed
        podcast_name = getattr(episode, 'podcast_name', 'Unknown Podcast')
        if not self.force_reprocess and self.progress_tracker.is_episode_transcribed(podcast_name, episode.title):
            logger.info(f"Episode already transcribed, skipping: {episode.title}")
            result['status'] = 'skipped'
            result['error'] = 'Already transcribed'
            return result
        
        start_time = datetime.now()
        
        try:
            # Step 1: Search for YouTube URL if enabled and not already present
            if self.youtube_searcher and not episode.youtube_url:
                logger.info("Step 1: Searching for YouTube URL")
                try:
                    # Use the async search method directly with proper parameters
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    youtube_url = loop.run_until_complete(
                        self.youtube_searcher.search_youtube_url(
                            episode_title=episode.title,
                            podcast_name=episode.podcast_name if hasattr(episode, 'podcast_name') else None,
                            episode_description=episode.description,
                            episode_guid=episode.guid,
                            episode_number=episode.episode_number,
                            duration_seconds=self._parse_duration_to_seconds(episode.duration) if episode.duration else None
                        )
                    )
                    loop.close()
                    
                    if youtube_url:
                        episode.youtube_url = youtube_url
                        logger.info(f"Found YouTube URL: {episode.youtube_url}")
                    else:
                        logger.info("No YouTube URL found")
                except Exception as e:
                    logger.warning(f"YouTube search failed: {str(e)}")
            
            # Step 2: Transcribe audio
            logger.info("Step 2: Transcribing audio with Deepgram")
            deepgram_response = self.deepgram_client.transcribe_audio(episode.audio_url)
            
            # Step 3: Format as VTT (includes speaker mapping)
            logger.info("Step 3: Formatting transcript as VTT with speaker mapping")
            vtt_content = self.vtt_formatter.format_deepgram_response(
                deepgram_response.results, 
                episode=episode,
                deepgram_metadata=deepgram_response.metadata
            )
            
            # Validate VTT
            logger.info("Validating VTT content")
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
            
            # Mark episode as transcribed
            date_str = episode.published_date.strftime('%Y-%m-%d') if episode.published_date else datetime.now().strftime('%Y-%m-%d')
            self.progress_tracker.mark_episode_transcribed(podcast_name, episode.title, date_str)
            
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
            'skipped': 0,
            'episodes': []
        }
        
        for i, episode in enumerate(episodes, 1):
            logger.info(f"Processing episode {i}/{len(episodes)}: {episode.title}")
            
            episode_result = self.process_episode(episode)
            results['episodes'].append(episode_result)
            
            if episode_result['status'] == 'completed':
                results['completed'] += 1
            elif episode_result['status'] == 'skipped':
                results['skipped'] += 1
            else:
                results['failed'] += 1
        
        logger.info(
            f"Batch processing completed: {results['completed']} successful, "
            f"{results['skipped']} skipped, {results['failed']} failed "
            f"(total: {results['total_episodes']})"
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
            f"Skipped: {results.get('skipped', 0)}",
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