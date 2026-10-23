#!/usr/bin/env python3
"""Build only site/data/mutability.json from the saved reviewed claims and mutation audit.

Run with .venv/bin/python site/build/mutability_json.py. No network or other outputs.
Storage outcomes and live pointer control are independent. Fail on stale joins/counts
rather than publish mixed review populations. Every timeline entry comes from setter_events.csv.
"""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/mutability"
OUT = ROOT / "site/data/mutability.json"
REPO = "https://github.com/DicksonWu654/jpeg-unplugged"
CLASSES = ["immutable", "dao-or-timelock-mutable", "multisig-mutable", "eoa-mutable", "unknown"]


def read_csv(path):
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def counts(rows):
    vc = Counter(r["class_final"] for r in rows)
    assert set(vc) <= set(CLASSES), "Unknown mutation class"
    return {**{c: vc[c] for c in CLASSES}, "total": len(rows)}


def yes(value):
    return str(value).lower() == "true"


df = read_csv(D / "mutability.csv")
ev = read_csv(D / "setter_events.csv")
review = read_csv(ROOT / "data/claims/claims_reviewed.csv")
outcomes = read_csv(ROOT / "data/claims/claim_outcomes.csv")
summary = json.loads((ROOT / "data/analysis/claims_summary.json").read_text())
metrics = summary["metrics"]


def metric(key, computed):
    value = metrics[key]["value"]
    assert value == computed, f"Stale reviewed metric {key}: {value} != {computed}"
    return value


by_address = {r["address"]: r for r in df}
by_review_id = {r["review_id"]: r for r in review}
claimants = [r for r in df if yes(r["in_w5"])]
assert len({r["address"] for r in outcomes}) == len(outcomes), "Duplicate claim outcomes"
assert {r["address"] for r in claimants} == {r["address"] for r in outcomes}, "Stale claimant membership"
for outcome in outcomes:
    quote = by_review_id[outcome["selected_review_id"]]
    assert yes(quote["claim_valid"]) and quote["address"] == outcome["address"], "Unreviewed selected quote"
    assert by_address[outcome["address"]]["claim_outcome"] == outcome["claim_outcome"], "Stale joined outcome"

explicit = [r for r in claimants if r["w5_claim_strength"] == "explicit-100%/fully"]
generic = [r for r in claimants if r["w5_claim_strength"] == "on-chain-generic"]
forever = [r for r in claimants if r["w5_claim_strength"] == "storage-forever"]
none = [r for r in df if not yes(r["in_w5"])]
assert len(explicit) + len(generic) + len(forever) == len(claimants), "Unknown claim strength"
pp = Counter(r["pointer_power"] or "none" for r in df)

funnel = {
    "claimants": metric("claimants", len(claimants)),
    "explicit": metric("explicit_100_fully_claimants", len(explicit)),
    "claimants_repointable": metric("claimants_repointable_one_account", sum(r["pointer_power"] in ("eoa", "multisig") for r in claimants)),
    "explicit_repointable": metric("explicit_repointable_one_account", sum(r["pointer_power"] in ("eoa", "multisig") for r in explicit)),
    "explicit_repointable_eoa": metric("explicit_repointable_eoa", sum(r["pointer_power"] == "eoa" for r in explicit)),
    "data_only_mutable": metric("claimants_data_mutable_only", sum(yes(r["claim_data_mutable_only"]) for r in claimants)),
    "definition": metrics["claimants_repointable_one_account"]["definition"],
}
outcome_counts = Counter(r["claim_outcome"] for r in outcomes)
assert set(outcome_counts) <= set(summary["outcome_definitions"]), "Unknown outcome"
claims = {
    "claimants": funnel["claimants"],
    "explicit": funnel["explicit"],
    "outcomes": {k: metric("outcome_" + k, outcome_counts[k]) for k in summary["outcome_definitions"]},
    "definitions": summary["outcome_definitions"],
    "population": summary["population"],
    "evidence": REPO + "/blob/main/data/claims/claim_outcomes.csv",
    "examples": [],
}
# Curated cases illustrate each observed outcome; all quotes and assessments come from the review.
example_names = {"Moonbirds", "CryptoSkulls", "Blitmap", "ChainFaces", "MoonCats", "Chain Runners",
                 "Art Blocks (Curated contract; Fidenza, Ringers)"}
