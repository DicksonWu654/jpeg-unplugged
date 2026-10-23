"""Fetch OpenSea public collection API (no key) for slugs -> data/raw/claims-web/osapi_<slug>.json ; print description snippet + contracts.
usage: osapi.py slug [slug...]"""
import sys, time, json
sys.path.insert(0, 'scripts/lib')
from rawfetch import get_soft
for s in sys.argv[1:]:
    r = get_soft(f'https://api.opensea.io/api/v2/collections/{s}', source='claims-web', key=f'osapi_{s}', ext='json', timeout=30, retries=2)
    j = r['json'] or {}
    d = (j.get('description') or '').replace('\n', ' ')
    print(s, r['status'], j.get('name'), j.get('contracts'), '|', j.get('project_url'), '|', d[:260], flush=True)
    if not r.get('cached'): time.sleep(0.4)
