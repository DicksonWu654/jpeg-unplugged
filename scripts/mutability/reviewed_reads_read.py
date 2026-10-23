"""Bounded, read-only reviewed calls. Save request, verbatim response, provenance and hash in owned evidence dir."""
import hashlib
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/mutability'))
from keccak import selector
from eth_abi import encode,decode
OUT=ROOT/'data/mutability/reviewed_reads'
OUT.mkdir(exist_ok=True)
URL='https://ethereum-rpc.publicnode.com'


def save(key,url,method,request=None):
    p=OUT/f'{key}.json'
    if p.exists():
        record=json.loads(p.read_text())
        if 'response' not in record:
            try: record['response']=json.loads(record['response_text'])
            except ValueError: record['response']=None
        return record
    data=json.dumps(request).encode() if request is not None else None
    req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json','User-Agent':'nft-unplugged-research/reviewed_reads'})
    try:
        with urllib.request.urlopen(req,timeout=60) as r: raw=r.read();status=r.status
    except urllib.error.HTTPError as e:raw=e.read();status=e.code
    except Exception as e:raw=str(e).encode();status=None
    try:body=json.loads(raw)
    except ValueError:body=None
    result={'url':url,'method':method,'request':request,'status':status,'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'sha256':hashlib.sha256(raw).hexdigest(),'response_text':raw.decode(errors='replace')}
    p.write_text(json.dumps(result,indent=1)+'\n')
    time.sleep(.4)
    result['response']=body
    return result


def rpc(key,method,params):
    return save(key,URL,'POST',{'jsonrpc':'2.0','id':1,'method':method,'params':params})['response']


def block():
    return rpc('block','eth_blockNumber',[])['result']


def call(a,sig,args=(),types=(),key=None,block_tag=None,gas=150_000_000):
    dat=selector(sig)+(encode(types,args).hex() if types else '')
    return rpc(key or (a+'_'+sig.split('(')[0]+'_'+hashlib.sha256(dat.encode()).hexdigest()[:12]),'eth_call',[{'to':a,'data':dat,'gas':hex(gas)},block_tag or block()])


if __name__=='__main__':
    a='0x9a7b94954751d539c63e16aa6e0557c451251394'
    print('block',block())
    r=save(a+'_source','https://eth.blockscout.com/api/v2/smart-contracts/'+a,'GET');j=r['response'] or {};print('source',r['status'],j.get('name'),len(j.get('source_code','')))
    print('source files',[x.get('file_path') for x in j.get('additional_sources',[])])
    print('functions',[(x['name'],x.get('inputs'),x.get('outputs')) for x in (j.get('abi') or []) if x.get('type')=='function'])
