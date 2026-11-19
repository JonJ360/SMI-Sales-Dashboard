"""Compatibility entry point: approved estimated-overall browser contract.
Legacy literal-byte UI and outline-only expectations are superseded.
"""
from pathlib import Path
from verify_estimated_progress_browser import run
if __name__ == '__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    run(ap.parse_args().output)
