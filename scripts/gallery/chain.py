"""Minimal eth_call client with per-collection evidence capture.

Every call is saved to data/gallery/<slug>/chain/<key>.json as
{url, method, to, data, block, status, retrieved_at, sha256(result), result}
so each assembled artwork can be traced back to raw chain bytes.
"""
import hashlib, json, os, pathlib, time, urllib.request, urllib.error
from eth_abi import encode, decode

ROOT = pathlib.Path(__file__).resolve().parents[2]
GAL = ROOT / "data" / "gallery"
RPCS = [u for u in [os.environ.get("NFTU_RPC_URL"), "https://eth.drpc.org", "https://eth.rpc.blxrbdn.com"] if u]
UA = {"User-Agent": "nft-unplugged-research/0.1", "Content-Type": "application/json"}

# ---- pure python keccak256 ----
_RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B,
       0x0000000080000001, 0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088,
       0x0000000080008009, 0x000000008000000A, 0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
       0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
       0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M = (1 << 64) - 1
def _rol(x, n): n %= 64; return ((x << n) | (x >> (64 - n))) & _M if n else x
def _f(A):
    for rc in _RC:
        C = [A[x][0] ^ A[x][1] ^ A[x][2] ^ A[x][3] ^ A[x][4] for x in range(5)]
        D = [C[(x - 1) % 5] ^ _rol(C[(x + 1) % 5], 1) for x in range(5)]
        A = [[A[x][y] ^ D[x] for y in range(5)] for x in range(5)]
        B = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                B[y][(2 * x + 3 * y) % 5] = _rol(A[x][y], _ROT[x][y])
        A = [[B[x][y] ^ ((~B[(x + 1) % 5][y]) & B[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        A[0][0] ^= rc
    return A
def keccak256(data: bytes) -> bytes:
    rate = 136
    data = bytearray(data) + b"\x01"
    while len(data) % rate: data += b"\x00"
    data[-1] |= 0x80
    A = [[0] * 5 for _ in range(5)]
    for off in range(0, len(data), rate):
        blk = data[off:off + rate]
        for i in range(rate // 8):
            A[i % 5][i // 5] ^= int.from_bytes(blk[8 * i:8 * i + 8], "little")
        A = _f(A)
    out = b"".join(A[i % 5][i // 5].to_bytes(8, "little") for i in range(4))
    return out[:32]

def selector(sig): return keccak256(sig.encode())[:4]

def calldata(sig, *args):
    """sig like 'tokenURI(uint256)'; args python values matching types."""
    types = sig[sig.index("(") + 1:sig.rindex(")")]
    tl = [t for t in _split_types(types)] if types else []
    return "0x" + (selector(sig) + (encode(tl, args) if tl else b"")).hex()

def _split_types(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(": depth += 1
        if ch == ")": depth -= 1
        if ch == "," and depth == 0: out.append(cur); cur = ""
        else: cur += ch
    if cur: out.append(cur)
    return out

def _post(url, body, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

ANVIL = os.environ.get('NFTU_ANVIL', 'http://127.0.0.1:8571')  # local fork of mainnet (pinned block, no gas cap) for gas-heavy renderers

def rpc_raw(method, params, timeout=120, retries=5, rpc=None):
    last = None
    for i in range(retries):
        url = rpc or RPCS[i % len(RPCS)]
        try:
            j = _post(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout)
            if "error" in j:
                msg = str(j["error"])
                if "revert" in msg.lower() or "execution" in msg.lower():
                    return url, j  # real revert: do not retry elsewhere endlessly
                last = RuntimeError(msg)
                time.sleep(1.5 * (i + 1)); continue
            return url, j
        except Exception as e:  # noqa
            last = e; time.sleep(1.5 * (i + 1))
    raise last

def eth_call(to, data, slug, key, block="latest", frm=None, refresh=False, rpc=None, gas=None):
    """Returns result bytes (b'' on revert). Evidence saved under data/gallery/<slug>/chain/<key>.json"""
    d = GAL / slug / "chain"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{key}.json"
    if p.exists() and not refresh:
        rec = json.loads(p.read_text())
        return bytes.fromhex(rec["result"][2:]) if rec.get("result") else b""
    call = {"to": to, "data": data}
    if frm: call["from"] = frm
    if gas: call["gas"] = gas
    url, j = rpc_raw("eth_call", [call, block], rpc=rpc)
    if rpc == ANVIL: url = 'anvil-fork@' + os.environ.get('NFTU_FORK_BLOCK', open(ROOT/'data/gallery/FORK_BLOCK').read().strip() if (ROOT/'data/gallery/FORK_BLOCK').exists() else '?') + ' of ' + RPCS[1]
    res = j.get("result")
    rec = {"url": url, "method": "eth_call", "gas_param": gas, "to": to, "data": data if len(data) < 2000 else data[:2000] + "...", "block": block,
           "status": "ok" if res else "error", "error": j.get("error"), "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "result_len_bytes": (len(res) - 2) // 2 if res else 0,
           "sha256": hashlib.sha256(bytes.fromhex(res[2:])).hexdigest() if res else None, "result": res}
    p.write_text(json.dumps(rec))
    return bytes.fromhex(res[2:]) if res else b""

def call(to, sig, args, outtypes, slug, key=None, **kw):  # kw: block, rpc, refresh
    cd = calldata(sig, *args)
    key = key or (sig.split("(")[0] + "_" + "_".join(str(a) for a in args))[:100]
    raw = eth_call(to, cd, slug, key, **kw)
    if not raw:
        return None
    r = decode(outtypes, raw)
    return r[0] if len(r) == 1 else r

def get_code(addr, slug, key="code", refresh=False):
    d = GAL / slug / "chain"; d.mkdir(parents=True, exist_ok=True)
    p = d / f"{key}.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text())["result"]
    url, j = rpc_raw("eth_getCode", [addr, "latest"])
    rec = {"url": url, "method": "eth_getCode", "address": addr, "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "status": "ok", "result_len_bytes": (len(j["result"]) - 2) // 2,
           "sha256": hashlib.sha256(bytes.fromhex(j["result"][2:])).hexdigest(), "result": j["result"]}
    p.write_text(json.dumps(rec))
    return j["result"]

def checksum(addr):
    a = addr.lower().replace("0x", "")
    h = keccak256(a.encode()).hex()
    return "0x" + "".join(c.upper() if int(h[i], 16) >= 8 else c for i, c in enumerate(a))
