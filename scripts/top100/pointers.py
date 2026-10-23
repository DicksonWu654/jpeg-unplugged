"""Read available verified base-URI/renderer getters without changing state."""
import asyncio
import json
import re
import sys
from common import ROOT, OUT
from refresh import c, selector
sys.path.insert(0,str(ROOT/'scripts/mutability'))
import mlib


def audit(address):
    for directory in ('data/raw/top100-mutability','data/mutability/evidence'):
        p=ROOT/directory/f'{address}.json'
        if p.exists():return json.loads(p.read_text()),p
    return {},None


async def one(address,rpc,sem):
    async with sem:
        root=ROOT/'data/raw/top100-pointers'
        if (root/address/'result.json').exists():return
        ev=c.Evidence(root,address)
        a,path=audit(address)
        impl=(a.get('proxy') or {}).get('impl')
        funcs=mlib.abi_of(impl or address) or []
        getters=[]
        for f in funcs:
            if (f.get('type')=='function' and not f.get('inputs') and f.get('stateMutability') in ('view','pure')
                and len(f.get('outputs',[]))==1 and f['outputs'][0]['type'] in ('string','address')
                and re.search(r'uri|url|renderer|descriptor|metadata|image|base',f['name'],re.I)):
                getters.append(f)
        values=[]
        for f in getters[:20]:
            sig=f['name']+'()'
            r=await rpc.eth_call(ev,sig,address,selector(sig).removeprefix('0x'))
            value=None
            if r['ok']:
                if f['outputs'][0]['type']=='string':value,_=c.decode_abi_string(r['result'])
                elif len(r['result'] or '')==66:value='0x'+r['result'][-40:]
            values.append({'getter':sig,'type':f['outputs'][0]['type'],'ok':r['ok'],'value':value,'error':r.get('error')})
        c.jdump(root/address/'result.json',{'address':address,'checked_at':c.now_iso(),'getters':values,
                                          'audit':str(path.relative_to(ROOT)) if path else None})
        ev.flush()
        print(address,len(values),flush=True)


async def main():
    rows=json.loads((OUT/'ranking.json').read_text());addresses={a for r in rows for a in r['contracts']}
    addresses.add('0x16f5a35647d6f03d5d3da7b35409d65ba03af3b2')
    net=c.Net();await net.start();rpc=c.Rpc(net)
    for ep in c.RPC_ENDPOINTS+c.RPC_FALLBACK:net.throttle.configure(ep,interval=.4,conc=3)
    sem=asyncio.Semaphore(8)
    try:await asyncio.gather(*(one(a,rpc,sem) for a in sorted(addresses)))
    finally:await net.close()


if __name__=='__main__':asyncio.run(main())
