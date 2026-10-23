"""Stage 3: read-only HTTP probes.  For each host (priority order = holders affected): GET root and up to 2 NFT URLs
(one metadata, one media if present).  Body capped at 16 KB, no JS, <=5 redirects (history recorded), a resolver that refuses
non-public IPs (so redirects/DNS tricks cannot make us touch private networks).  TLS errors are retried once with verification
off (flagged).  Raw: data/raw/hosts/<host>/http_<label>.json.  Usage: http_probe.py [N_hosts]"""
import asyncio, json, socket, sys, pathlib, ssl
import aiohttp
from aiohttp.abc import AbstractResolver
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import *

CAP = 16384
UA = {"User-Agent": "nft-unplugged-research/0.1 (read-only measurement)", "Accept": "*/*"}


class SafeResolver(AbstractResolver):
    async def resolve(self, host, port=0, family=socket.AF_INET):
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
            infos = [(fam, 0, 0, 0, sa) for fam, _, _, _, sa in infos]
        except OSError:
            # local resolver quirk (e.g. ipfs.io): fall back to the A records we already collected via 1.1.1.1 (stage 1)
            dj = RAW / safe(host) / "dns.json"
            if not dj.exists():
                raise
            infos = [(socket.AF_INET, 0, 0, 0, (r["data"], port)) for r in json.loads(dj.read_text())["A"]["answer"] if r["type"] == "A"]
        out = []
        for fam, _, _, _, sa in infos:
            if is_nonpublic_ip(sa[0]):
                continue
            out.append({"hostname": host, "host": sa[0], "port": port, "family": fam, "proto": 0, "flags": socket.AI_NUMERICHOST})
        if not out:
            raise OSError("refused: only non-public addresses")
        return out

    async def close(self):
        pass


async def fetch(session, url, verify=True):
    rec = {"url": url, "retrieved_at": now(), "verify_tls": verify}
    try:
        async with session.get(url, headers=UA, allow_redirects=True, max_redirects=5, ssl=None if verify else False,
                               timeout=aiohttp.ClientTimeout(total=18, connect=9)) as r:
            rec["status"] = r.status
            rec["final_url"] = str(r.url)
            rec["history"] = [{"status": h.status, "url": str(h.url), "location": h.headers.get("Location")} for h in r.history]
            rec["headers"] = {k: v for k, v in list(r.headers.items())[:40]}
            body = b""
            async for chunk in r.content.iter_chunked(4096):
                body += chunk
                if len(body) >= CAP:
                    break
            rec["body_len_read"] = len(body)
            rec["body_sha256"] = sha(body)
            rec["body_head"] = body.decode("utf8", "replace")
    except Exception as e:  # noqa
        rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        rec["error_kind"] = ("tls" if isinstance(e, (ssl.SSLError, aiohttp.ClientConnectorCertificateError, aiohttp.ClientSSLError))
                             else "timeout" if isinstance(e, asyncio.TimeoutError) else "conn")
    return rec


async def probe(session, url):
    rec = await fetch(session, url)
    if rec.get("error_kind") == "tls":
        rec2 = await fetch(session, url, verify=False)
        rec2["tls_verify_failed"] = rec["error"]
        rec = rec2
    if "error" in rec and rec.get("error_kind") in ("conn", "timeout") and url.startswith("https://"):
        # could be https not served; try http once (for root only)
        pass
    return rec


async def do_host(sem, session, host, urls, dnsrow):
    d = host_dir(host)
    if (d / "http_done").exists():
        return
    async with sem:
        out = {}
        if dnsrow is not None and not dnsrow["dns_resolves"]:
            (d / "http_root.json").write_text(json.dumps({"skipped": "no-dns", "dns_rcode": dnsrow["dns_a_rcode"]}))
        else:
            out["root"] = await probe(session, f"https://{host}/")
            if "error" in out["root"] and out["root"].get("error_kind") != "tls":
                r2 = await probe(session, f"http://{host}/")
                r2["fallback_after"] = out["root"]["error"]
                out["root_http"] = r2
            for i, u in enumerate(urls[:2]):
                await asyncio.sleep(0.3)
                out[f"nft{i}"] = await probe(session, u)
            for k, v in out.items():
                (d / f"http_{k}.json").write_text(json.dumps(v, indent=1))
        (d / "http_done").write_text(now())


async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    prio = pd.read_parquet(HOSTS_DIR / "host_priority.parquet")  # host, holders, urls(list)
    dns = {}
    for h in pd.read_parquet(HOSTS_DIR / "host_priority.parquet").host.head(int(sys.argv[1]) if len(sys.argv) > 1 else 500):
        p = RAW / safe(h) / "dns.json"
        if p.exists():
            o = json.loads(p.read_text())
            dns[h] = {"dns_resolves": any(r["type"] in ("A", "AAAA") for k in ("A", "AAAA") for r in o[k]["answer"]), "dns_a_rcode": o["A"]["final"]}
    prio = prio.head(n)
    conn = aiohttp.TCPConnector(limit=200, limit_per_host=3, resolver=SafeResolver(), ttl_dns_cache=300)
    sem = asyncio.Semaphore(120)
    async with aiohttp.ClientSession(connector=conn) as s:
        tasks = []
        for r in prio.itertuples():
            if is_ip(r.host):
                continue
            tasks.append(do_host(sem, s, r.host, list(r.urls), dns.get(r.host)))
        for i in range(0, len(tasks), 300):
            await asyncio.gather(*tasks[i:i + 300])
            print("http", min(i + 300, len(tasks)), "/", len(tasks), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
