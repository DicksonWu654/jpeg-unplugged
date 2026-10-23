"""Stage 1: DNS for every host (A/AAAA/CNAME chain) and NS of the registrable domain.  Queries 1.1.1.1 then 8.8.8.8
(on SERVFAIL/timeout; rcodes from both are recorded).  Saves data/raw/hosts/<host>/dns.json and a summary
data/hosts/dns.parquet.  Read-only."""
import asyncio, json, sys, pathlib
import dns.asyncquery, dns.message, dns.rcode, dns.rdatatype, dns.exception, dns.flags
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import *

RESOLVERS = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
sem = asyncio.Semaphore(150)


async def q(name, rtype, resolver):
    msg = dns.message.make_query(name, rtype, use_edns=0, want_dnssec=False)
    for attempt in range(2):
        try:
            async with sem:
                try:
                    r = await dns.asyncquery.udp(msg, resolver, timeout=4)
                    if r.flags & dns.flags.TC:
                        r = await dns.asyncquery.tcp(msg, resolver, timeout=6)
                except dns.exception.Timeout:
                    r = await dns.asyncquery.tcp(msg, resolver, timeout=6)
            ans = [{"name": rs.name.to_text(), "type": dns.rdatatype.to_text(rs.rdtype), "data": rr.to_text(), "ttl": rs.ttl}
                   for rs in r.answer for rr in rs]
            return {"resolver": resolver, "rcode": dns.rcode.to_text(r.rcode()), "answer": ans}
        except Exception as e:  # noqa
            err = f"{type(e).__name__}: {e}"
            await asyncio.sleep(0.5)
    return {"resolver": resolver, "rcode": "ERROR", "error": err, "answer": []}


async def query(name, rtype):
    """first resolver unless SERVFAIL/ERROR -> try the next; keep all attempts."""
    attempts = []
    for res in RESOLVERS:
        a = await q(name, rtype, res)
        attempts.append(a)
        if a["rcode"] in ("NOERROR", "NXDOMAIN"):
            break
    last = attempts[-1]
    return {"final": last["rcode"], "answer": last["answer"], "attempts": [{k: v for k, v in x.items() if k != "answer"} for x in attempts]}


async def scan_host(host):
    out = {"host": host, "queried_at": now()}
    out["A"] = await query(host, "A")
    out["AAAA"] = await query(host, "AAAA")
    # CNAME chain is in the A answer; if A is NODATA also ask CNAME explicitly
    if out["A"]["final"] == "NOERROR" and not out["A"]["answer"]:
        out["CNAME"] = await query(host, "CNAME")
    (host_dir(host) / "dns.json").write_text(json.dumps(out, indent=1))
    return out


async def scan_ns(domain):
    out = {"domain": domain, "queried_at": now(), "NS": await query(domain, "NS")}
    d = RAW / "_domains"
    d.mkdir(parents=True, exist_ok=True)
    (d / (safe(domain) + ".ns.json")).write_text(json.dumps(out, indent=1))
    return out


def summarize(o):
    a, aaaa = o["A"], o["AAAA"]
    ans = a["answer"] + aaaa["answer"] + o.get("CNAME", {"answer": []})["answer"]
    cn = [r["data"].rstrip(".").lower() for r in ans if r["type"] == "CNAME"]
    # keep chain order from A answer
    cn = [r["data"].rstrip(".").lower() for r in a["answer"] if r["type"] == "CNAME"] or cn
    ips = sorted({r["data"] for r in a["answer"] if r["type"] == "A"})
    ip6 = sorted({r["data"] for r in aaaa["answer"] if r["type"] == "AAAA"})
    return {"host": o["host"], "dns_a_rcode": a["final"], "dns_aaaa_rcode": aaaa["final"], "ips": ",".join(ips), "ip6": ",".join(ip6),
            "cname_chain": ",".join(cn), "cname_final": cn[-1] if cn else None,
            "dns_resolves": bool(ips or ip6)}


async def main():
    deps = pd.read_parquet(HOSTS_DIR / "host_deps.parquet")
    hosts = sorted(h for h in deps.host.unique() if not is_ip(h))
    todo = [h for h in hosts if not (RAW / safe(h) / "dns.json").exists()]
    print(len(hosts), "hosts;", len(todo), "to query", flush=True)
    done = 0

    async def run(h):
        nonlocal done
        r = await scan_host(h)
        done += 1
        if done % 500 == 0:
            print("dns", done, flush=True)
        return r
    await asyncio.gather(*(run(h) for h in todo))
    doms = sorted({reg_domain(h) for h in hosts if reg_domain(h)})
    tdo = [d for d in doms if not (RAW / "_domains" / (safe(d) + ".ns.json")).exists()]
    print(len(doms), "registrable domains;", len(tdo), "NS to query", flush=True)
    await asyncio.gather(*(scan_ns(d) for d in tdo))
    rows = []
    for h in hosts:
        rows.append(summarize(json.loads((RAW / safe(h) / "dns.json").read_text())))
    ns = []
    for d in doms:
        o = json.loads((RAW / "_domains" / (safe(d) + ".ns.json")).read_text())
        n = o["NS"]
        ns.append({"reg_domain": d, "ns_rcode": n["final"], "ns": ",".join(sorted(r["data"].rstrip(".").lower() for r in n["answer"] if r["type"] == "NS"))})
    pd.DataFrame(rows).to_parquet(HOSTS_DIR / "dns.parquet", index=False)
    pd.DataFrame(ns).to_parquet(HOSTS_DIR / "dns_ns.parquet", index=False)
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
