"""Main Orchestrator for Podcast Transcription Pipeline.

This module coordinates all components of the transcription pipeline,
including checkpoint recovery and error handling.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

from src.feed_parser import parse_feed, Episode, PodcastMetadata
from src.progress_tracker import ProgressTracker, EpisodeStatus
from src.gemini_client import create_gemini_client, RateLimitedGeminiClient
from src.key_rotation_manager import KeyRotationManager, create_key_rotation_manager
from src.transcription_processor import TranscriptionProcessor
from src.speaker_identifier import SpeakerIdentifier
from src.vtt_generator import VTTGenerator, VTTMetadata
from src.youtube_searcher import YouTubeSearcher
from src.checkpoint_recovery import CheckpointManager
from src.retry_wrapper import QuotaExceededException, CircuitBreakerOpenException
from src.utils.logging import get_logger, log_progress
from src.utils.batch_progress import BatchProgressTracker
from src.config import Config
# New simplified workflow components
from src.transcript_analyzer import TranscriptAnalyzer
from src.continuation_manager import ContinuationManager
from src.transcript_stitcher import TranscriptStitcher
from src.text_to_vtt_converter import TextToVTTConverter

logger = get_logger('orchestrator')


class TranscriptionOrchestrator:
    """Orchestrates the complete podcast transcription pipeline."""
    
    def __init__(self, output_dir: Path = Path("data/transcripts"), 
                 enable_checkpoint: bool = True,
                 resume: bool = False,
                 data_dir: Optional[Path] = None,
                 config: Optional[Config] = None):
        """Initialize orchestrator.
        
        Args:
            output_dir: Directory for output VTT files
            enable_checkpoint: Enable checkpoint recovery
            resume: Resume from existing checkpoint if available
            data_dir: Base data directory (defaults to 'data')
            config: Optional configuration object. If not provided, creates default Config()
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize configuration
        self.config = config if config is not None else Config()
        
        # Initialize components
        # Use data directory for progress tracking
        if data_dir is None:
            data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        self.progress_tracker = ProgressTracker(data_dir / ".progress.json")
        self.key_manager = create_key_rotation_manager()
        self.gemini_client = create_gemini_client(self.key_manager)
        
        # Initialize checkpoint manager if enabled
        self.checkpoint_manager = CheckpointManager(data_dir) if enable_checkpoint else None
        
        # Initialize processors with checkpoint support
        self.transcription_processor = TranscriptionProcessor(
            self.gemini_client, self.key_manager, self.checkpoint_manager
        )
        self.speaker_identifier = SpeakerIdentifier(
            self.gemini_client, self.key_manager, self.checkpoint_manager
        )
        self.vtt_generator = VTTGenerator(self.checkpoint_manager)
        self.youtube_searcher = YouTubeSearcher(self.config)
        
        # Initialize new simplified workflow components
        self.transcript_analyzer = TranscriptAnalyzer()
        self.continuation_manager = ContinuationManager(
            self.gemini_client, 
            max_attempts=self.config.validation.max_continuation_attempts
        )
        self.transcript_stitcher = TranscriptStitcher()
        self.text_to_vtt_converter = TextToVTTConverter()
        
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
            logger.info(f"Found {len(episodes)} episodes in feed: {podcast_metadata.title}")
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
        
        # Initialize batch progress tracker
        batch_tracker = BatchProgressTracker(self.progress_tracker, len(pending_episodes))
        batch_tracker.start_batch()
        
        # Process episodes sequentially
        results = {
            'status': 'completed',
            'processed': 0,
            'failed': 0,
            'skipped': 0,
            'episodes': []
        }
        
        i = 0
        while i < len(pending_episodes):
            episode = pending_episodes[i]
            
            # Update current episode in progress tracker
            batch_tracker.update_current_episode(episode.title)
            
            # Check daily quota
            usage = self.gemini_client.get_usage_summary()
            total_requests = sum(key_data['requests_today'] for key_data in usage.values())
            
            if total_requests >= (len(self.gemini_client.api_keys) * 20):  # Conservative limit
                logger.warning("Approaching daily quota limit, stopping processing")
                results['status'] = 'quota_reached'
                results['skipped'] = len(pending_episodes) - i
                break
            
            # Prepare episode data for error handling
            episode_data = episode.to_dict()
            episode_data['podcast_name'] = podcast_metadata.title
            
            # Process episode
            try:
                episode_result = await self._process_episode(episode, podcast_metadata)
                results['episodes'].append(episode_result)
                
                if episode_result['status'] == 'completed':
                    results['processed'] += 1
                    # Calculate processing time for progress tracker
                    processing_time = episode_result.get('duration', 300.0)  # Default 5 minutes
                    batch_tracker.episode_completed(processing_time)
                elif episode_result['status'] == 'failed':
                    results['failed'] += 1
                    error_msg = episode_result.get('error', 'Unknown error')
                    batch_tracker.episode_failed(error_msg)
                elif episode_result['status'] == 'skipped':
                    results['skipped'] += 1
                    reason = episode_result.get('reason', 'Unknown reason')
                    batch_tracker.episode_skipped(reason)
                
                # Move to next episode
                i += 1
                    
            except QuotaExceededException as e:
                logger.warning(f"Quota exceeded during processing: {e}")
                
                # First, try to find another key with available quota
                if self.key_manager:
                    # Estimate tokens needed (rough estimate: 2000 tokens per minute of audio)
                    duration_seconds = 3600  # Default to 1 hour if unknown
                    if hasattr(episode, 'duration') and episode.duration:
                        # Parse duration string
                        try:
                            if ':' in str(episode.duration):
                                parts = str(episode.duration).split(':')
                                if len(parts) == 3:
                                    duration_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                                elif len(parts) == 2:
                                    duration_seconds = int(parts[0]) * 60 + int(parts[1])
                        except:
                            pass
                    
                    estimated_tokens = (duration_seconds / 60) * 2000
                    
                    # Try to get a key with available quota
                    alt_key = self.key_manager.get_available_key_for_quota(int(estimated_tokens))
                    
                    if alt_key:
                        logger.info(f"Switching to alternative API key with available quota")
                        # The gemini client will pick up the new key on next request
                        # Retry the current episode (don't increment i)
                        continue
                
                # No keys have quota, check if we should wait
                if self.config.processing.quota_wait_enabled:
                    # Update results to show we're waiting
                    results['status'] = 'quota_wait'
                    results['skipped'] = len(pending_episodes) - i
                    
                    # Wait for quota reset
                    wait_success = await self._wait_for_quota_reset()
                    
                    if wait_success:
                        # Reset quota tracking for all keys
                        if self.key_manager:
                            self.key_manager._daily_reset()
                        # Reset API client usage tracking
                        self.gemini_client._load_usage_state()
                        
                        # Continue processing remaining episodes
                        logger.info("Resuming processing after quota reset")
                        # Retry the current episode (don't increment i)
                        continue
                    else:
                        # Wait was interrupted or exceeded max time
                        results['status'] = 'quota_wait_failed'
                        break
                else:
                    # Quota wait disabled, skip remaining episodes including current one
                    results['status'] = 'quota_reached'
                    results['skipped'] = len(pending_episodes) - i  # Skip current and remaining episodes
                    break
        
        # Finish batch progress tracking
        status_message = results.get('status', 'completed')
        if status_message == 'completed':
            batch_tracker.finish_batch("All episodes processed successfully")
        elif status_message == 'quota_reached':
            batch_tracker.finish_batch("Processing stopped - quota limit reached")
        elif status_message == 'quota_wait_failed':
            batch_tracker.finish_batch("Processing stopped - quota wait failed")
        else:
            batch_tracker.finish_batch(f"Processing finished with status: {status_message}")
        
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
            # Parse published_date from string if present
            published_date_str = checkpoint.metadata.get('published_date')
            published_date = None
            if published_date_str:
                try:
                    published_date = datetime.fromisoformat(published_date_str.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    logger.warning(f"Failed to parse published_date: {published_date_str}")
            
            episode = Episode(
                guid=checkpoint.episode_id,
                title=checkpoint.title,
                audio_url=checkpoint.audio_url,
                published_date=published_date,
                description=checkpoint.metadata.get('description', ''),
                duration=checkpoint.metadata.get('duration', ''),
                author=checkpoint.metadata.get('author', '')
            )
            
            # Resume from appropriate stage
            if resume_stage == 'transcription':
                # Check if YouTube URL search was completed, if not, do it now
                if not checkpoint.metadata.get('youtube_url') and self.youtube_searcher.search_enabled:
                    logger.info("YouTube URL missing from checkpoint, running search before transcription")
                    await self._search_youtube_url(episode, checkpoint.metadata)
                
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
        episode_data['podcast_name'] = podcast_metadata.title
        
        # Search for YouTube URL if enabled
        if self.youtube_searcher.search_enabled:
            await self._search_youtube_url(episode, episode_data)
        
        # Start checkpoint
        if self.checkpoint_manager:
            self.checkpoint_manager.start_episode(
                episode.guid, episode.audio_url, episode.title, episode_data
            )
        
        return await self._process_episode_full(episode, episode_data)
    
    async def _search_youtube_url(self, episode: Episode, episode_data: Dict[str, Any]):
        """Search for YouTube URL for the episode.
        
        Args:
            episode: Episode to search for
            episode_data: Episode metadata dictionary to update
        """
        try:
            # Parse duration to seconds if available
            duration_seconds = None
            if episode.duration:
                # Try to parse duration string (e.g., "1:23:45" or "45:30")
                duration_parts = episode.duration.split(':')
                if len(duration_parts) == 3:  # hours:minutes:seconds
                    duration_seconds = int(duration_parts[0]) * 3600 + int(duration_parts[1]) * 60 + int(duration_parts[2])
                elif len(duration_parts) == 2:  # minutes:seconds
                    duration_seconds = int(duration_parts[0]) * 60 + int(duration_parts[1])
            
            youtube_url = await self.youtube_searcher.search_youtube_url(
                podcast_name=episode_data.get('podcast_name', ''),
                episode_title=episode.title,
                episode_description=episode.description,
                episode_number=episode.episode_number,
                duration_seconds=duration_seconds
            )
            
            if youtube_url:
                episode.youtube_url = youtube_url
                episode_data['youtube_url'] = youtube_url
                logger.info(f"Found YouTube URL for {episode.title}: {youtube_url}")
            else:
                episode_data['youtube_url'] = None
                logger.debug(f"No YouTube URL found for {episode.title}")
                
        except Exception as e:
            episode_data['youtube_url'] = None
            logger.warning(f"YouTube search failed for {episode.title}: {e}")
    
    async def _process_episode_full(self, episode: Episode, 
                                  episode_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process episode from start.
        
        Args:
            episode: Episode to process
            episode_data: Episode metadata
            
        Returns:
            Processing result
        """
        # Check if simplified workflow is enabled
        use_simplified_workflow = os.getenv('USE_SIMPLIFIED_WORKFLOW', 'false').lower() == 'true'
        
        if use_simplified_workflow:
            return await self._process_episode_simplified(episode, episode_data)
        else:
            return await self._process_episode_legacy(episode, episode_data)
    
    async def _process_episode_simplified(self, episode: Episode, 
                                        episode_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process episode using new simplified workflow.
        
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
                episode.guid, EpisodeStatus.IN_PROGRESS, episode_data
            )
            
            logger.info(f"Starting simplified transcription: {episode.title}")
            
            # Stage 1: Raw Transcription (using simplified prompt)
            if self.checkpoint_manager:
                self.checkpoint_manager.update_stage('raw_transcription')
            
            self.progress_tracker.update_workflow_stage(
                episode.guid, 'raw_transcription', 'simplified',
                {"step": "Initial transcription with simplified prompt"}
            )
            
            logger.info("Stage 1: Raw transcription with simple prompt")
            raw_transcript = await self.gemini_client.transcribe_audio(
                episode.audio_url, episode_data
            )
            
            if not raw_transcript:
                raise Exception("Raw transcription failed")
            
            # Stage 2: Coverage Analysis and Continuation Loop
            if self.checkpoint_manager:
                self.checkpoint_manager.update_stage('continuation_analysis')
            
            self.progress_tracker.update_workflow_stage(
                episode.guid, 'continuation_analysis', 'simplified',
                {"step": "Analyzing coverage and requesting continuations"}
            )
            
            logger.info("Stage 2: Coverage analysis and continuation")
            complete_transcript, continuation_info = await self.continuation_manager.ensure_complete_transcript(
                raw_transcript, 
                episode.audio_url, 
                episode_data,
                min_coverage=self.config.validation.min_coverage_ratio
            )
            
            # Store continuation info in episode data
            episode_data['_continuation_info'] = continuation_info
            
            # Update progress tracking with continuation results
            self.progress_tracker.update_continuation_progress(
                episode.guid,
                attempts=continuation_info.get('attempts', 0),
                coverage=continuation_info.get('final_coverage', 0.0),
                segments_count=continuation_info.get('segments_count', 1),
                consecutive_failures=continuation_info.get('consecutive_failures', 0),
                api_errors=continuation_info.get('api_errors', [])
            )
            
            # Check if episode should be failed based on continuation results
            if self.continuation_manager.should_fail_episode(continuation_info):
                failure_reason = self.continuation_manager.get_failure_reason(continuation_info)
                logger.error(f"Episode failed continuation requirements: {failure_reason}")
                
                # Update failure tracking
                self.progress_tracker.update_failure_info(
                    episode.guid, 
                    continuation_info.get('failure_type', 'coverage_failure'),
                    failure_reason
                )
                
                self.progress_tracker.update_episode_state(
                    episode.guid, EpisodeStatus.FAILED, episode_data,
                    error=failure_reason
                )
                if self.checkpoint_manager:
                    self.checkpoint_manager.mark_failed(failure_reason)
                
                return {
                    'episode_id': episode.guid,
                    'title': episode.title,
                    'status': 'failed',
                    'error': failure_reason,
                    'workflow': 'simplified',
                    'failure_type': continuation_info.get('failure_type', 'coverage_failure'),
                    'continuation_info': continuation_info,
                    'duration': (datetime.now() - start_time).total_seconds()
                }
            
            # Stage 3: Transcript Stitching (if multiple segments)
            if self.checkpoint_manager:
                self.checkpoint_manager.update_stage('transcript_stitching')
            
            logger.info("Stage 3: Transcript stitching")
            # Note: continuation_manager already handles stitching internally
            final_raw_transcript = complete_transcript
            
            # Stage 4: Text-to-VTT Conversion
            if self.checkpoint_manager:
                self.checkpoint_manager.update_stage('vtt_conversion')
            
            self.progress_tracker.update_workflow_stage(
                episode.guid, 'vtt_conversion', 'simplified',
                {"step": "Converting raw transcript to WebVTT format"}
            )
            
            logger.info("Stage 4: Converting raw transcript to VTT format")
            vtt_content = self.text_to_vtt_converter.convert(final_raw_transcript, episode_data)
            
            if not vtt_content:
                raise Exception("VTT conversion failed")
            
            # Stage 5: Save VTT File
            self.progress_tracker.update_workflow_stage(
                episode.guid, 'vtt_save', 'simplified',
                {"step": "Saving VTT file to disk"}
            )
            
            output_path = self._generate_output_path(episode_data)
            success = self.text_to_vtt_converter.save_vtt_file(vtt_content, output_path)
            
            if not success:
                raise Exception(f"Failed to save VTT file to {output_path}")
            
            # Update progress tracker
            self.progress_tracker.update_episode_state(
                episode.guid, EpisodeStatus.COMPLETED, episode_data,
                output_file=str(output_path),
                continuation_info=continuation_info
            )
            
            if self.checkpoint_manager:
                self.checkpoint_manager.mark_completed()
            
            logger.info(f"Simplified workflow completed: {output_path}")
            logger.info(f"Continuation attempts: {continuation_info.get('attempts', 0)}, "
                       f"final coverage: {continuation_info.get('final_coverage', 0):.1%}")
            
            return {
                'episode_id': episode.guid,
                'title': episode.title,
                'status': 'completed',
                'output_file': str(output_path),
                'workflow': 'simplified',
                'continuation_info': continuation_info,
                'duration': (datetime.now() - start_time).total_seconds()
            }
            
        except QuotaExceededException as e:
            logger.warning(f"Quota exceeded for episode: {e}")
            raise
        
        except CircuitBreakerOpenException as e:
            logger.error(f"Circuit breaker open for episode: {e}")
            self.progress_tracker.update_episode_state(
                episode.guid, EpisodeStatus.FAILED, episode_data,
                error=str(e)
            )
            if self.checkpoint_manager:
                self.checkpoint_manager.mark_failed(str(e))
            
            return {
                'episode_id': episode.guid,
                'title': episode.title,
                'status': 'skipped',
                'reason': 'circuit_breaker_open',
                'error': str(e)
            }
        
        except Exception as e:
            logger.error(f"Simplified episode processing failed: {e}")
            self.progress_tracker.update_episode_state(
                episode.guid, EpisodeStatus.FAILED, episode_data,
                error=str(e)
            )
            if self.checkpoint_manager:
                self.checkpoint_manager.mark_failed(str(e))
            
            return {
                'episode_id': episode.guid,
                'title': episode.title,
                'status': 'failed',
                'error': str(e),
                'workflow': 'simplified',
                'duration': (datetime.now() - start_time).total_seconds()
            }
    
    async def _process_episode_legacy(self, episode: Episode, 
                                    episode_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process episode using legacy workflow.
        
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
                episode.guid, EpisodeStatus.IN_PROGRESS, episode_data
            )
            
            # Stage 1: Transcription
            if self.checkpoint_manager:
                self.checkpoint_manager.update_stage('transcription')
            
            logger.info(f"Transcribing: {episode.title}")
            # Convert validation config to dict for passing to processor
            validation_config = {
                'enabled': self.config.validation.enabled,
                'min_coverage_ratio': self.config.validation.min_coverage_ratio,
                'max_continuation_attempts': self.config.validation.max_continuation_attempts
            }
            transcript = await self.transcription_processor.transcribe_episode(
                episode.audio_url, episode_data, validation_config
            )
            
            if not transcript:
                raise Exception("Transcription failed")
            
            # Continue with speaker identification
            return await self._process_from_speaker_id(episode, episode_data, transcript)
            
        except QuotaExceededException as e:
            logger.warning(f"Quota exceeded for episode: {e}")
            
            # Always raise the exception to be handled at the process_feed level
            # This allows the batch processing to stop properly when quota is exceeded
            raise
        
        except CircuitBreakerOpenException as e:
            logger.error(f"Circuit breaker open for episode: {e}")
            self.progress_tracker.update_episode_state(
                episode.guid, EpisodeStatus.FAILED, episode_data,
                error=str(e)
            )
            if self.checkpoint_manager:
                self.checkpoint_manager.mark_failed(str(e))
            
            return {
                'episode_id': episode.guid,
                'title': episode.title,
                'status': 'skipped',
                'reason': 'circuit_breaker_open',
                'error': str(e)
            }
        
        except Exception as e:
            logger.error(f"Episode processing failed: {e}")
            self.progress_tracker.update_episode_state(
                episode.guid, EpisodeStatus.FAILED, episode_data,
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
            
            # Update progress tracker with continuation info if available
            continuation_info = episode_data.get('_continuation_info')
            self.progress_tracker.update_episode_state(
                episode.guid, EpisodeStatus.COMPLETED, episode_data,
                output_file=str(output_path),
                continuation_info=continuation_info
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
                episode.guid, EpisodeStatus.FAILED, episode_data,
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
            # Check if episode is in progress tracker
            episode_progress = self.progress_tracker.state.episodes.get(episode.guid)
            
            # If not tracked or pending/failed, add to pending list
            if (episode_progress is None or 
                episode_progress.status in [EpisodeStatus.PENDING, EpisodeStatus.FAILED]):
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
            'podcast': podcast_metadata.title,
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
        report_file = self.output_dir / f"{podcast_metadata.title}_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Summary report saved to: {report_file}")
    
    async def _wait_for_quota_reset(self) -> bool:
        """Wait for API quota to reset.
        
        Returns:
            True if wait completed successfully, False if interrupted
        """
        # Calculate wait time until midnight Pacific Time (quota reset time)
        from datetime import timezone
        now = datetime.now(timezone.utc)
        
        # Gemini uses Pacific Time for quota reset (UTC-8 or UTC-7 for DST)
        # For simplicity, use UTC-8
        pacific_tz = timezone(timedelta(hours=-8))
        pacific_now = now.astimezone(pacific_tz)
        
        # Calculate time until midnight Pacific
        midnight = pacific_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        wait_seconds = (midnight - pacific_now).total_seconds()
        
        # Add a small buffer to ensure quota has reset
        wait_seconds += 300  # 5 minute buffer
        
        # Check max wait time
        max_wait_seconds = self.config.processing.max_quota_wait_hours * 3600
        if wait_seconds > max_wait_seconds:
            logger.warning(
                f"Wait time ({wait_seconds/3600:.1f} hours) exceeds maximum "
                f"({self.config.processing.max_quota_wait_hours} hours)"
            )
            return False
        
        wait_hours = wait_seconds / 3600
        logger.info(f"Waiting {wait_hours:.1f} hours for quota reset at midnight Pacific Time")
        
        # Wait with periodic progress updates
        check_interval = self.config.processing.quota_check_interval_minutes * 60
        elapsed = 0
        
        while elapsed < wait_seconds:
            # Calculate remaining time
            remaining = wait_seconds - elapsed
            remaining_hours = remaining / 3600
            
            # Log progress
            if elapsed > 0:
                logger.info(
                    f"Quota wait progress: {elapsed/3600:.1f} hours elapsed, "
                    f"{remaining_hours:.1f} hours remaining"
                )
            
            # Sleep for interval or remaining time, whichever is less
            sleep_time = min(check_interval, remaining)
            
            try:
                await asyncio.sleep(sleep_time)
                elapsed += sleep_time
            except asyncio.CancelledError:
                logger.warning("Quota wait interrupted")
                return False
        
        logger.info("Quota wait completed, resuming processing")
        return True
    
    def cleanup_old_data(self, days: int = 7):
        """Clean up old checkpoint and progress data.
        
        Args:
            days: Keep data newer than this many days
        """
        if self.checkpoint_manager:
            self.checkpoint_manager.cleanup_old_checkpoints(days)
            logger.info("Cleaned up old checkpoints")
        
        # Could also clean up old progress data if needed
    
    def _generate_output_path(self, episode_data: Dict[str, Any]) -> Path:
        """Generate output path for VTT file.
        
        Args:
            episode_data: Episode metadata
            
        Returns:
            Path for the output VTT file
        """
        # Create safe filename from episode title
        title = episode_data.get('title', 'Unknown_Episode')
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title.replace(' ', '_')[:100]  # Limit length
        
        # Create podcast subdirectory
        podcast_name = episode_data.get('podcast_name', 'Unknown_Podcast')
        safe_podcast = "".join(c for c in podcast_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_podcast = safe_podcast.replace(' ', '_')[:50]
        
        podcast_dir = self.output_dir / safe_podcast
        podcast_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate VTT filename
        filename = f"{safe_title}.vtt"
        return podcast_dir / filename