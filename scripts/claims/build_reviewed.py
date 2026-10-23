"""Materialize manual quote decisions; reject unreviewed input, then select one valid claim per address.

The historical claims.csv is a candidate/evidence inventory, never the publication claimant set.
"""
import json
import pathlib
import re
import sys
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/claims'))
from review_packets import packets


def main():
    decisions = json.loads((ROOT / 'data/claims/review_decisions.json').read_text())
    assert not (set(decisions['valid']) & set(decisions['invalid']))
    population = pd.read_csv(ROOT / 'data/claims/review_population.csv').fillna('').set_index('address')
    out = []
    for q in packets():
        i = str(q['review_id'])
        library = (q['source_type'] == 'contract-source' and
                   re.search(r'openzeppelin|chainlink|solmate|solady|erc721a|scripty|(?:^|/)(?:Base64|SSTORE2)\.sol',
                             q['evidence_location'], re.I))
        if library:
            assert i not in decisions['valid'], 'A dependency cannot override the strict claim rule: ' + i
            valid, reason = False, 'Dependency/library documentation; excluded automatically from project storage claims.'
        elif i in decisions['valid']:
            valid, reason = True, decisions['valid'][i]
        elif i in decisions['invalid']:
            valid, reason = False, decisions['invalid'][i]
        elif q['source_type'] == 'directory':
            valid, reason = False, 'Third-party directory/editorial text; no evidence that this wording is the project\'s own statement.'
        elif q['claim_strength'] == 'implied':
            valid, reason = False, 'Contract name, directory heading or implied association alone is not an art or metadata storage statement.'
        else:
            raise ValueError(f'Unreviewed candidate {i}: {q["collection"]}')
        if valid:
            # HTML meta descriptions are public project-authored descriptions too.
            raw = (ROOT / q['raw_path']).read_text(errors='replace')
            assert q['evidence_quote_found'] or q['claim_text'] in raw, i
        q.update(claim_valid=valid, claim_valid_reason=reason, reviewer='manual review 2026-10-22', reviewed_at='2026-10-22')
        if not q['collection']:
            q['collection'] = population.loc[q['address'], 'name'] or q['address']
        q['claim_strength_original'] = q['claim_strength']
        if valid and q['claim_strength'] == 'implied':
            q['claim_strength'] = 'on-chain-generic'
        # Normalize the old scanner's missed hyphen and entire-Ethereum variants.
        if valid and re.search(r'(?:100\s*%|fully|entirely|completely)[\s-]*(?:on[\s-]?chain|(?:stored\s+)?on\s+(?:the\s+)?Ethereum)', q['claim_text'], re.I):
            q['claim_strength'] = 'explicit-100%/fully'
        out.append(q)
    df = pd.DataFrame(out)
    assert df.address.nunique() == 283
    assert set(df.address) == set(pd.read_csv(ROOT / 'data/claims/review_population.csv').address)
    df['collection_claim_valid'] = df.groupby('address').claim_valid.transform('any')
    df.to_csv(ROOT / 'data/claims/claims_reviewed.csv', index=False)
    valid = df[df.claim_valid].copy()
    valid['rank'] = valid.claim_strength.map({'explicit-100%/fully':4,'storage-forever':3,'on-chain-generic':2,'implied':1})
    valid['source_preference'] = valid.source_type.map({'marketplace':0,'website':1,'contractURI':2,'contract-source':3})
    best = valid.sort_values(['address','rank','source_preference','review_id'], ascending=[True,False,True,True]).drop_duplicates('address')
    best.drop(columns=['rank','source_preference']).to_csv(ROOT / 'data/claims/claimants_reviewed.csv',index=False)
    collections = []
    for address, group in df.groupby('address'):
        selected = best[best.address == address]
        q = selected.iloc[0] if len(selected) else group.iloc[0]
        collections.append({'address': address, 'collection': q.collection,
                            'claim_valid': bool(group.claim_valid.any()),
                            'claim_valid_reason': q.claim_valid_reason,
                            'quote_rows_reviewed': len(group),
                            'selected_review_id': int(q.review_id) if len(selected) else None})
    pd.DataFrame(collections).to_csv(ROOT / 'data/claims/collections_reviewed.csv', index=False)
    print(f'{len(df)} quotes / {df.address.nunique()} collections reviewed; {len(valid)} valid quotes / {len(best)} claimants')
    print(best.claim_strength.value_counts().to_dict())


if __name__ == '__main__':
    main()
