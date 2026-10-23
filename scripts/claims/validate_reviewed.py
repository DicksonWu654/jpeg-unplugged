"""Offline evidence-integrity and publication-regression checks for the reviewed claim rebuild."""
import hashlib
import json
import pathlib
import sys
from collections import Counter
import pandas as pd
from eth_abi import encode,decode
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/mutability'))
from keccak import keccak256,selector
from skulls_coverage import lens,LENS


def raw_record(path):
    r=json.loads(path.read_text())
    assert hashlib.sha256(r['response_text'].encode()).hexdigest()==r['sha256'],path
    return r,json.loads(r['response_text'])


def main():
    q=pd.read_csv(ROOT/'data/claims/claims_reviewed.csv')
    c=pd.read_csv(ROOT/'data/claims/claimants_reviewed.csv').set_index('address')
    pop=pd.read_csv(ROOT/'data/claims/review_population.csv')
    o=pd.read_csv(ROOT/'data/claims/claim_outcomes.csv').set_index('address')
    m=pd.read_csv(ROOT/'data/mutability/mutability.csv').set_index('address')
    assert set(q.address)==set(pop.address) and len(pop)==283
    assert len(q)==518 and q.review_id.is_unique
    assert q.claim_valid_reason.notna().all()
    assert set(c.index)==set(q[q.claim_valid].address)==set(o.index)==set(m[m.in_w5].index)
    assert len(c)==160 and c.claim_strength.eq('explicit-100%/fully').sum()==103
    for path,grp in q.groupby('raw_path'):
        assert (ROOT/path).exists()
        assert set(grp.evidence_sha256)=={hashlib.sha256((ROOT/path).read_bytes()).hexdigest()}
    for path,grp in q.groupby('evidence_quote_raw_path'):
        assert set(grp.evidence_quote_raw_sha256)=={hashlib.sha256((ROOT/path).read_bytes()).hexdigest()}
    assert q[q.claim_valid].evidence_quote_found.all()
    assert not q[(q.source_type=='directory') & q.claim_valid].shape[0]
    assert not q[q.claim_valid & q.claim_text.str.startswith('ContractName:')].shape[0]
    rejected=['0x889edc2edab5f40e902b864ad4d7ade8e412f9b1','0x7aa4ac1399e2af80fb19c6d383e50232ccb57ad1',
              '0x375ea781c49eafedde07afe6196f885761f166ae','0x4db1f25d3d98600140dfc18deb7515be5bd293af',
              '0x38585ed7a204c2957bc0704a7898f96e6f5b5667','0xe31703379e32cad7502a594a854a76f9bb0be0e5',
              '0xb352131fe48571b7661390e65be4f12119e9686f','0xd3120c2aba62e9ecaff28054ffcca843d963f1d3']
    assert not set(rejected)&set(c.index)
    for a in ['0xc1caf0c19a8ac28c41fe59ba6c754e4b9bd54de9','0x8d04a8c79ceb0889bdd12acdf3fa9d207ed3ff63',
              '0x91047abf3cab8da5a9515c8750ab33b4f1560a7a','0xc3f733ca98e0dad0386979eb96fb1722a1a05e69',
              '0x97597002980134bea46250aa0510c9b90d87a587','0x8754f54074400ce745a7ceddc928fb1b7e985ed6']:
        assert o.loc[a,'claim_outcome']=='onchain-data-offchain-pointer'
    assert o.loc['0x23581767a106ae21c074b2276d25e5c3e136a68b','claim_outcome']=='holds'
    assert m.repointable_eoa.equals(m.pointer_power.eq('eoa'))
    assert m.repointable_multisig.equals(m.pointer_power.eq('multisig'))
    assert m.repointable_one_account.equals(m.pointer_power.isin(['eoa','multisig']))
    assert m.claim_repointable_one_account.equals(m.in_w5 & m.repointable_one_account)
    assert m.claim_contradicted.equals(m.claim_outcome.eq('contradicted'))
    assert m.claim_contradicted_strong.equals(m.claim_contradicted & m.w5_claim_strength.eq('explicit-100%/fully'))
    assert m.claim_repointable_one_account.sum()==81
    assert m.loc[c[c.claim_strength=='explicit-100%/fully'].index,'claim_repointable_one_account'].sum()==53
    assert m.repointable_eoa.sum()==302 and m.class_final.eq('eoa-mutable').sum()==323
    assert m.loc['0xc1caf0c19a8ac28c41fe59ba6c754e4b9bd54de9','claim_data_contracts']=='0x9a7b94954751d539c63e16aa6e0557c451251394'
    records={}
    for p in (ROOT/'data/mutability/reviewed_reads').glob('*.json'):
        r=json.loads(p.read_text())
        if 'response_text' not in r:continue
        r,j=raw_record(p);records[p.name]=(r,j)
        if r.get('request'):
            assert r['request']['method'] in {'eth_call','eth_blockNumber','eth_getCode','eth_getTransactionByHash','eth_chainId','eth_getBlockByNumber'}
    assert records['chain_id.json'][1]['result']=='0x1'
    cov=json.loads((ROOT/'data/mutability/reviewed_reads/cryptoskulls_coverage.json').read_text())
    for sig,length in [('getAttrs(uint16)',10),('getPixels(uint16)',576)]:
        ranges=sorted((r for r in cov['ranges'] if r['signature']==sig),key=lambda r:r['start'])
        position=0
        for row in ranges:
            assert row['start']==position and row['valid']==row['end_exclusive']-row['start']
            position=row['end_exclusive']
            record,response=records[pathlib.Path(row['raw_path']).name]
            assert record['request']['params'][1]==cov['block']
            assert record['request']['params'][2][LENS]['code']==lens(row['start'],row['end_exclusive'],sig,length)
            raw=bytes.fromhex(response['result'][2:])
            assert int.from_bytes(raw[:32],'big')==row['valid'] and '0x'+raw[32:].hex()==row['digest']
        assert position==10000
        # Independent known-output check: the EVM lens digest must equal the hash
        # of the standalone response for token 1 at the control's pinned block.
        # This later control validates the lens algorithm; it need not use the
        # earlier full-coverage block after a public provider's archive cutoff.
        control_request,control=records['coverage_control_fresh_'+sig.split('(')[0]+'.json']
        control_block=control_request['request']['params'][1]
        calldata=selector(sig)+encode(['uint16'],[1]).hex()
        standalone=[j['result'] for r,j in records.values() if (r.get('request') or {}).get('method')=='eth_call'
                    and r['request']['params'][0].get('to')==cov['contract']
                    and r['request']['params'][1]==control_block
                    and r['request']['params'][0].get('data')==calldata and 'result' in j]
        assert standalone
        raw=bytes.fromhex(control['result'][2:])
        assert int.from_bytes(raw[:32],'big')==1
        expected=keccak256(bytes(32)+keccak256(bytes.fromhex(standalone[0][2:])))
        assert raw[32:]==expected, sig
    h=json.loads((ROOT/'data/analysis/headlines.json').read_text())
    s=json.loads((ROOT/'data/analysis/claims_summary.json').read_text())
    assert h['claims_summary']==s['metrics'] and h['claims_funnel']==s['funnel']
    for k,v in s['metrics'].items():assert isinstance(v['value'],int) and v['definition'],k
    assert s['metrics']['claimants']['value']==len(c)
    assert sum(s['metrics']['outcome_'+k]['value'] for k in s['outcome_definitions'])==len(c)
    f=pd.read_parquet(ROOT/'data/analysis/collections_enriched.parquet')
    assert set(f[f.claim_outcome.notna()].a)==set(c.index)&set(f.a)
    expected_map={'holds':'holds','onchain-data-offchain-pointer':'partial','contradicted':'fails','unverifiable':'unverified'}
    for filename in ['collections.json','collections_extra.json']:
        doc=json.loads((ROOT/'site/data'/filename).read_text())
        for row in doc['collections']:
            claim=row.get('claim');a=row['address'].lower()
            assert bool(claim)==(a in c.index)
            if claim:
                assert claim['outcome']==o.loc[a,'claim_outcome']
                assert claim['verdict']==expected_map[claim['outcome']]
                assert claim['source_url'].startswith(('https://','http://'))
    site=json.loads((ROOT/'site/data/claims_summary.json').read_text())
    assert site==s
    random=json.loads((ROOT/'site/data/collections.json').read_text())['collections']
    census=json.loads((ROOT/'site/data/census.json').read_text())
    actual=[r['claim'] for r in random if r.get('claim')]
    assert census['claims']['claimed']==len(actual)==15
    assert census['claims']['verdicts']=={k:Counter(r['verdict'] for r in actual)[k] for k in ['holds','partial','fails','unverified']}
    print(f'PASS: {len(q)} quote decisions / {len(pop)} collections; {len(c)} scored claimants; {len(records)} raw records hash-verified; complete 10,000-skull attribute/pixel coverage; counts and generated site fields agree.')


if __name__=='__main__':main()
