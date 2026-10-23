"""One command: .venv/bin/python -I scripts/analysis/run_all.py  (about 2 minutes). Re-reads the census parquet files (copied to a temp file)."""
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
if "--claims-only" in sys.argv:
    # Shared reviewed jobs own census/host/site work in the same tree. Refresh only
    # claim fields in existing outputs without rewriting their unrelated results.
    subprocess.run([sys.executable, "-I", str(here / "claims_refresh.py")], check=True)
    sys.exit(0)
for step in ["build_frame", "headlines", "dead_hosts", "audit", "site_data", "report", "claims_refresh"]:
    print("==", step, flush=True)
    r = subprocess.run([sys.executable, "-I", str(here / (step + ".py"))])
    if r.returncode:
        sys.exit("step %s failed" % step)
print("done")
