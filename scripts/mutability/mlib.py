"""mutability shared helpers: throttled, raw-saved RPC batches / Etherscan / Blockscout calls; ABI + source loading; decoding.

Every response is written through rawfetch._save (data/raw/<source>/<key>.json + MANIFEST line). Cached files are reused;
rate-limit / transport errors are retried and never cached ("unknown != dead").
"""
import json, os, pathlib, re, sys, threading, time, urllib.request, urllib.error, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "scripts" / "claims"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import rawfetch as rf  # noqa: E402
from keccak import keccak256, selector, topic  # noqa: E402,F401

RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "mutability"
EVID = OUT / "evidence"
RPC_BATCH = "https://eth.rpc.blxrbdn.com"   # accepts batches of 100
RPC_ALT = "https://eth.drpc.org"            # free plan: batches <=3, serves historical eth_call
UA = rf.UA

# ---------------------------------------------------------------- throttles
class Throttle:
    def __init__(self, rate):
        self.iv = 1.0 / rate; self.t = 0.0; self.l = threading.Lock()
    def wait(self):
        with self.l:
            w = self.t + self.iv - time.time()
            if w > 0: time.sleep(w)
            self.t = time.time()

TH = {"rpc": Throttle(4.0), "rpc_alt": Throttle(2.5), "etherscan": Throttle(1.6), "blockscout": Throttle(1.0), "safe": Throttle(2.0), "blockscout_api": Throttle(0.2)}


BLOCKED = {}   # host -> epoch until which we treat the host as rate-limited (circuit breaker)


class RateLimited(RuntimeError):
    pass


def _http(url, body=None, host="blockscout", timeout=60, retries=5):
    """returns (status, bytes) ; retries 429/5xx/transport; raises RateLimited when the server asks us to wait >60s (circuit breaker)."""
    if BLOCKED.get(host, 0) > time.time():
        raise RateLimited(f"{host} blocked for {int(BLOCKED[host]-time.time())}s more")
    last = None
    for i in range(retries):
        TH[host].wait()
        try:
            req = urllib.request.Request(url, data=body, headers=UA if body else {"User-Agent": UA["User-Agent"]})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            b = e.read()
            if e.code == 404: return 404, b
            last = f"http{e.code}"
            if e.code == 429:
                try: reset = float(e.headers.get("x-ratelimit-reset") or 0) / 1000.0
                except Exception: reset = 0
                if reset > 60:
                    BLOCKED[host] = time.time() + min(reset, 3600)
                    raise RateLimited(f"{host} 429, reset in {int(reset)}s")
                time.sleep(max(reset, 3 * (i + 1)))
            else:
                time.sleep(2 * (i + 1))
        except Exception as e:  # noqa: BLE001
            last = repr(e)[:100]; time.sleep(2 * (i + 1))
    raise RuntimeError(last)


def save(source, key, obj, url, method, params=None, status=200):
    b = json.dumps(obj, separators=(",", ":")).encode() if not isinstance(obj, bytes) else obj
    p = rf._save(source, key, "json", b, {"url": url, "method": method, "params": params, "status": status})
    return str(p.relative_to(ROOT))


def cached(source, key):
    p = RAW / rf._safe(source) / f"{rf._safe(key)}.json"
    return p if p.exists() else None

