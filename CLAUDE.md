# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Core Purpose

This repository contains a binary file parser for converting proprietary .LBY force measurement files into CSV format. The .LBY files contain force sensor data from physical testing equipment, and the parser extracts both timestamp metadata and force measurements.

## Key Commands

### Process LBY files
```bash
# Process all LBY files in current directory
python3 test.py

# Process LBY files from a specific directory
python3 test.py original/

# Force overwrite existing CSV files
python3 test.py original/ --force

# Process single file programmatically
python3 -c "import test; test.process_lby_file('original/HC0020.LBY')"
```

### Basic verification
```bash
# Check generated CSV files
ls -la *.csv

# View a sample CSV output
head -20 20250820-075600-0020.csv
```

## Architecture Overview

### Binary File Format (.LBY)
- **Header section** (dynamic size, typically 256-800 bytes): Contains ASCII metadata including version, timestamp, and force calibration values
- **Data section**: 32-bit signed little-endian integers representing force measurements in Newtons
- **Dynamic offset detection**: The parser automatically finds where header ends and data begins by analyzing data patterns

### Core Processing Pipeline
1. **Dynamic offset detection** (`find_data_offset()`) - Locates data section start by analyzing value patterns
2. **Header parsing** - Extracts timestamp and ASCII metadata strings  
3. **Universal calibration** - Applies fixed 0.001 factor (Newtons → kilonewtons)
4. **Data extraction** - Reads signed 32-bit integers, converts to absolute force values
5. **CSV generation** - Outputs timestamped force data with 0.5s intervals

### Critical Implementation Details
- **Universal calibration factor**: Always 0.001 kN/count (confirmed across 7+ test files)
- **Signed integer parsing**: Uses 'i' format (signed) not 'I' (unsigned) to handle negative values correctly
- **Absolute force values**: No baseline subtraction - shows raw force measurements
- **Timestamp extraction**: Specific byte positions (5=min, 6=hour, 8=day, 9=month, 10-11=year)

### File Structure
- `test.py` - Main parser script with CLI interface
- `original/` - Directory containing source .LBY binary files  
- Generated CSV files follow pattern: `YYYYMMDD-HHMMSS-{test_id}.csv`

## Data Flow Architecture
```
.LBY binary file
    ↓
Dynamic offset detection → Header parsing (metadata/timestamp)
    ↓                            ↓
Data section extraction  →  Force calculation (raw * 0.001)
    ↓                            ↓
CSV output (time_s, force_kN)
```

## Key Considerations

### Calibration Accuracy
The 0.001 calibration factor is universal across all .LBY files and produces force values matching physical tester readings with <0.1% error. Do not implement file-specific calibration logic.

### File Processing Strategy  
The parser handles variable file structures through dynamic offset detection rather than fixed offsets. Each .LBY file may have different header sizes and data start positions.

### Output Format
CSV files contain absolute force measurements (not baseline-zeroed). The format is deliberately simple: `time_s,force_kN` with 0.5-second intervals matching the original sampling rate.