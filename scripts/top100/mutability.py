"""Reuse mutability audits; run the identical analyzer for uncovered contracts.

All new analysis/evidence stays under data/raw; build.py exports redacted fields.
"""
import concurrent.futures
import json
import re
import sys
import time
import urllib.error
import urllib.request
from common import ROOT, OUT

sys.path.insert(0, str(ROOT/'scripts/mutability'))
import collect
import mlib

EVID = ROOT/'data/raw/top100-mutability'
EVID.mkdir(parents=True, exist_ok=True)
collect.EVID = EVID
mlib.TH['rpc'] = mlib.Throttle(2.5)


def recorded_http(url, body=None, host='blockscout', timeout=40, retries=3):
    """Preserve error responses too, without disclosing API credentials."""
    if mlib.BLOCKED.get(host,0)>time.time():
        raise mlib.RateLimited('API circuit breaker active')
    safe_url = re.sub(r'(apikey=)[^&]+',r'\1REDACTED',url)
    for i in range(retries):
        mlib.TH[host].wait()
        status, payload, error = None, b'', None
        try:
            req=urllib.request.Request(url,data=body,headers=mlib.UA)
            try:
                with urllib.request.urlopen(req,timeout=min(timeout,40)) as r:
                    status,payload=r.status,r.read(2_000_001)
            except urllib.error.HTTPError as exc:
                status,payload=exc.code,exc.read(2_000_001)
        except Exception as exc:
            error=repr(exc)[:200]
        mlib.rf._save('top100-mutability-http',str(time.time_ns()),'body',payload,
                      {'url':safe_url,'method':'POST' if body else 'GET','status':status,'error':error})
        if status in (200,404):
            return status,payload
        if status==429:
            mlib.BLOCKED[host]=time.time()+30
            raise mlib.RateLimited('API rate limited; retained unknown')
        time.sleep(2*(i+1))
    raise RuntimeError(error or f'HTTP {status}')


def one(row):
    address=row['contract']
    old=ROOT/f'data/mutability/evidence/{address}.json'
    if old.exists():
        return address,'reused'
    result=collect.run_one({'address':address,'name':row['name']})
    return address,result


if __name__=='__main__':
    mlib._http=recorded_http
    selected=json.loads((OUT/'ranking.json').read_text())
    rows=[{**r,'contract':address} for r in selected for address in r.get('contracts',[r['contract']])]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(one,r):r for r in rows}
        for future in concurrent.futures.as_completed(futures):
            row=futures[future]
            try:
                address,status=future.result()
                print(row['rank'],row['name'],status,flush=True)
            except Exception as exc:
                print(row['rank'],row['name'],'error',repr(exc),flush=True)
