#!/usr/bin/env python3
"""Generate speaker report in table format showing episodes and their speakers."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import json
from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig

def generate_speaker_table_report():
    """Generate table format report of episodes and speakers."""
    config = PipelineConfig()
    storage = GraphStorageService(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password,
        database=config.neo4j_database
    )
    
    try:
        # Query for all episodes and their speakers
        query = """
        MATCH (e:Episode)
        OPTIONAL MATCH (mu:MeaningfulUnit)-[:PART_OF]->(e)
        WHERE mu.speaker_distribution IS NOT NULL
        WITH e, collect(DISTINCT mu.speaker_distribution) as speaker_patterns
        RETURN e.id as episode_id,
               e.title as title,
               e.youtube_url as youtube_url,
               speaker_patterns
        ORDER BY e.title
        """
        
        results = storage.query(query)
        
        if not results:
            print("No episodes found in database.")
            return
        
        # Process results to extract unique speakers per episode
        table_data = []
        for r in results:
            # Extract unique speakers from patterns
            speakers_set = set()
            for pattern in r['speaker_patterns']:
                if pattern:
                    # Handle JSON speaker format
                    try:
                        if isinstance(pattern, str) and pattern.startswith('{'):
                            speaker_dict = json.loads(pattern.replace("'", '"'))
                            speakers_set.update(speaker_dict.keys())
                        else:
                            # Simple string format
                            speakers_set.add(pattern)
                    except:
                        speakers_set.add(str(pattern))
            
            # Sort speakers for consistent display
            speakers_list = sorted(list(speakers_set))
            speakers_str = "; ".join(speakers_list) if speakers_list else "No speakers identified"
            
            episode_id = r['episode_id']
            # Shorten long episode IDs
            if len(episode_id) > 35:
                episode_id = episode_id[:32] + '...'
            
            table_data.append([
                episode_id,
                r['title'] or 'Untitled',
                r['youtube_url'] or 'N/A',
                speakers_str
            ])
        
        # Print table
        print("\nSpeaker CLI Report (Table Format)")
        print("=" * 220)
        
        # Table headers
        headers = ['Episode ID', 'Title', 'YouTube URL', 'Speakers']
        col_widths = [35, 70, 50, 60]
        
        # Print header
        header_line = '| ' + ' | '.join(h.ljust(w) for h, w in zip(headers, col_widths)) + ' |'
        separator = '|' + '|'.join('-' * (w + 2) for w in col_widths) + '|'
        
        print(separator)
        print(header_line)
        print(separator)
        
        # Print rows
        for row in table_data:
            # Format each cell
            formatted_cells = []
            for cell, width in zip(row, col_widths):
                cell_str = str(cell)
                if len(cell_str) > width:
                    cell_str = cell_str[:width-3] + '...'
                formatted_cells.append(cell_str.ljust(width))
            
            row_line = '| ' + ' | '.join(formatted_cells) + ' |'
            print(row_line)
        
        print(separator)
        print(f"\nTotal episodes: {len(table_data)}")
        
    except Exception as e:
        print(f"Error generating report: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        storage.close()

if __name__ == "__main__":
    generate_speaker_table_report()