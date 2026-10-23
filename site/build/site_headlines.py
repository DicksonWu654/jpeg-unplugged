#!/usr/bin/env python3
"""Publish the site's small, aggregate-only subset of the paper's headlines.

Run after scripts/analysis/headlines.py. Never copy host-level evidence or rows.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = json.loads((ROOT / "data/analysis/headlines.json").read_text())
onchain = source["random"]["onchain"]
keys = ("truly_onchain_census", "fake_onchain_A_offchain_media_of_onchain_metadata")
# Only these public, shared gateways are needed for the explanatory chart.
gateways = {"arweave.net", "ipfs.io", "gateway.pinata.cloud", "nftstorage.link", "dweb.link"}
out = {
    "source": "data/analysis/headlines.json",
    "generated_at": source["meta"]["generated_at"],
    "random": {
        "onchain": {key: onchain[key] for key in keys},
        "exact_url": {"by_gateway_host": [
            {key: row[key] for key in ("host", "collections", "exact_unknown")}
            for row in source["random"]["exact_url"]["by_gateway_host"]
            if row["host"] in gateways
        ]},
    },
}
target = ROOT / "site/data/headlines.json"
target.write_text(json.dumps(out, indent=1) + "\n")
print("wrote", target.relative_to(ROOT), target.stat().st_size, "bytes")
