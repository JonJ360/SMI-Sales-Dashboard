"""Five-minute scheduler entrypoint: one attempt per RPC, no in-run replay.

Install beside smi_sales_refresh.py in the default Hermes scripts directory.
Failures propagate to cron; inspect indeterminate publication before manual retry.
"""
import sys
from pathlib import Path

# Hermes executes scripts via runpy; make the installed sibling import explicit.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from smi_sales_refresh import main

if __name__ == '__main__':
    sys.argv = [__file__, '--single-attempt']
    main()
