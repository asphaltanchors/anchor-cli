#!/usr/bin/env python3
# ABOUTME: Main CLI entrypoint for anchor test processing pipeline
# ABOUTME: Provides subcommands for organizing, processing, and promoting anchor test data

import argparse
import os
import sys
from pathlib import Path


def create_parser():
    """Create the main argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog='anchor',
        description='Anchor test processing pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  anchor ingest 2025-09-10              # Process files from intake date
  anchor ingest --date 2025-09-10       # Same as above  
  anchor ingest 2025-09-10 --dry-run    # Preview what would happen
        """
    )
    
    # Global options
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--intake-dir', 
                       default='~/Projects/AnchorTesting/_Intake',
                       help='Path to intake directory (default: %(default)s)')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # ingest subcommand
    ingest_parser = subparsers.add_parser(
        'ingest',
        help='Process intake files into staged UTC format'
    )
    ingest_parser.add_argument('date', nargs='?',
                              help='Date to process (YYYY-MM-DD format)')
    ingest_parser.add_argument('--date',
                              help='Date to process (alternative to positional)')
    ingest_parser.add_argument('--dry-run', action='store_true',
                              help='Show what would happen without processing')
    ingest_parser.add_argument('--force', action='store_true',
                              help='Overwrite existing staged files')
    
    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Handle date argument (positional or --date flag) 
    if args.command == 'ingest':
        # Get the date from positional argument or --date flag
        date_arg = None
        if hasattr(args, 'date') and args.date:
            date_arg = args.date
        elif hasattr(args, '__dict__'):
            # Check if there's a date in the namespace
            for key, val in args.__dict__.items():
                if key == 'date' and val:
                    date_arg = val
                    break
        
        if not date_arg:
            print("Error: Date is required for ingest command", file=sys.stderr)
            print("Usage: anchor ingest YYYY-MM-DD", file=sys.stderr)
            return 1
        
        # Import and run ingest
        try:
            from ingest import run_ingest
            return run_ingest(
                date=date_arg,
                intake_dir=args.intake_dir,
                dry_run=getattr(args, 'dry_run', False),
                force=getattr(args, 'force', False),
                verbose=getattr(args, 'verbose', False)
            )
        except ImportError as e:
            print(f"Error: Could not import ingest module: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error running ingest: {e}", file=sys.stderr)
            if getattr(args, 'verbose', False):
                import traceback
                traceback.print_exc()
            return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())