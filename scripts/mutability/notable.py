"""Print a human-readable evidence digest for chosen addresses (used to write docs/methods/mutability.md)."""
import json, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
for a in sys.argv[1:]:
    a = a.lower()
    e = json.load(open(ROOT / f"data/mutability/evidence/{a}.json"))
    print("=" * 100)
    print(a, e.get("contract_name"), "|", e["class_direct"], "deps:", e.get("class_deps"), "final:", e["class_final"], "ptr:", e.get("pointer_power"))
    print(" reason:", e["class_reason"][:300])
    ow = e.get("owner")
    print(" proxy:", (e.get("proxy") or {}).get("kind"), "| owner:", ow and (ow["type"], ow["addr"], ow.get("threshold"), ow.get("n_owners"), ow.get("bs_name")), "| locks:", e.get("lock_views"), "| lockfns:", e.get("lock_functions"))
    for m in e.get("mutators", []):
        if m["category"] in ("uri", "renderer", "upgrade"):
            print("   ", m["category"], m["name"], "power=", m.get("power"), "frozen=", m.get("frozen"), "eff=", m.get("effective"), [h["desc"] for h in m["holders"]][:2])
    for d in e.get("dependencies", []):
        an = d["analysis"]
        print("   dep", d["address"], d["via"], "path" if d.get("in_tokenuri_path") or d.get("via_setter") else "", an.get("class_direct"), "|", an.get("contract_name"), "|", (an.get("class_reason") or "")[:100])
    H = e.get("history") or {}
    for t in sorted([t for t in H.get("txs", []) if "hash" in t], key=lambda t: t["timestamp"]):
        print("   tx", t["timestamp"][:10], t.get("method"), t.get("category"), t.get("from", "")[:10], t["hash"][:14])
    for d in H.get("decoded", []):
        print("   dec", d["timestamp"][:10], d["method"], [(p["type"], p["value"][:90]) for p in (d.get("params") or [])][:2])
    for k, v in (H.get("events") or {}).items():
        if v.get("n"): print("   evt", k.split("(")[0], v["n"], v.get("first"), v.get("last"), [(x["date"], x["tx"][:12]) for x in v.get("list", [])][:6])
    for sf, v in (H.get("safe_calls") or {}).items():
        for c in (v.get("calls") or [])[:12]: print("   safe", sf[:10], c["date"], c["method"], c["category"], [x["value"][:42] for x in c["params"]][:2])
    if e.get("artblocks"):
        ab = e["artblocks"]; print("   AB", ab["family"], ab.get("admin_acl_desc"), ab["n_projects_checked"], ab["n_script_locked"])
