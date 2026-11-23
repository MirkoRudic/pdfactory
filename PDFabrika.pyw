"""Old name of the launcher (desktop shortcuts and updates from before the rename call it): runs PDFactory.pyw."""
import runpy
import sys
from pathlib import Path

p = Path(__file__).resolve().with_name("PDFactory.pyw")
sys.argv[0] = str(p)
runpy.run_path(str(p), run_name="__main__")
