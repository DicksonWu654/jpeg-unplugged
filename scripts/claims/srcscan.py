"""claims: fetch verified source (Etherscan v2 getsourcecode, raw-saved) and extract claim phrases + code signals.

Usage: .venv/bin/python -I scripts/claims/srcscan.py fetch ADDRS_FILE [--workers 3]
       .venv/bin/python -I scripts/claims/srcscan.py analyze        # builds data/claims/source_signals.parquet + claims_source.csv
Raw responses: data/raw/etherscan/src_<addr>.json (never cached when the API returned an error/rate-limit).
"""
import json, os, pathlib, re, sys, threading, time, urllib.request, urllib.error, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import rawfetch as rf  # noqa: E402

RAW = ROOT / "data" / "raw" / "etherscan"
OUT = ROOT / "data" / "claims"
RATE = 3.0
_lock = threading.Lock(); _last = [0.0]


def _throttle():
    with _lock:
        now = time.time(); wait = _last[0] + 1 / RATE - now
        if wait > 0: time.sleep(wait)
        _last[0] = time.time()


def _key():
    k = os.environ.get("ETHERSCAN_API_KEY")
    if k: return k
    for line in (pathlib.Path("etherscan.env")).read_text().splitlines():
        if line.startswith("ETHERSCAN_API_KEY="): return line.split("=", 1)[1].strip().strip('"')


KEY = None


def src_path(addr): return RAW / f"src_{addr.lower()}.json"


def fetch_one(addr, refresh=False):
    """Returns 'cached' | 'ok' | 'error:<msg>'. Saves only well-formed responses."""
    global KEY
    addr = addr.lower()
    if have(addr) and not refresh: return "cached"
    KEY = KEY or _key()
    url = f"https://api.etherscan.io/v2/api?chainid=1&module=contract&action=getsourcecode&address={addr}&apikey={KEY}"
    last = "?"
    for i in range(6):
        _throttle()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=rf.UA), timeout=45) as r:
                b = r.read(); st = r.status
            j = json.loads(b)
            res = j.get("result")
            if isinstance(res, list) and res and isinstance(res[0], dict):
                rf._save("etherscan", f"src_{addr}", "json", b,
                         {"url": url.replace(KEY, "REDACTED"), "method": "GET", "status": st})
                return "ok"
            last = str(res)[:100]  # rate limit text etc
        except Exception as e:  # noqa: BLE001
            last = repr(e)[:100]
        time.sleep(1.5 * (i + 1))
    return "error:" + last


BS = ROOT / "data" / "raw" / "blockscout-src"


def bs_path(addr): return BS / f"{addr.lower()}.json"


def have(addr): return src_path(addr).exists() or bs_path(addr).exists()


def load(addr):
    p = src_path(addr)
    if p.exists(): return json.loads(p.read_bytes())["result"][0]
    q = bs_path(addr)
    if not q.exists(): return None
    j = json.loads(q.read_bytes())
    if not j.get("is_verified") and not j.get("source_code"):
        return {"SourceCode": "", "ContractName": "", "CompilerVersion": "", "_via": "blockscout"}
    srcs = {j.get("file_path") or "main.sol": j.get("source_code") or ""}
    for a in j.get("additional_sources") or []: srcs[a.get("file_path")] = a.get("source_code") or ""
    impls = j.get("implementations") or []
    return {"SourceCode": "{{" + json.dumps({"sources": {k: {"content": v} for k, v in srcs.items()}}) + "}}",
            "ContractName": j.get("name"), "CompilerVersion": j.get("compiler_version"), "LicenseType": j.get("license_type"),
            "Proxy": "1" if impls else "0", "Implementation": (impls[0].get("address_hash") if impls else "") or "", "_via": "blockscout"}


_bl = threading.Lock(); _bt = [0.0]


def fetch_bs(addr):
    addr = addr.lower()
    if have(addr): return "cached"
    url = f"https://eth.blockscout.com/api/v2/smart-contracts/{addr}"
    last = "?"
    for i in range(5):
        with _bl:
            w = _bt[0] + 1 / 2.5 - time.time()
            if w > 0: time.sleep(w)
            _bt[0] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=rf.UA), timeout=45) as r:
                b = r.read(); st = r.status
            rf._save("blockscout-src", addr, "json", b, {"url": url, "method": "GET", "status": st}); return "ok"
        except urllib.error.HTTPError as e:
            if e.code == 404:  # not verified on blockscout: record as unverified
                rf._save("blockscout-src", addr, "json", b'{"is_verified": false, "note": "HTTP 404"}', {"url": url, "method": "GET", "status": 404}); return "ok"
            last = f"http{e.code}"; time.sleep(3 * (i + 1))
        except Exception as e:  # noqa: BLE001
            last = repr(e)[:80]; time.sleep(2 * (i + 1))
    return "error:" + last


