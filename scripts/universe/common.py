"""Shared helpers for the universe universe scripts: rate limiter + resilient cached GET on top of rawfetch."""
import json, pathlib, random, sys, threading, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import rawfetch as rf  # noqa: E402

UNI = ROOT / "data" / "universe"
UNI.mkdir(parents=True, exist_ok=True)


class Limiter:
    """Global min-interval limiter shared by threads."""

    def __init__(self, rps):
        self.dt = 1.0 / rps
        self.lock = threading.Lock()
        self.next = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.dt
        if t > now:
            time.sleep(t - now)


def cached_json(source, key):
    rel = rf.raw_path(source, key)
    if not rel:
        return None
    try:
        return json.loads((ROOT / rel).read_bytes())
    except ValueError:
        return None


def fetch_json(url, source, key, limiter, valid, max_attempts=10, log=print):
    """Return (json, from_cache). Cached file is reused only if valid(json). 429/5xx/invalid => exponential backoff.
    Every attempt (including 429 bodies) is saved by rawfetch.get_soft and logged in the MANIFEST."""
    j = cached_json(source, key)
    if j is not None and valid(j):
        return j, True
    for a in range(max_attempts):
        limiter.wait()
        r = rf.get_soft(url, source, key, refresh=True, timeout=120, retries=1)
        if r["status"] == 200 and r["json"] is not None and valid(r["json"]):
            return r["json"], False
        wait = min(120, 3 * 2 ** a)
        if "rate limit" in str(r["json"]).lower() and "Max calls per sec" in str(r["json"]):
            wait = 0.5 + random.random() * 2  # Etherscan per-second cap shared with other workstreams: retry soon
            log = (lambda *_a, **_k: None)
        log(f"  [{source}/{key}] attempt {a+1} status={r['status']} err={r['error']} -> sleep {wait}s")
        time.sleep(wait)
    raise RuntimeError(f"giving up on {source}/{key}")


def etherscan_key():
    import os
    k = os.environ.get("ETHERSCAN_API_KEY")
    if not k:
        for line in (pathlib.Path("etherscan.env")).read_text().splitlines():
            if line.startswith("ETHERSCAN_API_KEY="):
                k = line.split("=", 1)[1].strip().strip('"')
    return k


def load_token_rows(min_holders=100):
    """Rows (verbatim Blockscout items + 'type') from all raw token pages on disk (all segments), deduped by address."""
    import glob, re
    seen, out = set(), []
    for tag, typ in (("erc721", "ERC-721"), ("erc1155", "ERC-1155")):
        files = glob.glob(str(ROOT / "data/raw/blockscout-tokens" / f"{tag}_*.json"))
        for p in sorted(files):
            try:
                j = json.load(open(p))
            except ValueError:
                continue
            if not isinstance(j, dict):
                continue
            for it in j.get("items", []):
                a = it["address_hash"].lower()
                if int(it["holders_count"]) >= min_holders and a not in seen:
                    seen.add(a)
                    out.append({**it, "type": typ})
    return out
