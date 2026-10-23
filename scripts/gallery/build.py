"""Assemble the 'unplugged' artwork document for each gallery item from raw chain bytes.
Usage: build.py [slug ...]    (no args = all)    ->  data/gallery/<slug>/{chain/*.json, artwork.*, meta.json}
Evidence: every eth_call is stored in data/gallery/<slug>/chain/ (url, calldata, block, sha256, result)."""
import json, re, sys, html
import chain
from glib import *

REG = {}
def item(fn):
    REG[fn.__name__] = fn
    return fn

# ---------------------------------------------------------------- generic tokenURI -> JSON -> media
def from_json(slug, name, contract, tid, storage, j, how, info, call_desc, **extra):
    img, anim = j.get("image") or j.get("image_data"), j.get("animation_url")
    fields = dict(image=scheme_of(img), animation_url=scheme_of(anim), external_url=scheme_of(j.get("external_url")), json_how=how)
    meta = dict(collection=name, slug=slug, contract=contract, token_id=tid, chain_method=storage, chain_call=call_desc, json_name=j.get("name"),
                fields=fields, rpc=info, **extra)
    if anim and anim.startswith("data:text/html"):
        mime, b = decode_data_uri(anim)
        meta.update(medium="html+js (animation_url data URI)", primary="animation_url")
        return write_item(slug, meta, b, "html", HTML_CT)
    if img and img.lstrip().startswith("<svg"):
        fields["image"] = "inline-svg-in-json"
        meta.update(medium="svg (inline in JSON image field)", primary="image")
        return write_item(slug, meta, img, "svg", SVG_CT)
    if img and img.startswith("data:image/svg"):
        mime, b = decode_data_uri(img)
        meta.update(medium="svg (image data URI)", primary="image")
        if anim: meta["note_animation_url"] = f"animation_url is {anim[:80]}"
        return write_item(slug, meta, b, "svg", SVG_CT)
    if img and img.startswith("data:image/"):
        mime, b = decode_data_uri(img)
        meta.update(medium=f"{mime} (image data URI)", primary="image")
        return write_item(slug, meta, img_viewer(img), "html", HTML_CT)
    if img:
        meta.update(medium="offchain image", primary="image", note_offchain=img[:200])
        return write_item(slug, meta, img_viewer(img), "html", HTML_CT)
    raise RuntimeError("no image in json")

def tokenuri_item(slug, name, contract, tid, storage, sig="tokenURI(uint256)", **extra):
    u, info = smart_call(contract, sig, [tid], ["string"], slug, "tokenURI")
    if u is None: raise RuntimeError(f"{slug}: tokenURI reverted on public and fork RPC")
    j, how = parse_json_uri(u)
    if j is None: raise RuntimeError(f"{slug}: tokenURI is not a JSON data URI: {u[:80]}")
    return from_json(slug, name, contract, tid, storage, j, how, info, f"{sig.split('(')[0]}({tid})", **extra)

# ---------------------------------------------------------------- the simple on-chain classics
@item
def loot(): return tokenuri_item("loot", "Loot (for Adventurers)", "0xFF9C1b15B16263C61d017ee9F65C50e4AE0113D7", 1, "data URI: contract assembles SVG+JSON")

@item
def onchainmonkey(): return tokenuri_item("onchainmonkey", "OnChainMonkey", "0x960b7a6BCD451c9968473f7bbFd9Be826EFd549A", 1, "data URI: contract assembles SVG+JSON")

@item
def anonymice(): return tokenuri_item("anonymice", "Anonymice", "0xbad6186E92002E312078b5a1dAfd5ddf63d3f731", 1, "data URI: SVG layers stored in contract")

@item
def corruption(): return tokenuri_item("corruption", "Corruption(s)", "0x5BDf397bB2912859Dbd8011F320a222f79A28d2E", 1, "data URI: contract generates SVG")

