"""Stage 1: join census (+universe, claims claims, mutability mutability, gallery gallery) into one analysis frame.

Writes data/analysis/collections_enriched.parquet and data/analysis/host_events.parquet.
Never writes into data/census (census owns it); parquet files are copied to a temp file first.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa

SUPPLY_MAX = 1e6  # larger "total_supply" values are junk (6.8e25 etc.); treated as unknown


def norm_loc(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return {"no-token-found": "other"}.get(x, x)


def load_claims():
    cl = pd.read_csv(DATA / "claims" / "claims_reviewed.csv")
    cl = cl[cl.claim_valid].copy()
    cl = cl[cl.address.notna()].copy()
    cl["a"] = cl.address.str.strip().str.lower()
    rank = {"explicit-100%/fully": 4, "storage-forever": 3, "on-chain-generic": 2, "implied": 1}
    cl["rank"] = cl.claim_strength.map(rank).fillna(0).astype(int)
    stype_pref = {"marketplace": 0, "website": 1, "contractURI": 2, "contract-source": 3, "directory": 4}
    cl["sp"] = cl.source_type.map(stype_pref).fillna(9)
    bad = cl.claim_text.str.startswith("{") | cl.claim_text.str.contains("\n") | (cl.claim_text.str.len() > 300)
    cl["clean_text"] = (~bad).astype(int)
    selected = set(pd.read_csv(DATA / "claims/claimants_reviewed.csv").review_id)
    best = cl[cl.review_id.isin(selected)].copy()
    n_by = cl.groupby("a").agg(n_claim_rows=("rank", "size"), claim_sources=("source_type", lambda s: ",".join(sorted(set(s)))))
    best = best.merge(n_by, left_on="a", right_index=True)

    def excerpt(t):
        t = str(t)
        description = re.search(r'"description"\s*:\s*"([^"]+)"', t)
        if description:
            return description.group(1)[:300]
        t = re.sub(r'^\s*(?:///?|\*)\s*(?:@(?:notice|title|dev)\s*)?', '', t)
        if t.startswith("{") or len(t) > 300 or "\n" in t:
            m = re.search(r"[^.\n\"]{0,140}on-?chain[^.\n\"]{0,140}", t, flags=re.I)
            t = (m.group(0).strip() if m else t[:280].replace("\n", " "))
        return t[:300]

    best["claim_text_clean"] = best.claim_text.map(excerpt)
    best["source_url"] = [u.split(" (")[0] if isinstance(u, str) and u.startswith("http")
                          else "https://etherscan.io/address/%s#readContract" % a
                          for u, a in zip(best.source_url, best.a)]
    best["strength_site"] = best.claim_strength.map({"explicit-100%/fully": "explicit-100%", "storage-forever": "strong",
                                                     "on-chain-generic": "strong", "implied": "weak"})
    return best[["a", "claim_strength", "strength_site", "claim_text_clean", "source_url", "source_type", "collection",
                 "n_claim_rows", "claim_sources"]].rename(columns={"collection": "claim_collection_name"})


def load_w4():
    g = json.loads((SITE / "data" / "gallery.json").read_text())
    rows = []
    for it in g["items"]:
        rows.append({"a": it["contract"].lower(), "slug": it["slug"], "vB": it.get("verdict_B"), "vC": it.get("verdict_C")})
    d = pd.DataFrame(rows)
    ok = {"identical", "a-blank"}
    agg = d.groupby("a").agg(w4_tokens=("slug", "size"), w4_slugs=("slug", lambda s: ",".join(s)),
                             w4_B_ok=("vB", lambda s: all(v in ok for v in s)),
                             w4_B_verdicts=("vB", lambda s: ",".join(sorted(set(map(str, s))))),
                             w4_C_ok=("vC", lambda s: all(v in ok for v in s)))
    return agg


def load_w6():
    m = pd.read_csv(DATA / "mutability" / "mutability.csv")
    m["a"] = m.address.str.lower()
    keep = ["a", "class_final", "class_direct", "pointer_power", "owner_simple", "upgradeable", "claim_contradicted",
            "repointable_one_account", "claim_repointable_one_account", "claim_outcome",
            "claim_contradicted_strong", "immutable_but_offchain_pointer"]
    keep = [k for k in keep if k in m.columns]
    return m[keep].rename(columns={k: "w6_" + k for k in keep if k != "a"})


def main():
    census = read_parquet_safe(DATA / "census" / "census_collections.parquet")
    tokens = read_parquet_safe(DATA / "census" / "census_tokens.parquet")
    uni = pd.read_parquet(DATA / "universe" / "collections.parquet")
    uni["a"] = uni.address.str.lower()
    census["a"] = census.address.str.lower()
    tokens["a"] = tokens.address.str.lower()
    # only collections that have a finished collection row and tokens
    census = census.drop_duplicates("a", keep="last")

    u = uni[["a", "deploy_year", "total_supply", "is_ens_or_infra", "is_proxy", "is_minimal_proxy_clone", "contract_factory",
             "is_verified", "symbol"]].rename(columns={"deploy_year": "deploy_year_u", "total_supply": "total_supply_u",
                                                       "is_verified": "verified_u"})
    f = census.merge(u, on="a", how="left")
    f["holders"] = f.holders_count.astype("Int64")
    f["year"] = f.deploy_year.fillna(f.deploy_year_u).astype("Int64")
    ts = pd.to_numeric(f.total_supply_u, errors="coerce")
    ts = ts.where((ts >= 1) & (ts <= SUPPLY_MAX))
    f["supply_known"] = ts
    f["stratum"] = f.sample_stratum

    # ---- locations -------------------------------------------------------------------------------
    f["meta_loc"] = f.meta_class.map(norm_loc)
    f["meta_onchain"] = f.meta_loc.isin(ONCHAIN)
    src = f.media_class_source
    mc = f.media_class.map(norm_loc)
    unresolved = (mc == "none") & src.isna()
    f["media_loc"] = np.where(unresolved, "unresolved", mc)
    f["anim_loc"] = f.anim_class.map(norm_loc)
    f["media_resolved"] = ~unresolved
    f["media_onchain"] = f.media_loc.isin(ONCHAIN)
    anim_off = f.anim_loc.isin(OFFCHAIN)
    f["any_media_offchain"] = f.media_loc.isin(OFFCHAIN) | anim_off
    f["truly_onchain"] = f.onchain_candidate_clean.fillna(False).astype(bool)
    f["onchain_candidate"] = f.onchain_candidate.fillna(False).astype(bool)
    # fake on-chain A: metadata on-chain but some media field off-chain
    f["fake_a"] = f.meta_onchain & f.any_media_offchain
    # fake on-chain B: metadata + media on-chain but loads an external resource
    f["fake_b"] = f.meta_onchain & f.media_onchain & f.has_external_refs.fillna(False).astype(bool) & ~f.any_media_offchain

    # ---- tokens -> reasons, hosts, exact-gateway evidence ----------------------------------------
    t = tokens[tokens.a.isin(f.a)].copy()
    t["meta_cat"] = [reason_cat(r, c) for r, c in zip(t.meta_verdict_reason, t.meta_class)]
    t["img_cat"] = [reason_cat(r, c) for r, c in zip(t.image_reason, t.image_class)]

    dead_t = t[t.liveness == "dead"]
    deg_t = t[t.liveness == "degraded"]
    from collections import defaultdict
    cats = defaultdict(list)
    for a_, c_ in zip(dead_t.a, dead_t.meta_cat):
        cats[a_].append(c_)
    deg_cats = defaultdict(list)
    for a_, c_ in zip(deg_t.a, deg_t.img_cat):
        deg_cats[a_].append(c_)
    rs = {a_: pick_reason(cats[a_] if cats.get(a_) else deg_cats.get(a_, [])) for a_ in set(cats) | set(deg_cats)}
    f["reason_cat"] = f.a.map(rs)
    f.loc[~f.liveness.isin(["dead", "degraded"]), "reason_cat"] = None
    unk = defaultdict(list)
    u_ = t[t.liveness == "unknown"]
    for a_, mv, mr, mc_, iv, ir, ic_ in zip(u_.a, u_.meta_verdict, u_.meta_verdict_reason, u_.meta_class, u_.image_verdict, u_.image_reason, u_.image_class):
        if mv == "unknown":
            unk[a_].append(reason_cat(mr, mc_))
        if iv == "unknown":
            unk[a_].append(reason_cat(ir, ic_))
    f["unknown_cat"] = f.a.map({a_: pick_reason(v) for a_, v in unk.items()})
    f.loc[f.liveness != "unknown", "unknown_cat"] = None

    # tokens that are alive by content but whose hard-coded gateway is dead (exact URL dead, content on IPFS/Arweave)
    def dead_gw(row_state):
        return isinstance(row_state, str) and row_state.startswith("dead:")
    t["meta_gw_dead"] = t.meta_hardcoded_gateway_state.map(dead_gw)
    t["img_gw_dead"] = t.image_hardcoded_gateway_state.map(dead_gw)
    t["rescuable"] = (t.meta_gw_dead | t.img_gw_dead) & (t.liveness == "alive")
    t["gw_botwalled"] = (t.meta_hardcoded_gateway_state == "bot-walled") | (t.image_hardcoded_gateway_state == "bot-walled")
    gw = t.groupby("a").agg(n_tokens=("token_id", "size"), rescuable_tokens=("rescuable", "sum"),
                            gw_dead_tokens=("meta_gw_dead", "sum"), botwalled_tokens=("gw_botwalled", "sum"))
    f = f.merge(gw, left_on="a", right_index=True, how="left")
    f["exact_dead_content_alive"] = f.rescuable_tokens.fillna(0) > 0

    dgh = defaultdict(set)
    for a_, h, st in zip(t.a, t.meta_gateway, t.meta_hardcoded_gateway_state):
        if dead_gw(st) and isinstance(h, str):
            dgh[a_].add(h)
    for a_, h, st in zip(t.a, t.image_gateway, t.image_hardcoded_gateway_state):
        if dead_gw(st) and isinstance(h, str):
            dgh[a_].add(h)
    f["dead_gateway_hosts"] = f.a.map({k: ",".join(sorted(v)) for k, v in dgh.items()}).fillna("")
    hh = defaultdict(set)
    for ccol, hcol in (("meta_class", "meta_host"), ("image_class", "image_host"), ("anim_class", "anim_host")):
        for a_, c_, h_ in zip(t.a, t[ccol], t[hcol]):
            if c_ == "http" and isinstance(h_, str):
                hh[a_].add(h_)
    f["http_hosts"] = f.a.map({k: ",".join(sorted(v)) for k, v in hh.items()}).fillna("")
    f["gateways_list"] = f.hardcoded_gateways.fillna("").map(lambda s: [x for x in s.split(",") if x])

    # ---- host events (for dead_hosts.csv) ---------------------------------------------------------
    ev = []
    cols_by_role = {
        "metadata": ("meta_class", "meta_host", "meta_reg_domain", "meta_gateway", "meta_verdict_exact", "meta_verdict_reason", "meta_hardcoded_gateway_state"),
        "image": ("image_class", "image_host", "image_reg_domain", "image_gateway", "image_verdict_exact", "image_reason", "image_hardcoded_gateway_state"),
        "animation": ("anim_class", "anim_host", None, "anim_gateway", "anim_verdict", "anim_reason", None),
    }
    for role, (cc, hc, rc, gc, vc, reasc, sc) in cols_by_role.items():
        sub = t[t[cc].isin(["http", "ipfs", "arweave"])]
        for r in sub.itertuples(index=False):
            d = r._asdict()
            cls = d[cc]
            verdict = d[vc]
            if cls == "http":
                host, reg, kind = d[hc], (d[rc] if rc else None), "http-origin"
            else:
                host, reg, kind = d[gc], None, ("ipfs-gateway" if cls == "ipfs" else "arweave-gateway")
                if not isinstance(host, str):
                    continue  # ipfs:// / ar:// URIs hardcode no gateway
            if not isinstance(host, str):
                continue
            ev.append((d["a"], role, cls, kind, host, reg if isinstance(reg, str) else None, verdict,
                       reason_cat(d[reasc], cls) if verdict == "dead" else None,
                       d[sc] if sc else None))
    he = pd.DataFrame(ev, columns=["a", "role", "cls", "kind", "host", "reg_domain", "verdict", "reason_cat", "gw_state"])
    he = he.merge(f[["a", "stratum", "holders", "name", "year"]], on="a", how="left")

    # ---- survival (site schema) -------------------------------------------------------------------
    w4 = load_w4()
    f = f.merge(w4, left_on="a", right_index=True, how="left")
    f["in_w4"] = f.w4_tokens.notna()
    surv = np.where(f.truly_onchain & (~f.in_w4 | f.w4_B_ok.fillna(True).astype(bool)), "yes", None)
    surv = pd.Series(surv, index=f.index, dtype=object)
    partial = (f.onchain_candidate & ~f.truly_onchain) | (f.truly_onchain & f.in_w4 & ~f.w4_B_ok.fillna(True).astype(bool)) | \
              (f.meta_onchain & f.media_loc.eq("none") & f.media_resolved) | (f.meta_mixed.fillna(False) & f.meta_onchain)
    surv[surv.isna() & partial] = "partial"
    no = f.meta_loc.isin(["ipfs", "arweave", "http", "broken"]) | (f.meta_onchain & f.any_media_offchain) | f.media_loc.eq("broken")
    surv[surv.isna() & no] = "no"
    surv[surv.isna()] = "unknown"
    f["survives"] = surv

    # ---- claims claims and mutability mutability ---------------------------------------------------------------
    cl = load_claims()
    f = f.merge(cl, on="a", how="left")
    f["claim_tier"] = np.select([f.claim_strength.eq("explicit-100%/fully"),
                                 f.claim_strength.eq("storage-forever"),
                                 f.claim_strength.eq("on-chain-generic"), f.claim_strength.eq("implied")],
                                ["explicit", "forever", "generic", "implied"], default="")
    w6 = load_w6()
    f = f.merge(w6, on="a", how="left")

    # Storage statements are scored against their wording and alternate data paths.
    # Neither an off-chain pointer nor a live mutation key alone is a false claim.
    outcomes = pd.read_csv(DATA / "claims/claim_outcomes.csv").set_index("address")
    for field in ("claim_outcome", "claim_verdict", "claim_reason", "outcome_evidence"):
        f[field] = f.a.map(outcomes[field])

    # tidy columns
    f.to_parquet(OUT / "collections_enriched.parquet", index=False)
    he.to_parquet(OUT / "host_events.parquet", index=False)
    print("frame", f.shape, f.stratum.value_counts().to_dict(), "host events", len(he))
    return f, he, t


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    main()
