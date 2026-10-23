"""Resume acquisition, review, build and validate the saved top-100 snapshot.

Usage: .venv/bin/python scripts/top100/run.py [--build-only]
This reuses raw caches. A new dated census needs a fresh evidence namespace.
"""
import argparse
import pathlib
import subprocess
import sys


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build-only',action='store_true',help='rebuild and validate saved evidence without network')
    args=ap.parse_args()
    root=pathlib.Path(__file__).resolve().parents[2]
    stages=[] if args.build_only else [
        ('ranking.py',[]),('crosscheck.py',[]),('refresh.py',[]),('mutability.py',[]),
        ('repair.py',[]),('finalize_samples.py',[]),('sample_owners.py',[]),
        ('replace_burned.py',[]),('sample_owners.py',[]),('refresh.py',['--retry']),('pointers.py',[])]
    stages += [(name,[]) for name in ('build.py','report.py','sanitize.py','validate.py')]
    for name,extra in stages:
        print('Running',name,*extra,flush=True)
        subprocess.run([sys.executable,str(root/'scripts/top100'/name),*extra],cwd=root,check=True)


if __name__=='__main__':main()
