"""Polite async networking for the census: public-DNS resolver (with NXDOMAIN/SERVFAIL distinction), SSRF-safe
HTTP fetch with manual redirects and a byte cap, per-host throttling, per-collection evidence log.

Why a custom resolver: the WSL host resolver refuses some real names (e.g. ipfs.io) that resolve fine on public DNS,
and getaddrinfo cannot tell NXDOMAIN from SERVFAIL/NODATA. We resolve via 1.1.1.1 / 8.8.8.8 over UDP and hand the
IP to aiohttp (TLS SNI + Host still use the original name).
"""
import asyncio
import hashlib
import json
import os
import pathlib
import random
import socket
import ssl
import struct
import time
from urllib.parse import urljoin, urlsplit

import aiohttp
from aiohttp.abc import AbstractResolver

from classify import is_global_ip, reg_domain

UA = "jpeg-unplugged-research (+https://github.com/DicksonWu654/jpeg-unplugged)"
DNS_SERVERS = ("1.1.1.1", "8.8.8.8")


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ----------------------------------------------------------------------------------------------
# DNS
# ----------------------------------------------------------------------------------------------
class DNSError(OSError):
    kind = "dns-error"


class DNSNxdomain(DNSError):
    kind = "dns-nxdomain"


class DNSServfail(DNSError):
    kind = "dns-servfail"


class DNSNodata(DNSError):
    kind = "dns-nodata"


class DNSTemp(DNSError):
    kind = "dns-temp"


class BlockedAddress(OSError):
    kind = "blocked-private-ip"


def _enc_name(name):
    out = b""
    for lab in name.rstrip(".").encode("idna").decode().split("."):
        out += bytes([len(lab)]) + lab.encode()
    return out + b"\0"


def _skip_name(d, i):
    while True:
        n = d[i]
        if n == 0:
            return i + 1
        if n & 0xC0 == 0xC0:
            return i + 2
        i += 1 + n


def _parse_dns(d):
    flags = struct.unpack(">H", d[2:4])[0]
    rcode = flags & 0xF
    qd, an = struct.unpack(">HH", d[4:8])
    i = 12
    for _ in range(qd):
        i = _skip_name(d, i) + 4
    ips, ttl = [], 300
    for _ in range(an):
        i = _skip_name(d, i)
        t, _c, tt, rl = struct.unpack(">HHIH", d[i:i + 10])
        i += 10
        if t == 1 and rl == 4:
            ips.append(socket.inet_ntoa(d[i:i + 4]))
            ttl = min(ttl, tt)
        i += rl
    return rcode, ips, max(ttl, 30)


class PublicDNS:
    def __init__(self):
        self.cache = {}
        self.inflight = {}
        self.sem = asyncio.Semaphore(40)

    async def _udp(self, name, server):
        loop = asyncio.get_running_loop()
        pid = random.randrange(65536)
        pkt = struct.pack(">HHHHHH", pid, 0x0100, 1, 0, 0, 0) + _enc_name(name) + struct.pack(">HH", 1, 1)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        try:
            await loop.sock_connect(sock, (server, 53))
            await loop.sock_sendall(sock, pkt)
            while True:
                data = await asyncio.wait_for(loop.sock_recv(sock, 4096), 3.0)
                if len(data) >= 12 and struct.unpack(">H", data[:2])[0] == pid:
                    return data
        finally:
            sock.close()

    async def query(self, name):
        """-> ('ok', [ips], rcode) | ('nxdomain'|'servfail'|'nodata'|'temp', [], rcode)"""
        name = name.lower().rstrip(".")
        hit = self.cache.get(name)
        if hit and hit[0] > time.time():
            return hit[1]
        if name in self.inflight:
            return await self.inflight[name]
        fut = asyncio.ensure_future(self._query(name))
        self.inflight[name] = fut
        try:
            return await fut
        finally:
            self.inflight.pop(name, None)

    async def _query(self, name):
        res = ("temp", [], None)
        async with self.sem:
            for attempt in range(3):
                srv = DNS_SERVERS[attempt % 2]
                try:
                    d = await self._udp(name, srv)
                    rcode, ips, ttl = _parse_dns(d)
                except (asyncio.TimeoutError, OSError, struct.error, IndexError, UnicodeError):
                    await asyncio.sleep(0.2)
                    continue
                if rcode == 0 and ips:
                    res = ("ok", ips, 0)
                    self.cache[name] = (time.time() + min(ttl, 900), res)
                    return res
                if rcode == 0:
                    res = ("nodata", [], 0)
                elif rcode == 3:
                    res = ("nxdomain", [], 3)
                elif rcode == 2:
                    res = ("servfail", [], 2)
                else:
                    res = ("temp", [], rcode)
                    continue
                # confirm negative answers against the second server once
                if attempt == 0:
                    first = res
                    try:
                        d2 = await self._udp(name, DNS_SERVERS[1])
                        r2, ips2, ttl2 = _parse_dns(d2)
                        if r2 == 0 and ips2:
                            res = ("ok", ips2, 0)
                            self.cache[name] = (time.time() + min(ttl2, 900), res)
                            return res
                    except (asyncio.TimeoutError, OSError, struct.error, IndexError, UnicodeError):
                        pass
                    res = first
                break
        if res[0] != "temp":
            self.cache[name] = (time.time() + 180, res)
        return res


