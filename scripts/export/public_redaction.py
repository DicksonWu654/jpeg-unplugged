"""Redact withheld origins and provider failure signatures from public datasets."""
import base64
import binascii
import csv
import html
import json
import re
import zlib
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, unquote

WITHHELD = "[withheld-host]"
URL = re.compile(r"(?:[a-z][a-z0-9+.-]*:)?//[^\s\"'<>`\\]+", re.I)
HTTP_FAILURE = re.compile(r"\bhttp[- :]+([45])\d{2}\b", re.I)
RAW_NXDOMAIN = re.compile(r"(?<!dns-)\bnxdomain\b", re.I)
# These describe a missing provider resource, rather than an ordinary HTTP/DNS failure.
FINGERPRINT = re.compile(
    r"no[\s_-]*such[\s_-]*bucket|the specified bucket does not exist|"
    r"no[\s_-]*such[\s_-]*app|there['’]s nothing here,? yet|"
    r"deployment[\s_-]*not[\s_-]*found|the deployment could not be found|"
    r"there isn['’]t a github pages site here|github[\s_-]*pages[\s_-]*404|"
    r"<title>site not found|not found - request id|netlify[\s_-]*not[\s_-]*found|"
    r"site not found|firebase hosting setup complete|firebase[\s_-]*site[\s_-]*not[\s_-]*found|"
    r"there is nothing here yet|nothing is here yet|pages[\s_-]*dev[\s_-]*nothing[\s_-]*here|"
    r"project not found|surge[\s_-]*not[\s_-]*found|"
    r"error 404 - web app not found|microsoft azure app service - welcome|azure[\s_-]*webapp[\s_-]*404|"
    r"fastly error: unknown domain|fastly[\s_-]*unknown[\s_-]*domain|"
    r"sorry, this shop is currently unavailable|shopify[\s_-]*unavailable|"
    r"the gods are wise, but do not know of the site which you seek|404 error unknown site|pantheon[\s_-]*unknown[\s_-]*site|"
    r"repository not found|domain is not configured|bitbucket/ghost[\s_-]*unconfigured|"
    r"not_found_gateway|pinata[\s_-]*gateway[\s_-]*gone|fleek[\s_-]*not[\s_-]*found|"
    r"err_ngrok_3200|ngrok[\s_-]*offline|"
    r"(?:azure(?:websites|[\s_-]*(?:appservice|blob|cdn|vm|tm))|aws[\s_-]*beanstalk|heroku|"
    r"firebase[\s_-]*hosting|github[\s_-]*pages|vercel|netlify|surge)[^\n]{0,100}nxdomain|"
    r"nxdomain[^\n]{0,100}(?:azure(?:websites|[\s_-]*(?:appservice|blob|cdn|vm|tm))|aws[\s_-]*beanstalk|"
    r"heroku|firebase[\s_-]*hosting|github[\s_-]*pages|vercel|netlify|surge)", re.I,
)


# Match embedded URIs as well as URI-valued cells. Percent-encoded whole URIs
# are normalized by encoded_payload before this expression is used.
DATA_URI = re.compile(r"data(?:%3a|:)[^\s\"'<>)]*?(?:,|%2c)[^\s\"'<>)]*", re.I)
BASE64_TEXT = re.compile(r"[A-Za-z0-9+/_-]{16,}={0,2}\Z")


def encoded_payload(text):
    """Return decoded text and its encoder, including recoverable truncated prefixes.

    Census uri_raw values may be truncated mid-base64. Retain the decodable
    prefix, rather than treating missing padding as evidence of no hidden host.
    Binary image/font payloads are not text and remain untouched.
    """
    normalized = unquote(text) if re.match(r"data(?:%3a|:)", text, re.I) else text
    uri = normalized.lower().startswith("data:") and "," in normalized
    if uri:
        header, payload = normalized.split(",", 1)
        encoded = ";base64" in header.lower()
    else:
        if not BASE64_TEXT.fullmatch(text):
            return None
        header, payload, encoded = "", text, True
    if not encoded:
        return unquote(payload), lambda clean: header + "," + quote(clean, safe="")
    payload = unquote(payload)
    compact = re.sub(r"\s+", "", payload).rstrip("=")
    if not re.fullmatch(r"[A-Za-z0-9+/_-]*", compact):
        return None
    if len(compact) % 4 == 1:
        compact = compact[:-1]
    try:
        raw = base64.b64decode(compact + "=" * (-len(compact) % 4), altchars=b"-_", validate=True)
        compressed = raw.startswith(b"\x1f\x8b")
        if compressed:
            inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
            raw = inflater.decompress(raw, 32 * 1024 * 1024)
            if inflater.unconsumed_tail:
                raise ValueError("compressed payload exceeds scan limit")
        # An incomplete final UTF-8 sequence is possible in a truncated cell.
        decoded = raw.decode("utf8", errors="replace")
    except (binascii.Error, zlib.error):
        return None
    if "\ufffd" in decoded[:-1] or "\x00" in decoded:
        return None
    if not uri and not decoded.lstrip().startswith(("{", "[", "<svg", "<?xml")):
        return None

    def encode(clean):
        raw = clean.encode("utf8")
        if compressed:
            import gzip
            raw = gzip.compress(raw, mtime=0)
        value = base64.b64encode(raw).decode("ascii")
        return header + "," + value if uri else value
    return decoded, encode


