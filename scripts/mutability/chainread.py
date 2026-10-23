"""mutability on-chain reads: holder classification (EOA / renounced / Safe / timelock / governor / other contract), proxy slots,
zero-arg view reads. All through mlib.rpc_batch (saved raw)."""
import json, re, threading
import mlib
from mlib import rpc_batch, call_obj, word_addr, word_int, selector, DEAD

SLOTS = {
    "eip1967_impl": "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc",
    "eip1967_admin": "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103",
    "eip1967_beacon": "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50",
    "zos_impl": "0x7050c9e0f4ca769c69bd3a8ef740bc37934f8e2c036e5a723fd8ee048ed3f8c3",
    "zos_admin": "0x10d6a54a4754c8869d6886b5f5d7fbfa5b4522237ea5c60d11bc4e7a1ff9390b",
    "slot0": "0x0000000000000000000000000000000000000000000000000000000000000000",
}
S = lambda sg: selector(sg)  # noqa: E731
HOLDER_PROBES = ["getThreshold()", "getOwners()", "VERSION()", "getMinDelay()", "delay()", "admin()", "owner()", "proposalThreshold()",
                 "votingPeriod()", "required()", "timelock()", "GRACE_PERIOD()", "masterCopy()", "quorumVotes()", "pendingAdmin()", "superAdmin()"]
_cache = {}
_lock = threading.RLock()


def dec_addr_list(h):
    try:
        b = h[2:]
        off = int(b[0:64], 16) * 2
        n = int(b[off:off + 64], 16)
        return ["0x" + b[off + 64 + 64 * i + 24: off + 64 + 64 * (i + 1)] for i in range(n)]
    except Exception:
        return None


def get_code(addr, key):
    out, path = rpc_batch([("eth_getCode", [addr, "latest"])], key)
    r = out[0]
    return (r["result"] if r["ok"] else None), path


def blockscout_label(addr):
    try:
        j = mlib.blockscout(f"/api/v2/addresses/{addr}", f"addr_{addr.lower()}")
    except Exception as e:  # noqa: BLE001
        return {"label_error": str(e)[:80]}
    if j.get("_404"): return {}
    impls = [i.get("name") for i in (j.get("implementations") or []) if i.get("name")]
    tags = [t.get("name") for t in (j.get("public_tags") or [])] + [t.get("name") for t in (j.get("private_tags") or [])]
    md = (j.get("metadata") or {}).get("tags") or []
    return {"bs_name": j.get("name"), "ens": j.get("ens_domain_name"), "bs_impl_names": impls,
            "bs_tags": tags + [t.get("name") for t in md if isinstance(t, dict)],
            "is_contract": j.get("is_contract"), "creator": j.get("creator_address_hash"), "is_verified": j.get("is_verified"), "bs_reputation": j.get("reputation")}


def holder_info(addr, depth=0):
    """Classify who/what `addr` is. Returns dict with keys: addr, type in {eoa, renounced, safe, multisig-other, timelock, governor,
    contract-owned, contract-unknown, none}, plus details. Cached process-wide."""
    if addr is None: return {"addr": None, "type": "none"}
    a = addr.lower()
    with _lock:
        if a in _cache: return _cache[a]
    info = {"addr": a}
    if int(a, 16) == 0 or a in DEAD:
        info["type"] = "renounced"
        with _lock: _cache[a] = info
        return info
    code, p = get_code(a, f"{a}_holdercode")
    info["code_raw"] = p
    if code is None:
        info["type"] = "unknown"; info["note"] = "eth_getCode failed"
    elif code in ("0x", "0x0", ""):
        info["type"] = "eoa"
    elif code.lower().startswith("0xef0100"):
        info["type"] = "eoa"; info["note"] = "EIP-7702 delegated EOA"
    else:
        info["code_len"] = (len(code) - 2) // 2
        out, p2 = rpc_batch([call_obj(a, S(s)) for s in HOLDER_PROBES], f"{a}_holderprobe")
        info["probe_raw"] = p2
        r = dict(zip(HOLDER_PROBES, out))
        ok = lambda n: r[n]["ok"] and r[n]["result"] not in ("0x", None)  # noqa: E731
        if ok("getThreshold()") and ok("getOwners()"):
            owners = dec_addr_list(r["getOwners()"]["result"])
            info.update(type="safe", threshold=word_int(r["getThreshold()"]["result"]), n_owners=len(owners or []), owners=owners,
                        version=_dec_str(r["VERSION()"]["result"]) if ok("VERSION()") else None)
        elif ok("required()") and ok("getOwners()"):
            owners = dec_addr_list(r["getOwners()"]["result"])
            info.update(type="multisig-other", threshold=word_int(r["required()"]["result"]), n_owners=len(owners or []), owners=owners)
        elif ok("proposalThreshold()") or ok("votingPeriod()"):
            info.update(type="governor", timelock=word_addr(r["timelock()"]["result"]) if ok("timelock()") else None)
        elif ok("getMinDelay()") or (ok("delay()") and (ok("GRACE_PERIOD()") or ok("admin()"))):
            delay = word_int(r["getMinDelay()"]["result"]) if ok("getMinDelay()") else word_int(r["delay()"]["result"])
            info.update(type="timelock", delay_s=delay, flavour="openzeppelin" if ok("getMinDelay()") else "compound")
            if ok("admin()") and depth < 3:
                info["controller"] = holder_info(word_addr(r["admin()"]["result"]), depth + 1)
            elif ok("getMinDelay()") and depth < 3:
                info["controller"] = timelock_proposers(a, depth)
        elif (ok("owner()") or ok("superAdmin()")) and depth < 3:
            o = holder_info(word_addr(r["owner()" if ok("owner()") else "superAdmin()"]["result"]), depth + 1)
            info.update(type="contract-owned", owner=o["addr"], controller=o)
        else:
            info["type"] = "contract-unknown"
    info.update(blockscout_label(a))
    with _lock: _cache[a] = info
    return info


