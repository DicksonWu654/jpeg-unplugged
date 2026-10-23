"""Fresh ownership sanity check for sampled ERC-721 IDs, preserving evidence."""
import asyncio
import json
import sys
from common import ROOT,OUT
from refresh import c,PUNKS,selector
from pointers import audit
import mlib


async def one(row,address,rpc,sem):
    async with sem:
        res=c.load_result(c.RAW/address);tokens=res.get('tokens',[])
        directory=ROOT/'data/raw/top100-sample-validity'
        ev=c.Evidence(directory,address)
        a,_=audit(address);abi=mlib.abi_of((a.get('proxy') or {}).get('impl') or address) or []
        have=any(f.get('name')=='ownerOf' for f in abi)
        if address==PUNKS:
            signature=selector('punkIndexToAddress(uint256)').removeprefix('0x')
        elif '1155' in res.get('standard','') or not have:
            c.jdump(directory/address/'result.json',{'contract':address,'check':'ERC-1155 or legacy ABI; ownerOf not applicable','invalid':[]})
            return
        else:signature='6352211e'
        result=await rpc.multicall(ev,'validate_sample_owners',[(address,signature+c.u256(t['token_id'])) for t in tokens]) if tokens else []
        checks=[{'token_id':t['token_id'],'owned':bool(r[0] and len(r[1])==32 and int.from_bytes(r[1],'big'))}
                for t,r in zip(tokens,result or [])]
        invalid=[r['token_id'] for r in checks if not r['owned']]
        c.jdump(directory/address/'result.json',{'contract':address,'checked_at':c.now_iso(),'checks':checks,'invalid':invalid,
                                                'rpc_unknown':result is None})
        ev.flush()
        if invalid:print('INVALID',row['name'],address,invalid,flush=True)


async def main():
    rows=json.loads((OUT/'ranking.json').read_text());net=c.Net();await net.start();rpc=c.Rpc(net)
    for ep in c.RPC_ENDPOINTS+c.RPC_FALLBACK:net.throttle.configure(ep,interval=.4,conc=3)
    sem=asyncio.Semaphore(8)
    try:await asyncio.gather(*(one(r,a,rpc,sem) for r in rows for a in r['contracts']))
    finally:await net.close()
    print('Ownership sanity check completed.',flush=True)


if __name__=='__main__':asyncio.run(main())
