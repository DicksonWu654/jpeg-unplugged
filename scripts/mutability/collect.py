"""mutability: per-contract mutability analysis. Usage:
    .venv/bin/python -I scripts/mutability/collect.py run [--workers 4] [--limit N] [--only 0xaddr,...] [--refresh]
Writes data/mutability/evidence/<addr>.json (analysis + pointers to saved raw files under data/raw/{rpc,etherscan,blockscout}-mutability).
"""
import json, re, sys, time, argparse, threading, concurrent.futures as cf, pathlib, traceback
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mlib, static, chainread as cr, history, artblocks
from mlib import word_addr, word_int, selector, call_obj, ROOT, EVID

REDO_INCOMPLETE = False
RANK = {"eoa": 3, "multisig": 2, "dao-or-timelock": 1}
LIBRX = re.compile(r"(openzeppelin|solmate|solady|/utils/|/interfaces?/|erc721a|ds-test|forge-std|chiru-labs|base64\.sol|/lib/|node_modules|@ensdomains)", re.I)
ADDR_NAME_HOLDER = re.compile(r"^(owner|admin|_owner|_admin|artist|deployer|dev|developer|creator|manager|controller|governor|governance|authority|core|proxyAdmin|multisig)$", re.I)


def merged_abi(*addrs):
    seen = {}; out = []
    for a in addrs:
        if not a: continue
        for f in mlib.abi_of(a) or []:
            k = (f.get("type"), f.get("name"), json.dumps([i["type"] for i in f.get("inputs", [])]))
            if k in seen: continue
            seen[k] = 1; out.append(f)
    return out


def source_bundle(*addrs):
    all_t, nonlib = "", ""
    for a in addrs:
        if not a: continue
        rec, files = mlib.source_text(a)
        for fn, t in files or []:
            all_t += "\n" + t
            if not LIBRX.search(fn): nonlib += "\n" + t
    return all_t, nonlib


def dec_str(h):
    try:
        b = bytes.fromhex(h[2:]); off = int.from_bytes(b[:32], "big"); n = int.from_bytes(b[off:off + 32], "big")
        return b[off + 32:off + 32 + n].decode(errors="replace")
    except Exception: return None


def written_vars(body):
    b = static.strip_comments(body)
    decl = set(re.findall(r"\b(?:string|uint\d*|int\d*|address|bytes\d*|bool|[A-Z]\w*)\s+(?:memory\s+|calldata\s+|storage\s+)?(\w+)\s*(?:=|;|,|\))", b))
    names = set()
    for m in re.finditer(r"(?<![\w.])([A-Za-z_]\w*)\s*(?:\[[^\]]*\])*\s*=(?!=)", b): names.add(m.group(1))
    for m in re.finditer(r"\.\s*([A-Za-z_]\w*)\s*=(?!=)", b): names.add(m.group(1))
    return {n for n in names if n not in decl or n.lower().endswith(("uri", "url"))}


def tokenuri_text(src_all, src_nonlib):
    """Text of tokenURI/uri path: non-library definitions if present (plus library if they call super), else library."""
    ids_n, txt_n = static.tokenuri_targets(src_nonlib) if src_nonlib else (set(), "")
    if txt_n.strip():
        if "super.tokenURI" in txt_n or "super.uri" in txt_n:
            ids_a, txt_a = static.tokenuri_targets(src_all)
            return ids_n | ids_a, txt_n + "\n" + txt_a, "override+super"
        return ids_n, txt_n, "override"
    ids_a, txt_a = static.tokenuri_targets(src_all)
    return ids_a, txt_a, ("inherited" if txt_a.strip() else "none")


