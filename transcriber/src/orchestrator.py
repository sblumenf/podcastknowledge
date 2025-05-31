"""Main Orchestrator for Podcast Transcription Pipeline.

This module coordinates all components of the transcription pipeline,
including checkpoint recovery and error handling.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from feed_parser import parse_feed, Episode, PodcastMetadata
from progress_tracker import ProgressTracker, EpisodeState
from gemini_client import create_gemini_client, RateLimitedGeminiClient
from key_rotation_manager import KeyRotationManager
from transcription_processor import TranscriptionProcessor
from speaker_identifier import SpeakerIdentifier
from vtt_generator import VTTGenerator, VTTMetadata
from checkpoint_recovery import CheckpointManager
from retry_wrapper import QuotaExceededException, CircuitBreakerOpenException
from utils.logging import get_logger, log_progress

logger = get_logger('orchestrator')


class TranscriptionOrchestrator:
    """Orchestrates the complete podcast transcription pipeline."""
    
    def __init__(self, output_dir: Path = Path("data/transcripts"), 
                 enable_checkpoint: bool = True,
                 resume: bool = False):
        """Initialize orchestrator.
        
        Args:
            output_dir: Directory for output VTT files
            enable_checkpoint: Enable checkpoint recovery
            resume: Resume from existing checkpoint if available
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.progress_tracker = ProgressTracker()
        self.key_manager = KeyRotationManager()
        self.gemini_client = create_gemini_client()
        
        # Initialize checkpoint manager if enabled
        self.checkpoint_manager = CheckpointManager() if enable_checkpoint else None
        
        # Initialize processors with checkpoint support
        self.transcription_processor = TranscriptionProcessor(
            self.gemini_client, self.key_manager, self.checkpoint_manager
        )
        self.speaker_identifier = SpeakerIdentifier(
            self.gemini_client, self.key_manager, self.checkpoint_manager
        )
        self.vtt_generator = VTTGenerator(self.checkpoint_manager)
        
        # Check for resumable checkpoint
        self.resume_mode = resume
        if resume and self.checkpoint_manager and self.checkpoint_manager.can_resume():
            resume_info = self.checkpoint_manager.get_resume_info()
            logger.info(f"Found resumable checkpoint: {resume_info['episode_title']}")
            logger.info(f"Last updated {resume_info['hours_since_update']} hours ago")
    
    async def process_feed(self, rss_url: str, max_episodes: Optional[int] = None) -> Dict[str, Any]:
        """Process podcast RSS feed.
        
        Args:
            rss_url: URL of the RSS feed
            max_episodes: Maximum episodes to process (default 12)
            
        Returns:
            Processing results summary
        """
        # Default to 12 episodes (conservative for 2 API keys)
        if max_episodes is None:
            max_episodes = 12
        
        # Parse RSS feed
        try:
            podcast_metadata, episodes = parse_feed(rss_url)
            logger.info(f"Found {len(episodes)} episodes in feed: {podcast_metadata.name}")
        except Exception as e:
            logger.error(f"Failed to parse RSS feed: {e}")
            return {'status': 'failed', 'error': str(e)}
        
        # Check for checkpoint resume
        if self.resume_mode and self.checkpoint_manager and self.checkpoint_manager.can_resume():
            results = await self._resume_processing()
            if results:
                return results
        
        # Get pending episodes
        pending_episodes = self._get_pending_episodes(episodes, max_episodes)
        
        if not pending_episodes:
            logger.info("No pending episodes to process")
            return {
                'status': 'completed',
                'processed': 0,
                'message': 'All episodes already processed'
            }
        
        # Process episodes sequentially
        results = {
            'status': 'completed',
            'processed': 0,
            'failed': 0,
            'skipped': 0,
            'episodes': []
        }
        
        for i, episode in enumerate(pending_episodes):
            log_progress(i + 1, len(pending_episodes), f"Processing: {episode.title}")
            
            # Check daily quota
            usage = self.gemini_client.get_usage_summary()
            total_requests = sum(key_data['requests_today'] for key_data in usage.values())
            
            if total_requests >= (len(self.gemini_client.api_keys) * 20):  # Conservative limit
                logger.warning("Approaching daily quota limit, stopping processing")
                results['status'] = 'quota_reached'
                results['skipped'] = len(pending_episodes) - i
                break
            
            # Process episode
            episode_result = await self._process_episode(episode, podcast_metadata)
            results['episodes'].append(episode_result)
            
            if episode_result['status'] == 'completed':
                results['processed'] += 1
            elif episode_result['status'] == 'failed':
                results['failed'] += 1
            elif episode_result['status'] == 'skipped':
                results['skipped'] += 1
        
        # Generate summary report
        self._generate_summary_report(results, podcast_metadata)
        
        return results
    
    async def _resume_processing(self) -> Optional[Dict[str, Any]]:
        """Resume processing from checkpoint.
        
        Returns:
            Processing results or None if cannot resume
        """
        if not self.checkpoint_manager:
            return None
        
        resume_info = self.checkpoint_manager.resume_processing()
        if not resume_info:
            return None
        
        resume_stage, checkpoint_data = resume_info
        checkpoint = checkpoint_data['checkpoint']
        
        logger.info(f"Resuming episode: {checkpoint.title}")
        logger.info(f"Starting from stage: {resume_stage}")
        
        try:
            # Reconstruct episode data
            episode = Episode(
                guid=checkpoint.episode_id,
                title=checkpoint.title,
                audio_url=checkpoint.audio_url,
                publication_date=checkpoint.metadata.get('publication_date', ''),
                description=checkpoint.metadata.get('description', ''),
                duration=checkpoint.metadata.get('duration', ''),
                author=checkpoint.metadata.get('author', '')
            )
            
            # Resume from appropriate stage
            if resume_stage == 'transcription':
                # Need to redo transcription
                result = await self._process_episode_full(episode, checkpoint.metadata)
            elif resume_stage == 'speaker_identification':
                # Load transcript and continue
                transcript = checkpoint_data['temp_data'].get('transcription')
                if transcript:
                    result = await self._process_from_speaker_id(
                        episode, checkpoint.metadata, transcript
                    )
                else:
                    # Missing data, start over
                    result = await self._process_episode_full(episode, checkpoint.metadata)
            elif resume_stage == 'vtt_generation':
                # Load transcript and speaker mapping
                transcript = checkpoint_data['temp_data'].get('transcription')
                speaker_mapping_str = checkpoint_data['temp_data'].get('speaker_mapping')
                
                if transcript and speaker_mapping_str:
                    speaker_mapping = json.loads(speaker_mapping_str)
                    result = await self._process_from_vtt_gen(
                        episode, checkpoint.metadata, transcript, speaker_mapping
                    )
                else:
                    # Missing data, start over
                    result = await self._process_episode_full(episode, checkpoint.metadata)
            else:
                # Unknown stage, start over
                result = await self._process_episode_full(episode, checkpoint.metadata)
            
            return {
                'status': 'resumed',
                'processed': 1 if result['status'] == 'completed' else 0,
                'failed': 1 if result['status'] == 'failed' else 0,
                'skipped': 0,
                'episodes': [result]
            }
            
        except Exception as e:
            logger.error(f"Failed to resume processing: {e}")
            if self.checkpoint_manager:
                self.checkpoint_manager.mark_failed(str(e))
            return None
    
    async def _process_episode(self, episode: Episode, 
                             podcast_metadata: PodcastMetadata) -> Dict[str, Any]:
        """Process a single episode.
        
        Args:
            episode: Episode to process
            podcast_metadata: Podcast metadata
            
        Returns:
            Processing result for the episode
        """
        episode_data = episode.to_dict()
        episode_data['podcast_name'] = podcast_metadata.name
        
        # Start checkpoint
        if self.checkpoint_manager:
            self.checkpoint_manager.start_episode(
                episode.guid, episode.audio_url, episode.title, episode_data
            )
        
        return await self._process_episode_full(episode, episode_data)
    
    async def _process_episode_full(self, episode: Episode, 
                                  episode_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process episode from start.
        
        Args:
            episode: Episode to process
            episode_data: Episode metadata
            
        Returns:
            Processing result
        """
        start_time = datetime.now()
        
        try:
            # Update progress tracker
            self.progress_tracker.update_episode_state(
                episode.guid, EpisodeState.IN_PROGRESS, episode_data
            )
            
            # Stage 1: Transcription
            if self.checkpoint_manager:
                self.checkpoint_manager.update_stage('transcription')
            
            logger.info(f"Transcribing: {episode.title}")
            transcript = await self.transcription_processor.transcribe_episode(
                episode.audio_url, episode_data
            )
            
            if not transcript:
                raise Exception("Transcription failed")
            
            # Continue with speaker identification
            return await self._process_from_speaker_id(episode, episode_data, transcript)
            
        except (QuotaExceededException, CircuitBreakerOpenException) as e:
            logger.error(f"Cannot process episode due to limits: {e}")
            self.progress_tracker.update_episode_state(
                episode.guid, EpisodeState.FAILED, episode_data,
                error=str(e)
            )
            if self.checkpoint_manager:
                self.checkpoint_manager.mark_failed(str(e))
            
            return {
                'episode_id': episode.guid,
                'title': episode.title,
                'status': 'skipped',
                'reason': 'quota_exceeded',
                'error': str(e)
            }
        
        except Exception as e:
            logger.error(f"Episode processing failed: {e}")
            self.progress_tracker.update_episode_state(
                episode.guid, EpisodeState.FAILED, episode_data,
                error=str(e)
            )
            if self.checkpoint_manager:
                self.checkpoint_manager.mark_failed(str(e))
            
            return {
                'episode_id': episode.guid,
                'title': episode.title,
                'status': 'failed',
                'error': str(e),
                'duration': (datetime.now() - start_time).total_seconds()
            }
    
    async def _process_from_speaker_id(self, episode: Episode,
                                     episode_data: Dict[str, Any],
                                     transcript: str) -> Dict[str, Any]:
        """Process from speaker identification stage.
        
        Args:
            episode: Episode being processed
            episode_data: Episode metadata
            transcript: VTT transcript
            
        Returns:
            Processing result
        """
        try:
            # Stage 2: Speaker Identification
            if self.checkpoint_manager:
                self.checkpoint_manager.update_stage('speaker_identification')
            
            logger.info("Identifying speakers")
            speaker_mapping = await self.speaker_identifier.identify_speakers(
                transcript, episode_data
            )
            
            # Continue with VTT generation
            return await self._process_from_vtt_gen(
                episode, episode_data, transcript, speaker_mapping
            )
            
        except Exception as e:
            logger.error(f"Speaker identification failed: {e}")
            # Use transcript without speaker names
            speaker_mapping = {}
            return await self._process_from_vtt_gen(
                episode, episode_data, transcript, speaker_mapping
            )
    
    async def _process_from_vtt_gen(self, episode: Episode,
                                  episode_data: Dict[str, Any],
                                  transcript: str,
                                  speaker_mapping: Dict[str, str]) -> Dict[str, Any]:
        """Process from VTT generation stage.
        
        Args:
            episode: Episode being processed
            episode_data: Episode metadata
            transcript: VTT transcript
            speaker_mapping: Speaker identification results
            
        Returns:
            Processing result
        """
        start_time = datetime.now()
        
        try:
            # Stage 3: VTT Generation
            if self.checkpoint_manager:
                self.checkpoint_manager.update_stage('vtt_generation')
            
            logger.info("Generating final VTT file")
            
            # Apply speaker mapping
            if speaker_mapping:
                final_transcript = self.speaker_identifier.apply_speaker_mapping(
                    transcript, speaker_mapping
                )
            else:
                final_transcript = transcript
            
            # Generate VTT metadata
            vtt_metadata = self.vtt_generator.create_metadata_from_episode(
                episode_data, speaker_mapping
            )
            
            # Generate output path
            output_path = self.vtt_generator.generate_output_path(
                episode_data, self.output_dir
            )
            
            # Generate and save VTT file
            self.vtt_generator.generate_vtt(
                final_transcript, vtt_metadata, output_path
            )
            
            # Update progress tracker
            self.progress_tracker.update_episode_state(
                episode.guid, EpisodeState.COMPLETED, episode_data,
                output_file=str(output_path)
            )
            
            logger.info(f"Episode completed: {output_path}")
            
            return {
                'episode_id': episode.guid,
                'title': episode.title,
                'status': 'completed',
                'output_file': str(output_path),
                'speakers': list(speaker_mapping.values()) if speaker_mapping else [],
                'duration': (datetime.now() - start_time).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"VTT generation failed: {e}")
            self.progress_tracker.update_episode_state(
                episode.guid, EpisodeState.FAILED, episode_data,
                error=str(e)
            )
            if self.checkpoint_manager:
                self.checkpoint_manager.mark_failed(str(e))
            
            return {
                'episode_id': episode.guid,
                'title': episode.title,
                'status': 'failed',
                'error': str(e),
                'duration': (datetime.now() - start_time).total_seconds()
            }
    
    def _get_pending_episodes(self, episodes: List[Episode], 
                            max_episodes: int) -> List[Episode]:
        """Get list of pending episodes to process.
        
        Args:
            episodes: All episodes from feed
            max_episodes: Maximum to process
            
        Returns:
            List of pending episodes
        """
        pending = []
        
        for episode in episodes:
            state = self.progress_tracker.get_episode_state(episode.guid)
            if state in [None, EpisodeState.PENDING, EpisodeState.FAILED]:
                pending.append(episode)
                
                if len(pending) >= max_episodes:
                    break
        
        return pending
    
    def _generate_summary_report(self, results: Dict[str, Any], 
                               podcast_metadata: PodcastMetadata):
        """Generate summary report of processing.
        
        Args:
            results: Processing results
            podcast_metadata: Podcast metadata
        """
        report = {
            'podcast': podcast_metadata.name,
            'processing_date': datetime.now().isoformat(),
            'summary': {
                'total_processed': results['processed'],
                'successful': results['processed'],
                'failed': results['failed'],
                'skipped': results['skipped']
            },
            'episodes': results['episodes'],
            'api_usage': self.gemini_client.get_usage_summary()
        }
        
        # Save report
        report_file = self.output_dir / f"{podcast_metadata.name}_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Summary report saved to: {report_file}")
    
    def cleanup_old_data(self, days: int = 7):
        """Clean up old checkpoint and progress data.
        
        Args:
            days: Keep data newer than this many days
        """
        if self.checkpoint_manager:
            self.checkpoint_manager.cleanup_old_checkpoints(days)
            logger.info("Cleaned up old checkpoints")
        
        # Could also clean up old progress data if needed