"""Fetch each fullyonchain.art project's own website (projectUrl) raw. Soft-fail; 6 threads over distinct hosts (<=3 req/s per host trivially)."""
import sys, re, json, glob, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'scripts/lib')
from rawfetch import get
jobs=[]
for f in sorted(glob.glob('data/raw/claims-web/wd_foc_*.html')):
    key=f.split('/')[-1][:-5]
    if key.startswith(('wd_foc_list','wd_foc_scan','wd_foc_res','wd_foc_why')): continue
    raw=open(f,errors='replace').read()
    pr=json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',raw,re.S).group(1))['props']['pageProps']['project']
    u=(pr.get('projectUrl') or '').strip()
    if u.startswith('http'): jobs.append(('wd_site_'+key[len('wd_foc_'):],u))
print(len(jobs),flush=True)
def run(j):
    k,u=j
    try:
        b=get(u,source='claims-web',key=k,ext='html',timeout=30,retries=2); return f'OK {k} {len(b)} {u}'
    except Exception as e:
        return f'FAIL {k} {u} {repr(e)[:80]}'
with ThreadPoolExecutor(6) as ex:
    for r in ex.map(run,jobs): print(r,flush=True); time.sleep(0.05)
print('done')
