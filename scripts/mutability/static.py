"""mutability static analysis of verified source + ABI: mutation surface (URI / renderer / script / upgrade / lock functions),
who gates each (owner / role / named address / token-owner / none), lock flags, tokenURI call targets, bytecode selector scan."""
import re
from keccak import selector

# ------------------------------------------------------------------ classification of function names
EXCL = re.compile(r"royalt|price|fee|supply|whitelist|allowlist|merkle|paus|sale|approval|operator|ownership|treasury|withdraw|payee|"
                  r"phase|window|limit|cap$|maxm|signer|verifier|oracle|vrf|keyhash|subscription|callback|proxyregistry|"
                  r"marketplace|filter|burn|stake|reward|vote|delegate|threshold|cost|discount|mintingcontract|minter|"
                  r"purchase|auction|bid|start|end(time|date)|time|date|receiver|recipient|balance|cooldown|duration|"
                  r"name$|symbol$|^setname|collectionname", re.I)
K_URI = re.compile(r"(base_?token_?uri|base_?uri|baseextension|token_?uri|metadata_?uri|^(set|update|change)_?uri|_uri$|^setURI|"
                   r"(set|update|change)\w*(uri|url)\b|(uri|url)s?$|ipfs|arweave|\bcid\b|contenthash|baseurl|hiddenuri|notrevealed|unrevealed|placeholder)", re.I)
K_REND = re.compile(r"(render|descriptor|metadata(address|contract|renderer)?$|^set_?metadata|generator|resolver|seeder|palette|template|"
                    r"\bsvg|image|artwork|^(set|update|change|add|remove)_?art\b|(set|update|add|remove)(trait|part|layer|asset|attribute|background|body|head|accessor|glasses|sprite|bitmap|pixel|glyph|font|css|html|js|script|canvas|chunk|dependency|dependencies|library|ethfs|filestore|logic|pointer|datastore|storage|code|project|json)|"
                    r"(trait|part|layer|asset|bitmap|sprite)s?$|dependency|script|^(set|update)_?data|^(set|update)_?contract$|uploadfile|storefile|writefile)", re.I)
K_UPG = re.compile(r"^(upgrade(to|toandcall|implementation)?|setimplementation|changeadmin|setbeacon|upgradebeacon|_authorizeupgrade|setproxyadmin|updateimplementation|setlogic|changeproxyadmin)$", re.I)
K_REVEAL = re.compile(r"^(reveal\w*|setreveal\w*|togglereveal\w*|set_?provenance\w*|setprovenancehash|set_?seed|setrandomseed|setoffset|setstartingindex|setrevealed)", re.I)
K_LOCK = re.compile(r"(lock|freeze|frozen|finali[sz]e|seal|permanent|immutab|renounce(?!ownership))", re.I)


HARD_EXCL = re.compile(r"artist_?address|artist_?name|additional_?payee|payee|max_?invocations|secondary_?market|royalt|price|^updateProjectLicense|website|hashes_?generated|aspect_?ratio", re.I)


def categorize(name):
    n = name
    if HARD_EXCL.search(n): return None
    if K_UPG.match(n): return "upgrade"
    if re.match(r"^(initialize|init)\w*$", n, re.I): return None
    if re.search(r"contract_?uri|contractmetadata|collection_?uri", n, re.I) and re.match(r"^(set|update|change)", n, re.I): return "contracturi"
    if K_LOCK.search(n) and re.match(r"^(lock|freeze|finali[sz]e|seal|make|toggle|set|renounce|permanent|disable)", n, re.I) and not K_URI.search(n.replace("Lock", "")) : return "lock"
    if K_REVEAL.match(n): return "reveal"
    if EXCL.search(n) and not (K_URI.search(n) or K_REND.search(n)): return None
    if re.match(r"^(set|update|change|replace|swap|override|add|append|upload|store|write|register|edit|modify|define|import|load|configure|assign|remove|delete|clear|toggle|publish|reset|migrate|enable|disable|create|new|lock|unlock)", n, re.I) or re.match(r"^(freeze|unfreeze)", n, re.I):
        if K_URI.search(n): return "uri"
        if K_REND.search(n): return "renderer"
    return None


