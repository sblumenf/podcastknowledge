"""Scoring engine for YouTube search results.

This module scores and ranks YouTube search results to find the best match
for podcast episodes based on multiple factors.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import re

from src.utils.logging import get_logger

logger = get_logger('youtube_match_scorer')


class MatchScorer:
    """Scores YouTube search results for podcast episode matching."""
    
    # Scoring weights (must sum to 1.0)
    TITLE_WEIGHT = 0.40
    DURATION_WEIGHT = 0.30
    CHANNEL_WEIGHT = 0.20
    DATE_WEIGHT = 0.10
    
    def __init__(self, duration_tolerance: float = 0.10):
        """Initialize match scorer.
        
        Args:
            duration_tolerance: Tolerance for duration matching (default 10%)
        """
        self.duration_tolerance = duration_tolerance
        
    def score_results(
        self,
        results: List[Dict[str, Any]],
        episode_title: str,
        podcast_name: str,
        episode_duration: Optional[int] = None,
        episode_date: Optional[datetime] = None,
        known_channel_ids: Optional[List[str]] = None
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Score and rank search results.
        
        Args:
            results: List of search results from YouTube API
            episode_title: Title of the episode we're looking for
            podcast_name: Name of the podcast
            episode_duration: Expected duration in seconds
            episode_date: Publication date of the episode
            known_channel_ids: List of known channel IDs for this podcast
            
        Returns:
            List of (result, score) tuples sorted by score descending
        """
        scored_results = []
        
        for result in results:
            score = self._calculate_score(
                result,
                episode_title,
                podcast_name,
                episode_duration,
                episode_date,
                known_channel_ids or []
            )
            
            scored_results.append((result, score))
            
        # Sort by score descending
        scored_results.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"Scored {len(results)} results. Top score: {scored_results[0][1] if scored_results else 0:.3f}")
        
        return scored_results
        
    def _calculate_score(
        self,
        result: Dict[str, Any],
        episode_title: str,
        podcast_name: str,
        episode_duration: Optional[int],
        episode_date: Optional[datetime],
        known_channel_ids: List[str]
    ) -> float:
        """Calculate composite score for a single result.
        
        Args:
            result: YouTube search result
            episode_title: Title of the episode
            podcast_name: Name of the podcast
            episode_duration: Expected duration in seconds
            episode_date: Publication date
            known_channel_ids: Known channel IDs
            
        Returns:
            Composite score between 0.0 and 1.0
        """
        scores = {}
        
        # 1. Title similarity score
        scores['title'] = self._score_title_similarity(
            result.get('title', ''),
            episode_title,
            podcast_name
        )
        
        # 2. Duration score (if duration available)
        if episode_duration and 'duration_seconds' in result:
            scores['duration'] = self._score_duration_match(
                result['duration_seconds'],
                episode_duration
            )
        else:
            # If no duration info, use neutral score
            scores['duration'] = 0.5
            
        # 3. Channel verification score
        scores['channel'] = self._score_channel_match(
            result.get('channel_id', ''),
            result.get('channel_title', ''),
            podcast_name,
            known_channel_ids
        )
        
        # 4. Upload date proximity score
        if episode_date and 'published_at' in result:
            scores['date'] = self._score_date_proximity(
                result['published_at'],
                episode_date
            )
        else:
            # If no date info, use neutral score
            scores['date'] = 0.5
            
        # Calculate weighted composite score
        composite_score = (
            scores['title'] * self.TITLE_WEIGHT +
            scores['duration'] * self.DURATION_WEIGHT +
            scores['channel'] * self.CHANNEL_WEIGHT +
            scores['date'] * self.DATE_WEIGHT
        )
        
        # Log detailed scoring for debugging
        logger.debug(
            f"Scored '{result.get('title', 'Unknown')[:50]}...': "
            f"title={scores['title']:.2f}, duration={scores['duration']:.2f}, "
            f"channel={scores['channel']:.2f}, date={scores['date']:.2f}, "
            f"composite={composite_score:.3f}"
        )
        
        return composite_score
        
    def _score_title_similarity(
        self,
        video_title: str,
        episode_title: str,
        podcast_name: str
    ) -> float:
        """Score title similarity.
        
        Args:
            video_title: YouTube video title
            episode_title: Expected episode title
            podcast_name: Podcast name
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Normalize titles for comparison
        video_normalized = self._normalize_title(video_title)
        episode_normalized = self._normalize_title(episode_title)
        
        # Direct similarity
        direct_similarity = SequenceMatcher(None, video_normalized, episode_normalized).ratio()
        
        # Check if video title contains podcast name (good signal)
        podcast_normalized = self._normalize_title(podcast_name)
        has_podcast_name = podcast_normalized in video_normalized
        
        # Extract episode numbers and compare
        video_ep_num = self._extract_episode_number(video_title)
        episode_ep_num = self._extract_episode_number(episode_title)
        
        episode_number_match = 0.0
        if video_ep_num and episode_ep_num:
            episode_number_match = 1.0 if video_ep_num == episode_ep_num else 0.0
            
        # Combine factors
        base_score = direct_similarity
        
        # Boost score if podcast name is present
        if has_podcast_name:
            base_score = min(1.0, base_score * 1.2)
            
        # Heavily weight episode number match if available
        if episode_number_match > 0:
            base_score = max(base_score, 0.7) * episode_number_match
            
        return min(1.0, base_score)
        
    def _score_duration_match(
        self,
        video_duration: int,
        expected_duration: int
    ) -> float:
        """Score duration match within tolerance.
        
        Args:
            video_duration: Video duration in seconds
            expected_duration: Expected duration in seconds
            
        Returns:
            Duration match score between 0.0 and 1.0
        """
        if expected_duration == 0:
            return 0.5  # Neutral score if no expected duration
            
        # Calculate percentage difference
        diff_ratio = abs(video_duration - expected_duration) / expected_duration
        
        if diff_ratio <= self.duration_tolerance:
            # Within tolerance - scale linearly from 1.0 to 0.8
            return 1.0 - (diff_ratio / self.duration_tolerance) * 0.2
        elif diff_ratio <= self.duration_tolerance * 2:
            # Up to 2x tolerance - scale from 0.8 to 0.5
            excess = diff_ratio - self.duration_tolerance
            return 0.8 - (excess / self.duration_tolerance) * 0.3
        else:
            # Beyond 2x tolerance - low score
            return max(0.0, 0.5 - diff_ratio)
            
    def _score_channel_match(
        self,
        channel_id: str,
        channel_title: str,
        podcast_name: str,
        known_channel_ids: List[str]
    ) -> float:
        """Score channel match.
        
        Args:
            channel_id: YouTube channel ID
            channel_title: YouTube channel title
            podcast_name: Expected podcast name
            known_channel_ids: List of known channel IDs
            
        Returns:
            Channel match score between 0.0 and 1.0
        """
        # Perfect match if channel ID is known
        if channel_id in known_channel_ids:
            return 1.0
            
        # Check channel title similarity to podcast name
        channel_normalized = self._normalize_title(channel_title)
        podcast_normalized = self._normalize_title(podcast_name)
        
        # Direct similarity
        similarity = SequenceMatcher(None, channel_normalized, podcast_normalized).ratio()
        
        # Check if channel contains podcast name or vice versa
        contains_match = (
            podcast_normalized in channel_normalized or
            channel_normalized in podcast_normalized
        )
        
        if contains_match:
            return max(0.8, similarity)
        else:
            return similarity * 0.7  # Penalize if no containment
            
    def _score_date_proximity(
        self,
        video_date_str: str,
        expected_date: datetime
    ) -> float:
        """Score upload date proximity.
        
        Args:
            video_date_str: Video upload date as ISO string
            expected_date: Expected publication date
            
        Returns:
            Date proximity score between 0.0 and 1.0
        """
        try:
            # Parse YouTube date (ISO format)
            video_date = datetime.fromisoformat(video_date_str.replace('Z', '+00:00'))
            
            # Calculate days difference
            days_diff = abs((video_date - expected_date).days)
            
            if days_diff <= 2:
                return 1.0  # Perfect match (same day or very close)
            elif days_diff <= 7:
                return 0.9 - (days_diff - 2) * 0.1  # Linear decay from 0.9 to 0.4
            elif days_diff <= 14:
                return 0.4 - (days_diff - 7) * 0.05  # Slower decay from 0.4 to 0.05
            else:
                return max(0.0, 0.05 - days_diff * 0.001)  # Very low score
                
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse video date: {video_date_str}")
            return 0.5  # Neutral score on parse failure
            
    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison.
        
        Args:
            title: Raw title
            
        Returns:
            Normalized title
        """
        # Convert to lowercase
        normalized = title.lower()
        
        # Remove common prefixes
        prefixes_to_remove = [
            r'^episode\s*\d+\s*:?\s*',
            r'^ep\.?\s*\d+\s*:?\s*',
            r'^#\d+\s*:?\s*',
            r'^\d+\s*-\s*',
            r'^\d+\.\s*'
        ]
        
        for prefix in prefixes_to_remove:
            normalized = re.sub(prefix, '', normalized)
            
        # Remove punctuation and extra whitespace
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
        
    def _extract_episode_number(self, title: str) -> Optional[int]:
        """Extract episode number from title.
        
        Args:
            title: Title to extract from
            
        Returns:
            Episode number or None
        """
        patterns = [
            r'(?:episode|ep\.?|#)\s*(\d+)',
            r'^\s*(\d+)\s*[:\-\.]',
            r'\b(\d+)\s*(?:st|nd|rd|th)\s+(?:episode|ep)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
                    
        return None