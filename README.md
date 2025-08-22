# LBY Force Data Converter

A Python utility for converting proprietary .LBY force measurement files into standard CSV format. The .LBY files contain force sensor data from physical testing equipment, and this parser extracts both timestamp metadata and force measurements.

## Features

- **Dynamic header detection**: Automatically finds where header ends and data begins
- **Timestamp extraction**: Parses embedded timestamp data from file headers
- **Universal calibration**: Applies consistent 0.001 kN/count calibration factor
- **Batch processing**: Process entire directories of .LBY files
- **Smart naming**: Generated CSV files follow `YYYYMMDD-HHMMSS-{test_id}.csv` pattern

## Usage

### Basic Commands

```bash
# Process all LBY files in current directory
python3 lby_converter.py

# Process LBY files from a specific directory
python3 lby_converter.py original/

# Force overwrite existing CSV files
python3 lby_converter.py original/ --force

# Process single file programmatically
python3 -c "import lby_converter; lby_converter.process_lby_file('original/HC0020.LBY')"
```

### Verification

```bash
# Check generated CSV files
ls -la *.csv

# View a sample CSV output
head -20 20250820-075600-0020.csv
```

## File Format

### Input (.LBY files)
- **Header section** (256-800 bytes): ASCII metadata, timestamps, calibration data
- **Data section**: 32-bit signed little-endian integers (force in Newtons)

### Output (CSV files)
- Column 1: `time_s` - Time in seconds (0.5s intervals)
- Column 2: `force_kN` - Force in kilonewtons (absolute values)

## Technical Details

### Processing Pipeline
1. Dynamic offset detection locates data section start
2. Header parsing extracts timestamp and metadata
3. Universal 0.001 calibration factor applied (Newtons → kilonewtons)
4. Force data extracted as signed 32-bit integers
5. CSV output generated with 0.5-second time intervals

### Key Implementation Notes
- **Calibration factor**: Fixed 0.001 kN/count across all files
- **Signed integers**: Properly handles negative force values
- **Absolute measurements**: No baseline subtraction applied
- **Variable structure**: Handles different header sizes automatically

## Requirements

- Python 3.x
- Standard library modules: `sys`, `os`, `struct`, `csv`, `statistics`, `re`, `glob`, `argparse`

## File Structure

```
├── lby_converter.py    # Main parser script
├── original/          # Source .LBY binary files
├── CLAUDE.md          # Development documentation
└── README.md          # This file
```

Generated CSV files appear in the working directory with timestamp-based naming.