"""Stage 2: RDAP for each registrable domain (ICANN PSL) via https://rdap.org/domain/<d> (redirects to the registry).
<=3 req/s to rdap.org.  Raw: data/raw/hosts/_domains/<domain>.rdap.json {meta, body}.  Summary: data/hosts/rdap.parquet.
A 404 from the registry => 'not-registered' (possibly available). TLDs absent from the IANA bootstrap => 'no-rdap-tld'.
Never uses registrar purchase flows."""
import asyncio, json, os, sys, pathlib, time
import aiohttp
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import *

DOM = RAW / "_domains"
DOM.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "nft-unplugged-research/0.1 (read-only measurement; contact via github seal)", "Accept": "application/rdap+json, application/json"}


class Bucket:
    def __init__(self, rate):
        self.iv, self.t = 1 / rate, 0.0
        self.lock = asyncio.Lock()

    async def wait(self):
        async with self.lock:
            n = time.monotonic()
            if self.t > n:
                await asyncio.sleep(self.t - n)
            self.t = max(n, self.t) + self.iv


bucket = Bucket(2.5)


async def bootstrap(s):
    p = DOM / "_iana_bootstrap_dns.json"
    if not p.exists():
        async with s.get("https://data.iana.org/rdap/dns.json", headers=UA) as r:
            p.write_bytes(await r.read())
    j = json.loads(p.read_text())
    return {t for svc in j["services"] for t in svc[0]}


async def one(s, d, tlds, sem):
    out = DOM / (safe(d) + ".rdap.json")
    if out.exists():
        return
    t = tld(d)
    last_tld = t.split(".")[-1] if t else None
    if last_tld not in tlds:
        out.write_text(json.dumps({"meta": {"domain": d, "status": None, "outcome": "no-rdap-tld", "retrieved_at": now()}, "body": None}))
        return
    meta = {"domain": d, "url": f"https://rdap.org/domain/{d}", "retrieved_at": now()}
    body, status, err = None, None, None
    async with sem:
        for attempt in range(5):
            await bucket.wait()
            try:
                async with s.get(meta["url"], headers=UA, timeout=aiohttp.ClientTimeout(total=40), allow_redirects=True) as r:
                    status = r.status
                    meta["final_url"] = str(r.url)
                    body = await r.read()
                if status == 429 or status >= 500:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                err = None
                break
            except Exception as e:  # noqa
                err = f"{type(e).__name__}: {e}"
                await asyncio.sleep(3 * (attempt + 1))
    meta["status"] = status
    meta["error"] = err
    parsed, text = None, None
    if body is not None:
        text = body[:200000].decode("utf8", "replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = None
    meta["sha256"] = sha(body) if body is not None else None
    meta["outcome"] = ("registered" if status == 200 and parsed and parsed.get("ldhName") else
                       "not-registered" if status == 404 and parsed is not None else
                       "404-nonjson" if status == 404 else
                       "rate-limited" if status == 429 else "error")
    out.write_text(json.dumps({"meta": meta, "body": parsed if parsed is not None else text}))


def parse(d):
    j = json.loads((DOM / (safe(d) + ".rdap.json")).read_text())
    m, b = j["meta"], j["body"]
    row = {"reg_domain": d, "rdap_outcome": m["outcome"], "rdap_http": m.get("status"), "rdap_url": m.get("final_url")}
    if m["outcome"] == "registered" and isinstance(b, dict):
        ev = {e.get("eventAction"): e.get("eventDate") for e in b.get("events", [])}
        row.update(rdap_registered=ev.get("registration"), rdap_expires=ev.get("expiration"), rdap_changed=ev.get("last changed"),
                   rdap_status=",".join(b.get("status", [])),
                   rdap_ns=",".join(sorted(n.get("ldhName", "").lower() for n in b.get("nameservers", []))))
        reg = None
        for e in b.get("entities", []):
            if "registrar" in e.get("roles", []):
                try:
                    reg = next(x[3] for x in e["vcardArray"][1] if x[0] == "fn")
                except Exception:
                    reg = None
                if not reg:
                    reg = (e.get("publicIds") or [{}])[0].get("identifier")
        row["rdap_registrar"] = reg
    return row


async def main():
    deps = pd.read_parquet(HOSTS_DIR / "host_deps.parquet")
    hosts = [h for h in deps.host.unique() if not is_ip(h)]
    prio = pd.read_parquet(HOSTS_DIR / "host_priority.parquet")
    doms = []
    for h in prio.host:                      # priority order: most holders affected first
        d = None if is_ip(h) else reg_domain(h)
        if d and d not in doms:
            doms.append(d)
    if os.environ.get("NS_NX_ONLY"):          # second pass: only domains whose NS lookup says NXDOMAIN (availability candidates)
        nx = set(pd.read_parquet(HOSTS_DIR / "dns_ns.parquet").query("ns_rcode == 'NXDOMAIN'").reg_domain)
        doms = [d for d in doms if d in nx]
    print(len(doms), "domains", flush=True)
    conn = aiohttp.TCPConnector(limit=30)
    async with aiohttp.ClientSession(connector=conn) as s:
        tlds = await bootstrap(s)
        sem = asyncio.Semaphore(8)
        # a retry pass for earlier transient failures
        for d in doms:
            p = DOM / (safe(d) + ".rdap.json")
            if p.exists() and json.loads(p.read_text())["meta"]["outcome"] in ("rate-limited", "error"):
                p.unlink()
        tasks = [one(s, d, tlds, sem) for d in doms]
        for i in range(0, len(tasks), 200):
            await asyncio.gather(*tasks[i:i + 200])
            print("rdap", min(i + 200, len(tasks)), flush=True)
    rows = [parse(d) for d in doms]
    df = pd.DataFrame(rows)
    df.to_parquet(HOSTS_DIR / "rdap.parquet", index=False)
    print(df.rdap_outcome.value_counts().to_dict())


def parse_only():
    """build rdap.parquet from whatever raw RDAP files exist (the scan is slow; priority order means the top domains come first)."""
    rows = [parse_file(p) for p in sorted(DOM.glob("*.rdap.json"))]
    df = pd.DataFrame(rows)
    df.to_parquet(HOSTS_DIR / "rdap.parquet", index=False)
    print(len(df), df.rdap_outcome.value_counts().to_dict())


def parse_file(p):
    j = json.loads(p.read_text())
    return parse(j["meta"]["domain"])


if __name__ == "__main__":
    if "--parse-only" in sys.argv:
        parse_only()
    else:
        asyncio.run(main())