class SafeResolver(AbstractResolver):
    """Resolves via public DNS; refuses non-global addresses (SSRF guard, also applies to redirect targets)."""

    def __init__(self, dns):
        self.dns = dns

    async def resolve(self, host, port=0, family=socket.AF_INET):
        g = is_global_ip(host)
        if g is False:
            raise BlockedAddress(f"literal non-global ip {host}")
        if g is True:
            return [{"hostname": host, "host": host, "port": port, "family": socket.AF_INET, "proto": 0, "flags": 0}]
        status, ips, _ = await self.dns.query(host)
        if status == "nxdomain":
            raise DNSNxdomain(f"NXDOMAIN {host}")
        if status == "servfail":
            raise DNSServfail(f"SERVFAIL {host}")
        if status == "nodata":
            raise DNSNodata(f"NODATA {host}")
        if status != "ok":
            raise DNSTemp(f"dns temporary failure {host}")
        out = []
        for ip in ips:
            if not is_global_ip(ip):
                raise BlockedAddress(f"{host} resolves to non-global {ip}")
            out.append({"hostname": host, "host": ip, "port": port, "family": socket.AF_INET, "proto": 0, "flags": 0})
        return out

    async def close(self):
        pass


# ----------------------------------------------------------------------------------------------
# Throttling
# ----------------------------------------------------------------------------------------------
class Throttle:
    """Per-key minimum interval + concurrency cap. Key = host (or API name)."""

    def __init__(self, default_interval=0.34, default_conc=6):
        self.t_next, self.locks, self.sems = {}, {}, {}
        self.default_interval, self.default_conc = default_interval, default_conc
        self.intervals = {}
        self.concs = {}

    def configure(self, key, interval=None, conc=None):
        if interval is not None:
            self.intervals[key] = interval
        if conc is not None:
            self.concs[key] = conc

    def acquire(self, key):
        return _Slot(self, key)

    async def _wait(self, key):
        interval = self.intervals.get(key, self.default_interval)
        lock = self.locks.setdefault(key, asyncio.Lock())
        loop = asyncio.get_running_loop()
        async with lock:
            now = loop.time()
            t = max(now, self.t_next.get(key, 0.0))
            self.t_next[key] = t + interval
        if t > now:
            await asyncio.sleep(t - now)

    def backoff(self, key, seconds):
        loop = asyncio.get_event_loop()
        self.t_next[key] = max(self.t_next.get(key, 0), loop.time() + seconds)


class _Slot:
    def __init__(self, th, key):
        self.th, self.key = th, key

    async def __aenter__(self):
        sem = self.th.sems.get(self.key)
        if sem is None:
            sem = self.th.sems[self.key] = asyncio.Semaphore(self.th.concs.get(self.key, self.th.default_conc))
        self.sem = sem
        await sem.acquire()
        await self.th._wait(self.key)

    async def __aexit__(self, *a):
        self.sem.release()