@item
def brotchain(): return tokenuri_item("brotchain", "Brotchain", "0xd31fC221D2b0E0321C43E9F6824b26ebfFf01D7D", 1, "data URI: contract computes Mandelbrot bitmap (BMP)")

@item
def univ3_position(): return tokenuri_item("univ3-position", "Uniswap V3 Positions", "0xC36442b4a4522E871399CD717aBDD847Ab11FE88", 1, "data URI: NonfungibleTokenPositionDescriptor builds SVG")

@item
def zorbs(): return tokenuri_item("zorbs", "Zorbs", "0xCa21d4228cDCc68D4e23807E5e370C07577Dd152", 1, "data URI: contract assembles SVG gradient")

@item
def gnars(): return tokenuri_item("gnars", "Gnars", "0x558BFFF0D583416f7C4e380625c7865821b8E95C", 1500, "data URI: Nouns-style descriptor+art (SSTORE2)")

@item
def watchfaces(): return tokenuri_item("watchfaces", "Watchfaces World", "0x8d3b078D9D9697a8624d4B32743B02d270334AF1", 100, "data URI: contract-generated SVG")

@item
def checks(): return tokenuri_item("checks", "Checks (VV Originals)", "0x036721e5A769Cc48B3189EFbb9ccE4471E8A48B1", 100, "data URI: contract-generated SVG + animation_url HTML")

@item
def zero_mathcastles(): return tokenuri_item("zero-mathcastles", "ZERO by Mathcastles", "0x92096a1D7C864ed51e35ce4dcE15AA8183D143C3", 1, "data URI: contract-generated SVG")

@item
def nouns(): return tokenuri_item("nouns", "Nouns", "0x9C8fF314C9Bc7F6e59A9d9225Fb22946427eDC03", 1500, "data URI: NounsDescriptorV3 inflates SSTORE2 art (heavy gas)")

@item
def mooncat_lootprint(): return tokenuri_item("mooncat-lootprint", "MoonCatLootprint", "0x1e9385eE28c5C7d33F3472f732Fb08CE3ceBce1F", 1, "data URI: contract-generated SVG")

@item
def lilnouns(): return tokenuri_item("lilnouns", "Lil Nouns", "0x4b10701Bfd7BFEdc47d50562b76b436fbB5BdB3B", 1500, "data URI: Nouns-fork descriptor (heavy gas)")

@item
def autoglyphs():
    c = "0xd4e4078ca3495DE5B1d4dB434BEbc5a986197782"
    u, info = smart_call(c, "tokenURI(uint256)", [1], ["string"], "autoglyphs", "tokenURI")
    mime, b = decode_data_uri(u)
    meta = dict(collection="Autoglyphs", slug="autoglyphs", contract=c, token_id=1, chain_method="data URI (data:text/plain): contract draws ASCII art algorithmically",
                chain_call="tokenURI(1) / draw(1)", medium="ascii text (rendered in a <pre> viewer)", fields=dict(image=None), rpc=info, json_name="Autoglyph #1")
    return write_item("autoglyphs", meta, pre_viewer(b.decode(), fs=18), "html", HTML_CT)

@item
def chainfaces():
    c = "0x91047Abf3cAb8da5A9515c8750Ab33B4f1560a7A"; s = "chainfaces"
    face = chain.call(c, "getFace(uint256)", [1], ["string"], s, "getFace_1")
    bg = chain.call(c, "getBackgroundColor(uint256)", [1], ["uint256"], s, "getBackgroundColor_1")
    fg = chain.call(c, "getTextColor(uint256)", [1], ["uint256"], s, "getTextColor_1")
    tu = chain.call(c, "tokenURI(uint256)", [1], ["string"], s, "tokenURI_1")
    meta = dict(collection="ChainFaces", slug=s, contract=c, token_id=1, chain_method="contract getFace()/colors: text face generated on chain",
                chain_call="getFace(1), getBackgroundColor(1), getTextColor(1)", medium="ascii text (rendered in a <pre> viewer)",
                fields=dict(image=None, tokenURI_scheme=scheme_of(tu)), tokenURI_value=tu, rpc={"rpc": "public"},
                note="tokenURI() points at an HTTP API (chainfacesrinkeby.azurewebsites.net) although getFace() draws on chain")
    return write_item(s, meta, pre_viewer(face, bg="#%06x" % bg, fg="#%06x" % fg, fs=40), "html", HTML_CT)