def files_of(rec):
    """-> list of (filename, text)."""
    sc = rec.get("SourceCode") or ""
    if not sc: return []
    s = sc.strip()
    if s.startswith("{{") and s.endswith("}}"):
        try:
            j = json.loads(s[1:-1]); return [(k, v.get("content", "")) for k, v in j.get("sources", {}).items()]
        except Exception: pass
    if s.startswith("{"):
        try:
            j = json.loads(s)
            if "sources" in j: return [(k, v.get("content", "")) for k, v in j["sources"].items()]
            return [(k, v.get("content", "") if isinstance(v, dict) else str(v)) for k, v in j.items()]
        except Exception: pass
    return [(rec.get("ContractName") or "main", sc)]


LIB = re.compile(r"(openzeppelin|solmate|solady|/utils/|/interfaces?/|erc721a|ds-test|forge-std|chiru-labs|base64\.sol|/lib/|node_modules)", re.I)
ONCH = re.compile(r"on[\s_-]?chain|on[\s-]the[\s-](block)?chain|in[\s-]the[\s-](block)?chain|on[\s-]ethereum|stored (entirely )?(on|in) (the )?(block|eth)|fully[\s-]?decentrali[sz]ed|forever|permanent(ly)?|immutable|eternal", re.I)
STRONG = re.compile(r"(100\s?%|fully|entirely|completely|totally|purely|wholly|100 percent|all)[\s,]*(on[\s-]?chain|stored|generated|rendered|in the (block)?chain|on the (block)?chain)", re.I)
STRONG2 = re.compile(r"on[\s-]?chain.{0,40}(100\s?%|fully|entirely|completely|forever)|100\s?%.{0,40}on[\s-]?chain", re.I)
TECH = re.compile(r"sstore2|ethfs|filestore|scripty|base64|svg|data:application/json|data:image", re.I)
STORAGE = re.compile(r"(stored|live|lives|exist|exists|saved|permanent(ly)?|immutabl[ey]).{0,30}(forever|on the (block)?chain|in the (block)?chain|on ethereum|on-chain)", re.I)
SKIP_LINE = re.compile(r"(@dev|@notice|@param|@return)?\s*(onchain|on-chain)?\s*SPDX", re.I)
# identifiers: ignore matches that are camelCase/snake identifiers (onChainData, on_chain_x) unless in comment/string
IDENT = re.compile(r"\b\w*[oO]n[cC]hain\w*\b")


POS = re.compile(r"\b(art|artwork|image|images|svg|metadata|nft|nfts|token|tokens|collection|pixel|pixels|generated|generative|rendered|render|stored|storage|json|attributes|traits?|monkey|punk|avatar|characters?|sprite|glyph|canvas|palette|drawing|painting|mint|minted|data|assets?|project|contract|everything|entirely|fully|100\s?%)\b", re.I)
NEG = re.compile(r"royalt|enumerab|nonce|oracle|\bVRF\b|governance|proposal|\bvote|bridge|price feed|reference to|order ?book|settle|permit|signature|randomness|\bswap|\bgas\b|mandatory|filterer|operator|dst|src|chain ?id|cross-chain|layerzero|@author|@custom|@param|transfer(s)? (of|to)|balance|allowance|\bhash(es)? (of|on)|snapshot|\bsale\b|auction|allowlist|whitelist|merkle", re.I)


def in_comment_or_string(line):
    s = line.strip()
    if s.startswith(("//", "/*", "*", "///")): return "comment"
    if "//" in s or "/*" in s: return "comment" if ONCH.search(s[s.find("/"):]) else None
    if '"' in s or "'" in s: return "string"
    return None


def scan_text(fname, text):
    """-> list of dict(line_no, kind, strength, text)"""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if len(line) > 600: line = line[:600]
        if not ONCH.search(line): continue
        kind = in_comment_or_string(line)
        if not kind: continue
        t = line.strip()
        if kind == "string" and re.search(r"data:image|base64,|<svg|http", t) and not STRONG.search(t) and not STRONG2.search(t):
            if not re.search(r"on[\s-]?chain", t, re.I): continue
        m_on = re.search(r"on[\s-]?chain|on[\s-]the[\s-](block)?chain|in[\s-]the[\s-](block)?chain|stored.{0,15}(on|in) (the )?(block|eth)", t, re.I)
        m_str = STRONG.search(t) or STRONG2.search(t)
        m_sto = STORAGE.search(t)
        if m_str: strength = "explicit-100%/fully"
        elif m_on or m_sto:
            # generic mentions must look like a statement about the artwork/metadata, not protocol plumbing
            if NEG.search(t) or not POS.search(t): continue
            strength = "on-chain-generic" if m_on else "storage-forever"
        else: continue  # bare 'forever'/'immutable' w/o chain context is noise
        out.append({"file": fname, "line_no": i, "kind": kind, "strength": strength, "text": t[:400]})
    return out


