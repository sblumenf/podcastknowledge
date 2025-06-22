"""Speaker identification service for VTT transcript processing."""

import logging
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter, defaultdict
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path

from src.core.interfaces import TranscriptSegment
from src.extraction.prompts import PromptBuilder, PromptTemplate
from src.extraction.speaker_database import SpeakerDatabase
from src.extraction.speaker_metrics import SpeakerIdentificationMetrics
from src.services.llm_gemini_direct import GeminiDirectService
from src.utils.retry import ExponentialBackoff
from src.monitoring import get_pipeline_metrics

logger = logging.getLogger(__name__)


class SpeakerIdentifier:
    """Service for identifying speakers from VTT transcript segments."""
    
    def __init__(self, 
                 llm_service: GeminiDirectService,
                 confidence_threshold: float = 0.7,
                 use_large_context: bool = True,
                 timeout_seconds: int = 120,
                 max_segments_for_context: int = 50,
                 speaker_db_path: Optional[str] = None):
        """
        Initialize speaker identification service.
        
        Args:
            llm_service: Gemini Direct service for LLM calls
            confidence_threshold: Minimum confidence for speaker identification
            use_large_context: Whether to use large context prompts
            timeout_seconds: Maximum time for LLM call (default: 120s)
            max_segments_for_context: Maximum segments to include in context (default: 50)
            speaker_db_path: Optional path for persistent speaker database
        """
        self.llm_service = llm_service
        self.confidence_threshold = confidence_threshold
        self.prompt_builder = PromptBuilder(use_large_context)
        self.backoff = ExponentialBackoff(base=2.0, max_delay=30.0)
        self.timeout_seconds = timeout_seconds
        self.max_segments_for_context = max_segments_for_context
        
        # Speaker database for caching
        self.speaker_db = SpeakerDatabase(cache_dir=speaker_db_path)
        
        # Metrics tracking
        self.metrics = get_pipeline_metrics()
        
        # Speaker-specific metrics
        metrics_dir = Path(speaker_db_path) / "metrics" if speaker_db_path else None
        self.speaker_metrics = SpeakerIdentificationMetrics(metrics_dir=metrics_dir)
        
        # Error tracking
        self.error_counts = defaultdict(int)
        
        # Cache statistics
        self.cache_hits = 0
        self.cache_attempts = 0
        
    def identify_speakers(self, 
                         segments: List[TranscriptSegment], 
                         metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Identify speakers from transcript segments using LLM analysis.
        
        Args:
            segments: List of transcript segments with generic speaker labels
            metadata: Episode metadata (podcast name, title, description, episode_id)
            cached_content_name: Optional cached episode content name
            
        Returns:
            Dict containing:
                - speaker_mappings: Dict mapping generic IDs to identified names
                - confidence_scores: Confidence for each identification
                - identification_methods: How each speaker was identified
                - stats: Speaker statistics used for identification
                - errors: List of any errors encountered
                - performance: Performance metrics
        """
        start_time = time.time()
        errors = []
        
        if not segments:
            logger.warning("No segments provided for speaker identification")
            return self._create_empty_response()
            
        # Validate input size
        if len(segments) > 10000:  # Safeguard for extremely long transcripts
            logger.warning(f"Transcript too long ({len(segments)} segments), truncating context")
            errors.append(f"Truncated context from {len(segments)} to {self.max_segments_for_context} segments")
            
        # Calculate speaker statistics
        stats = self._calculate_speaker_statistics(segments)
        
        # Check if identification is worthwhile
        if len(stats) == 0:
            logger.info("No speakers found in segments")
            return self._create_empty_response()
        elif len(stats) == 1:
            logger.info("Only one speaker found, skipping identification")
            return self._create_single_speaker_response(stats)
            
        # DISABLED: Speaker cache causes cross-episode contamination
        # Each episode should identify its own speakers independently
        # This prevents guests from one episode appearing in all episodes
        
        # Original cache code commented out for reference:
        # podcast_name = metadata.get('podcast_name', '')
        # if podcast_name:
        #     ... cache lookup logic ...
        
        # Instead, always use LLM for fresh identification
        logger.info("Speaker cache disabled - using LLM for fresh identification")
            
        # Prepare context for LLM
        context = self._prepare_context(segments, metadata, stats)
        
        # Get speaker identification from LLM with timeout
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    self._call_llm_for_identification,
                    context['metadata'],
                    context['speaker_stats'],
                    context['opening_segments']
                )
                
                try:
                    llm_response = future.result(timeout=self.timeout_seconds)
                except TimeoutError:
                    logger.error(f"Speaker identification timed out after {self.timeout_seconds}s")
                    self.error_counts['timeout'] += 1
                    errors.append(f"LLM call timed out after {self.timeout_seconds}s")
                    
                    # Record timeout metric
                    # TODO: Fix metrics recording
                    # self.metrics.record_error('speaker_identification_timeout')
                    self.speaker_metrics.record_error('timeout', podcast_name)
                    
                    fallback_result = self._create_fallback_response(stats, errors)
                    
                    # Record in speaker metrics
                    self.speaker_metrics.record_identification(
                        podcast_name, fallback_result, time.time() - start_time
                    )
                    
                    return fallback_result
            
            # Parse and validate response
            identification_result = self._parse_llm_response(llm_response)
            
            # Add statistics to result
            identification_result['stats'] = stats
            
            # Apply confidence threshold
            identification_result = self._apply_confidence_threshold(identification_result)
            
            # Add performance metrics
            identification_result['performance'] = {
                'duration_seconds': time.time() - start_time,
                'segments_processed': len(segments),
                'speakers_identified': len(identification_result.get('speaker_mappings', {})),
                'cache_hit': False
            }
            
            # Add any errors encountered
            if errors:
                identification_result['errors'] = errors
                
            # DISABLED: Speaker cache storage to prevent cross-episode contamination
            # Each episode should maintain its own unique speakers
            # This prevents building up a shared cache that applies to all episodes
            
            # Original cache storage code commented out:
            # if podcast_name and identification_result.get('speaker_mappings'):
            #     ... store_speakers logic ...
            
            logger.info("Speaker cache storage disabled - each episode identifies speakers independently")
                
            # Record success metric
            # TODO: Fix metrics recording
            # self.metrics.record_success('speaker_identification')
            
            # Record in speaker metrics
            self.speaker_metrics.record_identification(
                podcast_name, identification_result, time.time() - start_time
            )
            
            return identification_result
            
        except Exception as e:
            logger.error(f"Speaker identification failed: {e}", exc_info=True)
            self.error_counts[type(e).__name__] += 1
            errors.append(f"LLM processing failed: {str(e)}")
            
            # Record error metric
            # TODO: Fix metrics recording
            # self.metrics.record_error('speaker_identification_error')
            self.speaker_metrics.record_error(type(e).__name__, podcast_name)
            
            # Return generic fallback
            fallback_result = self._create_fallback_response(stats, errors)
            
            # Record in speaker metrics
            self.speaker_metrics.record_identification(
                podcast_name, fallback_result, time.time() - start_time
            )
            
            return fallback_result
    
    def _calculate_speaker_statistics(self, segments: List[TranscriptSegment]) -> Dict[str, Any]:
        """
        Calculate speaking statistics for each speaker.
        
        Args:
            segments: List of transcript segments
            
        Returns:
            Dict with speaker statistics including:
                - speaking_time: Total seconds spoken
                - turn_count: Number of speaking turns
                - avg_turn_length: Average words per turn
                - first_appearance: First segment index
                - word_count: Total words spoken
        """
        stats = defaultdict(lambda: {
            'speaking_time': 0.0,
            'turn_count': 0,
            'word_count': 0,
            'first_appearance': float('inf'),
            'segments': []
        })
        
        for i, segment in enumerate(segments):
            speaker = segment.speaker or "Unknown"
            
            # Calculate speaking time
            duration = segment.end_time - segment.start_time
            stats[speaker]['speaking_time'] += duration
            
            # Count turns and words
            stats[speaker]['turn_count'] += 1
            stats[speaker]['word_count'] += len(segment.text.split())
            
            # Track first appearance
            if i < stats[speaker]['first_appearance']:
                stats[speaker]['first_appearance'] = i
                
            # Store segment indices for context
            stats[speaker]['segments'].append(i)
        
        # Calculate derived statistics
        for speaker, data in stats.items():
            data['avg_turn_length'] = (
                data['word_count'] / data['turn_count'] 
                if data['turn_count'] > 0 else 0
            )
            data['speaking_percentage'] = (
                data['speaking_time'] / sum(s.end_time - s.start_time for s in segments) * 100
                if segments else 0
            )
            
        return dict(stats)
    
    def _prepare_context(self, 
                        segments: List[TranscriptSegment], 
                        metadata: Dict[str, Any],
                        stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare context for LLM speaker identification.
        
        Args:
            segments: List of transcript segments
            metadata: Episode metadata
            stats: Speaker statistics
            
        Returns:
            Dict with formatted context for LLM
        """
        # Format metadata
        formatted_metadata = {
            'podcast_name': metadata.get('podcast_name', 'Unknown Podcast'),
            'episode_title': metadata.get('episode_title', 'Unknown Episode'),
            'description': metadata.get('description', ''),
            'date': metadata.get('date', ''),
            'duration': metadata.get('duration', '')
        }
        
        # Format speaker statistics
        formatted_stats = {}
        for speaker, data in stats.items():
            formatted_stats[speaker] = {
                'speaking_time': f"{data['speaking_time']:.1f}s",
                'speaking_percentage': f"{data['speaking_percentage']:.1f}%",
                'turn_count': data['turn_count'],
                'avg_words_per_turn': int(data['avg_turn_length']),
                'first_appears_at': f"{segments[data['first_appearance']].start_time:.1f}s"
            }
        
        # Get opening conversation (first 10 minutes or max_segments_for_context)
        opening_segments = []
        segment_limit = min(self.max_segments_for_context, len(segments))
        
        for segment in segments[:segment_limit]:
            if segment.start_time > 600:  # 10 minutes
                break
            opening_segments.append({
                'speaker': segment.speaker,
                'time': f"{int(segment.start_time // 60)}:{int(segment.start_time % 60):02d}",
                'text': segment.text[:200] + '...' if len(segment.text) > 200 else segment.text
            })
        
        return {
            'metadata': json.dumps(formatted_metadata, indent=2),
            'speaker_stats': json.dumps(formatted_stats, indent=2),
            'opening_segments': json.dumps(opening_segments, indent=2)
        }
    
    def _call_llm_for_identification(self,
                                   metadata: str,
                                   speaker_stats: str,
                                   opening_segments: str) -> str:
        """
        Call LLM for speaker identification.
        
        Args:
            metadata: Formatted metadata JSON string
            speaker_stats: Formatted speaker statistics JSON string
            opening_segments: Formatted opening segments JSON string
            cached_content_name: Optional cached content name
            
        Returns:
            LLM response text
        """
        # Get the speaker identification prompt template
        template = self.prompt_builder.get_template('speaker_identification')
        
        # Format the prompt
        prompt = template.format(
            metadata=metadata,
            speaker_stats=speaker_stats,
            opening_segments=opening_segments
        )
        
        # Make LLM call with retry logic
        self.backoff.reset()
        last_exception = None
        
        for attempt in range(3):
            try:
                # Use JSON mode for reliable speaker identification responses
                response_data = self.llm_service.complete_with_options(
                    prompt,
                    json_mode=True
                )
                return response_data['content']
                
            except Exception as e:
                last_exception = e
                if attempt < 2:
                    delay = self.backoff.get_next_delay()
                    logger.warning(f"LLM call failed on attempt {attempt + 1}, retrying in {delay}s: {e}")
                    import time
                    time.sleep(delay)
                    
        raise Exception(f"Speaker identification LLM call failed after 3 attempts: {last_exception}")
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parse and validate LLM response.
        
        Args:
            response: Raw LLM response text
            
        Returns:
            Parsed identification result
        """
        try:
            # Extract JSON from response
            # Handle potential markdown code blocks
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]
                
            # Parse JSON
            result = json.loads(response.strip())
            
            # Validate required fields
            required_fields = ['speaker_mappings', 'confidence_scores', 
                             'identification_methods', 'unresolved_speakers']
            
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")
                    
            # Ensure all mapped speakers have confidence scores
            for speaker_id in result['speaker_mappings']:
                if speaker_id not in result['confidence_scores']:
                    result['confidence_scores'][speaker_id] = 0.5  # Default confidence
                    
            return result
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Raw response: {response[:500]}...")
            
            # Return empty result on parse failure
            return {
                'speaker_mappings': {},
                'confidence_scores': {},
                'identification_methods': {},
                'unresolved_speakers': []
            }
    
    def _apply_confidence_threshold(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply confidence threshold to speaker identifications.
        
        Args:
            result: Identification result from LLM
            
        Returns:
            Result with low-confidence identifications moved to descriptive roles
        """
        updated_mappings = {}
        updated_methods = {}
        
        for speaker_id, identified_name in result['speaker_mappings'].items():
            confidence = result['confidence_scores'].get(speaker_id, 0.0)
            
            if confidence >= self.confidence_threshold:
                # Keep high-confidence identification
                updated_mappings[speaker_id] = identified_name
                updated_methods[speaker_id] = result['identification_methods'].get(
                    speaker_id, "LLM identification"
                )
            else:
                # Convert to descriptive role
                stats = result.get('stats', {}).get(speaker_id, {})
                speaking_pct = stats.get('speaking_percentage', 0)
                
                if speaking_pct > 40:
                    role = "Primary Speaker"
                elif speaking_pct > 20:
                    role = "Co-host/Major Guest"
                elif speaking_pct > 5:
                    role = "Guest/Contributor"
                else:
                    role = "Brief Contributor"
                    
                updated_mappings[speaker_id] = f"{role} ({speaker_id})"
                updated_methods[speaker_id] = f"Low confidence ({confidence:.2f}), assigned role"
                
                # Add to unresolved speakers if not already there
                if speaker_id not in result.get('unresolved_speakers', []):
                    result['unresolved_speakers'] = result.get('unresolved_speakers', []) + [speaker_id]
        
        result['speaker_mappings'] = updated_mappings
        result['identification_methods'] = updated_methods
        
        return result
    
    def _create_empty_response(self) -> Dict[str, Any]:
        """
        Create empty response when no segments provided.
        
        Returns:
            Empty identification result
        """
        return {
            'speaker_mappings': {},
            'confidence_scores': {},
            'identification_methods': {},
            'unresolved_speakers': [],
            'stats': {},
            'errors': ['No segments provided']
        }
    
    def _create_single_speaker_response(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create response for single speaker podcasts.
        
        Args:
            stats: Speaker statistics
            
        Returns:
            Simple identification result for single speaker
        """
        speaker_id = list(stats.keys())[0]
        return {
            'speaker_mappings': {speaker_id: "Host/Narrator"},
            'confidence_scores': {speaker_id: 0.9},
            'identification_methods': {speaker_id: "Single speaker podcast"},
            'unresolved_speakers': [],
            'stats': stats
        }
    
    def _create_fallback_response(self, stats: Dict[str, Any], errors: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Create fallback response when LLM identification fails.
        
        Args:
            stats: Speaker statistics
            errors: List of errors encountered
            
        Returns:
            Fallback identification result with descriptive roles
        """
        mappings = {}
        methods = {}
        confidence_scores = {}
        
        # Sort speakers by speaking time
        sorted_speakers = sorted(
            stats.items(), 
            key=lambda x: x[1]['speaking_percentage'],
            reverse=True
        )
        
        for i, (speaker_id, speaker_stats) in enumerate(sorted_speakers):
            speaking_pct = speaker_stats['speaking_percentage']
            
            if i == 0 and speaking_pct > 30:
                role = "Primary Host"
            elif i == 1 and speaking_pct > 20:
                role = "Co-host/Main Guest"
            elif speaking_pct > 10:
                role = f"Guest {i}"
            else:
                role = f"Contributor {i+1}"
                
            mappings[speaker_id] = f"{role} ({speaker_id})"
            methods[speaker_id] = "Fallback role assignment based on speaking time"
            confidence_scores[speaker_id] = 0.3  # Low confidence for fallback
        
        result = {
            'speaker_mappings': mappings,
            'confidence_scores': confidence_scores,
            'identification_methods': methods,
            'unresolved_speakers': list(stats.keys()),
            'stats': stats
        }
        
        if errors:
            result['errors'] = errors
            
        return result
    
    def _map_speakers(self, 
                     segments: List[TranscriptSegment], 
                     speaker_mappings: Dict[str, str]) -> List[TranscriptSegment]:
        """
        Apply identified speaker names to transcript segments.
        
        Args:
            segments: Original segments with generic speaker labels
            speaker_mappings: Mapping from generic IDs to identified names
            
        Returns:
            Updated segments with identified speaker names
        """
        updated_segments = []
        
        for segment in segments:
            # Create a copy of the segment
            updated_segment = TranscriptSegment(
                id=segment.id,
                text=segment.text,
                start_time=segment.start_time,
                end_time=segment.end_time,
                speaker=speaker_mappings.get(segment.speaker, segment.speaker),
                confidence=segment.confidence
            )
            
            # Add original speaker ID to metadata for traceability
            # if segment.speaker in speaker_mappings:
            #     if updated_segment.metadata is None:
            #         updated_segment.metadata = {}
            #     updated_segment.metadata['original_speaker_id'] = segment.speaker
                
            updated_segments.append(updated_segment)
            
        return updated_segments
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics for monitoring.
        
        Returns:
            Dict with error counts and rates
        """
        total_errors = sum(self.error_counts.values())
        
        return {
            'total_errors': total_errors,
            'error_counts': dict(self.error_counts),
            'timeout_rate': self.error_counts.get('timeout', 0) / max(1, total_errors),
            'parse_error_rate': self.error_counts.get('JSONDecodeError', 0) / max(1, total_errors)
        }
    
    def reset_error_statistics(self):
        """Reset error statistics."""
        self.error_counts.clear()
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        Get cache performance statistics.
        
        Returns:
            Dict with cache statistics
        """
        cache_hit_rate = (
            self.cache_hits / self.cache_attempts 
            if self.cache_attempts > 0 else 0.0
        )
        
        return {
            'cache_hits': self.cache_hits,
            'cache_attempts': self.cache_attempts,
            'cache_hit_rate': round(cache_hit_rate, 3),
            'database_stats': self.speaker_db.get_statistics()
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive performance metrics.
        
        Returns:
            Dict with all performance metrics
        """
        return {
            'cache_stats': self.get_cache_statistics(),
            'error_stats': self.get_error_statistics(),
            'speaker_metrics': self.speaker_metrics.get_summary(),
            'config': {
                'confidence_threshold': self.confidence_threshold,
                'timeout_seconds': self.timeout_seconds,
                'max_segments_for_context': self.max_segments_for_context,
                'use_large_context': self.prompt_builder.use_large_context
            }
        }
    
    def generate_metrics_report(self, output_path: Optional[str] = None) -> str:
        """
        Generate a comprehensive metrics report.
        
        Args:
            output_path: Optional path to save report
            
        Returns:
            Report as string
        """
        return self.speaker_metrics.generate_report(
            Path(output_path) if output_path else None
        )