@item
def cryptopunks():
    c = "0x16F5A35647D6F03D5D3da7b35409D65ba03aF3B2"; s = "cryptopunks-data"
    u = chain.call(c, "punkImageSvg(uint16)", [7804], ["string"], s, "punkImageSvg_7804")
    attrs = chain.call(c, "punkAttributes(uint16)", [7804], ["string"], s, "punkAttributes_7804")
    mime, b = decode_data_uri(u)
    meta = dict(collection="CryptoPunks (CryptopunksData contract)", slug=s, contract=c, token_id=7804, chain_method="SSTORE-packed sprite data + palette in CryptopunksData; punkImageSvg() builds SVG",
                chain_call="punkImageSvg(7804)", medium="svg (returned as data:image/svg+xml;utf8 string)", fields=dict(image="data:image/svg+xml"), attributes=attrs, rpc={"rpc": "public"},
                note="The original CryptoPunks contract (0xb47e..BBB) has no tokenURI/image; the on-chain art lives in the later CryptopunksData contract.")
    return write_item(s, meta, b, "svg", SVG_CT)

@item
def blitmap():
    c = "0x8d04a8c79cEB0889Bdd12acdF3Fa9D207eD3Ff63"; s = "blitmap"
    svg = chain.call(c, "tokenSvgDataOf(uint256)", [1], ["string"], s, "tokenSvgDataOf_1")
    tu = chain.call(c, "tokenURI(uint256)", [1], ["string"], s, "tokenURI_1")
    meta = dict(collection="Blitmap", slug=s, contract=c, token_id=1, chain_method="contract stores 16x16 bitmap bytes (tokenDataOf); tokenSvgDataOf() builds SVG",
                chain_call="tokenSvgDataOf(1)", medium="svg", fields=dict(image="svg via tokenSvgDataOf", tokenURI_scheme=scheme_of(tu)), tokenURI_value=tu, rpc={"rpc": "public"},
                note="tokenURI() is an HTTPS API URL (api.blitmap.com); the art itself is on chain")
    return write_item(s, meta, svg, "svg", SVG_CT)

@item
def avastars():
    c = "0xF3E778F839934fC819cFA1040AabaCeCBA01e049"; s = "avastars"
    svg = chain.call(c, "renderAvastar(uint256)", [1], ["string"], s, "renderAvastar_1")
    tu = chain.call(c, "tokenURI(uint256)", [1], ["string"], s, "tokenURI_1")
    meta = dict(collection="Avastars", slug=s, contract=c, token_id=1, chain_method="trait SVG art stored in contract (getTraitArtById); renderAvastar() composes SVG",
                chain_call="renderAvastar(1)", medium="svg", fields=dict(image="svg via renderAvastar", tokenURI_scheme=scheme_of(tu)), tokenURI_value=tu, rpc={"rpc": "public"},
                note="tokenURI() is an HTTPS URL (avastars.io/metadata/1); the art itself is on chain")
    return write_item(s, meta, svg, "svg", SVG_CT)

@item
def chainrunners():
    c = "0x97597002980134beA46250Aa0510C9B90d87A587"; s = "chain-runners"
    rend = chain.call(c, "renderingContractAddress()", [], ["address"], s, "renderingContractAddress")
    tu = chain.call(c, "tokenURI(uint256)", [1], ["string"], s, "tokenURI_1")
    u, info = smart_call(rend, "onChainTokenURI(uint256)", [1], ["string"], s, "onChainTokenURI_1")
    j, how = parse_json_uri(u)
    return from_json(s, "Chain Runners", c, 1, "data URI via renderer.onChainTokenURI(): layers in on-chain renderer", j, how, info, "ChainRunnersOffChainDNARenderer.onChainTokenURI(1)",
                     tokenURI_value=tu, note="tokenURI() returns an HTTPS API URL (api.chainrunners.xyz); an on-chain renderer exists and is called here")

