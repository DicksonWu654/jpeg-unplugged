"""Verify every address in web_famous_spec.PROJECTS against Blockscout (token or address endpoint) and probe tokenURI via eth_call.
Raw responses saved under data/raw/claims-addr/ (blockscout) and data/raw/rpc-claims/ (eth_call). Writes scripts/claims/addr_checks.json."""
import sys, json, time, base64, re
sys.path.insert(0, 'scripts/lib'); sys.path.insert(0, 'scripts/claims')
from rawfetch import get_soft, rpc
from web_famous_spec import PROJECTS

def abi_string(hexs):
    b = bytes.fromhex(hexs[2:])
    if len(b) < 64: return None
    off = int.from_bytes(b[:32], 'big'); ln = int.from_bytes(b[off:off+32], 'big')
    return b[off+32: off+32+ln].decode('utf8', 'replace')

def scheme(u):
    if u is None: return None
    m = re.match(r'^(data:[^,;]*(;base64)?|ipfs://|ar://|https?://[^/]+|http://[^/]+)', u)
    return m.group(1) if m else u[:30]

def r2_cached_bad(a):
    import pathlib
    p = pathlib.Path(f'data/raw/claims-addr/addr_{a}.json')
    return p.exists() and not p.read_text().startswith('{')

import os
ONLY = set(sys.argv[1:])
out = json.load(open('scripts/claims/addr_checks.json')) if ONLY and os.path.exists('scripts/claims/addr_checks.json') else {}
for k, (name, addr, expect, ids) in PROJECTS.items():
    if ONLY and k not in ONLY: continue
    a = addr.lower()
    r = get_soft(f'https://eth.blockscout.com/api/v2/tokens/{a}', source='claims-addr', key=f'tok_{a}', ext='json', timeout=30, retries=3)
    j = r['json'] or {}
    bname = j.get('name'); btype = j.get('type')
    if r['status'] != 200:
        time.sleep(0.4)
        for attempt in range(4):
            r2 = get_soft(f'https://eth.blockscout.com/api/v2/addresses/{a}', source='claims-addr', key=f'addr_{a}', ext='json', timeout=30, retries=3, refresh=attempt > 0 or (r2_cached_bad(a)))
            if r2['status'] == 200 and isinstance(r2['json'], dict): break
            time.sleep(2)
        j2 = r2['json'] if isinstance(r2['json'], dict) else {}
        bname = j2.get('name'); btype = 'contract' if j2.get('is_contract') else None
        status = r2['status']
    else:
        status = r['status']
    ok = bool(bname) and (expect is None or expect in (bname or '').lower().replace('​', ''))
    ent = {'collection': name, 'address': addr, 'blockscout_status': status, 'blockscout_name': bname, 'blockscout_type': btype, 'name_matches': ok, 'token_uri': None}
    time.sleep(0.4)
    for tid in ids:
        data = '0xc87b56dd' + hex(tid)[2:].zfill(64)
        try:
            res = rpc('eth_call', [{'to': addr, 'data': data}, 'latest'], key=f'tokenuri_{a}_{tid}', source='rpc-claims', timeout=40, retries=1)
        except Exception as e:  # noqa
            ent['token_uri'] = {'id': tid, 'error': str(e)[:120]}
            time.sleep(0.4); continue
        uri = abi_string(res) if isinstance(res, str) and len(res) > 2 else None
        info = {'id': tid, 'uri_scheme': scheme(uri), 'uri_head': (uri or '')[:90], 'uri_len': len(uri or '')}
        if uri and uri.startswith('data:application/json'):
            try:
                body = uri.split(',', 1)[1]
                js = base64.b64decode(body + '==').decode('utf8', 'replace') if ';base64' in uri.split(',', 1)[0] else body
                m = json.loads(js)
                info['image_scheme'] = scheme(m.get('image') or m.get('image_data') and 'image_data')
                info['animation_scheme'] = scheme(m.get('animation_url'))
            except Exception as e:  # noqa
                info['json_error'] = str(e)[:80]
        ent['token_uri'] = info
        time.sleep(0.4)
        break
    out[k] = ent
    print(k, ok, bname, btype, ent['token_uri'], flush=True)
json.dump(out, open('scripts/claims/addr_checks.json', 'w'), indent=1)
