#!/usr/bin/env python3
"""
Check Neo4j database for Mel Robbins podcast episodes and their YouTube URLs.
Provides detailed analysis of which episodes have or are missing YouTube URLs.
"""

import os
import sys
from neo4j import GraphDatabase
from typing import Dict, List, Optional, Tuple
import json

class MelRobbinsYouTubeChecker:
    def __init__(self):
        """Initialize database connection parameters."""
        # Get connection parameters from environment or use defaults
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "changeme")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
        
        # Initialize driver
        self.driver = None
        
    def connect(self) -> bool:
        """Establish connection to Neo4j database."""
        try:
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password)
            )
            # Test connection
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
            print(f"✓ Successfully connected to Neo4j at {self.uri} (database: {self.database})")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to Neo4j: {e}")
            print(f"  URI: {self.uri}")
            print(f"  Database: {self.database}")
            print(f"  Username: {self.username}")
            return False
    
    def get_episode_stats(self) -> Dict:
        """Get overall statistics about Mel Robbins episodes."""
        with self.driver.session(database=self.database) as session:
            # Total episodes
            total_result = session.run("""
                MATCH (e:Episode)
                RETURN count(e) as total
            """)
            total = total_result.single()["total"]
            
            # Episodes with YouTube URLs
            with_youtube_result = session.run("""
                MATCH (e:Episode)
                WHERE e.youtube_url IS NOT NULL AND e.youtube_url <> ''
                RETURN count(e) as count
            """)
            with_youtube = with_youtube_result.single()["count"]
            
            # Episodes without YouTube URLs
            without_youtube_result = session.run("""
                MATCH (e:Episode)
                WHERE e.youtube_url IS NULL OR e.youtube_url = ''
                RETURN count(e) as count
            """)
            without_youtube = without_youtube_result.single()["count"]
            
            return {
                "total": total,
                "with_youtube": with_youtube,
                "without_youtube": without_youtube,
                "percentage_with_youtube": (with_youtube / total * 100) if total > 0 else 0
            }
    
    def get_episodes_missing_youtube(self, limit: int = 10) -> List[Dict]:
        """Get details of episodes missing YouTube URLs."""
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (e:Episode)
                WHERE e.youtube_url IS NULL OR e.youtube_url = ''
                RETURN e.title as title, 
                       e.episode_number as episode_number,
                       e.publication_date as publication_date,
                       e.duration as duration,
                       e.description as description
                ORDER BY e.episode_number DESC
                LIMIT $limit
            """, limit=limit)
            
            episodes = []
            for record in result:
                episodes.append({
                    "title": record["title"],
                    "episode_number": record["episode_number"],
                    "publication_date": record["publication_date"],
                    "duration": record["duration"],
                    "description": record["description"][:100] + "..." if record["description"] and len(record["description"]) > 100 else record["description"]
                })
            
            return episodes
    
    def get_sample_episodes_with_youtube(self, limit: int = 5) -> List[Dict]:
        """Get sample of episodes that have YouTube URLs."""
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (e:Episode)
                WHERE e.youtube_url IS NOT NULL AND e.youtube_url <> ''
                RETURN e.title as title,
                       e.youtube_url as youtube_url,
                       e.episode_number as episode_number,
                       e.publication_date as publication_date
                ORDER BY e.episode_number DESC
                LIMIT $limit
            """, limit=limit)
            
            episodes = []
            for record in result:
                episodes.append({
                    "title": record["title"],
                    "youtube_url": record["youtube_url"],
                    "episode_number": record["episode_number"],
                    "publication_date": record["publication_date"]
                })
            
            return episodes
    
    def analyze_youtube_url_patterns(self) -> Dict:
        """Analyze patterns in YouTube URLs to understand their format."""
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (e:Episode)
                WHERE e.youtube_url IS NOT NULL AND e.youtube_url <> ''
                RETURN e.youtube_url as url
            """)
            
            patterns = {
                "youtube.com/watch": 0,
                "youtu.be": 0,
                "youtube.com/embed": 0,
                "other": 0,
                "sample_urls": []
            }
            
            for record in result:
                url = record["url"]
                if "youtube.com/watch" in url:
                    patterns["youtube.com/watch"] += 1
                elif "youtu.be" in url:
                    patterns["youtu.be"] += 1
                elif "youtube.com/embed" in url:
                    patterns["youtube.com/embed"] += 1
                else:
                    patterns["other"] += 1
                
                # Collect some sample URLs
                if len(patterns["sample_urls"]) < 3:
                    patterns["sample_urls"].append(url)
            
            return patterns
    
    def check_episode_metadata_completeness(self) -> Dict:
        """Check overall metadata completeness for episodes."""
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (e:Episode)
                RETURN 
                    count(e) as total,
                    count(e.title) as has_title,
                    count(e.episode_number) as has_episode_number,
                    count(e.publication_date) as has_publication_date,
                    count(e.duration) as has_duration,
                    count(e.description) as has_description,
                    count(e.youtube_url) as has_youtube_url
            """)
            
            record = result.single()
            total = record["total"]
            
            return {
                "total_episodes": total,
                "metadata_completeness": {
                    "title": (record["has_title"] / total * 100) if total > 0 else 0,
                    "episode_number": (record["has_episode_number"] / total * 100) if total > 0 else 0,
                    "publication_date": (record["has_publication_date"] / total * 100) if total > 0 else 0,
                    "duration": (record["has_duration"] / total * 100) if total > 0 else 0,
                    "description": (record["has_description"] / total * 100) if total > 0 else 0,
                    "youtube_url": (record["has_youtube_url"] / total * 100) if total > 0 else 0
                }
            }
    
    def run_analysis(self):
        """Run complete analysis and display results."""
        print("\n" + "="*60)
        print("MEL ROBBINS PODCAST - YOUTUBE URL ANALYSIS")
        print("="*60 + "\n")
        
        # Get episode statistics
        stats = self.get_episode_stats()
        print(f"📊 EPISODE STATISTICS:")
        print(f"   Total episodes: {stats['total']}")
        print(f"   Episodes with YouTube URLs: {stats['with_youtube']} ({stats['percentage_with_youtube']:.1f}%)")
        print(f"   Episodes missing YouTube URLs: {stats['without_youtube']} ({100 - stats['percentage_with_youtube']:.1f}%)")
        
        # Check metadata completeness
        print(f"\n📋 METADATA COMPLETENESS:")
        metadata = self.check_episode_metadata_completeness()
        for field, percentage in metadata["metadata_completeness"].items():
            status = "✓" if percentage == 100 else "⚠️" if percentage >= 90 else "✗"
            print(f"   {status} {field}: {percentage:.1f}%")
        
        # Show YouTube URL patterns
        if stats['with_youtube'] > 0:
            print(f"\n🔗 YOUTUBE URL PATTERNS:")
            patterns = self.analyze_youtube_url_patterns()
            for pattern, count in patterns.items():
                if pattern != "sample_urls" and count > 0:
                    print(f"   {pattern}: {count}")
            
            if patterns["sample_urls"]:
                print(f"\n   Sample URLs:")
                for url in patterns["sample_urls"]:
                    print(f"   - {url}")
        
        # Show sample episodes with YouTube URLs
        if stats['with_youtube'] > 0:
            print(f"\n✅ SAMPLE EPISODES WITH YOUTUBE URLs:")
            episodes_with = self.get_sample_episodes_with_youtube(5)
            for ep in episodes_with:
                print(f"   #{ep['episode_number']}: {ep['title']}")
                print(f"      URL: {ep['youtube_url']}")
                print(f"      Date: {ep['publication_date']}")
                print()
        
        # Show episodes missing YouTube URLs
        if stats['without_youtube'] > 0:
            print(f"\n❌ EPISODES MISSING YOUTUBE URLs (showing up to 10):")
            episodes_without = self.get_episodes_missing_youtube(10)
            for ep in episodes_without:
                episode_info = f"#{ep['episode_number']}: " if ep['episode_number'] else ""
                print(f"   {episode_info}{ep['title']}")
                if ep['publication_date']:
                    print(f"      Date: {ep['publication_date']}")
                if ep['duration']:
                    print(f"      Duration: {ep['duration']}")
                if ep['description']:
                    print(f"      Description: {ep['description']}")
                print()
        
        # Summary and recommendations
        print("\n" + "="*60)
        print("SUMMARY & RECOMMENDATIONS")
        print("="*60)
        
        if stats['percentage_with_youtube'] == 100:
            print("✅ EXCELLENT: All episodes have YouTube URLs!")
        elif stats['percentage_with_youtube'] >= 90:
            print(f"⚠️  GOOD: {stats['percentage_with_youtube']:.1f}% of episodes have YouTube URLs.")
            print(f"   Consider adding URLs for the remaining {stats['without_youtube']} episodes.")
        else:
            print(f"❌ NEEDS ATTENTION: Only {stats['percentage_with_youtube']:.1f}% of episodes have YouTube URLs.")
            print(f"   {stats['without_youtube']} episodes are missing YouTube URLs.")
            print("\n   Recommendations:")
            print("   1. Review the YouTube Episode Matcher configuration")
            print("   2. Run the transcriber's YouTube matching process")
            print("   3. Manually add missing URLs if needed")
    
    def close(self):
        """Close database connection."""
        if self.driver:
            self.driver.close()

def main():
    """Main execution function."""
    checker = MelRobbinsYouTubeChecker()
    
    try:
        # Connect to database
        if not checker.connect():
            sys.exit(1)
        
        # Run analysis
        checker.run_analysis()
        
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        checker.close()
    
    print("\n✓ Analysis complete!")

if __name__ == "__main__":
    main()