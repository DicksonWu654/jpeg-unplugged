"""Pass 2 of the discovery scan: for collections whose tokenURI is a data: URI, fetch it again, parse the JSON and classify the media fields,
statically scan embedded SVG/HTML for externally-hosted resources. Output data/gallery/discovery/classified.jsonl"""
import json, time, hashlib, sys
import chain
from glib import *
from concurrent.futures import ThreadPoolExecutor
from eth_abi import decode
rows=[json.loads(l) for l in open(chain.GAL/'discovery/scan.jsonl')]
rows=[r for r in rows if r.get('prefix','').startswith('data:')]
out=chain.GAL/'discovery/classified.jsonl'
done={json.loads(l)['address'] for l in open(out)} if out.exists() else set()
def one(r):
    time.sleep(0.3)
    a=r['address']; res=dict(address=a,name=r['name'],holders=r['holders'],tid=r['tid'],len=r['len'])
    try:
        url,j=chain.rpc_raw('eth_call',[{'to':a,'data':chain.calldata('tokenURI(uint256)',r['tid'])},'latest'],timeout=60,retries=3)
        s=decode(['string'],bytes.fromhex(j['result'][2:]))[0]
        js,how=parse_json_uri(s)
        if js is None:
            res['note']='not json: '+s[:60]; return res
        img=js.get('image') or js.get('image_data'); an=js.get('animation_url')
        res.update(image=scheme_of(img) if not (isinstance(img,str) and img.lstrip().startswith('<svg')) else 'inline-svg', animation=scheme_of(an),
                   external_url=scheme_of(js.get('external_url')), keys=sorted(js.keys())[:12], jname=js.get('name'))
        for lab,v in (('img',img),('anim',an)):
            if isinstance(v,str) and (v.startswith('data:image/svg') or v.startswith('data:text/html') or v.lstrip().startswith('<svg')):
                txt=v if v.lstrip().startswith('<svg') else decode_data_uri(v)[1].decode('utf-8','replace')
                res[lab+'_declared']=scan_declared(txt)
                res[lab+'_bytes']=len(txt)
    except Exception as e:
        res['err']=str(e)[:100]
    return res
with ThreadPoolExecutor(3) as ex, open(out,'a') as f:
    for res in ex.map(one,[r for r in rows if r['address'] not in done]):
        f.write(json.dumps(res)+'\n'); f.flush()
