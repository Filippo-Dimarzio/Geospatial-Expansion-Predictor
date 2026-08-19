"""Backward-compatible pipeline entry point."""

from market_predictor.cli import main

if __name__ == "__main__":
    import sys

    # Default to run-pipeline when invoked as python pipeline.py
    if len(sys.argv) == 1:
        sys.argv.append("run-pipeline")
    main()
