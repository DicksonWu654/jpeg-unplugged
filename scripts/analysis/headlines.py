"""Stage 2: headlines.json (random-stratum estimates with Wilson CIs, weighted variants, by-year, claims funnel)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa

META_LOCS = ["data-uri", "onchain-renderer", "ipfs", "arweave", "http", "broken", "other"]
MEDIA_LOCS = ["data-uri", "onchain-renderer", "ipfs", "arweave", "http", "broken", "none", "unresolved"]
POP = 49494
W6_ASSESSED = ["immutable", "eoa-mutable", "multisig-mutable", "dao-or-timelock-mutable"]


def counts_table(s, keys, n=None):
    n = len(s) if n is None else n
    return {k: prop((s == k).sum(), n) for k in keys}


def core_indicators(d):
    x = pd.DataFrame(index=d.index)
    x["meta_onchain"] = d.meta_onchain
    x["truly_onchain"] = d.truly_onchain
    x["fake_a"] = d.fake_a
    x["meta_ipfs"] = d.meta_loc.eq("ipfs")
    x["meta_http"] = d.meta_loc.eq("http")
    x["meta_arweave"] = d.meta_loc.eq("arweave")
    x["meta_broken"] = d.meta_loc.eq("broken")
    x["alive"] = d.liveness.eq("alive")
    x["degraded"] = d.liveness.eq("degraded")
    x["dead"] = d.liveness.eq("dead")
    x["unknown"] = d.liveness.eq("unknown")
    x["dead_or_degraded"] = d.liveness.isin(["dead", "degraded"])
    x["dead_or_degraded_or_unknown"] = d.liveness.isin(["dead", "degraded", "unknown"])
    return x.astype(float)


def summarize_stratum(d, label):
    N = len(d)
    out = {"label": label, "n": N}
    out["metadata_location"] = counts_table(d.meta_loc.fillna("other"), META_LOCS, N)
    res = d[d.media_resolved]
    out["media_location_all"] = counts_table(d.media_loc.fillna("other"), MEDIA_LOCS, N)
    out["media_location_resolved"] = {"n_resolved": len(res), **counts_table(res.media_loc, MEDIA_LOCS[:-1], len(res))}
    out["any_animation_url"] = prop(d.anim_loc.notna().sum(), N)
    onm = d[d.meta_onchain]
    out["onchain"] = {
        "metadata_onchain": prop(d.meta_onchain.sum(), N),
        "media_onchain_all": prop(d.media_onchain.sum(), N),
        "onchain_candidate_incl_external_refs": prop(d.onchain_candidate.sum(), N),
        "truly_onchain_census": prop(d.truly_onchain.sum(), N),
        "fake_onchain_A_offchain_media_of_all": prop(d.fake_a.sum(), N),
        "fake_onchain_A_offchain_media_of_onchain_metadata": prop(onm.fake_a.sum(), len(onm)),
        "fake_onchain_B_onchain_media_external_refs_of_all": prop(d.fake_b.sum(), N),
        "fake_onchain_B_of_onchain_metadata": prop(onm.fake_b.sum(), len(onm)),
        "onchain_metadata_media_split": {k: int((onm.media_loc == k).sum()) for k in MEDIA_LOCS},
        "of_onchain_metadata_n": len(onm),
        "metadata_renderer_vs_datauri": {"data-uri": int((d.meta_loc == "data-uri").sum()), "onchain-renderer": int((d.meta_loc == "onchain-renderer").sum())},
        "metadata_mixed_across_tokens": prop(d.meta_mixed.fillna(False).sum(), N),
    }
    k = {m: int((d.liveness == m).sum()) for m in ["alive", "degraded", "dead", "unknown"]}
    res_n = k["alive"] + k["degraded"] + k["dead"]
    out["liveness"] = {
        "all": counts_table(d.liveness, ["alive", "degraded", "dead", "unknown"], N),
        "unknown_excluded": {"n_resolved": res_n, **{m: prop(k[m], res_n) for m in ["alive", "degraded", "dead"]},
                             "dead_or_degraded": prop(k["dead"] + k["degraded"], res_n)},
        "bounds_dead": {"lower_unknown_alive": prop(k["dead"], N), "upper_unknown_dead": prop(k["dead"] + k["unknown"], N)},
        "bounds_dead_or_degraded": {"lower": prop(k["dead"] + k["degraded"], N), "upper": prop(k["dead"] + k["degraded"] + k["unknown"], N)},
        "bounds_alive": {"lower_unknown_dead": prop(k["alive"], N), "upper_unknown_alive": prop(k["alive"] + k["unknown"], N)},
        "alive_that_are_onchain": int((d.liveness.eq("alive") & d.meta_onchain).sum()),
    }
    off = d[~d.meta_onchain]
    ko = {m: int((off.liveness == m).sum()) for m in ["alive", "degraded", "dead", "unknown"]}
    out["liveness_offchain_metadata_only"] = {"n": len(off), **{m: prop(v, len(off)) for m, v in ko.items()},
                                              "dead_or_degraded_unknown_excluded": prop(ko["dead"] + ko["degraded"], ko["alive"] + ko["dead"] + ko["degraded"])}
    dd = d[d.liveness.isin(["dead", "degraded"])]
    out["dead_reasons"] = {
        "n_dead_or_degraded": len(dd),
        "dead_only": {k_: prop(v, N) for k_, v in d[d.liveness.eq("dead")].reason_cat.value_counts().items()},
        "dead_or_degraded": {k_: prop(v, N) for k_, v in dd.reason_cat.value_counts().items()},
        "dead_or_degraded_share_of_failures": {k_: prop(v, len(dd)) for k_, v in dd.reason_cat.value_counts().items()},
        "dead_only_soft_ipfs_arweave_not_found": prop(((d.liveness == "dead") & d.reason_cat.isin(["ipfs-not-found", "arweave-not-found"])).sum(), N),
        "dead_hard_evidence_dns_tls_http_revert_etc": prop(((d.liveness == "dead") & ~d.reason_cat.isin(["ipfs-not-found", "arweave-not-found"])).sum(), N),
        "dead_excluding_tokenuri_revert": prop(((d.liveness == "dead") & (d.reason_cat != "tokenuri-revert")).sum(), N),
        "unknown_why": {k_: int(v) for k_, v in d[d.liveness.eq("unknown")].unknown_cat.fillna("unspecified").value_counts().items()},
    }
    resc = d[d.exact_dead_content_alive]
    gwrows = []
    for h, g in d.assign(h=d.gateways_list).explode("h").dropna(subset=["h"]).groupby("h"):
        gwrows.append({"host": h, "collections": len(g), "exact_dead": int((g.liveness_exact == "dead").sum()),
                       "exact_unknown": int((g.liveness_exact == "unknown").sum()),
                       "exact_alive": int((g.liveness_exact == "alive").sum()),
                       "content_alive": int((g.liveness == "alive").sum()),
                       "content_dead_or_degraded": int(g.liveness.isin(["dead", "degraded"]).sum()),
                       "content_alive_but_exact_dead_collections": int((g.rescuable_tokens > 0).sum())})
    gwrows.sort(key=lambda r: -r["collections"])
    dh = d[d.dead_gateway_hosts != ""].assign(h=lambda x: x.dead_gateway_hosts.str.split(",")).explode("h")
    out["exact_url"] = {
        "liveness_exact": counts_table(d.liveness_exact, ["alive", "degraded", "dead", "unknown"], N),
        "content_alive_exact_dead": prop(len(resc), N),
        "content_alive_exact_dead_hosts": {h: int(v) for h, v in resc.assign(h=resc.dead_gateway_hosts.str.split(",")).explode("h").h.value_counts().items()},
        "hardcode_a_dead_gateway_any_token": prop(len(d[d.dead_gateway_hosts != ""]), N),
        "dead_gateway_hosts_collections": {h: int(v) for h, v in dh.h.value_counts().items()},
        "content_alive_exact_unknown_botwalled": prop(((d.liveness == "alive") & (d.liveness_exact == "unknown")).sum(), N),
        "collections_hardcoding_any_gateway": prop((d.gateways_list.map(len) > 0).sum(), N),
        "by_gateway_host": gwrows[:25],
    }
    return out


def weighted_views(d):
    x = core_indicators(d)
    out = {}
    w_h = d.holders.astype(float).values
    ts = d.supply_known.astype(float)
    views = {
        "holder_weighted": (np.arange(len(d)), w_h, "weights = holders_count (sum of per-collection holder slots; one wallet in k collections counts k times)"),
        "token_weighted_erc721_known_supply": (np.where((d.standard == "ERC-721") & ts.notna())[0], ts.fillna(0).values,
                                               "ERC-721 collections with a plausible total_supply (1..1e6); weights = total_supply"),
        "token_weighted_all_supply_imputed": (np.arange(len(d)), np.where(ts.notna(), ts, w_h),
                                              "all collections; unknown/implausible supply replaced by holders_count (lower bound on tokens)"),
    }
    for name, (idx, w, note) in views.items():
        sub = {"note": note, "n": int(len(idx))}
        for col in ["meta_onchain", "truly_onchain", "fake_a", "alive", "degraded", "dead", "unknown", "dead_or_degraded", "dead_or_degraded_or_unknown"]:
            sub[col] = boot_ratio(x[col].values[idx], w[idx])
        out[name] = sub
    return out


def by_year(d):
    rows = []
    yr = d.year.astype("float")
    groups = [(str(int(y)), d[yr == y]) for y in sorted(yr.dropna().unique())]
    groups.append(("<=2020", d[yr <= 2020]))
    for lab, g in groups:
        if len(g) == 0:
            continue
        x = core_indicators(g)
        r = {"year": lab, "n": len(g), "median_holders": float(g.holders.median())}
        for c in x.columns:
            r[c] = prop(int(x[c].sum()), len(g))
        res_n = int(g.liveness.isin(["alive", "degraded", "dead"]).sum())
        r["dead_or_degraded_unknown_excluded"] = prop(int(g.liveness.isin(["dead", "degraded"]).sum()), res_n)
        off = g[~g.meta_onchain]
        r["offchain_dead_or_degraded_unknown_excluded"] = prop(int(off.liveness.isin(["dead", "degraded"]).sum()),
                                                               int(off.liveness.isin(["alive", "dead", "degraded"]).sum()))
        for m in ("ipfs", "http", "arweave"):
            r["media_" + m] = prop(int(g.media_loc.eq(m).sum()), len(g))
        r["holder_weighted_dead_or_degraded"] = boot_ratio(x.dead_or_degraded.values, g.holders.astype(float).values, n_boot=500)
        r["holder_weighted_truly_onchain"] = boot_ratio(x.truly_onchain.values, g.holders.astype(float).values, n_boot=500)
        r["dead_reasons"] = {k: int(v) for k, v in g[g.liveness.isin(["dead", "degraded"])].reason_cat.value_counts().items()}
        rows.append(r)
    return rows


def funnel(f):
    cl = f[f.claim_tier.isin(["explicit", "generic", "forever"])]
    allc = pd.read_csv(DATA / "claims" / "claimants_reviewed.csv")
    allc = allc[allc.address.notna()].copy()
    allc["a"] = allc.address.str.strip().str.lower()
    rank = {"explicit-100%/fully": 3, "storage-forever": 3, "on-chain-generic": 2, "implied": 1}
    allc["r"] = allc.claim_strength.map(rank)
    best = allc.sort_values("r", ascending=False).drop_duplicates("a")
    uni = pd.read_parquet(DATA / "universe" / "collections.parquet")
    inu = set(uni.address.str.lower())
    spam = set(uni[uni.spam_suspect].address.str.lower())
    ni = best[best.r >= 2]
    out = {"definition": "Manually reviewed project-authored claims only; funnel stages concern ordinary tokenURI resolution, not truth of alternate-data storage claims.",
           "reviewed_candidate_collections": int(pd.read_csv(DATA / "claims/review_population.csv").address.nunique()),
           "w5_distinct_addresses_case_insensitive": int(allc.a.nunique()),
           "w5_non_implied_claimants": int(len(ni)), "w5_non_implied_in_universe": int(ni.a.isin(inu).sum()),
           "w5_non_implied_spam_flagged": int(ni.a.isin(spam).sum()),
           "claimants_in_census": int(len(cl)), "claimants_not_yet_in_census": int(ni.a.isin(inu).sum() - len(cl))}

    def one(sub):
        n = len(sub)
        a_ = sub[sub.meta_onchain]
        b_ = a_[a_.onchain_candidate]
        c_ok = b_.truly_onchain & (~b_.in_w4 | b_.w4_B_ok.fillna(True).astype(bool))
        c_ = b_[c_ok]
        d_ = c_[c_.w6_class_final.eq("immutable")]
        n_unas = int((~c_.w6_class_final.isin(W6_ASSESSED)).sum())
        return {"claimants": n,
                "a_tokenURI_onchain": prop(len(a_), n), "b_media_also_onchain": prop(len(b_), n),
                "c_renders_unplugged_clean": prop(len(c_), n), "c_of_which_render_tested_w4": int(c_.in_w4.sum()),
                "d_also_immutable": prop(len(d_), n),
                "c_w6_not_assessed_or_unknown": n_unas,
                "c_mutable_split": {k: int(v) for k, v in c_.w6_class_final.fillna("not-assessed").value_counts().items()},
                "failed_at": {
                    "tokenURI_offchain": int((~sub.meta_onchain & ~sub.meta_loc.isin(["broken", "other"])).sum()),
                    "tokenURI_broken_or_other": int(sub.meta_loc.isin(["broken", "other"]).sum()),
                    "media_offchain_or_unresolved": int(len(a_) - len(b_)),
                    "external_refs_or_render_broken": int(len(b_) - len(c_)),
                    "known_mutation_path": int(len(c_) - len(d_) - n_unas)},
                "live_pointer_power": {k: int(v) for k, v in c_.w6_pointer_power.fillna("none").value_counts().items()},
                "liveness_of_claimants": {k: int(v) for k, v in sub.liveness.value_counts().items()},
                "tokenURI_location": {k: int(v) for k, v in sub.meta_loc.fillna("other").value_counts().items()}}
    out["all_claimants_non_implied"] = one(cl)
    out["explicit_100"] = one(cl[cl.claim_tier == "explicit"])
    out["generic"] = one(cl[cl.claim_tier == "generic"])
    out["storage_forever"] = one(cl[cl.claim_tier == "forever"])
    out["random_stratum_claimants_unbiased_subset"] = one(cl[cl.stratum == "random"])
    out["by_stratum"] = {k: int(v) for k, v in cl.stratum.value_counts().items()}
    out["w6_class_final_of_claimants"] = {k: int(v) for k, v in cl.w6_class_final.fillna("not-assessed").value_counts().items()}
    out["claim_verdicts_site"] = {k: int(v) for k, v in cl.claim_verdict.value_counts().items()}
    r = f[f.stratum == "random"]
    nc = ~r.claim_tier.isin(["explicit", "generic", "forever"])
    out["baseline_random_nonclaimants_truly_onchain"] = prop(int(r[nc].truly_onchain.sum()), int(nc.sum()))
    return out


def main():
    f = pd.read_parquet(OUT / "collections_enriched.parquet")
    R = f[f.stratum == "random"].copy()
    T = f[f.stratum == "top"].copy()
    meta = {
        "generated_at": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "census_rows_by_stratum": {k: int(v) for k, v in f.stratum.value_counts().items()},
        "population_non_spam_collections": POP,
        "random_stratum_n": len(R),
        "random_stratum_complete": bool(len(R) == 3000),
        "census_last_finished_at": str(f.finished_at.max()),
        "estimator": "collection-weighted proportions with 95% Wilson CIs on the uniform random sample (fpc ignored, conservative: n/N=6%); "
                     "weighted views use a percentile bootstrap (2000 resamples) over collections",
        "caveats": ["unit is the collection (>=100 holders, non-spam), not the NFT",
                    "media location is unresolved for collections whose off-chain metadata could not be fetched (see media_location_all)",
                    "'truly on-chain' is census-level (metadata and all sampled media on-chain, no external loading refs); only collections also in the gallery gallery were render-tested"],
    }
    out = {"meta": meta, "random": summarize_stratum(R, "random (uniform, 3000 non-spam collections)")}
    out["random"]["weighted"] = weighted_views(R)
    out["random"]["by_year"] = by_year(R)
    out["random"]["by_standard"] = {s: {"n": int(len(g)), "truly_onchain": prop(int(g.truly_onchain.sum()), len(g)),
                                        "dead_or_degraded": prop(int(g.liveness.isin(["dead", "degraded"]).sum()), len(g))}
                                    for s, g in R.groupby("standard")}
    out["top_stratum_robustness_NOT_representative"] = summarize_stratum(T, "top by holders (partial; high-holder collections; descriptive only)")
    out["claims_funnel"] = funnel(f)
    jdump(out, OUT / "headlines.json")
    print("headlines.json written; random n=%d top n=%d" % (len(R), len(T)))
    return out


if __name__ == "__main__":
    main()
