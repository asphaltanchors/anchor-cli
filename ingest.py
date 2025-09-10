#!/usr/bin/env python3
# ABOUTME: Ingest module for processing intake files into staged UTC format
# ABOUTME: Combines LBY and media file processing with canonical filename generation

import glob
import os
import re
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from media_timestamp import (
    detect_device_from_metadata,
    extract_media_timestamp,
    extract_sequence_from_filename,
    generate_canonical_filename,
    get_file_mtime_utc
)


# File extensions we can process
LBY_EXTENSIONS = {'.lby'}
MEDIA_EXTENSIONS = {'.mov', '.mp4', '.heic', '.jpg', '.jpeg'}
ALL_EXTENSIONS = LBY_EXTENSIONS | MEDIA_EXTENSIONS


def extract_lby_timestamp(header_data: bytes) -> datetime | None:
    """
    Extract timestamp from LBY file header.
    Returns UTC datetime if found, else None.
    """
    if len(header_data) < 12:
        return None
    
    try:
        minute = header_data[5]    # byte 5
        hour = header_data[6]      # byte 6  
        day = header_data[8]       # byte 8
        month = header_data[9]     # byte 9
        year = struct.unpack('<H', header_data[10:12])[0]  # bytes 10-11 (little-endian)
        
        # Validate all components
        if (0 <= hour <= 23 and 0 <= minute <= 59 and 
            1 <= month <= 12 and 1 <= day <= 31 and 2020 <= year <= 2030):
            
            # LBY timestamps are in local time, convert to UTC
            local_naive = datetime(year, month, day, hour, minute, 0)
            ts = time.mktime(local_naive.timetuple())
            utc_dt = datetime.utcfromtimestamp(ts)
            return utc_dt.replace(tzinfo=timezone.utc)
            
    except (IndexError, struct.error):
        pass
    
    return None


