"""mutability history: did the setters / upgrades / lock / ownership changes actually happen, and when?
Sources: Blockscout advanced-filters (top-level txs by method id) + Etherscan v2 getLogs (events) + Blockscout tx decode."""
import re, datetime
import mlib
from mlib import selector, topic, blockscout, etherscan

LIFECYCLE_EVENTS = ["OwnershipTransferred(address,address)", "Upgraded(address)", "AdminChanged(address,address)", "BeaconUpgraded(address)",
                    "MetadataUpdate(uint256)", "BatchMetadataUpdate(uint256,uint256)", "PermanentURI(string,uint256)",
                    "PermanentURIGlobal()", "Locked(uint256)"]
EVT_NAME = re.compile(r"(uri|url|renderer|descriptor|metadata|lock|frozen|freeze|script|reveal|implementation|upgrade|baseuri|seeder|artist)", re.I)
TX_METHODS_EXTRA = ["transferOwnership(address)", "renounceOwnership()", "upgradeTo(address)", "upgradeToAndCall(address,bytes)", "changeAdmin(address)"]


def iso_from_hex(h):
    return datetime.datetime.fromtimestamp(int(h, 16), datetime.timezone.utc).strftime("%Y-%m-%d")


def adv_txs(addr, selectors, tag, max_pages=4):
    """Top-level contract calls to addr with given method ids. -> list of {hash,timestamp,method,from,status,block}"""
    out = []
    sels = list(dict.fromkeys(selectors))
    for ci in range(0, len(sels), 12):
        chunk = sels[ci:ci + 12]
        params = ""
        for pg in range(max_pages):
            q = f"/api/v2/advanced-filters?to_address_hashes_to_include={addr}&transaction_types=CONTRACT_CALL&methods={','.join(chunk)}{params}"
            try:
                j = blockscout(q, f"{addr}_adv_{tag}_{ci}_{pg}")
            except Exception as e:  # noqa: BLE001
                out.append({"error": str(e)[:100]}); break
            for it in j.get("items", []):
                out.append({"hash": it["hash"], "timestamp": it["timestamp"], "method": it.get("method"), "from": (it.get("from") or {}).get("hash"),
                            "from_is_contract": (it.get("from") or {}).get("is_contract"), "status": it.get("status"), "block": it.get("block_number")})
            nxt = j.get("next_page_params")
            if not nxt: break
            params = "&" + "&".join(f"{k}={v}" for k, v in nxt.items() if v is not None)
        else:
            out.append({"truncated": True, "chunk": ci})
    return out


def decode_txs_rpc(hashes, sig_by_sel, key):
    """Decode calldata of txs via eth_getTransactionByHash (RPC batch) + eth_abi using the known setter signatures. -> {hash: {...}}"""
    from eth_abi import decode
    out, path = mlib.rpc_batch([("eth_getTransactionByHash", [h]) for h in hashes], key, alt=True)
    res = {}
    for h, o in zip(hashes, out):
        if not o["ok"] or not o["result"]:
            res[h] = {"error": "eth_getTransactionByHash failed"}; continue
        tx = o["result"]; inp = tx.get("input") or "0x"; sel = inp[:10]
        sig = sig_by_sel.get(sel)
        params = []
        if sig:
            types = sig[sig.index("(") + 1:-1]
            types = [t for t in types.split(",") if t] if "(" not in types else None
            try:
                if types is None: raise ValueError("tuple args")
                vals = decode(types, bytes.fromhex(inp[10:])) if types else ()
                names = [f"arg{i}" for i in range(len(types))]
                for n, t, v in zip(names, types, vals):
                    if isinstance(v, bytes): v = "0x" + v.hex()
                    elif isinstance(v, (tuple, list)): v = str(list(v))
                    params.append({"name": n, "type": t, "value": str(v)[:300]})
            except Exception as e:  # noqa: BLE001
                params = [{"name": "raw", "type": "bytes", "value": inp[10:200]}]; res[h] = {"decode_note": repr(e)[:60]}
        res[h] = {**res.get(h, {}), "method_call": sig, "params": params, "from": tx.get("from"), "to": tx.get("to"), "block": tx.get("blockNumber"), "raw_batch": path}
    return res


def value_kind(v):
    v = (v or "").strip().lower()
    if v.startswith(("http://", "https://")): return "http"
    if v.startswith("ipfs://") or re.match(r"^(qm[1-9a-z]{44}|bafy)", v): return "ipfs"
    if v.startswith(("ar://", "arweave")): return "arweave"
    if v.startswith("data:"): return "data-uri"
    if re.match(r"^0x[0-9a-f]{40}$", v): return "address"
    if v == "": return "empty"
    return "other"


def logs(addr, sig_or_topic, tag, max_pages=2):
    t0 = sig_or_topic if sig_or_topic.startswith("0x") else topic(sig_or_topic)
    res = []
    for pg in range(1, max_pages + 1):
        r = mlib.getlogs(addr, t0, f"{addr}_logs_{tag}_{pg}", page=pg)
        if r is None:
            return {"error": "log APIs unavailable", "items": res}
        res += r
        if len(r) < 1000: break
    return {"items": res}


