"""Shared helpers for the hosts host-liveness pipeline (read-only: DNS, RDAP, HTTP GET/HEAD with body cap)."""
import hashlib, ipaddress, json, os, pathlib, re, time
import tldextract

ROOT = pathlib.Path(__file__).resolve().parents[2]
HOSTS_DIR = ROOT / "data" / "hosts"
RAW = ROOT / "data" / "raw" / "hosts"
SCRATCH = pathlib.Path(os.environ.get("W8_SCRATCH", "/tmp/claude-1000/-home-artemis/7b295f72-a96a-4bce-a17b-2df0adfadbb8/scratchpad"))

_icann = tldextract.TLDExtract(suffix_list_urls=(), include_psl_private_domains=False)
_priv = tldextract.TLDExtract(suffix_list_urls=(), include_psl_private_domains=True)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe(s):
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)[:150]


def host_dir(host):
    d = RAW / safe(host)
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_ip(host):
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def is_nonpublic_ip(ip):
    a = ipaddress.ip_address(ip)
    return (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved or a.is_unspecified
            or (a.version == 4 and a in ipaddress.ip_network("100.64.0.0/10")))


def reg_domain(host):
    """Registrable domain under the ICANN section of the PSL (what you would register at a registrar)."""
    if is_ip(host):
        return None
    e = _icann(host)
    return e.top_domain_under_public_suffix or None


def platform_domain(host):
    """Registrable domain under the PSL incl. private section (foo.herokuapp.com, [withheld-host] ...)."""
    if is_ip(host):
        return None
    e = _priv(host)
    return e.top_domain_under_public_suffix or None


def tld(host):
    e = _icann(host)
    return e.suffix or None


def sha(b):
    return hashlib.sha256(b).hexdigest()
