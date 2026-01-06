#!/usr/bin/env python3
"""
ParfumVault Data Auto-Population Module - Main Entry Point

This is the CLI interface for the automation microservice.

Usage:
    python ingestor.py --target all
    python ingestor.py --target ingredient --name "Bergamot"
    python ingestor.py --target ifra --source /app/data/ifra_standards.csv
    python ingestor.py --target batch --file ingredients.txt
    python ingestor.py --test-db

Examples:
    # Enrich a single ingredient
    docker compose run automation python ingestor.py --target ingredient --name "Lavender"
    
    # Sync IFRA library from CSV
    docker compose run automation python ingestor.py --target ifra --source /app/data/ifra.csv
    
    # Batch enrich from a list of ingredients
    docker compose run automation python ingestor.py --target batch --file /app/data/ingredients.txt
    
    # Enrich all existing ingredients in database
    docker compose run automation python ingestor.py --target all --limit 50
"""

import sys
from pathlib import Path

import click

from config import get_config, get_logger, setup_logging
from db_adapter import get_db
from enrichment import (
    enrich_ingredient,
    enrich_all_ingredients,
    batch_enrich_from_file,
    EnrichmentResult,
)
from ifra_sync import sync_ifra_library, update_ingredients_from_ifra, SyncResult


# =============================================================================
# CLI Commands
# =============================================================================

@click.group(invoke_without_command=True)
@click.option(
    "--target",
    type=click.Choice(["ingredient", "ifra", "batch", "all", "update-ifra-limits"]),
    help="Target operation type"
)
@click.option(
    "--name",
    type=str,
    default=None,
    help="Ingredient name (for --target ingredient)"
)
@click.option(
    "--source",
    type=click.Path(exists=False),
    default=None,
    help="Source file path (for --target ifra or --target batch)"
)
@click.option(
    "--file",
    "batch_file",
    type=click.Path(exists=True),
    default=None,
    help="Batch file with ingredient names (one per line)"
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Limit number of ingredients to process (for --target all)"
)
@click.option(
    "--owner-id",
    type=str,
    default=None,
    help="Owner ID for database records (default: from config)"
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing data (default: only fill missing)"
)
@click.option(
    "--test-db",
    is_flag=True,
    default=False,
    help="Test database connection and exit"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose logging"
)
@click.pass_context
def main(
    ctx,
    target: str,
    name: str,
    source: str,
    batch_file: str,
    limit: int,
    owner_id: str,
    overwrite: bool,
    test_db: bool,
    verbose: bool,
):
    """
    ParfumVault Data Auto-Population Module
    
    Automatically enriches ingredient data and syncs IFRA standards.
    """
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    logger = setup_logging(log_level)
    
    config = get_config()
    
    # Handle test-db flag
    if test_db:
        _test_database_connection()
        return
    
    # If no command or target, show help
    if ctx.invoked_subcommand is None and target is None:
        click.echo(ctx.get_help())
        return
    
    # Determine fill_missing_only from overwrite flag
    fill_missing_only = not overwrite
    
    # Execute based on target
    if target == "ingredient":
        if not name:
            logger.error("--name is required for --target ingredient")
            sys.exit(1)
        _enrich_single_ingredient(name, owner_id, fill_missing_only)
    
    elif target == "ifra":
        _sync_ifra(source, owner_id, fill_missing_only)
    
    elif target == "batch":
        if not batch_file:
            logger.error("--file is required for --target batch")
            sys.exit(1)
        _batch_enrich(batch_file, owner_id, fill_missing_only)
    
    elif target == "all":
        _enrich_all(owner_id, fill_missing_only, limit)
    
    elif target == "update-ifra-limits":
        _update_ifra_limits(owner_id)


# =============================================================================
# Command Implementations
# =============================================================================

def _test_database_connection():
    """Test database connectivity."""
    logger = get_logger()
    
    click.echo("Testing database connection...")
    
    try:
        db = get_db()
        if db.test_connection():
            click.secho("✓ Database connection successful!", fg="green")
            
            # Show some stats
            config = get_config()
            ingredients = db.get_all_ingredients(owner_id=config.owner_id, limit=1)
            click.echo(f"  Database: {config.db.database}")
            click.echo(f"  Host: {config.db.host}")
            click.echo(f"  Owner ID: {config.owner_id}")
            
            sys.exit(0)
        else:
            click.secho("✗ Database connection failed!", fg="red")
            sys.exit(1)
            
    except Exception as e:
        click.secho(f"✗ Database error: {e}", fg="red")
        sys.exit(1)


def _enrich_single_ingredient(
    name: str,
    owner_id: str | None,
    fill_missing_only: bool,
):
    """Enrich a single ingredient."""
    logger = get_logger()
    
    click.echo(f"Enriching ingredient: {name}")
    
    result = enrich_ingredient(
        name=name,
        owner_id=owner_id,
        fill_missing_only=fill_missing_only,
    )
    
    _print_enrichment_result(result)
    
    if not result.success:
        sys.exit(1)


def _sync_ifra(
    source: str | None,
    owner_id: str | None,
    fill_missing_only: bool,
):
    """Sync IFRA library from CSV."""
    logger = get_logger()
    
    click.echo("Syncing IFRA library...")
    
    result = sync_ifra_library(
        source=source,
        owner_id=owner_id,
        fill_missing_only=fill_missing_only,
    )
    
    _print_sync_result(result)
    
    if not result.success:
        sys.exit(1)


def _batch_enrich(
    filepath: str,
    owner_id: str | None,
    fill_missing_only: bool,
):
    """Batch enrich from a file."""
    logger = get_logger()
    
    click.echo(f"Batch enriching from: {filepath}")
    
    results = batch_enrich_from_file(
        filepath=filepath,
        owner_id=owner_id,
        fill_missing_only=fill_missing_only,
    )
    
    _print_batch_results(results)


