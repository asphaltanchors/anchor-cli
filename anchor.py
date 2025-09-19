#!/usr/bin/env python3
# ABOUTME: Main CLI entrypoint for anchor test processing pipeline
# ABOUTME: Provides subcommands for organizing, processing, and promoting anchor test data

import sys
from datetime import datetime
from typing import Optional
import typer

app = typer.Typer(
    name="anchor",
    help="Anchor test processing pipeline",
    epilog="""
Examples:
  anchor ingest 2025-09-10              # Process files from intake date
  anchor ingest 2025-09-10 --dry-run    # Preview what would happen
  anchor ingest 2025-09-10 --verbose    # Enable verbose output
    """
)


def validate_date(value: str) -> str:
    """Validate that the input string is a valid date in YYYY-MM-DD format."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError:
        raise typer.BadParameter(f"Date must be in YYYY-MM-DD format, got: {value}")


@app.command()
def ingest(
    intake_date: str = typer.Argument(callback=validate_date, help="Date to process (YYYY-MM-DD format)"),
    intake_dir: str = typer.Option(
        "~/Projects/AnchorTesting/_Intake",
        help="Path to intake directory"
    ),
    dry_run: bool = typer.Option(False, help="Show what would happen without processing"),
    force: bool = typer.Option(False, help="Overwrite existing staged files"),
    json: bool = typer.Option(False, help="Output LBY files as JSON instead of CSV"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """Process intake files into staged UTC format."""
    try:
        from ingest import run_ingest
        output_format = "json" if json else "csv"
        result = run_ingest(
            date=intake_date,
            intake_dir=intake_dir,
            dry_run=dry_run,
            force=force,
            verbose=verbose,
            output_format=output_format
        )
        if result != 0:
            raise typer.Exit(result)
    except ImportError as e:
        typer.echo(f"Error: Could not import ingest module: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error running ingest: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(1)


if __name__ == '__main__':
    app()