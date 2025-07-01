#!/usr/bin/env python3
"""
Extract themes from existing episodes in the database without full reprocessing.

This script reads MeaningfulUnits from episodes already in Neo4j and uses the
conversation analyzer to extract themes, then creates Topic nodes and relationships.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.graph_storage import GraphStorageService
from src.services.llm import LLMService
from src.services.llm_factory import LLMServiceFactory
from src.config.podcast_config_loader import get_podcast_config_loader
from src.config.podcast_config_models import PodcastConfig
from src.core.config import PipelineConfig, load_config
from src.core.env_config import env_config
from src.utils.api_key import get_gemini_api_key
from src.utils.logging import setup_logging, get_logger

# Setup logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)


class ThemeExtractor:
    """Extract themes from existing episodes without reprocessing."""
    
    def __init__(self, llm_service: LLMService):
        """Initialize theme extractor with LLM service.
        
        Args:
            llm_service: LLM service for theme extraction (Gemini 2.5 Pro)
        """
        self.llm_service = llm_service
        self.logger = logger
        # Load podcast registry
        self.config_loader = get_podcast_config_loader()
        self.podcast_registry = self.config_loader.load()
        
    def connect_to_podcast_db(self, podcast_config: PodcastConfig) -> GraphStorageService:
        """Connect to a specific podcast's Neo4j database.
        
        Args:
            podcast_config: Podcast configuration with database details
            
        Returns:
            GraphStorageService connected to the podcast's database
        """
        db_config = podcast_config.database
        
        # Fallback to environment if database config is missing
        if not db_config:
            self.logger.warning(f"No database config for {podcast_config.name}, using defaults")
            graph_storage = GraphStorageService(
                uri=os.getenv('NEO4J_URI', 'neo4j://localhost:7687'),
                username=os.getenv('NEO4J_USERNAME', 'neo4j'),
                password=os.getenv('NEO4J_PASSWORD', 'password'),
                database=os.getenv('NEO4J_DATABASE', 'neo4j')
            )
        else:
            # The YAML structure doesn't match Pydantic model exactly
            # Read credentials from environment or use defaults
            username = os.getenv('NEO4J_USERNAME', 'neo4j')
            password = os.getenv('NEO4J_PASSWORD', 'password')
            
            graph_storage = GraphStorageService(
                uri=db_config.uri,
                username=username,
                password=password,
                database=db_config.database_name or 'neo4j'
            )
        
        graph_storage.connect()
        
        # Extract port from URI for logging
        import re
        port_match = re.search(r':(\d+)', db_config.uri) if db_config else None
        port = port_match.group(1) if port_match else 'unknown'
        
        self.logger.info(f"Connected to database for podcast: {podcast_config.name} (port: {port})")
        return graph_storage
        
    def get_episodes_without_themes(self, graph_storage: GraphStorageService) -> List[Dict[str, Any]]:
        """Get all episodes that don't have any associated themes in a specific database.
        
        Args:
            graph_storage: Connected graph storage for a specific podcast
            
        Returns:
            List of episodes without themes
        """
        query = """
        MATCH (e:Episode)
        WHERE NOT (e)-[:HAS_TOPIC]->(:Topic)
        OPTIONAL MATCH (e)-[:PART_OF]->(p:Podcast)
        RETURN e.id AS episode_id, e.title AS title, e.description AS description,
               p.name AS podcast_name
        ORDER BY e.published_date DESC
        """
        
        results = graph_storage.query(query)
        self.logger.info(f"Found {len(results)} episodes without themes")
        return results
    
    def get_meaningful_units_for_episode(self, graph_storage: GraphStorageService, 
                                       episode_id: str) -> List[Dict[str, Any]]:
        """Get all MeaningfulUnits for an episode.
        
        Args:
            graph_storage: Connected graph storage
            episode_id: Episode ID to get units for
            
        Returns:
            List of MeaningfulUnit data
        """
        query = """
        MATCH (m:MeaningfulUnit)-[:PART_OF]->(e:Episode {id: $episode_id})
        RETURN m.id AS id, m.text AS text, m.start_time AS start_time, 
               m.end_time AS end_time, m.summary AS summary, m.unit_type AS unit_type,
               m.primary_speaker AS speaker, m.themes AS themes
        ORDER BY m.start_time
        """
        
        results = graph_storage.query(query, {'episode_id': episode_id})
        self.logger.debug(f"Found {len(results)} MeaningfulUnits for episode {episode_id}")
        return results
    
    async def extract_themes_from_units(self, units: List[Dict[str, Any]], 
                                      episode_metadata: Dict[str, Any]) -> List[str]:
        """Extract themes using LLM from all MeaningfulUnits of an episode.
        
        Args:
            units: List of MeaningfulUnit data
            episode_metadata: Episode information including title and description
            
        Returns:
            List of theme names extracted
        """
        if not units:
            return []
        
        # Build focused prompt for theme extraction
        # Truncate unit texts if too long to fit in context
        max_chars_per_unit = 500
        transcript_sections = []
        
        for unit in units[:50]:  # Limit to first 50 units to avoid context overflow
            unit_text = unit['text']
            if len(unit_text) > max_chars_per_unit:
                unit_text = unit_text[:max_chars_per_unit] + "..."
            
            timestamp = f"[{unit['start_time']:.1f}s]"
            speaker = unit.get('speaker', 'Speaker')
            transcript_sections.append(f"{timestamp} {speaker}: {unit_text}")
        
        transcript_text = "\n\n".join(transcript_sections)
        
        # Include podcast context if available
        podcast_name = episode_metadata.get('podcast_name', 'Unknown Podcast')
        
        prompt = f"""Analyze this podcast transcript and identify the main themes/topics discussed.

