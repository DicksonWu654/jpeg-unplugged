"""Stage 3: site/data/{collections,census}.json (+ collections_extra.json, evidence/*.json).

collections.json holds the RANDOM stratum only: the site recounts census.json from it (Data check), so mixing in the
high-holder 'top' stratum would bias every percentage. Top-stratum rows and out-of-sample claimants go to
collections_extra.json (stratum field), which the current page does not load (see docs/methods/analysis.md).
"""
import gzip
import importlib.util
import json
import csv
import re
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "export"))
from public_redaction import PublicRedactor, load_domain_hints, load_hosts

EVID_DIR = SITE / "data" / "evidence"
EVID_BUDGET = 30 * 1024 * 1024
WITHHELD = "[withheld-host]"


def withheld_hosts():
    """Load private host names for public-output redaction, when the file exists."""
    return load_hosts(Path(os.environ.get("WITHHELD_HOSTS_FILE", "withheld_hosts.csv")))


@lru_cache(maxsize=1)
def withheld_domain_hints():
    return load_domain_hints(Path(os.environ.get("WITHHELD_HOSTS_FILE", "withheld_hosts.csv")))


def redact_text(text, hosts):
    """Redact JSON values, so failure generalisation cannot erase a whole document."""
    redactor = PublicRedactor(hosts, withheld_domain_hints())
    obj = json.loads(text)
    clean = redactor.value(obj)
    # Definitions supplied by the claims generator must use public study names.
    # Keep historical schema keys stable for existing site consumers.
    if isinstance(clean, dict) and "funnel_definitions" in clean:
        def public_definitions(value):
            if isinstance(value, str):
                value = re.sub(r"\bW4\b", "gallery test", value)
                value = re.sub(r"\bW6\b", "mutation audit", value)
                return (value.replace("reviewed candidate", "reviewed candidate")
                        .replace("data/mutability/reviewed_reads/", "data/mutability/"))
            if isinstance(value, dict):
                return {key: public_definitions(item) for key, item in value.items()}
            return value
        clean = public_definitions(clean)
    count = redactor.host_values + redactor.failure_values + int(clean != obj)
    return (json.dumps(clean, separators=(",", ":"), ensure_ascii=False) if count else text), count


def write_public_json(path, obj, hosts):
    text = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    text, n = redact_text(text, hosts)
    Path(path).write_text(text)
    return n


def s(x):
    return x if isinstance(x, str) and x else None


def loc_site(x):
    return "other" if x in (None, "none", "nan") or (isinstance(x, float) and np.isnan(x)) else x


def row(r, evidence_ok):
    claim = None
    if isinstance(r.claim_verdict, str):
        claim = {"strength": r.strength_site, "text": r.claim_text_clean, "source_url": r.source_url,
                 "verdict": r.claim_verdict, "outcome": r.claim_outcome, "reason": r.claim_reason}
    dead_reason = REASON_SITE.get(r.reason_cat) if r.liveness in ("dead", "degraded") and isinstance(r.reason_cat, str) else None
    return {
        "address": r.address_c, "name": s(r.name) or "(unnamed)", "standard": r.standard,
        "holders": int(r.holders), "deploy_year": int(r.year) if pd.notna(r.year) else 0,
        "metadata_class": loc_site(r.meta_loc), "media_class": loc_site(r.media_loc),
        "animation_class": "unresolved" if r.media_loc == "unresolved" else (loc_site(r.anim_loc) if isinstance(r.anim_loc, str) else None),
        "liveness": r.liveness, "dead_reason": dead_reason, "survives_unplugged": r.survives,
        "hardcoded_gateways": list(r.gateways_list), "media_hosts": [h for h in r.http_hosts.split(",") if h] if isinstance(r.http_hosts, str) else [],
        "claim": claim,
        "evidence_url": ("data/evidence/%s.json" % r.a) if evidence_ok else None,
        "stratum": r.stratum,
    }


def evidence_summary(a, f_row):
    d = Path(RAW_CENSUS) / a
    try:
        res = json.load(gzip.open(d / "result.json.gz")) if (d / "result.json.gz").exists() else json.load(open(d / "result.json"))
    except Exception:
        return None
    fetches, rpcs = [], []
    for name, opener in (("evidence.jsonl.gz", gzip.open), ("evidence.jsonl", open)):
        p = d / name
        if p.exists():
            for line in opener(p, "rt"):
                try:
                    j = json.loads(line)
                except Exception:
                    continue
                if j.get("kind") == "rpc" and str(j.get("role", "")).startswith("eth_call"):
                    rpcs.append({k: j.get(k) for k in ("token_id", "method", "url", "status", "retrieved_at", "sha256", "bytes")})
                elif j.get("kind") == "fetch":
                    fetches.append({k: j.get(k) for k in ("role", "token_id", "url", "status", "error_kind", "verdict", "reason", "retrieved_at",
                                                          "sha256", "bytes", "content_type", "gateway", "pass")})
            break
    toks = []
    for t in res.get("tokens", []):
        u = t.get("uri_raw")
        toks.append({"token_id": t.get("token_id"), "how_found": t.get("how_found"), "called_fn": t.get("called_fn"),
                     "metadata_class": t.get("meta_class"),
                     "tokenuri": (u[:200] + ("..." if len(u) > 200 else "")) if isinstance(u, str) and not u.startswith("data:") else
                                 ("data: URI, %d chars, %s" % (len(u), t.get("meta_encoding"))) if isinstance(u, str) else None,
                     "verdict": (t.get("derived") or {}).get("liveness"), "reason": (t.get("derived") or {}).get("liveness_reason")})
    return {"address": a, "name": res.get("name"), "census_pass": res.get("pass"), "finished_at": res.get("finished_at"),
            "raw_evidence_dir": "data/raw/census/" + a + "/ (not published; evidence.jsonl.gz + bodies.zip)",
            "tokens": toks, "eth_calls": rpcs, "fetches": fetches[:60]}


