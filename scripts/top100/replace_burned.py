"""Replace stale indexer IDs only after fresh ownerOf checks; never count burns dead."""
import asyncio
import json
from common import ROOT,OUT
from refresh import c


async def main():
    rows=json.loads((OUT/'ranking.json').read_text());state=json.loads((OUT/'gateways.json').read_text())
    c.GW_STATE.update({k:state[k] for k in ('status','ipfs_ok','ar_ok')})
    net=c.Net();await net.start();rpc=c.Rpc(net)
    for ep in c.RPC_ENDPOINTS+c.RPC_FALLBACK:net.throttle.configure(ep,interval=.4,conc=3)
    try:
        for row in rows:
            for address in row['contracts']:
                p=ROOT/f'data/raw/top100-sample-validity/{address}/result.json'
                validity=json.loads(p.read_text())
                invalid=set(validity.get('invalid',[]))
                if not invalid:continue
                res=c.load_result(c.RAW/address);ev=c.Evidence(c.RAW,address)
                keep=[t for t in res['tokens'] if t['token_id'] not in invalid]
                page=await rpc.blockscout(ev,'owned_replacement_instances',f'/tokens/{address}/instances')
                pool=list(range(64))+[int(x['id']) for x in (page or {}).get('items',[]) if str(x.get('id','')).isdigit()]
                pool=list(dict.fromkeys(pool));used={int(t['token_id']) for t in keep}
                checks=await rpc.multicall(ev,'owned_replacement_confirm',[(address,'6352211e'+c.u256(i)) for i in pool])
                good=[i for i,r in zip(pool,checks or []) if r[0] and len(r[1])==32 and int.from_bytes(r[1],'big') and i not in used]
                wanted=3-len(keep)
                chosen=good[:wanted]
                if len(chosen)<wanted:
                    # Old source contract may contain only burned/migrated NFTs.
                    # Preserve the scope gap; the canonical source collection
                    # still has independently sampled active tokens.
                    res['ownership_scope_gap']='No replacement owner found among 64 low IDs and the current indexer page; not evidence of a dead server.'
                new=await asyncio.gather(*(c.process_token(rpc,net,ev,address,res['standard'],
                    {'token_id':i,'how':'replacement for burned/stale ID; ownerOf confirmed in fresh RPC multicall'},None) for i in chosen))
                res['discarded_burned_tokens']=[t for t in res['tokens'] if t['token_id'] in invalid]
                res['tokens']=keep+list(new)
                if res.get('legacy_no_tokenURI'):
                    # Reapply the saved-source legacy adapter using repair.py
                    # after this step if an active legacy ID was found.
                    res['requires_legacy_adapter_repair']=bool(new)
                for t in res['tokens']:c.derive_token(t)
                res.update(n_sampled=len(res['tokens']),finished_at=c.now_iso(),pass_no=1)
                res['pass']=1
                ev.flush();c.save_result(c.RAW/address,res)
                print(row['name'],'discarded',sorted(invalid),'replacements',chosen,'active sample',len(res['tokens']),flush=True)
    finally:await net.close()


if __name__=='__main__':asyncio.run(main())
