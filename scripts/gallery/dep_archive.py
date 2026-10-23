"""Build data/dep-archive/ from the condition-A request logs.

For every external URL an artwork requested successfully in condition A we download it once (polite client), store it under
data/dep-archive/files/ and record url, sha256, size, content-type, HTTP status, retrieval time and which gallery items reference it
in data/dep-archive/MANIFEST.json.  An entry is `archived: true` (served in condition C) when it is a *declared dependency*:
  - a script / stylesheet / font (a library the artwork pulls in), or
  - its URL appears as a literal in the artwork document the chain produced.
Runtime content fetches (API JSON, images computed at run time) are recorded with archived=false: an archive of declared
dependencies cannot resurrect content, so those stay broken in C by design.
Usage: dep_archive.py [--refresh]
"""
import hashlib, json, pathlib, re, sys, time, urllib.request, urllib.error
ROOT = pathlib.Path(__file__).resolve().parents[2]
GAL, ARCH = ROOT / "data" / "gallery", ROOT / "data" / "dep-archive"
BASE = "https://onchain.invalid/"
UA = "nft-unplugged-research/0.1 (dependency archive; contact: research)"
LIB_TYPES = {"script", "stylesheet", "font"}

def main():
    (ARCH / "files").mkdir(parents=True, exist_ok=True)
    mf = ARCH / "MANIFEST.json"
    old = {e["url"]: e for e in json.loads(mf.read_text())["entries"]} if mf.exists() and "--refresh" not in sys.argv else {}
    refs = {}
    for rl in sorted(GAL.glob("*/requests_A.json")):
        slug = rl.parent.name
        meta = json.loads((rl.parent / "meta.json").read_text())
        art = (rl.parent / meta["artwork_file"]).read_text(errors="replace")
        for r in json.loads(rl.read_text()):
            u = r["url"]
            if u.startswith(BASE) or u.startswith("data:") or not u.startswith("http"): continue
            e = refs.setdefault(u, {"url": u, "slugs": set(), "types": set(), "literal_in": set(), "a_status": set()})
            e["slugs"].add(slug); e["types"].add(r["type"]); e["a_status"].add(r.get("status"))
            if u in art: e["literal_in"].add(slug)
    entries = []
    for u, e in sorted(refs.items()):
        o = old.get(u)
        if o and o.get("sha256") is not None and o.get("file"):
            ent = o
        else:
            ent = {"url": u, "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            try:
                req = urllib.request.Request(u, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=60) as r:
                    b = r.read(8_000_000); ent["http_status"] = r.status; ent["content_type"] = r.headers.get("content-type", "application/octet-stream")
                ent["sha256"] = hashlib.sha256(b).hexdigest(); ent["size"] = len(b)
                fn = f"{ent['sha256'][:12]}_{re.sub(r'[^A-Za-z0-9._-]', '_', u.split('?')[0].rstrip('/').split('/')[-1])[:60]}"
                (ARCH / "files" / fn).write_bytes(b); ent["file"] = fn
            except Exception as ex:  # noqa
                ent.update(http_status=getattr(ex, "code", None), error=str(ex)[:200], sha256=None, file=None)
            time.sleep(0.4)
        ent.update(referenced_by=sorted(e["slugs"]), resource_types=sorted(e["types"]), declared_literal_in=sorted(e["literal_in"]),
                   kind="library" if e["types"] & LIB_TYPES else "content")
        ent["archived"] = bool(ent.get("sha256")) and (ent["kind"] == "library" or bool(ent["declared_literal_in"]))
        entries.append(ent)
    mf.write_text(json.dumps({"built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "policy": __doc__, "entries": entries}, indent=1))
    print(len(entries), "urls;", sum(1 for e in entries if e["archived"]), "archived;", sum(1 for e in entries if e.get("error")), "fetch errors")
    for e in entries: print(("ARCH " if e["archived"] else "skip "), e["url"][:110], e.get("http_status"), e.get("size"), e["referenced_by"][:3])

if __name__ == "__main__":
    main()
