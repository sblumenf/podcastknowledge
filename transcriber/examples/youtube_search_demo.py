#!/usr/bin/env python3
"""Demonstration of YouTube URL extraction from RSS feeds."""

import re
import xml.etree.ElementTree as ET
from typing import Optional, List

# Sample RSS content from the Mel Robbins podcast
SAMPLE_RSS_DESCRIPTION = """
<p>This is an encore episode with new insights!</p>
<p>Have you heard about "The Let Them" Theory?</p>
<p>You may have heard Mel talk about her new approach to life, but today, you'll hear the story of how and when she discovered it.</p>
<p>It's profound: there are only two things in life you can control.</p>
<ul>
  <li><a href="https://www.amazon.com/dp/1401971369?tag=lnk0001-20&geniuslink=true" target="_blank">Get Mel's #1 bestselling book, The Let Them Theory</a></li>
  <li><a href="https://bit.ly/45OWCNr" target="_blank">Watch the episodes on YouTube</a></li>
  <li><a href="https://bit.ly/3QfG8bb" target="_blank">Follow Mel on Instagram</a></li>
  <li><a href="https://bit.ly/49bg4GP" target="_blank">Follow The Mel Robbins Podcast on Instagram</a></li>
</ul>
"""

# YouTube URL patterns from youtube_searcher.py
YOUTUBE_PATTERNS = [
    r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
    r'https?://(?:www\.)?youtu\.be/[\w-]+',
    r'https?://(?:www\.)?youtube\.com/embed/[\w-]+',
    r'https?://(?:m\.)?youtube\.com/watch\?v=[\w-]+',
    r'https?://(?:music\.)?youtube\.com/watch\?v=[\w-]+'
]

def extract_youtube_url(text: str) -> Optional[str]:
    """Extract YouTube URL using the same logic as YouTubeSearcher."""
    for pattern in YOUTUBE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return matches[0]
    return None

def find_all_urls(text: str) -> List[str]:
    """Find ALL URLs in the text for comparison."""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+(?:\.[^\s<>"{}|\\^`\[\]]+)*'
    return re.findall(url_pattern, text)

def demonstrate_extraction():
    """Show what happens when extracting from the RSS feed."""
    print("=== YouTube URL Extraction Demo ===\n")
    
    print("1. RSS Description Content:")
    print("-" * 50)
    print(SAMPLE_RSS_DESCRIPTION[:200] + "...\n")
    
    print("2. All URLs found in the description:")
    print("-" * 50)
    all_urls = find_all_urls(SAMPLE_RSS_DESCRIPTION)
    for i, url in enumerate(all_urls, 1):
        print(f"   {i}. {url}")
    
    print("\n3. YouTube URL patterns being searched:")
    print("-" * 50)
    for i, pattern in enumerate(YOUTUBE_PATTERNS, 1):
        print(f"   {i}. {pattern}")
    
    print("\n4. Extraction result:")
    print("-" * 50)
    youtube_url = extract_youtube_url(SAMPLE_RSS_DESCRIPTION)
    if youtube_url:
        print(f"   ✓ Found: {youtube_url}")
    else:
        print("   ✗ No YouTube URL found!")
        print("\n   Why? None of the URLs match the YouTube patterns:")
        for url in all_urls:
            if 'bit.ly' in url:
                print(f"   - {url} is a shortened URL (not a YouTube pattern)")
            else:
                print(f"   - {url} doesn't match YouTube domains")
    
    print("\n5. What would need to match:")
    print("-" * 50)
    print("   Examples of URLs that WOULD be found:")
    print("   - https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    print("   - https://youtu.be/dQw4w9WgXcQ")
    print("   - https://youtube.com/embed/dQw4w9WgXcQ")
    
    print("\n6. The actual YouTube link:")
    print("-" * 50)
    print("   The bit.ly/45OWCNr link redirects to:")
    print("   → https://www.youtube.com/melrobbins (channel page)")
    print("   This is NOT a video URL, so even if we followed redirects,")
    print("   it wouldn't help find the specific episode video.")

if __name__ == "__main__":
    demonstrate_extraction()