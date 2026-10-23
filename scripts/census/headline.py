#!/usr/bin/env python3
"""Early headline numbers from data/census/census_collections.parquet (random stratum = unbiased sample)."""
import sys
import pandas as pd
pd.set_option("display.width", 200)
c = pd.read_parquet("data/census/census_collections.parquet")
t = pd.read_parquet("data/census/census_tokens.parquet")
r = c[c.sample_stratum == "random"].copy()
print("collections by stratum:", c.sample_stratum.value_counts().to_dict(), "| random with pass 2 done:", int((r["pass"] == 2).sum()), "of", len(r))
def pct(s):
    return (s.value_counts(normalize=True) * 100).round(1).to_dict()
print("\nMETADATA class (random):", pct(r.meta_class))
print("MEDIA (image) class (random):", pct(r.media_class))
print("LIVENESS content-level:", pct(r.liveness))
print("LIVENESS exact URL:", pct(r.liveness_exact))
r["onchain_meta"] = r.meta_class.isin(["data-uri", "onchain-renderer"])
print("\nmetadata on-chain: %.1f%% | onchain candidate (meta+all media on-chain): %.1f%% | ... with no external refs: %.1f%%" %
      (r.onchain_meta.mean() * 100, r.onchain_candidate.mean() * 100, r.onchain_candidate_clean.mean() * 100))
print("on-chain JSON but media off-chain:", round(((r.onchain_meta) & (~r.onchain_candidate)).mean() * 100, 1), "%")
print("hardcoded gateway present: %.1f%%" % (r.hardcoded_gateways.notna().mean() * 100))
gw = r.hardcoded_gateways.dropna().str.split(",").explode().value_counts().head(12)
print("top hardcoded gateways (collections):", gw.to_dict())
print("\nBy deploy year (random): n, %meta onchain, %candidate onchain, %ipfs, %http, %alive, %dead+degraded")
g = r.groupby("deploy_year")
tab = pd.DataFrame({"n": g.size(), "onchain_meta%": g.onchain_meta.mean() * 100, "onchain_cand%": g.onchain_candidate.mean() * 100,
                    "ipfs%": g.apply(lambda d: (d.meta_class == "ipfs").mean() * 100), "http%": g.apply(lambda d: (d.meta_class == "http").mean() * 100),
                    "alive%": g.apply(lambda d: (d.liveness == "alive").mean() * 100), "dead|degr%": g.apply(lambda d: d.liveness.isin(["dead", "degraded"]).mean() * 100),
                    "unknown%": g.apply(lambda d: (d.liveness == "unknown").mean() * 100)}).round(1)
print(tab.to_string())
print("\nTop liveness reasons (tokens, random):")
rt = t[t.address.isin(r.address)]
print(rt[rt.liveness.isin(["dead", "degraded", "unknown"])].liveness_reason.value_counts().head(15).to_string())
print("\nDead hosts (metadata), most common reg_domain with NXDOMAIN-type dead reasons:")
dd = rt[(rt.meta_verdict == "dead")]
print(dd.groupby(["meta_reg_domain", "meta_verdict_reason"]).size().sort_values(ascending=False).head(15).to_string())
print("\ngas-cap suspected collections:", int((c.n_gas_cap_suspected > 0).sum()), "of", len(c))
