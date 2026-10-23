"""Copy offline-embeddable artwork documents + thumbnails into site/gallery-assets/ and write manifest.json.
  <slug>.unplugged.<ext>  : the document assembled from chain bytes only (condition B) -- the site's 'unplug the internet' toggle loads this
  <slug>.archive.html     : only for items whose artwork declares external libraries: libraries inlined from data/dep-archive (condition C)
  <slug>_A.jpg/_B.jpg/_C.jpg : 400px thumbnails of the three conditions"""
import json, pathlib, re, shutil
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parents[2]
GAL, ARCH, OUT = ROOT / "data/gallery", ROOT / "data/dep-archive", ROOT / "site/gallery-assets"
OUT.mkdir(parents=True, exist_ok=True)
arch = {e["url"]: e for e in json.loads((ARCH / "MANIFEST.json").read_text())["entries"] if e.get("archived")}
man = []
total = 0
for md in sorted(GAL.glob("*/meta.json")):
    d = md.parent; slug = d.name
    if not (d / "result.json").exists(): continue
    meta = json.loads(md.read_text()); res = json.loads((d / "result.json").read_text())
    ext = pathlib.Path(meta["artwork_file"]).suffix
    shutil.copy(d / meta["artwork_file"], OUT / f"{slug}.unplugged{ext}")
    ent = dict(slug=slug, collection=meta["collection"], doc_type=meta["doc_type"], unplugged=f"{slug}.unplugged{ext}", unplugged_bytes=meta["artwork_bytes"],
               verdict_B=res["metrics"]["B"]["verdict"], verdict_C=res["metrics"].get("C", {}).get("verdict"), archive=None)
    text = (d / meta["artwork_file"]).read_text(errors="replace")
    used = [u for u in arch if u in text]
    if used and ext == ".html":
        out = text
        for u in used:
            body = (ARCH / "files" / arch[u]["file"]).read_text(errors="replace").replace("</script", "<\\/script")
            tag = re.compile(r"<script[^>]*\ssrc=[\"']" + re.escape(u) + r"[\"'][^>]*>\s*</script>", re.I)
            repl = f"<script>/* inlined from archive: {u} sha256={arch[u]['sha256']} */\n{body}\n</script>"
            out, n = tag.subn(lambda m: repl, out)
            if n == 0:   # URL referenced some other way (e.g. created by script): leave untouched, note it
                ent.setdefault("archive_unresolved", []).append(u)
        (OUT / f"{slug}.archive.html").write_text(out)
        ent["archive"] = f"{slug}.archive.html"; ent["archive_bytes"] = len(out.encode()); ent["archive_urls"] = used
    for c in "ABC":
        p = d / f"shot_{c}.png"
        if p.exists():
            im = Image.open(p).convert("RGB"); im.thumbnail((400, 400)); im.save(OUT / f"{slug}_{c}.jpg", quality=78)
    man.append(ent)
(OUT / "manifest.json").write_text(json.dumps(man, indent=1))
tot = sum(f.stat().st_size for f in OUT.iterdir())
print(len(man), "items;", round(tot / 1e6, 1), "MB total in", OUT)
print("largest:", sorted(((f.stat().st_size, f.name) for f in OUT.iterdir() if not f.name.endswith(".jpg")), reverse=True)[:6])
