"""Aggregate data/gallery/*/result.json + meta.json -> data/gallery/results.csv (+ results.json). Manual review overrides: data/gallery/manual_review.json
({slug: {"verdict_B": ..., "verdict_C": ..., "note": ...}}), applied in separate columns so the automated verdict is never overwritten."""
import csv, json, pathlib, collections
ROOT = pathlib.Path(__file__).resolve().parents[2]
GAL = ROOT / "data" / "gallery"
BASE = "https://onchain.invalid/"
man = json.loads((GAL / "manual_review.json").read_text()) if (GAL / "manual_review.json").exists() else {}

def ext(log): return [r for r in log if not r["url"].startswith(BASE) and not r["url"].startswith("data:")]

rows = []
for rj in sorted(GAL.glob("*/result.json")):
    d = rj.parent; slug = d.name
    res = json.loads(rj.read_text()); meta = json.loads((d / "meta.json").read_text()); m = res.get("metrics", {})
    LA = json.loads((d / "requests_A.json").read_text()); LB = json.loads((d / "requests_B.json").read_text()) if (d / "requests_B.json").exists() else []
    LC = json.loads((d / "requests_C.json").read_text()) if (d / "requests_C.json").exists() else []
    eA, eB, eC = ext(LA), ext(LB), ext(LC)
    hostsA = sorted({r["url"].split("/")[2] for r in eA if "//" in r["url"]})
    cb = json.loads((d / "console_B.json").read_text()) if (d / "console_B.json").exists() else {}
    declared = list(meta.get("declared", {}).get("load", []))
    if meta.get("script_type"): declared.insert(0, f"script type {meta['script_type']}")
    sf = meta.get("source_flags", {}) or {}
    tech = [k for k in ("sstore2", "ethfs", "scripty", "gzip") if sf.get(k)]
    rpc = meta.get("rpc", {}) or {}
    mm = man.get(slug, {})
    rows.append(dict(
        slug=slug, collection=meta.get("collection"), contract=meta.get("contract"), token=meta.get("token_id"), medium=meta.get("medium"),
        chain_storage_method=meta.get("chain_method"), source_technique_flags="+".join(tech), source_verified=sf.get("verified"),
        read_default_public_rpc=rpc.get("default_public_ok", rpc.get("public_rpc_ok")), read_needed_fork=rpc.get("needed_fork", False), est_gas=rpc.get("gas_estimate"),
        external_requests_A=len(eA), external_hosts_A=";".join(hostsA), external_blocked_B=sum(1 for r in eB if r.get("action") == "blocked"),
        archive_served_C=sum(1 for r in eC if r.get("action") == "archive"), still_blocked_C=sum(1 for r in eC if r.get("action") == "blocked"),
        verdict_B=m.get("B", {}).get("verdict"), diff_B=m.get("B", {}).get("diff_frac"), verdict_C=m.get("C", {}).get("verdict"), diff_C=m.get("C", {}).get("diff_frac"),
        noise=m.get("noise_A_vs_A2_and_late"), B_console_errors=len(cb.get("console", [])), B_page_errors=len(cb.get("pageerrors", [])),
        declared_deps=" | ".join(declared), manual_verdict_B=mm.get("verdict_B"), manual_verdict_C=mm.get("verdict_C"), notes=(mm.get("note") or meta.get("note") or "")))
cols = list(rows[0].keys()) if rows else []
with open(GAL / "results.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
(GAL / "results.json").write_text(json.dumps(rows, indent=1))
c = collections.Counter((r["manual_verdict_B"] or r["verdict_B"]) for r in rows); print("B:", dict(c))
c = collections.Counter((r["manual_verdict_C"] or r["verdict_C"]) for r in rows); print("C:", dict(c))
print(len(rows), "items;", sum(1 for r in rows if r["external_requests_A"]), "with external requests in A")