# ---------------------------------------------------------------- RPC
def rpc_batch(calls, key, block="latest", source="rpc-mutability", refresh=False, alt=False):
    """calls: list of (method, params). Returns (list of results-or-error-dicts, raw_path). Result entry:
    {'ok': True, 'result': '0x..'} or {'ok': False, 'error': msg, 'revert': bool}. Saved as one file with request+response."""
    p = cached(source, key)
    if p and not refresh:
        d = json.loads(p.read_bytes()); return d["out"], str(p.relative_to(ROOT))
    out = []
    if alt:  # historical / tx-index lookups: drpc (archive-ish), batches of <=3
        for o3 in range(0, len(calls), 3):
            sub = [{"jsonrpc": "2.0", "id": i, "method": m, "params": pr} for i, (m, pr) in enumerate(calls[o3:o3 + 3])]
            st, b = _http(RPC_ALT, json.dumps(sub if len(sub) > 1 else sub[0]).encode(), host="rpc_alt")
            j = json.loads(b); j = j if isinstance(j, list) else [j]
            for r in sorted(j, key=lambda x: x["id"]):
                if "result" in r: out.append({"ok": True, "result": r["result"]})
                else: out.append({"ok": False, "error": (r.get("error") or {}).get("message", ""), "revert": False})
        path = save(source, key, {"request": [{"method": m, "params": pr} for m, pr in calls], "out": out}, RPC_ALT, "batch-alt", status=200)
        return out, path
    for off in range(0, len(calls), 100):
        chunk = calls[off:off + 100]
        body = [{"jsonrpc": "2.0", "id": i, "method": m, "params": pr} for i, (m, pr) in enumerate(chunk)]
        resp = None
        for attempt in range(4):
            try:
                st, b = _http(RPC_BATCH, json.dumps(body).encode(), host="rpc")
                j = json.loads(b)
                if isinstance(j, list) and len(j) == len(chunk): resp = j; break
            except Exception: pass
            time.sleep(2 * (attempt + 1))
        if resp is None:  # fallback to drpc, 3-call batches
            resp = []
            for o3 in range(0, len(body), 3):
                sub = body[o3:o3 + 3]
                st, b = _http(RPC_ALT, json.dumps(sub if len(sub) > 1 else sub[0]).encode(), host="rpc_alt")
                j = json.loads(b); j = j if isinstance(j, list) else [j]
                resp += sorted(j, key=lambda x: x["id"])
        resp = sorted(resp, key=lambda x: x["id"])
        for r in resp:
            if "result" in r: out.append({"ok": True, "result": r["result"]})
            else:
                msg = (r.get("error") or {}).get("message", "")
                out.append({"ok": False, "error": msg, "revert": ("revert" in msg.lower() or "invalid opcode" in msg.lower() or "out of gas" in msg.lower() or "stack" in msg.lower())})
    path = save(source, key, {"request": [{"method": m, "params": pr} for m, pr in calls], "out": out}, RPC_BATCH, "batch", status=200)
    return out, path


def call_obj(to, data, block="latest"):
    return ("eth_call", [{"to": to, "data": data}, block])

# ---------------------------------------------------------------- etherscan / blockscout
_KEY = [None]
def ekey():
    if not _KEY[0]:
        k = os.environ.get("ETHERSCAN_API_KEY")
        if not k:
            for line in (pathlib.Path("etherscan.env")).read_text().splitlines():
                if line.startswith("ETHERSCAN_API_KEY="): k = line.split("=", 1)[1].strip().strip('"')
        _KEY[0] = k
    return _KEY[0]


def etherscan(params, key, source="etherscan-mutability", refresh=False):
    """Etherscan v2 GET; caches only status 1 (or 'No records found' status 0) answers. Returns parsed json or None."""
    p = cached(source, key)
    if p and not refresh: return json.loads(p.read_bytes())
    q = urllib.parse.urlencode(params)
    url = f"https://api.etherscan.io/v2/api?chainid=1&{q}&apikey={ekey()}"
    for i in range(5):
        st, b = _http(url, host="etherscan")
        try: j = json.loads(b)
        except Exception: time.sleep(2); continue
        res = j.get("result")
        if j.get("status") == "1" or (isinstance(res, list)) or (isinstance(res, str) and "No records found" in (j.get("message") or "") + res):
            save(source, key, b, url.replace(ekey(), "REDACTED"), "GET", status=st); return j
        if isinstance(res, str) and "rate limit" in res.lower(): time.sleep(1.5 * (i + 1)); continue
        time.sleep(1.5 * (i + 1))
    return None


def blockscout(path, key, source="blockscout-mutability", refresh=False):
    p = cached(source, key)
    if p and not refresh: return json.loads(p.read_bytes())
    url = "https://eth.blockscout.com" + path
    st, b = _http(url, host="blockscout")
    if st == 404:
        j = {"_404": True}; save(source, key, j, url, "GET", status=404); return j
    j = json.loads(b); save(source, key, b, url, "GET", status=st); return j

# ---------------------------------------------------------------- decode helpers
def word_addr(h):
    if not h or len(h) < 66: return None
    return "0x" + h[-40:].lower()

def is_zero_addr(a): return a is None or int(a, 16) == 0
DEAD = {"0x000000000000000000000000000000000000dead", "0xdead000000000000000000000000000000000000", "0x0000000000000000000000000000000000000001", "0xffffffffffffffffffffffffffffffffffffffff"}

def word_int(h):
    try: return int(h[2:66], 16)
    except Exception: return None

