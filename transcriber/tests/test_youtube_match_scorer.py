"""Unit tests for YouTube match scorer module."""

import pytest
from datetime import datetime, timedelta
from src.youtube_match_scorer import MatchScorer


class TestMatchScorer:
    """Test cases for MatchScorer class."""
    
    @pytest.fixture
    def scorer(self):
        """Create a MatchScorer instance for testing."""
        return MatchScorer(duration_tolerance=0.10)
    
    @pytest.fixture
    def sample_result(self):
        """Create a sample YouTube search result."""
        return {
            'video_id': 'abc123',
            'title': 'The Podcast Episode 123: Interview with Jane Doe',
            'channel_id': 'channel123',
            'channel_title': 'The Podcast Official',
            'published_at': datetime.utcnow().isoformat() + 'Z',
            'duration_seconds': 3600,  # 1 hour
            'description': 'Great interview about technology',
            'view_count': 10000,
            'like_count': 500
        }
    
    def test_title_similarity_scoring_exact_match(self, scorer):
        """Test title similarity scoring with exact match."""
        score = scorer._score_title_similarity(
            "Episode 123: Jane Doe Interview",
            "Episode 123: Jane Doe Interview",
            "My Podcast"
        )
        
        assert score >= 0.95  # Should be very high for exact match
        
    def test_title_similarity_scoring_with_podcast_name(self, scorer):
        """Test title similarity with podcast name present."""
        score = scorer._score_title_similarity(
            "My Podcast - Episode 123: Jane Doe",
            "Episode 123: Jane Doe",
            "My Podcast"
        )
        
        assert score >= 0.8  # Should be boosted by podcast name presence
        
    def test_title_similarity_scoring_episode_number_match(self, scorer):
        """Test title similarity with matching episode numbers."""
        score = scorer._score_title_similarity(
            "Ep 123: Different Title",
            "Episode 123: Original Title",
            "Podcast"
        )
        
        assert score >= 0.7  # Episode number match should boost score
        
    def test_title_similarity_scoring_normalized(self, scorer):
        """Test title similarity with normalization."""
        score = scorer._score_title_similarity(
            "EPISODE 123: JANE DOE!!!",
            "Episode 123 - Jane Doe",
            "Podcast"
        )
        
        assert score >= 0.8  # Should handle case and punctuation differences
        
    def test_duration_matching_within_tolerance(self, scorer):
        """Test duration matching within tolerance."""
        # 10% tolerance of 3600 seconds = 360 seconds
        
        # Exact match
        score = scorer._score_duration_match(3600, 3600)
        assert score == 1.0
        
        # 5% difference (within tolerance)
        score = scorer._score_duration_match(3780, 3600)  # 180 seconds diff
        assert 0.9 <= score <= 1.0
        
        # 10% difference (edge of tolerance)
        score = scorer._score_duration_match(3960, 3600)  # 360 seconds diff
        assert 0.8 <= score <= 0.9
        
    def test_duration_matching_outside_tolerance(self, scorer):
        """Test duration matching outside tolerance."""
        # 15% difference (1.5x tolerance)
        score = scorer._score_duration_match(4140, 3600)  # 540 seconds diff
        assert 0.5 <= score <= 0.8
        
        # 30% difference (3x tolerance)
        score = scorer._score_duration_match(4680, 3600)  # 1080 seconds diff
        assert score < 0.5
        
    def test_duration_matching_edge_cases(self, scorer):
        """Test duration matching edge cases."""
        # Zero expected duration
        score = scorer._score_duration_match(3600, 0)
        assert score == 0.5  # Neutral score
        
        # Very large difference
        score = scorer._score_duration_match(7200, 1800)  # 4x difference
        assert score >= 0.0
        
    def test_channel_match_known_channel(self, scorer):
        """Test channel matching with known channel."""
        score = scorer._score_channel_match(
            'channel123',
            'The Podcast Channel',
            'The Podcast',
            ['channel123', 'channel456']
        )
        
        assert score == 1.0  # Perfect match for known channel
        
    def test_channel_match_title_similarity(self, scorer):
        """Test channel matching by title similarity."""
        score = scorer._score_channel_match(
            'unknown_channel',
            'The Daily Show',
            'The Daily',
            []
        )
        
        assert score >= 0.8  # High similarity
        
    def test_channel_match_contains(self, scorer):
        """Test channel matching when names contain each other."""
        # Channel contains podcast name
        score = scorer._score_channel_match(
            'channel_id',
            'The Joe Rogan Experience Official',
            'Joe Rogan',
            []
        )
        assert score >= 0.8
        
        # Podcast name contains channel
        score = scorer._score_channel_match(
            'channel_id',
            'TED',
            'TED Talks Daily',
            []
        )
        assert score >= 0.8
        
    def test_date_proximity_scoring_same_day(self, scorer):
        """Test date proximity scoring for same day."""
        now = datetime.utcnow()
        score = scorer._score_date_proximity(
            now.isoformat() + 'Z',
            now
        )
        
        assert score == 1.0  # Perfect match
        
    def test_date_proximity_scoring_within_week(self, scorer):
        """Test date proximity scoring within a week."""
        expected = datetime.utcnow()
        
        # 3 days difference
        video_date = expected + timedelta(days=3)
        score = scorer._score_date_proximity(
            video_date.isoformat() + 'Z',
            expected
        )
        assert 0.7 <= score <= 0.9
        
        # 7 days difference
        video_date = expected + timedelta(days=7)
        score = scorer._score_date_proximity(
            video_date.isoformat() + 'Z',
            expected
        )
        assert 0.4 <= score <= 0.6
        
    def test_date_proximity_scoring_beyond_week(self, scorer):
        """Test date proximity scoring beyond a week."""
        expected = datetime.utcnow()
        
        # 10 days difference
        video_date = expected + timedelta(days=10)
        score = scorer._score_date_proximity(
            video_date.isoformat() + 'Z',
            expected
        )
        assert 0.1 <= score <= 0.4
        
        # 30 days difference
        video_date = expected + timedelta(days=30)
        score = scorer._score_date_proximity(
            video_date.isoformat() + 'Z',
            expected
        )
        assert score < 0.1
        
    def test_date_proximity_invalid_date(self, scorer):
        """Test date proximity with invalid date."""
        score = scorer._score_date_proximity(
            'invalid-date',
            datetime.utcnow()
        )
        
        assert score == 0.5  # Neutral score on parse failure
        
    def test_composite_score_calculation(self, scorer):
        """Test composite score calculation."""
        result = {
            'video_id': 'test123',
            'title': 'My Podcast Episode 10: Great Interview',
            'channel_id': 'ch123',
            'channel_title': 'My Podcast Official',
            'published_at': datetime.utcnow().isoformat() + 'Z',
            'duration_seconds': 3600
        }
        
        score = scorer._calculate_score(
            result,
            episode_title='Episode 10: Great Interview',
            podcast_name='My Podcast',
            episode_duration=3650,  # Close to 3600
            episode_date=datetime.utcnow(),
            known_channel_ids=[]
        )
        
        # Should be high score due to good matches
        assert score >= 0.7
        assert score <= 1.0
        
    def test_composite_score_weights(self, scorer):
        """Test that composite score weights sum to 1.0."""
        total_weight = (
            scorer.TITLE_WEIGHT +
            scorer.DURATION_WEIGHT +
            scorer.CHANNEL_WEIGHT +
            scorer.DATE_WEIGHT
        )
        
        assert abs(total_weight - 1.0) < 0.001  # Allow for floating point error
        
    def test_score_results_sorting(self, scorer):
        """Test that results are sorted by score descending."""
        results = [
            {'video_id': '1', 'title': 'Poor Match', 'channel_id': 'ch1', 
             'channel_title': 'Random', 'published_at': '2023-01-01T00:00:00Z'},
            {'video_id': '2', 'title': 'Episode 123: Exact Match', 'channel_id': 'ch2',
             'channel_title': 'My Podcast', 'published_at': datetime.utcnow().isoformat() + 'Z'},
            {'video_id': '3', 'title': 'Medium Match Ep 123', 'channel_id': 'ch3',
             'channel_title': 'Similar', 'published_at': '2023-06-01T00:00:00Z'},
        ]
        
        scored = scorer.score_results(
            results,
            episode_title='Episode 123: Exact Match',
            podcast_name='My Podcast',
            episode_duration=None,
            episode_date=datetime.utcnow()
        )
        
        # Check sorted order
        scores = [score for _, score in scored]
        assert scores == sorted(scores, reverse=True)
        
        # Best match should be the exact title match
        assert scored[0][0]['video_id'] == '2'
        
    def test_normalize_title(self, scorer):
        """Test title normalization."""
        test_cases = [
            ("Episode 123: Title", "title"),
            ("Ep. 456 - Title", "title"),
            ("#789 Title", "title"),
            ("123 - Title", "title"),
            ("Title!@#$%", "title"),
            ("Multiple   Spaces", "multiple spaces"),
            ("UPPERCASE", "uppercase"),
        ]
        
        for original, expected in test_cases:
            result = scorer._normalize_title(original)
            assert result == expected
            
    def test_extract_episode_number(self, scorer):
        """Test episode number extraction."""
        test_cases = [
            ("Episode 123: Title", 123),
            ("Ep. 456", 456),
            ("#789", 789),
            ("1st Episode", 1),
            ("2nd Episode Special", 2),
            ("The 3rd Episode", 3),
            ("No Episode Number", None),
        ]
        
        for title, expected in test_cases:
            result = scorer._extract_episode_number(title)
            assert result == expected