for outcome in outcomes:
    if outcome["collection"] not in example_names:
        continue
    quote = by_review_id[outcome["selected_review_id"]]
    claims["examples"].append({
        "name": outcome["collection"], "address": outcome["address"],
        "text": quote["claim_text"], "source_url": quote["source_url"],
        "outcome": outcome["claim_outcome"], "reason": outcome["claim_reason"],
        "evidence_url": claims["evidence"],
    })

timeline, lanes, seen = [], [], set()
lane_summaries = {
    "Moonbirds": "The core is owned by a Safe multisig. Its current renderer is held by one wallet key: owner-only setBaseUri(string) and setAnimationBaseUri(string) redirect illustrated-art and animation URLs. They do not rewrite the legacy on-chain pixel data; setArtwork(uint256,bool) and setArtworks(uint256[],bool[]) are token-holder controls.",
    "Chain Runners": "An ordinary key owns the contract and set the renderer address {n} times in the saved history. An alternate on-chain renderer supplies SVG; the ordinary tokenURI points to HTTP.",
    "Heraldia": "An ordinary key owns the contract and set the renderer address {n} times between {first} and {last}. Replacing the renderer or its storage source can change displayed pixels and metadata.",
}
kind = {"uri": "uri-pointer", "renderer": "renderer-swap"}
what = {"http": "base URI set to a web server", "ipfs": "base URI set to IPFS",
        "arweave": "base URI set to Arweave", "address": "renderer address set"}
for name, description in lane_summaries.items():
    r = next(r for r in df if r["name"] == name)
    events = [e for e in ev if e["address"] == r["address"] and e["category"] in kind]
    for e in events:
        key = (e["address"], e["date"], e["method"], e["tx"])
        if key in seen:
            continue
        seen.add(key)
        timeline.append({"lane": name, "contract": e["address"], "date": e["date"],
                         "kind": kind[e["category"]], "method": e["method"],
                         "what": what[e["value_kind"]] + " (" + e["method"] + ")", "tx": e["tx"]})
    dates = sorted(e["date"] for e in events)
    lanes.append({"lane": name, "contract": r["address"], "class": r["class_final"],
                  "class_label": "Renderer held by one wallet key" if name == "Moonbirds" else None,
                  "summary": description.format(n=len(dates), first=dates[0][:7], last=dates[-1][:7]),
                  "evidence": REPO + "/blob/main/data/mutability/evidence/" + r["address"] + ".json"})
timeline.sort(key=lambda t: (t["date"], t["lane"], t["tx"]))

out = {
    "schema_version": 2,
    "snapshot_date": summary["review_date"],
    "repo": REPO,
    "universe": {"contracts": metric("mutation_audit_contracts", len(df))},
    "classes": counts(df),
    "by_claim": {"explicit": counts(explicit), "generic": counts(generic),
                 "forever": counts(forever), "none": counts(none)},
    "claims": claims,
    "funnel": funnel,
    "pointer_power": {"eoa": metric("audit_repointable_eoa", pp["eoa"]),
                      "multisig": metric("audit_repointable_multisig", pp["multisig"]),
                      "dao-or-timelock": pp["dao-or-timelock"], "none": pp["none"]},
    "broad_eoa_mutable": metric("audit_broad_eoa_mutable", counts(df)["eoa-mutable"]),
    "upgradeable": sum(yes(r["upgradeable"]) for r in df),
    "swaps_observed": sum(float(r["observed_renderer_swaps"] or 0) > 0 for r in df),
    "timeline_evidence": REPO + "/blob/main/data/mutability/setter_events.csv",
    "lanes": lanes,
    "timeline": timeline,
}
OUT.write_text(json.dumps(out, indent=1) + "\n")
print("wrote", OUT, out["classes"], funnel, claims["outcomes"], len(timeline), "CSV-backed events")
