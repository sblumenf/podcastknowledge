"""Main YouTube episode matcher that orchestrates the search process.

This module integrates query building, API searching, scoring, and validation
to find the best YouTube match for podcast episodes.
"""

import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from src.youtube_api_client import YouTubeAPIClient, YouTubeAPIError, QuotaExceededError
from src.youtube_query_builder import QueryBuilder
from src.youtube_match_scorer import MatchScorer
from src.config import Config
from src.utils.logging import get_logger

logger = get_logger('youtube_episode_matcher')


class NoConfidentMatchError(Exception):
    """Raised when no match meets the confidence threshold."""
    pass


class YouTubeEpisodeMatcher:
    """Orchestrates YouTube episode matching with multiple strategies."""
    
    def __init__(self, config: Config):
        """Initialize the episode matcher.
        
        Args:
            config: Application configuration
        """
        self.config = config
        
        # Initialize components
        self.api_client = YouTubeAPIClient(config.youtube_api.api_key)
        self.query_builder = QueryBuilder()
        self.match_scorer = MatchScorer(
            duration_tolerance=config.youtube_search.duration_tolerance
        )
        
        # Configuration
        self.confidence_threshold = config.youtube_api.confidence_threshold
        self.max_results_per_search = config.youtube_api.max_results_per_search
        self.search_quota_per_episode = config.youtube_api.search_quota_per_episode
        
        # Channel learning cache
        self.channel_cache_file = Path(config.output.default_dir) / ".channel_associations.json"
        self.channel_associations = self._load_channel_cache()
        
        # Metrics tracking
        self.metrics = {
            'searches_performed': 0,
            'matches_found': 0,
            'matches_above_threshold': 0,
            'quota_used': 0,
            'cache_hits': 0,
            'average_confidence': 0.0,
            'total_episodes': 0
        }
        
    async def match_episode(
        self,
        podcast_name: str,
        episode_title: str,
        episode_guid: Optional[str] = None,
        episode_number: Optional[int] = None,
        episode_duration: Optional[int] = None,
        episode_date: Optional[datetime] = None
    ) -> Optional[str]:
        """Find YouTube URL for a podcast episode.
        
        Args:
            podcast_name: Name of the podcast
            episode_title: Title of the episode
            episode_guid: Unique episode identifier
            episode_number: Episode number if available
            episode_duration: Duration in seconds
            episode_date: Publication date
            
        Returns:
            YouTube URL if confident match found, None otherwise
            
        Raises:
            YouTubeAPIError: If API errors occur
            QuotaExceededError: If quota is exceeded
        """
        self.metrics['total_episodes'] += 1
        
        logger.info(f"Searching for YouTube match: {podcast_name} - {episode_title}")
        
        # Get known channels for this podcast
        known_channels = self.channel_associations.get(podcast_name, [])
        if known_channels:
            logger.debug(f"Known channels for {podcast_name}: {known_channels}")
            self.metrics['cache_hits'] += 1
            
        # Build search queries
        queries = self.query_builder.build_queries(
            podcast_name,
            episode_title,
            episode_number
        )
        
        all_results = []
        quota_used = 0
        
        # Execute searches progressively
        for query, rank in queries:
            # Check quota budget
            if quota_used >= self.search_quota_per_episode:
                logger.warning(f"Reached quota limit for episode: {episode_title}")
                break
                
            try:
                # Search with the current query
                logger.debug(f"Searching with query (rank {rank}): {query}")
                
                results = await self._search_with_details(
                    query,
                    episode_date,
                    known_channels[0] if known_channels else None
                )
                
                self.metrics['searches_performed'] += 1
                quota_used += self.api_client.SEARCH_COST
                
                if results:
                    all_results.extend(results)
                    
                    # Score results after each search
                    scored_results = self.match_scorer.score_results(
                        all_results,
                        episode_title,
                        podcast_name,
                        episode_duration,
                        episode_date,
                        known_channels
                    )
                    
                    # Check if we have a confident match
                    if scored_results and scored_results[0][1] >= self.confidence_threshold:
                        best_match, confidence = scored_results[0]
                        logger.info(
                            f"Found confident match (score={confidence:.3f}): "
                            f"{best_match['title']}"
                        )
                        
                        # Learn channel association
                        self._learn_channel_association(
                            podcast_name,
                            best_match['channel_id'],
                            best_match['channel_title']
                        )
                        
                        # Update metrics
                        self.metrics['matches_found'] += 1
                        self.metrics['matches_above_threshold'] += 1
                        self._update_average_confidence(confidence)
                        self.metrics['quota_used'] += quota_used
                        
                        # Return YouTube URL
                        return f"https://www.youtube.com/watch?v={best_match['video_id']}"
                        
            except QuotaExceededError:
                logger.error("YouTube API quota exceeded")
                raise
            except YouTubeAPIError as e:
                logger.warning(f"Search failed for query '{query}': {e}")
                continue
                
        # No confident match found after all searches - try fallback strategies
        if not all_results or not scored_results or scored_results[0][1] < self.confidence_threshold:
            logger.info("Attempting fallback search strategies")
            
            # Fallback 1: Try broader search with just podcast and guest name
            if guest_name := self.query_builder._extract_guest_name(episode_title):
                try:
                    fallback_query = f'"{podcast_name}" "{guest_name}"'
                    logger.debug(f"Fallback search with guest name: {fallback_query}")
                    
                    fallback_results = await self._search_with_details(
                        fallback_query,
                        episode_date
                    )
                    
                    if fallback_results:
                        all_results.extend(fallback_results)
                        quota_used += self.api_client.SEARCH_COST
                        
                except YouTubeAPIError as e:
                    logger.warning(f"Fallback search failed: {e}")
                    
            # Fallback 2: Search channel's recent uploads if we know the channel
            if known_channels and quota_used < self.search_quota_per_episode:
                try:
                    await self._search_channel_uploads(
                        known_channels[0],
                        episode_title,
                        episode_date,
                        all_results
                    )
                    quota_used += self.api_client.SEARCH_COST
                    
                except YouTubeAPIError as e:
                    logger.warning(f"Channel uploads search failed: {e}")
                    
        # Final scoring with all results including fallbacks
        if all_results:
            scored_results = self.match_scorer.score_results(
                all_results,
                episode_title,
                podcast_name,
                episode_duration,
                episode_date,
                known_channels
            )
            
            if scored_results:
                best_match, confidence = scored_results[0]
                logger.info(
                    f"Best match after fallbacks (score={confidence:.3f}): "
                    f"{best_match['title']}"
                )
                self._update_average_confidence(confidence)
                
                # Accept lower confidence for fallback matches if still reasonable
                fallback_threshold = self.confidence_threshold * 0.85
                if confidence >= fallback_threshold:
                    logger.info(f"Accepting fallback match with adjusted threshold")
                    
                    # Learn channel if not known
                    if best_match['channel_id'] not in known_channels:
                        self._learn_channel_association(
                            podcast_name,
                            best_match['channel_id'],
                            best_match['channel_title']
                        )
                        
                    self.metrics['matches_found'] += 1
                    self.metrics['quota_used'] += quota_used
                    
                    return f"https://www.youtube.com/watch?v={best_match['video_id']}"
                    
        self.metrics['quota_used'] += quota_used
        logger.warning(f"No confident match found for: {episode_title}")
        return None
        
    async def _search_with_details(
        self,
        query: str,
        published_after: Optional[datetime] = None,
        channel_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search and enrich results with video details.
        
        Args:
            query: Search query
            published_after: Filter by publish date
            channel_id: Restrict to specific channel
            
        Returns:
            List of enriched search results
        """
        # Perform search
        results = self.api_client.search_videos(
            query=query,
            max_results=self.max_results_per_search,
            published_after=published_after,
            channel_id=channel_id
        )
        
        if not results:
            return []
            
        # Get video IDs for detail lookup
        video_ids = [r['video_id'] for r in results]
        
        # Get video details (duration, stats)
        details = self.api_client.get_video_details(video_ids)
        
        # Merge details into results
        details_map = {d['video_id']: d for d in details}
        
        for result in results:
            if result['video_id'] in details_map:
                result.update(details_map[result['video_id']])
                
        return results
        
    async def _search_channel_uploads(
        self,
        channel_id: str,
        episode_title: str,
        episode_date: Optional[datetime],
        existing_results: List[Dict[str, Any]]
    ) -> None:
        """Search a channel's recent uploads for the episode.
        
        Args:
            channel_id: YouTube channel ID
            episode_title: Episode title to match
            episode_date: Expected publication date
            existing_results: List to append new results to
        """
        # Extract key terms from episode title for searching
        key_terms = self.query_builder._extract_key_terms(
            self.query_builder._clean_title(episode_title)
        )
        
        if not key_terms:
            return
            
        # Search channel with key terms
        channel_query = ' '.join(key_terms[:3])
        logger.debug(f"Searching channel {channel_id} uploads with: {channel_query}")
        
        results = self.api_client.search_videos(
            query=channel_query,
            max_results=self.max_results_per_search,
            channel_id=channel_id,
            published_after=episode_date - timedelta(days=7) if episode_date else None
        )
        
        if results:
            # Get video details
            video_ids = [r['video_id'] for r in results]
            details = self.api_client.get_video_details(video_ids)
            
            # Merge details
            details_map = {d['video_id']: d for d in details}
            for result in results:
                if result['video_id'] in details_map:
                    result.update(details_map[result['video_id']])
                    
            # Add to existing results if not duplicate
            existing_ids = {r['video_id'] for r in existing_results}
            for result in results:
                if result['video_id'] not in existing_ids:
                    existing_results.append(result)
                    
    def _learn_channel_association(
        self,
        podcast_name: str,
        channel_id: str,
        channel_title: str
    ) -> None:
        """Learn and cache channel association for a podcast.
        
        Args:
            podcast_name: Name of the podcast
            channel_id: YouTube channel ID
            channel_title: YouTube channel title
        """
        if podcast_name not in self.channel_associations:
            self.channel_associations[podcast_name] = []
            
        # Add channel if not already known
        if channel_id not in self.channel_associations[podcast_name]:
            self.channel_associations[podcast_name].append(channel_id)
            logger.info(f"Learned channel association: {podcast_name} -> {channel_title}")
            
            # Save updated cache
            self._save_channel_cache()
            
    def _load_channel_cache(self) -> Dict[str, List[str]]:
        """Load channel associations from cache.
        
        Returns:
            Dictionary of podcast -> channel IDs
        """
        if not self.channel_cache_file.exists():
            return {}
            
        try:
            with open(self.channel_cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load channel cache: {e}")
            return {}
            
    def _save_channel_cache(self) -> None:
        """Save channel associations to cache."""
        try:
            self.channel_cache_file.parent.mkdir(exist_ok=True)
            with open(self.channel_cache_file, 'w') as f:
                json.dump(self.channel_associations, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save channel cache: {e}")
            
    def _update_average_confidence(self, confidence: float) -> None:
        """Update running average confidence score.
        
        Args:
            confidence: New confidence score
        """
        n = self.metrics['matches_found']
        if n == 0:
            self.metrics['average_confidence'] = confidence
        else:
            # Running average formula
            self.metrics['average_confidence'] = (
                (self.metrics['average_confidence'] * (n - 1) + confidence) / n
            )
            
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            **self.metrics,
            'quota_status': self.api_client.get_quota_status(),
            'known_podcast_channels': len(self.channel_associations),
            'success_rate': (
                self.metrics['matches_above_threshold'] / self.metrics['total_episodes']
                if self.metrics['total_episodes'] > 0 else 0.0
            )
        }
        
    def clear_channel_cache(self) -> None:
        """Clear the channel associations cache."""
        self.channel_associations = {}
        if self.channel_cache_file.exists():
            self.channel_cache_file.unlink()
        logger.info("Cleared channel associations cache")