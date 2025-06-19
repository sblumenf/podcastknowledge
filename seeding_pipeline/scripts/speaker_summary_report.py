#!/usr/bin/env python3
"""
Generate a comprehensive speaker summary report from the knowledge graph database.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from typing import Dict, List, Tuple
import json
from collections import defaultdict
from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig
from src.utils.logging import get_logger

logger = get_logger(__name__)


def get_speaker_statistics(storage: GraphStorageService) -> List[Dict]:
    """Get comprehensive statistics for each speaker."""
    
    # First get all speaker distributions
    query = """
    MATCH (mu:MeaningfulUnit)-[:PART_OF]->(e:Episode)
    WHERE mu.speaker_distribution IS NOT NULL
    RETURN mu.speaker_distribution as speaker_dist,
           mu.text as text,
           e.title as episode_title,
           e.id as episode_id
    """
    
    results = storage.query(query)
    
    # Process results to extract speaker statistics
    speaker_data = defaultdict(lambda: {
        'units': 0,
        'episodes': set(),
        'total_text_length': 0,
        'texts': []
    })
    
    for r in results:
        speaker_dist = r['speaker_dist']
        text = r['text'] or ""
        episode_title = r['episode_title'] or "Untitled"
        
        # Parse speaker distribution
        speakers = {}
        try:
            if isinstance(speaker_dist, str) and speaker_dist.startswith('{'):
                speakers = json.loads(speaker_dist.replace("'", '"'))
            else:
                # Single speaker format
                speakers = {speaker_dist: 100.0}
        except:
            continue
            
        # Update statistics for each speaker
        for speaker_name in speakers.keys():
            if speaker_name and not speaker_name.startswith('{'):
                speaker_data[speaker_name]['units'] += 1
                speaker_data[speaker_name]['episodes'].add(episode_title)
                speaker_data[speaker_name]['total_text_length'] += len(text)
                speaker_data[speaker_name]['texts'].append(text)
    
    # Convert to list of statistics
    speaker_stats = []
    for speaker_name, data in speaker_data.items():
        # Calculate average text length
        avg_length = data['total_text_length'] / data['units'] if data['units'] > 0 else 0
        
        # Determine speaker type
        speaker_type = "Named"
        if any(generic in speaker_name.lower() for generic in ['speaker', 'guest', 'host', 'contributor', 'producer']):
            if not any(char.isalpha() and char.isupper() for word in speaker_name.split() for char in word[1:]):
                speaker_type = "Generic"
        
        # Check for potential issues
        issues = []
        if len(speaker_name) < 3:
            issues.append("Too short")
        if speaker_name.lower() in ['you know what', 'brief family member', 'um', 'uh']:
            issues.append("Non-name")
        if data['units'] < 2:
            issues.append("Low contribution")
        if avg_length < 50:
            issues.append("Short utterances")
            
        speaker_stats.append({
            'name': speaker_name,
            'type': speaker_type,
            'episodes': len(data['episodes']),
            'units': data['units'],
            'avg_length': round(avg_length, 1),
            'issues': ', '.join(issues) if issues else 'None',
            'sample_episodes': list(data['episodes'])[:3]
        })
    
    # Sort by unit count descending
    speaker_stats.sort(key=lambda x: x['units'], reverse=True)
    
    return speaker_stats


def print_speaker_table(speaker_stats: List[Dict]):
    """Print speaker statistics in a formatted table."""
    
    # Define column widths
    col_widths = {
        'name': 35,
        'type': 10,
        'episodes': 10,
        'units': 10,
        'avg_length': 12,
        'issues': 25
    }
    
    # Print header
    headers = ['Speaker Name', 'Type', 'Episodes', 'Units', 'Avg Length', 'Issues']
    header_line = '| ' + ' | '.join(h.ljust(col_widths[k]) for h, k in zip(headers, col_widths.keys())) + ' |'
    separator = '+' + '+'.join('-' * (w + 2) for w in col_widths.values()) + '+'
    
    print("\n" + "="*80)
    print("SPEAKER SUMMARY REPORT")
    print("="*80 + "\n")
    
    print(separator)
    print(header_line)
    print(separator)
    
    # Print rows
    for stat in speaker_stats:
        row = [
            stat['name'][:col_widths['name']],
            stat['type'],
            str(stat['episodes']),
            str(stat['units']),
            str(stat['avg_length']),
            stat['issues'][:col_widths['issues']]
        ]
        row_line = '| ' + ' | '.join(val.ljust(col_widths[k]) for val, k in zip(row, col_widths.keys())) + ' |'
        print(row_line)
    
    print(separator)
    
    # Print summary statistics
    print(f"\nTotal speakers: {len(speaker_stats)}")
    named_count = sum(1 for s in speaker_stats if s['type'] == 'Named')
    generic_count = sum(1 for s in speaker_stats if s['type'] == 'Generic')
    issue_count = sum(1 for s in speaker_stats if s['issues'] != 'None')
    
    print(f"Named speakers: {named_count}")
    print(f"Generic speakers: {generic_count}")
    print(f"Speakers with issues: {issue_count}")
    
    # Show detailed issues
    if issue_count > 0:
        print("\n" + "="*80)
        print("SPEAKERS REQUIRING ATTENTION")
        print("="*80 + "\n")
        
        for stat in speaker_stats:
            if stat['issues'] != 'None':
                print(f"- {stat['name']}: {stat['issues']}")
                if stat['units'] < 5:
                    print(f"  Sample episodes: {', '.join(stat['sample_episodes'][:2]) if stat['sample_episodes'] else 'N/A'}")


def main():
    """Main function."""
    config = PipelineConfig()
    storage = GraphStorageService(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password,
        database=config.neo4j_database
    )
    
    try:
        # Get speaker statistics
        speaker_stats = get_speaker_statistics(storage)
        
        if not speaker_stats:
            print("No speakers found in database.")
            return
        
        # Print the table
        print_speaker_table(speaker_stats)
        
    except Exception as e:
        logger.error(f"Error generating speaker report: {str(e)}")
        print(f"Error: {str(e)}")
    finally:
        storage.close()


if __name__ == "__main__":
    main()