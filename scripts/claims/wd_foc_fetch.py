"""Fetch fullyonchain.art ETH directory list + every project page raw (soft-fail, ~2.5 req/s)."""
import sys, re, json, time
sys.path.insert(0,'scripts/lib')
from rawfetch import get
def tryget(key,url):
    try:
        return get(url, source='claims-web', key=key, ext='html', timeout=30, retries=2)
    except Exception as e:
        print('FAIL',key,repr(e)[:80],flush=True); return None
b=tryget('wd_foc_list_eth','https://www.fullyonchain.art/collections/chain/eth')
d=json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',b.decode('utf8','replace'),re.S).group(1))
slugs=[p['slug'] for p in d['props']['pageProps']['projects']]
print(len(slugs),flush=True)
for i,s in enumerate(slugs):
    tryget('wd_foc_'+s, 'https://www.fullyonchain.art/collections/'+s)
    time.sleep(0.4)
print('done')
