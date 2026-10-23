"""claims web-directories helper: fetch key<TAB>url lines (arg: file) raw into data/raw/claims-web/. Soft-fail, <=3 req/s."""
import sys, time
sys.path.insert(0,'scripts/lib')
from rawfetch import get
for line in open(sys.argv[1]):
    line=line.strip()
    if not line or line.startswith('#'): continue
    key,url=line.split('\t')[:2]
    try:
        b=get(url, source='claims-web', key=key, ext='html', timeout=30, retries=2)
        print('OK',key,len(b),url,flush=True)
    except Exception as e:
        print('FAIL',key,url,repr(e)[:100],flush=True)
    time.sleep(0.4)
