"""Print keyword-context snippets from saved raw claims-web files. usage: scan.py slug [slug...]"""
import sys, re, html, pathlib
KW = re.compile(r'(on[- ]?chain|fully on|100%|forever|stored (on|in)|ipfs|arweave|decentralized storage|permanent|immutable|blockchain)', re.I)
def text(p):
    t = pathlib.Path(p).read_text(errors='replace')
    t = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', t)
    t = re.sub(r'<[^>]+>', ' ', t)
    return re.sub(r'\s+', ' ', html.unescape(t))
for s in sys.argv[1:]:
    p = f'data/raw/claims-web/{s}.html'
    try: t = text(p)
    except Exception as e: print('##', s, 'ERR', e); continue
    print('##', s, len(t))
    last = -999; n = 0
    for m in KW.finditer(t):
        if m.start() - last < 250: continue
        last = m.start(); n += 1
        if n > 8: break
        print('  -', t[max(0, m.start()-130): m.end()+170])
