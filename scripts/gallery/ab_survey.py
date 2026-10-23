"""Survey Art Blocks project script types (core V1 ids 3-373, core V3 ids 374-493) -> data/gallery/artblocks-survey/survey.json"""
import chain, json, time, sys
from concurrent.futures import ThreadPoolExecutor
V1='0xa7d8d9ef8D8Ce8992Df33D8b8CF4Aebabd5bD270'; V3='0x99a9B7c1116f9ceEB1652de04d5969CcE509B069'
out={}
def one(pid):
    time.sleep(0.2)
    try:
        if pid<374:
            r=chain.call(V1,'projectScriptInfo(uint256)',[pid],['string','uint256','bool','string','bool','bool'],'artblocks-survey',f'v1_script_{pid}')
            if not r: return pid,None
            j=json.loads(r[0]) if r[0] else {}
            t=j.get('type'); v=j.get('version'); n=r[1]
            inv=chain.call(V1,'projectTokenInfo(uint256)',[pid],['address','uint256','uint256','uint256','bool','address','uint256','string','address'],'artblocks-survey',f'v1_tok_{pid}')
            return pid,dict(core=V1,type=t,version=v,scripts=n,invocations=inv[1] if inv else None)
        else:
            r=chain.call(V3,'projectScriptDetails(uint256)',[pid],['string','string','uint256'],'artblocks-survey',f'v3_script_{pid}')
            if not r: return pid,None
            return pid,dict(core=V3,type=r[0],version=None,scripts=r[2],invocations=None)
    except Exception as e:
        return pid,dict(error=str(e))
ids=list(range(3,494))
with ThreadPoolExecutor(3) as ex:
    for pid,d in ex.map(one,ids):
        out[pid]=d
json.dump(out,open(chain.GAL/'artblocks-survey'/'survey.json','w'),indent=1)
from collections import Counter
print(Counter((d or {}).get('type') for d in out.values()))