def analyze(addr, depth=0, meta=None, refresh=False):
    a = addr.lower()
    ev = {"address": a, "depth": depth, "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    code, cp = cr.get_code(a, f"{a}_code")
    ev["code_raw"] = cp
    if code in (None,):
        ev.update(class_direct="unknown", class_reason="eth_getCode failed"); return ev
    if code in ("0x", ""):
        ev.update(class_direct="unknown", class_reason="no code at address (EOA or self-destructed)"); return ev
    ev["code_len"] = (len(code) - 2) // 2
    # ---- proxy detection
    slots, sp = cr.storage_slots(a, f"{a}_slots")
    ev["slots"] = slots; ev["slots_raw"] = sp
    impl = slots.get("eip1967_impl") or slots.get("zos_impl")
    padm = slots.get("eip1967_admin") or slots.get("zos_admin")
    proxy = {"kind": None}
    clone = static.clone_target(code)
    beacon = slots.get("eip1967_beacon")
    mlib.ensure_src(a)
    rec = mlib.srcscan.load(a)
    verified = bool(rec and (rec.get("SourceCode") or "").strip())
    if clone:
        proxy = {"kind": "eip1167-clone", "impl": clone}; impl = clone
    elif beacon:
        out, bp = mlib.rpc_batch([call_obj(beacon, selector("implementation()")), call_obj(beacon, selector("owner()"))], f"{a}_beacon")
        proxy = {"kind": "beacon", "beacon": beacon, "beacon_raw": bp}
        if out[0]["ok"] and out[0]["result"] != "0x": impl = word_addr(out[0]["result"]); proxy["impl"] = impl
        if out[1]["ok"] and out[1]["result"] != "0x":
            proxy["beacon_owner"] = cr.holder_info(word_addr(out[1]["result"]))
    elif slots.get("eip1967_impl"):
        proxy = {"kind": "eip1967", "impl": impl}
    elif slots.get("zos_impl"):
        proxy = {"kind": "zos-unstructured", "impl": impl}
    elif rec and rec.get("Implementation") and re.match(r"^0x[0-9a-fA-F]{40}$", rec["Implementation"].strip()):
        impl = rec["Implementation"].strip().lower(); proxy = {"kind": "explorer-detected", "impl": impl}
    if impl and impl != a:
        mlib.ensure_src(impl)
        irec = mlib.srcscan.load(impl)
        proxy["impl_verified"] = bool(irec and (irec.get("SourceCode") or "").strip())
        proxy["impl_name"] = (irec or {}).get("ContractName")
    ev["verified"] = verified; ev["contract_name"] = (rec or {}).get("ContractName")
    ev["proxy"] = proxy
    if padm and proxy["kind"] in ("eip1967", "zos-unstructured"):
        proxy["admin"] = cr.holder_info(padm)
    # ---- abi/source
    impl_used = impl if (impl and impl != a and proxy.get("impl_verified")) else None
    abi = merged_abi(impl_used, a)
    src_all, src_nonlib = source_bundle(impl_used, a)
    have_src = bool(src_all.strip()) and bool(abi)
    ev["has_source"] = have_src
    ev["abi_from"] = "impl+proxy" if impl_used else ("self" if abi else None)
    surf = static.surface_from_abi(abi)
    ev["unverified_selector_hits"] = []
    if not have_src:
        # bytecode selector scan (impl if proxy)
        tgt_code = code
        if impl and impl != a:
            c2, _ = cr.get_code(impl, f"{impl}_code")
            if c2: tgt_code = c2
        ev["unverified_selector_hits"] = static.bytecode_selectors(tgt_code)
    # ---- history (needs only ABI/selectors) -- computed early so hidden owners can be inferred from it
    setter_sigs = {c: [x["sig"] for x in surf.get(c, [])] for c in ("uri", "renderer", "upgrade", "contracturi", "reveal")}
    lock_sigs = [x["sig"] for x in surf.get("lock", [])]
    H = {}
    if depth == 0 or any(surf.get(c) for c in ("uri", "renderer", "upgrade")) or proxy["kind"]:
        try:
            H = history.collect(a, setter_sigs, lock_sigs, static.abi_events(abi), upgrade_sigs=[x["sig"] for x in surf.get("upgrade", [])],
                                is_proxy=bool(proxy["kind"] and proxy["kind"] != "eip1167-clone"))
        except Exception as e:  # noqa: BLE001
            H = {"error": repr(e)[:200]}
    ev["history"] = H
    creator = (meta or {}).get("creator")
    # ---- reads batch 1
    sels = [("owner()", selector("owner()")), ("pendingOwner()", selector("pendingOwner()")), ("admin()", selector("admin()")),
            ("getOwner()", selector("getOwner()")), ("proxiableUUID()", selector("proxiableUUID()")),
            ("supportsInterface4906", selector("supportsInterface(bytes4)") + "49064906" + "0" * 56)]
    av = [x for x in static.address_views(abi) if x["name"] not in ("owner", "pendingOwner", "admin", "getOwner")][:40]
    for x in av: sels.append((x["name"] + "()", x["selector"]))
    lv = static.lock_views(abi)
    for x in lv: sels.append((x["name"] + "()", x["selector"]))
    role_consts = [f["name"] for f in static.abi_funcs(abi) if not f.get("inputs") and f.get("stateMutability") in ("view", "pure")
                   and len(f.get("outputs", [])) == 1 and f["outputs"][0]["type"] == "bytes32" and f["name"].endswith("ROLE")][:30]
    for r in role_consts: sels.append((r + "()", selector(r + "()")))
    out, rp = mlib.rpc_batch([call_obj(a, d) for _, d in sels], f"{a}_reads1")
    R = {l: o for (l, _), o in zip(sels, out)}
    ev["reads1_raw"] = rp
    okv = lambda l: R.get(l, {}).get("ok") and R[l]["result"] not in ("0x", None)  # noqa: E731
    reads = {}
    for l in R:
        if okv(l): reads[l] = R[l]["result"]
    ev["eip4906"] = bool(okv("supportsInterface4906") and word_int(R["supportsInterface4906"]["result"]) == 1)
    owner = word_addr(R["owner()"]["result"]) if okv("owner()") else (word_addr(R["getOwner()"]["result"]) if okv("getOwner()") else None)
    admin_v = word_addr(R["admin()"]["result"]) if okv("admin()") else None
    pend = word_addr(R["pendingOwner()"]["result"]) if okv("pendingOwner()") else None
    ev["owner"] = cr.holder_info(owner) if owner else None
    ev["pending_owner"] = cr.holder_info(pend) if pend and int(pend, 16) else None
    ev["admin_fn"] = cr.holder_info(admin_v) if admin_v else None
    ev["uups"] = bool(okv("proxiableUUID()"))
    # lock flag values
    locks = {}
    for x in lv:
        l = x["name"] + "()"
        if okv(l): locks[x["name"]] = word_int(R[l]["result"])
    ev["lock_views"] = locks
    # roles (lazy: only roles that gate a mutator are resolved)
    has_ac = any(f.get("name") == "hasRole" for f in static.abi_funcs(abi))
    roles = {}
    role_vals = {"DEFAULT_ADMIN_ROLE": "0x" + "0" * 64}
    if has_ac:
        for r in role_consts:
            if okv(r + "()"): role_vals[r] = R[r + "()"]["result"]
        for m in re.finditer(r"bytes32\s+(?:public\s+|private\s+|internal\s+)*(?:constant\s+)?(\w+)\s*=\s*keccak256\(\s*\"([^\"]+)\"\s*\)", src_all):
            role_vals.setdefault(m.group(1), "0x" + mlib.keccak256(m.group(2).encode()).hex())
    has_count = any(f.get("name") == "getRoleMemberCount" for f in static.abi_funcs(abi))

    def role_members(rn):
        if rn in roles: return roles[rn]
        rv = role_vals.get(rn)
        members = None
        if rv and has_count:
            o1, _ = mlib.rpc_batch([call_obj(a, selector("getRoleMemberCount(bytes32)") + rv[2:])], f"{a}_rolecount_{rn}")
            if o1[0]["ok"] and o1[0]["result"] != "0x":
                n = word_int(o1[0]["result"])
                if n is not None and n <= 8:
                    o2, _ = mlib.rpc_batch([call_obj(a, selector("getRoleMember(bytes32,uint256)") + rv[2:] + f"{i:064x}") for i in range(n)], f"{a}_rolemembers_{rn}")
                    members = [word_addr(x["result"]) for x in o2 if x["ok"]]
        src_ = "enumerable"
        if members is None and rv:
            # non-enumerable AccessControl: candidates from RoleGranted logs, confirmed with hasRole
            lg = mlib.getlogs(a, mlib.topic("RoleGranted(bytes32,address,address)"), f"{a}_rolegranted_{rn}", topic1=rv)
            if lg is None:
                ev["roles_incomplete"] = True; src_ = "logs unavailable"
            else:
                accts = list(dict.fromkeys("0x" + x["topics"][2][-40:] for x in lg if len(x.get("topics", [])) > 2 and x["topics"][2]))[:25]
                members = []
                if accts:
                    o3, _ = mlib.rpc_batch([call_obj(a, selector("hasRole(bytes32,address)") + rv[2:] + "0" * 24 + x[2:]) for x in accts], f"{a}_hasrole_{rn}")
                    members = [x for x, o in zip(accts, o3) if o["ok"] and o["result"] != "0x" and word_int(o["result"]) == 1]
                src_ = "RoleGranted logs + hasRole"
        roles[rn] = {"value": rv, "members": members, "source": src_}
        return roles[rn]

    # ---- gates
    hidden_cache = {}

    def hidden_holder(var):
        """Owner/admin stored in a private variable with no getter: infer from history (last transferOwnership / renounce / last owner-gated
        caller / creator) and confirm by finding the address in storage slots 0..31."""
        if "h" in hidden_cache: return hidden_cache["h"]
        cands = []; how = []
        dec = [d for d in H.get("decoded", []) if d.get("category") == "ownership"]
        dec.sort(key=lambda d: d["timestamp"])
        if dec:
            last = dec[-1]
            if (last.get("method") or "").startswith("renounce"):
                hidden_cache["h"] = (["0x0000000000000000000000000000000000000000"], "private owner renounced (renounceOwnership tx " + last["hash"][:12] + ")")
                return hidden_cache["h"]
            for p_ in last.get("params") or []:
                if p_["type"] == "address":
                    v_ = p_["value"].lower()
                    if int(v_, 16) == 0 or v_ in mlib.DEAD:
                        hidden_cache["h"] = ([v_], "private owner set to zero/dead address by transferOwnership tx " + last["hash"][:14] + " on " + last["timestamp"][:10])
                        return hidden_cache["h"]
                    cands.append(v_); how.append("last transferOwnership arg")
        sett = sorted([t for t in H.get("txs", []) if t.get("category") in ("uri", "renderer", "upgrade", "contracturi") and t.get("from")], key=lambda t: t["timestamp"])
        if sett:
            cands.append(sett[-1]["from"].lower()); how.append("sender of last owner-gated call")
        if creator and isinstance(creator, str): cands.append(creator.lower()); how.append("deployer")
        else:
            lab = cr.blockscout_label(a)
            if lab.get("creator"): cands.append(lab["creator"].lower()); how.append("deployer")
        cands = list(dict.fromkeys(cands))[:3]
        if not cands: return None
        slots = [("eth_getStorageAt", [a, hex(i), "latest"]) for i in range(32)]
        out, sp = mlib.rpc_batch(slots, f"{a}_slotscan")
        for c in cands:
            for i, o in enumerate(out):
                if o["ok"] and o["result"] and int(o["result"], 16) & ((1 << 160) - 1) == int(c, 16) and int(o["result"], 16) != 0:
                    hidden_cache["h"] = ([c], f"private {var}: inferred {how[cands.index(c)]}, confirmed in storage slot {i} ({sp})")
                    return hidden_cache["h"]
        hidden_cache["h"] = None
        ev["hidden_owner_unconfirmed"] = cands
        return None

    def holders_for_gate(g):
        t, ref = g["type"], g["ref"]
        if t == "owner":
            if owner: return [owner], "owner()"
            hh = hidden_holder("owner")
            return hh if hh else (None, "owner() unavailable")
        if t == "named":
            for cand in (ref, ref.lstrip("_"), "get" + ref[:1].upper() + ref[1:].lstrip("_")):
                l = cand + "()"
                if okv(l): return [word_addr(R[l]["result"])], l
            if ref.lower() in ("admin", "_admin") and admin_v: return [admin_v], "admin()"
            if ref.lower() in ("owner", "_owner") and owner: return [owner], "owner()"
            # last resort: direct call (getter missing from ABI view list)
            o3, _ = mlib.rpc_batch([call_obj(a, selector(ref.lstrip("_") + "()"))], f"{a}_named_{re.sub(r'[^A-Za-z0-9]', '', ref)}")
            if o3[0]["ok"] and o3[0]["result"] not in ("0x", None) and len(o3[0]["result"]) == 66: return [word_addr(o3[0]["result"])], ref + "()"
            hh = hidden_holder(ref)
            if hh: return hh
            return None, f"{ref} (no public getter)"
        if t == "perkey": return None, f"per-key gate on {ref}"
        if t == "role":
            rn = ref.split(".")[-1]
            r = role_members(rn)
            hs = []
            if r and r["members"]: hs = list(r["members"])
            da = role_members("DEFAULT_ADMIN_ROLE")
            if da and da["members"]: hs = list(dict.fromkeys(hs + da["members"]))
            return (hs or None), f"role:{rn}"
        if t == "allowlist": return None, f"mapping {ref}"
        if t == "token-owner": return "token-owner", "ownerOf"
        return None, f"unknown gate {ref}"

    muts = []
    for cat in ("uri", "renderer", "upgrade", "reveal", "contracturi"):
        for f in surf.get(cat, []):
            gi = static.gates_for_function(src_all, f["name"]) if have_src else None
            if cat == "upgrade" and gi is not None and not gi["groups"]:
                au = static.gates_for_function(src_all, "_authorizeUpgrade")
                if au: gi["groups"] = au["groups"]; gi["gates"] = au["gates"]
            m = {"name": f["name"], "sig": f["sig"], "selector": f["selector"], "category": cat, "inputs": f.get("inputs", []), "gates": (gi or {}).get("gates"), "groups": (gi or {}).get("groups"),
                 "modifiers": (gi or {}).get("modifiers"), "body_head": ((gi or {}).get("body_head") or "")[:160]}
            if gi is None and have_src:
                m["note"] = "no body found (interface-only or inherited)"
            muts.append(m)
    # effectiveness
    tuids, tutxt, tu_kind = (set(), "", "n/a")
    if have_src: tuids, tutxt, tu_kind = tokenuri_text(src_all, src_nonlib)
    ev["tokenuri_path"] = tu_kind
    for m in muts:
        gi = static.gates_for_function(src_all, m["name"]) if have_src else None
        wv = written_vars((gi or {}).get("body_full", "")) if gi else set()
        m["writes"] = sorted(wv)[:6]
        if m["category"] in ("uri", "renderer") and have_src:
            if tu_kind == "none": m["effective"] = "unknown"
            elif not wv: m["effective"] = "unknown"
            else:
                m["effective"] = "yes" if any(re.search(rf"\b{re.escape(v)}\b", tutxt) for v in wv) else "no"
                if m["effective"] == "no" and re.search(r"_baseURI\s*\(", tutxt) and re.search(r"\bbaseURI\b", " ".join(wv)): m["effective"] = "yes"
    # holders per mutator: groups are ANDed (every modifier/require must pass), gates inside a group are ORed.
    def eval_power(m):
        groups = m.get("groups"); how = []; gres = []
        if groups is None: how.append("no source body")
        elif not groups: how.append("no access check found in header/body head")
        for grp in groups or []:
            hs = []; unk = False; tok = False
            for g in grp:
                if g["type"] == "named" and g["ref"] in ("_getAdmin", "getAdmin", "_admin", "admin") and padm and proxy["kind"] in ("eip1967", "zos-unstructured"):
                    h, why = [padm], "eip1967 admin slot"
                else:
                    h, why = holders_for_gate(g)
                how.append(why)
                if h == "token-owner": tok = True
                elif h is None: unk = True
                else: hs += h
            gres.append({"holders": list(dict.fromkeys(hs)), "unknown": unk, "token": tok})
        if m["category"] == "upgrade" and not any(gr["holders"] and not gr["unknown"] for gr in gres):
            if padm and proxy["kind"] in ("eip1967", "zos-unstructured"):
                gres.append({"holders": [padm], "unknown": False, "token": False}); how.append("fallback: eip1967 admin slot")
            elif owner:
                gres.append({"holders": [owner], "unknown": False, "token": False}); how.append("fallback: owner() (upgrade authority not parsed)")
        info = {}
        def typ(x):
            if x not in info: info[x] = cr.simple_type(cr.holder_info(x))
            return info[x]
        known = []; dead = False; tokg = False
        for gr in gres:
            if gr["token"] and not gr["holders"]: tokg = True; continue
            if gr["unknown"] or not gr["holders"]: continue
            tp = [typ(x) for x in gr["holders"]]
            live_ = [t for t in tp if t != "renounced"]
            if not live_: dead = True; continue
            if any(t == "unknown" for t in live_): continue
            known.append((max(RANK[t] for t in live_), gr))
        if dead: power, chosen = "renounced", None
        elif known:
            rk, chosen = min(known, key=lambda x: x[0])
            power = {3: "eoa", 2: "multisig", 1: "dao-or-timelock"}[rk]
        elif tokg: power, chosen = "token-holder", None
        else: power, chosen = "unknown", None
        hl = (chosen["holders"] if chosen else [x for gr in gres for x in gr["holders"]])[:6]
        return power, hl, how

    for m in muts:
        power, hl, how = eval_power(m)
        m["power"] = power
        m["holder_addrs"] = hl
        m["holder_how"] = how
        m["unknown_gate"] = power == "unknown"
        m["token_owner_gated"] = power == "token-holder"
        m["holders"] = [cr.holder_info(x) for x in hl]
    # upgrade mutator synthesized from proxy admin if not already via ABI (transparent proxies have no ABI mutator in impl)
    if proxy["kind"] in ("eip1967", "zos-unstructured") and not ev["uups"] and padm and not any(m["category"] == "upgrade" for m in muts):
        muts.append({"name": "(proxy admin upgrade)", "category": "upgrade", "gates": [{"type": "proxy-admin", "ref": "slot"}], "holder_addrs": [padm],
                     "holders": [proxy["admin"]], "holder_how": ["eip1967 admin slot"], "unknown_gate": False, "token_owner_gated": False, "effective": "yes",
                     "power": cr.simple_type(proxy["admin"])})
    if proxy["kind"] == "beacon" and proxy.get("beacon_owner"):
        muts.append({"name": "(beacon upgrade)", "category": "upgrade", "gates": [{"type": "beacon-owner", "ref": "beacon.owner()"}],
                     "holder_addrs": [proxy["beacon_owner"]["addr"]], "holders": [proxy["beacon_owner"]], "holder_how": ["beacon.owner()"],
                     "unknown_gate": False, "token_owner_gated": False, "effective": "yes", "power": cr.simple_type(proxy["beacon_owner"])})
    # UUPS upgrade mutator with abi (upgradeTo) already in muts via category 'upgrade'. For UUPS proxies where ABI came from impl it is there.
    # ---- lock linkage
    lock_fns = [x["name"] for x in surf.get("lock", [])]
    ev["lock_functions"] = lock_fns
    true_locks = {k: v for k, v in locks.items() if v}
    ev["lock_flags_true"] = true_locks
    for m in muts:
        gi = static.gates_for_function(src_all, m["name"]) if have_src else None
        text = ((gi or {}).get("body_full") or "")
        for mod in (gi or {}).get("modifiers", []) or []:
            md = static.find_funcs(src_all, re.split(r"[\s(]", mod)[0], kind="modifier")
            if md: text += md[-1]["body"]
        text = static.strip_comments(text)
        linked = [k for k in locks if re.search(rf"\b_?{re.escape(re.sub(r'^(is|get)', '', k, flags=re.I)[:1].lower() + re.sub(r'^(is|get)', '', k, flags=re.I)[1:])}\b", text, re.I) or re.search(rf"\b{re.escape(k)}\b", text)]
        m["lock_linked"] = linked
        m["frozen"] = any(locks[k] for k in linked)
        # private lock flags (no getter): a lock function that assigns `X = true`, where X is read by this setter's gate, and
        # that has a SUCCESSFUL historical call, freezes the setter (e.g. CryptopunksData.sealContract 2021-08-18).
        if not m["frozen"] and have_src and text:
            for lf in lock_fns:
                for fd in static.find_funcs(src_all, lf):
                    for var in re.findall(r"\b(\w+)\s*=\s*true\b", static.strip_comments(fd["body"])):
                        if re.search(rf"\b{re.escape(var)}\b", text):
                            ok = [t for t in (ev.get("history") or {}).get("txs", []) if t.get("method") == lf and t.get("status") in ("success", "ok") and t.get("category") == "lock"]
                            if ok:
                                m["frozen"] = True; m["lock_linked"] = linked + [f"{lf}()->{var}"]
                                m["frozen_by_history"] = min(t["timestamp"] for t in ok)[:10]
    ev["roles"] = {k: {"value": v["value"], "members": v["members"], "source": v.get("source")} for k, v in roles.items()}
    ev["mutators"] = [{k: v for k, v in m.items() if k not in ("holders", "groups")} | {"holders": [{kk: vv for kk, vv in h.items() if kk in ("addr", "type", "threshold", "n_owners", "bs_name", "ens", "delay_s")} | {"desc": cr.describe(h), "simple": cr.simple_type(h)} for h in m["holders"]]} for m in muts]
    # ---- class (direct)
    live = [m for m in muts if m["category"] in ("uri", "renderer", "upgrade") and not m["frozen"] and m.get("effective") != "no"]
    reasons = []
    cls = None
    CL = {"eoa": "eoa-mutable", "multisig": "multisig-mutable", "dao-or-timelock": "dao-or-timelock-mutable"}
    powers = [m["power"] for m in live]
    best = max([p_ for p_ in powers if p_ in RANK], key=lambda p_: RANK[p_], default=None)
    allm = [m for m in muts if m["category"] in ("uri", "renderer", "upgrade")]
    if best:
        cls = CL[best]
        reasons.append("live setters (" + best + "): " + ",".join(sorted({m["name"] for m in live if m["power"] == best})[:6]))
        if not have_src: reasons.insert(0, "unverified source; power via proxy admin / bytecode only")
    elif not have_src:
        cls = "unknown"
        reasons.append(("unverified source; selector hits: " + ",".join(ev["unverified_selector_hits"][:6])) if ev["unverified_selector_hits"] else "unverified source; no known setter selectors in bytecode")
        if owner: ev["likely_class_if_setters"] = cr.simple_type(ev["owner"])
    elif "unknown" in powers:
        cls = "unknown"; reasons.append("live setter with unresolved holder: " + ",".join(sorted({m["name"] for m in live if m["power"] == "unknown"})[:6]))
    else:
        cls = "immutable"
        if not allm: reasons.append("no uri/renderer/upgrade function in ABI and not a proxy")
        else:
            parts = []
            for m in allm:
                if m["frozen"]: parts.append(f"{m['name']}:frozen({','.join(m['lock_linked'])})")
                elif m.get("effective") == "no": parts.append(f"{m['name']}:inert(not read by tokenURI)")
                elif m["power"] == "token-holder": parts.append(f"{m['name']}:token-holder-only")
                else: parts.append(f"{m['name']}:renounced")
            reasons.append("; ".join(parts)[:300])
    ev["class_direct"] = cls; ev["class_reason"] = "; ".join(reasons)
    # ---- Art Blocks per-project override
    if have_src and artblocks.is_artblocks(abi):
        toks = [t for t in str((meta or {}).get("gallery_tokens") or "").split(";") if t.strip()]
        pids = sorted({int(float(t)) // 1_000_000 for t in toks})
        if not pids:
            npid = mlib.rpc_batch([call_obj(a, selector("nextProjectId()"))], f"{a}_nextpid")[0][0]
            n = word_int(npid["result"]) if npid["ok"] and npid["result"] != "0x" else None
            pids = sorted({x for x in (0, 1, 2, (n or 3) - 1, (n or 3) - 2) if x is not None and x >= 0 and (n is None or x < n)})
        ab = artblocks.extra(a, abi, pids)
        v3 = "projectStateData" in {f.get("name") for f in static.abi_funcs(abi)}
        ab["family"] = "V3 (admin-ACL gated default base URI)" if v3 else "V0/V1 (per-project artist gated projectBaseURI)"
        types = []
        if v3:
            acl = word_addr(R["adminACLContract()"]["result"]) if okv("adminACLContract()") else None
            ab["admin_acl"] = cr.holder_info(acl) if acl else None
            if ab["admin_acl"]: types.append(cr.simple_type(ab["admin_acl"])); ab["admin_acl_desc"] = cr.describe(ab["admin_acl"])
        else:
            types += [p_.get("artist_simple") for p_ in ab["projects"] if p_.get("artist_simple")]
        types = [t for t in types if t in RANK]
        n_locked = sum(1 for p_ in ab["projects"] if p_.get("locked"))
        ab["n_projects_checked"] = len(ab["projects"]); ab["n_script_locked"] = n_locked
        if types:
            best_t = max(types, key=lambda t: RANK[t])
            ev["class_direct"] = {"eoa": "eoa-mutable", "multisig": "multisig-mutable", "dao-or-timelock": "dao-or-timelock-mutable"}[best_t]
            ev["class_reason"] = (f"Art Blocks {ab['family']}; tokenURI = baseURI + id (off-chain API); {n_locked}/{len(ab['projects'])} sampled project scripts locked "
                                  f"(lock does not freeze projectBaseURI)")
        else:
            ev["class_direct"] = "unknown"; ev["class_reason"] = "Art Blocks: could not resolve project artists / admin ACL"
        ev["artblocks"] = ab
    ev["live_mutators"] = sorted({m["name"] for m in live})
    # ---- calls executed through Safe multisigs that hold power (invisible to top-level method filters)
    safes = []
    for h in ([ev.get("owner")] if ev.get("owner") else []) + [h for m in live for h in m["holders"]]:
        hh = h
        while hh and hh.get("type") == "contract-owned": hh = hh.get("controller")
        if hh and hh.get("type") in ("safe", "multisig-other") and hh["addr"] not in safes: safes.append(hh["addr"])
    if safes and depth == 0:
        sel_cat = {}
        for c_, lst in surf.items():
            for x in lst: sel_cat[x["selector"]] = c_
        for sg_ in ("transferOwnership(address)", "renounceOwnership()", "upgradeTo(address)", "upgradeToAndCall(address,bytes)", "grantRole(bytes32,address)", "revokeRole(bytes32,address)"):
            sel_cat.setdefault(selector(sg_), "ownership" if "wnership" in sg_ else ("role" if "Role" in sg_ else "upgrade"))
        ev.setdefault("history", {})["safe_calls"] = {sf: history.safe_calls(sf, a, sel_cat) for sf in safes[:3]}
        if any("error" in v for v in ev["history"]["safe_calls"].values()): ev["history"]["incomplete"] = True
    # ---- dependencies (one level)
    deps = []
    if depth == 0 and have_src:
        cand = {}
        for x in av:
            l = x["name"] + "()"
            if not okv(l): continue
            v = word_addr(R[l]["result"])
            if int(v, 16) == 0 or v in mlib.DEAD: continue
            nm = x["name"]
            in_tu = nm in tuids or nm.lstrip("_") in tuids
            if (static.DEP_NAME.search(nm) and not static.DEP_EXCL.search(nm)) or in_tu:
                cand[v] = {"via": f"{nm}()", "in_tokenuri_path": in_tu}
        for m in muts:  # setter name hints (setRenderer -> renderer getter) already covered; add setter arg addresses seen in history later
            pass
        for v, nm in static.hardcoded_addresses(src_all).items():
            if (nm in tuids or static.DEP_NAME.search(nm)) and not static.DEP_EXCL.search(nm) and v not in cand:
                cand[v] = {"via": f"constant {nm}", "in_tokenuri_path": nm in tuids}
        if ev.get("artblocks"):
            cand = {k_: v_ for k_, v_ in cand.items() if "egistry" in v_["via"]}
        for v, info in list(cand.items())[:6]:
            if v == a or (owner and v == owner): continue
            c2, _ = cr.get_code(v, f"{v}_code")
            if not c2 or c2 == "0x": continue
            try:
                d = analyze(v, depth=1)
            except Exception as e:  # noqa: BLE001
                d = {"address": v, "class_direct": "unknown", "class_reason": "analysis error " + repr(e)[:100]}
            setter_target = any(m["category"] == "renderer" and re.sub(r"^(set|update|change)_?", "", m["name"], flags=re.I).lower().rstrip("address") in info["via"].lower() for m in muts)
            if "ependencyRegistry" in info["via"] or "ependencyregistry" in info["via"]: info["in_tokenuri_path"] = True
            deps.append({"address": v, **info, "via_setter": setter_target, "analysis": slim(d)})
    ev["dependencies"] = deps
    ev["meta"] = meta or {}
    return ev


def slim(d):
    keep = ("address", "verified", "contract_name", "proxy", "owner", "admin_fn", "uups", "lock_views", "lock_flags_true", "lock_functions", "class_direct", "class_reason", "live_mutators", "mutators", "history", "unverified_selector_hits", "tokenuri_path")
    return {k: d.get(k) for k in keep if k in d}


def worst(classes):
    order = {"eoa-mutable": 4, "multisig-mutable": 3, "dao-or-timelock-mutable": 2}
    known = [c for c in classes if c in order]
    if known: return max(known, key=lambda c: order[c])
    if "unknown" in classes: return "unknown"
    return "immutable"


def ptr_power(ev):
    """strongest live power (eoa > multisig > dao-or-timelock) over mutators able to point tokenURI/art anywhere:
    URI string setters, upgrades, and renderer/descriptor address swaps. Data-only setters (addTrait, uploadImages...) are excluded."""
    best = None
    if ev.get("artblocks") and ev.get("class_direct") in CL_REV:
        best = CL_REV[ev["class_direct"]]
    for m in ev.get("mutators") or []:
        capable = m["category"] in ("uri", "upgrade") or (m["category"] == "renderer" and "address" in (m.get("inputs") or []))
        if capable and not m.get("frozen") and m.get("effective") != "no" and m.get("power") in RANK:
            if best is None or RANK[m["power"]] > RANK[best]: best = m["power"]
    return best


CL_REV = {"eoa-mutable": "eoa", "multisig-mutable": "multisig", "dao-or-timelock-mutable": "dao-or-timelock"}


def finalize(ev):
    cd = ev.get("class_direct")
    cdeps = [d["analysis"].get("class_direct") for d in ev.get("dependencies", [])]
    inpath = [d["analysis"].get("class_direct") for d in ev.get("dependencies", []) if d.get("in_tokenuri_path") or d.get("via_setter")]
    ev["class_deps_all"] = worst(cdeps) if cdeps else "none"
    ev["class_deps"] = worst(inpath) if inpath else "none"
    ev["class_final"] = worst([cd] + inpath) if cd else "unknown"
    pp = [ptr_power(ev)] + [ptr_power(d["analysis"]) for d in ev.get("dependencies", []) if d.get("in_tokenuri_path") or d.get("via_setter")]
    pp = [p_ for p_ in pp if p_]
    ev["pointer_power"] = max(pp, key=lambda p_: RANK[p_]) if pp else None
    return ev


def run_one(row, refresh=False):
    a = row["address"].lower()
    p = EVID / f"{a}.json"
    if p.exists() and not refresh:
        if REDO_INCOMPLETE:
            try:
                old = json.loads(p.read_text())
                if not ((old.get("history") or {}).get("incomplete") or old.get("roles_incomplete")): return "cached"
            except Exception: pass
        else:
            return "cached"
    try:
        ev = analyze(a, meta={k: (None if (isinstance(v, float) and v != v) else v) for k, v in row.items()})
        ev = finalize(ev)
    except Exception as e:  # noqa: BLE001
        ev = {"address": a, "error": repr(e)[:300], "trace": traceback.format_exc()[-1500:], "class_final": "unknown", "class_direct": "unknown", "class_reason": "analysis error"}
        p.with_suffix(".err.json").write_text(json.dumps(ev, indent=1))
        return "error"
    p.write_text(json.dumps(ev, indent=1, default=str))
    return "incomplete" if ((ev.get("history") or {}).get("incomplete") or ev.get("roles_incomplete")) else "ok"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd"); ap.add_argument("--workers", type=int, default=4); ap.add_argument("--limit", type=int); ap.add_argument("--only")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--redo-incomplete", action="store_true")
    ar = ap.parse_args()
    REDO_INCOMPLETE = ar.redo_incomplete
    EVID.mkdir(parents=True, exist_ok=True)
    t = pd.read_csv(ROOT / "data/mutability/targets.csv")
    if ar.only: t = t[t.address.isin([x.lower() for x in ar.only.split(",")])]
    if ar.limit: t = t.head(ar.limit)
    rows = t.to_dict("records")
    done = 0; t0 = time.time(); stats = {}
    with cf.ThreadPoolExecutor(ar.workers) as ex:
        futs = {ex.submit(run_one, r, ar.refresh): r for r in rows}
        for f in cf.as_completed(futs):
            s = f.result(); stats[s] = stats.get(s, 0) + 1; done += 1
            if done % 10 == 0 or s == "error":
                print(f"{time.strftime('%H:%M:%S')} {done}/{len(rows)} {stats} {time.time()-t0:.0f}s {futs[f]['address'] if s=='error' else ''}", flush=True)
    print("done", stats)