@item
def terraforms():
    c = "0x4E1f41613c9084FdB9E34E11fAE9412427480e56"; s = "terraforms"
    h, info = smart_call(c, "tokenHTML(uint256)", [1], ["string"], s, "tokenHTML_1")
    tu = chain.call(c, "tokenURI(uint256)", [1], ["string"], s, "tokenURI_1")
    j, how = parse_json_uri(tu)
    meta = dict(collection="Terraforms", slug=s, contract=c, token_id=1, chain_method="contract tokenHTML(): HTML+JS+CSS assembled on chain (animated)", chain_call="tokenHTML(1)",
                medium="html+js", fields=dict(image=scheme_of(j.get("image")), animation_url=scheme_of(j.get("animation_url")), animation_url_value=j.get("animation_url")), rpc=info, json_name=j.get("name"),
                note="tokenURI.animation_url is https://tokens.mathcastles.xyz/terraform (HTTP); tokenHTML() is the on-chain animated artwork")
    return write_item(s, meta, h, "html", HTML_CT)

# ---------------------------------------------------------------- Art Blocks via the on-chain Generator
AB_GEN = "0x953D288708bB771F969FCfD9BA0819eF506Ac718"
AB_V0 = "0x059EDD72Cd353dF5106D2B9cC5ab83a52287aC3a"; AB_V1 = "0xa7d8d9ef8D8Ce8992Df33D8b8CF4Aebabd5bD270"; AB_V3 = "0x99a9B7c1116f9ceEB1652de04d5969CcE509B069"
AB_PROJECTS = [0, 1, 2, 8, 12, 13, 22, 23, 32, 76, 78, 136, 138, 145, 160, 161, 163, 172, 233, 385, 391, 457, 487]

def ab_item(pid):
    core = AB_V0 if pid < 3 else AB_V1 if pid < 374 else AB_V3
    s = f"ab-{pid}"; tid = pid * 1000000
    det = chain.call(core, "projectDetails(uint256)", [pid], ["string", "string", "string", "string", "string"], s, "projectDetails")
    if core == AB_V3:
        sd = chain.call(core, "projectScriptDetails(uint256)", [pid], ["string", "string", "uint256"], s, "projectScriptDetails")
        stype, scount = sd[0], sd[2]
    else:
        si = chain.call(core, "projectScriptInfo(uint256)", [pid], ["string", "uint256", "bool", "string", "bool", "bool"], s, "projectScriptInfo")
        stj = json.loads(si[0]) if si[0] else {}
        stype = (stj.get("type") or "p5js?(legacy: no type field)") + ("@" + stj["version"] if stj.get("version") else ""); scount = si[1]
    script_parts = [chain.call(core, "projectScriptByIndex(uint256,uint256)", [pid, i], ["string"], s, f"projectScriptByIndex_{i}") for i in range(scount)]
    thash = None
    try:
        thash = chain.call(core, "tokenIdToHash(uint256)", [tid], ["bytes32"], s, "tokenIdToHash")
    except Exception:
        pass
    html_, info = smart_call(AB_GEN, "getTokenHtml(address,uint256)", [core, tid], ["string"], s, "getTokenHtml")
    if html_ is None: raise RuntimeError("generator failed")
    # cross-check: the project script (from the core contract) must appear inside the generator output
    full_script = "".join(p for p in script_parts if p)
    contains = bool(full_script) and (full_script in html_ or (script_parts[0][:200] in html_ if script_parts and script_parts[0] else False))
    meta = dict(collection=f"Art Blocks #{pid} {det[0]} ({det[1]})", slug=s, contract=core, token_id=tid, project_id=pid, project_name=det[0], artist=det[1], script_type=stype,
                script_count=scount, script_bytes=sum(len(p.encode()) for p in script_parts if p), token_hash=("0x" + thash.hex()) if thash else None,
                chain_method="Art Blocks: project script on core contract + libraries from on-chain Dependency Registry, assembled by on-chain Generator getTokenHtml()",
                chain_call=f"GenArt721Generator.getTokenHtml({core}, {tid}) @ {AB_GEN}", medium=f"html+js ({stype})", fields={}, rpc=info,
                generator_embeds_project_script=contains,
                note="tokenURI of the core contract is an HTTPS URL on the Art Blocks API; B uses the on-chain Generator output instead (the honest on-chain test)")
    return write_item(s, meta, html_, "html", HTML_CT)

