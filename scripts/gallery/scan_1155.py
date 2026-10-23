"""Discovery scan for ERC-1155: uri(id) of top collections by holders; records data: URI ones (classified for media)."""
import csv, json, sys, time
import chain
from glib import *
from concurrent.futures import ThreadPoolExecutor
from eth_abi import decode
N=int(sys.argv[1]) if len(sys.argv)>1 else 800
rows=[r for r in csv.DictReader(open(chain.ROOT/'data/universe/collections.csv')) if r['standard']=='ERC-1155' and r['spam_suspect'] not in('True','true') and r['is_scam'] not in('True','true') and r['is_ens_or_infra'] not in ('True','true')]
rows.sort(key=lambda r:-int(float(r['holders_count'] or 0))); rows=rows[:N]
out=chain.GAL/'discovery/scan1155.jsonl'
done={json.loads(l)['address'] for l in open(out)} if out.exists() else set()
def one(r):
    a=r['address']; time.sleep(0.3); res=dict(address=a,name=r['name'],holders=r['holders_count'])
    for tid in (1,0,2,3,10,100):
        try: url,j=chain.rpc_raw('eth_call',[{'to':a,'data':chain.calldata('uri(uint256)',tid)},'latest'],timeout=60,retries=3)
        except Exception as e: res['err']=str(e)[:60]; continue
        if j.get('result') and len(j['result'])>130:
            try: s=decode(['string'],bytes.fromhex(j['result'][2:]))[0]
            except Exception: continue
            res.update(tid=tid,len=len(s),prefix=s[:100])
            if s.startswith('data:'):
                try:
                    js,how=parse_json_uri(s.replace('{id}','%064x'%tid))
                    img=(js or {}).get('image'); an=(js or {}).get('animation_url')
                    res.update(image=scheme_of(img) if not (isinstance(img,str) and img.lstrip().startswith('<svg')) else 'inline-svg',animation=scheme_of(an),jname=(js or {}).get('name'))
                except Exception as e: res['parse_err']=str(e)[:60]
            res.pop('err',None); break
    return res
with ThreadPoolExecutor(3) as ex, open(out,'a') as f:
    for res in ex.map(one,[r for r in rows if r['address'] not in done]):
        f.write(json.dumps(res)+'\n'); f.flush()
