#!/usr/bin/env python3
"""
License Key Generator - Quick CLI tool for Phase 1 testing.

Usage:
    python generate_license.py --tier personal --days 30
    python generate_license.py --trial --email friend@example.com
    python generate_license.py validate PERS-12345678-ABCDEFGH-CHECKSUM
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from github_issue_solver.license import main

if __name__ == '__main__':
    main()
