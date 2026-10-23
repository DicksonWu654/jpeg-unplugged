"""Static flags from verified source (Etherscan getsourcecode, cached by rawfetch): storage technique hints. Used to label 'chain storage method'."""
import sys, json, re, time
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'lib'))
import rawfetch

def _src(addr):
    for i in range(6):
        r = rawfetch.etherscan({'module': 'contract', 'action': 'getsourcecode', 'address': addr}, f'src_{addr}', refresh=(i > 0))
        if isinstance(r.get('result'), list): return r['result'][0]
        time.sleep(1.5 * (i + 1))
    return None

def _text(res):
    s = res.get('SourceCode') or ''
    if s.startswith('{{'):
        try:
            j = json.loads(s[1:-1]); return "\n".join(v.get('content', '') for v in j.get('sources', {}).values())
        except Exception: return s
    if s.startswith('{'):
        try:
            j = json.loads(s); return "\n".join(v.get('content', '') for v in j.values())
        except Exception: return s
    return s

def flags(addr, depth=0):
    res = _src(addr)
    if not res or not res.get('SourceCode'):
        return dict(verified=False)
    t = _text(res)
    f = dict(verified=True, contract_name=res.get('ContractName'), proxy=res.get('Proxy') == '1', implementation=res.get('Implementation') or None,
             sstore2=bool(re.search(r'SSTORE2|sstore2|\bwrite\(bytes memory|CREATE\b.*0x600b', t)), ethfs=bool(re.search(r'ethfs|EthFS|IFileStore|FileStore', t)),
             scripty=bool(re.search(r'scripty|Scripty|IScriptyBuilder', t)), base64=('Base64' in t or 'base64' in t),
             gzip=bool(re.search(r'gunzip|gzip', t)), data_uri=('data:application/json' in t or 'data:image/svg' in t or 'data:text/html' in t),
             http_literals=sorted(u for u in set(re.findall(r'https?://[A-Za-z0-9._/-]+', t)) if not re.search(r'eips\.ethereum|openzeppelin|soliditylang|consensys|stackexchange|w3\.org|github\.com|ethereum\.org|medium\.com|solidity\.readthedocs|zeppelin', u))[:8], ipfs_literal=('ipfs://' in t),
             setters=[s for s in ('setBaseURI', 'setBaseUri', 'setRenderer', 'setDescriptor', 'setTokenURI', 'setArt', 'upgradeTo') if s in t])
    if f['proxy'] and f['implementation'] and depth == 0:
        f['implementation_flags'] = flags(f['implementation'], 1)
    return f

if __name__ == '__main__':
    for a in sys.argv[1:]: print(a, json.dumps(flags(a))[:600])