def _enrich_all(
    owner_id: str | None,
    fill_missing_only: bool,
    limit: int | None,
):
    """Enrich all ingredients in database."""
    logger = get_logger()
    
    click.echo("Enriching all ingredients in database...")
    
    if limit:
        click.echo(f"  (limited to {limit} ingredients)")
    
    results = enrich_all_ingredients(
        owner_id=owner_id,
        fill_missing_only=fill_missing_only,
        limit=limit,
    )
    
    _print_batch_results(results)


def _update_ifra_limits(owner_id: str | None):
    """Update ingredient IFRA limits from IFRALibrary."""
    logger = get_logger()
    
    click.echo("Updating ingredient IFRA limits from library...")
    
    counts = update_ingredients_from_ifra(owner_id=owner_id)
    
    click.echo()
    click.secho("Update Complete:", fg="blue", bold=True)
    click.echo(f"  Matched: {counts['matched']}")
    click.echo(f"  Updated: {counts['updated']}")
    click.echo(f"  Skipped: {counts['skipped']}")


# =============================================================================
# Output Formatting
# =============================================================================

def _print_enrichment_result(result: EnrichmentResult):
    """Pretty print an enrichment result."""
    click.echo()
    
    if result.success:
        status = "Created" if result.was_created else "Updated"
        click.secho(f"✓ {status}: {result.ingredient_name}", fg="green")
        
        if result.updated_fields:
            click.echo(f"  Fields: {', '.join(result.updated_fields)}")
        
        if result.sources_used:
            click.echo(f"  Sources: {', '.join(result.sources_used)}")
    else:
        click.secho(f"✗ Failed: {result.ingredient_name}", fg="red")
        if result.error_message:
            click.echo(f"  Error: {result.error_message}")


def _print_sync_result(result: SyncResult):
    """Pretty print an IFRA sync result."""
    click.echo()
    
    if result.success:
        click.secho("✓ IFRA Sync Complete", fg="green")
    else:
        click.secho("✗ IFRA Sync Failed", fg="red")
    
    click.echo(f"  Total entries: {result.total_entries}")
    click.echo(f"  Inserted: {result.inserted}")
    click.echo(f"  Updated: {result.updated}")
    click.echo(f"  Skipped: {result.skipped}")
    
    if result.errors:
        click.echo()
        click.secho("Errors:", fg="yellow")
        for error in result.errors[:10]:  # Limit displayed errors
            click.echo(f"  - {error}")
        
        if len(result.errors) > 10:
            click.echo(f"  ... and {len(result.errors) - 10} more errors")


def _print_batch_results(results: list[EnrichmentResult]):
    """Pretty print batch enrichment results."""
    click.echo()
    
    successful = sum(1 for r in results if r.success)
    created = sum(1 for r in results if r.was_created)
    failed = len(results) - successful
    
    click.secho("Batch Enrichment Complete:", fg="blue", bold=True)
    click.echo(f"  Total: {len(results)}")
    click.secho(f"  Successful: {successful}", fg="green")
    click.echo(f"  Created: {created}")
    
    if failed > 0:
        click.secho(f"  Failed: {failed}", fg="red")
        
        # Show failed items
        click.echo()
        click.echo("Failed items:")
        for r in results:
            if not r.success:
                click.echo(f"  - {r.ingredient_name}: {r.error_message}")


# =============================================================================
# Additional Commands
# =============================================================================

@main.command()
@click.argument("names", nargs=-1)
@click.option("--owner-id", type=str, default=None)
def quick(names: tuple[str, ...], owner_id: str | None):
    """
    Quick enrich one or more ingredients.
    
    Usage: python ingestor.py quick "Bergamot" "Lavender" "Rose"
    """
    if not names:
        click.echo("Please provide ingredient names")
        return
    
    for name in names:
        result = enrich_ingredient(name=name, owner_id=owner_id)
        _print_enrichment_result(result)


@main.command()
@click.option("--owner-id", type=str, default=None)
def status(owner_id: str | None):
    """Show database status and statistics."""
    config = get_config()
    db = get_db()
    owner = owner_id or config.owner_id
    
    click.secho("ParfumVault Automation Status", fg="blue", bold=True)
    click.echo()
    
    # Database info
    click.echo("Database Configuration:")
    click.echo(f"  Host: {config.db.host}")
    click.echo(f"  Database: {config.db.database}")
    click.echo(f"  Owner ID: {owner}")
    
    # Connection test
    if db.test_connection():
        click.secho("  Status: Connected ✓", fg="green")
    else:
        click.secho("  Status: Disconnected ✗", fg="red")
        return
    
    click.echo()
    
    # Ingredient stats
    ingredients = db.get_all_ingredients(owner_id=owner)
    click.echo("Ingredient Statistics:")
    click.echo(f"  Total: {len(ingredients)}")
    
    with_cas = sum(1 for i in ingredients if i.cas)
    with_profile = sum(1 for i in ingredients if i.profile)
    
    click.echo(f"  With CAS: {with_cas} ({100*with_cas//max(len(ingredients),1)}%)")
    click.echo(f"  With Profile: {with_profile} ({100*with_profile//max(len(ingredients),1)}%)")
    
    click.echo()
    
    # Scraper config
    click.echo("Scraper Configuration:")
    click.echo(f"  Delay: {config.scraper.delay_seconds}s")
    click.echo(f"  Cache Enabled: {config.scraper.cache_enabled}")
    click.echo(f"  User-Agent Rotation: {config.scraper.enable_user_agent_rotation}")


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    main()