# ------------------------------------------------------------------ source parsing
def match_paren(s, i, o="(", c=")"):
    d = 0
    for j in range(i, len(s)):
        if s[j] == o: d += 1
        elif s[j] == c:
            d -= 1
            if d == 0: return j
    return -1


def find_funcs(text, name, kind="function"):
    out = []
    for m in re.finditer(rf"\b{kind}\s+{re.escape(name)}\s*\(", text):
        a = m.end() - 1
        b = match_paren(text, a)
        if b < 0: continue
        # header until { or ;
        k = b + 1
        depth = 0
        while k < len(text):
            ch = text[k]
            if ch == "(": depth += 1
            elif ch == ")": depth -= 1
            elif depth == 0 and ch in "{;": break
            k += 1
        header = text[b + 1:k]
        body = ""
        if k < len(text) and text[k] == "{":
            e = match_paren(text, k, "{", "}")
            body = text[k + 1:e if e > 0 else k + 6000]
        out.append({"args": text[a + 1:b], "header": header, "body": body, "has_body": bool(body.strip())})
    return out


KEYW = {"public", "external", "internal", "private", "view", "pure", "payable", "virtual", "override", "nonpayable", "returns", "constant"}


def header_modifiers(header):
    h = re.sub(r"returns\s*\((?:[^()]|\([^()]*\))*\)", " ", header)
    h = re.sub(r"override\s*\((?:[^()]|\([^()]*\))*\)", " ", h)
    mods = []
    for m in re.finditer(r"([A-Za-z_]\w*)(\s*\((?:[^()]|\([^()]*\))*\))?", h):
        if m.group(1) in KEYW: continue
        mods.append((m.group(1), (m.group(2) or "").strip()))
    return mods


def static_strip(t):
    return strip_comments(t)


def strip_comments(t):
    t = re.sub(r"/\*.*?\*/", " ", t, flags=re.S)
    return re.sub(r"//[^\n]*", " ", t)


GATE_PATTERNS = [
    ("owner", re.compile(r"\bonlyOwner\b|_checkOwner\s*\(|msg\.sender\s*==\s*(_?owner)\b(\(\))?|(\b_?owner)\s*(\(\))?\s*==\s*(msg\.sender|_msgSender\(\))|_msgSender\(\)\s*==\s*owner\(\)|\bisOwner\s*\(\)|\bonlyContractOwner|\bonlyDeployer\b")),
]
ROLE_RE = re.compile(r"(?:onlyRole|_checkRole|_checkOnlyRole)\s*\(\s*([A-Za-z_][A-Za-z_0-9.]*)|hasRole\s*\(\s*([A-Za-z_][A-Za-z_0-9.]*)\s*,\s*(?:msg\.sender|_msgSender\(\))")
ADDR_EQ_RE = re.compile(r"(?:msg\.sender|_msgSender\(\)|tx\.origin)\s*==\s*([A-Za-z_]\w*)\s*(\(\s*\)|\([^)]|\[|\.)?|([A-Za-z_]\w*)\s*(\(\s*\)|\([^)]|\[|\.)?\s*==\s*(?:msg\.sender|_msgSender\(\))")
MAP_RE = re.compile(r"require\s*\(\s*!?\s*(\w+)\s*\[\s*(?:msg\.sender|_msgSender\(\))\s*\]|\b(\w+)\s*\[\s*(?:msg\.sender|_msgSender\(\))\s*\]")


