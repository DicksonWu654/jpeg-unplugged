"""Top-100 bounded public API reads, preserving every response and failure."""
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import rawfetch as rf

OUT = ROOT / 'data/top100'
SOURCE = 'top100-api'
_last = {}


def get(url, key, refresh=False):
    """Single-threaded caller; per-host 2 req/s, full JSON/HTML <=2 MB."""
    from urllib.parse import urlsplit
    p = rf._cached(SOURCE, key, 'json')
    if p and not refresh:
        return json.loads(p.read_text())
    host = urlsplit(url).netloc
    last = None
    for attempt in range(3):
        time.sleep(max(0, _last.get(host, 0) + .5 - time.monotonic()))
        _last[host] = time.monotonic()
        body, status, error = b'', None, None
        try:
            req = urllib.request.Request(url, headers={'User-Agent': rf.UA['User-Agent'], 'Accept': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=25) as response:
                    status, body = response.status, response.read(2_000_001)
            except urllib.error.HTTPError as exc:
                status, body = exc.code, exc.read(2_000_001)
        except Exception as exc:
            error = str(exc)[:200]
        rf._save(SOURCE, f'{key}-attempt{attempt+1}-{time.time_ns()}', 'body', body,
                 {'url': url, 'method': 'GET', 'status': status, 'error': error,
                  'bytes': len(body), 'truncated': len(body) > 2_000_000})
        try:
            last = json.loads(body)
        except ValueError:
            last = {'_status': status, '_error': error or 'not-json'}
        if status == 200 and len(body) <= 2_000_000:
            rf._save(SOURCE, key, 'json', body, {'url': url, 'method': 'GET', 'status': status})
            return last
        if status not in (None, 429, 500, 502, 503, 504):
            return last
        time.sleep(3 * (attempt + 1))
    return last


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def evidence(key):
    """Locate the cached success or the last saved unsuccessful attempt."""
    cached=rf._cached(SOURCE,key,'json')
    if cached:return str(cached.relative_to(ROOT))
    attempts=sorted((ROOT/'data/raw'/SOURCE).glob(rf._safe(key)+'-attempt*.body'),key=lambda p:p.stat().st_mtime_ns)
    return str(attempts[-1].relative_to(ROOT)) if attempts else None
