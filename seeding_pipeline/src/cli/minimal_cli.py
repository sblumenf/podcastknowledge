#!/usr/bin/env python3
"""
Minimal VTT CLI - Fast, lightweight entry point for basic VTT processing.

This minimal CLI provides essential VTT processing functionality with:
- Fast startup time (< 100ms)
- Minimal memory footprint
- No heavy dependencies required
- Simple error handling
- Clear progress feedback

Usage:
    python -m src.cli.minimal_cli transcript.vtt
    python src/cli/minimal_cli.py transcript.vtt --verbose
"""

import argparse
import sys
import os
import time
from pathlib import Path
from typing import Optional, Tuple

# Add project root to path for imports (like main CLI does)
project_root = Path(__file__).parent.parent.parent  # Go up to seeding_pipeline/
sys.path.insert(0, str(project_root))

# Only import standard library at module level for fast startup  
# Heavy imports are deferred until actually needed


def create_parser() -> argparse.ArgumentParser:
    """Create minimal argument parser with essential options only."""
    parser = argparse.ArgumentParser(
        description='Minimal VTT transcript processor - Fast processing with essential features only',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s transcript.vtt               # Process VTT file
  %(prog)s transcript.vtt --verbose     # With detailed output
  %(prog)s transcript.vtt --quiet       # Suppress progress output
        '''
    )
    
    # Single positional argument for simplicity
    parser.add_argument(
        'vtt_file',
        type=str,
        help='VTT file to process'
    )
    
    # Minimal optional arguments
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output with detailed processing information'
    )
    
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress progress output (errors still shown)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Parse and validate VTT file without processing'
    )
    
    return parser


def validate_vtt_file(file_path: Path) -> Tuple[bool, Optional[str]]:
    """Validate VTT file with minimal overhead - no heavy imports."""
    # Check file existence and basic properties
    if not file_path.exists():
        return False, f"File not found: {file_path}"
    
    if not file_path.is_file():
        return False, f"Not a file: {file_path}"
    
    if file_path.suffix.lower() != '.vtt':
        return False, f"Not a VTT file (expected .vtt extension): {file_path}"
    
    # Quick VTT format validation - check header
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            if not first_line.upper().startswith('WEBVTT'):
                return False, "Invalid VTT format (missing WEBVTT header)"
    except UnicodeDecodeError:
        return False, "Cannot read file (invalid UTF-8 encoding)"
    except Exception as e:
        return False, f"Cannot read file: {e}"
    
    return True, None


def simple_progress(message: str, show: bool = True) -> None:
    """Display simple progress message without dependencies."""
    if show:
        timestamp = time.strftime('%H:%M:%S')
        print(f"[{timestamp}] {message}")


def process_vtt(file_path: Path, args) -> int:
    """Process VTT file with minimal imports and dependencies."""
    start_time = time.time()
    
    try:
        # Lazy import heavy modules only when actually processing
        simple_progress(f"Loading VTT parser...", not args.quiet)
        
        # Import only what we need from the VTT module
        from src.vtt.vtt_parser import VTTParser
        
        simple_progress(f"Parsing VTT file: {file_path.name}", not args.quiet)
        
        # Create parser and process file
        parser = VTTParser()
        segments = parser.parse_file(str(file_path))
        
        processing_time = time.time() - start_time
        
        if args.dry_run:
            simple_progress(f"✓ Dry run complete - VTT file is valid", not args.quiet)
        else:
            simple_progress(f"✓ Basic parsing complete", not args.quiet)
        
        # Show results
        if not args.quiet:
            print(f"\nResults:")
            print(f"  Segments processed: {len(segments)}")
            print(f"  Processing time: {processing_time:.2f}s")
            print(f"  File size: {file_path.stat().st_size:,} bytes")
            
            if args.verbose:
                print(f"\nFirst few segments:")
                for i, segment in enumerate(segments[:3]):
                    start = getattr(segment, 'start_time', 'unknown')
                    end = getattr(segment, 'end_time', 'unknown') 
                    text = getattr(segment, 'text', 'No text')
                    print(f"  {i+1}. [{start}-{end}] {text[:60]}...")
        
        return 0
        
    except ImportError as e:
        print(f"Error: Missing module - {e}", file=sys.stderr)
        print("This might indicate missing dependencies or incorrect installation", file=sys.stderr)
        return 1
        
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}", file=sys.stderr)
        return 1
        
    except PermissionError as e:
        print(f"Error: Permission denied - {e}", file=sys.stderr)
        return 1
        
    except MemoryError:
        print("Error: Out of memory - try processing a smaller file", file=sys.stderr)
        return 1
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        return 130
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            print("\nDetailed error information:", file=sys.stderr)
            traceback.print_exc()
        else:
            print("Use --verbose for detailed error information", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point with minimal overhead and fast startup."""
    # Parse arguments first (very fast)
    parser = create_parser()
    
    try:
        args = parser.parse_args()
    except SystemExit as e:
        return e.code
    
    # Quick validation before any heavy imports
    file_path = Path(args.vtt_file)
    is_valid, error_message = validate_vtt_file(file_path)
    
    if not is_valid:
        print(f"Error: {error_message}", file=sys.stderr)
        return 1
    
    # Show startup info
    if not args.quiet:
        print("VTT Minimal CLI - Fast transcript processing")
        print("=" * 45)
    
    # Process the file
    return process_vtt(file_path, args)


if __name__ == '__main__':
    sys.exit(main())