def infer_gates(texts, modsrc, depth=0, seen=None):
    """texts: list of code fragments (function body head + header). modsrc: full source text for modifier lookup.
    -> list of {'type','ref'}"""
    seen = seen or set()
    gates = []
    for t in texts:
        if not t: continue
        t = strip_comments(t)
        if re.search(r"\bonlyOwner\b|_checkOwner\s*\(|\bisOwner\s*\(\)", t): gates.append({"type": "owner", "ref": "owner"})
        for m in ROLE_RE.finditer(t): gates.append({"type": "role", "ref": m.group(1) or m.group(2)})
        if re.search(r"\bownerOf\s*\(", t) and re.search(r"msg\.sender|_msgSender", t) or re.search(r"_isApprovedOrOwner|isApprovedOrOwner", t):
            gates.append({"type": "token-owner", "ref": "ownerOf"})
        for m in ADDR_EQ_RE.finditer(t):
            v = m.group(1) or m.group(3)
            trail = (m.group(2) if m.group(1) else m.group(4)) or ""
            if v in ("owner", "_owner") and trail in ("", "()", "( )"): gates.append({"type": "owner", "ref": "owner"})
            elif v in ("address", "this", "payable"): continue
            elif v == "ownerOf": gates.append({"type": "token-owner", "ref": "ownerOf"})
            elif trail in ("[", ".") or (trail.startswith("(") and trail not in ("()", "( )")): gates.append({"type": "perkey", "ref": v})
            elif v and v not in ("address", "this"): gates.append({"type": "named", "ref": v})
        for m in MAP_RE.finditer(t):
            gates.append({"type": "allowlist", "ref": m.group(1) or m.group(2)})
    return gates


def _uniq(lst):
    out = []
    for g in lst:
        if g not in out: out.append(g)
    return out


def gates_for_function(src, fname, argsig_hint=None):
    """Find best definition (with body) of function fname; return dict with modifiers, gates (flat), groups, body head.
    groups = list of OR-groups; the groups are ANDed (Solidity: every modifier / require must pass)."""
    defs = [d for d in find_funcs(src, fname) if d["has_body"]]
    if not defs: return None
    d = defs[-1]  # most-derived is usually last in flattened source
    mods = header_modifiers(d["header"])
    groups = []
    mod_names = []
    for mn, margs in mods:
        mod_names.append(mn + margs)
        if mn == "onlyOwner": groups.append([{"type": "owner", "ref": "owner"}]); continue
        if mn == "onlyRole":
            groups.append([{"type": "role", "ref": re.sub(r"[()\s]", "", margs)}]); continue
        mdefs = find_funcs(src, mn, kind="modifier")
        if mdefs:
            mb = mdefs[-1]["body"][:900]
            sub = infer_gates([mb], src)
            if not sub:
                for cm in re.finditer(r"\b(_?\w+)\s*\(\s*\)\s*;", mb):
                    fd = [x for x in find_funcs(src, cm.group(1)) if x["has_body"]]
                    if fd: sub += infer_gates([fd[-1]["body"][:900]], src)
            if sub: groups.append(_uniq(sub))
            elif re.search(r"msg\.sender|_msgSender|tx\.origin", strip_comments(mb)): groups.append([{"type": "unknown", "ref": mn}])
            # else: pure state-condition modifier (whenNotPaused, whenUnsealed, whenDescriptorNotLocked ...) - no access control
        else:
            low = mn.lower()
            if "owner" in low: groups.append([{"type": "owner", "ref": "owner"}])
            elif low in ("ifadmin", "onlyproxyadmin", "onlyadmin") or "admin" in low or "governance" in low: groups.append([{"type": "named", "ref": "admin"}])
            elif low in ("onlyproxy", "notdelegated", "whennotpaused", "nonreentrant", "nonreentrantview", "whenpaused"): continue
            else: groups.append([{"type": "unknown", "ref": mn}])
    # inline checks: one group per require/if statement that mentions the sender
    head = d["body"][:1500]
    for stmt in re.split(r";", strip_comments(head))[:12]:
        if re.search(r"msg\.sender|_msgSender|tx\.origin|\b_checkOwner\b|\b_checkRole\b", stmt):
            sub = infer_gates([stmt], src)
            if sub: groups.append(_uniq(sub))
    # internal check calls in the first lines (e.g. _onlyAdmin();)
    for cm in re.finditer(r"^\s*(_?(?:only|check|require|auth)\w*)\s*\(", d["body"][:300], re.M | re.I):
        fd = [x for x in find_funcs(src, cm.group(1)) if x["has_body"]]
        if fd:
            sub = infer_gates([fd[-1]["body"][:900]], src)
            if sub: groups.append(_uniq(sub))
    # de-duplicate groups
    ug = []
    for g in groups:
        if g not in ug: ug.append(g)
    flat = _uniq([x for g in ug for x in g])
    return {"modifiers": mod_names, "gates": flat, "groups": ug, "body_head": strip_comments(d["body"])[:300].strip(), "body_full": d["body"]}


