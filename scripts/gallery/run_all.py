"""Render all (or named) gallery slugs with 3 parallel workers. Usage: run_all.py [--conds A,A2,B,C] [slug ...]"""
import subprocess, sys, pathlib, json
from concurrent.futures import ThreadPoolExecutor
ROOT = pathlib.Path(__file__).resolve().parents[2]
GAL = ROOT / "data" / "gallery"
args = sys.argv[1:]
conds = "A,A2,B,C"
if args and args[0] == "--conds": conds = args[1]; args = args[2:]
slugs = args or sorted(p.parent.name for p in GAL.glob("*/meta.json"))
def run(s):
    r = subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/gallery/render.py"), s, "--conds", conds], capture_output=True, text=True, timeout=900)
    return s, r.returncode, (r.stdout + r.stderr)[-400:]
with ThreadPoolExecutor(3) as ex:
    for s, rc, out in ex.map(run, slugs):
        print(s, "rc", rc, "" if rc == 0 else out)
