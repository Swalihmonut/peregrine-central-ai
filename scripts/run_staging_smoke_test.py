#!/usr/bin/env python3
"""Convenience script to run the isolated staging smoke test."""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.staging_smoke_test import main

if __name__ == "__main__":
    main()
