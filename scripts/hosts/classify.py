"""Stage 4: join dependants + DNS + RDAP + HTTP evidence into one verdict per host.
Outputs data/hosts/hosts.csv/.parquet (public; claimable detail columns redacted to platform-level classes) and
WITHHELD_HOSTS_FILE (default: withheld_hosts.csv) (full detail for claimable / available / re-registered hosts; gitignored)."""
import json, os, re, sys, pathlib
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import *

WITHHELD_HOSTS_FILE = pathlib.Path(os.environ.get("WITHHELD_HOSTS_FILE", "withheld_hosts.csv"))
WITHHELD_HOSTS_FILE.parent.mkdir(parents=True, exist_ok=True)

# shared platforms: the host's registrable domain belongs to the platform, the *name* is the claimable resource.
PLATFORMS = [  # (suffix regex, label)
    (r"\.s3[.-]([a-z0-9-]+\.)?amazonaws\.com(\.cn)?$|^s3[.-]([a-z0-9-]+\.)?amazonaws\.com$", "aws-s3"),
    (r"\.s3-website[.-][a-z0-9.-]+\.amazonaws\.com$", "aws-s3-website"),
    (r"\.cloudfront\.net$", "aws-cloudfront"), (r"\.elasticbeanstalk\.com$", "aws-beanstalk"),
    (r"\.herokuapp\.com$", "heroku"), (r"\.herokudns\.com$", "heroku"),
    (r"\.github\.io$", "github-pages"), (r"\.vercel\.app$", "vercel"), (r"\.now\.sh$", "vercel"),
    (r"\.netlify\.app$", "netlify"), (r"\.netlify\.com$", "netlify"),
    (r"\.azurewebsites\.net$", "azure-appservice"), (r"\.blob\.core\.windows\.net$", "azure-blob"),
    (r"\.azureedge\.net$", "azure-cdn"), (r"\.cloudapp\.azure\.com$|\.cloudapp\.net$", "azure-vm"),
    (r"\.trafficmanager\.net$", "azure-tm"),
    (r"\.firebaseapp\.com$|\.web\.app$", "firebase-hosting"), (r"(^|\.)storage\.googleapis\.com$", "gcs"),
    (r"\.appspot\.com$", "gae"), (r"\.run\.app$", "cloud-run"),
    (r"\.pages\.dev$", "cloudflare-pages"), (r"\.workers\.dev$", "cloudflare-workers"), (r"\.r2\.dev$", "cloudflare-r2"),
    (r"\.digitaloceanspaces\.com$", "do-spaces"), (r"\.ondigitalocean\.app$", "do-apps"),
    (r"\.mypinata\.cloud$", "pinata-dedicated-gateway"), (r"(^|\.)pinata\.cloud$", "pinata"),
    (r"\.on\.fleek\.co$|\.ipfs\.fleek\.co$|\.fleek\.cool$", "fleek"),
    (r"\.onrender\.com$", "render"), (r"\.fly\.dev$", "fly"), (r"\.railway\.app$", "railway"),
    (r"\.glitch\.me$", "glitch"), (r"\.repl\.co$|\.replit\.app$|\.replit\.dev$", "replit"),
    (r"\.ngrok\.io$|\.ngrok-free\.app$|\.ngrok\.app$", "ngrok"), (r"\.surge\.sh$", "surge"),
    (r"\.wixsite\.com$", "wix"), (r"\.blogspot\.com$", "blogger"), (r"\.webflow\.io$", "webflow"),
    (r"\.ghost\.io$", "ghost"), (r"\.gitbook\.io$", "gitbook"), (r"\.bubbleapps\.io$", "bubble"),
    (r"\.supabase\.co$", "supabase"), (r"\.backblazeb2\.com$", "backblaze"), (r"\.wasabisys\.com$", "wasabi"),
    (r"\.linodeobjects\.com$", "linode-objects"), (r"\.googleusercontent\.com$", "google-usercontent"),
    (r"\.discordapp\.(com|net)$", "discord-cdn"), (r"\.imgur\.com$", "imgur"), (r"\.ipfs\.(w3s\.link|dweb\.link|nftstorage\.link|cf-ipfs\.com)$", "ipfs-subdomain-gateway"),
]
PLAT_RE = [(re.compile(r, re.I), l) for r, l in PLATFORMS]
GATEWAYS = {"ipfs.io", "gateway.ipfs.io", "cloudflare-ipfs.com", "dweb.link", "gateway.pinata.cloud", "nftstorage.link", "w3s.link",
            "ipfs.infura.io", "infura-ipfs.io", "ipfs.fleek.co", "gateway.ipfs.io", "arweave.net", "ar-io.net", "ipfs.filebase.io",
            "cf-ipfs.com", "ipfs.4everland.io", "4everland.io", "gateway.lighthouse.storage", "ipfs.eth.aragon.network", "ipfs.cf-ipfs.com",
            "quicknode.quicknode-ipfs.com", "ipfs.runfission.com", "hardbin.com", "ipfs.dweb.link", "ipfs.w3s.link", "ipfs.nftstorage.link"}

