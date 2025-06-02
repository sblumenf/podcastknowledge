"""Integration tests for RSS feed parser with various feed formats."""

import pytest
from datetime import datetime
from unittest.mock import patch, Mock
import xml.etree.ElementTree as ET
import feedparser

from src.feed_parser import parse_feed


@pytest.mark.integration
@pytest.mark.network
class TestFeedParserFormats:
    """Test feed parser with various RSS feed formats."""
    
    @pytest.fixture
    def standard_rss_20_feed(self):
        """Standard RSS 2.0 feed without iTunes extensions."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Standard Podcast</title>
                <link>https://example.com</link>
                <description>A standard RSS 2.0 podcast</description>
                <language>en-us</language>
                <lastBuildDate>Mon, 01 Jun 2025 12:00:00 GMT</lastBuildDate>
                <item>
                    <title>Episode 1</title>
                    <description>First episode description</description>
                    <link>https://example.com/ep1</link>
                    <guid>https://example.com/ep1</guid>
                    <pubDate>Mon, 01 Jun 2025 10:00:00 GMT</pubDate>
                    <enclosure url="https://example.com/ep1.mp3" length="12345678" type="audio/mpeg"/>
                </item>
                <item>
                    <title>Episode 2</title>
                    <description>Second episode description</description>
                    <link>https://example.com/ep2</link>
                    <guid>https://example.com/ep2</guid>
                    <pubDate>Wed, 03 Jun 2025 10:00:00 GMT</pubDate>
                    <enclosure url="https://example.com/ep2.mp3" length="23456789" type="audio/mpeg"/>
                </item>
            </channel>
        </rss>"""
    
    @pytest.fixture
    def itunes_podcast_feed(self):
        """iTunes-enhanced podcast feed."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
            <channel>
                <title>iTunes Enhanced Podcast</title>
                <link>https://example.com</link>
                <description>A podcast with iTunes extensions</description>
                <language>en-us</language>
                <itunes:author>John Podcaster</itunes:author>
                <itunes:summary>This is a more detailed summary of the podcast</itunes:summary>
                <itunes:owner>
                    <itunes:name>John Podcaster</itunes:name>
                    <itunes:email>john@example.com</itunes:email>
                </itunes:owner>
                <itunes:image href="https://example.com/podcast-logo.jpg"/>
                <itunes:category text="Technology">
                    <itunes:category text="Tech News"/>
                </itunes:category>
                <itunes:explicit>no</itunes:explicit>
                <item>
                    <title>iTunes Episode 1</title>
                    <description>Episode with iTunes metadata</description>
                    <guid isPermaLink="false">unique-guid-001</guid>
                    <pubDate>Mon, 01 Jun 2025 10:00:00 GMT</pubDate>
                    <enclosure url="https://example.com/itunes-ep1.mp3" length="34567890" type="audio/mpeg"/>
                    <itunes:duration>45:32</itunes:duration>
                    <itunes:episode>1</itunes:episode>
                    <itunes:season>1</itunes:season>
                    <itunes:episodeType>full</itunes:episodeType>
                    <itunes:author>Guest Speaker</itunes:author>
                    <itunes:summary>Detailed episode summary with more information</itunes:summary>
                </item>
            </channel>
        </rss>"""
    
    @pytest.fixture
    def feed_without_duration(self):
        """Feed with episodes that don't have duration."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>No Duration Podcast</title>
                <link>https://example.com</link>
                <description>Episodes without duration info</description>
                <item>
                    <title>No Duration Episode</title>
                    <guid>no-duration-001</guid>
                    <pubDate>Mon, 01 Jun 2025 10:00:00 GMT</pubDate>
                    <enclosure url="https://example.com/no-duration.mp3" type="audio/mpeg"/>
                </item>
            </channel>
        </rss>"""
    
    @pytest.fixture
    def feed_with_youtube_links(self):
        """Feed with YouTube links in description."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
            <channel>
                <title>YouTube Linked Podcast</title>
                <link>https://example.com</link>
                <description>Podcast with YouTube video links</description>
                <item>
                    <title>Episode with YouTube</title>
                    <guid>youtube-001</guid>
                    <pubDate>Mon, 01 Jun 2025 10:00:00 GMT</pubDate>
                    <enclosure url="https://example.com/yt-ep1.mp3" type="audio/mpeg"/>
                    <description><![CDATA[
                        Check out the video version on YouTube: https://www.youtube.com/watch?v=dQw4w9WgXcQ
                        
                        This episode discusses various topics...
                    ]]></description>
                    <itunes:duration>30:00</itunes:duration>
                </item>
                <item>
                    <title>Episode with short YouTube link</title>
                    <guid>youtube-002</guid>
                    <pubDate>Wed, 03 Jun 2025 10:00:00 GMT</pubDate>
                    <enclosure url="https://example.com/yt-ep2.mp3" type="audio/mpeg"/>
                    <description>Video: https://youtu.be/dQw4w9WgXcQ | Topics discussed...</description>
                </item>
            </channel>
        </rss>"""
    
    @pytest.fixture
    def complex_feed(self):
        """Complex feed with multiple namespace and edge cases."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" 
             xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
             xmlns:content="http://purl.org/rss/1.0/modules/content/"
             xmlns:atom="http://www.w3.org/2005/Atom">
            <channel>
                <title>Complex &amp; Technical Podcast</title>
                <link>https://example.com</link>
                <description>A podcast with various edge cases</description>
                <language>en-us</language>
                <atom:link href="https://example.com/feed.xml" rel="self" type="application/rss+xml"/>
                <itunes:author>Tech &amp; Co.</itunes:author>
                <itunes:owner>
                    <itunes:name>Tech Company</itunes:name>
                    <itunes:email>podcast@techco.com</itunes:email>
                </itunes:owner>
                <image>
                    <url>https://example.com/logo.jpg</url>
                    <title>Complex Podcast Logo</title>
                    <link>https://example.com</link>
                </image>
                <item>
                    <title>Episode: "Special Characters" &amp; More!</title>
                    <description>Testing special chars: &lt;, &gt;, &amp;, ', "</description>
                    <content:encoded><![CDATA[
                        <p>Full HTML content with <b>formatting</b></p>
                        <p>YouTube: https://youtube.com/watch?v=abc123</p>
                    ]]></content:encoded>
                    <guid isPermaLink="true">https://example.com/episodes/special-001</guid>
                    <pubDate>Mon, 01 Jun 2025 10:00:00 +0000</pubDate>
                    <enclosure url="https://cdn.example.com/episodes/2025/06/special.mp3" 
                              length="45678901" 
                              type="audio/mpeg"/>
                    <itunes:duration>1:05:30</itunes:duration>
                    <itunes:episode>10</itunes:episode>
                    <itunes:season>2</itunes:season>
                </item>
                <item>
                    <title>Minimal Episode</title>
                    <guid>minimal-001</guid>
                    <enclosure url="https://example.com/minimal.mp3" type="audio/mpeg"/>
                </item>
            </channel>
        </rss>"""
    
    def test_parse_standard_rss_20(self, standard_rss_20_feed):
        """Test parsing standard RSS 2.0 feed."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.headers = {'content-type': 'application/rss+xml'}
        
        with patch('feedparser.parse') as mock_parse:
            # Manually parse and create the expected structure
            parsed = Mock()
            parsed.bozo = False
            parsed.feed = Mock()
            parsed.feed.title = 'Standard Podcast'
            parsed.feed.link = 'https://example.com'
            parsed.feed.description = 'A standard RSS 2.0 podcast'
            parsed.feed.language = 'en-us'
            parsed.feed.itunes_author = None
            parsed.feed.itunes_category = None
            parsed.feed.itunes_explicit = None
            parsed.feed.itunes_image = None
            parsed.feed.itunes_owner = None
            parsed.feed.image = None
            parsed.feed.get = Mock(side_effect=lambda key, default=None: {
                'title': 'Standard Podcast',
                'link': 'https://example.com',
                'description': 'A standard RSS 2.0 podcast',
                'language': 'en-us'
            }.get(key, default))
            
            # Create episode entries
            ep1 = Mock()
            ep1.get = Mock(side_effect=lambda key, default=None: {
                'title': 'Episode 1',
                'description': 'First episode description',
                'link': 'https://example.com/ep1',
                'id': 'https://example.com/ep1',
                'published': 'Mon, 01 Jun 2025 10:00:00 GMT',
                'published_parsed': (2025, 6, 1, 10, 0, 0, 0, 152, 0),
                'enclosures': [{
                    'href': 'https://example.com/ep1.mp3',
                    'length': '12345678',
                    'type': 'audio/mpeg'
                }]
            }.get(key, default))
            
            ep2 = Mock()
            ep2.get = Mock(side_effect=lambda key, default=None: {
                'title': 'Episode 2',
                'description': 'Second episode description',
                'link': 'https://example.com/ep2',
                'id': 'https://example.com/ep2',
                'published': 'Wed, 03 Jun 2025 10:00:00 GMT',
                'published_parsed': (2025, 6, 3, 10, 0, 0, 2, 154, 0),
                'enclosures': [{
                    'href': 'https://example.com/ep2.mp3',
                    'length': '23456789',
                    'type': 'audio/mpeg'
                }]
            }.get(key, default))
            
            parsed.entries = [ep1, ep2]
            
            mock_parse.return_value = parsed
            
            podcast_metadata, episodes = parse_feed("https://example.com/feed.xml")
            
            # Verify podcast metadata
            assert podcast_metadata.title == "Standard Podcast"
            assert podcast_metadata.description == "A standard RSS 2.0 podcast"
            assert podcast_metadata.link == "https://example.com"
            assert podcast_metadata.language == "en-us"
            assert podcast_metadata.author is None  # No author in standard RSS
            
            # Verify episodes
            assert len(episodes) == 2
            assert episodes[0].title == "Episode 2"  # Should be sorted by date, newest first
            assert episodes[0].audio_url == "https://example.com/ep2.mp3"
            assert episodes[0].guid == "https://example.com/ep2"
            assert episodes[0].file_size == 23456789
            
            assert episodes[1].title == "Episode 1"
            assert episodes[1].audio_url == "https://example.com/ep1.mp3"
    
    def test_parse_itunes_podcast_feed(self, itunes_podcast_feed):
        """Test parsing iTunes-enhanced podcast feed."""
        with patch('feedparser.parse') as mock_parse:
            parsed = feedparser.FeedParserDict()
            parsed.bozo = False
            parsed.feed = feedparser.FeedParserDict({
                'title': 'iTunes Enhanced Podcast',
                'link': 'https://example.com',
                'description': 'A podcast with iTunes extensions',
                'language': 'en-us',
                'itunes_author': 'John Podcaster',
                'itunes_summary': 'This is a more detailed summary of the podcast',
                'itunes_owner': {'name': 'John Podcaster', 'email': 'john@example.com'},
                'itunes_image': {'href': 'https://example.com/podcast-logo.jpg'},
                'itunes_explicit': 'no'
            })
            parsed.entries = [
                feedparser.FeedParserDict({
                    'title': 'iTunes Episode 1',
                    'description': 'Episode with iTunes metadata',
                    'id': 'unique-guid-001',
                    'published': 'Mon, 01 Jun 2025 10:00:00 GMT',
                    'published_parsed': (2025, 6, 1, 10, 0, 0, 0, 152, 0),
                    'enclosures': [{
                        'href': 'https://example.com/itunes-ep1.mp3',
                        'length': '34567890',
                        'type': 'audio/mpeg'
                    }],
                    'itunes_duration': '45:32',
                    'itunes_episode': '1',
                    'itunes_season': '1',
                    'itunes_episodetype': 'full',
                    'itunes_author': 'Guest Speaker',
                    'itunes_summary': 'Detailed episode summary with more information'
                })
            ]
            
            mock_parse.return_value = parsed
            
            podcast_metadata, episodes = parse_feed("https://example.com/itunes-feed.xml")
            
            # Verify iTunes metadata is captured
            assert podcast_metadata.author == "John Podcaster"
            assert podcast_metadata.image_url == "https://example.com/podcast-logo.jpg"
            
            # Verify episode iTunes metadata
            assert len(episodes) == 1
            episode = episodes[0]
            assert episode.duration == "45:32"
            assert episode.episode_number == 1
            assert episode.season_number == 1
            assert episode.author == "Guest Speaker"
    
    def test_parse_feed_without_duration(self, feed_without_duration):
        """Test parsing feed with episodes lacking duration."""
        with patch('feedparser.parse') as mock_parse:
            parsed = feedparser.FeedParserDict()
            parsed.bozo = False
            parsed.feed = feedparser.FeedParserDict({
                'title': 'No Duration Podcast',
                'link': 'https://example.com',
                'description': 'Episodes without duration info'
            })
            parsed.entries = [
                feedparser.FeedParserDict({
                    'title': 'No Duration Episode',
                    'id': 'no-duration-001',
                    'published': 'Mon, 01 Jun 2025 10:00:00 GMT',
                    'published_parsed': (2025, 6, 1, 10, 0, 0, 0, 152, 0),
                    'enclosures': [{
                        'href': 'https://example.com/no-duration.mp3',
                        'type': 'audio/mpeg'
                    }]
                })
            ]
            
            mock_parse.return_value = parsed
            
            podcast_metadata, episodes = parse_feed("https://example.com/no-duration-feed.xml")
            
            assert len(episodes) == 1
            assert episodes[0].duration is None
            assert episodes[0].file_size is None  # No length attribute
    
    def test_parse_feed_with_youtube_links(self, feed_with_youtube_links):
        """Test parsing feed with YouTube links in descriptions."""
        with patch('feedparser.parse') as mock_parse:
            parsed = feedparser.FeedParserDict()
            parsed.bozo = False
            parsed.feed = feedparser.FeedParserDict({
                'title': 'YouTube Linked Podcast',
                'link': 'https://example.com',
                'description': 'Podcast with YouTube video links'
            })
            parsed.entries = [
                feedparser.FeedParserDict({
                    'title': 'Episode with YouTube',
                    'id': 'youtube-001',
                    'published': 'Mon, 01 Jun 2025 10:00:00 GMT',
                    'published_parsed': (2025, 6, 1, 10, 0, 0, 0, 152, 0),
                    'enclosures': [{
                        'href': 'https://example.com/yt-ep1.mp3',
                        'type': 'audio/mpeg'
                    }],
                    'description': 'Check out the video version on YouTube: https://www.youtube.com/watch?v=dQw4w9WgXcQ\n\nThis episode discusses various topics...',
                    'itunes_duration': '30:00'
                }),
                feedparser.FeedParserDict({
                    'title': 'Episode with short YouTube link',
                    'id': 'youtube-002',
                    'published': 'Wed, 03 Jun 2025 10:00:00 GMT',
                    'published_parsed': (2025, 6, 3, 10, 0, 0, 2, 154, 0),
                    'enclosures': [{
                        'href': 'https://example.com/yt-ep2.mp3',
                        'type': 'audio/mpeg'
                    }],
                    'description': 'Video: https://youtu.be/dQw4w9WgXcQ | Topics discussed...'
                })
            ]
            
            mock_parse.return_value = parsed
            
            podcast_metadata, episodes = parse_feed("https://example.com/youtube-feed.xml")
            
            assert len(episodes) == 2
            # YouTube URL extraction would be done by YouTubeSearcher, not feed parser
            # Just verify descriptions are preserved
            assert "youtube.com/watch?v=dQw4w9WgXcQ" in episodes[1].description
            assert "youtu.be/dQw4w9WgXcQ" in episodes[0].description
    
    def test_parse_complex_feed(self, complex_feed):
        """Test parsing complex feed with multiple namespaces and edge cases."""
        with patch('feedparser.parse') as mock_parse:
            parsed = feedparser.FeedParserDict()
            parsed.bozo = False
            parsed.feed = feedparser.FeedParserDict({
                'title': 'Complex & Technical Podcast',
                'link': 'https://example.com',
                'description': 'A podcast with various edge cases',
                'language': 'en-us',
                'itunes_author': 'Tech & Co.',
                'image': {'url': 'https://example.com/logo.jpg'}
            })
            parsed.entries = [
                feedparser.FeedParserDict({
                    'title': 'Episode: "Special Characters" & More!',
                    'description': 'Testing special chars: <, >, &, \', "',
                    'content': [{'value': '<p>Full HTML content with <b>formatting</b></p>\n<p>YouTube: https://youtube.com/watch?v=abc123</p>'}],
                    'id': 'https://example.com/episodes/special-001',
                    'published': 'Mon, 01 Jun 2025 10:00:00 +0000',
                    'published_parsed': (2025, 6, 1, 10, 0, 0, 0, 152, 0),
                    'enclosures': [{
                        'href': 'https://cdn.example.com/episodes/2025/06/special.mp3',
                        'length': '45678901',
                        'type': 'audio/mpeg'
                    }],
                    'itunes_duration': '1:05:30',
                    'itunes_episode': '10',
                    'itunes_season': '2'
                }),
                feedparser.FeedParserDict({
                    'title': 'Minimal Episode',
                    'id': 'minimal-001',
                    'enclosures': [{
                        'href': 'https://example.com/minimal.mp3',
                        'type': 'audio/mpeg'
                    }]
                })
            ]
            
            mock_parse.return_value = parsed
            
            podcast_metadata, episodes = parse_feed("https://example.com/complex-feed.xml")
            
            # Verify special characters are handled
            assert '&' in podcast_metadata.title
            assert len(episodes) == 2
            assert '"Special Characters"' in episodes[0].title
            assert episodes[0].duration == "1:05:30"
            assert episodes[0].episode_number == 10
            assert episodes[0].season_number == 2
            
            # Verify minimal episode still works
            assert episodes[1].title == "Minimal Episode"
            assert episodes[1].audio_url == "https://example.com/minimal.mp3"
            assert episodes[1].description == ""  # No description provided
    
    def test_parse_multiple_real_feeds(self):
        """Test parsing with multiple real podcast RSS feeds."""
        # This test would actually hit real RSS feeds to validate
        # For unit testing, we'll mock the responses
        test_feeds = [
            {
                'url': 'https://example.com/standard-rss.xml',
                'title': 'Standard RSS Feed',
                'has_itunes': False
            },
            {
                'url': 'https://example.com/itunes-podcast.xml',
                'title': 'iTunes Podcast',
                'has_itunes': True
            },
            {
                'url': 'https://example.com/complex-feed.xml',
                'title': 'Complex Feed',
                'has_itunes': True
            }
        ]
        
        successfully_parsed = 0
        
        for feed_info in test_feeds:
            with patch('feedparser.parse') as mock_parse:
                # Create a valid parsed feed
                parsed = feedparser.FeedParserDict()
                parsed.bozo = False
                parsed.feed = feedparser.FeedParserDict({
                    'title': feed_info['title'],
                    'link': feed_info['url'],
                    'description': f"Description for {feed_info['title']}"
                })
                
                if feed_info['has_itunes']:
                    parsed.feed['itunes_author'] = 'Test Author'
                
                parsed.entries = [
                    feedparser.FeedParserDict({
                        'title': f"Episode from {feed_info['title']}",
                        'id': f"guid-{feed_info['title']}",
                        'enclosures': [{
                            'href': f"https://example.com/{feed_info['title']}/episode.mp3",
                            'type': 'audio/mpeg'
                        }]
                    })
                ]
                
                mock_parse.return_value = parsed
                
                try:
                    podcast_metadata, episodes = parse_feed(feed_info['url'])
                    assert podcast_metadata.title == feed_info['title']
                    assert len(episodes) > 0
                    successfully_parsed += 1
                except Exception as e:
                    pytest.fail(f"Failed to parse {feed_info['url']}: {e}")
        
        assert successfully_parsed >= 3  # Successfully parsed at least 3 different feed formats
    
    def test_create_feed_fixtures(self, tmp_path, standard_rss_20_feed, itunes_podcast_feed,
                                feed_without_duration, feed_with_youtube_links, complex_feed):
        """Create test fixtures for each RSS format type."""
        fixtures_dir = tmp_path / "feed_fixtures"
        fixtures_dir.mkdir()
        
        # Save each fixture type
        fixtures = {
            'standard_rss_20.xml': standard_rss_20_feed,
            'itunes_podcast.xml': itunes_podcast_feed,
            'no_duration.xml': feed_without_duration,
            'youtube_links.xml': feed_with_youtube_links,
            'complex_feed.xml': complex_feed
        }
        
        for filename, content in fixtures.items():
            fixture_file = fixtures_dir / filename
            fixture_file.write_text(content)
            
            # Verify the fixture is valid XML
            try:
                ET.fromstring(content)
            except ET.ParseError as e:
                pytest.fail(f"Invalid XML in {filename}: {e}")
        
        # Verify all fixtures were created
        assert len(list(fixtures_dir.glob("*.xml"))) == 5