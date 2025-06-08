"""Query builder for YouTube episode searches.

This module generates multiple search query variations to find the best match
for podcast episodes on YouTube.
"""

import re
from typing import List, Optional, Tuple
from datetime import datetime

from src.utils.logging import get_logger

logger = get_logger('youtube_query_builder')


class QueryBuilder:
    """Builds search queries for finding podcast episodes on YouTube."""
    
    def __init__(self):
        """Initialize query builder."""
        # Common episode number patterns
        self.episode_patterns = [
            r'(?:episode|ep\.?|#)\s*(\d+)',
            r'^\s*(\d+)\s*[:\-\.]',
            r'\b(\d+)\s*(?:st|nd|rd|th)\s+(?:episode|ep)',
        ]
        
        # Common guest name patterns
        self.guest_patterns = [
            r'(?:with|featuring|ft\.?|guest[:\s])\s*([^,\-\(\)]+)',
            r'(?:interview(?:ing)?|conversation with)\s*([^,\-\(\)]+)',
            r'(?:^[^-]+)\s*-\s*([^-|\(\)]+?)(?:\s*(?:\||$))',  # Name after dash
        ]
        
    def build_queries(
        self,
        podcast_name: str,
        episode_title: str,
        episode_number: Optional[int] = None
    ) -> List[Tuple[str, int]]:
        """Build multiple search query variations ranked by expected accuracy.
        
        Args:
            podcast_name: Name of the podcast
            episode_title: Title of the episode
            episode_number: Episode number if available
            
        Returns:
            List of (query, rank) tuples where lower rank = higher priority
        """
        queries = []
        
        # Extract episode number from title if not provided
        if episode_number is None:
            episode_number = self._extract_episode_number(episode_title)
            
        # Extract guest name if present
        guest_name = self._extract_guest_name(episode_title)
        
        # Clean title for searching
        clean_title = self._clean_title(episode_title)
        
        # 1. Exact match query (highest priority)
        queries.append((self.build_exact_match_query(podcast_name, episode_title), 1))
        
        # 2. Episode number query if available
        if episode_number:
            queries.append((self.build_episode_number_query(podcast_name, episode_number, clean_title), 2))
            
        # 3. Guest name query if available
        if guest_name:
            queries.append((self.build_guest_name_query(podcast_name, guest_name), 3))
            
        # 4. Fuzzy match query (cleaned title)
        if clean_title != episode_title:
            queries.append((self.build_fuzzy_match_query(podcast_name, clean_title), 4))
            
        # 5. Broad search (podcast + key terms)
        key_terms = self._extract_key_terms(clean_title)
        if key_terms:
            queries.append((f'"{podcast_name}" {" ".join(key_terms[:3])}', 5))
            
        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for query, rank in queries:
            if query not in seen:
                seen.add(query)
                unique_queries.append((query, rank))
                
        logger.debug(f"Generated {len(unique_queries)} queries for episode: {episode_title}")
        return unique_queries
        
    def build_exact_match_query(self, podcast_name: str, episode_title: str) -> str:
        """Build query for exact title match.
        
        Args:
            podcast_name: Name of the podcast
            episode_title: Full episode title
            
        Returns:
            Exact match search query
        """
        # Strip and normalize input strings
        podcast_name = podcast_name.strip()
        episode_title = episode_title.strip()
        
        # Use quotes for exact phrase matching
        query = f'"{podcast_name}" "{episode_title}"'
        return self._normalize_query(query)
        
    def build_episode_number_query(
        self,
        podcast_name: str,
        episode_number: int,
        title_fragment: Optional[str] = None
    ) -> str:
        """Build query using episode number.
        
        Args:
            podcast_name: Name of the podcast
            episode_number: Episode number
            title_fragment: Optional title fragment to include
            
        Returns:
            Episode number based search query
        """
        # Try multiple episode number formats
        number_variations = [
            f"episode {episode_number}",
            f"ep {episode_number}",
            f"#{episode_number}",
        ]
        
        base_query = f'"{podcast_name}" ({" OR ".join(number_variations)})'
        
        if title_fragment:
            # Add key terms from title
            key_terms = self._extract_key_terms(title_fragment)[:2]
            if key_terms:
                base_query += f' {" ".join(key_terms)}'
                
        return self._normalize_query(base_query)
        
    def build_guest_name_query(self, podcast_name: str, guest_name: str) -> str:
        """Build query using guest name.
        
        Args:
            podcast_name: Name of the podcast
            guest_name: Name of the guest
            
        Returns:
            Guest name based search query
        """
        # Clean guest name
        guest_name = re.sub(r'\s+', ' ', guest_name.strip())
        
        query = f'"{podcast_name}" "{guest_name}"'
        return self._normalize_query(query)
        
    def build_fuzzy_match_query(self, podcast_name: str, cleaned_title: str) -> str:
        """Build query for fuzzy title matching.
        
        Args:
            podcast_name: Name of the podcast
            cleaned_title: Cleaned episode title
            
        Returns:
            Fuzzy match search query
        """
        # Use key terms without quotes for fuzzy matching
        key_terms = self._extract_key_terms(cleaned_title)
        
        if key_terms:
            query = f'"{podcast_name}" {" ".join(key_terms[:4])}'
        else:
            query = f'"{podcast_name}" {cleaned_title}'
            
        return self._normalize_query(query)
        
    def _extract_episode_number(self, title: str) -> Optional[int]:
        """Extract episode number from title.
        
        Args:
            title: Episode title
            
        Returns:
            Episode number or None if not found
        """
        for pattern in self.episode_patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
                    
        return None
        
    def _extract_guest_name(self, title: str) -> Optional[str]:
        """Extract guest name from title.
        
        Args:
            title: Episode title
            
        Returns:
            Guest name or None if not found
        """
        for pattern in self.guest_patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                guest_name = match.group(1).strip()
                # Basic validation - should have at least 2 words
                if len(guest_name.split()) >= 2 and len(guest_name) < 50:
                    return guest_name
                    
        return None
        
    def _clean_title(self, title: str) -> str:
        """Clean title by removing common prefixes and special characters.
        
        Args:
            title: Original title
            
        Returns:
            Cleaned title
        """
        # Remove common episode prefixes
        prefixes_to_remove = [
            r'^(?:episode|ep\.?)\s*\d+\s*[:\-]?\s*',
            r'^#?\d+\s*[:\-]?\s*',
            r'^\d+\.\s*',
            r'^[A-Z]+\d+\s*[:\-]\s*',  # e.g., "EP123: "
        ]
        
        cleaned = title
        for prefix in prefixes_to_remove:
            cleaned = re.sub(prefix, '', cleaned, flags=re.IGNORECASE)
            
        # Remove special characters but keep important punctuation
        cleaned = re.sub(r'[^\w\s\-\'\"&]', ' ', cleaned)
        
        # Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
        
    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms from text for searching.
        
        Args:
            text: Text to extract terms from
            
        Returns:
            List of key terms
        """
        # Split into words
        words = text.split()
        
        # Filter out common words and short words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that',
            'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'over', 'under', 'above', 'below', 'between', 'through'
        }
        
        key_terms = []
        for word in words:
            word_lower = word.lower()
            if (len(word) > 2 and 
                word_lower not in stop_words and 
                not word.isdigit()):
                key_terms.append(word)
                
        return key_terms
        
    def _normalize_query(self, query: str) -> str:
        """Normalize query for YouTube search.
        
        Args:
            query: Raw query string
            
        Returns:
            Normalized query
        """
        # Remove extra spaces
        query = re.sub(r'\s+', ' ', query).strip()
        
        # Ensure query isn't too long (YouTube limit)
        if len(query) > 100:
            # Truncate intelligently at word boundary
            query = query[:97] + '...'
            
        return query