"""claims: summary stats + red-flag join (claims x source_signals x contractURI). Writes data/claims/redflags.csv, prints markdown."""
import json, pathlib
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]; C = ROOT / "data/claims"
cl = pd.read_csv(C / "claimants_reviewed.csv"); sig = pd.read_parquet(C / "source_signals.parquet")
uni = pd.read_parquet(ROOT / "data/universe/collections.parquet"); uni["address"] = uni.address.str.lower()
print("rows", len(cl), "distinct addresses", cl.address.nunique(), "rows w/o address", cl.address.isna().sum())
print("claimant addresses in universe:", cl[cl.address.isin(uni.address)].address.nunique())
print(cl.groupby(["source_type", "claim_strength"]).size().unstack(fill_value=0).to_string())
best = cl.assign(r=cl.claim_strength.map({"explicit-100%/fully": 0, "on-chain-generic": 1, "storage-forever": 2, "implied": 3})).sort_values("r").drop_duplicates("address")
print("distinct addresses by best strength:\n", best.claim_strength.value_counts().to_string())
print("distinct collections (by name) w/o address:", cl[cl.address.isna()].collection.nunique())
nonimp = best[best.claim_strength != "implied"]
print("non-implied claimants with address:", len(nonimp))
# contractURI offchain
cu = {}
for line in open(C / "contracturi_results.jsonl"):
    j = json.loads(line); cu[j["address"]] = j
m = nonimp.merge(sig, on="address", how="left", suffixes=("", "_sig"))
for c in [c for c in sig.columns if sig[c].dtype == bool]:
    m[c] = m[c].fillna(False).astype(bool)
m["curi_scheme"] = m.address.map(lambda a: cu.get(a, {}).get("uri_scheme"))
m["verified_src"] = m.verified.fillna(False)
m["flag_mutable_uri"] = m.has_set_baseuri.fillna(False) | m.has_set_renderer.fillna(False)
m["flag_mutable_unfrozen"] = m.flag_mutable_uri & ~m.has_freeze_lock.fillna(False)
m["flag_http_literal_no_data"] = m.has_http_literal.fillna(False) & ~m.has_data_uri.fillna(False)
m["flag_ipfs_literal"] = m.has_ipfs_literal.fillna(False)
m["flag_no_onchain_uri_code"] = m.verified_src & ~(m.has_base64.fillna(False) | m.has_data_uri.fillna(False) | m.has_sstore2.fillna(False) | m.has_svg.fillna(False))
m["flag_proxy"] = m.is_proxy.fillna(False)
m["flag_curi_offchain"] = m.curi_scheme.isin(["http", "https", "ipfs", "ar"])
m["flag_pointer_needs_review"] = m.verified_src & ((m.flag_http_literal_no_data) | (m.tokenuri_concat_baseuri & ~m.has_data_uri & ~m.has_base64 & ~m.has_svg))
m["flag_baseuri_concat"] = m.tokenuri_concat_baseuri.fillna(False) & ~m.has_base64.fillna(False)
flags = [c for c in m.columns if c.startswith("flag_")]
m.to_csv(C / "redflags.csv", index=False, columns=["address", "collection", "holders_count", "claim_strength", "claim_text", "source_type", "verified_src", "contract_name"] + flags)
ex = m[m.claim_strength == "explicit-100%/fully"]
print("\nverified-source coverage among non-implied claimants:", int(m.verified_src.sum()), "of", len(m))
for name, d in (("all non-implied", m), ("explicit-100%/fully", ex)):
    dv = d[d.verified_src]
    print(f"\n{name}: n={len(d)}, with verified source n={len(dv)}")
    print({f: int(dv[f].sum()) for f in flags})
print("\nflag_baseuri_concat / http / mutable examples (explicit):")
print(ex[ex.flag_mutable_unfrozen | ex.flag_http_literal_no_data | ex.flag_baseuri_concat][["collection", "holders_count", "flag_mutable_unfrozen", "flag_http_literal_no_data", "flag_baseuri_concat", "flag_ipfs_literal", "flag_proxy"]].head(40).to_string())
