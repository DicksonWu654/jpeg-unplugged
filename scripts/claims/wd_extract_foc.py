import sys, re, json, glob, csv
sys.path.insert(0, 'scripts/claims'); import wd_common as C
out = []; nonclaim = []
for f in sorted(glob.glob('data/raw/claims-web/wd_foc_*.html')):
    key = f.split('/')[-1][:-5]
    if key.startswith(('wd_foc_list','wd_foc_scan','wd_foc_res','wd_foc_why')): continue
    raw = open(f, errors='replace').read()
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', raw, re.S)
    pr = json.loads(m.group(1))['props']['pageProps']['project']
    addr = (pr.get('contractId') or '').strip().lower()
    if not re.fullmatch(r'0x[0-9a-f]{40}', addr): addr = ''
    if pr.get('chain') != 'Ethereum': continue
    # JSON-escaped raw uses \n and \" — compare against raw as saved
    s, st = C.best_sentence([pr.get('description'), pr.get('body')], raw)
    p, rec = C.raw_for(key)
    url = rec['url'] if rec else ''
    if s is None:
        d = pr.get('description') or ''
        nonclaim.append((pr['projectName'], d))
        continue
    out.append(dict(address=addr, collection=pr['projectName'], claim_text=s, claim_strength=st, source_type='directory',
                    source_url=url, raw_path=p, retrieved_at=rec['retrieved_at']))
json.dump(out, open('scripts/claims/wd/foc_rows.json', 'w'), indent=0)
print(len(out), 'claim rows;', len(nonclaim), 'no-claim')
import collections; print(collections.Counter(r['claim_strength'] for r in out))
for n, d in nonclaim[:15]: print('NOCLAIM', n, '|', d[:100])
for r in out[:12]: print(r['collection'], '|', r['claim_strength'], '|', r['claim_text'][:140])
