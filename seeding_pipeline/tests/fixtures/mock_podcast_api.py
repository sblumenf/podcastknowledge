"""Mock implementations for podcast API functions."""

from typing import Dict, Any, List
from unittest.mock import Mock


def mock_seed_podcast(podcast: Dict[str, Any], max_episodes: int = 5, 
                     config: Any = None) -> Dict[str, Any]:
    """Mock implementation of seed_podcast that returns success."""
    # If the podcast has vtt_files, use that count
    if 'vtt_files' in podcast:
        episodes_count = len(podcast['vtt_files'])
    else:
        episodes_count = min(max_episodes, 3)
    
    return {
        'podcasts_processed': 1,
        'episodes_processed': episodes_count,
        'episodes_failed': 0,
        'entities_extracted': 15,
        'insights_extracted': 10,
        'quotes_extracted': 5,
        'processing_time': 2.5,
        'errors': []
    }


def mock_seed_podcasts(podcasts: List[Dict[str, Any]], max_episodes: int = 5,
                      max_episodes_each: int = None, max_episodes_per_podcast: int = None,
                      config: Any = None, **kwargs) -> Dict[str, Any]:
    """Mock implementation of seed_podcasts that returns success."""
    # Handle different parameter names for max episodes
    episodes_limit = max_episodes_each or max_episodes_per_podcast or max_episodes
    
    results = []
    for podcast in podcasts:
        results.append(mock_seed_podcast(podcast, episodes_limit, config))
    
    return {
        'podcasts_processed': len(podcasts),
        'episodes_processed': sum(r['episodes_processed'] for r in results),
        'episodes_failed': sum(r['episodes_failed'] for r in results),
        'results': results
    }


class MockVTTKnowledgeExtractor:
    """Mock VTT Knowledge Extractor."""
    
    def __init__(self, config=None):
        self.config = config
        self.processed_count = 0
    
    def process_vtt_file(self, file_path: str) -> Dict[str, Any]:
        """Mock processing of VTT file."""
        self.processed_count += 1
        return {
            'segments_processed': 10,
            'entities_extracted': 5,
            'insights_extracted': 3,
            'file': str(file_path)
        }
    
    def process_vtt_directory(self, directory: str) -> List[Dict[str, Any]]:
        """Mock processing of VTT directory."""
        # Simulate processing 3 files
        results = []
        for i in range(3):
            results.append(self.process_vtt_file(f"{directory}/file_{i}.vtt"))
        return results
    
    def seed_podcast(self, podcast: Dict[str, Any], max_episodes: int = 5) -> Dict[str, Any]:
        """Mock seed_podcast method."""
        return mock_seed_podcast(podcast, max_episodes, self.config)
    
    def seed_podcasts(self, podcasts: List[Dict[str, Any]], 
                     max_episodes_per_podcast: int = 5) -> Dict[str, Any]:
        """Mock seed_podcasts method."""
        return mock_seed_podcasts(podcasts, 
                                max_episodes_per_podcast=max_episodes_per_podcast,
                                config=self.config)
    
    def cleanup(self):
        """Mock cleanup method."""
        pass