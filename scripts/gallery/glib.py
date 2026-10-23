"""Shared helpers for building gallery items (assemble chain bytes -> artwork file + meta.json)."""
import base64, hashlib, html, json, pathlib, re, time, urllib.parse, urllib.request
import chain

GAL = chain.GAL
HTML_CT = "text/html; charset=utf-8"
SVG_CT = "image/svg+xml; charset=utf-8"

def b64d(s): return base64.b64decode(s + "=" * (-len(s) % 4))

def decode_data_uri(u):
    """'data:<mime>[;charset=..][;base64],<payload>' -> (mime, bytes)"""
    head, _, payload = u.partition(",")
    mime = head[5:].split(";")[0] or "text/plain"
    if ";base64" in head:
        return mime, b64d(payload)
    return mime, urllib.parse.unquote_to_bytes(payload)

def parse_json_uri(u):
    """tokenURI string -> (dict, how). how in {data-uri-base64, data-uri-utf8, raw-json}"""
    if u.startswith("data:application/json"):
        mime, b = decode_data_uri(u)
        how = "data-uri-base64" if ";base64" in u[:60] else "data-uri-utf8"
        return json.loads(b.decode("utf-8", "replace"), strict=False), how
    if u.lstrip().startswith("{"):
        return json.loads(u, strict=False), "raw-json"
    return None, None

def scheme_of(v):
    if not isinstance(v, str): return None
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):", v)
    if m:
        s = m.group(1).lower()
        if s == "data":
            return "data:" + v[5:].split(";")[0].split(",")[0]
        return s
    return "relative"

_URL = re.compile(r"""(?:https?:)?//[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%\-]+""")
_LOAD = re.compile(r"""(?:src|href|xlink:href|data|poster)\s*=\s*["']?\s*((?:https?:)?//[^"'\s>]+)|url\(\s*["']?((?:https?:)?//[^"')\s]+)|@import\s+["']((?:https?:)?//[^"']+)|(?:import|fetch|importScripts)\s*\(?\s*["'`]((?:https?:)?//[^"'`]+)""", re.I)
_IGN = ("www.w3.org", "w3.org/", "purl.org", "schemas.xmlsoap", "inkscape.org", "sodipodi", "creativecommons.org")

def scan_declared(text):
    """Static scan of an artwork document for externally-hosted resources it *declares*.
    returns dict(load=[urls in load position: src/href/url()/@import/fetch literal], literals=[all other http(s) literals, excluding XML namespaces])."""
    stripped = re.sub(r"base64,[A-Za-z0-9+/=_-]{64,}", "base64,#", text)
    load = []
    for m in _LOAD.finditer(stripped):
        u = next(g for g in m.groups() if g)
        if not any(i in u for i in _IGN): load.append(u)
    lits = [u.rstrip(".,;)'\"`") for u in _URL.findall(stripped) if not any(i in u for i in _IGN)]
    load = sorted(set(load))
    lits = sorted(set(l for l in lits if l not in load and not l.startswith("//") or (l.startswith("//") and l[2:3].isalnum() and "." in l[:40])))
    return dict(load=load, literals=lits[:40])

def gas_estimate(to, data, slug, key):
    """eth_estimateGas on the local anvil fork (no gas cap) -> int or None. Saved as chain/gas_<key>.json"""
    d = GAL / slug / "chain"; d.mkdir(parents=True, exist_ok=True); p = d / f"gas_{key}.json"
    if p.exists():
        return json.loads(p.read_text()).get("gas")
    try:
        url, j = chain.rpc_raw("eth_estimateGas", [{"to": to, "data": data}], rpc=chain.ANVIL, retries=1, timeout=300)
        g = int(j["result"], 16) if j.get("result") else None
        p.write_text(json.dumps({"method": "eth_estimateGas", "to": to, "data": data[:200], "rpc": "anvil-fork@" + (chain.ROOT / "data/gallery/FORK_BLOCK").read_text().strip(), "gas": g, "error": j.get("error"),
                                 "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
        return g
    except Exception:
        return None

HIGH_GAS = "0x3B9ACA00"   # 1e9: explicit eth_call gas, per coordinator instruction

def smart_call(to, sig, args, outtypes, slug, key=None, heavy_ok=True):
    """Read ladder (every rung recorded in meta['rpc']):
       1 default public eth_call (drpc, then blxrbdn via retry)   2 public eth_call with explicit gas 0x3B9ACA00 on BOTH public RPCs
       3 local anvil fork of mainnet at a pinned block (no gas cap).  Returns (result, info)."""
    key = key or (sig.split("(")[0] + "_" + "_".join(str(a) for a in args))[:100]
    info = {"default_public_ok": None, "highgas_drpc_ok": None, "highgas_blxr_ok": None, "fork_ok": None, "rpc": "public-default"}
    r = chain.call(to, sig, args, outtypes, slug, key)
    info["default_public_ok"] = r is not None
    if r is None and heavy_ok:
        for i, tag in ((0, "drpc"), (1, "blxr")):
            if r is None:
                r = chain.call(to, sig, args, outtypes, slug, f"{key}__highgas_{tag}", rpc=chain.RPCS[i], gas=HIGH_GAS)
                info[f"highgas_{tag}_ok"] = r is not None
                if r is not None: info["rpc"] = f"public with explicit gas {HIGH_GAS} ({tag})"
    if r is None and heavy_ok:
        r = chain.call(to, sig, args, outtypes, slug, key + "__anvil", rpc=chain.ANVIL)
        info["fork_ok"] = r is not None
        info["rpc"] = "local anvil fork (public RPCs revert even with explicit gas)" if r is not None else "failed"
    info["needed_fork"] = bool(info["fork_ok"])
    info["unreadable_from_default_public_call"] = not info["default_public_ok"]
    info["gas_estimate"] = gas_estimate(to, chain.calldata(sig, *args), slug, key) if (r is not None and not info["default_public_ok"]) else info.get("gas_estimate")
    return r, info

def write_item(slug, meta, artwork, ext, doc_type):
    d = GAL / slug; d.mkdir(parents=True, exist_ok=True)
    data = artwork if isinstance(artwork, bytes) else artwork.encode("utf-8")
    fn = f"artwork.{ext}"
    (d / fn).write_bytes(data)
    text = data.decode("utf-8", "replace")
    meta = dict(meta)
    if meta.get("want_flags", True) and str(meta.get("contract", "")).startswith("0x") and not str(slug).startswith("ab-") and "source_flags" not in meta:
        try:
            import srcflags
            meta["source_flags"] = srcflags.flags(meta["contract"])
        except Exception as e:  # noqa
            meta["source_flags"] = {"error": str(e)[:100]}
    meta.update(artwork_file=fn, doc_type=doc_type, artwork_bytes=len(data), artwork_sha256=hashlib.sha256(data).hexdigest(),
                declared=scan_declared(text), built_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    (d / "meta.json").write_text(json.dumps(meta, indent=1))
    return meta

def img_viewer(src, bg="#fff"):
    return f'<!doctype html><meta charset="utf-8"><body style="margin:0;background:{bg};display:flex;align-items:center;justify-content:center;height:100vh"><img src="{html.escape(src, quote=True)}" style="max-width:100vw;max-height:100vh;image-rendering:pixelated"></body>'

def pre_viewer(text, bg="#fff", fg="#000", fs=14):
    return f'<!doctype html><meta charset="utf-8"><body style="margin:0;background:{bg};color:{fg}"><pre style="font:{fs}px/{fs}px monospace;margin:16px">{html.escape(text)}</pre></body>'
