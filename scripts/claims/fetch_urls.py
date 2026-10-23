"""Fetch every URL in scripts/claims/urls.tsv (slug<TAB>url) raw into data/raw/claims-web/<slug>.html (soft-fail, <=3 req/s).
Skips slugs already saved. Prints status/size per slug."""
import sys, time, pathlib
sys.path.insert(0, 'scripts/lib')
from rawfetch import get_soft
only = set(sys.argv[1:])
for line in pathlib.Path('scripts/claims/urls.tsv').read_text().splitlines():
    if not line.strip() or line.startswith('#'): continue
    slug, url = line.split('\t')[:2]
    if only and slug not in only: continue
    r = get_soft(url, source='claims-web', key=slug, ext='html', timeout=30, retries=2)
    print(slug, r['status'], len(r['body']), r['error'] or '', flush=True)
    if not r.get('cached'): time.sleep(0.4)
