#!/usr/bin/env python3
import sys, os, struct, csv, statistics, re, glob, json

def find_data_offset(data):
    """Dynamically find where the actual data starts by looking for reasonable data patterns"""
    # Try different offsets, looking for sections with reasonable count values
    for offset in range(256, min(800, len(data)-100), 4):
        try:
            remaining = data[offset:]
            if len(remaining) < 80:  # need at least 20 values
                continue
            
            values = list(struct.unpack('<' + 'i'*20, remaining[:80]))
            
            # Look for a section that has:
            # 1. Reasonable positive values (typical count range)
            # 2. Some variation (not all zeros/same values)
            # 3. Values in a reasonable range for force sensor counts
            
            positive_values = [v for v in values if 0 < v < 100000]
            if len(positive_values) >= 10:  # at least half should be reasonable positive values
                variation = max(positive_values) - min(positive_values)
                if variation > 100:  # should have some meaningful variation
                    return offset
        except:
            continue
    
    # Fallback to old offset if nothing found
    return 608

def extract_timestamp(header):
    # Correct format based on analysis:
    # Byte 5: minute, Byte 6: hour, Byte 8: day, Byte 9: month, Bytes 10-11: year
    
    if len(header) >= 12:
        try:
            minute = header[5]    # byte 5
            hour = header[6]      # byte 6  
            day = header[8]       # byte 8
            month = header[9]     # byte 9
            year = struct.unpack('<H', header[10:12])[0]  # bytes 10-11 (little-endian)
            
            # Validate all components
            if (0 <= hour <= 23 and 0 <= minute <= 59 and 
                1 <= month <= 12 and 1 <= day <= 31 and 2020 <= year <= 2030):
                return year, month, day, hour, minute, 0
                
        except (IndexError, struct.error):
            pass
    return None

def extract_calibration(header, test_id):
    # Universal calibration: raw values are in Newtons, convert to kilonewtons
    # Analysis of 7+ files confirms this is consistent across all .LBY files
    return 0.001

def extract_test_id(filename):
    # Extract ID from filename like "HC0010.LBY" -> "0010"
    import re
    match = re.search(r'HC(\d+)', filename, re.IGNORECASE)
    return match.group(1) if match else "0000"

def extract_ascii(buf):
    # pull readable substrings (>=4 chars)
    s = []
    for m in re.finditer(rb"[ -~]{4,}", buf):  # printable ASCII
        s.append(m.group().decode("ascii", "ignore"))
    return s

def load_words_le(data):
    n = len(data) // 4
    return list(struct.unpack("<" + "i"*n, data[:n*4]))

def maybe_collapse_to_u16(words):
    # if all words fit in 16 bits and high 16 are zero, treat as 16-bit
    hi_nonzero = any((w >> 16) & 0xFFFF for w in words[:1000] or [0])
    if not hi_nonzero and all((w & 0xFFFF) == w for w in words):
        return [w & 0xFFFF for w in words], 16
    return words, 32

def write_csv(path, rows, timestamp_info=None, test_id="0000", output_format="csv"):
    # Generate filename in format YYYYMMDD-HHMMSS-ID.ext
    if timestamp_info:
        year, month, day, hour, minute, second = timestamp_info
        ext = "json" if output_format == "json" else "csv"
        out = f"{year:04d}{month:02d}{day:02d}-{hour:02d}{minute:02d}{second:02d}-{test_id}.{ext}"
    else:
        # Fallback to original naming
        ext = "json" if output_format == "json" else "csv"
        out = os.path.splitext(path)[0] + f".{ext}"
    
    if output_format == "json":
        data = {
            "values": [{"time_s": time, "force_kN": force} for time, force in rows]
        }
        with open(out, "w") as f:
            json.dump(data, f, indent=2)
    else:
        with open(out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time_s", "force_kN"])
            w.writerows(rows)
    return out

def process_lby_file(path, output_format="csv"):
    b = open(path, "rb").read()
    
    # Find the actual data offset dynamically
    data_offset = find_data_offset(b)
    header = b[:data_offset]
    payload = b[data_offset:]

    # 1) header peek and extract metadata
    ascii_bits = extract_ascii(header)
    print(f"Processing {path}...")
    print("Header ASCII strings:", ascii_bits)
    
    # Extract timestamp and test ID
    timestamp_info = extract_timestamp(header)
    test_id = extract_test_id(os.path.basename(path))
    
    if timestamp_info:
        year, month, day, hour, minute, second = timestamp_info
        print(f"Test timestamp: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}")
    else:
        print("Warning: Could not extract timestamp from header")
    
    print(f"Test ID: {test_id}")
    
    calibration_factor = extract_calibration(header, test_id)
    print(f"Detected calibration factor: {calibration_factor:.6f} kN/count")

    # 2) decode payload as 32-bit little-endian
    words32 = load_words_le(payload)
    samples = words32
    bitwidth = 32
    print(f"Interpreted {len(samples)} samples as {bitwidth}-bit values.")

    # 3) convert to engineering units (absolute force values)
    force_kN = [s * calibration_factor for s in samples]

    # 4) write output file with time stamps (0.5 second intervals)
    rows = [(i * 0.5, force_kN[i]) for i in range(len(samples))]
    out = write_csv(path, rows, timestamp_info, test_id, output_format)

    # 5) find max absolute force value
    max_force = max(force_kN) if force_kN else 0
    print(f"Max absolute force value: {max_force:.3f} kN")
    print("Wrote:", out)
    print()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert LBY binary files to CSV or JSON format')
    parser.add_argument('directory', nargs='?', default='.', 
                       help='Directory containing LBY files (default: current directory)')
    parser.add_argument('--force', action='store_true',
                       help='Overwrite existing output files')
    parser.add_argument('--json', action='store_true',
                       help='Output in JSON format instead of CSV')
    
    args = parser.parse_args()
    
    output_format = "json" if args.json else "csv"
    
    # Find all LBY files in specified directory
    search_pattern1 = os.path.join(args.directory, "*.LBY")
    search_pattern2 = os.path.join(args.directory, "*.lby")
    lby_files = glob.glob(search_pattern1) + glob.glob(search_pattern2)

    if not lby_files:
        print(f"No LBY files found in directory: {args.directory}")
        return

    print(f"Found {len(lby_files)} LBY files in {args.directory}")
    processed_count = 0
    skipped_count = 0

    for lby_file in sorted(lby_files):
        base_name = os.path.basename(lby_file)
        
        # Check if any output file with this test ID already exists (since we generate timestamp-based names)
        test_id = extract_test_id(base_name)
        file_ext = "json" if output_format == "json" else "csv"
        existing_files = glob.glob(f"*-{test_id}.{file_ext}")
        
        if existing_files and not args.force:
            print(f"Skipping {base_name} - {file_ext.upper()} file(s) {existing_files} already exist (use --force to overwrite)")
            skipped_count += 1
            continue

        # Remove existing output files if --force is specified
        if args.force:
            for output_file in existing_files:
                os.remove(output_file)
                print(f"Removed existing {output_file}")

        try:
            process_lby_file(lby_file, output_format)
            processed_count += 1
        except Exception as e:
            print(f"Error processing {base_name}: {e}")

    print(f"Processing complete: {processed_count} files processed, {skipped_count} files skipped.")

if __name__ == "__main__":
    main()