SET_URI = r"function\s+((?:set|update|change|reveal|edit)(?!contract)\w*(?:base\s?uri|token\s?uri|baseTokenURI|nft\s?uri|metadata\s?uri|hidden\s?uri|unrevealed\w*|notrevealed\w*|uri\b)\w*)\s*\([^)]*\)[^;{]*\{"
SET_REND = r"function\s+((?:set|update|change|upgrade)\w*(?:render\w*|descriptor|metadata\s?(?:contract|address)|generator|artwork\w*|art\s?(?:contract|address)|svg\s?(?:contract|address)|palette\w*|scripty\w*|trait\s?(?:contract|address)|image\s?(?:contract|address))\w*)\s*\([^)]*\)[^;{]*\{"
FREEZE = r"function\s+(?:freeze|lock|finali[sz]e|seal|permanentlyLock)\w*\s*\(|metadata\w*(?:frozen|locked)|(?:frozen|isFrozen|uriFrozen|baseURIFrozen|locked)\b\s*[=;)\]]"


def signals(rec, files, impl_rec=None, impl_files=None):
    allf = files + (impl_files or [])
    blob = "\n".join(t for _, t in allf)
    low = blob.lower()
    def has(rx): return bool(re.search(rx, blob, re.I))
    s = {
        "verified": bool(rec.get("SourceCode")),
        "contract_name": rec.get("ContractName"), "compiler": rec.get("CompilerVersion"),
        "is_proxy": rec.get("Proxy") == "1" or bool(rec.get("Implementation")),
        "implementation": (rec.get("Implementation") or "").lower() or None,
        "impl_verified": bool(impl_rec and impl_rec.get("SourceCode")),
        "n_files": len(allf), "src_bytes": len(blob.encode()),
        "has_base64": has(r"\bbase64\b"), "has_sstore2": has(r"sstore2"),
        "has_ethfs": has(r"ethfs|filestore|file[_ ]?store"), "has_scripty": has(r"scripty"),
        "has_svg": has(r"<svg|svg\+xml|\bsvg\b"), "has_data_json": has(r"data:application/json"),
        "has_data_uri": has(r"data:(image|application|text)"),
        "has_http_literal": has(r'"https?://'), "has_ipfs_literal": has(r'ipfs://|ipfs/|ipfs\.io|pinata'),
        "has_arweave_literal": has(r"arweave\.net|\bar://|arweave"),
        "has_set_baseuri": has(SET_URI),
        "uri_setters": ",".join(sorted({m.group(1) for m in re.finditer(SET_URI, blob, re.I)}))[:300] or None,
        "has_set_renderer": has(SET_REND),
        "renderer_setters": ",".join(sorted({m.group(1) for m in re.finditer(SET_REND, blob, re.I)}))[:300] or None,
        "has_freeze_lock": has(FREEZE),
        "has_renounce": has(r"renounceOwnership|renounceRole"),
        "has_reveal": has(r"reveal"),
        "has_owner_upgrade": has(r"upgradeTo|_upgradeTo|delegatecall|UUPS|TransparentUpgradeableProxy"),
        "tokenuri_concat_baseuri": has(r"abi\.encodePacked\(\s*_?base\w*uri|_baseURI\(\)"),
        "has_set_contracturi": has(r"function\s+set\w*contracturi\w*\s*\([^)]*\)[^;{]*\{"),
        "has_contracturi": has(r"function\s+contractURI"),
        "has_tokenuri": has(r"function\s+tokenURI"),
        "license": rec.get("LicenseType"),
    }
    return s


