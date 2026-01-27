# Anchor Test Processing Utilities

Simple, focused tools for parsing pull-tester force data (.LBY files) and (optionally) organizing media files.

## Overview

- Parse .LBY files into CSV/JSON
- Optionally organize photos/videos into canonical UTC filenames
- Defaults to an interactive date picker when dates aren't provided

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd anchor-cli

# Make anchor executable
chmod +x anchor.py
```

### Basic Usage

```bash
# Parse LBY files (interactive date picker if --dates/--all not provided)
python3 anchor.py lby --input ~/projects/pull-test-data/HCVNS

# Parse a specific date (comma list or range)
python3 anchor.py lby --input ~/projects/pull-test-data/HCVNS --dates 2026-01-27
python3 anchor.py lby --input ~/projects/pull-test-data/HCVNS --dates 2025-09-10,2025-09-11
python3 anchor.py lby --input ~/projects/pull-test-data/HCVNS --dates 2025-09-10..2025-09-19

# Output JSON instead of CSV
python3 anchor.py lby --input ~/projects/pull-test-data/HCVNS --dates 2026-01-27 --json

# Media processing (optional)
python3 anchor.py media --input ~/projects/pull-test-data/HCVNS --all
```

## Commands

### `lby`

Parse pull-tester `.LBY` files into CSV/JSON.

**Input**: A directory containing `.LBY` files.
**Output**: `./output` by default, containing `HC0001.csv` style outputs.

#### Behavior

- Reads timestamps from the LBY header (bytes 5/6/8/9/10-11)
- Falls back to file mtime if header is missing or invalid
- Uses a fixed 0.001 kN/count calibration
- Writes `time_s,force_kN` with 0.5s intervals

#### Options

- `--input`: directory containing `.LBY` files
- `--output`: output directory (default `./output`)
- `--dates`: comma list or range (YYYY-MM-DD..YYYY-MM-DD)
- `--all`: process all dates found
- `--json`: output JSON instead of CSV
- `--dry-run`: preview without writing files
- `--force`: overwrite existing outputs

### `media`

Process media files into canonical UTC filenames (symlinks).

**Input**: A directory containing media files.
**Output**: `./output` by default.

#### Behavior

- Extracts timestamps via ffprobe (or mtime fallback)
- Detects device type via exiftool
- Creates symlinks using canonical UTC filenames

#### Options

- `--input`: directory containing media files
- `--output`: output directory (default `./output`)
- `--dates`: comma list or range (YYYY-MM-DD..YYYY-MM-DD)
- `--all`: process all dates found
- `--dry-run`: preview without writing files
- `--force`: overwrite existing outputs

## File Format Details

### LBY Files (Force Data)

**Input Format:**
- Header (256-800 bytes): ASCII metadata, timestamps
- Data: 32-bit signed little-endian integers (force in Newtons)

**Output Format (CSV):**
```csv
time_s,force_kN
0.0,0.003
0.5,0.003
1.0,0.002
```

**Output Format (JSON):**
```json
{
  "values": [
    {"time_s": 0.0, "force_kN": 0.003},
    {"time_s": 0.5, "force_kN": 0.003}
  ]
}
```

### Media Files

**Supported formats:** `.mov`, `.mp4`, `.heic`, `.jpg`, `.jpeg`

**Processing:**
- Timestamp extraction via ffprobe/exiftool
- Device detection from metadata
- Symlink creation (preserves originals)

## Legacy (previous behavior)

The older `ingest` pipeline expected a fixed folder layout and produced canonical UTC filenames:

- Input: `~/Projects/AnchorTesting/_Intake/YYYY-MM-DD_import/`
- Output: `~/Projects/AnchorTesting/_StagedUTC/`
- LBY output: `YYYYMMDDThhmmssZ__HCV5S__HC0057.csv`
- Media output: `YYYYMMDDThhmmssZ__android__PXL.mp4`

That legacy pipeline has been removed from the codebase, but the behavior is documented here for reference.

## Requirements

- Python 3.9+
- External tools: `ffprobe`, `exiftool` (for media processing)
- Standard library modules

## File Structure

```
├── anchor.py              # Main CLI entrypoint
├── lby.py                 # LBY parsing command
├── media.py               # Media processing command
├── media_timestamp.py     # Media timestamp extraction utilities
├── CLAUDE.md              # Development documentation
└── README.md              # This file
```
