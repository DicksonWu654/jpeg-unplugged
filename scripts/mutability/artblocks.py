"""mutability: Art Blocks core contracts (V0/V1/V3 families). Mutation power is per project: the project artist can repoint
projectBaseURI (onlyArtist, no unlock requirement); project scripts freeze when `locked`. Reads per gallery project."""
import mlib, chainread as cr
from mlib import call_obj, selector, word_addr
from eth_abi import decode
import history

def _fn(abi, name):
    for f in abi:
        if f.get("type") == "function" and f["name"] == name: return f

def _call(a, abi, name, args, key):
    f = _fn(abi, name)
    if not f: return None
    sig = mlib.abi_sig(f)
    data = selector(sig) + "".join(f"{x:064x}" for x in args)
    out, p = mlib.rpc_batch([call_obj(a, data)], key)
    o = out[0]
    if not o["ok"] or o["result"] in ("0x", None): return {"error": o.get("error"), "raw": p}
    types = [x["type"] for x in f["outputs"]]
    names = [x.get("name") or str(i) for i, x in enumerate(f["outputs"])]
    try:
        vals = decode(types, bytes.fromhex(o["result"][2:]))
    except Exception as e:  # noqa: BLE001
        return {"error": "decode " + repr(e)[:60], "raw": p}
    return {"vals": dict(zip(names, vals)), "raw": p}

def is_artblocks(abi):
    names = {f.get("name") for f in abi if f.get("type") == "function"}
    return ("projectScriptInfo" in names or "projectStateData" in names) and "projectURIInfo" in names

def extra(a, abi, pids):
    res = {"projects": []}
    names = {f.get("name") for f in abi if f.get("type") == "function"}
    v3 = "projectStateData" in names
    for pid in pids:
        k = f"{a}_ab_{pid}"
        r = {"project_id": pid}
        if v3:
            art = _call(a, abi, "projectIdToArtistAddress", [pid], k + "_artist")
            st = _call(a, abi, "projectStateData", [pid], k + "_state")
            sd = _call(a, abi, "projectScriptDetails", [pid], k + "_scriptdetails")
            r["artist"] = art and art.get("vals", {}).get("0")
            r["locked"] = st and st.get("vals", {}).get("locked")
            r["completed_ts"] = st and st.get("vals", {}).get("completedTimestamp")
            r["script_type"] = sd and sd.get("vals", {}).get("scriptTypeAndVersion")
            r["raw"] = [x.get("raw") for x in (art, st, sd) if x]
        else:
            ti = _call(a, abi, "projectTokenInfo", [pid], k + "_tokeninfo")
            si = _call(a, abi, "projectScriptInfo", [pid], k + "_scriptinfo")
            r["artist"] = ti and ti.get("vals", {}).get("artistAddress")
            r["locked"] = si and si.get("vals", {}).get("locked")
            r["script_count"] = si and si.get("vals", {}).get("scriptCount")
            r["raw"] = [x.get("raw") for x in (ti, si) if x]
        ui = _call(a, abi, "projectURIInfo", [pid], k + "_uri")
        if ui and ui.get("vals"):
            r["base_uri"] = ui["vals"].get("projectBaseURI", ui["vals"].get("0"))
            r["base_uri_kind"] = history.value_kind(r["base_uri"])
            r["base_ipfs_uri"] = ui["vals"].get("projectBaseIpfsURI"); r["use_ipfs"] = ui["vals"].get("useIpfs")
            r["raw"].append(ui.get("raw"))
        if r.get("artist"):
            h = cr.holder_info(r["artist"])
            r["artist_holder"] = {kk: h.get(kk) for kk in ("addr", "type", "threshold", "n_owners", "bs_name", "ens")}
            r["artist_desc"] = cr.describe(h); r["artist_simple"] = cr.simple_type(h)
        res["projects"].append(r)
    return res
