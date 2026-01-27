#!/usr/bin/env python3
# ABOUTME: Parse pull-tester .LBY files into CSV/JSON outputs.
# ABOUTME: Provides an interactive date picker when dates are not supplied.

import csv
import json
import os
import re
import struct
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import typer

app = typer.Typer(add_completion=False, help="Parse pull-tester .LBY files")

LBY_EXTENSIONS = {".lby"}


def _iter_lby_files(input_dir: Path) -> list[Path]:
    files: list[Path] = []
    for entry in input_dir.iterdir():
        if entry.is_file() and entry.suffix.lower() in LBY_EXTENSIONS:
            files.append(entry)
    return sorted(files)


def extract_lby_timestamp(header_data: bytes) -> datetime | None:
    """Extract timestamp from LBY header. Returns UTC-aware datetime if found."""
    if len(header_data) < 12:
        return None
    try:
        minute = header_data[5]
        hour = header_data[6]
        day = header_data[8]
        month = header_data[9]
        year = struct.unpack("<H", header_data[10:12])[0]
        if (
            0 <= hour <= 23
            and 0 <= minute <= 59
            and 1 <= month <= 12
            and 1 <= day <= 31
            and 2020 <= year <= 2035
        ):
            local_naive = datetime(year, month, day, hour, minute, 0)
            ts = time.mktime(local_naive.timetuple())
            utc_dt = datetime.utcfromtimestamp(ts)
            return utc_dt.replace(tzinfo=timezone.utc)
    except (IndexError, struct.error):
        pass
    return None


def get_file_mtime_utc(path: Path) -> datetime:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def extract_lby_sequence(filename: str) -> str:
    base = os.path.splitext(os.path.basename(filename))[0]
    m = re.search(r"(HC\d+)", base, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return base.upper() if base else "HC0000"


def find_lby_data_offset(data: bytes) -> int:
    for offset in range(256, min(800, len(data) - 100), 4):
        try:
            remaining = data[offset:]
            if len(remaining) < 80:
                continue
            values = list(struct.unpack("<" + "i" * 20, remaining[:80]))
            positive_values = [v for v in values if 0 < v < 100000]
            if len(positive_values) >= 10:
                variation = max(positive_values) - min(positive_values)
                if variation > 100:
                    return offset
        except Exception:
            continue
    return 608


def load_lby_words_le(data: bytes) -> list[int]:
    n = len(data) // 4
    return list(struct.unpack("<" + "i" * n, data[: n * 4]))


def write_lby_output(output_path: Path, rows: list[tuple], output_format: str) -> None:
    if output_format == "json":
        data = {"values": [{"time_s": t, "force_kN": f} for t, f in rows]}
        output_path.write_text(json.dumps(data, indent=2))
    else:
        with output_path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time_s", "force_kN"])
            w.writerows(rows)


def lby_file_date(path: Path, verbose: bool = False) -> datetime:
    with path.open("rb") as f:
        header = f.read(64)
    ts = extract_lby_timestamp(header)
    if ts is None:
        ts = get_file_mtime_utc(path)
        if verbose:
            print(f"Warning: {path.name} missing header timestamp, using mtime")
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
        raise ValueError("No LBY files found in input directory")
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
    files = _iter_lby_files(input_dir)
    date_map: dict[str, list[Path]] = {}
    for path in files:
        date_str = lby_file_date(path, verbose).strftime("%Y-%m-%d")
        date_map.setdefault(date_str, []).append(path)
    return date_map


def process_lby_file(
    file_path: Path,
    output_dir: Path,
    output_format: str,
    dry_run: bool,
    force: bool,
    verbose: bool,
) -> bool:
    try:
        data = file_path.read_bytes()
        data_offset = find_lby_data_offset(data)
        header = data[:data_offset]
        payload = data[data_offset:]

        timestamp_utc = extract_lby_timestamp(header)
        if timestamp_utc is None:
            timestamp_utc = get_file_mtime_utc(file_path)
            if verbose:
                print(f"Warning: Could not extract timestamp from {file_path.name}, using mtime")

        sequence = extract_lby_sequence(file_path.name)
        ext = ".json" if output_format == "json" else ".csv"
        output_path = output_dir / f"{sequence}{ext}"

        if verbose:
            print(f"LBY: {file_path.name} -> {output_path.name}")
            print(f"  Timestamp: {timestamp_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"  Output: {output_format.upper()}")

        if output_path.exists() and not force:
            if verbose:
                print(f"  Skipping: {output_path.name} already exists (use --force to overwrite)")
            return True

        if not dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)
            samples = load_lby_words_le(payload)
            force_kN = [s * 0.001 for s in samples]
            rows = [(i * 0.5, force_kN[i]) for i in range(len(samples))]
            write_lby_output(output_path, rows, output_format)
        return True
    except Exception as exc:
        if verbose:
            print(f"Error processing {file_path.name}: {exc}")
        return False


@app.callback(invoke_without_command=True)
def main(
    input_dir: Path = typer.Option(None, "--input", "-i", help="Directory containing LBY files"),
    output_dir: Path = typer.Option(Path("./output"), "--output", "-o", help="Output directory"),
    dates: str = typer.Option(None, "--dates", help="Comma list or range (YYYY-MM-DD..YYYY-MM-DD)"),
    all_dates: bool = typer.Option(False, "--all", help="Process all dates found"),
    json_output: bool = typer.Option(False, "--json", help="Write JSON instead of CSV"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would happen without writing files"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing output files"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Parse pull-tester LBY files into CSV/JSON outputs."""
    if input_dir is None:
        input_dir = Path(typer.prompt("Input directory")).expanduser()
    else:
        input_dir = input_dir.expanduser()
    output_dir = output_dir.expanduser()

    if not input_dir.exists() or not input_dir.is_dir():
        raise typer.BadParameter(f"Input directory does not exist: {input_dir}")

    date_map = collect_files_by_date(input_dir, verbose=verbose)
    if not date_map:
        typer.echo("No .LBY files found.")
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

    output_format = "json" if json_output else "csv"
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
        ok = process_lby_file(
            file_path=file_path,
            output_dir=output_dir,
            output_format=output_format,
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
        print(f"\nParse complete. Processed {success_count} files, {error_count} errors.")


if __name__ == "__main__":
    app()