def main():
    hosts_to_withhold = withheld_hosts()
    replacements = 0
    f = pd.read_parquet(OUT / "collections_enriched.parquet")
    uni = pd.read_parquet(DATA / "universe" / "collections.parquet")[["address"]]
    cs = {x.lower(): x for x in uni.address}
    f["address_c"] = f.a.map(lambda a: cs.get(a, a))
    f = f[f.stratum.isin(["random", "top"])]
    R = f[f.stratum == "random"].sort_values("a")
    # evidence for random stratum + all claimants (budgeted)
    EVID_DIR.mkdir(parents=True, exist_ok=True)
    want = pd.concat([R, f[f.claim_verdict.notna()]]).drop_duplicates("a")
    total, have = 0, set()
    for r in want.itertuples():
        ep = EVID_DIR / (r.a + ".json")
        if ep.exists():
            old = ep.read_text()
            clean, n = redact_text(old, hosts_to_withhold)
            if clean != old:
                ep.write_text(clean)
            replacements += n
            total += len(clean)
            have.add(r.a)
            continue
        ev = evidence_summary(r.a, r)
        if ev is None:
            continue
        b = json.dumps(ev, separators=(",", ":"), ensure_ascii=False)
        if total + len(b) > EVID_BUDGET:
            break
        b, n = redact_text(b, hosts_to_withhold)
        (EVID_DIR / (r.a + ".json")).write_text(b)
        replacements += n
        total += len(b)
        have.add(r.a)
    print("evidence files", len(have), "bytes", total)
    now = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    cols = [row(r, r.a in have) for r in R.itertuples()]
    for c in cols:
        c.pop("stratum")
    doc = {"schema_version": 1, "sample": False, "generated_at": now, "collections": cols}
    p = SITE / "data" / "collections.json"
    replacements += write_public_json(p, doc, hosts_to_withhold)
    print("collections.json", len(cols), p.stat().st_size)
    ex = f[(f.stratum == "top") | (f.claim_verdict.notna() & (f.stratum != "random"))].sort_values("holders", ascending=False)
    exdoc = {"schema_version": 1, "sample": False, "generated_at": now,
             "note": "NOT a random sample: census collections outside the uniform random stratum (stratum=top: descending holders, partial). Never use for headline percentages.",
             "collections": [row(r, r.a in have) for r in ex.itertuples()]}
    p2 = SITE / "data" / "collections_extra.json"
    replacements += write_public_json(p2, exdoc, hosts_to_withhold)
    print("collections_extra.json", len(exdoc["collections"]), p2.stat().st_size)
    # census.json via the site's own aggregator
    spec = importlib.util.spec_from_file_location("agg", SITE / "build" / "aggregate_census.py")
    agg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agg)
    doc2 = json.loads(p.read_text())
    # the stock aggregator does not know `unresolved`; aggregate with it folded into `other`, then patch the true counts in
    fold = json.loads(p.read_text())
    for c in fold["collections"]:
        if c["media_class"] == "unresolved":
            c["media_class"] = "other"
        if c["animation_class"] == "unresolved":
            c["animation_class"] = "other"
    census = agg.build(fold, "2026-10-21", None)
    rows = doc2["collections"]
    from collections import Counter

    def tally_u(rs):
        cn = Counter(r["media_class"] for r in rs)
        return {k: cn.get(k, 0) for k in agg.LOC + ["unresolved"]}
    census["media_location"] = tally_u(rows)
    for y in census["by_year"]:
        y["media_location"] = tally_u([r for r in rows if r["deploy_year"] == y["year"]])
    census["fake_onchain"]["media_location"] = tally_u([r for r in rows if r["metadata_class"] in agg.ONCHAIN])
    weak = {"ipfs-not-found", "arweave-not-found"}
    ff = f[(f.stratum == "random") & (f.liveness == "dead")]
    census["liveness"]["dead_strength"] = {
        "strong": int((~ff.reason_cat.isin(weak)).sum()), "weak": int(ff.reason_cat.isin(weak).sum())}
    h = json.loads((OUT / "headlines.json").read_text())
    census["sampling"] = {
        "design": "uniform random sample of non-spam ERC-721/1155 collections with >=100 holders; every share in this file is a share of the sample",
        "universe_collections_non_spam": h["meta"]["population_non_spam_collections"], "sample_size": len(cols), "seed": SEED,
        "ci": "95% Wilson intervals are in data/analysis/headlines.json", "census_complete_for_sample": h["meta"]["random_stratum_complete"],
        "media_location_note": "'other' in media_location includes collections whose off-chain metadata could not be fetched, so the media location is unresolved",
        "claims_note": "claims counts cover claimants that fall inside the random sample; the full claims funnel (all strata) is in headlines.json and collections_extra.json"}
    replacements += write_public_json(SITE / "data" / "census.json", census, hosts_to_withhold)
    print("census.json", census["totals"], census["liveness"], census["survival"])
    # Include retained evidence and optional public datasets, not just the current selection.
    redactor = PublicRedactor(hosts_to_withhold, withheld_domain_hints())
    redactor.tree(SITE / "data")
    replacements += redactor.host_values + redactor.failure_values
    print("public host/failure replacements", replacements, "withheld hosts", len(hosts_to_withhold))


if __name__ == "__main__":
    main()