# ---------------------------------------------------------------- discovery-scan finds (on-chain data-URI collections found by scanning the census universe)
EXTRA = {  # slug: (display name, address, note)
 "argonauts": ("Argonauts", "0x387C41B0B2F1128dE44dB1Bcf8baad085f26392C"), "trace": ("Trace", "0x691bd9fd56fDD24831b3C3068d4a10EC00341e40"),
 "the-simulation": ("The Simulation", "0xc3706195fF60658585B58716717ee7Acc5ebcA60"), "credited-punks": ("Credited Punks", "0x5E9F813Aa8D09b744a0E557D06776a484f64446a"),
 "bit-beach-club": ("Bit Beach Club", "0x54Bc3c7E13ec1F591286dC95908Ae8fbC9C09273"), "chillorbs": ("ChillOrbs", "0x6C6789fd71D819D2f18f4796Ae161a49FE8c325b"),
 "slabscollection": ("slabscollection", "0xdC7eE2E7DFa298179164919B79B3fb79b1d13712"), "x-y-z": ("X-Y-Z", "0xB77c7520574795d4Cb5766920044A2bFDEA6AD1F"),
 "clickbait": ("ClickBait", "0xb40E4620d3A2bfe0259B409840aDCdD5D78AEe02"), "etherean": ("Etherean", "0x38251dbc366D8069d9310dC79917feE6a5403002"),
 "quantum-echoes": ("Quantum Echoes", "0x5A5c9c3Cd186D95eFF4dA56ce48a173C7e46455A"), "merge": ("merge.", "0xc3f8a0F5841aBFf777d3eefA5047e8D413a1C9c0"),
 "bitmappunks": ("BitmapPunks", "0xBBBBA1eE822c9B8fc134deA6aDfC26603a9cBBBB"), "every-icon": ("Every Icon", "0xF9a423b86AfBF8Db41b4469AB3fdCB9D5f4a0D1A"),
 "infinites": ("Infinites", "0x327450151c11D54442A0c974b25DD12Dd902A722"), "proof-of-stake-pages": ("Proof Of Stake Pages", "0x5bF5BCc5362F88721167C1068b58C60caD075aAc"),
 "save-eth": ("SAVE ETH", "0x355919971B379cA9741fF29939C4ba716f873560"), "mirror": ("mirror", "0x44e6dAA3FB787D97C44ff4492343A62e357f9347"),
 "fat-punks": ("Fat Punks", "0x40b832368613B74e6114f01c9256BcCeF401894C"), "wild-pitch": ("Wild Pitch", "0x5ACe36eFA5FD7c80565a3bf686181fA1F3f6F26d"),
 "bleeps": ("BLEEPS", "0xd3cB32E04bcDB3a8dF0F6FC43fD3fCD9DE8A5d4e"), "heraldia": ("Heraldia", "0x11A7E4e1Ac9B2Fc5D0EFF2B9c8d8F4f89d6a5C52"),
 "glyphpunks": ("Glyphpunks", "0x104Fc2"), "pixelchain-256": ("PixelChain 256", "0x3D578d"), "syntax": ("Syntax", "0xC05717"),
 "noisies": ("NOISIES", "0x106356"), "galaxy-seeds": ("Galaxy Seeds", "0x1A6bb2"), "worlds": ("Worlds", "0x69525D"), "scapes": ("Scapes", "0xb7def6"),
 "erosion": ("EROSION", "0xbD07f4"), "flipmap": ("Flipmap", "0x0E4B8e"), "open-palette": ("Open Palette", "0x1308c1"),
}
_CLS = {json.loads(l)["address"].lower(): json.loads(l) for l in open(chain.GAL / "discovery/classified.jsonl")} if (chain.GAL / "discovery/classified.jsonl").exists() else {}
def _resolve(prefix):
    if prefix.lower() in _CLS: return prefix.lower()
    m = [a for a in _CLS if a.startswith(prefix[:8].lower())]
    return m[0] if len(m) == 1 else None
