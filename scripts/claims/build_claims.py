"""claims: merge claim sources into data/claims/claims.csv (one row per address x source_type x best claim).
Inputs: claims_source_lines.csv (+source_signals.parquet), contracturi_results.jsonl, web_directories.csv, web_famous.csv.
"""
import json, pathlib, re
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]
C = ROOT / "data" / "claims"
RANK = {"explicit-100%/fully": 0, "on-chain-generic": 1, "storage-forever": 2, "implied": 3}
COLS = ["address", "collection", "claim_text", "claim_strength", "source_type", "source_url", "raw_path", "retrieved_at"]

uni = pd.read_parquet(ROOT / "data/universe/collections.parquet")[["address", "name", "holders_count", "spam_suspect"]]
uni["address"] = uni.address.str.lower()
uname = dict(zip(uni.address, uni.name)); uhold = dict(zip(uni.address, uni.holders_count))
sig = pd.read_parquet(C / "source_signals.parquet")
ts = dict(zip(sig.address, sig.retrieved_at)); cname = dict(zip(sig.address, sig.contract_name))
rows = []

# 1. contract source
sl = pd.read_csv(C / "claims_source_lines.csv")
sl["rank"] = sl.strength.map(RANK)
sl["nonlib"] = ~sl.file.str.contains(r"openzeppelin|solmate|solady|/lib/|chainlink|node_modules", case=False, regex=True)
sl["isstr"] = (sl.kind == "string").astype(int)
sl = sl.sort_values(["address", "rank", "nonlib", "isstr"], ascending=[True, True, False, True])
for a, g in sl.groupby("address", sort=False):
    r = g.iloc[0]
    rows.append({"address": a, "collection": uname.get(a) or r.contract_name,
                 "claim_text": r.text, "claim_strength": r.strength, "source_type": "contract-source",
                 "source_url": f"https://etherscan.io/address/{a}#code ({r.file}:{r.line_no})",
                 "raw_path": r.raw_path, "retrieved_at": ts.get(a)})
# ContractName itself claims on-chain
for r in sig[sig.name_has_onchain].itertuples():
    rows.append({"address": r.address, "collection": uname.get(r.address) or r.contract_name,
                 "claim_text": f"ContractName: {r.contract_name}", "claim_strength": "implied", "source_type": "contract-source",
                 "source_url": f"https://etherscan.io/address/{r.address}#code", "raw_path": r.raw_path, "retrieved_at": r.retrieved_at})

# 2. contractURI
import sys
sys.path.insert(0, str(ROOT / "scripts" / "claims"))
from contracturi import sentences_with_claim
p = C / "contracturi_results.jsonl"
if p.exists():
    seen = {}
    for line in open(p):
        j = json.loads(line); seen[j["address"]] = j
    for a, j in seen.items():
        cl = sentences_with_claim(j.get("description") or "") if isinstance(j.get("description"), str) else []
        if j.get("status") == "ok" and cl:
            cl = sorted(cl, key=lambda x: RANK[x[1]])
            rows.append({"address": a, "collection": j.get("name") or uname.get(a), "claim_text": cl[0][0][:600],
                         "claim_strength": cl[0][1], "source_type": "contractURI",
                         "source_url": j["uri_head"], "raw_path": j.get("body_raw"), "retrieved_at": None})
# 2b. OpenSea public collection endpoint
import sys
sys.path.insert(0, str(ROOT / "scripts" / "claims"))
from contracturi import sentences_with_claim
p = C / "opensea_results.jsonl"
if p.exists():
    for line in open(p):
        j = json.loads(line)
        if j.get("status") != "ok": continue
        cl = sorted(sentences_with_claim(j.get("description") or ""), key=lambda x: RANK[x[1]])
        if cl:
            rows.append({"address": j["address"], "collection": j["name"], "claim_text": cl[0][0][:600], "claim_strength": cl[0][1],
                         "source_type": "marketplace", "source_url": j["source_url"], "raw_path": j["raw_path"], "retrieved_at": None})
# 3/4. web (helper scripts)
for f in ("web_directories.csv", "web_famous.csv"):
    p = C / f
    if p.exists():
        d = pd.read_csv(p)
        for r in d.to_dict("records"):
            a = r.get("address")
            r["address"] = a.lower() if isinstance(a, str) and a.startswith("0x") else None
            rows.append({k: r.get(k) for k in COLS} | {"_note": r.get("note")})

df = pd.DataFrame(rows)
neg = df[df.claim_strength == "none-found"]; neg.to_csv(C / "negative_controls.csv", index=False)
df = df[df.claim_strength != "none-found"]
if "_note" not in df: df["_note"] = None
# fill retrieved_at for contractURI from MANIFEST
man = {}
for line in open(ROOT / "data/raw/MANIFEST.jsonl"):
    try: m = json.loads(line)
    except Exception: continue
    if m.get("path"): man[m["path"]] = m["retrieved_at"]
df["retrieved_at"] = df.retrieved_at.fillna(df.raw_path.map(man))
df["holders_count"] = df.address.map(uhold)
df["in_universe"] = df.address.isin(uhold)
df["collection"] = df.collection.fillna(df.address.map(uname))
df = df.drop_duplicates(["address", "source_type", "claim_text"])
df["_r"] = df.claim_strength.map(RANK)
df = df.sort_values(["_r", "holders_count"], ascending=[True, False]).drop(columns="_r")
df.rename(columns={"_note": "note"}).to_csv(C / "claims.csv", index=False)
print(len(df), "rows;", df.address.nunique(), "distinct addresses")
print(df.groupby(["source_type", "claim_strength"]).size().unstack(fill_value=0))
