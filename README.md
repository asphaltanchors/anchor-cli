# Anchor Test Processing Pipeline

A unified CLI for processing anchor test data including force measurements (.LBY files) and media files (videos, photos) into a structured pipeline for downstream editing and analysis.

## Overview

The anchor test processing pipeline organizes, processes, and promotes test data through a systematic workflow:

1. **Ingest**: Process raw intake files into staged UTC format
2. **Cluster**: Group staged files by time gaps (future)  
3. **Promote**: Organize clusters into test hierarchies (future)
4. **Process**: Generate final analysis outputs (future)

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd HV-V5S-parser

# Make anchor executable
chmod +x anchor.py
```

### Basic Usage

```bash
# Process files from a specific date
python3 anchor.py ingest 2025-09-10

# Preview what would happen (dry run)
python3 anchor.py ingest 2025-09-10 --dry-run

# Process with verbose output
python3 anchor.py --verbose ingest 2025-09-10

# Generate JSON instead of CSV for LBY files
python3 anchor.py ingest 2025-09-10 --json

# Force overwrite existing files
python3 anchor.py ingest 2025-09-10 --force
```

## Commands

### `ingest`

Processes files from intake directory into staged UTC format with canonical filenames.

**Input**: `~/Projects/AnchorTesting/_Intake/YYYY-MM-DD_import/`
**Output**: `~/Projects/AnchorTesting/_StagedUTC/`

#### File Processing

**LBY Files (Force Data)**:
- Extracts binary force sensor data and timestamps
- Applies universal 0.001 kN/count calibration
- Generates time-series CSV/JSON with 0.5s intervals
- Output: `YYYYMMDDThhmmssZ__HCV5S__HC0057.csv`

**Media Files (Videos/Images)**:
- Extracts timestamps from EXIF/QuickTime metadata
- Detects device type (iPhone/Android) automatically
- Creates symlinks with canonical names
- Output: `YYYYMMDDThhmmssZ__android__PXL.mp4`

#### Options

- `--dry-run`: Preview changes without processing
- `--force`: Overwrite existing staged files
- `--json`: Output LBY data as JSON instead of CSV
- `--intake-dir`: Override default intake directory

#### Examples

```bash
# Basic processing
python3 anchor.py ingest 2025-09-10

# Custom intake directory
python3 anchor.py --intake-dir /path/to/intake ingest 2025-09-10

# JSON output with verbose logging
python3 anchor.py --verbose ingest 2025-09-10 --json

# Dry run to preview
python3 anchor.py ingest 2025-09-10 --dry-run
```

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

## Directory Structure

```
~/Projects/AnchorTesting/
├── _Intake/
│   └── 2025-09-10_import/       # Raw intake files
│       ├── HC0057.LBY           # Force measurement files
│       ├── HC0058.LBY
│       └── PXL_*.mp4            # Video files
├── _StagedUTC/                  # Processed files with UTC names
│   ├── 20250910T153000Z__HCV5S__HC0057.csv
│   └── 20250910T152945Z__android__PXL.mp4 -> ../intake/...
├── _Clusters/                   # Time-based clusters (future)
├── 00_Input/                    # Per-test organized files (future)  
└── 01_Processed/                # Final analysis outputs (future)
```

## Technical Details

### Force Data Processing
- **Dynamic offset detection**: Automatically finds data section start
- **Universal calibration**: 0.001 kN/count across all LBY files
- **Signed integer parsing**: Handles negative force values
- **Absolute measurements**: No baseline subtraction
- **Time intervals**: 0.5-second sampling rate

### Media Processing
- **Metadata extraction**: ffprobe for videos, exiftool fallback
- **Device detection**: Apple/iPhone vs Android/Google identification
- **UTC conversion**: Local timestamps converted to UTC
- **Symlink preservation**: Originals remain untouched

### Canonical Naming
All processed files use UTC-based canonical names:
`YYYYMMDDThhmmssZ__SOURCE__SEQUENCE.extension`

Examples:
- `20250910T153000Z__HCV5S__HC0057.csv`
- `20250910T152945Z__android__PXL.mp4`

## Requirements

- Python 3.9+
- External tools: `ffprobe`, `exiftool` (for media processing)
- Standard library modules

## File Structure

```
├── anchor.py              # Main CLI entrypoint
├── ingest.py              # Ingest command implementation  
├── media_timestamp.py     # Media timestamp extraction utilities
├── CLAUDE.md              # Development documentation
└── README.md              # This file
```