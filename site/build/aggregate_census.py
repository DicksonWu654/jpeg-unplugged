#!/usr/bin/env python3
"""Compute census.json (site schema v1) from collections.json so the two files cannot drift.

  .venv/bin/python site/build/aggregate_census.py IN_collections.json OUT_census.json \
      [--snapshot-date 2026-10-21] [--snapshot-block N]

Stdlib only. See site/data/SCHEMA.md.
"""
import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone

LOC = ["data-uri", "onchain-renderer", "ipfs", "arweave", "http", "broken", "other"]
LIVE = ["alive", "degraded", "dead", "unknown"]
SURV = ["yes", "partial", "no", "unknown"]
VERD = ["holds", "partial", "fails", "unverified"]
ONCHAIN = ("data-uri", "onchain-renderer")


def tally(values, keys):
    c = Counter(values)
    unknown = set(c) - set(keys)
    if unknown:
        raise SystemExit("unexpected enum values: %s" % sorted(unknown))
    return {k: c.get(k, 0) for k in keys}


def gw_kind(host):
    h = host.lower()
    if "ipfs" in h or "pinata" in h or "dweb" in h or "nftstorage" in h or "w3s" in h:
        return "ipfs-gateway"
    if "arweave" in h or h.endswith("ar.io"):
        return "arweave-gateway"
    if "cloudfront" in h or "cdn" in h or "cloudinary" in h or "imgix" in h:
        return "cdn"
    if h.startswith("api.") or "/api" in h:
        return "api"
    return "other"


def build(doc, snapshot_date, snapshot_block, min_holders=100):
    cols = doc["collections"]
    n = len(cols)
    by_year = defaultdict(list)
    for c in cols:
        by_year[c["deploy_year"]].append(c)
    years = []
    for y in sorted(by_year):
        g = by_year[y]
        years.append({
            "year": y,
            "collections": len(g),
            "media_location": tally([c["media_class"] for c in g], LOC),
            "liveness": tally([c["liveness"] for c in g], LIVE),
            "survival": tally([c["survives_unplugged"] for c in g], SURV),
        })
    gw = defaultdict(lambda: [0, 0])
    for c in cols:
        for h in set(c.get("hardcoded_gateways") or []):
            gw[h][0] += 1
            if c["liveness"] in ("dead", "degraded"):
                gw[h][1] += 1
    gateways = sorted(
        ({"host": h, "kind": gw_kind(h), "collections": v[0], "dead_collections": v[1]} for h, v in gw.items()),
        key=lambda d: (-d["collections"], d["host"]))
    meta_on = [c for c in cols if c["metadata_class"] in ONCHAIN]
    fake = {
        "metadata_onchain": len(meta_on),
        "media_location": tally([c["media_class"] for c in meta_on], LOC),
        "http_dead": sum(1 for c in meta_on if c["media_class"] == "http" and c["liveness"] in ("dead", "degraded")),
    }
    claimed = [c for c in cols if c.get("claim")]
    reasons = Counter(c["dead_reason"] for c in cols if c["liveness"] in ("dead", "degraded") and c.get("dead_reason"))
    return {
        "schema_version": 1,
        "sample": bool(doc.get("sample", False)),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "snapshot_date": snapshot_date,
        "snapshot_block": snapshot_block,
        "criteria": {"chain": "ethereum", "min_holders": min_holders,
                     "standards": ["ERC-721", "ERC-1155"], "spam_excluded": True},
        "totals": {"collections": n,
                   "erc721": sum(1 for c in cols if c["standard"] == "ERC-721"),
                   "erc1155": sum(1 for c in cols if c["standard"] == "ERC-1155")},
        "metadata_location": tally([c["metadata_class"] for c in cols], LOC),
        "media_location": tally([c["media_class"] for c in cols], LOC),
        "liveness": tally([c["liveness"] for c in cols], LIVE),
        "dead_reasons": dict(reasons.most_common()),
        "survival": tally([c["survives_unplugged"] for c in cols], SURV),
        "by_year": years,
        "gateways": gateways,
        "fake_onchain": fake,
        "claims": {"claimed": len(claimed),
                   "verdicts": tally([c["claim"]["verdict"] for c in claimed], VERD),
                   "explicit_100": sum(1 for c in claimed if c["claim"]["strength"] == "explicit-100%")},
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("collections")
    ap.add_argument("out")
    ap.add_argument("--snapshot-date", default="2026-10-21")
    ap.add_argument("--snapshot-block", type=int, default=None)
    a = ap.parse_args()
    out = build(json.load(open(a.collections)), a.snapshot_date, a.snapshot_block)
    json.dump(out, open(a.out, "w"), indent=1)
    print("wrote", a.out, out["totals"])