def extract_lby_sequence(filename: str) -> str:
    """Extract sequence tag from LBY filename like 'HC0010.LBY' -> 'HC0010'"""
    base = os.path.splitext(os.path.basename(filename))[0]
    m = re.search(r'(HC\d+)', base, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return base.upper() if base else "HC0000"


def find_lby_data_offset(data: bytes) -> int:
    """Dynamically find where the actual data starts by looking for reasonable data patterns"""
    # Try different offsets, looking for sections with reasonable count values
    for offset in range(256, min(800, len(data)-100), 4):
        try:
            remaining = data[offset:]
            if len(remaining) < 80:  # need at least 20 values
                continue
            
            values = list(struct.unpack('<' + 'i'*20, remaining[:80]))
            
            # Look for a section that has reasonable positive values and variation
            positive_values = [v for v in values if 0 < v < 100000]
            if len(positive_values) >= 10:  # at least half should be reasonable positive values
                variation = max(positive_values) - min(positive_values)
                if variation > 100:  # should have some meaningful variation
                    return offset
        except:
            continue
    
    # Fallback to old offset if nothing found
    return 608


def process_lby_file(file_path: str, output_dir: str, dry_run: bool = False, 
                     force: bool = False, verbose: bool = False) -> tuple[bool, str]:
    """
    Process a single LBY file and create canonical filename in output directory.
    Returns (success, output_path)
    """
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        # Find header and extract timestamp
        data_offset = find_lby_data_offset(data)
        header = data[:data_offset]
        
        timestamp_utc = extract_lby_timestamp(header)
        if timestamp_utc is None:
            # Fallback to file mtime
            timestamp_utc = get_file_mtime_utc(file_path)
            if verbose:
                print(f"Warning: Could not extract timestamp from {file_path}, using file mtime")
        
        # Extract sequence from filename
        sequence = extract_lby_sequence(file_path)
        
        # Generate canonical filename
        canonical_name = generate_canonical_filename(
            timestamp_utc, "HCV5S", sequence, ".lby"
        )
        output_path = os.path.join(output_dir, canonical_name)
        
        if verbose:
            print(f"LBY: {os.path.basename(file_path)} -> {canonical_name}")
            print(f"  Timestamp: {timestamp_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"  Sequence: {sequence}")
        
        # Check if output already exists
        if os.path.exists(output_path) and not force:
            if verbose:
                print(f"  Skipping: {canonical_name} already exists (use --force to overwrite)")
            return True, output_path
        
        if not dry_run:
            # Create symlink to original file
            os.makedirs(output_dir, exist_ok=True)
            if os.path.exists(output_path):
                os.unlink(output_path)
            os.symlink(os.path.abspath(file_path), output_path)
            
        return True, output_path
        
    except Exception as e:
        if verbose:
            print(f"Error processing LBY file {file_path}: {e}")
        return False, ""


def process_media_file(file_path: str, output_dir: str, dry_run: bool = False,
                      force: bool = False, verbose: bool = False) -> tuple[bool, str]:
    """
    Process a single media file and create canonical filename in output directory.
    Returns (success, output_path)
    """
    try:
        # Extract timestamp (prefer metadata over file mtime)
        timestamp_utc = extract_media_timestamp(file_path)
        if timestamp_utc is None:
            timestamp_utc = get_file_mtime_utc(file_path)
            if verbose:
                print(f"Warning: Could not extract metadata timestamp from {file_path}, using file mtime")
        
        # Detect device type
        device_type = detect_device_from_metadata(file_path)
        
        # Extract sequence from filename
        sequence = extract_sequence_from_filename(file_path)
        
        # Get file extension
        _, ext = os.path.splitext(file_path)
        
        # Generate canonical filename
        canonical_name = generate_canonical_filename(
            timestamp_utc, device_type, sequence, ext
        )
        output_path = os.path.join(output_dir, canonical_name)
        
        if verbose:
            print(f"Media: {os.path.basename(file_path)} -> {canonical_name}")
            print(f"  Timestamp: {timestamp_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"  Device: {device_type}")
            print(f"  Sequence: {sequence}")
        
        # Check if output already exists
        if os.path.exists(output_path) and not force:
            if verbose:
                print(f"  Skipping: {canonical_name} already exists (use --force to overwrite)")
            return True, output_path
        
        if not dry_run:
            # Create symlink to original file
            os.makedirs(output_dir, exist_ok=True)
            if os.path.exists(output_path):
                os.unlink(output_path)
            os.symlink(os.path.abspath(file_path), output_path)
            
        return True, output_path
        
    except Exception as e:
        if verbose:
            print(f"Error processing media file {file_path}: {e}")
        return False, ""


def run_ingest(date: str, intake_dir: str, dry_run: bool = False, 
               force: bool = False, verbose: bool = False) -> int:
    """
    Main ingest function. Process all files from intake date directory.
    Returns 0 on success, 1 on error.
    """
    # Expand paths
    intake_path = Path(intake_dir).expanduser()
    intake_date_dir = intake_path / f"{date}_import"
    
    if not intake_date_dir.exists():
        print(f"Error: Intake directory does not exist: {intake_date_dir}", file=sys.stderr)
        return 1
    
    if not intake_date_dir.is_dir():
        print(f"Error: Intake path is not a directory: {intake_date_dir}", file=sys.stderr)
        return 1
    
    # Output directory is _StagedUTC in parent of intake
    output_dir = intake_path.parent / "_StagedUTC"
    
    if verbose:
        print(f"Processing intake directory: {intake_date_dir}")
        print(f"Output directory: {output_dir}")
        if dry_run:
            print("DRY RUN MODE - no files will be created")
        print()
    
    # Find all processable files
    all_files = []
    for ext in ALL_EXTENSIONS:
        pattern = str(intake_date_dir / f"*{ext}")
        files = glob.glob(pattern, recursive=False)
        all_files.extend(files)
        
        # Also check uppercase
        pattern = str(intake_date_dir / f"*{ext.upper()}")
        files = glob.glob(pattern, recursive=False)
        all_files.extend(files)
    
    if not all_files:
        print(f"No processable files found in {intake_date_dir}")
        return 0
    
    # Sort files for consistent processing
    all_files.sort()
    
    if verbose:
        print(f"Found {len(all_files)} files to process:")
        for f in all_files:
            print(f"  {os.path.basename(f)}")
        print()
    
    # Process each file
    success_count = 0
    error_count = 0
    
    for file_path in all_files:
        _, ext = os.path.splitext(file_path)
        ext_lower = ext.lower()
        
        if ext_lower in LBY_EXTENSIONS:
            success, output_path = process_lby_file(
                file_path, str(output_dir), dry_run, force, verbose
            )
        elif ext_lower in MEDIA_EXTENSIONS:
            success, output_path = process_media_file(
                file_path, str(output_dir), dry_run, force, verbose
            )
        else:
            if verbose:
                print(f"Skipping unsupported file: {os.path.basename(file_path)}")
            continue
        
        if success:
            success_count += 1
        else:
            error_count += 1
    
    # Summary
    if dry_run:
        print(f"\nDry run complete. Would process {success_count} files, {error_count} errors.")
    else:
        print(f"\nIngest complete. Processed {success_count} files, {error_count} errors.")
        
    if verbose and success_count > 0:
        print(f"Files staged in: {output_dir}")
    
    return 0 if error_count == 0 else 1