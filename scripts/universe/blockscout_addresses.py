"""Step 3 (enrichment, optional): Blockscout /api/v2/addresses/{addr} per universe contract -> is_scam, reputation,
proxy_type, implementations, is_verified, creation tx, creator. Raw: data/raw/blockscout-addresses/<addr>.json.
Order: highest holders first. Resumable; ~2.5 req/s total. Output data/universe/addresses.jsonl (rebuilt from raw)."""
import json, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from common import UNI, ROOT, Limiter, fetch_json, load_token_rows

import re
from creation_order import URLISH
lim = Limiter(1.8)


def one(r):
    a = r["address_hash"]
    try:
        j, _ = fetch_json(f"https://eth.blockscout.com/api/v2/addresses/{a}", "blockscout-addresses", a.lower(), lim,
                          lambda j: "hash" in j, max_attempts=6)
    except RuntimeError:
        return None
    return j


def build():
    import glob
    n = 0
    with open(UNI / "addresses.jsonl", "w") as f:
        for p in glob.glob(str(ROOT / "data/raw/blockscout-addresses/*.json")):
            try:
                j = json.load(open(p))
            except ValueError:
                continue
            if "hash" not in j:
                continue
            f.write(json.dumps({k: j.get(k) for k in (
                "hash", "is_contract", "is_scam", "is_verified", "reputation", "proxy_type", "implementations",
                "creation_transaction_hash", "creator_address_hash", "creation_status", "name", "ens_domain_name")}) + "\n")
            n += 1
    return n


if __name__ == "__main__":
    if "--build" not in sys.argv:
        rows = sorted(load_token_rows(), key=lambda r: (bool(URLISH.search((r["name"] or "") + " " + (r["symbol"] or ""))), -int(r["holders_count"])))
        t0 = time.time()
        with ThreadPoolExecutor(6) as ex:
            for k, _ in enumerate(ex.map(one, rows)):
                if k % 200 == 0:
                    print(time.strftime("%H:%M:%S"), f"{k}/{len(rows)}", int(time.time() - t0), "s", flush=True)
    print("rows", build())