# ----------------------------------------------------------------------------------------------
# HTTP
# ----------------------------------------------------------------------------------------------
def map_error(e):
    """Map an exception to (error_kind, message)."""
    msg = f"{type(e).__name__}: {e}"[:300]
    if isinstance(e, asyncio.TimeoutError):
        return "timeout", msg
    oe = getattr(e, "os_error", None) or (e if isinstance(e, OSError) else None)
    if isinstance(oe, DNSError):
        return oe.kind, msg
    if isinstance(oe, BlockedAddress):
        return "blocked-private-ip", msg
    if isinstance(e, (aiohttp.ClientConnectorCertificateError, aiohttp.ClientSSLError, ssl.SSLError, ssl.CertificateError)) or \
            isinstance(oe, ssl.SSLError):
        t = msg.lower()
        sub = ("expired" if "expired" in t else "hostname-mismatch" if ("hostname" in t or "doesn't match" in t or "match" in t and "cert" in t)
               else "self-signed" if "self" in t and "signed" in t else "unknown-ca" if ("unable to get local issuer" in t or "unknown ca" in t)
               else "handshake")
        return "tls:" + sub, msg
    if isinstance(oe, ConnectionRefusedError):
        return "conn-refused", msg
    if isinstance(e, (aiohttp.ServerDisconnectedError, ConnectionResetError)) or isinstance(oe, ConnectionResetError):
        return "conn-reset", msg
    if isinstance(oe, OSError) and getattr(oe, "errno", None) in (101, 113, 110):
        return ("timeout" if oe.errno == 110 else "unreachable"), msg
    if isinstance(e, aiohttp.InvalidURL) or isinstance(e, ValueError):
        return "bad-url", msg
    if isinstance(e, aiohttp.TooManyRedirects):
        return "redirect-loop", msg
    if isinstance(e, aiohttp.ClientPayloadError):
        return "payload-error", msg
    return "other:" + type(e).__name__, msg


class Net:
    """Shared HTTP session + DNS + throttle for the whole run."""

    def __init__(self):
        self.dns = PublicDNS()
        self.throttle = Throttle()
        self.session = None
        self.rpc_session = None

    async def start(self):
        conn = aiohttp.TCPConnector(resolver=SafeResolver(self.dns), limit=500, limit_per_host=0, ttl_dns_cache=0,
                                    enable_cleanup_closed=True, force_close=False, keepalive_timeout=15)
        self.session = aiohttp.ClientSession(connector=conn, headers={"User-Agent": UA}, auto_decompress=True,
                                             max_line_size=16384, max_field_size=16384)
        # API endpoints (RPC, Blockscout) use the normal system resolver; they are fixed, trusted hosts.
        self.rpc_session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=64),
                                                 headers={"User-Agent": UA}, timeout=aiohttp.ClientTimeout(total=45))

    async def close(self):
        for s in (self.session, self.rpc_session):
            if s:
                await s.close()

    async def fetch(self, url, *, max_bytes=2_000_000, timeout=20.0, accept=None, max_redirects=5, method="GET"):
        """GET url (manual redirects, SSRF-safe). Never raises. Returns a dict (see keys below); body = bytes read (<= max_bytes)."""
        t0 = time.time()
        res = {"url": url, "method": method, "status": None, "final_url": url, "redirects": [], "headers": {},
               "error_kind": None, "error": None, "body": b"", "bytes_read": 0, "sha256": None, "truncated": False,
               "content_length": None, "retrieved_at": now_iso(), "elapsed": None}
        cur = url
        try:
            for hop in range(max_redirects + 1):
                sp = urlsplit(cur)
                if sp.scheme not in ("http", "https") or not sp.hostname:
                    res["error_kind"], res["error"] = "bad-url", f"unsupported url {cur[:200]}"
                    break
                if is_global_ip(sp.hostname) is False:
                    res["error_kind"], res["error"] = "blocked-private-ip", sp.hostname
                    break
                host = sp.hostname.lower()
                hdrs = {"Accept": accept or "*/*"}
                try:
                    async with self.throttle.acquire(host):
                        tmo = aiohttp.ClientTimeout(total=timeout, sock_connect=min(12.0, timeout))
                        async with self.session.request(method, cur, allow_redirects=False, timeout=tmo, headers=hdrs) as r:
                            res["status"] = r.status
                            res["headers"] = {k.lower(): v for k, v in r.headers.items()
                                              if k.lower() in ("content-type", "content-length", "server", "location", "content-encoding",
                                                               "cf-ray", "x-ipfs-path", "x-ipfs-roots", "retry-after", "cache-control")}
                            if r.status in (301, 302, 303, 307, 308) and r.headers.get("Location"):
                                nxt = urljoin(cur, r.headers["Location"])
                                res["redirects"].append({"status": r.status, "from": cur, "to": nxt})
                                cur = nxt
                                res["final_url"] = cur
                                continue
                            cl = r.headers.get("Content-Length")
                            res["content_length"] = int(cl) if cl and cl.isdigit() else None
                            res["final_url"] = cur
                            buf = bytearray()
                            if method != "HEAD":
                                async for chunk in r.content.iter_chunked(65536):
                                    buf += chunk
                                    if len(buf) >= max_bytes:
                                        res["truncated"] = True
                                        break
                            res["body"] = bytes(buf[:max_bytes])
                            res["bytes_read"] = len(res["body"])
                            res["sha256"] = hashlib.sha256(res["body"]).hexdigest()
                            if r.status == 429 or (r.status == 503 and r.headers.get("Retry-After")):
                                self.throttle.backoff(host, 5.0)
                            break
                except Exception as e:  # noqa: BLE001
                    res["error_kind"], res["error"] = map_error(e)
                    break
            else:
                res["error_kind"], res["error"] = "redirect-loop", f"more than {max_redirects} redirects"
        except Exception as e:  # noqa: BLE001
            res["error_kind"], res["error"] = map_error(e)
        res["elapsed"] = round(time.time() - t0, 2)
        if res["error_kind"] in ("dns-nxdomain", "dns-servfail", "dns-nodata"):
            try:
                host = urlsplit(cur).hostname or ""
                rd = reg_domain(host)
                if rd and rd != host:
                    st, _, _ = await self.dns.query(rd)
                    res["reg_domain_dns"] = st
                else:
                    res["reg_domain_dns"] = res["error_kind"].split("-", 1)[1]
            except Exception:  # noqa: BLE001
                pass
        return res