def decoded_strings(text, depth=0):
    """Visit decoded URI/JSON/SVG text without executing artwork or metadata."""
    if depth > 32:
        raise ValueError("encoded payload nesting exceeds scan limit")
    yield text
    decoded = encoded_payload(text)
    if decoded:
        payload, _ = decoded
        try:
            obj = json.loads(payload)
        except (ValueError, RecursionError):
            yield from decoded_strings(payload, depth + 1)
        else:
            yield from value_strings(obj, depth + 1)
    else:
        for match in DATA_URI.finditer(text):
            if match.group() != text:
                yield from decoded_strings(match.group(), depth + 1)


def value_strings(value, depth=0):
    if isinstance(value, str):
        yield from decoded_strings(value, depth)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from value_strings(key, depth)
            yield from value_strings(item, depth)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from value_strings(item, depth)
    elif type(value).__module__ == "numpy" and hasattr(value, "tolist"):
        yield from value_strings(value.tolist(), depth)


def load_hosts(path, *, required=False):
    path = Path(path)
    if not path.exists() and not required:
        return []
    with path.open(newline="", encoding="utf8") as fh:
        names = {(r.get("host") or r.get("hostname") or "").strip().lower()
                 for r in csv.DictReader(fh)} - {""}
    if required and not names:
        raise ValueError("withheld host list is empty")
    return sorted(names, key=len, reverse=True)


