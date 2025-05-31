"""Metadata indexing system for podcast transcripts.

This module provides searchable indexing functionality for processed episodes,
enabling quick lookup by speaker, date, podcast, and other metadata.
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Union
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, asdict

from src.utils.logging import get_logger
from src.file_organizer import EpisodeMetadata

logger = get_logger('metadata_index')


@dataclass
class SearchResult:
    """Container for search results."""
    query: str
    total_results: int
    episodes: List[EpisodeMetadata]
    search_time_ms: float


class MetadataIndex:
    """Searchable index for podcast episode metadata."""
    
    def __init__(self, base_dir: str = "data"):
        """Initialize metadata index.
        
        Args:
            base_dir: Base directory containing transcripts and index
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Index file location
        self.index_file = self.base_dir / "index.json"
        
        # In-memory indices for fast searching
        self.episodes: List[EpisodeMetadata] = []
        self.speaker_index: Dict[str, Set[int]] = defaultdict(set)  # speaker -> episode indices
        self.podcast_index: Dict[str, Set[int]] = defaultdict(set)  # podcast -> episode indices  
        self.date_index: Dict[str, Set[int]] = defaultdict(set)     # date -> episode indices
        self.word_index: Dict[str, Set[int]] = defaultdict(set)     # word -> episode indices
        
        # Load existing index
        self.load_index()
    
    def add_episode(self, episode: EpisodeMetadata):
        """Add an episode to the index.
        
        Args:
            episode: Episode metadata to add
        """
        # Check if episode already exists (by file path)
        existing_idx = None
        for i, existing_episode in enumerate(self.episodes):
            if existing_episode.file_path == episode.file_path:
                existing_idx = i
                break
        
        if existing_idx is not None:
            # Update existing episode
            self.episodes[existing_idx] = episode
            episode_idx = existing_idx
            logger.info(f"Updated episode in index: {episode.title}")
        else:
            # Add new episode
            self.episodes.append(episode)
            episode_idx = len(self.episodes) - 1
            logger.info(f"Added episode to index: {episode.title}")
        
        # Update search indices
        self._update_indices(episode, episode_idx)
        
        # Save to disk
        self.save_index()
    
    def _update_indices(self, episode: EpisodeMetadata, episode_idx: int):
        """Update search indices for an episode.
        
        Args:
            episode: Episode metadata
            episode_idx: Index of episode in episodes list
        """
        # Clear existing indices for this episode (in case of update)
        self._remove_from_indices(episode_idx)
        
        # Speaker index
        for speaker in episode.speakers:
            speaker_key = speaker.lower().strip()
            if speaker_key:
                self.speaker_index[speaker_key].add(episode_idx)
        
        # Podcast index
        podcast_key = episode.podcast_name.lower().strip()
        if podcast_key:
            self.podcast_index[podcast_key].add(episode_idx)
        
        # Date index
        if episode.publication_date:
            # Index by full date and year-month
            self.date_index[episode.publication_date].add(episode_idx)
            if len(episode.publication_date) >= 7:  # YYYY-MM-DD format
                year_month = episode.publication_date[:7]  # YYYY-MM
                self.date_index[year_month].add(episode_idx)
        
        # Word index (title and description)
        words = []
        if episode.title:
            words.extend(self._extract_words(episode.title))
        if episode.description:
            words.extend(self._extract_words(episode.description))
        
        for word in words:
            word_key = word.lower().strip()
            if word_key and len(word_key) > 2:  # Skip very short words
                self.word_index[word_key].add(episode_idx)
    
    def _remove_from_indices(self, episode_idx: int):
        """Remove an episode from all search indices.
        
        Args:
            episode_idx: Index of episode to remove
        """
        # Remove from all indices
        for speaker_set in self.speaker_index.values():
            speaker_set.discard(episode_idx)
        
        for podcast_set in self.podcast_index.values():
            podcast_set.discard(episode_idx)
        
        for date_set in self.date_index.values():
            date_set.discard(episode_idx)
        
        for word_set in self.word_index.values():
            word_set.discard(episode_idx)
    
    def _extract_words(self, text: str) -> List[str]:
        """Extract searchable words from text.
        
        Args:
            text: Text to extract words from
            
        Returns:
            List of words
        """
        import re
        # Simple word extraction (alphanumeric + basic punctuation)
        words = re.findall(r'\b\w+\b', text.lower())
        return [word for word in words if len(word) > 2]
    
    def search_by_speaker(self, speaker_name: str) -> SearchResult:
        """Search episodes by speaker name.
        
        Args:
            speaker_name: Name or partial name of speaker
            
        Returns:
            SearchResult with matching episodes
        """
        start_time = datetime.now()
        
        speaker_key = speaker_name.lower().strip()
        matching_indices = set()
        
        # Exact and partial matches
        for indexed_speaker, episode_indices in self.speaker_index.items():
            if speaker_key in indexed_speaker or indexed_speaker in speaker_key:
                matching_indices.update(episode_indices)
        
        episodes = [self.episodes[i] for i in sorted(matching_indices)]
        
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return SearchResult(
            query=f"speaker:{speaker_name}",
            total_results=len(episodes),
            episodes=episodes,
            search_time_ms=round(search_time, 2)
        )
    
    def search_by_podcast(self, podcast_name: str) -> SearchResult:
        """Search episodes by podcast name.
        
        Args:
            podcast_name: Name or partial name of podcast
            
        Returns:
            SearchResult with matching episodes
        """
        start_time = datetime.now()
        
        podcast_key = podcast_name.lower().strip()
        matching_indices = set()
        
        # Exact and partial matches
        for indexed_podcast, episode_indices in self.podcast_index.items():
            if podcast_key in indexed_podcast or indexed_podcast in podcast_key:
                matching_indices.update(episode_indices)
        
        episodes = [self.episodes[i] for i in sorted(matching_indices)]
        
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return SearchResult(
            query=f"podcast:{podcast_name}",
            total_results=len(episodes),
            episodes=episodes,
            search_time_ms=round(search_time, 2)
        )
    
    def search_by_date_range(self, start_date: str, end_date: Optional[str] = None) -> SearchResult:
        """Search episodes by date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD or YYYY-MM format
            end_date: End date in YYYY-MM-DD format (optional)
            
        Returns:
            SearchResult with matching episodes
        """
        start_time = datetime.now()
        
        if end_date is None:
            end_date = start_date
        
        matching_indices = set()
        
        # Search date index
        for date_str, episode_indices in self.date_index.items():
            if start_date <= date_str <= end_date:
                matching_indices.update(episode_indices)
        
        episodes = [self.episodes[i] for i in sorted(matching_indices)]
        
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        
        query_str = f"date:{start_date}" if start_date == end_date else f"date:{start_date}..{end_date}"
        
        return SearchResult(
            query=query_str,
            total_results=len(episodes),
            episodes=episodes,
            search_time_ms=round(search_time, 2)
        )
    
    def search_by_keywords(self, keywords: Union[str, List[str]]) -> SearchResult:
        """Search episodes by keywords in title or description.
        
        Args:
            keywords: Keywords to search for (string or list)
            
        Returns:
            SearchResult with matching episodes
        """
        start_time = datetime.now()
        
        if isinstance(keywords, str):
            keywords = [keywords]
        
        keyword_keys = [kw.lower().strip() for kw in keywords]
        matching_indices = set()
        
        # Search for each keyword
        for keyword in keyword_keys:
            if not keyword:
                continue
                
            # Exact and partial matches in word index
            for indexed_word, episode_indices in self.word_index.items():
                if keyword in indexed_word or indexed_word in keyword:
                    matching_indices.update(episode_indices)
        
        episodes = [self.episodes[i] for i in sorted(matching_indices)]
        
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return SearchResult(
            query=f"keywords:{','.join(keywords)}",
            total_results=len(episodes),
            episodes=episodes,
            search_time_ms=round(search_time, 2)
        )
    
    def search_all(self, query: str) -> SearchResult:
        """Search across all fields with a single query.
        
        Args:
            query: Search query
            
        Returns:
            SearchResult with matching episodes
        """
        start_time = datetime.now()
        
        # Search across all indices
        speaker_results = self.search_by_speaker(query)
        podcast_results = self.search_by_podcast(query)
        keyword_results = self.search_by_keywords(query)
        
        # Combine results (union of all matches)
        all_episodes = set()
        for episode in speaker_results.episodes:
            all_episodes.add(episode.file_path)
        for episode in podcast_results.episodes:
            all_episodes.add(episode.file_path)
        for episode in keyword_results.episodes:
            all_episodes.add(episode.file_path)
        
        # Convert back to episodes list
        final_episodes = []
        for episode in self.episodes:
            if episode.file_path in all_episodes:
                final_episodes.append(episode)
        
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return SearchResult(
            query=f"all:{query}",
            total_results=len(final_episodes),
            episodes=final_episodes,
            search_time_ms=round(search_time, 2)
        )
    
    def get_all_episodes(self) -> List[EpisodeMetadata]:
        """Get all episodes in the index.
        
        Returns:
            List of all episodes
        """
        return self.episodes.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get index statistics.
        
        Returns:
            Dictionary with index statistics
        """
        total_episodes = len(self.episodes)
        
        if total_episodes == 0:
            return {'total_episodes': 0}
        
        # Unique counts
        unique_speakers = len(self.speaker_index)
        unique_podcasts = len(self.podcast_index)
        unique_dates = len([date for date in self.date_index.keys() if len(date) == 10])  # Full dates only
        
        # Date range
        dates = [ep.publication_date for ep in self.episodes if ep.publication_date]
        date_range = (min(dates), max(dates)) if dates else (None, None)
        
        # Duration statistics
        durations = [ep.duration for ep in self.episodes if ep.duration]
        total_duration = sum(durations) if durations else 0
        avg_duration = total_duration / len(durations) if durations else 0
        
        return {
            'total_episodes': total_episodes,
            'unique_speakers': unique_speakers,
            'unique_podcasts': unique_podcasts,
            'unique_dates': unique_dates,
            'date_range': date_range,
            'total_duration_seconds': total_duration,
            'total_duration_hours': round(total_duration / 3600, 2),
            'average_duration_seconds': round(avg_duration, 2),
            'index_size_kb': round(self.index_file.stat().st_size / 1024, 2) if self.index_file.exists() else 0
        }
    
    def export_to_csv(self, output_file: str, include_all_fields: bool = True) -> str:
        """Export index to CSV format.
        
        Args:
            output_file: Path to output CSV file
            include_all_fields: Whether to include all fields or just basic ones
            
        Returns:
            Path to created CSV file
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Define CSV columns
        if include_all_fields:
            fieldnames = [
                'title', 'podcast_name', 'publication_date', 'file_path',
                'speakers', 'duration', 'episode_number', 'description', 'processed_date'
            ]
        else:
            fieldnames = [
                'title', 'podcast_name', 'publication_date', 'file_path',
                'speakers', 'duration'
            ]
        
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for episode in self.episodes:
                    row_data = asdict(episode)
                    
                    # Convert speakers list to comma-separated string
                    row_data['speakers'] = ', '.join(episode.speakers) if episode.speakers else ''
                    
                    # Filter fields if not including all
                    if not include_all_fields:
                        row_data = {k: v for k, v in row_data.items() if k in fieldnames}
                    
                    writer.writerow(row_data)
            
            logger.info(f"Exported {len(self.episodes)} episodes to CSV: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to export to CSV: {e}")
            raise
    
    def load_index(self):
        """Load index from disk."""
        if not self.index_file.exists():
            logger.info("No existing index found, starting with empty index")
            return
        
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load episodes
            self.episodes = []
            for episode_data in data.get('episodes', []):
                episode = EpisodeMetadata(**episode_data)
                self.episodes.append(episode)
            
            # Rebuild search indices
            self._rebuild_indices()
            
            logger.info(f"Loaded {len(self.episodes)} episodes from index")
            
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            logger.info("Starting with empty index")
            self.episodes = []
            self._rebuild_indices()
    
    def save_index(self):
        """Save index to disk."""
        try:
            data = {
                'version': '1.0',
                'generated_at': datetime.now().isoformat(),
                'total_episodes': len(self.episodes),
                'episodes': [asdict(episode) for episode in self.episodes],
                'statistics': self.get_statistics()
            }
            
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved index with {len(self.episodes)} episodes")
            
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
    
    def _rebuild_indices(self):
        """Rebuild all search indices from episodes list."""
        # Clear existing indices
        self.speaker_index.clear()
        self.podcast_index.clear()
        self.date_index.clear()
        self.word_index.clear()
        
        # Rebuild indices
        for i, episode in enumerate(self.episodes):
            self._update_indices(episode, i)
    
    def rebuild_from_manifest(self, manifest_file: str):
        """Rebuild index from a file organizer manifest.
        
        Args:
            manifest_file: Path to manifest.json file
        """
        manifest_path = Path(manifest_file)
        if not manifest_path.exists():
            logger.error(f"Manifest file not found: {manifest_file}")
            return
        
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Clear existing index
            self.episodes = []
            
            # Load episodes from manifest
            for episode_data in data.get('episodes', []):
                episode = EpisodeMetadata(**episode_data)
                self.add_episode(episode)
            
            logger.info(f"Rebuilt index from manifest with {len(self.episodes)} episodes")
            
        except Exception as e:
            logger.error(f"Failed to rebuild from manifest: {e}")


# Global index instance
_index_instance = None


def get_metadata_index(base_dir: str = "data") -> MetadataIndex:
    """Get the global metadata index instance.
    
    Args:
        base_dir: Base directory for index
        
    Returns:
        MetadataIndex instance
    """
    global _index_instance
    if _index_instance is None:
        _index_instance = MetadataIndex(base_dir)
    return _index_instance