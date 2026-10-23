"""Finish legacy adapters and sample a third fungible unit in the 2-ID ERC-1155."""
import asyncio
import json
from common import ROOT, OUT
from repair import repair, LEGACY
from refresh import c, selector

EIGHTS='0x36d30b3b85255473d27dd0f7fd8f35e36a9d6f06'


async def main():
    selected=json.loads((OUT/'ranking.json').read_text())
    state=json.loads((OUT/'gateways.json').read_text());c.GW_STATE.update({k:state[k] for k in ('status','ipfs_ok','ar_ok')})
    net=c.Net();await net.start();rpc=c.Rpc(net)
    for endpoint in c.RPC_ENDPOINTS+c.RPC_FALLBACK:net.throttle.configure(endpoint,interval=.4,conc=3)
    try:
        for row in selected:
            for address in row['contracts']:
                if address in LEGACY:
                    await repair(row,address,rpc,net)
                if address==EIGHTS:
                    res=c.load_result(c.RAW/address);ev=c.Evidence(c.RAW,address)
                    if len(res['tokens'])<3:
                        count=await rpc.eth_call(ev,'edition_supply',address,selector('totalSupply(uint256)').removeprefix('0x')+c.u256(888))
                        assert count['ok'] and int(count['result'],16)>=2
                        sample=await c.process_token(rpc,net,ev,address,res['standard'],
                            {'token_id':888,'how':'second fungible unit of ID 888; totalSupply(888)>=2 confirmed'},None)
                        sample['sample_unit']=2
                        for t in res['tokens']:t['sample_unit']=1
                        c.derive_token(sample);res['tokens'].append(sample)
                        res.update(n_sampled=3,sampling_note='Only two indexed ERC-1155 token IDs (1,888); three units sampled, including a second fungible unit of 888. This is two distinct metadata paths, not three independent IDs.')
                        ev.flush();c.save_result(c.RAW/address,res)
                        print('888 Inner Circle: three units, two IDs; supply',int(count['result'],16),flush=True)
    finally:await net.close()


if __name__=='__main__':asyncio.run(main())