def load_domain_hints(path):
    """Hide standalone parent-domain hints that could rejoin provider and DNS evidence."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf8") as fh:
        return sorted({r.get("reg_domain", "").strip().lower() for r in csv.DictReader(fh)} - {""},
                      key=len, reverse=True)


@lru_cache(maxsize=8)
def host_pattern(names):
    """Factor shared prefixes so scanning long payloads does not try every host."""
    root = {}
    for name in names:
        node = root
        for char in name:
            node = node.setdefault(char, {})
        node[""] = {}

    def emit(node):
        parts = [re.escape(char) + emit(child) for char, child in node.items() if char]
        body = parts[0] if len(parts) == 1 else "(?:" + "|".join(parts) + ")" if parts else ""
        return "(?:" + body + ")?" if "" in node and body else body
    return emit(root)


class PublicRedactor:
    def __init__(self, hosts, domain_hints=()):
        self.names = re.compile(host_pattern(tuple(hosts)), re.I) if hosts else None
        # Include surrounding labels so an alias/subdomain cannot retain a resource name.
        self.tokens = re.compile(r"[a-z0-9.-]*(?:" + self.names.pattern + r")[a-z0-9.-]*", re.I) if hosts else None
        self.hints = re.compile(r"(?<![a-z0-9.-])(?:" + host_pattern(tuple(domain_hints))
                                + r")(?![a-z0-9.-])", re.I) if domain_hints else None
        self.host_values = 0
        self.failure_values = 0

    def has_host(self, text):
        if not any(char in text for char in (".", "%", "&")):
            return False
        decoded = unquote(html.unescape(text))
        return bool((self.names and self.names.search(decoded)) or (self.hints and self.hints.search(decoded)))

    def mask_names(self, text):
        if self.tokens:
            text = self.tokens.sub(WITHHELD, text)
        if self.hints:
            text = self.hints.sub(WITHHELD, text)
        return text

    def text(self, text, depth=0):
        if depth > 32:
            raise ValueError("encoded payload nesting exceeds redaction limit")
        decoded = encoded_payload(text)
        if decoded:
            payload, encode = decoded
            before = (self.host_values, self.failure_values)
            try:
                obj = json.loads(payload)
            except (ValueError, RecursionError):
                clean = self.text(payload, depth + 1)
            else:
                clean = json.dumps(self.value(obj, depth + 1), ensure_ascii=False, separators=(",", ":"))
            if before != (self.host_values, self.failure_values):
                return encode(clean)
        else:
            text = DATA_URI.sub(lambda m: self.text(m.group(), depth + 1)
                                if m.group() != text else m.group(), text)
        fingerprint = FINGERPRINT.search(text)
        if self.has_host(text):
            self.host_values += 1
            text = URL.sub(lambda m: WITHHELD if self.has_host(m.group()) else m.group(), text)
            text = self.mask_names(text)
            # Percent-encoded host names outside a URL must not survive either.
            if self.has_host(text):
                text = self.mask_names(unquote(html.unescape(text)))
        if fingerprint:
            self.failure_values += 1
            return "dns-nxdomain" if "nxdomain" in text.lower() else "http-4xx"
        # Use the same classes for ordinary failures, so a newly generic value
        # cannot itself identify the collections whose provider signature was removed.
        clean = HTTP_FAILURE.sub(r"http-\1xx", text)
        clean = RAW_NXDOMAIN.sub("dns-nxdomain", clean)
        self.failure_values += clean != text
        return clean

    def value(self, value, depth=0):
        if isinstance(value, str):
            return self.text(value, depth)
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                key = self.text(key, depth) if isinstance(key, str) else key
                item = self.value(item, depth)
                if key in result:
                    raise ValueError("redaction would merge dictionary keys")
                result[key] = item
            return result
        if isinstance(value, (list, tuple)):
            return [self.value(v, depth) for v in value]
        # Arrow list columns are returned as numpy arrays by pandas.
        if type(value).__module__ == "numpy" and hasattr(value, "tolist"):
            return self.value(value.tolist(), depth)
        return value

    def file(self, path):
        """Rewrite only changed files. Return whether any public value changed."""
        path = Path(path)
        before = (self.host_values, self.failure_values)
        suffix = path.suffix.lower()
        if suffix == ".parquet":
            import pandas as pd
            frame = pd.read_parquet(path)
            for column in frame:
                if pd.api.types.is_object_dtype(frame[column]) or pd.api.types.is_string_dtype(frame[column]):
                    frame[column] = frame[column].map(self.value)
            frame.columns = [self.text(c) for c in frame.columns]
            if before != (self.host_values, self.failure_values):
                frame.to_parquet(path, index=False)
        elif suffix in (".csv", ".tsv"):
            csv.field_size_limit(1 << 30)
            delimiter = "\t" if suffix == ".tsv" else ","
            with path.open(newline="", encoding="utf8") as fh:
                rows = [[self.text(v) for v in row] for row in csv.reader(fh, delimiter=delimiter)]
            if before != (self.host_values, self.failure_values):
                with path.open("w", newline="", encoding="utf8") as fh:
                    csv.writer(fh, delimiter=delimiter).writerows(rows)
        elif suffix in (".json", ".jsonl"):
            old = path.read_text(encoding="utf8")
            if suffix == ".json":
                result = self.value(json.loads(old))
                new = json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
            else:
                new = "".join(json.dumps(self.value(json.loads(line)), ensure_ascii=False, separators=(",", ":")) + "\n"
                              for line in old.splitlines() if line.strip())
            if before != (self.host_values, self.failure_values):
                path.write_text(new, encoding="utf8")
        else:
            try:
                old = path.read_text(encoding="utf8")
            except UnicodeDecodeError:
                return False
            # Preserve code/prose; sanitize only embedded URI payloads and host tokens.
            new = DATA_URI.sub(lambda m: self.text(m.group()), old)
            if self.has_host(new):
                self.host_values += 1
                new = URL.sub(lambda m: WITHHELD if self.has_host(m.group()) else m.group(), new)
                new = self.mask_names(new)
                if self.has_host(new):
                    new = self.mask_names(unquote(html.unescape(new)))
            if new != old:
                path.write_text(new, encoding="utf8")
        return before != (self.host_values, self.failure_values)

    def tree(self, root):
        return sum(self.file(p) for p in sorted(Path(root).rglob("*")) if p.is_file())


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tree", type=Path)
    ap.add_argument("withheld_hosts", type=Path)
    args = ap.parse_args()
    redactor = PublicRedactor(load_hosts(args.withheld_hosts, required=True), load_domain_hints(args.withheld_hosts))
    changed = redactor.tree(args.tree)
    print(f"public data redaction: {changed} files; {redactor.host_values} host-bearing values; "
          f"{redactor.failure_values} failure values generalized")
