"""claims step 2: call contractURI() via eth_call, decode/fetch the JSON, scan description for on-chain claims.
Usage: .venv/bin/python -I scripts/claims/contracturi.py ADDRS_FILE
Raw: data/raw/rpc-claims/curi_<addr>.json (rpc envelope), data/raw/claims-contracturi/<addr>.json (fetched/decoded body).
Outputs data/claims/contracturi_results.jsonl (one record per address) and data/claims/claims_contracturi.csv.
"""
import base64, urllib.error, json, pathlib, re, sys, threading, time, urllib.request, urllib.parse, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib")); sys.path.insert(0, str(ROOT / "scripts" / "claims"))
import rawfetch as rf  # noqa: E402
from srcscan import ONCH, STRONG, STRONG2, STORAGE  # noqa: E402

ENDPOINTS = ["https://eth.drpc.org", "https://eth.rpc.blxrbdn.com"]
OUT = ROOT / "data" / "claims"
_l = threading.Lock(); _t = {}
def throttle(ep, rate=2.5):
    with _l:
        w = _t.get(ep, 0) + 1 / rate - time.time()
        if w > 0: time.sleep(w)
        _t[ep] = time.time()

def decode_string(hexs):
    b = bytes.fromhex(hexs[2:])
    if len(b) < 64: return None
    off = int.from_bytes(b[:32], "big"); ln = int.from_bytes(b[off:off + 32], "big")
    return b[off + 32:off + 32 + ln].decode("utf-8", "replace")

def call(addr, i):
    cached = rf._cached("rpc-claims", f"curi_{addr}", "json")
    if cached:
        return json.loads(cached.read_bytes())
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": addr, "data": "0xe8a3d485"}, "latest"]}).encode()
    last = None
    for k in range(4):
        ep = ENDPOINTS[(i + k) % 2]; throttle(ep)
        try:
            with urllib.request.urlopen(urllib.request.Request(ep, data=body, headers=rf.UA), timeout=30) as r:
                b = r.read()
            j = json.loads(b)
            if "result" in j or ("error" in j and "revert" in json.dumps(j["error"]).lower()) or ("error" in j and j["error"].get("code") == 3):
                rf._save("rpc-claims", f"curi_{addr}", "json", b, {"url": ep, "method": "eth_call", "params": [addr, "contractURI()"], "status": 200})
                return j
            last = j
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(1 + k)
    return {"transient": str(last)[:200]}

def fetch_uri(addr, uri):
    """-> (body_text|None, how, raw_path|None)"""
    if uri.startswith("data:"):
        head, _, data = uri.partition(",")
        try:
            txt = base64.b64decode(data).decode("utf-8", "replace") if "base64" in head else urllib.parse.unquote(data)
        except Exception: return None, "data-undecodable", None
        p = rf._save("claims-contracturi", addr, "json", txt.encode(), {"url": "data-uri-from-contractURI", "method": "decode", "status": 200})
        return txt, "data-uri", str(p.relative_to(ROOT))
    url = uri
    kind = "http"
    if uri.startswith("ipfs://"): url = "https://gateway.pinata.cloud/ipfs/" + uri[7:]; kind = "ipfs"
    elif uri.startswith("ar://"): url = "https://arweave.net/" + uri[5:]; kind = "arweave"
    elif not uri.startswith("http"): return None, "unknown-scheme", None
    try:
        req = urllib.request.Request(url, headers=rf.UA)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    b = r.read(300_000); st = r.status
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 2: time.sleep(3 * (attempt + 1)); continue
                raise
        p = rf._save("claims-contracturi", addr, "json", b, {"url": url, "method": "GET", "status": st, "contracturi": uri})
        return b.decode("utf-8", "replace"), kind, str(p.relative_to(ROOT))
    except Exception as e:  # noqa: BLE001
        return None, f"{kind}-fetch-failed:{repr(e)[:80]}", None

ART = re.compile(r"\b(art|artworks?|images?|svg|nfts?|metadata|collection|generative|generated|stored|stores|pfps?|pixel|pixels|traits|punks?|monsters?|avatars?|characters?|sprites?|glyphs?|animation|artist|drawings?|paintings?|collectibles?|tokens?|ascii|code|renderer|rendered|fully|entirely|100\s?%|completely|assets?|project|contract|everything|forever|permanent(ly)?|immutable)\b", re.I)
ACT = re.compile(r"on[\s-]?chain[\s-]+(activity|activities|data|royalt\w+|transactions?|governance|voting|votes?|reputation|identity|footprint|history|wallets?|behaviou?r|analytics|payments?|lending|trading|economy|rewards?|credentials?|attestations?|games?|gaming|divination|presence|record)|(brought?|bring|bringing|move|moving|onboard\w*)\b.{0,40}\bon[\s-]?chain|\bon[\s-]?chain (activity|data)", re.I)
ONC = re.compile(r"on[\s-]?chain|onchain|on the (block)?chain.{0,12}forever|in the (block)?chain", re.I)


def sentences_with_claim(text):
    out = []
    for s in re.split(r"(?<=[.!?])\s+|\n+", text):
        s = s.strip()
        if not s or len(s) > 700: continue
        if STRONG.search(s) or STRONG2.search(s):
            if ACT.search(s) and not re.search(r"fully|100|entirely", s, re.I): continue
            out.append((s, "explicit-100%/fully"))
        elif ONC.search(s) and ART.search(s) and not ACT.search(s): out.append((s, "on-chain-generic"))
        elif STORAGE.search(s) and ART.search(s) and not re.search(r"^(crypto|\w+)\s+(live|lives)\b", s, re.I): out.append((s, "storage-forever"))
    return out


def one(args):
    i, addr = args
    r = call(addr, i)
    rec = {"address": addr}
    rec["rpc_raw"] = f"data/raw/rpc-claims/curi_{addr}.json"
    if "transient" in r: rec["status"] = "rpc-transient"; return rec
    res = r.get("result")
    if not res or res == "0x" or len(res) < 130: rec["status"] = "no-contractURI"; return rec
    uri = decode_string(res)
    if not uri: rec["status"] = "empty"; return rec
    rec["uri_scheme"] = uri.split(":", 1)[0][:10]; rec["uri_head"] = uri[:200]
    body, how, rp = fetch_uri(addr, uri)
    rec["fetch"] = how; rec["body_raw"] = rp
    if body is None: rec["status"] = "uri-unfetched"; return rec
    rec["status"] = "ok"
    try: j = json.loads(body)
    except Exception: j = None
    desc = (j or {}).get("description") if isinstance(j, dict) else None
    rec["name"] = (j or {}).get("name") if isinstance(j, dict) else None
    rec["description"] = desc
    txt = desc if isinstance(desc, str) else ""
    rec["claims"] = sentences_with_claim(txt)
    return rec

if __name__ == "__main__":
    addrs = []
    for a in pathlib.Path(sys.argv[1]).read_text().split():
        a = a.strip().lower()
        if a.startswith("0x") and a not in addrs: addrs.append(a)
    print(len(addrs), "addrs", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(OUT / "contracturi_results.jsonl", "a") as f, cf.ThreadPoolExecutor(4) as ex:
        for rec in ex.map(one, list(enumerate(addrs))):
            f.write(json.dumps(rec) + "\n"); n += 1
            if n % 200 == 0: print("progress", n, flush=True)
    print("done")
