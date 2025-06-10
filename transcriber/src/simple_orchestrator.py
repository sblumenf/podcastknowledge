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
from src.semantic_vtt_formatter import SemanticVTTFormatter
from src.syntactic_vtt_formatter import SyntacticVTTFormatter
from src.conversational_vtt_formatter import ConversationalVTTFormatter
from src.file_organizer import FileOrganizer
from src.feed_parser import Episode
from src.config import Config
from src.youtube_searcher import YouTubeSearcher

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
        self.file_organizer = FileOrganizer(base_output_dir=self.output_dir)
        
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
            # Step 1: Search for YouTube URL if enabled and not already present
            if self.youtube_searcher and not episode.youtube_url:
                logger.info("Step 1: Searching for YouTube URL")
                search_query = f"{episode.podcast_name} {episode.title}"
                try:
                    youtube_results = self.youtube_searcher.search_youtube(search_query)
                    if youtube_results and len(youtube_results) > 0:
                        # Take the first result
                        episode.youtube_url = f"https://www.youtube.com/watch?v={youtube_results[0]['video_id']}"
                        logger.info(f"Found YouTube URL: {episode.youtube_url}")
                    else:
                        logger.info("No YouTube URL found")
                except Exception as e:
                    logger.warning(f"YouTube search failed: {str(e)}")
            
            # Step 2: Transcribe audio
            logger.info("Step 2: Transcribing audio with Deepgram")
            deepgram_response = self.deepgram_client.transcribe_audio(episode.audio_url)
            
            # Save comprehensive JSON with episode metadata and Deepgram response
            import json
            output_path = self.file_organizer.get_output_path(episode)
            json_path = output_path.with_suffix('.json')
            
            # Calculate transcript statistics
            words = []
            alternatives = []
            if hasattr(deepgram_response.results, 'channels') and deepgram_response.results.channels:
                alternatives = deepgram_response.results.channels[0].get('alternatives', [])
                if alternatives:
                    words = alternatives[0].get('words', [])
            
            # Count unique speakers
            unique_speakers = set()
            for word in words:
                unique_speakers.add(word.get('speaker', 0))
            
            # Create comprehensive metadata
            comprehensive_data = {
                'episode': {
                    'title': episode.title,
                    'podcast_name': getattr(episode, 'podcast_name', None),
                    'description': episode.description if episode.description else None,
                    'published_date': episode.published_date.isoformat() if episode.published_date else None,
                    'duration': episode.duration,
                    'episode_number': episode.episode_number,
                    'season_number': episode.season_number,
                    'author': episode.author,
                    'keywords': episode.keywords if episode.keywords else [],
                    'link': episode.link,
                    'youtube_url': episode.youtube_url,
                    'audio_url': episode.audio_url,
                    'guid': episode.guid,
                    'file_size': episode.file_size,
                    'mime_type': episode.mime_type
                },
                'transcription': {
                    'service': 'Deepgram',
                    'model': deepgram_response.metadata.get('model_info', {}).get(
                        list(deepgram_response.metadata.get('model_info', {}).keys())[0] if deepgram_response.metadata.get('model_info') else '',
                        {}
                    ).get('arch', 'unknown'),
                    'model_version': deepgram_response.metadata.get('model_info', {}).get(
                        list(deepgram_response.metadata.get('model_info', {}).keys())[0] if deepgram_response.metadata.get('model_info') else '',
                        {}
                    ).get('version', 'unknown'),
                    'request_id': deepgram_response.metadata.get('request_id'),
                    'transcribed_at': datetime.utcnow().isoformat() + 'Z',
                    'duration_seconds': deepgram_response.metadata.get('duration', 0),
                    'word_count': len(words),
                    'speakers_detected': len(unique_speakers),
                    'confidence': alternatives[0].get('confidence', 0) if alternatives else 0
                },
                'deepgram_response': {
                    'metadata': deepgram_response.metadata,
                    'results': deepgram_response.results
                }
            }
            
            # Ensure directory exists
            json_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write JSON file
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(comprehensive_data, f, indent=2, default=str)  # default=str handles datetime serialization
            logger.info(f"Saved comprehensive metadata to: {json_path}")
            
            # Step 3: Format as VTT (includes speaker mapping)
            logger.info("Step 3: Formatting transcript as VTT with speaker mapping and metadata")
            vtt_content = self.vtt_formatter.format_deepgram_response(
                deepgram_response.results, 
                episode=episode,
                deepgram_metadata=deepgram_response.metadata
            )
            
            # Step 4: Validate VTT
            logger.info("Step 4: Validating VTT content")
            is_valid, error_msg = self.vtt_formatter.validate_vtt(vtt_content)
            if not is_valid:
                raise ValueError(f"Invalid VTT content: {error_msg}")
            
            # Step 5: Save VTT file
            logger.info("Step 5: Saving VTT file")
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