PARK_BODY = re.compile(r"sedo\.com|sedoparking|afternic|dan\.com|hugedomains|domain (is |may be )?for sale|buy this domain|this domain (name )?is (for sale|available)|"
                       r"domain (has )?expired|parked (free|domain)|parkingcrew|bodis\.com|above\.com|undeveloped\.com|namebright|domainmarket|"
                       r"sav\.com|squadhelp|brandbucket|godaddy\.com/domainsearch|park-?ing|this web page is parked|domain parking|"
                       r"lander|inquire about this domain|make an offer", re.I)
PARK_NS = re.compile(r"sedoparking|parkingcrew|bodis|above\.com|dan\.com|hugedomains|afternic|domaincontrol.*park|parklogic|undeveloped|smartname|"
                     r"namebrightdns|cashparking|dsredirection|ztomy|trafficz|sav\.com", re.I)
PARK_URL = re.compile(r"sedo\.com|afternic\.com|dan\.com|hugedomains\.com|godaddy\.com|parkingcrew|bodis|undeveloped|sav\.com|squadhelp|brandbucket|/lander|"
                      r"domainmarket|buydomains\.com|namecheap\.com/domains|porkbun\.com|dynadot\.com|spaceship\.com", re.I)

# (platform label, regex on status+body, fingerprint name, claimable?)
FP = [
    ("aws-s3", r"<Code>NoSuchBucket</Code>", "s3-NoSuchBucket", True),
    ("aws-s3-website", r"NoSuchBucket|The specified bucket does not exist", "s3-website-NoSuchBucket", True),
    ("gcs", r"<Code>NoSuchBucket</Code>|The specified bucket does not exist", "gcs-NoSuchBucket", True),
    ("do-spaces", r"<Code>NoSuchBucket</Code>", "do-spaces-NoSuchBucket", True),
    ("heroku", r"no-such-app|No such app|There's nothing here, yet", "heroku-no-such-app", True),
    ("github-pages", r"There isn't a GitHub Pages site here|<title>Site not found", "github-pages-404", True),
    ("vercel", r"DEPLOYMENT_NOT_FOUND|The deployment could not be found on Vercel", "vercel-DEPLOYMENT_NOT_FOUND", True),
    ("netlify", r"Not Found - Request ID", "netlify-not-found", True),
    ("firebase-hosting", r"Site Not Found|Firebase Hosting Setup Complete", "firebase-site-not-found", True),
    ("cloudflare-pages", r"There is nothing here yet|Nothing is here yet", "pages-dev-nothing-here", True),
    ("surge", r"project not found", "surge-not-found", True),
    ("azure-appservice", r"Error 404 - Web app not found|Microsoft Azure App Service - Welcome", "azure-webapp-404", False),
    ("*", r"Fastly error: unknown domain", "fastly-unknown-domain", True),
    ("*", r"Sorry, this shop is currently unavailable", "shopify-unavailable", True),
    ("*", r"The gods are wise, but do not know of the site which you seek|404 error unknown site!", "pantheon-unknown-site", True),
    ("*", r"Repository not found|Domain is not configured", "bitbucket/ghost-unconfigured", True),
    ("pinata-dedicated-gateway", r"Gateway not found|gateway.*(does not exist|not found)|NOT_FOUND_GATEWAY", "pinata-gateway-gone", None),
    ("fleek", r"not found|Site not found", "fleek-not-found", None),
    ("ngrok", r"ERR_NGROK_3200|tunnel .* not found|offline", "ngrok-offline", False),
]
FP = [(p, re.compile(r, re.I), n, c) for p, r, n, c in FP]
NXDOMAIN_CLAIMABLE = {"azure-appservice", "azure-blob", "azure-cdn", "azure-vm", "azure-tm", "aws-beanstalk", "heroku", "firebase-hosting",
                      "github-pages", "vercel", "netlify", "surge"}  # NXDOMAIN on the platform name = no resource registered under it (checked below)
