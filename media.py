#!/usr/bin/env python3
# ABOUTME: Process media files (images/videos) into canonical UTC filenames.
# ABOUTME: Provides an interactive date picker when dates are not supplied.

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import typer

from media_timestamp import (
    detect_device_from_metadata,
    extract_media_timestamp,
    extract_sequence_from_filename,
    generate_canonical_filename,
    get_file_mtime_utc,
)

app = typer.Typer(add_completion=False, help="Process media files into canonical names")

MEDIA_EXTENSIONS = {".mov", ".mp4", ".heic", ".jpg", ".jpeg"}


def _iter_media_files(input_dir: Path) -> list[Path]:
    files: list[Path] = []
    for entry in input_dir.iterdir():
        if entry.is_file() and entry.suffix.lower() in MEDIA_EXTENSIONS:
            files.append(entry)
    return sorted(files)


def media_file_date(path: Path, verbose: bool = False) -> datetime:
    ts = extract_media_timestamp(str(path))
    if ts is None:
        ts = get_file_mtime_utc(str(path))
        if verbose:
            print(f"Warning: {path.name} missing metadata timestamp, using mtime")
    return ts


def _expand_date_range(start: datetime, end: datetime) -> Iterable[str]:
    if end < start:
        start, end = end, start
    current = start
    while current <= end:
        yield current.strftime("%Y-%m-%d")
        current += timedelta(days=1)


def _parse_date_value(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def parse_date_selection(selection: str, available_dates: set[str]) -> set[str]:
    raw = selection.strip()
    if not raw:
        raise ValueError("No dates provided")
    if raw.lower() in {"all", "*"}:
        return set(available_dates)
    selected: set[str] = set()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    for part in parts:
        if ".." in part:
            start_str, end_str = [p.strip() for p in part.split("..", 1)]
            start = _parse_date_value(start_str)
            end = _parse_date_value(end_str)
            selected.update(_expand_date_range(start, end))
        else:
            selected.add(_parse_date_value(part).strftime("%Y-%m-%d"))
    return selected


def prompt_for_dates(available_dates: dict[str, list[Path]]) -> set[str]:
    if not available_dates:
        raise ValueError("No media files found in input directory")
    print("Available dates:")
    for date_str in sorted(available_dates.keys()):
        print(f"  {date_str} ({len(available_dates[date_str])} files)")
    while True:
        selection = input("Select dates (comma list, range 2025-09-10..2025-09-19, or 'all'): ").strip()
        try:
            selected = parse_date_selection(selection, set(available_dates.keys()))
        except ValueError as exc:
            print(f"Invalid selection: {exc}")
            continue
        missing = sorted(d for d in selected if d not in available_dates)
        if missing:
            print(f"These dates have no files and will be ignored: {', '.join(missing)}")
        selected = set(d for d in selected if d in available_dates)
        if not selected:
            print("No matching dates selected.")
            continue
        return selected


def collect_files_by_date(input_dir: Path, verbose: bool = False) -> dict[str, list[Path]]:
    files = _iter_media_files(input_dir)
    date_map: dict[str, list[Path]] = {}
    for path in files:
        date_str = media_file_date(path, verbose).strftime("%Y-%m-%d")
        date_map.setdefault(date_str, []).append(path)
    return date_map


def process_media_file(
    file_path: Path,
    output_dir: Path,
    dry_run: bool,
    force: bool,
    verbose: bool,
) -> bool:
    try:
        timestamp_utc = extract_media_timestamp(str(file_path))
        if timestamp_utc is None:
            timestamp_utc = get_file_mtime_utc(str(file_path))
            if verbose:
                print(f"Warning: Could not extract metadata timestamp from {file_path.name}, using mtime")

        device_type = detect_device_from_metadata(str(file_path))
        sequence = extract_sequence_from_filename(file_path.name)
        _, ext = os.path.splitext(file_path.name)

        canonical_name = generate_canonical_filename(timestamp_utc, device_type, sequence, ext)
        output_path = output_dir / canonical_name

        if verbose:
            print(f"Media: {file_path.name} -> {output_path.name}")
            print(f"  Timestamp: {timestamp_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"  Device: {device_type}")

        if output_path.exists() and not force:
            if verbose:
                print(f"  Skipping: {output_path.name} already exists (use --force to overwrite)")
            return True

        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)
            if output_path.exists():
                output_path.unlink()
            output_path.symlink_to(file_path.resolve())

        return True
    except Exception as exc:
        if verbose:
            print(f"Error processing media file {file_path.name}: {exc}")
        return False


@app.callback(invoke_without_command=True)
def main(
    input_dir: Path = typer.Option(None, "--input", "-i", help="Directory containing media files"),
    output_dir: Path = typer.Option(Path("./output"), "--output", "-o", help="Output directory"),
    dates: str = typer.Option(None, "--dates", help="Comma list or range (YYYY-MM-DD..YYYY-MM-DD)"),
    all_dates: bool = typer.Option(False, "--all", help="Process all dates found"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would happen without writing files"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing output files"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Process media files into canonical UTC filenames."""
    if input_dir is None:
        input_dir = Path(typer.prompt("Input directory")).expanduser()
    else:
        input_dir = input_dir.expanduser()
    output_dir = output_dir.expanduser()

    if not input_dir.exists() or not input_dir.is_dir():
        raise typer.BadParameter(f"Input directory does not exist: {input_dir}")

    date_map = collect_files_by_date(input_dir, verbose=verbose)
    if not date_map:
        typer.echo("No media files found.")
        raise typer.Exit(0)

    if all_dates:
        selected_dates = set(date_map.keys())
    elif dates:
        selected_dates = parse_date_selection(dates, set(date_map.keys()))
        missing = sorted(d for d in selected_dates if d not in date_map)
        if missing:
            typer.echo(f"Warning: These dates have no files and will be ignored: {', '.join(missing)}")
        selected_dates = set(d for d in selected_dates if d in date_map)
        if not selected_dates:
            raise typer.BadParameter("No matching dates selected")
    else:
        selected_dates = prompt_for_dates(date_map)

    files_to_process: list[Path] = []
    for date_str in sorted(selected_dates):
        files_to_process.extend(sorted(date_map[date_str]))

    if verbose:
        print(f"Processing {len(files_to_process)} files from {len(selected_dates)} date(s)")
        print(f"Output directory: {output_dir}")
        if dry_run:
            print("DRY RUN MODE - no files will be created")
        print()

    success_count = 0
    error_count = 0
    for file_path in files_to_process:
        ok = process_media_file(
            file_path=file_path,
            output_dir=output_dir,
            dry_run=dry_run,
            force=force,
            verbose=verbose,
        )
        if ok:
            success_count += 1
        else:
            error_count += 1

    if dry_run:
        print(f"\nDry run complete. Would process {success_count} files, {error_count} errors.")
    else:
        print(f"\nMedia processing complete. Processed {success_count} files, {error_count} errors.")


if __name__ == "__main__":
    app()
