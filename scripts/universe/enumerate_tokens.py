"""Step 1: enumerate Blockscout /api/v2/tokens (ERC-721 and ERC-1155) sorted by holders_count desc, down to
holders_count < MIN_HOLDERS.

Blockscout's keyset-paged token list takes 15-40 s per page, so a single cursor chain would need hours. The cursor
is a plain keyset (holders_count, name, contract_address_hash), so we run several *segments* in parallel: segment 0
is the real chain from the top; every other segment starts at a synthetic cursor (holders_count=H, name=U+10FFFF,
address=0xff..ff, which sorts before every real tie at H) and walks downward until it passes the next-lower
segment's start H'. Segments overlap on the tie group at H' by construction, rows are deduped by address, and
integrity checks (monotone, seam coverage) are run at the end.

Resumable: each page is saved raw (source blockscout-tokens, key <type>_p#### for segment 0, else
<type>_s<H>_p####) and re-read from disk on rerun.
Output: data/universe/tokens_raw_rows.jsonl (verbatim Blockscout items >= MIN_HOLDERS, plus 'type')."""
import json, sys, threading, time, urllib.parse
from common import UNI, Limiter, fetch_json, cached_json

MIN_HOLDERS = 100
SRC = "blockscout-tokens"
BASE = "https://eth.blockscout.com/api/v2/tokens"
STARTS = [None, 3000, 2400, 2000, 1700, 1450, 1200, 1000, 850, 720, 600, 500, 420, 350, 300, 260, 240, 220, 200, 171, 150, 133, 120, 109]  # None = the real top chain
lim = Limiter(2.5)
log_lock = threading.Lock()
results = {}


def log(*a):
    with log_lock:
        print(time.strftime("%H:%M:%S"), *a, flush=True)


def qs(d):
    return urllib.parse.urlencode({k: (str(v).lower() if isinstance(v, bool) else ("null" if v is None else v))
                                   for k, v in d.items()})


def run(typ, si):
    tag = typ.replace("-", "").lower()
    start = STARTS[si]
    lower = STARTS[si + 1] if si + 1 < len(STARTS) else MIN_HOLDERS
    prefix = f"{tag}_p" if start is None else f"{tag}_s{start}_p"
    params = {"type": typ, "sort": "holders_count", "order": "desc"}
    if start is not None:
        params.update(holders_count=start, items_count=50, is_name_null=False, name="\U0010ffff",
                      contract_address_hash="0x" + "f" * 40, fiat_value=None, market_cap=None)
    page, items_all, prev_min = 0, [], None
    while True:
        page += 1
        j, cached = fetch_json(f"{BASE}?{qs(params)}", SRC, f"{prefix}{page:04d}", lim, lambda j: "items" in j,
                               log=log)
        items = j["items"]
        hs = [int(i["holders_count"]) for i in items]
        if hs:
            assert prev_min is None or hs[0] <= prev_min, f"non-monotone {typ} seg {start} page {page}"
            assert all(a >= b for a, b in zip(hs, hs[1:]))
            prev_min = hs[-1]
        items_all += items
        if page % 5 == 0:
            log(f"{typ} seg{start} page {page} min={prev_min} cached={cached}")
        nxt = j.get("next_page_params")
        if not items or not nxt or hs[-1] < lower:
            break
        params = {"type": typ, "sort": "holders_count", "order": "desc", **nxt}
    results[(typ, si)] = dict(start=start, lower=lower, pages=page, first=items_all[0]["holders_count"] if items_all else None,
                              min=prev_min, items=items_all)
    log(f"{typ} seg{start} done pages={page} items={len(items_all)} min={prev_min}")


if __name__ == "__main__":
    ths = [threading.Thread(target=run, args=(t, si)) for t in ("ERC-721", "ERC-1155") for si in range(len(STARTS))]
    for t in ths:
        t.start()
        time.sleep(0.5)
    [t.join() for t in ths]
    seen, out, rep = set(), [], []
    for t in ("ERC-721", "ERC-1155"):
        for si in range(len(STARTS)):
            r = results[(t, si)]
            if si > 0:  # seam checks: segment must start at/below its cursor and reach strictly below `lower`
                assert int(r["first"]) <= r["start"], (t, r["start"], r["first"])
            assert int(r["min"]) < r["lower"], (t, si, r["min"], r["lower"])
            rep.append((t, r["start"], r["pages"], len(r["items"]), r["first"], r["min"]))
            for it in r["items"]:
                a = it["address_hash"].lower()
                if int(it["holders_count"]) >= MIN_HOLDERS and a not in seen:
                    seen.add(a)
                    out.append({**it, "type": t})
    with open(UNI / "tokens_raw_rows.jsonl", "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
    json.dump(rep, open(UNI / "enumerate_segments.json", "w"))
    log("wrote tokens_raw_rows.jsonl", len(out), rep)
