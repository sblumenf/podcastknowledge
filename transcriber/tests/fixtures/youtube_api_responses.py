"""Mock YouTube API responses for testing."""

from datetime import datetime, timedelta
from typing import Dict, List, Any


class YouTubeAPIResponseFactory:
    """Factory for creating mock YouTube API responses."""
    
    @staticmethod
    def create_search_response(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a mock search response.
        
        Args:
            items: List of search result items
            
        Returns:
            Mock search response in YouTube API format
        """
        return {
            "kind": "youtube#searchListResponse",
            "etag": "mock-etag",
            "nextPageToken": "mock-next-page-token",
            "regionCode": "US",
            "pageInfo": {
                "totalResults": len(items),
                "resultsPerPage": len(items)
            },
            "items": items
        }
    
    @staticmethod
    def create_search_item(
        video_id: str,
        title: str,
        channel_id: str,
        channel_title: str,
        description: str = "",
        published_at: datetime = None,
        thumbnail_url: str = None
    ) -> Dict[str, Any]:
        """Create a mock search result item.
        
        Args:
            video_id: YouTube video ID
            title: Video title
            channel_id: Channel ID
            channel_title: Channel name
            description: Video description
            published_at: Publication date
            thumbnail_url: Thumbnail URL
            
        Returns:
            Mock search item
        """
        if published_at is None:
            published_at = datetime.utcnow()
            
        if thumbnail_url is None:
            thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/default.jpg"
            
        return {
            "kind": "youtube#searchResult",
            "etag": f"mock-etag-{video_id}",
            "id": {
                "kind": "youtube#video",
                "videoId": video_id
            },
            "snippet": {
                "publishedAt": published_at.isoformat() + "Z",
                "channelId": channel_id,
                "title": title,
                "description": description,
                "thumbnails": {
                    "default": {
                        "url": thumbnail_url,
                        "width": 120,
                        "height": 90
                    }
                },
                "channelTitle": channel_title,
                "liveBroadcastContent": "none"
            }
        }
    
    @staticmethod
    def create_video_details_response(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a mock video details response.
        
        Args:
            items: List of video detail items
            
        Returns:
            Mock video details response
        """
        return {
            "kind": "youtube#videoListResponse",
            "etag": "mock-etag",
            "pageInfo": {
                "totalResults": len(items),
                "resultsPerPage": len(items)
            },
            "items": items
        }
    
    @staticmethod
    def create_video_details_item(
        video_id: str,
        duration_seconds: int,
        view_count: int = 0,
        like_count: int = 0,
        comment_count: int = 0
    ) -> Dict[str, Any]:
        """Create a mock video details item.
        
        Args:
            video_id: YouTube video ID
            duration_seconds: Duration in seconds
            view_count: Number of views
            like_count: Number of likes
            comment_count: Number of comments
            
        Returns:
            Mock video details item
        """
        # Convert seconds to ISO 8601 duration
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        
        duration_parts = []
        if hours:
            duration_parts.append(f"{hours}H")
        if minutes:
            duration_parts.append(f"{minutes}M")
        if seconds:
            duration_parts.append(f"{seconds}S")
            
        iso_duration = "PT" + "".join(duration_parts)
        
        return {
            "kind": "youtube#video",
            "etag": f"mock-etag-{video_id}",
            "id": video_id,
            "contentDetails": {
                "duration": iso_duration,
                "dimension": "2d",
                "definition": "hd",
                "caption": "false"
            },
            "statistics": {
                "viewCount": str(view_count),
                "likeCount": str(like_count),
                "commentCount": str(comment_count)
            }
        }
    
    @staticmethod
    def create_channel_response(channel_id: str, uploads_playlist_id: str) -> Dict[str, Any]:
        """Create a mock channel response.
        
        Args:
            channel_id: Channel ID
            uploads_playlist_id: Uploads playlist ID
            
        Returns:
            Mock channel response
        """
        return {
            "kind": "youtube#channelListResponse",
            "etag": "mock-etag",
            "pageInfo": {
                "totalResults": 1,
                "resultsPerPage": 1
            },
            "items": [{
                "kind": "youtube#channel",
                "etag": f"mock-etag-{channel_id}",
                "id": channel_id,
                "contentDetails": {
                    "relatedPlaylists": {
                        "uploads": uploads_playlist_id
                    }
                }
            }]
        }
    
    @staticmethod
    def create_error_response(
        status_code: int,
        reason: str,
        message: str
    ) -> Dict[str, Any]:
        """Create a mock error response.
        
        Args:
            status_code: HTTP status code
            reason: Error reason
            message: Error message
            
        Returns:
            Mock error response
        """
        return {
            "error": {
                "code": status_code,
                "message": message,
                "errors": [{
                    "message": message,
                    "domain": "youtube.api",
                    "reason": reason
                }]
            }
        }


# Pre-built mock responses for common scenarios
class MockResponses:
    """Pre-built mock responses for testing."""
    
    @staticmethod
    def successful_search_with_matches():
        """Mock successful search with good matches."""
        factory = YouTubeAPIResponseFactory()
        
        items = [
            factory.create_search_item(
                video_id="exact_match_123",
                title="The Podcast Episode 123: Interview with Jane Doe",
                channel_id="channel_official",
                channel_title="The Podcast Official",
                description="In this episode, we interview Jane Doe about AI and technology",
                published_at=datetime.utcnow()
            ),
            factory.create_search_item(
                video_id="good_match_456",
                title="Ep 123 - Jane Doe Interview",
                channel_id="channel_official",
                channel_title="The Podcast Official",
                description="Jane Doe discusses the future of technology",
                published_at=datetime.utcnow() - timedelta(days=1)
            ),
            factory.create_search_item(
                video_id="partial_match_789",
                title="Episode 123 Highlights",
                channel_id="channel_clips",
                channel_title="The Podcast Clips",
                description="Best moments from episode 123",
                published_at=datetime.utcnow() - timedelta(days=2)
            )
        ]
        
        return factory.create_search_response(items)
    
    @staticmethod
    def no_results_found():
        """Mock search with no results."""
        factory = YouTubeAPIResponseFactory()
        return factory.create_search_response([])
    
    @staticmethod
    def multiple_similar_results():
        """Mock search with multiple similar results."""
        factory = YouTubeAPIResponseFactory()
        base_date = datetime.utcnow()
        
        items = [
            factory.create_search_item(
                video_id=f"similar_{i}",
                title=f"Episode 123: Great Interview (Part {i})" if i > 1 else "Episode 123: Great Interview",
                channel_id="channel_official",
                channel_title="The Podcast",
                published_at=base_date - timedelta(hours=i)
            )
            for i in range(1, 4)
        ]
        
        return factory.create_search_response(items)
    
    @staticmethod
    def video_details_for_ids(video_ids: List[str], base_duration: int = 3600):
        """Mock video details for given IDs."""
        factory = YouTubeAPIResponseFactory()
        
        items = []
        for i, video_id in enumerate(video_ids):
            items.append(factory.create_video_details_item(
                video_id=video_id,
                duration_seconds=base_duration + (i * 60),  # Slight duration variations
                view_count=10000 - (i * 1000),
                like_count=500 - (i * 50),
                comment_count=100 - (i * 10)
            ))
            
        return factory.create_video_details_response(items)
    
    @staticmethod
    def quota_exceeded_error():
        """Mock quota exceeded error."""
        factory = YouTubeAPIResponseFactory()
        return factory.create_error_response(
            status_code=403,
            reason="quotaExceeded",
            message="The request cannot be completed because you have exceeded your quota."
        )
    
    @staticmethod
    def invalid_api_key_error():
        """Mock invalid API key error."""
        factory = YouTubeAPIResponseFactory()
        return factory.create_error_response(
            status_code=403,
            reason="forbidden",
            message="The request is missing a valid API key."
        )
    
    @staticmethod
    def network_error():
        """Mock network error."""
        factory = YouTubeAPIResponseFactory()
        return factory.create_error_response(
            status_code=503,
            reason="backendError",
            message="Service temporarily unavailable."
        )
    
    @staticmethod
    def channel_uploads_results(channel_id: str, episode_count: int = 5):
        """Mock channel uploads search results."""
        factory = YouTubeAPIResponseFactory()
        base_date = datetime.utcnow()
        
        items = []
        for i in range(episode_count):
            items.append(factory.create_search_item(
                video_id=f"channel_ep_{i}",
                title=f"Episode {100 + i}: Channel Upload",
                channel_id=channel_id,
                channel_title="The Podcast Official",
                description=f"Episode {100 + i} uploaded to our channel",
                published_at=base_date - timedelta(days=i * 7)  # Weekly uploads
            ))
            
        return factory.create_search_response(items)
    
    @staticmethod
    def realistic_podcast_scenario(podcast_name: str = "The Tim Ferriss Show"):
        """Create realistic search results for a known podcast."""
        factory = YouTubeAPIResponseFactory()
        base_date = datetime.utcnow()
        
        items = [
            # Exact match - official channel
            factory.create_search_item(
                video_id="tim_official_123",
                title=f"{podcast_name} Episode 123: Dr. Jane Smith on Longevity",
                channel_id="tim_ferriss_official",
                channel_title="Tim Ferriss",
                description="Dr. Jane Smith discusses the latest research on longevity and healthspan",
                published_at=base_date - timedelta(days=2)
            ),
            # Fan upload - different channel
            factory.create_search_item(
                video_id="fan_upload_123",
                title="TFS #123 - Dr. Jane Smith [FULL EPISODE]",
                channel_id="podcast_fan_channel",
                channel_title="Podcast Archive",
                description="Full episode of Tim Ferriss Show #123",
                published_at=base_date - timedelta(days=3)
            ),
            # Clips channel
            factory.create_search_item(
                video_id="clips_123",
                title="Best Moments - Tim Ferriss & Dr. Jane Smith",
                channel_id="tim_clips",
                channel_title="Tim Ferriss Clips",
                description="Highlights from episode 123",
                published_at=base_date - timedelta(days=1)
            )
        ]
        
        return factory.create_search_response(items)