"""Shared helpers for claims web-directories extraction: claim classification, manifest lookup, verbatim verification."""
import json, re, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT/'data'/'raw'
_man = None
def manifest():
    global _man
    if _man is None:
        _man = {}
        for l in open(RAW/'MANIFEST.jsonl'):
            try: r = json.loads(l)
            except Exception: continue
            _man[r['path']] = r   # last entry wins
    return _man
def raw_for(key):
    p = f'data/raw/claims-web/{key}.html'
    r = manifest().get(p)
    return p, r
ONCHAIN = re.compile(r"(?i)(\bon[\s-]?chain|\bonchain|\bin[\s-]chain\b|(stored|lives?|lived|saved|written|encoded|generated|rendered|deployed|permanently|forever|entirely|fully)[^.]{0,30}\b(blockchain|ethereum|smart contract|the contract)\b|\b(blockchain|ethereum) forever)")
NEG = re.compile(r"(?i)(n't|\bnot\b|\bno longer\b|\bisn|\bnever\b|\bwithout\b|\bTweets\b|\boff[\s-]?chain\b|\bwhether\b|\bif\b|\bhow to\b|\bwhy\b)")
STRICT = re.compile(r'(?i)(100\s?%|fully|entirely|completely|wholly|totally|purely|all[\s-]on[\s-]?chain|\bfull[\s-]on[\s-]?chain|100 percent|every(thing| ?bit)? (is |lives |stored |on))')
FOREVER = re.compile(r'(?i)(forever|permanen|eternal|immutab|persist|outlive|last as long|for all time|never (disappear|go away))')
def strength(s):
    on = ONCHAIN.search(s)
    if not on or NEG.search(s): return None
    if STRICT.search(s) and re.search(r'(?i)on[\s-]?chain|blockchain|ethereum|contract', s): return 'explicit-100%/fully'
    if FOREVER.search(s): return 'storage-forever'
    return 'on-chain-generic'
RANK = {'explicit-100%/fully':3,'storage-forever':2,'on-chain-generic':1}
def sentences(text):
    for para in re.split(r'\n+', text):
        for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"“(])', para):
            s = s.strip()
            if 12 <= len(s) <= 400: yield s
def best_sentence(texts, raw, name=None, ok=lambda s: True):
    best = None
    nm = re.sub(r'[^a-z0-9]', '', (name or '').lower())
    for t in texts:
        if not t: continue
        for s in sentences(t):
            st = strength(s)
            if not st or s not in raw or not ok(s): continue
            has = bool(nm) and nm in re.sub(r'[^a-z0-9]', '', s.lower())
            sc = (RANK[st], has, -abs(len(s) - 90))
            if best is None or sc > best[0]: best = (sc, s, st)
    return (best[1], best[2]) if best else (None, None)

import html as _html
def html_candidates(raw):
    """Yield text snippets (visible text nodes + meta content attrs) that appear verbatim in raw."""
    raw2 = re.sub(r'(?is)<(script|style|noscript|svg)\b.*?</\1>', '\x00', raw)
    for m in re.finditer(r'(?is)<meta\b[^>]*?(?:name|property)=["\'](?:description|og:description|twitter:description)["\'][^>]*?content=["\']([^"\']*)["\']', raw2):
        yield m.group(1)
    for m in re.finditer(r'(?is)<meta\b[^>]*?content=["\']([^"\']*)["\'][^>]*?(?:name|property)=["\'](?:description|og:description|twitter:description)["\']', raw2):
        yield m.group(1)
    for node in re.split(r'<[^>]*>|\x00', raw2):
        node = node.strip()
        if node: yield node
def clean_ok(s):
    return not re.search(r'&[#a-zA-Z0-9]+;', s)