def analyze_one(addr):
    rec = load(addr)
    if rec is None: return None, []
    files = files_of(rec)
    impl = (rec.get("Implementation") or "").lower()
    irec = load(impl) if impl and have(impl) else None
    ifiles = files_of(irec) if irec else []
    sig = signals(rec, files, irec, ifiles)
    claims = []
    for tag, fs in (("self", files), ("impl", ifiles)):
        for fn, t in fs:
            if LIB.search(fn) and not re.search(r"on[\s-]?chain", t[:20000], re.I): continue
            for c in scan_text(fn, t):
                # skip license-boilerplate / lib noise
                if LIB.search(fn) and c["strength"] == "on-chain-generic" and "@openzeppelin" in fn: continue
                c["where"] = tag; claims.append(c)
    sig["n_claim_lines"] = len(claims)
    sig["best_strength"] = (["explicit-100%/fully", "on-chain-generic", "storage-forever"] and
                            next((s for s in ("explicit-100%/fully", "on-chain-generic", "storage-forever")
                                  if any(c["strength"] == s for c in claims)), None))
    return sig, claims


def cmd_fetch(args):
    addrs = [a.strip().lower() for a in pathlib.Path(args[0]).read_text().split() if a.strip().startswith("0x")]
    workers = int(os.environ.get("W", 3))
    seen = set(); todo = [a for a in addrs if not (a in seen or seen.add(a))]
    if os.environ.get("REV"): todo = todo[::-1]
    print(len(todo), "addresses", flush=True)
    stats = {}
    done = [0]
    def job(a):
        r = (fetch_bs if os.environ.get("BS") else fetch_one)(a)
        rec = None
        if r in ("ok", "cached"):
            rec = load(a)
            impl = (rec.get("Implementation") or "").lower()
            if impl and impl.startswith("0x") and not have(impl): (fetch_bs if os.environ.get("BS") else fetch_one)(impl)
        done[0] += 1
        if done[0] % 200 == 0: print("progress", done[0], stats, flush=True)
        return a, r
    with cf.ThreadPoolExecutor(workers) as ex:
        for a, r in ex.map(job, todo):
            k = r.split(":")[0]; stats[k] = stats.get(k, 0) + 1
            if k == "error": print("ERR", a, r, flush=True)
    print("done", stats)


def _safe_analyze(a):
    try: return analyze_one(a)
    except Exception as e:  # noqa: BLE001
        print("analyze fail", a, e); return None, []


def cmd_analyze(args):
    import pandas as pd
    rows, claims = [], []
    names = {}
    paths = {p.stem[4:]: p for p in RAW.glob("src_0x*.json")}
    for p in BS.glob("0x*.json"): paths.setdefault(p.stem, p)
    import multiprocessing as mp
    items = sorted(paths.items())
    with mp.Pool(8) as pool:
        results = pool.map(_safe_analyze, [a for a, _ in items], chunksize=20)
    for (a, p), (sig, cl) in zip(items, results):
        if sig is None: continue
        sig["address"] = a; sig["raw_path"] = str(p.relative_to(ROOT))
        sig["retrieved_at"] = None
        rows.append(sig)
        for c in cl: claims.append({"address": a, "contract_name": sig["contract_name"], **c, "raw_path": sig["raw_path"]})
    from collections import Counter
    freq = Counter(); seen = set()
    for c in claims:
        k = (c["address"], c["text"])
        if k not in seen: seen.add(k); freq[c["text"]] += 1
    claims = [c for c in claims if c["strength"] == "explicit-100%/fully" and freq[c["text"]] < 8 or freq[c["text"]] < 4]
    byaddr = {}
    for c in claims: byaddr.setdefault(c["address"], []).append(c["strength"])
    order = ("explicit-100%/fully", "on-chain-generic", "storage-forever")
    for r in rows:
        ss = byaddr.get(r["address"], [])
        r["n_claim_lines"] = len(ss)
        r["best_strength"] = next((x for x in order if x in ss), None)
        r["name_has_onchain"] = bool(re.search(r"on[\s_-]?chain", (r["contract_name"] or ""), re.I))
    df = pd.DataFrame(rows); OUT.mkdir(parents=True, exist_ok=True)
    # retrieved_at from MANIFEST
    ts = {}
    for line in open(ROOT / "data/raw/MANIFEST.jsonl"):
        try: m = json.loads(line)
        except Exception: continue
        if m.get("path") and ("/src_0x" in m["path"] or "blockscout-src" in m["path"]): ts[m["path"]] = m["retrieved_at"]
    df["retrieved_at"] = df["raw_path"].map(ts)
    df.to_parquet(OUT / "source_signals.parquet", index=False)
    pd.DataFrame(claims).to_csv(OUT / "claims_source_lines.csv", index=False)
    print(len(df), "contracts;", len(claims), "claim lines;", df["best_strength"].value_counts(dropna=False).to_dict())


if __name__ == "__main__":
    {"fetch": cmd_fetch, "analyze": cmd_analyze}[sys.argv[1]](sys.argv[2:])
