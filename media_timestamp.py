#!/usr/bin/env python3
# ABOUTME: Functions for extracting timestamps from EXIF, QuickTime, or filesystem metadata  
# ABOUTME: Renaming logic for canonical UTC filenames

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def detect_device_from_metadata(path: str) -> str:
    """
    Detect device type from metadata using exiftool. Returns 'iphone' or 'android'.
    Fallback to extension-based detection if metadata unavailable.
    """
    try:
        cmd = ["exiftool", "-Make", "-Model", "-AndroidMake", "-AndroidModel", "-j", path]
        out = subprocess.check_output(cmd)
        data = json.loads(out.decode("utf-8", errors="replace"))
        if data and len(data) > 0:
            metadata = data[0]
            
            # Check all possible make/model fields
            make = metadata.get("Make", "").lower()
            model = metadata.get("Model", "").lower()
            android_make = metadata.get("AndroidMake", "").lower()
            android_model = metadata.get("AndroidModel", "").lower()
            
            # Check for Apple/iPhone
            if make == "apple" or "iphone" in model:
                return "iphone"
            
            # Check for Android/Google
            if android_make or android_model or make == "google" or "pixel" in model:
                return "android"
                
    except Exception:
        pass
    
    # Fallback to extension-based detection
    ext_lower = os.path.splitext(path)[1].lower()
    if ext_lower in [".mov", ".heic"]:
        return "iphone"
    else:  # .mp4, .jpg, .jpeg
        return "android"


def extract_media_timestamp(path: str) -> datetime | None:
    """
    Try to extract a creation timestamp via ffprobe.
    Returns an aware UTC datetime if found, else None.
    """
    # Ask for creation_time in both container and stream tags, JSON for reliability
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_entries",
        "format_tags=creation_time:stream_tags=creation_time",
        path
    ]
    try:
        out = subprocess.check_output(cmd)
        data = json.loads(out.decode("utf-8", errors="replace"))
    except Exception:
        return None

    # Possible places creation_time may appear (container first, then streams)
    candidates = []
    fmt_tags = data.get("format", {}).get("tags", {})
    if "creation_time" in fmt_tags:
        candidates.append(fmt_tags["creation_time"])

    for stream in data.get("streams", []):
        tags = stream.get("tags", {})
        if "creation_time" in tags:
            candidates.append(tags["creation_time"])

    # Parse the first valid ISO-ish timestamp we can
    for ts in candidates:
        dt = _parse_iso_to_utc(ts)
        if dt:
            return dt
    return None


def get_file_mtime_utc(path: str) -> datetime:
    """Fallback: file modification time as UTC-aware datetime."""
    ts = os.path.getmtime(path)
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _parse_iso_to_utc(s: str) -> datetime | None:
    """
    Parse common ffprobe date formats into an aware UTC datetime.
    Examples:
      '2025-08-20T18:23:45.000000Z'
      '2025-08-20T18:23:45Z'
      '2025-08-20 18:23:45'
    """
    s = s.strip()
    try:
        # If it ends with Z or includes offset, fromisoformat (with tweaks) can handle it
        if s.endswith("Z"):
            s = s.replace("Z", "+00:00")
        # Some files use space instead of T
        s = s.replace(" ", "T")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            # Assume UTC if no tz in metadata
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        # Try a couple of common fallback formats
        fmts = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ]
        for f in fmts:
            try:
                dt = datetime.strptime(s, f).replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                pass
    return None


def generate_canonical_filename(timestamp_utc: datetime, source_tag: str, 
                               sequence_tag: str = "", extension: str = "") -> str:
    """
    Generate canonical UTC filename: YYYYMMDDThhmmssZ__SRC__SEQ.ext
    
    Args:
        timestamp_utc: UTC datetime
        source_tag: Source tag (e.g., 'HCV5S', 'iphone', 'android')
        sequence_tag: Sequence identifier (optional, e.g., 'HC0057')
        extension: File extension including dot (e.g., '.lby', '.mp4')
    """
    # Format timestamp as YYYYMMDDThhmmssZ
    utc_str = timestamp_utc.strftime("%Y%m%dT%H%M%SZ")
    
    # Build filename components
    parts = [utc_str, source_tag]
    if sequence_tag:
        parts.append(sequence_tag)
    
    base_name = "__".join(parts)
    return base_name + extension.lower()


def extract_sequence_from_filename(filename: str) -> str:
    """
    Extract sequence identifier from filename.
    For videos like 'PXL_20250910_152856979.TS.mp4', returns base without timestamp.
    """
    base = os.path.splitext(os.path.basename(filename))[0]
    
    # Remove common timestamp patterns from Android files
    # Pattern: PXL_YYYYMMDD_HHMMSSXXX -> PXL
    base = re.sub(r'_\d{8}_\d{9,}', '', base)
    
    # Remove .TS suffix if present
    base = re.sub(r'\.TS$', '', base, re.IGNORECASE)
    
    return base if base else "MEDIA"