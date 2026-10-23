"""Pure classification helpers for the JPEG Unplugged census (no network, no I/O).

URI classes (level 1 = metadata, level 2 = media use the same classifier):
  data-uri  data: URI, or the string itself is raw JSON / SVG / HTML        (on-chain)
  ipfs      ipfs://, /ipfs/<cid>, bare CID, or any http(s) IPFS gateway URL (records hardcoded gateway)
  arweave   ar://, or arweave-gateway URL with a 43-char tx id
  http      any other http(s) URL (records host + approx. registrable domain)
  other     recognised non-http scheme we do not fetch (ipns://, bzz://, sia://, ...)
  broken    revert / empty / malformed / undecodable
`onchain-renderer` vs static data-uri is decided elsewhere (bytecode/source hints), see census.py.
"""
import base64
import binascii
import ipaddress
import json
import re
from urllib.parse import urlsplit, unquote, unquote_to_bytes, urljoin  # noqa: F401

CIDV0 = re.compile(r"^Qm[1-9A-HJ-NP-Za-km-z]{44}$")
CIDV1 = re.compile(r"^(?:b[a-z2-7]{50,}|z[1-9A-HJ-NP-Za-km-z]{40,}|f[0-9a-f]{60,})$")
IPNS_KEY = re.compile(r"^(?:k51[0-9a-z]{50,}|12D3[1-9A-HJ-NP-Za-km-z]{40,})$")
AR_TX = re.compile(r"^[A-Za-z0-9_-]{43}$")

AR_GATEWAY_SUFFIXES = (
    "arweave.net", "ar-io.net", "ar-io.dev", "g8way.io", "arweave.dev", "ar.io", "permagate.io",
    "irys.xyz", "bundlr.network", "arweave.live", "arweave.cloud",
)
# 2-level public suffixes we care about (approximation; the paper's final domain stats should use the PSL)
TWO_LEVEL = {"co.uk", "org.uk", "ac.uk", "com.au", "net.au", "co.jp", "co.kr", "com.br", "com.cn", "co.nz",
             "com.sg", "co.za", "com.mx", "com.tr", "com.hk", "com.tw", "co.in", "com.ar", "[withheld-host]",
             "[withheld-host]", "[withheld-host]", "[withheld-host]", "[withheld-host]", "firebaseapp.com", "appspot.com",
             "[withheld-host]", "cloudfront.net", "[withheld-host]", "pages.dev", "workers.dev",
             "ngrok.io", "glitch.me", "repl.co", "onrender.com", "fly.dev", "railway.app",
             "storage.googleapis.com", "web.core.windows.net"}


def reg_domain(host):
    """Approximate registrable domain (eTLD+1). Keeps hosting-platform suffixes so tenants differ."""
    host = (host or "").lower().strip(".")
    if not host or re.fullmatch(r"[\d.]+", host) or ":" in host:
        return host
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if ".".join(labels[-2:]) in TWO_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def is_cid(s):
    return bool(CIDV0.match(s) or CIDV1.match(s))


def substitute_id(uri, token_id):
    """EIP-1155: replace the literal {id} with the token id as 64 lowercase hex digits, zero padded."""
    return uri.replace("{id}", format(int(token_id), "064x"))


# ----------------------------------------------------------------------------------------------
# data: URIs
# ----------------------------------------------------------------------------------------------
def _b64decode_lenient(s):
    s = re.sub(r"\s+", "", s)
    if "%" in s:
        s = unquote(s)
    s = s.replace("-", "+").replace("_", "/")
    if re.search(r"[^A-Za-z0-9+/=]", s):
        raise ValueError("non-base64 characters")
    s += "=" * (-len(s) % 4)
    return base64.b64decode(s, validate=False)


