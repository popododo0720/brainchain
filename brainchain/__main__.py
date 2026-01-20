"""
Entry point for running brainchain as a module.

Usage:
    python -m brainchain [args...]
"""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
