"""
Command-line interface for migration tools.

This module provides CLI commands for running migrations,
checking compatibility, and validating data.
"""

import click
import logging
from pathlib import Path
from datetime import datetime
import json

from ..core.config import get_config
from ..providers.graph.neo4j import Neo4jProvider
from .schema_manager import SchemaManager
from .data_migrator import DataMigrator
from .compatibility import CompatibilityChecker
from .validators import MigrationValidator

logger = logging.getLogger(__name__)


@click.group()
@click.option("--config", "-c", default="config/config.yml", help="Config file path")
@click.pass_context
def migration_cli(ctx, config):
    """Migration tools for podcast knowledge pipeline."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = get_config(config)
    
    # Initialize graph provider
    graph_config = ctx.obj["config"]["providers"]["graph"]
    ctx.obj["graph_provider"] = Neo4jProvider(
        uri=graph_config["uri"],
        username=graph_config["username"],
        password=graph_config["password"]
    )


@migration_cli.command()
@click.pass_context
def check_compatibility(ctx):
    """Check compatibility between monolithic and modular systems."""
    logger.info("Checking system compatibility")
    
    graph_provider = ctx.obj["graph_provider"]
    
    # Look for monolithic system
    monolithic_path = Path("../../../")  # Adjust based on structure
    
    checker = CompatibilityChecker(graph_provider, monolithic_path)
    report = checker.check_all()
    
    # Display report
    click.echo("\n" + "="*60)
    click.echo("COMPATIBILITY CHECK REPORT")
    click.echo("="*60)
    
    click.echo(f"\nCompatible: {click.style(str(report.compatible), 
                                            fg='green' if report.compatible else 'red', 
                                            bold=True)}")
    
    # Show statistics
    click.echo("\nStatistics:")
    for key, value in report.statistics.items():
        click.echo(f"  {key}: {value}")
    
    # Show issues by severity
    errors = [i for i in report.issues if i.severity == "error"]
    warnings = [i for i in report.issues if i.severity == "warning"]
    info = [i for i in report.issues if i.severity == "info"]
    
    if errors:
        click.echo(f"\n{click.style('ERRORS', fg='red', bold=True)} ({len(errors)}):")
        for issue in errors[:10]:  # Show first 10
            click.echo(f"  - {issue.message}")
            if issue.resolution:
                click.echo(f"    Resolution: {issue.resolution}")
    
    if warnings:
        click.echo(f"\n{click.style('WARNINGS', fg='yellow', bold=True)} ({len(warnings)}):")
        for issue in warnings[:10]:
            click.echo(f"  - {issue.message}")
    
    if info:
        click.echo(f"\n{click.style('INFO', fg='blue', bold=True)} ({len(info)}):")
        for issue in info[:5]:
            click.echo(f"  - {issue.message}")
    
    # Show recommendations
    if report.recommendations:
        click.echo("\nRecommendations:")
        for i, rec in enumerate(report.recommendations, 1):
            click.echo(f"  {i}. {rec}")
    
    # Save full report
    report_file = f"compatibility_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w") as f:
        json.dump(report.to_dict(), f, indent=2)
    
    click.echo(f"\nFull report saved to: {report_file}")
    
    # Generate fix script if needed
    if not report.compatible:
        if click.confirm("\nGenerate compatibility fix script?"):
            script = checker.generate_compatibility_script(report)
            script_file = f"compatibility_fixes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.cypher"
            
            with open(script_file, "w") as f:
                f.write(script)
            
            click.echo(f"Fix script saved to: {script_file}")


@migration_cli.command()
@click.pass_context
def validate_pre(ctx):
    """Validate data before migration."""
    logger.info("Running pre-migration validation")
    
    graph_provider = ctx.obj["graph_provider"]
    validator = MigrationValidator(graph_provider)
    
    with click.progressbar(length=100, label="Validating") as bar:
        result = validator.validate_pre_migration()
        bar.update(100)
    
    # Display results
    click.echo("\n" + "="*60)
    click.echo("PRE-MIGRATION VALIDATION REPORT")
    click.echo("="*60)
    
    click.echo(f"\nValid: {click.style(str(result.valid), 
                                      fg='green' if result.valid else 'red', 
                                      bold=True)}")
    click.echo(f"Total nodes checked: {result.total_checked}")
    click.echo(f"Errors: {len(result.errors)}")
    click.echo(f"Warnings: {len(result.warnings)}")
    
    # Show sample errors
    if result.errors:
        click.echo(f"\n{click.style('Sample Errors:', fg='red', bold=True)}")
        for error in result.errors[:10]:
            click.echo(f"  - {error.node_type}[{error.node_id}].{error.field}: {error.error}")
    
    # Save full report
    report_file = f"pre_migration_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w") as f:
        json.dump(result.to_dict(), f, indent=2)
    
    click.echo(f"\nFull report saved to: {report_file}")
    
    if not result.valid:
        click.echo(click.style("\n⚠️  Fix validation errors before proceeding with migration!", 
                              fg='yellow', bold=True))


@migration_cli.command()
@click.option("--target-version", "-v", default="1.1.0", help="Target schema version")
@click.option("--dry-run", is_flag=True, help="Simulate migration without changes")
@click.pass_context
def migrate_schema(ctx, target_version, dry_run):
    """Migrate database schema to target version."""
    logger.info(f"Migrating schema to version {target_version}")
    
    if dry_run:
        click.echo(click.style("DRY RUN MODE - No changes will be made", fg='yellow'))
    
    graph_provider = ctx.obj["graph_provider"]
    schema_manager = SchemaManager(graph_provider)
    
    # Get current version
    current = schema_manager.get_current_version()
    click.echo(f"Current version: {current.version if current else 'unknown'}")
    click.echo(f"Target version: {target_version}")
    
    if current and current.version == target_version:
        click.echo("Already at target version!")
        return
    
    # Show migration path
    migrations = schema_manager.get_available_migrations(current.version if current else "0.0.0")
    if migrations:
        click.echo("\nMigrations to apply:")
        for m in migrations:
            if m.version <= target_version:
                click.echo(f"  - {m.version}: {m.description}")
    
    if not dry_run and click.confirm("\nProceed with migration?"):
        success = schema_manager.migrate_to(target_version)
        
        if success:
            click.echo(click.style("\n✅ Schema migration completed successfully!", 
                                 fg='green', bold=True))
        else:
            click.echo(click.style("\n❌ Schema migration failed!", 
                                 fg='red', bold=True))
    
    # Validate schema
    click.echo("\nValidating schema...")
    validation = schema_manager.validate_schema()
    
    click.echo(f"\nSchema validation: {click.style('PASSED' if validation['valid'] else 'FAILED',
                                                  fg='green' if validation['valid'] else 'red')}")
    
    if validation['errors']:
        click.echo("\nErrors:")
        for error in validation['errors']:
            click.echo(f"  - {error}")


@migration_cli.command()
@click.option("--dry-run", is_flag=True, help="Simulate migration without changes")
@click.option("--batch-size", default=100, help="Number of items per batch")
@click.option("--checkpoint-dir", default="migration_checkpoints", help="Checkpoint directory")
@click.pass_context
def migrate_data(ctx, dry_run, batch_size, checkpoint_dir):
    """Migrate data from monolithic to modular system."""
    logger.info("Starting data migration")
    
    if dry_run:
        click.echo(click.style("DRY RUN MODE - No changes will be made", fg='yellow'))
    
    graph_provider = ctx.obj["graph_provider"]
    migrator = DataMigrator(
        graph_provider,
        checkpoint_dir=Path(checkpoint_dir),
        batch_size=batch_size
    )
    
    # Check for existing checkpoint
    checkpoint_path = Path(checkpoint_dir) / "migration" / "migration_progress.json"
    if checkpoint_path.exists():
        if click.confirm("Found existing checkpoint. Resume from checkpoint?"):
            click.echo("Resuming migration from checkpoint...")
        else:
            if click.confirm("Start fresh migration? (This will overwrite checkpoint)"):
                checkpoint_path.unlink()
            else:
                return
    
    click.echo("\nMigrating data...")
    
    # Progress tracking
    node_types = ["podcasts", "episodes", "segments", "entities", 
                  "insights", "quotes", "topics", "speakers"]
    
    with click.progressbar(node_types, label="Migrating") as bar:
        progress = migrator.migrate_all(dry_run=dry_run)
        
        for node_type in bar:
            # Progress is updated internally
            pass
    
    # Display results
    click.echo("\n" + "="*60)
    click.echo("MIGRATION RESULTS")
    click.echo("="*60)
    
    total_processed = 0
    total_failed = 0
    
    for node_type, prog in progress.items():
        total_processed += prog.processed_items
        total_failed += prog.failed_items
        
        status_color = 'green' if prog.status.value == 'completed' else 'red'
        click.echo(f"\n{node_type.upper()}:")
        click.echo(f"  Status: {click.style(prog.status.value, fg=status_color)}")
        click.echo(f"  Total: {prog.total_items}")
        click.echo(f"  Processed: {prog.processed_items}")
        click.echo(f"  Failed: {prog.failed_items}")
        click.echo(f"  Skipped: {prog.skipped_items}")
        
        if prog.duration_seconds:
            click.echo(f"  Duration: {prog.duration_seconds:.2f}s")
        
        if prog.errors:
            click.echo(f"  Sample errors:")
            for error in prog.errors[:3]:
                click.echo(f"    - {error}")
    
    click.echo(f"\nTotal processed: {total_processed}")
    click.echo(f"Total failed: {total_failed}")
    
    # Save detailed report
    report_file = f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_data = {node_type: prog.to_dict() for node_type, prog in progress.items()}
    
    with open(report_file, "w") as f:
        json.dump(report_data, f, indent=2)
    
    click.echo(f"\nDetailed report saved to: {report_file}")


@migration_cli.command()
@click.pass_context
def validate_post(ctx):
    """Validate data after migration."""
    logger.info("Running post-migration validation")
    
    graph_provider = ctx.obj["graph_provider"]
    validator = MigrationValidator(graph_provider)
    
    with click.progressbar(length=100, label="Validating") as bar:
        result = validator.validate_post_migration()
        bar.update(100)
    
    # Display results
    click.echo("\n" + "="*60)
    click.echo("POST-MIGRATION VALIDATION REPORT")
    click.echo("="*60)
    
    click.echo(f"\nValid: {click.style(str(result.valid), 
                                      fg='green' if result.valid else 'red', 
                                      bold=True)}")
    
    # Show validation summary
    if result.valid:
        click.echo(click.style("\n✅ Migration validation PASSED!", fg='green', bold=True))
    else:
        click.echo(click.style("\n❌ Migration validation FAILED!", fg='red', bold=True))
        
        if result.errors:
            click.echo(f"\nErrors found: {len(result.errors)}")
            for error in result.errors[:10]:
                click.echo(f"  - {error.node_type}[{error.node_id}]: {error.error}")
    
    # Save report
    report_file = f"post_migration_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w") as f:
        json.dump(result.to_dict(), f, indent=2)
    
    click.echo(f"\nFull report saved to: {report_file}")


@migration_cli.command()
@click.option("--target-date", required=True, help="Target date (YYYY-MM-DD HH:MM:SS)")
@click.pass_context
def rollback(ctx, target_date):
    """Rollback migration to a specific date."""
    logger.info(f"Rolling back to {target_date}")
    
    try:
        target_dt = datetime.fromisoformat(target_date)
    except ValueError:
        click.echo(click.style("Invalid date format! Use YYYY-MM-DD HH:MM:SS", fg='red'))
        return
    
    if not click.confirm(f"⚠️  This will rollback all changes after {target_date}. Continue?"):
        return
    
    graph_provider = ctx.obj["graph_provider"]
    migrator = DataMigrator(graph_provider)
    
    success = migrator.rollback(target_dt)
    
    if success:
        click.echo(click.style("\n✅ Rollback completed successfully!", fg='green', bold=True))
    else:
        click.echo(click.style("\n❌ Rollback failed!", fg='red', bold=True))


if __name__ == "__main__":
    migration_cli()