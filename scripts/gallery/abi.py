"""Print function signatures from Etherscan verified ABI. Usage: abi.py <addr> [filter]"""
import sys, json, time
sys.path.insert(0, '../lib')
import rawfetch
def sig(i): 
    def t(x):
        if x['type'].startswith('tuple'): return '('+','.join(t(c) for c in x['components'])+')'+x['type'][5:]
        return x['type']
    return f"{i['name']}({','.join(t(x) for x in i['inputs'])})->({','.join(t(x) for x in i.get('outputs',[]))}) {i.get('stateMutability','')}"
def abi(addr):
    for i in range(5):
        r=rawfetch.etherscan({'module':'contract','action':'getsourcecode','address':addr},f'src_{addr}',refresh=(i>0))
        if isinstance(r['result'],list): break
        time.sleep(2*(i+1))
    res=r['result'][0]
    return res, (json.loads(res['ABI']) if res['ABI'].startswith('[') else [])
if __name__=='__main__':
    res,a=abi(sys.argv[1])
    print(res['ContractName'], res.get('Proxy'), res.get('Implementation'), res['CompilerVersion'])
    for i in a:
        if i['type']=='function' and (len(sys.argv)<3 or sys.argv[2].lower() in i['name'].lower()): print(sig(i))
