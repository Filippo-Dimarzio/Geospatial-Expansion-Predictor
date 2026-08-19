"""Backward-compatible mock data entry point."""

import sys

from market_predictor.cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(["generate-data", "--mode", "mock"])
    main()