EXPECT = {"metadata": ("json", "text/plain", "octet"), "image": ("image", "octet", "svg", "video"), "animation_url": ("html", "video", "audio", "image", "octet", "model")}


def plat(host):
    for r, l in PLAT_RE:
        if r.search(host):
            return l
    return None


def load(p):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def http_summary(host):
    d = RAW / safe(host)
    out = {}
    for k in ("root", "root_http", "nft0", "nft1"):
        j = load(d / f"http_{k}.json")
        if j is not None:
            out[k] = j
    return out


def content_ok(rec, url_role_hint=""):
    """True if an NFT URL response looks like what an NFT URL should return (JSON / image / media), False if HTML page or error."""
    if rec is None or "status" not in rec or not (200 <= rec["status"] < 300):
        return None
    ct = (rec.get("headers", {}).get("Content-Type") or rec.get("headers", {}).get("content-type") or "").lower()
    head = (rec.get("body_head") or "")[:300].lstrip().lower()
    if "html" in ct or head.startswith("<!doctype html") or head.startswith("<html"):
        return False if url_role_hint in ("metadata", "image") else None
    return True


def main():
    pr = pd.read_parquet(HOSTS_DIR / "host_priority.parquet")
    dns = pd.read_parquet(HOSTS_DIR / "dns.parquet").set_index("host")
    nsd = pd.read_parquet(HOSTS_DIR / "dns_ns.parquet").set_index("reg_domain")
    rd = pd.read_parquet(HOSTS_DIR / "rdap.parquet").set_index("reg_domain") if (HOSTS_DIR / "rdap.parquet").exists() else pd.DataFrame()
    deps = pd.read_parquet(HOSTS_DIR / "host_deps.parquet")
    ghp = RAW / "_domains" / "github_user_check.json"
    gh = json.loads(ghp.read_text()) if ghp.exists() else {}
    rows = []
    for r in pr.itertuples():
        h = r.host
        row = dict(host=h, priority_rank=r.priority_rank, n_collections=r.n_collections, holders_affected=int(r.holders), roles=r.roles,
                   strata=r.strata, min_deploy_year=r.min_deploy_year, top_collections=r.top_collections, sample_urls=" | ".join(r.urls))
        pl = plat(h)
        row["platform"] = pl or ("ipfs-or-arweave-gateway" if h in GATEWAYS else None)
        row["is_gateway"] = h in GATEWAYS
        rdom = reg_domain(h)
        row["reg_domain"] = rdom
        notes = []
        if is_ip(h):
            row.update(verdict="unknown", verdict_reason="ip-literal host (not probed)")
            rows.append(row)
            continue
        d = dns.loc[h].to_dict() if h in dns.index else None
        if d is None:
            row.update(verdict="unknown", verdict_reason="no DNS data")
            rows.append(row)
            continue
        row.update(dns_a_rcode=d["dns_a_rcode"], dns_resolves=d["dns_resolves"], cname_chain=d["cname_chain"])
        cn_final = d["cname_final"] if isinstance(d["cname_final"], str) else None
        cpl = plat(cn_final) if cn_final else None
        if cpl and not pl:
            row["platform"] = f"cname->{cpl}"
        # registration data
        own_domain = pl is None and not row["is_gateway"] or (pl in (None,) and True)
        reg_state, rereg = None, False
        if rdom and not pl and len(rd) and rdom in rd.index:
            x = rd.loc[rdom]
            reg_state = x.rdap_outcome
            row.update(rdap_outcome=x.rdap_outcome, rdap_registered=x.get("rdap_registered"), rdap_expires=x.get("rdap_expires"),
                       rdap_registrar=x.get("rdap_registrar"), rdap_status=x.get("rdap_status"))
            if x.rdap_outcome == "registered" and isinstance(x.get("rdap_registered"), str) and pd.notna(r.min_deploy_year):
                try:
                    ry = int(x.rdap_registered[:4])
                    rereg = ry > int(r.min_deploy_year) and h not in GATEWAYS and not row['is_gateway']
                    row["rdap_registered_year"] = ry
                except Exception:
                    pass
        if rdom in nsd.index:
            row["ns_rcode"] = nsd.loc[rdom].ns_rcode
            row["ns"] = nsd.loc[rdom].ns
        row["rereg_after_deploy_flag"] = bool(rereg)
        hs = http_summary(h)
        root, nft0, nft1 = hs.get("root"), hs.get("nft0"), hs.get("nft1")
        def st(x):
            return None if x is None else (str(x.get("status")) if "status" in x else f"ERR:{x.get('error_kind')}")
        row.update(root_status=st(root), nft_status=st(nft0), nft2_status=st(nft1), root_final_url=(root or {}).get("final_url"),
                   nft_final_url=(nft0 or {}).get("final_url"), tls_verify_failed=bool((root or {}).get("tls_verify_failed") or (nft0 or {}).get("tls_verify_failed")))
        row["http_probed"] = bool(hs)
        bodies = " ".join(((x or {}).get("body_head") or "")[:6000] for x in (root, nft0, nft1) if x)
        urls_seen = " ".join(str((x or {}).get("final_url")) + " " + " ".join(hh.get("url", "") for hh in (x or {}).get("history", [])) for x in (root, nft0, nft1) if x)
        # --- fingerprints
        fp_hit, claimable = None, None
        target_pl = pl or cpl
        for p, rx, name, c in FP:
            if p != "*" and p != target_pl:
                continue
            for x in (nft0, root, nft1):
                if x and "status" in x and x["status"] in (400, 403, 404, 410, 500, 502, 503, 530) and rx.search(x.get("body_head") or ""):
                    fp_hit, claimable = name, c
                    break
            if fp_hit:
                break
        # cloudfront with custom domain: 403 "Bad request" no alias
        if not fp_hit and cpl == "aws-cloudfront" and nft0 and nft0.get("status") == 403 and "The request could not be satisfied" in (nft0.get("body_head") or ""):
            fp_hit, claimable = "cloudfront-no-alias(403)", None
        row["cloud_fingerprint"] = fp_hit
        row["path_style_shared_host"] = h in ("[withheld-host]", "storage.googleapis.com") or bool(re.fullmatch(r"s3[.-][a-z0-9-]+\.amazonaws\.com", h))
        nx = d["dns_a_rcode"] == "NXDOMAIN"
        nx_cloud = nx and (target_pl in NXDOMAIN_CLAIMABLE)
        # --- parking
        nsl = str(row.get("ns") or "") + " " + str(d.get("cname_chain") or "")
        parked = bool(PARK_NS.search(nsl)) or bool(PARK_URL.search(urls_seen) and not PARK_URL.search(h)) or \
            (bool(PARK_BODY.search(bodies)) and not pl and not row["is_gateway"] and not all(x and x.get("status") == 200 and content_ok(x, "metadata") for x in (nft0,) if x))
        row["parked_signal"] = parked
        # --- verdict
        v, why = "unknown", ""
        nft_ok = content_ok(nft0, "metadata" if "metadata" in r.roles else "image" if "image" in r.roles else "") if nft0 else None
        nft_alive_any = any(x and "status" in x and 200 <= x["status"] < 300 for x in (nft0, nft1))
        if fp_hit == "github-pages-404" and gh.get(h, {}).get("github_status") == 200:
            v, why = "dead-http", "GitHub Pages 404, but the GitHub user/org exists (only the owner can restore; not claimable)"
        elif fp_hit and claimable:
            v, why = "dangling-cloud-claimable", f"{fp_hit} on {target_pl}"
        elif nx_cloud:
            v, why = "dangling-cloud-claimable", f"NXDOMAIN for {target_pl} name" + (f" (CNAME->{cn_final})" if cn_final else "")
        elif reg_state == "not-registered":
            v, why = "domain-likely-available", f"RDAP 404 for {rdom}"
        elif not pl and not row["is_gateway"] and rdom and nx and row.get("ns_rcode") == "NXDOMAIN" and reg_state in (None, "no-rdap-tld", "404-nonjson"):
            v, why = "domain-likely-available", f"{rdom} has no NS delegation (NXDOMAIN) and no RDAP; unverified"
        elif parked:
            v, why = "parked-or-for-sale", "parking signal (ns/redirect/body)"
        elif nx or d["dns_a_rcode"] == "NXDOMAIN":
            v, why = "dead-dns", f"NXDOMAIN" + (f"; domain RDAP {reg_state}" if reg_state else "") + (f"; CNAME dangling->{cn_final}" if cn_final else "")
        elif not d["dns_resolves"]:
            v, why = ("dead-dns", "no A/AAAA records (NODATA)") if d["dns_a_rcode"] == "NOERROR" else ("unknown", f"DNS rcode {d['dns_a_rcode']}")
        elif not hs:
            v, why = "unknown", "resolves; HTTP not probed (beyond rank cutoff)"
        else:
            sts = [st(x) for x in (nft0, nft1)]
            if not nft_alive_any and row["is_gateway"] and (any(x and x.isdigit() for x in sts) or (row["root_status"] or "").isdigit()):
                v, why = "unknown", f"gateway answered root {row['root_status']} but sampled content URLs {sts}: content-level failure, not host death (see census liveness)"
            elif not nft_alive_any and all(x in ("429", "ERR:timeout", None) for x in sts) and (row["root_status"] in ("429", "ERR:timeout") or row["is_gateway"]):
                v, why = "unknown", f"rate-limited/timeout on probe ({sts}); not evidence of death"
            elif nft_alive_any:
                if nft_ok is False and nft1 is None or (nft_ok is False and not (nft1 and content_ok(nft1, "image"))):
                    v, why = "alive-but-wrong-content", "NFT URL returned HTML page, not metadata/media"
                else:
                    v, why = "alive-serving", "NFT URL returns 2xx"
            elif nft0 is None and root and "status" in root:
                v, why = ("alive-serving" if 200 <= root["status"] < 300 else "dead-http", f"no NFT URL probed; root {root['status']}")
            else:
                v, why = "dead-http", f"NFT URL {sts}; root {st(root)}"
        # re-registration after deploy overrides unless still serving as expected
        if rereg and v not in ("alive-serving", "dangling-cloud-claimable", "domain-likely-available"):
            v, why = "rereg-after-deploy", f"{why}; RDAP registration {row.get('rdap_registered')} after deploy_year {int(r.min_deploy_year)}"
        row.update(verdict=v, verdict_reason=why)
        if v == "domain-likely-available":
            row["available_evidence"] = "rdap-404" if reg_state == "not-registered" else "ns-nxdomain-only"
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_parquet(HOSTS_DIR / "hosts_full.parquet", index=False)
    risky = ("dangling-cloud-claimable", "domain-likely-available", "rereg-after-deploy")
    priv = df[df.verdict.isin(risky) | df.rereg_after_deploy_flag.fillna(False).astype(bool)]
    priv.to_csv(WITHHELD_HOSTS_FILE, index=False)
    pub = df.copy()
    mask = pub.verdict.isin(["dangling-cloud-claimable", "domain-likely-available"])
    for c in ("host", "reg_domain", "top_collections", "sample_urls", "cname_chain", "root_final_url", "nft_final_url", "ns"):
        if c in pub:
            pub.loc[mask, c] = "[redacted: see WITHHELD_HOSTS_FILE (default: withheld_hosts.csv)]"
    # sibling hosts under the same (non-platform) registrable domain as an availability candidate are redacted too
    cand_doms = set(df.loc[df.verdict.isin(["domain-likely-available", "dangling-cloud-claimable"]) & df.platform.fillna("").apply(lambda x: x == "" or x.startswith("cname->")), "reg_domain"].dropna())
    sib = df.reg_domain.isin(cand_doms) & ~mask & df.platform.isna()
    for c in ("host", "reg_domain", "top_collections", "sample_urls", "cname_chain", "root_final_url", "nft_final_url", "ns"):
        if c in pub:
            pub.loc[sib, c] = "[redacted: sibling of availability candidate]"
    priv_names = set(df.loc[mask, "host"])
    hit = df.cname_chain.fillna("").apply(lambda c: any(n and n in c for n in priv_names)) & ~mask
    for c in ("cname_chain", "sample_urls", "ips"):
        if c in pub:
            pub.loc[hit, c] = "[redacted]"
    pub["cname_chain"] = pub["cname_chain"].where(pub["cname_chain"].isna() | pub["cname_chain"].eq(""), "[cname present; chain withheld]")
    pub.loc[mask, "verdict_reason"] = [("cloud fingerprint: " + str(f)) if isinstance(f, str) else ("RDAP " + str(a)) for f, a in zip(df.loc[mask, "cloud_fingerprint"], df.loc[mask, "available_evidence"])]
    for c in ("rdap_registrar", "rdap_registered", "rdap_expires", "rdap_status", "ns_rcode", "ips", "sample_urls"):
        if c in pub:
            pub.loc[mask, c] = None
    pub.loc[mask, "host"] = [f"[redacted-{i}]" for i in df.loc[mask, "priority_rank"]]
    pub.to_csv(HOSTS_DIR / "hosts.csv", index=False)
    pub.to_parquet(HOSTS_DIR / "hosts.parquet", index=False)
    print(df.verdict.value_counts().to_string())
    print(df.groupby("verdict").holders_affected.sum().to_string())


if __name__ == "__main__":
    main()
