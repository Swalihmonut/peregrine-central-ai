#!/usr/bin/env python3
"""Convenience launcher for central_runtime_api/health_check.py."""

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from central_runtime_api.health_check import main

if __name__ == "__main__":
    main()