def sel_of_sig(sig): return selector(sig)

def abi_sig(f):
    return f"{f['name']}({','.join(_t(i) for i in f.get('inputs', []))})"

def _t(i):
    t = i["type"]
    if t.startswith("tuple"):
        inner = "(" + ",".join(_t(c) for c in i["components"]) + ")"
        return inner + t[5:]
    return t

# ---------------------------------------------------------------- source / ABI loading
import srcscan  # claims loader (etherscan/blockscout cache)  # noqa: E402

def abi_of(addr):
    addr = addr.lower()
    p = RAW / "etherscan" / f"src_{addr}.json"
    if p.exists():
        r = json.loads(p.read_bytes())["result"][0]
        a = r.get("ABI") or ""
        try: return json.loads(a)
        except Exception: return None
    q = RAW / "blockscout-src" / f"{addr}.json"
    if q.exists():
        j = json.loads(q.read_bytes()); a = j.get("abi")
        if isinstance(a, str):
            try: a = json.loads(a)
            except Exception: a = None
        return a
    return None

def ensure_src(addr):
    """Make sure claims-style source cache exists (etherscan first, blockscout fallback). Returns True if cached/ok."""
    addr = addr.lower()
    if srcscan.have(addr): return True
    r = srcscan.fetch_one(addr)
    if r in ("ok", "cached"): return True
    r = srcscan.fetch_bs(addr)
    return r in ("ok", "cached")

def source_text(addr):
    rec = srcscan.load(addr)
    if not rec: return None, None
    files = srcscan.files_of(rec)
    fixed = []
    for fn, t in files:
        if "\\n" in t and t.count("\n") < 8:   # double-escaped source (literal backslash-n): unescape
            try: t = t.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
            except Exception: pass
        fixed.append((fn, t))
    return rec, fixed


def getlogs(address, topic0, key, topic1=None, page=1, offset=1000):
    """eth_getLogs over the whole chain history: Etherscan v2 first, Blockscout's etherscan-compatible /api endpoint as fallback
    (its free quota is tiny: ~10 calls then a ~20-40 min lockout, tracked by a separate circuit breaker). Returns list or None."""
    src = "etherscan-mutability"
    for s_ in (src, "blockscout-mutability"):
        p = cached(s_, key) or cached(s_, key + "_es")
        if p:
            j = json.loads(p.read_bytes())
            return j.get("result") if isinstance(j.get("result"), list) else []
    params = {"module": "logs", "action": "getLogs", "address": address, "topic0": topic0, "fromBlock": 0, "toBlock": "latest", "page": page, "offset": offset}
    if topic1: params.update(topic1=topic1, topic0_1_opr="and")
    try:
        j = etherscan(params, key)
    except Exception:
        j = None
    if j is not None:
        return j["result"] if isinstance(j.get("result"), list) else []
    q = f"module=logs&action=getLogs&fromBlock=0&toBlock=latest&address={address}&topic0={topic0}&page={page}&offset={offset}"
    if topic1: q += f"&topic1={topic1}&topic0_1_opr=and"
    url = "https://eth.blockscout.com/api?" + q
    try:
        st, b = _http(url, host="blockscout_api", retries=2)
        j = json.loads(b)
        res = j.get("result")
        if isinstance(res, list):
            save("blockscout-mutability", key, b, url, "GET", status=st); return res
        if isinstance(res, str) and "no logs" in (j.get("message", "") + res).lower():
            save("blockscout-mutability", key, b, url, "GET", status=st); return []
    except Exception:
        pass
    return None


def checksum(a):
    a = a.lower().replace("0x", ""); h = keccak256(a.encode()).hex()
    return "0x" + "".join(c.upper() if int(h[i], 16) >= 8 else c for i, c in enumerate(a))


def safe_txs(safe, to, key, limit=100):
    """Executed multisig txs of `safe` whose target is `to`, from the Safe Transaction Service (no key needed). Returns list or None."""
    src = "safe-mutability"
    p = cached(src, key)
    if p: return json.loads(p.read_bytes()).get("results", [])
    url = f"https://api.safe.global/tx-service/eth/api/v1/safes/{checksum(safe)}/multisig-transactions/?to={checksum(to)}&executed=true&limit={limit}"
    try:
        st, b = _http(url, host="safe")
        j = json.loads(b)
    except Exception:
        return None
    if "results" not in j: return None
    save(src, key, b, url, "GET", status=st)
    return j["results"]
