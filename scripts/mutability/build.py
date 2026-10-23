"""mutability step 3: flatten data/mutability/evidence/*.json into data/mutability/mutability.csv (+ parquet), artblocks_projects.csv, setter_events.csv.
Usage: .venv/bin/python -I scripts/mutability/build.py"""
import json, pathlib, re, sys
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chainread as cr  # noqa: E402

EV = ROOT / "data/mutability/evidence"
OUT = ROOT / "data/mutability"
CLAIM_STRONG = {"explicit-100%/fully", "storage-forever"}
CLAIM_ANY = {"explicit-100%/fully", "storage-forever", "on-chain-generic"}


def fnd(h):
    return (h or {}).get("addr")


def main():
    t = pd.read_csv(OUT / "targets.csv")
    t["address"] = t.address.str.lower()
    reviewed = pd.read_csv(ROOT / "data/claims/claimants_reviewed.csv").set_index("address")
    outcomes = pd.read_csv(ROOT / "data/claims/claim_outcomes.csv").set_index("address")
    # Preserve the historical 606-contract mutation audit population while replacing
    # all claims membership/quotes with the manually reviewed set.
    for col, source in {"w5_claim_strength":"claim_strength", "w5_claim_text":"claim_text",
                        "w5_source_type":"source_type", "w5_source_url":"source_url"}.items():
        t[col] = t.address.map(reviewed[source])
    t["in_w5"] = t.address.isin(reviewed.index)
    t.to_csv(OUT / "targets.csv", index=False)
    cen = pd.read_parquet(ROOT / "data/census/census_collections.parquet")
    cen["address"] = cen.address.str.lower()
    cen = cen.drop_duplicates("address").set_index("address")
    sig = pd.read_parquet(ROOT / "data/claims/source_signals.parquet")
    sig["address"] = sig.address.str.lower()
    sig = sig.drop_duplicates("address").set_index("address")
    rows = []; swaps = []; ab_rows = []
    for r in t.to_dict("records"):
        a = r["address"]
        p = EV / f"{a}.json"
        row = {k: (None if (isinstance(v, float) and v != v) else v) for k, v in r.items()}
        row["evidence_path"] = f"data/mutability/evidence/{a}.json"
        if not p.exists():
            row.update(class_final="unknown", class_reason="not analysed"); rows.append(row); continue
        e = json.loads(p.read_text())
        px = e.get("proxy") or {}
        row.update(verified=e.get("verified"), contract_name=e.get("contract_name"), proxy_kind=px.get("kind"), proxy_impl=px.get("impl"),
                   upgradeable=px.get("kind") in ("eip1967", "zos-unstructured", "beacon", "explorer-detected") or bool(e.get("uups")))
        if px.get("admin"): row["proxy_admin"] = cr.describe(px["admin"]); row["proxy_admin_addr"] = fnd(px["admin"])
        ow = e.get("owner")
        if ow:
            row.update(owner_addr=ow.get("addr"), owner_type=ow.get("type"), owner_desc=cr.describe(ow), owner_simple=cr.simple_type(ow),
                       owner_label=ow.get("bs_name") or ow.get("ens"))
        # per-mutator holders
        muts = e.get("mutators") or []
        live = [m for m in muts if m["category"] in ("uri", "renderer", "upgrade") and not m.get("frozen") and m.get("effective") != "no"]
        row["live_mutators"] = ";".join(sorted({m["name"] for m in live}))
        row["mutator_categories"] = ";".join(sorted({m["category"] for m in live}))
        hs = {}
        for m in live:
            for h in m["holders"]: hs[h["addr"]] = h["desc"]
        row["power_holders"] = " | ".join(f"{k}:{v}" for k, v in list(hs.items())[:5])
        row["inert_setters"] = ";".join(sorted({m["name"] for m in muts if m["category"] in ("uri", "renderer") and m.get("effective") == "no"}))[:200]
        row["frozen_setters"] = ";".join(sorted({m["name"] for m in muts if m.get("frozen")}))
        row["lock_functions"] = ";".join(e.get("lock_functions") or [])
        row["lock_flags"] = json.dumps(e.get("lock_views") or {})
        row["lock_flag_true"] = bool(e.get("lock_flags_true"))
        row["tokenuri_path"] = e.get("tokenuri_path")
        row["eip4906"] = e.get("eip4906")
        row["class_direct"] = e.get("class_direct"); row["class_deps"] = e.get("class_deps"); row["class_final"] = e.get("class_final")
        row["class_reason"] = e.get("class_reason")
        deps = e.get("dependencies") or []
        row["dependencies"] = " | ".join(f"{d['address']}[{d['via']}]={d['analysis'].get('class_direct')}{'*' if d.get('in_tokenuri_path') or d.get('via_setter') else ''}" for d in deps)
        row["n_deps"] = len(deps)
        row["unverified_selector_hits"] = ";".join(e.get("unverified_selector_hits") or [])
        # history
        H = e.get("history") or {}
        txs = [x for x in H.get("txs", []) if "hash" in x and x.get("status") in ("success", "ok", None)]
        sett = sorted([x for x in txs if x.get("category") in ("uri", "renderer", "upgrade", "contracturi")], key=lambda x: x["timestamp"])
        row["setter_txs_truncated"] = any(x.get("truncated") for x in H.get("txs", []))
        row["n_setter_txs"] = len(sett)
        row["n_uri_renderer_txs"] = len([x for x in sett if x["category"] in ("uri", "renderer")])
        row["first_setter_date"] = sett[0]["timestamp"][:10] if sett else None
        row["last_setter_date"] = sett[-1]["timestamp"][:10] if sett else None
        own = [x for x in txs if x.get("category") == "ownership"]
        row["n_ownership_txs"] = len(own)
        up = H.get("upgrades") or []
        row["n_upgrades"] = len(up); row["last_upgrade_date"] = up[-1]["date"] if up else None
        lk = [x for x in txs if x.get("category") == "lock"]
        row["lock_fn_called"] = lk[-1]["timestamp"][:10] if lk else None
        ot = H.get("ownership_transfers") or []
        row["n_ownership_events"] = (H.get("events", {}).get("OwnershipTransferred(address,address)") or {}).get("n")
        row["last_ownership_event"] = ot[-1]["date"] if ot else None
        evn = {k.split("(")[0]: v for k, v in (H.get("events") or {}).items() if v.get("n")}
        row["events_seen"] = ";".join(f"{k}x{v['n']}({v.get('first')}..{v.get('last')})" for k, v in evn.items())[:400]
        # decoded setter calls: kinds + dates
        offc = []
        for d in H.get("decoded", []):
            if d.get("category") in ("uri", "renderer", "upgrade", "contracturi"):
                for k in d.get("value_kinds") or []:
                    swaps.append({"address": a, "name": r.get("name"), "date": d["timestamp"][:10], "method": d["method"], "category": d["category"], "value_kind": k,
                                  "value": next((q["value"] for q in d["params"] if q["type"] in ("string", "address")), "")[:160], "from": d.get("from"), "tx": d["hash"]})
                    if k in ("http", "ipfs", "arweave") and d["category"] in ("uri",): offc.append(f"{d['timestamp'][:10]}:{k}")
        row["observed_uri_to_offchain"] = ";".join(offc)
        row["observed_renderer_swaps"] = len([1 for d in H.get("decoded", []) if d.get("category") == "renderer" and "address" in (d.get("value_kinds") or [])])
        # joins
        sg = sig.loc[a] if a in sig.index else None
        if sg is not None:
            row.update(sig_has_http_literal=bool(sg.has_http_literal), sig_has_data_uri=bool(sg.has_data_uri), sig_has_base64=bool(sg.has_base64), sig_has_sstore2=bool(sg.has_sstore2))
        if a in cen.index:
            c = cen.loc[a]
            row.update(census_meta_class_all=c.meta_class, census_media_class_all=c.media_class, census_liveness_all=c.liveness)
        # claim contradiction
        cs = row.get("w5_claim_strength")
        cf = row["class_final"]
        pp = e.get("pointer_power")
        row["pointer_power"] = pp
        row["repointable_eoa"] = pp == "eoa"
        row["repointable_multisig"] = pp == "multisig"
        row["repointable_one_account"] = pp in ("eoa", "multisig")
        row["claim_repointable_one_account"] = bool(row["in_w5"] and row["repointable_one_account"])
        row["claim_outcome"] = outcomes.loc[a, "claim_outcome"] if a in outcomes.index else None
        row["claim_outcome_reason"] = outcomes.loc[a, "claim_reason"] if a in outcomes.index else None
        row["claim_data_contracts"] = outcomes.loc[a, "claim_data_contracts"] if a in outcomes.index else None
        row["claim_data_control_note"] = outcomes.loc[a, "claim_data_control_note"] if a in outcomes.index else None
        row["claim_contradicted"] = row["claim_outcome"] == "contradicted"
        row["claim_contradicted_strong"] = bool(cs == "explicit-100%/fully" and row["claim_contradicted"])
        row["claim_data_mutable_only"] = bool(cs in CLAIM_ANY and cf in ("eoa-mutable", "multisig-mutable") and pp not in ("eoa", "multisig"))
        # immutable pointer but off-chain?
        row["immutable_but_offchain_pointer"] = bool(cf == "immutable" and row.get("census_meta_class_all") in ("http", "ipfs", "arweave"))
        ab = e.get("artblocks")
        if ab:
            row["ab_family"] = ab["family"]; row["ab_projects_checked"] = ab["n_projects_checked"]; row["ab_scripts_locked"] = ab["n_script_locked"]
            row["ab_admin_acl"] = ab.get("admin_acl_desc")
            for pj in ab["projects"]:
                ab_rows.append({"contract": a, "project_id": pj["project_id"], "artist": pj.get("artist"), "artist_holder": pj.get("artist_desc"), "script_locked": pj.get("locked"),
                                "script_type": pj.get("script_type"), "base_uri": pj.get("base_uri"), "base_uri_kind": pj.get("base_uri_kind"), "family": ab["family"]})
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "mutability.csv", index=False)
    df.to_parquet(OUT / "mutability.parquet", index=False)
    pd.DataFrame(ab_rows).to_csv(OUT / "artblocks_projects.csv", index=False)
    pd.DataFrame(swaps).to_csv(OUT / "setter_events.csv", index=False)
    print(len(df), "rows;", df.class_final.value_counts().to_dict())


if __name__ == "__main__":
    main()
