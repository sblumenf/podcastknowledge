"""CLI commands for viewing and updating speaker information."""

import click
import json
from typing import Optional, List, Dict, Any
# Simple table formatting without external dependencies

from src.utils.logging import get_logger
from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig
from src.post_processing.speaker_mapper import SpeakerMapper

logger = get_logger(__name__)


@click.group()
@click.pass_context
def speaker_report(ctx):
    """Manage speaker identification and reporting."""
    # Initialize configuration and storage
    config = PipelineConfig()
    storage = GraphStorageService(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password,
        database=config.neo4j_database
    )
    
    # Store in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['storage'] = storage
    ctx.obj['config'] = config
    logger.info("Initialized speaker report CLI")


@speaker_report.command()
@click.option('--format', type=click.Choice(['table', 'csv']), default='table',
              help='Output format')
@click.option('--output', type=click.Path(), help='Output file path (optional)')
@click.pass_context
def list(ctx, format: str, output: Optional[str]):
    """List all episodes and their speakers."""
    storage = ctx.obj['storage']
    
    try:
        # Query for all episodes and their speakers
        query = """
        MATCH (e:Episode)
        OPTIONAL MATCH (e)-[:HAS_MEANINGFUL_UNIT]->(mu:MeaningfulUnit)
        WHERE mu.speakers IS NOT NULL
        WITH e, collect(DISTINCT mu.speakers) as speaker_patterns
        RETURN e.podcast as podcast,
               e.episodeNumber as episode_number,
               e.title as title,
               e.episodeUrl as youtube_url,
               speaker_patterns
        ORDER BY e.podcast, e.episodeNumber
        """
        
        results = storage.query(query)
        
        if not results:
            click.echo("No episodes found in database.")
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
            if len(episode_id) > 30:
                episode_id = episode_id[:30] + '...'
            
            table_data.append([
                episode_id,
                r['title'] or 'Untitled',
                r['youtube_url'] or 'N/A',
                speakers_str
            ])
        
        # Format output
        if format == 'table':
            headers = ['Episode ID', 'Title', 'YouTube URL', 'Speakers']
            
            # Simple table formatting
            col_widths = [35, 50, 30, 50]
            
            # Format header
            header_line = '|'.join(h.ljust(w)[:w] for h, w in zip(headers, col_widths))
            separator = '+'.join('-' * w for w in col_widths)
            
            table_lines = [separator, header_line, separator]
            
            # Format rows
            for row in table_data:
                row_line = '|'.join(str(cell).ljust(w)[:w] for cell, w in zip(row, col_widths))
                table_lines.append(row_line)
            
            table_lines.append(separator)
            table = '\n'.join(table_lines)
            
            if output:
                with open(output, 'w') as f:
                    f.write(table)
                click.echo(f"Table saved to {output}")
            else:
                click.echo(table)
        
        elif format == 'csv':
            import csv
            headers = ['Podcast', 'Episode #', 'Title', 'YouTube URL', 'Speakers']
            
            if output:
                with open(output, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    writer.writerows(table_data)
                click.echo(f"CSV saved to {output}")
            else:
                # Print CSV to stdout
                import io
                csv_buffer = io.StringIO()
                writer = csv.writer(csv_buffer)
                writer.writerow(headers)
                writer.writerows(table_data)
                click.echo(csv_buffer.getvalue())
        
        logger.info(f"Listed {len(table_data)} episodes with speakers")
        
    except Exception as e:
        logger.error(f"Error listing speakers: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)
    finally:
        storage.close()


@speaker_report.command()
@click.argument('episode_id')
@click.argument('old_name')
@click.argument('new_name')
@click.option('--dry-run', is_flag=True, help='Preview changes without applying them')
@click.pass_context
def update(ctx, episode_id: str, old_name: str, new_name: str, dry_run: bool):
    """Update a speaker name in a specific episode.
    
    EPISODE_ID: The episode ID to update
    OLD_NAME: The current generic speaker name
    NEW_NAME: The new speaker name to use
    """
    storage = ctx.obj['storage']
    
    try:
        # First, check if episode exists
        check_query = """
        MATCH (e:Episode {id: $episode_id})
        RETURN e.title as title
        """
        result = storage.query(check_query, {"episode_id": episode_id})
        
        if not result:
            click.echo(f"Error: Episode '{episode_id}' not found", err=True)
            return
        
        episode_title = result[0]['title']
        
        # Find all MeaningfulUnits with the old speaker name
        preview_query = """
        MATCH (e:Episode {id: $episode_id})<-[:PART_OF]-(mu:MeaningfulUnit)
        WHERE mu.speaker_distribution CONTAINS $old_name
        RETURN count(mu) as count, collect(mu.id)[..5] as sample_units
        """
        preview_result = storage.query(preview_query, {
            "episode_id": episode_id,
            "old_name": old_name
        })
        
        if not preview_result or preview_result[0]['count'] == 0:
            click.echo(f"No units found with speaker '{old_name}' in episode '{episode_id}'")
            return
        
        unit_count = preview_result[0]['count']
        sample_units = preview_result[0]['sample_units']
        
        # Show preview
        click.echo(f"\nEpisode: {episode_title}")
        click.echo(f"Found {unit_count} units with speaker '{old_name}'")
        click.echo(f"Sample units: {', '.join(sample_units)}")
        click.echo(f"Will replace with: '{new_name}'")
        
        if dry_run:
            click.echo("\n[DRY RUN] No changes applied")
            return
        
        # Get confirmation
        if not click.confirm("\nProceed with update?"):
            click.echo("Update cancelled")
            return
        
        # Apply the update
        from src.post_processing.speaker_mapper import SpeakerMapper
        from src.services.llm import LLMService
        
        # Initialize mapper (we don't need LLM for manual updates)
        llm_service = LLMService(model_name='gemini-1.5-flash')
        mapper = SpeakerMapper(storage, llm_service, ctx.obj['config'])
        
        # Use the mapper's update method
        mappings = {old_name: new_name}
        mapper._update_speakers_in_database(episode_id, mappings)
        mapper._log_speaker_changes(episode_id, mappings)
        
        click.echo(f"\n✓ Successfully updated {unit_count} units")
        logger.info(f"Updated speaker '{old_name}' to '{new_name}' in episode {episode_id}")
        
    except Exception as e:
        logger.error(f"Error updating speaker: {str(e)}")
        click.echo(f"Error: {str(e)}", err=True)
    finally:
        storage.close()


# Add command group to main CLI if this is run directly
if __name__ == '__main__':
    speaker_report()