def _dec_str(h):
    try:
        b = bytes.fromhex(h[2:]); off = int.from_bytes(b[:32], "big"); n = int.from_bytes(b[off:off + 32], "big")
        return b[off + 32:off + 32 + n].decode(errors="replace")
    except Exception: return None


def timelock_proposers(tl, depth):
    """OZ TimelockController: PROPOSER_ROLE members via RoleGranted logs, confirmed with hasRole."""
    role = "0x" + mlib.keccak256(b"PROPOSER_ROLE").hex()
    t0 = mlib.topic("RoleGranted(bytes32,address,address)")
    res = mlib.getlogs(tl, t0, f"{tl}_proposer_logs", topic1=role)
    accts = []
    for lg in res or []:
        accts.append("0x" + lg["topics"][2][-40:])
    accts = list(dict.fromkeys(accts))
    live = []
    if accts:
        has = mlib.selector("hasRole(bytes32,address)")
        out, _ = rpc_batch([call_obj(tl, has + role[2:] + "0" * 24 + x[2:]) for x in accts], f"{tl}_proposer_hasrole")
        live = [x for x, o in zip(accts, out) if o["ok"] and word_int(o["result"]) == 1]
    return {"type": "oz-proposers", "proposers": [holder_info(x, depth + 1) for x in live[:5]]}


def simple_type(h):
    """collapse holder_info to one of: eoa / multisig / dao-or-timelock / renounced / unknown ; follows contract-owned chains."""
    t = h.get("type")
    if t in ("eoa", "renounced"): return t
    if t in ("safe", "multisig-other"): return "multisig"
    if t in ("timelock", "governor"): return "dao-or-timelock"
    if t == "contract-owned": return simple_type(h["controller"])
    return "unknown"


def describe(h):
    t = h.get("type")
    if t == "safe": return f"safe {h.get('threshold')}/{h.get('n_owners')}"
    if t == "multisig-other": return f"multisig {h.get('threshold')}/{h.get('n_owners')}"
    if t == "timelock":
        d = h.get("delay_s"); c = h.get("controller")
        inner = ""
        if c:
            if c.get("type") == "oz-proposers": inner = ("<-" + ",".join(describe(x) for x in c["proposers"])) if c["proposers"] else ""
            else: inner = "<-" + describe(c)
        return f"timelock({d}s){inner}"
    if t == "governor": return "governor"
    if t == "contract-owned": return f"{h.get('bs_name') or 'contract'}->" + describe(h["controller"])
    if t == "contract-unknown": return f"contract:{h.get('bs_name') or '?'}"
    return t or "?"


def read_views(addr, sels, key, block="latest"):
    """sels: list of (label, calldata hex). Returns ({label: result dict}, raw_path)"""
    out, path = rpc_batch([call_obj(addr, d, block) for _, d in sels], key)
    return {l: o for (l, _), o in zip(sels, out)}, path


def storage_slots(addr, key):
    names = list(SLOTS)
    out, path = rpc_batch([("eth_getStorageAt", [addr, SLOTS[n], "latest"]) for n in names], key)
    res = {}
    for n, o in zip(names, out):
        if o["ok"] and o["result"] and int(o["result"], 16) != 0: res[n] = word_addr(o["result"]) if n != "slot0" else o["result"]
    return res, path
