"""Refresh three token samples using census, in an isolated evidence namespace.

Usage: .venv/bin/python scripts/top100/refresh.py [--retry]
Never modifies the main census or its saved evidence.
"""
import argparse
import asyncio
import json
import sys
import traceback
from common import ROOT, OUT

sys.path.insert(0, str(ROOT / 'scripts/census'))
import census as c
sys.path.insert(0, str(ROOT / 'scripts/mutability'))
from keccak import selector

OLD_RAW = c.RAW
c.load_gateways()
c.RAW = ROOT / 'data/raw/top100-census'
PUNKS = '0xb47e3cd837ddf8e4c57f05d70ab865de6e193bbb'
PUNK_DATA = '0x16f5a35647d6f03d5d3da7b35409d65ba03af3b2'


async def gateways(net):
    ev = c.Evidence(c.RAW, '_gateways')
    state = {}
    async def one(host, kind):
        url = f'https://{host}/ipfs/{c.BAYC_META}' if kind == 'ipfs' else f'https://{host}/info'
        r = await net.fetch(url, max_bytes=20_000, timeout=20)
        text = r['body'].decode(errors='replace')
        ok = r['status'] == 200 and ('"image"' in text if kind == 'ipfs' else '"network"' in text)
        wall = r['status'] in (403, 429) or c.looks_bot_wall(text)
        state[host] = {'state': 'ok' if ok else 'bot-walled' if wall else 'untested',
                       'status': r['status'], 'error_kind': r['error_kind']}
        ev.record(kind='canary', role=kind, url=url, method='GET', status=r['status'], body=r['body'],
                  error=r['error'], error_kind=r['error_kind'], extra=state[host])
    await asyncio.gather(*(one(g, 'ipfs') for g in c.IPFS_CANDIDATES),
                         *(one(g, 'ar') for g in c.AR_CANDIDATES))
    ev.flush()
    good = [g for g in c.GW_STATE['ipfs_ok'] if state.get(g, {}).get('state') == 'ok']
    good += [g for g in c.IPFS_CANDIDATES if state[g]['state'] == 'ok' and g not in good and g not in c.GW_EXCLUDE]
    c.GW_STATE.update(status=state, ipfs_ok=good, ar_ok=[g for g in c.AR_CANDIDATES if state[g]['state']=='ok'])
    c.jdump(OUT / 'gateways.json', {'tested_at': c.now_iso(), **c.GW_STATE})
    print('working gateways', good, c.GW_STATE['ar_ok'], flush=True)


async def punk(rpc, net, ev, tid):
    sig = selector('punkImageSvg(uint16)').removeprefix('0x')
    result = await rpc.eth_call(ev, 'punkImageSvg', PUNK_DATA, sig+c.u256(tid), token_id=str(tid))
    svg, note = c.decode_abi_string(result['result']) if result['ok'] else (None, result.get('error'))
    t = {'token_id': str(tid), 'how_found': 'fixed low/mid/high in legacy supply 10000', 'rpc': result,
         'uri_raw': f'ethereum:{PUNK_DATA}/punkImageSvg({tid})', 'uri': None,
         'meta_class': 'onchain-renderer' if svg else 'broken', 'meta_reason': 'legacy-no-tokenURI',
         'rpc_infra_failure': not result['ok'] and not result.get('revert'), 'special_case': 'cryptopunks-data-contract'}
    if svg:
        assert '<svg' in svg
        media, target = c.media_entry('image_data', 'punkImageSvg(uint16)', svg, str(tid))
        t.update(meta_fields=[], media=[media])
        t['art_sha256'] = media.get('payload_sha256')
    # Check the marketplace presentation separately; it is not the immutable art store.
    url = f'https://cryptopunks.app/cryptopunks/cryptopunk{tid:04d}.png'
    target = c.new_target('marketplace_image', url, c.classify_uri(url))
    await c.check_target(net, ev, target, str(tid), 1, 'media')
    t['marketplace_target'] = target
    c.derive_token(t)
    return t


async def collection(row, rpc, net, sem, retry):
    address = row['contract']
    async with sem:
        if c.has_result(c.RAW / address) and not retry:
            return
        ev = c.Evidence(c.RAW, address)
        try:
            if retry:
                res = c.load_result(c.RAW / address)
                for t in res.get('tokens', []):
                    await c.retry_token(net, ev, t, pass_no=2)
                    if t.get('marketplace_target', {}).get('verdict') != 'alive' and t.get('marketplace_target'):
                        await c.check_target(net, ev, t['marketplace_target'], t['token_id'], 2, 'media')
                    c.derive_token(t)
                res.update(pass_no=2, retried_at=c.now_iso())
                res['pass'] = 2
            else:
                old = c.load_result(OLD_RAW/address) if c.has_result(OLD_RAW/address) else {}
                standard = old.get('standard') or 'ERC-721'
                res = {'address': address, 'name': row['name'], 'standard': standard, 'started_at': c.now_iso(),
                       'pass': 1, 'reused_census_evidence': str((OLD_RAW/address).relative_to(ROOT)) if old else None}
                if address == PUNKS:
                    tokens = await asyncio.gather(*(punk(rpc, net, ev, i) for i in (0,5000,9999)))
                else:
                    samples = [{'token_id': int(t['token_id']), 'how': 'reused census: '+t.get('how_found','')}
                               for t in old.get('tokens', [])]
                    if len({s['token_id'] for s in samples}) < 3:
                        samples, notes = await c.sample_tokens(rpc, ev, address, standard, want=3)
                        res['sampling'] = notes
                    # census may yield fewer than three on nonstandard contracts: preserve that gap.
                    samples = list({s['token_id']: s for s in samples}.values())[:3]
                    tokens = await asyncio.gather(*(c.process_token(rpc, net, ev, address, standard, s, old.get('renderer')) for s in samples))
                res['tokens'] = list(tokens)
                res['n_sampled'] = len(tokens)
                for t in tokens:
                    c.derive_token(t)
            res['finished_at'] = c.now_iso()
            c.save_result(c.RAW/address, res)
            r = c.collection_row(res)
            print(row['rank'], row['name'], r['n_sampled'], r['meta_class'], r['media_class'], r['liveness'], flush=True)
        except Exception:
            print('ERROR',row['name'],traceback.format_exc(),flush=True)
        finally:
            ev.flush()


async def main(retry, only=None):
    selected = json.loads((OUT/'ranking.json').read_text())
    rows = [{**r, 'contract': address} for r in selected for address in r.get('contracts',[r['contract']])]
    if only:
        rows=[r for r in rows if r['contract'] in set(only.lower().split(','))]
    net = c.Net()
    await net.start()
    rpc = c.Rpc(net)
    for endpoint in c.RPC_ENDPOINTS+c.RPC_FALLBACK:
        net.throttle.configure(endpoint, interval=.4, conc=4)
    net.throttle.configure('blockscout', interval=.5, conc=3)
    try:
        if not retry:
            await gateways(net)
        else:
            state=json.loads((OUT/'gateways.json').read_text())
            c.GW_STATE.update({k: state[k] for k in ('status','ipfs_ok','ar_ok')})
        await asyncio.gather(*(collection(row,rpc,net,async_sem,retry) for row in rows))
    finally:
        await net.close()


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--retry',action='store_true')
    ap.add_argument('--only',help='comma-separated contract addresses for targeted repair retries')
    args=ap.parse_args()
    # Constructed before the loop but first bound on acquire (Python 3.12).
    async_sem=asyncio.Semaphore(12)
    asyncio.run(main(args.retry,args.only))
