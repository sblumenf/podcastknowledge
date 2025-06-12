"""Podcast Transcription Pipeline - Core Package."""

__version__ = "0.1.0"

# Load environment variables from .env file as early as possible
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    import sys
    print("\nError: Required dependencies not installed.", file=sys.stderr)
    print("\nPlease activate the virtual environment and install dependencies:", file=sys.stderr)
    print("  source venv/bin/activate", file=sys.stderr)
    print("  pip install -r requirements.txt", file=sys.stderr)
    print("\nOr use the wrapper script:", file=sys.stderr)
    print("  ./transcribe <command>", file=sys.stderr)
    sys.exit(1)