"""Verify addresses against Blockscout (saved raw in data/raw/claims-addr/). usage: verify_addrs.py addr [addr...] or -s query"""
import sys, time
sys.path.insert(0, 'scripts/lib')
from rawfetch import get_soft
def verify(a):
    r = get_soft(f'https://eth.blockscout.com/api/v2/tokens/{a}', source='claims-addr', key=f'tok_{a.lower()}', ext='json', timeout=30, retries=3)
    j = r['json'] or {}
    return r['status'], j.get('name'), j.get('symbol'), j.get('type'), j.get('holders_count') or j.get('holders'), j.get('total_supply'), j.get('address_hash') or j.get('address')
def search(q):
    r = get_soft('https://eth.blockscout.com/api/v2/search?q=' + q.replace(' ', '+'), source='claims-addr', key='search_' + q.lower().replace(' ', '_'), ext='json', timeout=30, retries=3)
    for it in ((r['json'] or {}).get('items') or [])[:6]:
        print('   ', it.get('type'), it.get('name'), it.get('symbol'), it.get('address_hash') or it.get('address'), it.get('holder_count') or it.get('holders_count'), it.get('is_smart_contract_verified'))
if __name__ == '__main__':
    if sys.argv[1] == '-s':
        for q in sys.argv[2:]:
            print('?', q); search(q); time.sleep(0.4)
    else:
        for a in sys.argv[1:]:
            print(a, verify(a)); time.sleep(0.4)
