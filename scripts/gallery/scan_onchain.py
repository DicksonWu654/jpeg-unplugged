"""Discovery scan: for the top ERC-721 collections in data/universe/collections.csv (by holders, non-spam), call tokenURI on a few ids and
record whether it is a data: URI. Output data/gallery/discovery/scan.jsonl (prefix 120 chars, length, sha256). Candidate finder only."""
import csv, json, sys, time, hashlib, os
import chain
from concurrent.futures import ThreadPoolExecutor
from eth_abi import decode
N=int(sys.argv[1]) if len(sys.argv)>1 else 3000
rows=[r for r in csv.DictReader(open(chain.ROOT/'data/universe/collections.csv')) if r['standard']=='ERC-721' and r['spam_suspect'] not in('True','true') and r['is_scam'] not in('True','true') and r['is_ens_or_infra'] not in ('True','true')]
rows.sort(key=lambda r:-int(float(r['holders_count'] or 0)))
rows=rows[:N]
out=chain.GAL/'discovery'; out.mkdir(exist_ok=True)
fn=out/'scan.jsonl'
done=set()
if fn.exists(): done={json.loads(l)['address'] for l in open(fn)}
def one(r):
    a=r['address']; time.sleep(0.3)
    res=dict(address=a,name=r['name'],holders=r['holders_count'])
    for tid in (1,0,2,10,100):
        try:
            url,j=chain.rpc_raw('eth_call',[{'to':a,'data':chain.calldata('tokenURI(uint256)',tid)},'latest'],timeout=60,retries=3)
        except Exception as e:
            res['err']=str(e)[:80]; continue
        if j.get('result') and len(j['result'])>130:
            try: s=decode(['string'],bytes.fromhex(j['result'][2:]))[0]
            except Exception: continue
            res.update(tid=tid,len=len(s),prefix=s[:120],sha=hashlib.sha256(s.encode()).hexdigest()); res.pop('err',None); break
    return res
with ThreadPoolExecutor(3) as ex, open(fn,'a') as f:
    for res in ex.map(one,[r for r in rows if r['address'] not in done]):
        f.write(json.dumps(res)+'\n'); f.flush()