def summarize_logs(items):
    if not items: return {"n": 0}
    items = sorted(items, key=lambda x: int(x["timeStamp"], 16))
    f = lambda t: datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%d")  # noqa: E731
    ts = [int(x["timeStamp"], 16) for x in items]
    lst = [{"date": f(int(x["timeStamp"], 16)), "tx": x["transactionHash"], "topics": [t_[-40:] if t_ and len(t_) == 66 and t_.startswith("0x000000000000000000000000") else t_ for t_ in x["topics"][1:]],
            "data": (x.get("data") or "")[:130]} for x in items[:30]]
    return {"n": len(items), "first": f(ts[0]), "last": f(ts[-1]), "last_tx": items[-1]["transactionHash"], "list": lst}


def collect(addr, setter_sigs, lock_sigs, abi_events, upgrade_sigs=(), is_proxy=False, decode_cap=8):
    """setter_sigs: dict category -> list of signatures. Returns history dict."""
    H = {"txs": [], "events": {}, "decoded": []}
    sig2cat = {}
    for cat, sigs in setter_sigs.items():
        for s in sigs: sig2cat[selector(s)] = (cat, s)
    for s in lock_sigs: sig2cat[selector(s)] = ("lock", s)
    for s in upgrade_sigs: sig2cat[selector(s)] = ("upgrade", s)
    for s in TX_METHODS_EXTRA: sig2cat.setdefault(selector(s), ("ownership" if "wnership" in s else "upgrade", s))
    txs = adv_txs(addr, list(sig2cat), "setters")
    for t in txs:
        if "method" in t:
            cat = None
            for sel, (c, s) in sig2cat.items():
                if (t.get("method") or "").lower() == s.split("(")[0].lower(): cat = c; break
            t["category"] = cat
    H["txs"] = txs
    # events
    abi_names = {e["name"] for e in abi_events}
    ev_sigs = [s for s in LIFECYCLE_EVENTS if s.split("(")[0] in abi_names or (is_proxy and s.startswith(("Upgraded", "AdminChanged", "BeaconUpgraded")))
               or s.startswith("OwnershipTransferred") and not abi_events]
    for e in abi_events:
        if EVT_NAME.search(e["name"]):
            s = mlib.abi_sig(e)
            if s not in ev_sigs: ev_sigs.append(s)
    ev_sigs = ev_sigs[:10]
    for s in ev_sigs:
        r = logs(addr, s, re.sub(r"[^A-Za-z0-9]", "", s)[:40])
        H["events"][s] = {**summarize_logs(r.get("items", [])), **({"error": r["error"]} if "error" in r else {})}
        if s.startswith("OwnershipTransferred") and r.get("items"):
            H["ownership_transfers"] = [{"date": iso_from_hex(x["timeStamp"]), "from": "0x" + x["topics"][1][-40:], "to": "0x" + x["topics"][2][-40:], "tx": x["transactionHash"]}
                                        for x in sorted(r["items"], key=lambda x: int(x["timeStamp"], 16))][-8:]
        if s.startswith("Upgraded") and r.get("items"):
            H["upgrades"] = [{"date": iso_from_hex(x["timeStamp"]), "impl": "0x" + x["topics"][1][-40:], "tx": x["transactionHash"]}
                             for x in sorted(r["items"], key=lambda x: int(x["timeStamp"], 16))]
    # decode setter txs
    cand = [t for t in txs if t.get("category") in ("uri", "renderer", "upgrade", "contracturi", "reveal", "ownership") and t.get("status") in ("success", "ok", None)]
    own = sorted([t for t in cand if t["category"] == "ownership"], key=lambda t: t["timestamp"])[-3:]
    cand = [t for t in cand if t["category"] != "ownership"]
    cand.sort(key=lambda t: t["timestamp"])
    pick = cand[:3] + cand[-(decode_cap - 3):] if len(cand) > decode_cap else cand
    pick = list(pick) + own
    seen = []
    for t in pick:
        if t["hash"] not in seen: seen.append(t["hash"])
    sig_by_sel = {sel: sg for sel, (c, sg) in sig2cat.items()}
    dec = decode_txs_rpc(seen, sig_by_sel, f"{addr}_txdecode") if seen else {}
    by_hash = {t["hash"]: t for t in pick}
    for h in seen:
        t = by_hash[h]; d = dec.get(h, {})
        kinds = [value_kind(p["value"]) for p in d.get("params", []) if p["type"] in ("string", "address")]
        H["decoded"].append({"hash": h, "timestamp": t["timestamp"], "method": t.get("method"), "category": t.get("category"), "from": t.get("from"),
                             "params": d.get("params"), "value_kinds": kinds, "error": d.get("error")})
    H["incomplete"] = bool(any("error" in t for t in H["txs"]) or any("error" in v for v in H["events"].values()) or any(d.get("error") for d in H["decoded"]))
    return H


def safe_calls(safe, contract, sel_cat):
    """sel_cat: {selector: category}. Returns list of {date, method, category, params, tx, success} for Safe-executed calls to `contract`."""
    res = mlib.safe_txs(safe, contract, f"{safe}_to_{contract}")
    if res is None: return {"error": "safe tx service unavailable"}
    out = []
    for r in res:
        data = r.get("data") or "0x"
        sel = data[:10]
        dd = r.get("dataDecoded") or {}
        params = [{"name": p.get("name"), "type": p.get("type"), "value": str(p.get("value"))[:200]} for p in dd.get("parameters", [])] if dd else []
        out.append({"date": (r.get("executionDate") or "")[:10], "method": dd.get("method") or sel, "category": sel_cat.get(sel), "params": params[:3],
                    "tx": r.get("transactionHash"), "success": r.get("isSuccessful"), "safe": safe,
                    "value_kinds": [value_kind(p["value"]) for p in params if p["type"] in ("string", "address")]})
    return {"count": len(out), "calls": out}
