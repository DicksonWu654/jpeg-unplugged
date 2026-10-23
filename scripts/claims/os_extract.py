import re, sys, json, pathlib, html
for s in sys.argv[1:]:
    t = pathlib.Path(f'data/raw/claims-web/{s}.html').read_text(errors='replace')
    print('##', s)
    m = re.search(r'<meta[^>]+(?:name|property)="(?:og:)?description"[^>]+content="([^"]*)"', t)
    print('  meta:', html.unescape(m.group(1))[:400] if m else None)
    ds = []
    for m in re.finditer(r'"description":"((?:[^"\\]|\\.)*)"', t):
        d = m.group(1)
        if d not in ds and re.search(r'chain', d, re.I): ds.append(d)
    for d in ds[:3]: print('  desc:', d[:500])
    print('  addrs:', sorted(set(re.findall(r'0x[0-9a-fA-F]{40}', t)))[:5])