def extra_item(slug):
    name, addr = EXTRA[slug][:2]
    addr = _resolve(addr) or addr
    row = _CLS.get(addr.lower())
    if row is None:
        raise RuntimeError(f"{slug}: address {addr} not in discovery classification")
    return tokenuri_item(slug, name, chain.checksum(addr), row["tid"], "data URI (contract-assembled; technique labelled from verified source flags)")
for _s in EXTRA:
    REG[_s.replace("-", "_")] = (lambda s=_s: extra_item(s))

# ---------------------------------------------------------------- ERC-1155 (uri(id) data URIs)
E1155 = {"proof-of-merge": ("Proof of Merge", "0xF4Dd946D1406e215a87029db56C69e1Bcf3e1773"), "infinity-1155": ("Infinity", "0x0082578eedFD01ec97c36165469D012D6DC257CC"),
         "provably-rare-gem": ("Provably Rare Gem", "0xC67DED0eC78b849e17771b2E8a7e303B4dAd6dD4"), "floadmaps": ("Floadmaps", "0x1F95CFfd675F2a63455Cf693bA6C1AF63E73600A"),
         "mangled-drone-crow": ("Mangled Drone Crow", "0xd3a0B315023243632A15Fd623D6f33314193df4e"), "air-rune": ("Air Rune", "0xFa1A07056C48DCbA4B5E9e71aACC6aa791A93929"),
         "generative-exploration": ("Generative Exploration Edition (Reflections)", "0xD1AE247309a89953B06b18446a3f54dB453BA065")}
_C55 = {json.loads(l)["address"].lower(): json.loads(l) for l in open(chain.GAL / "discovery/scan1155.jsonl")} if (chain.GAL / "discovery/scan1155.jsonl").exists() else {}
def erc1155_item(slug):
    name, addr = E1155[slug]; row = _C55[addr.lower()]; tid = row["tid"]
    u, info = smart_call(addr, "uri(uint256)", [tid], ["string"], slug, "uri")
    if u is None: raise RuntimeError("uri reverted")
    u = u.replace("{id}", "%064x" % tid)
    j, how = parse_json_uri(u)
    return from_json(slug, name + " [ERC-1155]", addr, tid, "ERC-1155 uri(): data URI (contract-assembled)", j, how, info, f"uri({tid})")
for _s in E1155:
    REG[_s.replace("-", "_")] = (lambda s=_s: erc1155_item(s))

for _p in AB_PROJECTS:
    REG[f"ab_{_p}"] = (lambda p=_p: ab_item(p))

if __name__ == "__main__":
    names = sys.argv[1:] or list(REG)
    ok, bad = [], []
    for n in names:
        try:
            m = REG[n]()
            ok.append(n); print("OK ", n, m["medium"], m["artwork_bytes"], m.get("declared", {}).get("load"))
        except Exception as e:  # noqa
            bad.append((n, str(e)[:200])); print("ERR", n, str(e)[:200])
    print(len(ok), "ok", len(bad), "failed")
