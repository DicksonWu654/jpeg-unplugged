"""mutability step 0: build data/mutability/targets.csv = scope (claims non-implied claimants in universe + gallery gallery + census on-chain classes).
Rerun at the end to pick up newly finished census rows. Census cap: top 600 by holders if more."""
import pandas as pd, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
CAP = 600
rank = {"explicit-100%/fully": 3, "on-chain-generic": 2, "storage-forever": 2, "implied": 1}

c = pd.read_csv(ROOT / "data/claims/claimants_reviewed.csv")
c["address"] = c.address.str.lower()
c = c[c.address.notna()]
c["r"] = c.claim_strength.map(rank)
nonimp = c[c.claim_strength != "implied"]
best = nonimp.sort_values("r", ascending=False).drop_duplicates("address")
w5 = best[best.in_universe == True][["address", "collection", "claim_strength", "claim_text", "source_type", "source_url", "holders_count"]]  # noqa: E712
w5 = w5.rename(columns={"collection": "name", "claim_strength": "w5_claim_strength", "claim_text": "w5_claim_text", "source_type": "w5_source_type", "source_url": "w5_source_url"})
w5["in_w5"] = True
# implied-only addresses are NOT in scope
g = pd.read_csv(ROOT / "data/gallery/results.csv")
g["address"] = g.contract.str.lower()
gal = g.groupby("address").agg(gallery_slugs=("slug", lambda s: ";".join(s)), gallery_tokens=("token", lambda s: ";".join(str(x) for x in s)), gallery_name=("collection", "first")).reset_index()
gal["in_gallery"] = True
cc = pd.read_parquet(ROOT / "data/census/census_collections.parquet")
cc["address"] = cc.address.str.lower()
cen = cc[cc.meta_class.isin(["data-uri", "onchain-renderer"])]
n_cen_all = len(cen)
cen = cen.sort_values("holders_count", ascending=False).head(CAP)
cen = cen[["address", "name", "holders_count", "meta_class", "media_class", "liveness"]].rename(columns={"meta_class": "census_meta_class", "media_class": "census_media_class", "liveness": "census_liveness"})
cen["in_census_onchain"] = True
t = w5.merge(gal, on="address", how="outer").merge(cen, on="address", how="outer", suffixes=("", "_cen"))
for col in ("in_w5", "in_gallery", "in_census_onchain"):
    t[col] = t[col].fillna(False).astype(bool)
t["name"] = t.name.fillna(t.gallery_name).fillna(t.name_cen)
t["holders_count"] = t.holders_count.fillna(t.holders_count_cen)
t = t.drop(columns=[c for c in t.columns if c.endswith("_cen")] + ["gallery_name"])
u = pd.read_parquet(ROOT / "data/universe/collections.parquet")
u["address"] = u.address.str.lower()
t = t.merge(u[["address", "standard", "creator", "deploy_block"]].drop_duplicates("address"), on="address", how="left")
t = t.sort_values("holders_count", ascending=False, na_position="last").reset_index(drop=True)
t.to_csv(ROOT / "data/mutability/targets.csv", index=False)
print(len(t), "targets; w5", t.in_w5.sum(), "gallery", t.in_gallery.sum(), "census", t.in_census_onchain.sum(), f"(census on-chain rows total so far {n_cen_all}, cap {CAP}; census finished rows {len(cc)})")