def parse_data_uri(uri):
    """Return dict(mime, params, encoding, payload: bytes). Raises ValueError if undecodable."""
    if not uri[:5].lower() == "data:":
        raise ValueError("not a data uri")
    rest = uri[5:]
    i = rest.find(",")
    if i < 0:
        raise ValueError("data uri without comma")
    header, data = rest[:i], rest[i + 1:]
    parts = [p.strip() for p in header.split(";")]
    mime = (parts[0] or "text/plain").lower()
    flags = [p.lower() for p in parts[1:]]
    if "base64" in flags:
        try:
            payload = _b64decode_lenient(data)
            enc = "base64"
        except (binascii.Error, ValueError) as e:
            if data.lstrip()[:1] in "{[<":
                payload, enc = data.encode("utf-8", "replace"), "raw-mislabeled-base64"
            else:
                raise ValueError(f"bad base64: {e}")
    else:
        payload = unquote_to_bytes(data)
        enc = "percent" if "%" in data else ("utf8" if any(f.startswith(("utf8", "utf-8", "charset")) for f in flags) else "plain")
    return {"mime": mime, "params": flags, "encoding": enc, "payload": payload}


def sniff(head):
    """Magic-byte sniff of the first bytes of a response. Returns a short type string or None."""
    h = head[:2048]
    if h.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if h.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if h[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if h[:4] == b"RIFF" and h[8:12] == b"WEBP":
        return "webp"
    if h[4:8] == b"ftyp":
        return "avif" if h[8:12] in (b"avif", b"avis") else "mp4"
    if h[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if h[:4] == b"glTF":
        return "glb"
    if h[:3] == b"ID3" or h[:2] in (b"\xff\xfb", b"\xff\xf3"):
        return "mp3"
    if h[:4] == b"OggS":
        return "ogg"
    if h[:4] == b"RIFF" and h[8:12] == b"WAVE":
        return "wav"
    if h[:2] == b"BM":
        return "bmp"
    if h[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if h[:4] == b"%PDF":
        return "pdf"
    t = h.lstrip(b"\xef\xbb\xbf \t\r\n")
    tl = t[:600].lower()
    if tl.startswith(b"<svg") or (tl.startswith((b"<?xml", b"<!--", b"<!doctype svg")) and b"<svg" in h.lower()):
        return "svg"
    if tl.startswith((b"<!doctype html", b"<html", b"<head", b"<body", b"<script", b"<meta", b"<title")) or b"<html" in tl:
        return "html"
    if t[:1] in (b"{", b"["):
        return "json?"
    return None


def parse_json_lenient(raw):
    """Parse metadata JSON from bytes/str. Returns (obj, note) ; obj None if not JSON."""
    if isinstance(raw, bytes):
        try:
            s = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            s = raw.decode("utf-8", "replace")
    else:
        s = raw
    s2 = s.strip().strip("\x00")
    for strict, note in ((True, None), (False, "lenient-control-chars")):
        try:
            return json.loads(s2, strict=strict), note
        except (ValueError, RecursionError):
            pass
    return None, "not-json"


# ----------------------------------------------------------------------------------------------
# URI classification
# ----------------------------------------------------------------------------------------------
def _split_ipfs_path(rest):
    """rest = '<cid>[/path][?query]' (after stripping ipfs://, optional 'ipfs/'). -> (cid, path)"""
    rest = rest.lstrip("/")
    if rest.lower().startswith("ipfs/"):
        rest = rest[5:]
    m = re.match(r"^([^/?#]+)(.*)$", rest, re.S)
    return (m.group(1), m.group(2)) if m else ("", "")


def classify_uri(uri):
    """Classify a (substituted) tokenURI / image / animation_url string."""
    out = {"cls": "broken", "reason": None}
    if uri is None:
        out["reason"] = "none"
        return out
    u = uri.strip().strip("\x00").strip()
    if not u:
        out["reason"] = "empty"
        return out
    ul = u.lower()
    if ul.startswith("data:"):
        try:
            d = parse_data_uri(u)
        except ValueError as e:
            out["reason"] = f"data-undecodable: {e}"
            out["scheme"] = "data"
            return out
        out.update(cls="data-uri", reason=None, scheme="data", mime=d["mime"], encoding=d["encoding"], size=len(d["payload"]))
        return out
    if u[:1] in "{[" or ul.startswith(("<svg", "<?xml", "<!doctype", "<html")):
        kind = "json" if u[:1] in "{[" else ("svg" if "<svg" in ul[:400] else "html")
        out.update(cls="data-uri", scheme="raw", mime=kind, encoding="raw-" + kind, size=len(u.encode("utf-8", "replace")))
        return out
    if ul.startswith(("ipfs://http://", "ipfs://https://", "ipfs:///http://", "ipfs:///https://")):
        inner = u[7:].lstrip("/")  # real-world quirk: "ipfs://https://gateway/ipfs/<cid>/n"
        r = classify_uri(inner)
        r["quirk"] = "ipfs-scheme-prefix-on-url"
        r["fetch_uri"] = inner
        return r
    if ul.startswith("ipfs://") or ul.startswith("ipns://"):
        is_ns = ul.startswith("ipns://")
        cid, path = _split_ipfs_path(u[7:])
        out.update(scheme="ipns" if is_ns else "ipfs", cid=cid, path=path, gateway=None)
        if is_ns:
            out.update(cls="other", reason=None, ipns=True)
        elif is_cid(cid):
            out.update(cls="ipfs", reason=None)
        else:
            out.update(cls="broken", reason="ipfs-malformed-cid")
        return out
    if ul.startswith("ar://"):
        rest = u[5:].lstrip("/")
        tx, _, path = rest.partition("/")
        out.update(scheme="ar", ar_id=tx, path=("/" + path) if path else "", gateway=None)
        out.update(cls="arweave" if AR_TX.match(tx) else "broken", reason=None if AR_TX.match(tx) else "arweave-malformed-id")
        return out
    if ul.startswith(("http://", "https://")):
        try:
            sp = urlsplit(u)
            host = (sp.hostname or "").lower()
        except ValueError:
            out["reason"] = "malformed-url"
            return out
        if not host:
            out["reason"] = "malformed-url"
            return out
        out.update(scheme=sp.scheme.lower(), host=host, reg_domain=reg_domain(host), port=sp.port if _safe_port(sp) else None)
        # path-style IPFS gateway: /ipfs/<cid>[/path]  (also .../ipfs/ipfs/cid, ?arg=cid for the infura API)
        m = re.search(r"/ipfs/(?:ipfs/)?([A-Za-z0-9]+)(/[^?#]*)?", sp.path)
        if m and is_cid(m.group(1)):
            out.update(cls="ipfs", cid=m.group(1), path=(m.group(2) or "") + (("?" + sp.query) if sp.query else ""),
                       gateway=host, gateway_style="path")
            return out
        m = re.search(r"(?:^|[?&])arg=([A-Za-z0-9]+)", sp.query)
        if m and is_cid(m.group(1)) and "ipfs" in host:
            out.update(cls="ipfs", cid=m.group(1), path="", gateway=host, gateway_style="api-arg")
            return out
        m = re.match(r"^([a-z0-9]+)\.ipfs\.(.+)$", host)
        if m and is_cid(m.group(1)):
            out.update(cls="ipfs", cid=m.group(1), path=sp.path + (("?" + sp.query) if sp.query else ""),
                       gateway=m.group(2), gateway_style="subdomain")
            return out
        m = re.search(r"/ipns/([^/?#]+)(/[^?#]*)?", sp.path)
        if m:  # mutable IPNS name behind an HTTP gateway: fetched as written, counted as http (single point of failure = that host)
            out.update(cls="http", ipns=True, gateway=host, reason=None)
            return out
        if any(host == s or host.endswith("." + s) for s in AR_GATEWAY_SUFFIXES):
            seg = sp.path.lstrip("/").split("/", 1)
            if AR_TX.match(seg[0]):
                out.update(cls="arweave", ar_id=seg[0], path=("/" + seg[1]) if len(seg) > 1 else "", gateway=host)
                return out
            if host.endswith(".arweave.net") or host.endswith(".ar-io.net"):  # sandbox subdomain gateway
                out.update(cls="arweave", ar_id=None, path=sp.path, gateway=host.split(".", 1)[1], gateway_style="sandbox-subdomain")
                return out
        out.update(cls="http", reason=None)
        return out
    # no scheme
    if is_cid(u.split("/", 1)[0]) or ul.startswith("/ipfs/") or ul.startswith("ipfs/"):
        cid, path = _split_ipfs_path(u)
        if is_cid(cid):
            out.update(cls="ipfs", cid=cid, path=path, gateway=None, scheme="bare", reason=None)
            return out
    m = re.match(r"^([a-z][a-z0-9+.-]*):", ul)
    if m and m.group(1) in ("bzz", "sia", "ceramic", "ens", "hyper", "dat", "ssb", "magnet", "tor", "ftp", "storj", "walrus"):
        out.update(cls="other", scheme=m.group(1))
        return out
    if AR_TX.match(u.split("/", 1)[0]) and len(u.split("/", 1)[0]) == 43 and "." not in u.split("/", 1)[0]:
        out.update(cls="arweave", ar_id=u.split("/", 1)[0], scheme="bare", gateway=None, path="")
        return out
    out["reason"] = "no-scheme" if "." in u or "/" in u else "unrecognised-string"
    out["scheme"] = None
    return out


def _safe_port(sp):
    try:
        sp.port
        return True
    except ValueError:
        return False


# ----------------------------------------------------------------------------------------------
# Media fields
# ----------------------------------------------------------------------------------------------
def extract_media(meta):
    """From parsed metadata JSON -> list of (field, key_used, value). image / image_data / animation_url,
    with common alternative spellings used only if the standard key is absent."""
    out = []
    if not isinstance(meta, dict):
        return out
    spec = (("image", ("image", "image_url", "imageUrl", "image_uri", "imageURI", "img", "icon")),
            ("image_data", ("image_data", "imageData")),
            ("animation_url", ("animation_url", "animationUrl", "animation", "animation_uri", "video", "video_url")))
    for field, keys in spec:
        for k in keys:
            if k in meta and meta[k] not in (None, ""):
                out.append((field, k, meta[k]))
                break
    return out


def classify_media_value(field, value):
    """Classify one media field value (any JSON type)."""
    if isinstance(value, (dict, list)):
        return {"cls": "broken", "reason": "non-string-" + type(value).__name__}
    if not isinstance(value, str):
        return {"cls": "broken", "reason": "non-string-" + type(value).__name__}
    v = value.strip()
    if field == "image_data" and v[:1] == "<":
        return {"cls": "data-uri", "scheme": "raw", "mime": "svg" if "<svg" in v[:400].lower() else "html",
                "encoding": "raw-svg" if "<svg" in v[:400].lower() else "raw-html", "size": len(v.encode("utf-8", "replace"))}
    return classify_uri(v)


# ----------------------------------------------------------------------------------------------
# External references inside on-chain SVG / HTML
# ----------------------------------------------------------------------------------------------
_NS_DECL = re.compile(r"""xmlns(?::\w+)?\s*=\s*(?:"[^"]*"|'[^']*')""", re.I)
_DOCTYPE = re.compile(r"<!DOCTYPE[^>]*>", re.I | re.S)
_URL = r"(?:https?:)?//[^\s\"'<>)\\]+"
_TAG_ATTR = re.compile(r"<\s*([a-zA-Z][\w:-]*)\b([^>]*)>", re.S)
_ATTR = re.compile(r"""\b(src|href|xlink:href|poster|data|action|srcset|content)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.I)
_CSS_URL = re.compile(r"url\(\s*[\"']?(" + _URL + ")", re.I)
_IMPORT = re.compile(r"@import\s+(?:url\(\s*)?[\"']?(" + _URL + ")", re.I)
_JS_URL = re.compile(r"""(?:fetch|import|XMLHttpRequest|open|\.src\s*=|\.href\s*=|from|loadScript|loadImage|loadJSON|loadFont|loadSound)\s*\(?\s*[`"'](""" + _URL + ")", re.I)
_ANY_URL = re.compile(r"(?:https?|ipfs|ar|ipns)://[^\s\"'<>)\\`]+", re.I)
_LOAD_TAGS = {"script", "img", "image", "link", "iframe", "frame", "embed", "object", "source", "video", "audio",
              "use", "feimage", "track", "input", "style", "font-face-src", "mpath", "textpath"}


def _norm_ref(u):
    u = u.rstrip(".,;")
    if u.startswith("//"):
        u = "https:" + u
    return u


def scan_external(text):
    """Scan decoded SVG/HTML text for references to resources outside the chain.
    Returns (refs, mentions): refs = URLs in resource-loading contexts (src/href on loading tags, url(), @import,
    fetch/import, xlink:href); mentions = other http(s)/ipfs/ar URLs that appear (e.g. <a href>, text, comments).
    Namespace URIs (xmlns*, DOCTYPE) are ignored."""
    if not text:
        return [], []
    t = _DOCTYPE.sub("", _NS_DECL.sub("", text))
    refs, seen_pos = [], set()

    def add(u):
        u = _norm_ref(u)
        if u not in refs:
            refs.append(u)

    for m in _TAG_ATTR.finditer(t):
        tag, attrs = m.group(1).lower(), m.group(2)
        for a in _ATTR.finditer(attrs):
            name = a.group(1).lower()
            val = a.group(2) or a.group(3) or a.group(4) or ""
            if name == "srcset":
                cand = [p.strip().split(" ")[0] for p in val.split(",")]
            else:
                cand = [val]
            for c in cand:
                if re.match(r"^(?:https?:)?//|^(?:ipfs|ar|ipns)://", c.strip(), re.I):
                    if tag == "a" or (name == "content" and tag == "meta") or name == "action":
                        continue  # navigation, not a load
                    if name in ("src", "poster", "data", "srcset", "xlink:href") or tag in _LOAD_TAGS:
                        add(c.strip())
                        seen_pos.add(c.strip())
    for rx in (_CSS_URL, _IMPORT, _JS_URL):
        for m in rx.finditer(t):
            add(m.group(1))
            seen_pos.add(m.group(1))
    refs_set = {_norm_ref(r) for r in refs}
    mentions = []
    for m in _ANY_URL.finditer(t):
        u = _norm_ref(m.group(0))
        if u not in refs_set and u not in mentions:
            mentions.append(u)
    return refs, mentions


def ext_domains(urls):
    out = []
    for u in urls:
        try:
            h = urlsplit(u).hostname or u.split("://")[0] + "://"
        except ValueError:
            h = u[:40]
        if h not in out:
            out.append(h)
    return out


# ----------------------------------------------------------------------------------------------
# Parked / for-sale heuristics, bot walls
# ----------------------------------------------------------------------------------------------
_PARKED = re.compile(
    r"domain (?:name )?(?:is |may be |might be )?for sale|this domain (?:is|may be) (?:for sale|available)|buy this domain|"
    r"is available for (?:purchase|sale)|make an offer|parkingcrew|sedoparking|sedo\.com|hugedomains|afternic|dan\.com|"
    r"domain parking|parked (?:free|domain|at)|this (?:web ?page|domain|site) is parked|godaddy\.com/domainfind|"
    r"the domain .{1,60}has expired|domain (?:has )?expired|renew (?:now|this domain)|registrar-servers|"
    r"account suspended|bluehost.{0,40}parked|namecheap.{0,40}parking|domain default page|related searches|"
    r"this site can.t be reached|website coming soon|under construction", re.I | re.S)
_BOT = re.compile(r"just a moment|cf-chl|cf_chl|attention required|checking your browser|ddos protection by|"
                  r"enable javascript and cookies|captcha|access denied.{0,80}(?:akamai|incapsula|cloudflare)", re.I | re.S)


def looks_parked(text):
    m = _PARKED.search(text or "")
    return m.group(0)[:60] if m else None


def looks_bot_wall(text):
    m = _BOT.search(text or "")
    return m.group(0)[:60] if m else None


def is_global_ip(host):
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return None  # not an IP literal
