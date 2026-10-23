"""Review sampling failures and legacy metadata adapters; retain original evidence."""
import asyncio
import json
import re
from common import ROOT, OUT
import rawfetch as rf
from refresh import c, selector

MASKS='0xc2c747e0f7004f9e8817db2ca4997657a7746928'
ENS='0x57f1887a8bf19b14fc0df6fd9b2acc9af147ea85'
LEGACY={MASKS,ENS,'0x23392b8615d68d8d3bc9cd1b7ea43e715db4512d'}


async def repair(row, address, rpc, net):
    res=c.load_result(c.RAW/address)
    ev=c.Evidence(c.RAW,address)
    tokens=res.get('tokens',[])
    # Use the indexer's current IDs, not unminted probes or stale burned IDs.
    all_broken=bool(tokens) and all(t['meta_class']=='broken' for t in tokens)
    if len(tokens)<3 or (all_broken and address not in LEGACY):
        info=await rpc.blockscout(ev,'repair_token_info',f'/tokens/{address}')
        std=(info or {}).get('type') or res['standard']
        res['standard']=std
        page=await rpc.blockscout(ev,'repair_instances',f'/tokens/{address}/instances')
        items=(page or {}).get('items',[])
        ids=sorted({int(v['id']) for v in items if str(v.get('id','')).isdigit()})
        if len(ids)>=3:
            samples=[{'token_id':ids[i],'how':'fresh Blockscout instances after insufficient/stale RPC sample'} for i in (0,len(ids)//2,len(ids)-1)]
            new=await asyncio.gather(*(c.process_token(rpc,net,ev,address,std,s,res.get('renderer')) for s in samples))
            res['superseded_tokens']=tokens
            res['tokens']=list(new)
        res['sampling_review']={'indexed_ids_in_page':len(ids),'token_type':std,'info_type':(info or {}).get('type'),
                               'note':'indexer not exhaustive; empty companion contracts remain outside token-level aggregate'}
    if address==ENS:
        page=await rpc.blockscout(ev,'ens_current_ids',f'/tokens/{address}/instances')
        ids=[int(x['id']) for x in (page or {}).get('items',[]) if str(x.get('id','')).isdigit()]
        checks=await rpc.multicall(ev,'ens_validate_active',[(address,'6352211e'+c.u256(i)) for i in ids])
        live=[i for i,check in zip(ids,checks or []) if check[0] and len(check[1])==32]
        if len(live)>=3:
            res['superseded_expired_name_tokens']=res['tokens']
            res['tokens']=await asyncio.gather(*(c.process_token(rpc,net,ev,address,res['standard'],
                {'token_id':i,'how':'Blockscout IDs; current ownerOf confirmed (expired names excluded)'},None) for i in live[:3]))
    if address in LEGACY:
        # These verified contracts omit tokenURI entirely. A missing selector
        # does not prove their externally provided metadata is dead.
        res['legacy_no_tokenURI']=True
        for t in res['tokens']:
            t['contract_tokenURI_class']=t['meta_class']
            t['contract_tokenURI_reason']=t.get('meta_reason')
            tid=t['token_id']
            if address==ENS:
                url=f'https://metadata.ens.domains/mainnet/{ENS}/{tid}'
            else:
                source=f'https://opensea.io/assets/ethereum/{address}/{tid}'
                fetched=await asyncio.to_thread(rf.get_soft,source,source='top100-api',key=f'legacy-asset-{address}-{tid}',
                                                ext='html',retries=1,timeout=35)
                text=fetched['body'].decode(errors='replace')
                match=re.search(r'"tokenUri":("(?:[^"\\]|\\.)*")',text)
                if not match:
                    t.update(meta_class='other',meta_reason='legacy-adapter-unresolved',meta_scheme='legacy')
                    t.pop('meta_target',None)
                    continue
                url=json.loads(match[1])
                t['adapter_evidence']=f'data/raw/top100-api/legacy-asset-{address}-{tid}.html'
            t['special_case']='external-metadata-adapter-no-tokenURI'
            t['uri_raw']=url
            cls=c.classify_uri(url)
            t.update(meta_class=cls['cls'],meta_host=cls.get('host'),meta_reg_domain=cls.get('reg_domain'),
                     meta_target=c.new_target('metadata',url,cls))
            t.pop('media',None)
            await c.resolve_token(net,ev,t,1)
    for t in res['tokens']:
        c.derive_token(t)
    res['n_sampled']=len(res['tokens'])
    res['finished_at']=c.now_iso()
    ev.flush()
    c.save_result(c.RAW/address,res)
    print(row['name'],address,'samples',len(res['tokens']),'verdict',c.collection_row(res)['liveness'],flush=True)


async def main():
    selected=json.loads((OUT/'ranking.json').read_text())
    state=json.loads((OUT/'gateways.json').read_text());c.GW_STATE.update({k:state[k] for k in ('status','ipfs_ok','ar_ok')})
    net=c.Net();await net.start();rpc=c.Rpc(net)
    for endpoint in c.RPC_ENDPOINTS+c.RPC_FALLBACK:net.throttle.configure(endpoint,interval=.4,conc=3)
    try:
        for row in selected:
            for address in row['contracts']:
                res=c.load_result(c.RAW/address)
                tokens=res.get('tokens',[])
                if address in LEGACY or len(tokens)<3 or (tokens and all(t['meta_class']=='broken' for t in tokens)):
                    await repair(row,address,rpc,net)
    finally:await net.close()


if __name__=='__main__':asyncio.run(main())
