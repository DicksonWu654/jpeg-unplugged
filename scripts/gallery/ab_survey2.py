"""For each Art Blocks project (V1 ids 3-373 token #0 [and #1 fallback], V3 ids 374-493, V0 ids 0-2), call the on-chain
Generator getTokenHtml and record: size, sha256, script type, external URL references. Raw HTML NOT stored (size), only digests.
Output: data/gallery/artblocks-survey/generator_survey.json"""
import chain, json, re, time, hashlib, sys
from concurrent.futures import ThreadPoolExecutor
from eth_abi import decode
G='0x953D288708bB771F969FCfD9BA0819eF506Ac718'
V0='0x059EDD72Cd353dF5106D2B9cC5ab83a52287aC3a'; V1='0xa7d8d9ef8D8Ce8992Df33D8b8CF4Aebabd5bD270'; V3='0x99a9B7c1116f9ceEB1652de04d5969CcE509B069'
surv=json.load(open(chain.GAL/'artblocks-survey/survey.json'))
URL=re.compile(r'''(?:https?:)?//[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+''')
def core_for(pid): return V0 if pid<3 else (V1 if pid<374 else V3)
def one(pid):
    time.sleep(0.25)
    core=core_for(pid)
    res=dict(project=pid,core=core,type=(surv.get(str(pid)) or {}).get('type'))
    for tok in (0,1,2):
        tid=pid*1000000+tok
        try:
            cd=chain.calldata('getTokenHtml(address,uint256)',core,tid)
            url,j=chain.rpc_raw('eth_call',[{'to':G,'data':cd},'latest'])
        except Exception as e:
            res['error']=str(e)[:200]; continue
        if j.get('result'):
            s=decode(['string'],bytes.fromhex(j['result'][2:]))[0]
            # strip base64 payloads for URL scan
            stripped=re.sub(r'base64,[A-Za-z0-9+/=]{64,}','base64,#',s)
            urls=sorted(set(u.rstrip('.,;)\'"`') for u in URL.findall(stripped)))
            res.update(token=tid,ok=True,html_bytes=len(s.encode()),sha256=hashlib.sha256(s.encode()).hexdigest(),ext_urls=urls,
                       has_gzip=('javascript+gzip' in s), rpc=url, retrieved_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
            res.pop('error',None); return res
        else:
            res['error']=json.dumps(j.get('error'))[:200]
    res['ok']=False
    return res
if __name__=='__main__':
    ids=list(range(0,494))
    out=[]
    with ThreadPoolExecutor(3) as ex:
        for r in ex.map(one,ids):
            out.append(r)
    json.dump(out,open(chain.GAL/'artblocks-survey/generator_survey.json','w'),indent=1)
    print(sum(1 for r in out if r.get('ok')),'ok of',len(out))
