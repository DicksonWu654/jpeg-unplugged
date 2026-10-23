"""Score storage statements separately from pointer control. No network activity.

A pointer outside Ethereum is not a contradiction without evidence addressing alternate data paths.
A sample supports a scoped storage observation, not collection-wide rendering or immutability.
"""
import base64
import json
import pathlib
import urllib.parse
import pandas as pd
from eth_abi import decode
ROOT=pathlib.Path(__file__).resolve().parents[2]
ONCHAIN={'data-uri','onchain-renderer'}
OUTCOMES={'holds','onchain-data-offchain-pointer','contradicted','unverifiable'}
SITE_VERDICT={'holds':'holds','onchain-data-offchain-pointer':'partial','contradicted':'fails','unverifiable':'unverified'}


def uri_metadata(uri):
    if not isinstance(uri,str) or not uri.startswith('data:'):return None
    try:
        head,body=uri.split(',',1)
        raw=base64.b64decode(body) if ';base64' in head else urllib.parse.unquote_to_bytes(body)
        j=json.loads(raw)
        return j if isinstance(j,dict) else None
    except (ValueError,UnicodeError):return None


def inline(value):
    return isinstance(value,str) and value.lstrip().startswith(('data:','<svg','<html','<!DOCTYPE','<!doctype'))


def main():
    claims=pd.read_csv(ROOT/'data/claims/claimants_reviewed.csv')
    f=pd.read_parquet(ROOT/'data/analysis/collections_enriched.parquet').set_index('a')
    more=json.loads((ROOT/'data/mutability/reviewed_reads/claimant_tokenuris.json').read_text())
    for row in more:
        raw=json.loads((ROOT/row['raw_path']).read_text())
        response=json.loads(raw['response_text'])
        try: row['uri']=decode(['string'],bytes.fromhex(response['result'][2:]))[0]
        except (KeyError,ValueError): row['uri']=None
    more={r['address']:r for r in more}
    overrides=json.loads((ROOT/'data/claims/outcome_adjudications.json').read_text())
    rows=[]
    for r in claims.to_dict('records'):
        a=r['address'];status='unverifiable';why='No successful sampled art/metadata read establishes the scoped claim.';evidence=[]
        if a in f.index:
            c=f.loc[a]
            evidence=['data/census/census_tokens.parquet']
            if c.meta_loc in ONCHAIN and c.media_loc in ONCHAIN:
                status='holds';why='Sampled token metadata and image bytes are supplied on-chain; storage observation does not assert immutable control or successful rendering.'
        elif a in more:
            c=more[a];evidence=[c['raw_path']];j=uri_metadata(c['uri'])
            if j:
                if inline(j.get('image')) or inline(j.get('image_data')):
                    status='holds';why='Saved eth_call returns on-chain JSON with inline image bytes; sampled storage claim supported, without an immutability or rendering guarantee.'
                elif inline(j.get('animation_url')):
                    status='onchain-data-offchain-pointer';why='Saved eth_call supplies the artwork program in inline animation data; the preview image remains an external pointer.'
                else:
                    why='On-chain metadata read succeeded, but its external media pointer does not establish or refute alternate on-chain artwork storage.'
            elif isinstance(c['uri'],str):
                why='Sampled tokenURI points outside Ethereum; alternate artwork storage is not established by this pointer read alone.'
            else:
                why='Sample read reverted or exceeded the provider gas cap; this is inconclusive about the project storage claim.'
        if a in overrides:
            o=overrides[a];status=o['outcome'];why=o['reason'];evidence+=o['evidence']
        for path in evidence:
            assert (ROOT/path).exists(), path
        assert status in OUTCOMES
        rows.append({'address':a,'collection':r['collection'],'selected_review_id':int(r['review_id']),
                     'claim_strength':r['claim_strength'],'claim_outcome':status,'claim_verdict':SITE_VERDICT[status],
                     'claim_reason':why,'outcome_evidence':';'.join(dict.fromkeys(evidence)),
                     'claim_data_contracts':';'.join(overrides.get(a,{}).get('data_contracts',[])),
                     'claim_data_control_note':overrides.get(a,{}).get('data_control_note',''),
                     'coverage':'Sampled token(s), except CryptoSkulls data coverage explicitly checks indices 0..9999.',
                     'claim_contradicted':status=='contradicted'})
    df=pd.DataFrame(rows)
    assert len(df)==len(claims) and df.address.is_unique
    df.to_csv(ROOT/'data/claims/claim_outcomes.csv',index=False)
    print('reviewed storage outcomes',df.claim_outcome.value_counts().to_dict())


if __name__=='__main__':main()
