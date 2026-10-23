"""Spam / infra heuristics (lightweight, flag-only; never drops rows)."""
import re
from collections import Counter

# Explicit non-collectible infrastructure (lower-case addresses). Short, hand-checked list.
INFRA_ADDR = {
    "0x57f1887a8bf19b14fc0df6fd9b2acc9af147ea85": "ENS BaseRegistrar (.eth names)",
    "0xd4416b13d2b3a9abae7acd5d6c2bbdbe25686401": "ENS NameWrapper",
    "0xc36442b4a4522e871399cd717abdd847ab11fe88": "Uniswap V3 positions",
    "0xbd216513d74c8cf14cf4747e6aaa6420ff64ee9e": "Uniswap V4 PositionManager",
    "0x22c1f6050e56d2876009903609a2cc3fef83b415": "POAP (attendance badges)",
    "0xd1e5b0ff1287aa9f9a268759062e4ab08b9dacbe": "Unstoppable Domains .crypto",
    "0x495f947276749ce646f68ac8c248420045cb7b5e": "OpenSea Shared Storefront (marketplace shared contract)",
    "0xd07dc4262bcdbf85190c01c996b4c06a461d2430": "Rarible ERC-1155 (marketplace shared contract)",
    "0x60f80121c31a0d46b5279700f9df786054aa5ee5": "Rarible ERC-721 (marketplace shared contract)",
}
INFRA_NAME = [  # matched on exact-ish names only; imitators are caught by spam rules
    (r"^ethereum name service$|^namewrapper$|^name ?wrapper$", "ENS"),
    (r"^(?!.*uniswap)\w[\w ]* v\d positions nft(-v\d)?$|^(?!.*uniswap).*positions nft-v\d$", "DEX liquidity-position NFT (fork)"),
    (r"^poap$|^poap\b.*(attendance|proof)|^proof of attendance", "POAP-like"),
    (r"^unstoppable domains$|^\.crypto$|^\.wallet$|^\.nft$", "naming service"),
    (r"^sablier\b.*(lockup|nft)|^llamapay|vesting (voucher|nft)", "vesting/streaming NFT"),
]

TLDS = "com|io|xyz|net|org|app|top|cc|club|site|vip|fun|live|online|gift|claims?|network|finance|co|me|info|fi|pro|global|win|rip|one|space|link|click|biz|dev|art|eth|nft|ltd|cloud|store|shop|tech|world|today|lol|gg|ai|ly|to|tv|us|eu|wtf|cash|money|exchange|capital|bio|run|vc|ink|page|wiki"
URL_RE = re.compile(r"(https?:|www\.|\w\.\s?(%s)\b)" % TLDS, re.I)
TEMPLATE_RE = re.compile(r"(mint pass|collector pass|membership pass|tickets?|genesis (pass|limited|original|oath)|\bkeys?\b|boosters?)"
                         r".*\b(official|originals?|origins?|limited|items?|20\d\d)\s*$", re.I)
STRONG_WORDS = re.compile(r"\b(claim|reward|rewards|voucher|airdrop|visit|giveaway|free ?mint|bonus|gift ?card|redeem|eligible|winner|prize|whitelist(ed)?|presale)\b", re.I)
BUREAU_RE = re.compile(r"^(verified|recognized|authenticated|authorized|validated|official|certified|approved|trusted|secured?|confirmed|registered|accredited|applied|processed|compliant)\s+\w+\s+(registry|reference|record|log|entry|statement|archive|receipt|document|index|ledger|certificate|manifest|directory|catalog|summary|report|filing)s?$", re.I)
EMOJI_OR_ODD = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def spam_flags(rows):
    """rows: list of dicts with name, symbol, holders_count, total_supply, creator. Adds spam_reasons (list),
    spam_suspect (bool), is_ens_or_infra, infra_reason."""
    name_ct = Counter((r["name"] or "").strip().lower() for r in rows if r["name"])
    hold_ct = Counter((r["standard"], int(r["holders_count"])) for r in rows)
    creator_ct = Counter(r["creator"] for r in rows if r.get("creator"))
    for r in rows:
        reasons, strong = [], False
        nm, sy = (r["name"] or ""), (r["symbol"] or "")
        txt = f"{nm} {sy}"
        nm_dups = name_ct[nm.strip().lower()] if nm else 0
        if URL_RE.search(txt):
            reasons.append("url_in_name"); strong = True
        if STRONG_WORDS.search(txt):
            reasons.append("spam_word"); strong = True
        if TEMPLATE_RE.search(nm.strip()) and nm_dups >= 1:
            reasons.append("mintpass_template_name"); strong = True
        if BUREAU_RE.match(nm.strip()):
            reasons.append("bureaucratic_template_name"); strong = True
        if r["standard"] == "ERC-1155" and hold_ct[("ERC-1155", int(r["holders_count"]))] >= 40:
            reasons.append("identical_holders_cluster_x%d" % hold_ct[("ERC-1155", int(r["holders_count"]))]); strong = True
        if "$" in txt:
            reasons.append("dollar_sign"); strong = True
        if re.search(r"uniswap.*positions", nm, re.I) and r["address"].lower() not in INFRA_ADDR:
            reasons.append("imitates_uniswap_positions"); strong = True
        if re.match(r"^\s*[!#*]", nm):
            reasons.append("leading_symbol_in_name"); strong = True
        if r.get("reputation") not in (None, "ok"):
            reasons.append(f"blockscout_reputation_{r['reputation']}"); strong = True
        if r.get("is_scam"):
            reasons.append("blockscout_is_scam"); strong = True
        weak = []
        h = int(r["holders_count"])
        ts = r.get("total_supply")
        if ts not in (None, "") and r["standard"] == "ERC-721":
            try:
                if int(ts) <= h * 1.02:
                    weak.append("supply_eq_holders")
            except ValueError:
                pass
        if not nm or not sy:
            weak.append("missing_name_or_symbol")
        if nm and name_ct[nm.strip().lower()] >= 10:
            reasons.append("duplicate_name_x%d" % name_ct[nm.strip().lower()]); strong = True
        elif nm and name_ct[nm.strip().lower()] >= 4:
            weak.append("duplicate_name_x%d" % name_ct[nm.strip().lower()])
        if r.get("creator") and creator_ct[r["creator"]] >= 5:
            weak.append("creator_has_%d_universe_contracts" % creator_ct[r["creator"]])
        if EMOJI_OR_ODD.search(txt):
            weak.append("emoji_in_name")
        reasons += weak
        r["spam_reasons"] = ";".join(reasons)
        r["spam_suspect"] = bool(strong or len(weak) >= 2)
        ie = INFRA_ADDR.get(r["address"].lower())
        if ie:  # hand-verified infra contracts are never spam, even if their name is duplicated by imitators
            r["spam_suspect"] = False
        if not ie:
            for pat, why in INFRA_NAME:
                if re.search(pat, nm.strip(), re.I):
                    ie = why; break
        r["is_ens_or_infra"] = bool(ie)
        r["infra_reason"] = ie or ""
    return rows