Podcast: {podcast_name}
Episode: {episode_metadata['title']}
Description: {episode_metadata.get('description', 'N/A')}

Transcript excerpts:
{transcript_text}

Identify 3-7 main themes or topics that are discussed in this episode. 
Focus on substantive topics that would help someone understand what this episode is about.
Be specific and descriptive. Avoid generic themes like "conversation" or "discussion".

Return a JSON object with:
{{
    "themes": [
        {{"theme": "Theme Name", "description": "Brief description of this theme in the episode"}}
    ]
}}
"""
        
        try:
            # Use Gemini 2.5 Pro for better context understanding
            response_data = self.llm_service.complete_with_options(
                prompt=prompt,
                temperature=0.3,
                json_mode=True
            )
            
            response = response_data['content']
            if isinstance(response, dict) and 'themes' in response:
                themes = [theme['theme'] for theme in response['themes']]
                self.logger.info(f"Extracted {len(themes)} themes: {themes}")
                return themes
            else:
                self.logger.warning(f"Unexpected response format: {response}")
                return []
                
        except Exception as e:
            self.logger.error(f"Failed to extract themes: {e}")
            return []
    
    async def process_episode(self, graph_storage: GraphStorageService, 
                            episode: Dict[str, Any]) -> int:
        """Process a single episode to extract and store themes.
        
        Args:
            graph_storage: Connected graph storage for the podcast
            episode: Episode data including ID and metadata
            
        Returns:
            Number of themes stored
        """
        episode_id = episode['episode_id']
        self.logger.info(f"Processing episode: {episode['title']} ({episode_id})")
        
        # Get MeaningfulUnits
        units = self.get_meaningful_units_for_episode(graph_storage, episode_id)
        if not units:
            self.logger.warning(f"No MeaningfulUnits found for episode {episode_id}")
            return 0
        
        # Extract themes
        themes = await self.extract_themes_from_units(units, episode)
        if not themes:
            self.logger.warning(f"No themes extracted for episode {episode_id}")
            return 0
        
        # Store themes
        stored_count = 0
        for theme in themes:
            success = graph_storage.create_topic_for_episode(
                topic_name=theme,
                episode_id=episode_id
            )
            if success:
                stored_count += 1
                self.logger.debug(f"Created topic: {theme}")
            else:
                self.logger.warning(f"Failed to create topic: {theme}")
        
        self.logger.info(f"Stored {stored_count} themes for episode {episode_id}")
        return stored_count
    
    async def process_single_podcast(self, podcast_id: str, limit: Optional[int] = None,
                                   episode_id: Optional[str] = None, dry_run: bool = False):
        """Process episodes for a single podcast.
        
        Args:
            podcast_id: ID of the podcast to process
            limit: Optional limit on number of episodes
            episode_id: Optional specific episode to process
            dry_run: If True, show what would be done without making changes
        """
        # Find podcast in registry
        podcast_config = self.podcast_registry.get_podcast(podcast_id)
        if not podcast_config:
            # Try to find by name
            for podcast in self.podcast_registry.podcasts:
                if podcast.name.lower() == podcast_id.lower():
                    podcast_config = podcast
                    break
        
        if not podcast_config:
            self.logger.error(f"Podcast '{podcast_id}' not found in configuration")
            return
        
        # Connect to podcast's database
        graph_storage = self.connect_to_podcast_db(podcast_config)
        
        try:
            if episode_id:
                # Process specific episode
                episode_query = """
                MATCH (e:Episode {id: $episode_id})
                OPTIONAL MATCH (e)-[:PART_OF]->(p:Podcast)
                RETURN e.id AS episode_id, e.title AS title, e.description AS description,
                       p.name AS podcast_name
                """
                episodes = graph_storage.query(episode_query, {'episode_id': episode_id})
                
                if not episodes:
                    self.logger.error(f"Episode {episode_id} not found")
                    return
                    
                if dry_run:
                    self.logger.info(f"DRY RUN: Would process episode: {episodes[0]['title']}")
                else:
                    await self.process_episode(graph_storage, episodes[0])
            else:
                # Process all episodes without themes
                episodes = self.get_episodes_without_themes(graph_storage)
                
                if limit:
                    episodes = episodes[:limit]
                
                if dry_run:
                    self.logger.info(f"DRY RUN: Would process {len(episodes)} episodes for {podcast_config.name}")
                    for ep in episodes[:5]:  # Show first 5
                        self.logger.info(f"  - {ep['title']}")
                    if len(episodes) > 5:
                        self.logger.info(f"  ... and {len(episodes) - 5} more")
                else:
                    total_themes = 0
                    for idx, episode in enumerate(episodes, 1):
                        self.logger.info(f"\nProcessing episode {idx}/{len(episodes)}")
                        theme_count = await self.process_episode(graph_storage, episode)
                        total_themes += theme_count
                    
                    self.logger.info(f"\nCompleted {podcast_config.name}: "
                                   f"Extracted {total_themes} themes from {len(episodes)} episodes")
                    
        finally:
            graph_storage.disconnect()
    
    async def process_all_podcasts(self, limit: Optional[int] = None, dry_run: bool = False):
        """Process all podcasts in the registry.
        
        Args:
            limit: Optional limit on episodes per podcast
            dry_run: If True, show what would be done without making changes
        """
        self.logger.info(f"Processing {len(self.podcast_registry.podcasts)} podcasts from registry")
        
        for podcast_config in self.podcast_registry.podcasts:
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Processing podcast: {podcast_config.name}")
            self.logger.info(f"{'='*60}")
            
            await self.process_single_podcast(
                podcast_id=podcast_config.id,
                limit=limit,
                dry_run=dry_run
            )


async def main():
    """Main execution function."""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Extract themes from existing episodes')
    parser.add_argument('--limit', type=int, help='Limit number of episodes to process per podcast')
    parser.add_argument('--episode-id', help='Process specific episode ID')
    parser.add_argument('--podcast-name', help='Process specific podcast by name or ID')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be processed without making changes')
    args = parser.parse_args()
    
    # Initialize services
    config = load_config()
    
    # Initialize LLM - Use Gemini 2.5 Pro for theme extraction
    # The model name from env should be gemini-2.0-flash-exp-2 or similar
    # but we'll override to use Pro model for better theme extraction
    llm_service = LLMServiceFactory.create_service(
        api_key=get_gemini_api_key(),
        model_name=os.getenv('GEMINI_PRO_MODEL', 'gemini-2.0-flash-exp'),
        service_type='gemini_direct',
        temperature=0.3,  # Lower temperature for consistent theme extraction
        enable_cache=True
    )
    
    # Create extractor
    extractor = ThemeExtractor(llm_service)
    
    try:
        if args.episode_id:
            # Process specific episode - need podcast context
            if not args.podcast_name:
                logger.error("--podcast-name required when using --episode-id")
                return
                
            await extractor.process_single_podcast(
                podcast_id=args.podcast_name,
                episode_id=args.episode_id,
                dry_run=args.dry_run
            )
        
        elif args.podcast_name:
            # Process specific podcast
            await extractor.process_single_podcast(
                podcast_id=args.podcast_name,
                limit=args.limit,
                dry_run=args.dry_run
            )
        
        else:
            # Process all podcasts
            await extractor.process_all_podcasts(
                limit=args.limit,
                dry_run=args.dry_run
            )
            
    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())