# ----------------------------------------------------------------------------------------------
# Evidence
# ----------------------------------------------------------------------------------------------
class Evidence:
    """Per-collection evidence dir: data/raw/census/<addr>/{evidence.jsonl.gz, bodies.zip, result.json.gz}.

    One line per request (url, method, status, retrieved_at, sha256, bytes, error, ...). Raw response bodies (possibly
    truncated to `store_cap` bytes; sha256 + size always refer to what was actually read) go into bodies.zip as
    `<seq>_<role>.<ext>`; `body_file` in the evidence line is that member name. Buffered in memory; call flush()."""

    def __init__(self, root, addr):
        self.dir = pathlib.Path(root) / addr
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "evidence.jsonl.gz"
        self.zip = self.dir / "bodies.zip"
        self.lines, self.bodies = [], {}
        self.n = 0
        old = self.dir / "evidence.jsonl"
        if self.path.exists():
            import gzip
            with gzip.open(self.path, "rt") as f:
                self.n = sum(1 for _ in f)
        elif old.exists():  # legacy plain-format dir (early seed runs): keep appending there
            self.path = old
            self.n = sum(1 for _ in open(old))

    def record(self, *, kind, role, url, method, status=None, error=None, error_kind=None, body=None, store_cap=65536,
               token_id=None, extra=None, sha256=None, size=None, retrieved_at=None, body_ext="bin", gz=None):
        self.n += 1
        rec = {"seq": self.n, "kind": kind, "role": role, "token_id": token_id, "url": url[:1500] if url else url, "method": method,
               "status": status, "retrieved_at": retrieved_at or now_iso()}
        if error:
            rec["error"] = error[:200]
        if error_kind:
            rec["error_kind"] = error_kind
        if body is not None:
            rec["sha256"] = sha256 or hashlib.sha256(body).hexdigest()
            rec["bytes"] = size if size is not None else len(body)
            if len(body) and store_cap:
                keep = body[:store_cap]
                fn = f"{self.n:04d}_{role}.{body_ext}"
                self.bodies[fn] = keep
                rec["body_file"] = fn
                rec["stored_bytes"] = len(keep)
        if extra:
            rec.update({k: v for k, v in extra.items() if v not in (None, [], "")})
        self.lines.append(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
        return rec

    def flush(self):
        import gzip
        import zipfile
        if self.bodies:
            with zipfile.ZipFile(self.zip, "a", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                for fn, b in self.bodies.items():
                    z.writestr(fn, b)
            self.bodies = {}
        if self.lines:
            data = ("\n".join(self.lines) + "\n").encode()
            if str(self.path).endswith(".gz"):
                with open(self.path, "ab") as f:
                    f.write(gzip.compress(data, 6))
            else:
                with open(self.path, "ab") as f:
                    f.write(data)
            self.lines = []
