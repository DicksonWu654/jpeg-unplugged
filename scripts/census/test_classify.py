"""Run: .venv/bin/python -I scripts/census/test_classify.py   (plain asserts; no pytest needed)"""
import base64, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from classify import *

Q = "QmeSjSinHpPnmXmspMjwiXyN6zS4E9zccariGR3jxcaWtq"
B = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
TX = "a" * 43
c = classify_uri
assert c(f"ipfs://{Q}/1")["cls"] == "ipfs" and c(f"ipfs://{Q}/1")["path"] == "/1"
assert c(f"ipfs://ipfs/{Q}")["cid"] == Q
assert c("ipfs://Qmbad")["cls"] == "broken"
r = c(f"https://ipfs.io/ipfs/{Q}/5.json")
assert r["cls"] == "ipfs" and r["gateway"] == "ipfs.io" and r["path"] == "/5.json", r
r = c(f"https://{B}.ipfs.dweb.link/1.json")
assert r["cls"] == "ipfs" and r["gateway"] == "dweb.link" and r["gateway_style"] == "subdomain", r
assert c(f"https://gateway.pinata.cloud/ipfs/{Q}")["gateway"] == "gateway.pinata.cloud"
assert c(f"/ipfs/{Q}")["cls"] == "ipfs" and c(Q)["cls"] == "ipfs" and c(Q)["scheme"] == "bare"
assert c(f"ar://{TX}/1")["cls"] == "arweave"
r = c(f"https://arweave.net/{TX}")
assert r["cls"] == "arweave" and r["gateway"] == "arweave.net"
assert c("https://arweave.net/graphql")["cls"] == "http"
r = c("https://api.example.co.uk/token/1")
assert r["cls"] == "http" and r["reg_domain"] == "example.co.uk", r
assert c("https://foo.herokuapp.com/x")["reg_domain"] == "foo.herokuapp.com"
assert c("")["reason"] == "empty" and c("   ")["cls"] == "broken"
assert c("ipns://k51qzi5uqu5abc")["cls"] == "other"
assert c("not a uri")["cls"] == "broken"
# data URIs
j = json.dumps({"name": "x", "image": "data:image/svg+xml;base64,PHN2Zy8+"})
for u, enc in ((  "data:application/json;base64," + base64.b64encode(j.encode()).decode(), "base64"),
                ("data:application/json;utf8," + j, "plain"),
                ("data:application/json," + __import__("urllib.parse").parse.quote(j), "percent"),
                ("data:text/plain;charset=utf-8," + j, "utf8")):
    r = c(u)
    assert r["cls"] == "data-uri", (u, r)
    d = parse_data_uri(u)
    assert json.loads(d["payload"])["name"] == "x", (u, d["encoding"])
assert c("data:application/json;base64,!!!")["cls"] == "broken"
assert c('{"name":"raw"}')["cls"] == "data-uri" and c("<svg xmlns='x'/>")["encoding"] == "raw-svg"
r = c("data:application/json;base64,{\"a\":1}")
assert r["cls"] == "data-uri" and r["encoding"] == "raw-mislabeled-base64", r
# {id}
assert substitute_id("https://x/{id}.json", 255) == "https://x/" + "0" * 62 + "ff.json"
# media
m = {"name": "n", "image": f"ipfs://{Q}", "animation_url": "https://a.b/x.mp4", "image_data": "<svg/>"}
f = extract_media(m)
assert [x[0] for x in f] == ["image", "image_data", "animation_url"]
assert classify_media_value("image_data", "<svg xmlns='x'/>")["cls"] == "data-uri"
assert classify_media_value("image", {"a": 1})["cls"] == "broken"
# external refs
svg = '''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><style>@import url('https://fonts.googleapis.com/css?family=X');
@font-face{src:url(https://cdn.x.com/f.woff)}</style><image href="https://ipfs.io/ipfs/Qm1"/><a href="https://twitter.com/foo"><text>t</text></a>
<script src="//cdnjs.cloudflare.com/ajax/libs/p5.js"></script></svg>'''
refs, men = scan_external(svg)
assert "https://fonts.googleapis.com/css?family=X" in refs and "https://cdn.x.com/f.woff" in refs, refs
assert "https://ipfs.io/ipfs/Qm1" in refs and "https://cdnjs.cloudflare.com/ajax/libs/p5.js" in refs, refs
assert "https://twitter.com/foo" in men and "https://twitter.com/foo" not in refs
assert scan_external('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>') == ([], [])
assert looks_parked("<html>This domain is for sale!</html>") and not looks_parked('{"name":"a"}')
assert sniff(b"\x89PNG\r\n\x1a\nxxxx") == "png" and sniff(b'  <?xml version="1.0"?><svg') == "svg" and sniff(b"<!DOCTYPE html><html>") == "html"
print("all classify tests passed")
r = classify_uri("ipfs://https://ipfs.io/ipfs/" + Q + "/252")
assert r["cls"] == "ipfs" and r["gateway"] == "ipfs.io" and r["fetch_uri"].startswith("https://ipfs.io"), r
print("quirk test ok")
