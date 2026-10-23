"""Read-only packets for manual adjudication; no fetching or claim inference."""
import hashlib
import html
import json
import pathlib
import re
import sys
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/claims'))
import srcscan


def normalized(text):
    return ' '.join(html.unescape(text).replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"').split())


def source_files(rec):
    """Explorer payloads sometimes wrap standard JSON in more than one brace pair."""
    text = rec.get('SourceCode', '')
    at = text.find('{"sources":')
    if at >= 0:
        obj = json.JSONDecoder().raw_decode(text[at:])[0]
        return [(k, v['content']) for k, v in obj['sources'].items()]
    return srcscan.files_of(rec)


def packets():
    c = pd.read_csv(ROOT / 'data/claims/claims.csv').fillna('')
    c['address'] = c.address.str.lower()
    # The frozen reviewed review population, independent of later rebuilt in_w5 flags.
    addresses = set(pd.read_csv(ROOT / 'data/claims/review_population.csv').address)
    out = []
    for idx, r in c[c.address.isin(addresses)].iterrows():
        raw = ROOT / r.raw_path
        b = raw.read_bytes()
        text = b.decode(errors='replace')
        location = ''
        quote = r.claim_text
        quote_raw = raw
        if r.source_type == 'contract-source':
            rec = srcscan.load(r.address)
            files = [(fn, t, r.address) for fn, t in source_files(rec)]
            impl = rec.get('Implementation', '').lower()
            if impl and srcscan.have(impl):
                files += [(fn, t, impl) for fn, t in source_files(srcscan.load(impl))]
            hay = ''
            for fn, content, source_address in files:
                if quote in content or quote.replace('\\n', '\n') in content:
                    at = content.find(quote)
                    if at < 0: at = content.find(quote.replace('\\n', '\n'))
                    line = content[:at].count('\n') + 1
                    location = f'{fn}:{line}'
                    hay = content[max(0, at-180):at+len(quote)+180]
                    quote_raw = srcscan.src_path(source_address)
                    if not quote_raw.exists(): quote_raw = srcscan.bs_path(source_address)
                    break
            matched = bool(hay) or quote.startswith('ContractName:')
        else:
            hay = html.unescape(re.sub(r'<[^>]+>', ' ', text))
            try:
                j = json.loads(text)
                if isinstance(j, dict):
                    hay += '\n' + str(j.get('description', ''))
                    if j.get('props'): hay += '\n' + json.dumps(j['props'], ensure_ascii=False)
            except ValueError:
                pass
            nh, nq = normalized(hay), normalized(quote)
            at = nh.find(nq)
            matched = at >= 0
            if not matched and normalized(quote) in normalized(text):
                # Meta description attributes disappear under tag stripping.
                nh = normalized(text)
                at = nh.find(nq)
                matched = True
            if not matched:
                # Escaped JSON literals occur in HTML/serialized source payloads.
                try: decoded = bytes(text, 'utf-8').decode('unicode_escape')
                except UnicodeError: decoded = text
                nh = normalized(re.sub(r'<[^>]+>', ' ', decoded))
                at = nh.find(nq)
                matched = at >= 0
            hay = nh[max(0, at-150):at+len(nq)+150] if matched else nh[:500]
        out.append(dict(review_id=int(idx), **r.to_dict(), evidence_sha256=hashlib.sha256(b).hexdigest(),
                        evidence_quote_raw_path=str(quote_raw.relative_to(ROOT)),
                        evidence_quote_raw_sha256=hashlib.sha256(quote_raw.read_bytes()).hexdigest(),
                        evidence_quote_found=matched, evidence_location=location, evidence_context=normalized(hay)))
    extra = ROOT / 'data/claims/review_supplemental.json'
    if extra.exists():
        for q in json.loads(extra.read_text()):
            raw = ROOT / q['raw_path']
            text = raw.read_text()
            if q['source_type'] == 'contract-source':
                text = '\n'.join(t for _, t in source_files(srcscan.load(q['address'])))
            else:
                text += '\n' + str(json.loads(text).get('description', ''))
            q['evidence_quote_found'] = normalized(q['claim_text']) in normalized(text)
            q['evidence_sha256'] = hashlib.sha256(raw.read_bytes()).hexdigest()
            q['evidence_quote_raw_path'] = q['raw_path']
            q['evidence_quote_raw_sha256'] = q['evidence_sha256']
            assert q['evidence_quote_found'], q['review_id']
            out.append(q)
    return out


if __name__ == '__main__':
    out = packets()
    (ROOT / 'data/claims/review_packets.json').write_text(json.dumps(out, indent=1, ensure_ascii=False)+'\n')
    start, end = map(int, sys.argv[1:3]) if len(sys.argv)>2 else (0,283)
    names = sorted({(r['collection'],r['address']) for r in out})
    # one collection label per address (source collection labels may differ)
    pop=pd.read_csv(ROOT / 'data/claims/review_population.csv').sort_values(['name','address']).reset_index(drop=True)
    for i,r in pop.iloc[start:end].iterrows():
        print(f'\n[{i}] {r["name"]} {r.address}')
        for q in out:
            if q['address'] != r.address: continue
            print(f'ID {q["review_id"]} {q["source_type"]} {q["claim_strength"]} MATCH={q["evidence_quote_found"]} {q["evidence_location"]}')
            print('QUOTE:',q['claim_text'])
            print('RAW:',normalized(q['evidence_context']))
            if q['source_type'] != 'contract-source': print('URL:',q['source_url'])