# ------------------------------------------------------------------ ABI-level
def abi_funcs(abi):
    return [x for x in (abi or []) if x.get("type") == "function"]


def abi_events(abi):
    return [x for x in (abi or []) if x.get("type") == "event"]


def sig(f):
    from mlib import abi_sig
    return abi_sig(f)


def surface_from_abi(abi):
    """-> dict category -> list of {name, sig, selector, mutability, inputs}"""
    out = {}
    for f in abi_funcs(abi):
        if f.get("stateMutability") in ("view", "pure"): continue
        c = categorize(f["name"])
        if not c: continue
        s = sig(f)
        out.setdefault(c, []).append({"name": f["name"], "sig": s, "selector": selector(s), "inputs": [i["type"] for i in f.get("inputs", [])]})
    return out


LOCKISH_VIEW = re.compile(r"(locked|frozen|sealed|finalized|finalised|immutable|permanent|permanently\w*)(at|timestamp)?$|^(lock|freeze)$", re.I)


def lock_views(abi):
    """zero-arg views that return bool/uint and look like lock flags"""
    out = []
    for f in abi_funcs(abi):
        if f.get("stateMutability") in ("view", "pure") and not f.get("inputs") and len(f.get("outputs", [])) == 1 and LOCKISH_VIEW.search(f["name"]) \
                and f["outputs"][0]["type"] in ("bool", "uint256", "uint8", "uint64", "uint32", "uint128"):
            out.append({"name": f["name"], "selector": selector(f["name"] + "()"), "type": f["outputs"][0]["type"]})
    return out


DEP_NAME = re.compile(r"(render|descriptor|metadata|generator|resolver|seeder|palette|template|svg|image|art(work)?$|^art|script|ethfs|filestore|file_?store|"
                      r"dependency|asset|trait|part|layer|data(store)?$|^data|storage|logic|pointer|uri|html|font|sprite|bitmap|canvas)", re.I)
DEP_EXCL = re.compile(r"(owner|admin$|^admin|operator|proxyregistry|weth|vrf|coordinator|linktoken|treasury|receiver|royalty|marketplace|opensea|conduit|feed|beneficiary|payment|splitter|signer|verifier|dev$|devaddr)", re.I)


def address_views(abi):
    out = []
    for f in abi_funcs(abi):
        if f.get("stateMutability") in ("view", "pure") and not f.get("inputs") and len(f.get("outputs", [])) == 1 \
                and f["outputs"][0]["type"] == "address":
            out.append({"name": f["name"], "selector": selector(f["name"] + "()")})
    return out


def zero_arg_views(abi):
    return [f["name"] for f in abi_funcs(abi) if f.get("stateMutability") in ("view", "pure") and not f.get("inputs") and f.get("outputs")]


def tokenuri_targets(src):
    """identifiers called/used inside tokenURI (and uri) bodies, one hop into internal helper functions."""
    ids = set(); body_all = ""
    for fn in ("tokenURI", "uri"):
        for d in find_funcs(src, fn):
            if d["has_body"]: body_all += d["body"][:6000]
    body_all = strip_comments(body_all)
    # one hop
    helpers = set(re.findall(r"\b(_?[a-z]\w*)\s*\(", body_all))
    for h in list(helpers)[:25]:
        if h in ("require", "abi", "string", "bytes", "uint256", "keccak256", "revert", "address", "type", "Strings", "if", "return", "emit"): continue
        for d in find_funcs(src, h):
            if d["has_body"] and len(d["body"]) < 6000: body_all += "\n" + strip_comments(d["body"])
    for m in re.finditer(r"\b([A-Za-z_]\w*)\s*\.\s*[A-Za-z_]\w*\s*\(", body_all): ids.add(m.group(1))
    for m in re.finditer(r"\bI?[A-Z]\w*\s*\(\s*([A-Za-z_]\w*)\s*\)\s*\.", body_all): ids.add(m.group(1))
    for m in re.finditer(r"\b([A-Za-z_]\w*)\s*\(\s*\)\s*\.", body_all): ids.add(m.group(1))
    return ids, body_all


