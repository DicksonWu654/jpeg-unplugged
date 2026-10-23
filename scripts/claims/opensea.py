"""claims step 2b: OpenSea public collection endpoint (no key; header x-ratelimit-limit 120) -> description claims.
Slug is guessed from the collection name and VERIFIED by requiring the address in the response's contracts[].
Usage: opensea.py NAMES_CSV(address,name)  [limit]   Raw: data/raw/opensea-collections/<slug>.json
"""
import json, pathlib, re, sys, time, urllib.request, urllib.error
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib")); sys.path.insert(0, str(ROOT / "scripts" / "claims"))
import rawfetch as rf
from contracturi import sentences_with_claim
OUT = ROOT / "data/claims/opensea_results.jsonl"
UA = {"User-Agent": "Mozilla/5.0 (nft-unplugged-research)"}
last = [0.0]

def slugs(name):
    n = re.sub(r"[^a-z0-9 ]+", " ", name.lower().replace("&", " and ")).split()
    if not n: return []
    c = ["-".join(n), "".join(n)]
    if n[0] == "the": c += ["-".join(n[1:])]
    return list(dict.fromkeys(c))

def get(slug):
    p = rf._cached("opensea-collections", slug, "json")
    if p: return json.loads(p.read_bytes()), str(p.relative_to(ROOT))
    for k in range(3):
        w = last[0] + 1.0 - time.time()
        if w > 0: time.sleep(w)
        last[0] = time.time()
        url = f"https://api.opensea.io/api/v2/collections/{slug}"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                b = r.read()
            p = rf._save("opensea-collections", slug, "json", b, {"url": url, "method": "GET", "status": 200})
            return json.loads(b), str(p.relative_to(ROOT))
        except urllib.error.HTTPError as e:
            if e.code == 404: return None, None
            if e.code == 429: time.sleep(20 * (k + 1)); continue
            return None, None
        except Exception: time.sleep(3)
    return None, None

if __name__ == "__main__":
    d = pd.read_csv(sys.argv[1]); lim = int(sys.argv[2]) if len(sys.argv) > 2 else len(d)
    done = set()
    if OUT.exists(): done = {json.loads(l)["address"] for l in open(OUT)}
    n = 0
    with open(OUT, "a") as f:
        for a, name in zip(d.address, d.name):
            a = str(a).lower()
            if a in done or not isinstance(name, str): continue
            n += 1
            if n > lim: break
            rec = {"address": a, "name": name, "status": "no-slug-match"}
            for s in slugs(name):
                j, rp = get(s)
                if j and any(c.get("address", "").lower() == a for c in j.get("contracts", [])):
                    desc = j.get("description") or ""
                    rec = {"address": a, "name": j.get("name"), "slug": s, "status": "ok", "description": desc,
                           "claims": sentences_with_claim(desc), "raw_path": rp, "source_url": f"https://opensea.io/collection/{s}"}
                    break
            f.write(json.dumps(rec) + "\n"); f.flush()
            if n % 100 == 0: print("progress", n, flush=True)
