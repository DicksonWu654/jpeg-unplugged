"""Check every contract-source / contractURI / marketplace(opensea) claim_text is a verbatim substring of its saved raw evidence."""
import json, pathlib, sys
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "claims")); import srcscan as S
c = pd.read_csv(ROOT / "data/claims/claims.csv")
bad = []
cache = {}
for i, r in c.iterrows():
    if not isinstance(r.raw_path, str): bad.append((i, "no raw_path")); continue
    p = ROOT / r.raw_path
    if not p.exists(): bad.append((i, "raw missing")); continue
    t = r.claim_text
    if r.source_type == "contract-source":
        if t.startswith("ContractName: "): continue
        a = r.address
        if a not in cache:
            rec = S.load(a); fs = S.files_of(rec); impl = (rec.get("Implementation") or "").lower()
            if impl and S.have(impl): fs += S.files_of(S.load(impl))
            cache[a] = "\n".join(x for _, x in fs)
        ok = t in cache[a] or t.replace("\\n", "\n") in cache[a]
    else:
        raw = p.read_text(errors="replace")
        try: j = json.loads(raw)
        except Exception: j = None
        hay = raw + (json.dumps(j, ensure_ascii=False) if j is not None else "")
        if j is not None and isinstance(j, dict) and isinstance(j.get("description"), str): hay += j["description"]
        ok = t in hay or " ".join(t.split()) in " ".join(hay.split()) or json.dumps(t, ensure_ascii=False)[1:-1] in raw
        if not ok:
            import re, html
            txt = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw)).split())
            norm = lambda x: re.sub(r"\s+", " ", x.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"'))
            ok = norm(" ".join(t.split())) in norm(txt)
    if not ok: bad.append((i, "not substring"))
print(len(c), "rows;", len(bad), "failures")
print(pd.Series([b[1] for b in bad]).value_counts().to_dict())
for i, why in bad[:15]: print(why, c.loc[i, ["collection", "source_type", "claim_text"]].tolist())
pd.Series([b[0] for b in bad]).to_csv(ROOT / "data/claims/_verify_fail_idx.csv", index=False)