def hardcoded_addresses(src):
    """address constants/immutables and literal 0x..40 addresses outside comments."""
    s = strip_comments(src)
    out = {}
    for m in re.finditer(r"\baddress\s+(?:public\s+|private\s+|internal\s+)*(?:immutable|constant)\s+(?:public\s+|private\s+|internal\s+)*(\w+)\s*=\s*(?:address\()?(0x[0-9a-fA-F]{40})", s):
        out[m.group(2).lower()] = m.group(1)
    for m in re.finditer(r"\bI?[A-Z]\w*\s*(?:public\s+|private\s+|internal\s+)*(?:immutable|constant)\s+(?:public\s+|private\s+|internal\s+)*(\w+)\s*=\s*I?[A-Za-z]\w*\(\s*(0x[0-9a-fA-F]{40})\s*\)", s):
        out[m.group(2).lower()] = m.group(1)
    return out


# ------------------------------------------------------------------ bytecode selector scan (for unverified contracts)
BYTECODE_SIGS = [
    "setBaseURI(string)", "setBaseTokenURI(string)", "setTokenURI(uint256,string)", "setURI(string)", "setUri(string)", "setBaseUri(string)",
    "setRenderer(address)", "setRenderingContract(address)", "setRenderingContractAddress(address)", "setDescriptor(address)", "setMetadata(address)",
    "setMetadataURI(string)", "setContractURI(string)", "setNotRevealedURI(string)", "setHiddenURI(string)", "setBaseExtension(string)", "reveal()", "setRevealed(bool)",
    "setProvenanceHash(string)", "setProvenance(string)", "freezeMetadata()", "lockMetadata()", "freeze()", "lock()", "lockURI()", "freezeBaseURI()",
    "upgradeTo(address)", "upgradeToAndCall(address,bytes)", "setImplementation(address)", "changeAdmin(address)", "proxiableUUID()",
    "setScript(string)", "updateScript(string)", "setMetadataRenderer(address)", "setTokenRenderer(address)", "setArtist(address)", "setTokenURIPrefix(string)",
    "setBaseTokenURI(string)", "updateBaseURI(string)", "changeBaseURI(string)", "setPlaceholderURI(string)", "setGenerator(address)", "setSeeder(address)",
    "setPalette(address)", "setSVGRenderer(address)", "setDataContract(address)", "renounceOwnership()", "transferOwnership(address)", "owner()",
    "setTokenMetadata(uint256,string)", "setBaseURIForToken(uint256,string)", "updateTokenURI(uint256,string)", "setImageURI(string)", "setAnimationURL(string)",
    "lockDescriptor()", "lockMinter()", "lockSeeder()", "isDescriptorLocked()", "setDescriptorMinter(address)", "setArt(address)", "setTokenURIResolver(address)",
]
_SELMAP = {selector(s): s for s in BYTECODE_SIGS}


def bytecode_selectors(code_hex):
    b = bytes.fromhex(code_hex[2:]) if code_hex.startswith("0x") else bytes.fromhex(code_hex)
    i = 0; found = set()
    while i < len(b):
        op = b[i]
        if op == 0x63 and i + 5 <= len(b):
            found.add("0x" + b[i + 1:i + 5].hex()); i += 5; continue
        if 0x60 <= op <= 0x7f: i += op - 0x5f + 1; continue
        i += 1
    return sorted(_SELMAP[s] for s in found if s in _SELMAP)


def clone_target(code_hex):
    """EIP-1167 minimal proxy -> implementation address or None"""
    c = code_hex.lower()
    m = re.match(r"0x363d3d373d3d3d363d73([0-9a-f]{40})5af43d82803e903d91602b57fd5bf3", c)
    if m: return "0x" + m.group(1)
    m = re.match(r"0x3d602d80600a3d3981f3363d3d373d3d3d363d73([0-9a-f]{40})5af43d82803e903d91602b57fd5bf3", c)
    if m: return "0x" + m.group(1)
    return None
