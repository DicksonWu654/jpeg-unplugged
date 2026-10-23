#!/usr/bin/env python3
"""Generate PLACEHOLDER census data (sample: true) to develop the site against. NOT real results.

  .venv/bin/python site/build/make_sample.py

Writes site/data/collections.json and site/data/census.json (via aggregate_census.build). Deterministic.
Names/addresses are obviously fake; class proportions are invented and must never be quoted.
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aggregate_census import build  # noqa: E402

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rnd = random.Random(20261021)
N = 820

def pick(weights):
    r = rnd.random() * sum(w for _, w in weights)
    for k, w in weights:
        r -= w
        if r <= 0:
            return k
    return weights[-1][0]

YEARS = [(2017, 1), (2018, 1), (2019, 2), (2020, 3), (2021, 17), (2022, 31), (2023, 19), (2024, 8), (2025, 11), (2026, 7)]
GWS = [("ipfs.io", 9), ("gateway.pinata.cloud", 6), ("cloudflare-ipfs.com", 5), ("nftstorage.link", 4),
       ("dweb.link", 3), ("arweave.net", 3), ("d1d3e8wlhx2.cloudfront.net", 2)]
DEAD_R = [("dns-nxdomain", 5), ("http-404", 6), ("gateway-not-found", 4), ("tls-error", 2), ("http-5xx", 2), ("timeout-confirmed", 2)]
CLAIMS = ["100% on-chain generative art", "Fully on-chain, forever", "Everything lives on the blockchain",
          "Entirely on-chain: no IPFS, no servers", "On-chain SVG collection"]

rows = []
for i in range(N):
    y = pick(YEARS)
    late = y >= 2022
    meta = pick([("ipfs", 38), ("http", 30), ("data-uri", 6 if late else 3), ("onchain-renderer", 9 if late else 4),
                 ("arweave", 6), ("broken", 6), ("other", 1)])
    if meta in ("data-uri", "onchain-renderer"):
        media = pick([("data-uri", 40), ("onchain-renderer", 25), ("ipfs", 12), ("http", 18), ("arweave", 3), ("broken", 2)])
    else:
        media = {"ipfs": "ipfs", "http": "http", "arweave": "arweave", "broken": "broken", "other": "other"}[meta]
        if rnd.random() < 0.15 and meta == "ipfs":
            media = "http"
    gws = []
    if meta == "ipfs" or media == "ipfs":
        if rnd.random() < 0.55:
            gws.append(pick(GWS[:5]))
    if meta == "arweave" or media == "arweave":
        if rnd.random() < 0.4:
            gws.append("arweave.net")
    if media == "http" and rnd.random() < 0.15:
        gws.append("d1d3e8wlhx2.cloudfront.net")
    if media == "http" and rnd.random() < 0.5:
        gws = list(dict.fromkeys(gws))
    onchain_both = meta in ("data-uri", "onchain-renderer") and media in ("data-uri", "onchain-renderer")
    if onchain_both:
        surv = pick([("yes", 70), ("partial", 24), ("unknown", 6)])
        live = "alive"
        reason = None
    else:
        surv = "unknown" if (meta == "other" or media == "other") and rnd.random() < 0.5 else "no"
        base = {"http": [("alive", 46), ("dead", 28), ("degraded", 10), ("unknown", 16)],
                "ipfs": [("alive", 74), ("dead", 6), ("degraded", 6), ("unknown", 14)],
                "arweave": [("alive", 88), ("dead", 1), ("degraded", 2), ("unknown", 9)],
                "broken": [("dead", 80), ("unknown", 20)],
                "other": [("alive", 60), ("unknown", 40)]}
        live = pick(base[media if media in base else "other"])
        if gws and live == "alive" and rnd.random() < 0.18:
            live = "degraded"
        reason = pick(DEAD_R) if live in ("dead", "degraded") else None
        if media == "broken" and not reason:
            reason = "tokenuri-revert"
    claim = None
    if (meta in ("data-uri", "onchain-renderer") and rnd.random() < 0.55) or rnd.random() < 0.012:
        v = "holds" if surv == "yes" else ("partial" if surv == "partial" else ("fails" if surv == "no" else "unverified"))
        claim = {
            "strength": pick([("explicit-100%", 6), ("strong", 3), ("weak", 1)]),
            "text": rnd.choice(CLAIMS),
            "source_url": "#",
            "verdict": v,
            "reason": {"holds": "metadata and media are data: URIs; renders offline",
                       "partial": "renders but loads a script from a CDN",
                       "fails": "image field is an https:// URL",
                       "unverified": "contract code not verified"}[v],
        }
    rows.append({
        "address": "0x%040x" % (0x5a3b1e00 + i),
        "name": "Sample collection %04d" % (i + 1),
        "standard": "ERC-1155" if rnd.random() < 0.28 else "ERC-721",
        "holders": int(100 * (1 + rnd.paretovariate(0.9))),
        "deploy_year": y,
        "metadata_class": meta,
        "media_class": media,
        "animation_class": None,
        "liveness": live,
        "dead_reason": reason,
        "survives_unplugged": surv,
        "hardcoded_gateways": list(dict.fromkeys(gws)),
        "media_hosts": [],
        "claim": claim,
        "evidence_url": "#",
    })

coll = {"schema_version": 1, "sample": True, "generated_at": "2026-10-21T00:00:00Z", "collections": rows}
os.makedirs(os.path.join(SITE, "data"), exist_ok=True)
json.dump(coll, open(os.path.join(SITE, "data", "collections.json"), "w"), separators=(",", ":"))
cen = build(coll, "2026-10-21", None)
cen["generated_at"] = "2026-10-21T00:00:00Z"
json.dump(cen, open(os.path.join(SITE, "data", "census.json"), "w"), indent=1)
print("sample written", cen["totals"], cen["survival"])
