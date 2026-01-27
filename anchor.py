#!/usr/bin/env python3
# ABOUTME: Main CLI entrypoint for anchor test processing utilities
# ABOUTME: Provides focused subcommands for LBY parsing and media handling

import typer

import lby
import media

app = typer.Typer(
    name="anchor",
    help="Anchor test processing utilities",
    epilog="""
Examples:
  anchor lby --input ~/projects/pull-test-data/HCVNS
  anchor lby --input ~/projects/pull-test-data/HCVNS --dates 2026-01-27
  anchor media --input ~/projects/pull-test-data/HCVNS --all
    """,
)

app.add_typer(lby.app, name="lby", help="Parse pull-tester .LBY files")
app.add_typer(media.app, name="media", help="Process images/videos into canonical names")


if __name__ == '__main__':
    app()
