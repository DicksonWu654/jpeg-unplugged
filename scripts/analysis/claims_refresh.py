"""Refresh only claim fields in shared analysis/site outputs; preserve all unrelated data."""
import json
import pathlib
import sys
import subprocess
from collections import Counter
import pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/analysis'))
sys.path.insert(0,str(ROOT/'scripts/claims'))
sys.path.insert(0,str(ROOT/'scripts/mutability'))
from common import OUT, SITE, jdump
from build_frame import load_claims,load_w6
from headlines import funnel
from build_reviewed import main as review
from score_reviewed import main as score
from build import main as mutability
from site_data import write_public_json,withheld_hosts


def metric(value,definition,denominator=None):
    d={'value':int(value),'definition':definition}
    if denominator is not None:
        d.update(denominator=int(denominator),pct=round(100*value/denominator,3) if denominator else None)
    return d


def summary(frame,claims_funnel):
    m=pd.read_csv(ROOT/'data/mutability/mutability.csv')
    c=m[m.in_w5];e=c[c.w5_claim_strength=='explicit-100%/fully']
    q=pd.read_csv(ROOT/'data/claims/claims_reviewed.csv')
    oc=pd.read_csv(ROOT/'data/claims/claim_outcomes.csv')
    pp='A live, effective URI-string setter, renderer/descriptor address swap, or upgrade on the ordinary token metadata/art path, controlled by one EOA or one multisig account. Data-only edits are excluded. A multisig account may require several signatures; this does not mean one private key.'
    meanings={
        'holds':'The selected project statement is supported for its stated art/metadata scope by the sampled saved evidence. This does not imply immutable control, successful browser rendering, or exhaustive collection coverage.',
        'onchain-data-offchain-pointer':'Art/data bytes or creative code are evidenced on Ethereum, while ordinary tokenURI or a marketplace media/preview field points off-chain. This supports a data-storage claim and is not a false claim.',
        'contradicted':'Saved evidence establishes that the selected project statement is false as stated, accounting for alternate data paths and its scope. Only this outcome may be called a failed claim.',
        'unverifiable':'The scoped statement is not resolved by available reads, incomplete coverage, gas limits or ambiguous wording; neither true nor false is asserted.'}
    metrics={
        'reviewed_collections':metric(q.address.nunique(),'Distinct original reviewed candidate collections; every saved candidate quote was read against raw evidence.'),
        'reviewed_quote_rows':metric(len(q),'All original quote rows for that population plus explicitly identified recovered quotes from the same raw evidence; casing duplicates remain visible.'),
        'valid_quote_rows':metric(q.claim_valid.sum(),'Quote rows accepted under the strict project-authorship and art/metadata storage rule.'),
        'claimants':metric(len(c),'Distinct reviewed collections with at least one accepted project-authored art/metadata storage statement.'),
        'excluded_collections':metric(q.address.nunique()-len(c),'Reviewed candidate collections with no accepted project-authored storage statement.'),
        'explicit_100_fully_claimants':metric(len(e),'Reviewed claimants whose selected strongest accepted quote explicitly says 100%, fully, entirely or completely on-chain; storage-forever alone is excluded.'),
        'claimants_repointable_one_account':metric(c.claim_repointable_one_account.sum(),pp,len(c)),
        'claimants_repointable_eoa':metric(c.repointable_eoa.sum(),'Same live-pointer definition, restricted to EOA control.',len(c)),
        'claimants_repointable_multisig':metric(c.repointable_multisig.sum(),'Same live-pointer definition, restricted to one multisig account.',len(c)),
        'explicit_repointable_one_account':metric(e.claim_repointable_one_account.sum(),pp+' Restricted to the explicit subset.',len(e)),
        'explicit_repointable_eoa':metric(e.repointable_eoa.sum(),'Explicit subset with live pointer control by an EOA.',len(e)),
        'explicit_repointable_multisig':metric(e.repointable_multisig.sum(),'Explicit subset with live pointer control by one multisig account.',len(e)),
        'claimants_data_mutable_only':metric(c.claim_data_mutable_only.sum(),'Reviewed claimants classed EOA/multisig mutable but lacking live EOA/multisig pointer power; data-only edits are not repointing.'),
        'explicit_data_mutable_only':metric(e.claim_data_mutable_only.sum(),'Same data-only definition, restricted to the explicit subset.'),
        'contradicted_claims':metric(c.claim_contradicted.sum(),meanings['contradicted'],len(c)),
        'explicit_contradicted_claims':metric(e.claim_contradicted.sum(),meanings['contradicted']+' Restricted to the explicit subset.',len(e)),
        'mutation_audit_contracts':metric(len(m),'Historical 606-contract mutation audit population retained to make before/after comparisons coherent; it is not the claimant denominator.'),
        'audit_repointable_eoa':metric(m.repointable_eoa.sum(),'The publication definition for repointable by a single EOA: live effective pointer power, including in-path dependencies and upgrades; excludes data-only changes.'),
        'audit_repointable_multisig':metric(m.repointable_multisig.sum(),'Historical mutation-audit contracts with live pointer power held by a multisig account.'),
        'audit_broad_eoa_mutable':metric(m.class_final.eq('eoa-mutable').sum(),'Diagnostic broad class: some EOA-controlled effective mutation path, including data-only edits. Must not be labelled repointable.'),
        'audit_broad_eoa_without_pointer':metric((m.class_final.eq('eoa-mutable') & ~m.repointable_eoa).sum(),'Difference between the broad EOA mutation class and the narrower live-pointer EOA definition.'),
        'claimants_in_census':metric(claims_funnel['claimants_in_census'],'Reviewed claimants with a completed census collection row; denominator for the ordinary-pointer funnel.'),
        'claimants_outside_census':metric(claims_funnel['claimants_not_yet_in_census'],'Reviewed claimants without a completed census row; scored separately with additional saved reads where available.')}
    for outcome,definition in meanings.items():
        metrics['outcome_'+outcome]=metric(oc.claim_outcome.eq(outcome).sum(),definition,len(c))
        metrics['explicit_outcome_'+outcome]=metric((oc.claim_outcome.eq(outcome)&oc.claim_strength.eq('explicit-100%/fully')).sum(),definition+' Explicit subset only.',len(e))
    return {'schema_version':2,'review_date':'2026-10-22','population':'The 283 original reviewed candidate collections in data/claims/review_population.csv; directory-only and rejected candidates are not claimants.',
            'evidence':'data/claims/claims_reviewed.csv; data/claims/claim_outcomes.csv; data/mutability/mutability.csv; data/mutability/reviewed_reads/',
            'metrics':metrics,'outcome_definitions':meanings,'site_compatibility':{'holds':'holds','partial':'onchain-data-offchain-pointer','fails':'contradicted','unverified':'unverifiable'},
            'funnel_definitions':{'claimants':'Reviewed claimants present in the census; excludes reviewed claimants outside the census.',
                'a_tokenURI_onchain':'Ordinary tokenURI/uri returned on-chain metadata in the census.',
                'b_media_also_onchain':'Stage a plus census onchain_candidate (metadata and sampled media on-chain).',
                'c_renders_unplugged_clean':'Legacy key: census onchain_candidate_clean, additionally excluding observed gallery unplugged failures where tested. This is a candidate count; only c_of_which_render_tested_w4 was browser tested.',
                'c_of_which_render_tested_w4':'Stage c collections actually covered by gallery, not all candidates.',
                'd_also_immutable':'Stage c plus mutability class_final immutable. This concerns current known mutation paths, not historical immutability.',
                'failed_at':'Legacy schema key for exclusion at pointer-funnel stages; these are NOT false-claim counts.',
                'known_mutation_path':'Stage c collections with a known non-immutable mutability class; includes data-only edits and is not the repointable count.',
                'live_pointer_power':'Stage c split by the narrow pointer_power measure: EOA, multisig, DAO/timelock, or none; matches the repointable definition.',
                'denominator':'Each prop stores k/n, percentage and 95% Wilson interval; n is the full subgroup, not its previous stage.'},
            'funnel':claims_funnel}


def refresh_site(frame,doc,m):
    lookup=frame.set_index('a');hosts=withheld_hosts()
    for filename in ['collections.json','collections_extra.json']:
        p=SITE/'data'/filename;data=json.loads(p.read_text())
        for row in data['collections']:
            a=row['address'].lower();claim=None
            if a in lookup.index:
                r=lookup.loc[a]
                if isinstance(r.claim_outcome,str):
                    claim={'strength':r.strength_site,'text':r.claim_text_clean,'source_url':r.source_url,
                           'verdict':r.claim_verdict,'outcome':r.claim_outcome,'reason':r.claim_reason}
            row['claim']=claim
        write_public_json(p,data,hosts)
    # Preserve unrelated counts/fields in the shared census JSON.
    p=SITE/'data/census.json';data=json.loads(p.read_text())
    rows=json.loads((SITE/'data/collections.json').read_text())['collections'];claimed=[r['claim'] for r in rows if r.get('claim')]
    cnt=Counter(r['verdict'] for r in claimed)
    data['claims']={'claimed':len(claimed),'verdicts':{s:cnt[s] for s in ['holds','partial','fails','unverified']},
                    'explicit_100':sum(r['strength']=='explicit-100%' for r in claimed),
                    'outcomes':dict(Counter(r['outcome'] for r in claimed)),'reviewed':True}
    data.setdefault('sampling',{})['claims_note']='Manually reviewed project-authored claims in the random stratum only; full reviewed population, control counts and outcome definitions are in claims_summary.json. Only contradicted/fails denotes a false claim.'
    write_public_json(p,data,hosts)
    p=SITE/'data/mutability.json';data=json.loads(p.read_text());c=m[m.in_w5];e=c[c.w5_claim_strength=='explicit-100%/fully']
    for key,sub in [('explicit',e),('generic',c[c.w5_claim_strength=='on-chain-generic']),('forever',c[c.w5_claim_strength=='storage-forever']),('none',m[~m.in_w5])]:
        data['by_claim'][key]={cl:int(sub.class_final.eq(cl).sum()) for cl in ['immutable','dao-or-timelock-mutable','multisig-mutable','eoa-mutable','unknown']};data['by_claim'][key]['total']=len(sub)
    data['funnel']={'claimants':len(c),'claimants_contradicted':int(c.claim_contradicted.sum()),'explicit':len(e),
        'explicit_contradicted':int(e.claim_contradicted.sum()),'explicit_contradicted_eoa':int((e.claim_contradicted&e.repointable_eoa).sum()),
        'data_only_mutable':int(c.claim_data_mutable_only.sum()),'claimants_repointable':int(c.claim_repointable_one_account.sum()),
        'explicit_repointable':int(e.claim_repointable_one_account.sum()),'definition':doc['metrics']['claimants_repointable_one_account']['definition']}
    data['claim_outcomes']={k:int(c.claim_outcome.eq(k).sum()) for k in doc['outcome_definitions']}
    data['claims_summary']='data/claims_summary.json'
    # Current quote membership also applies to the fixed historical timeline lanes.
    by=m.set_index('address')
    for lane in data.get('lanes',[]):
        r=by.loc[lane['contract'].lower()];lane['claim']=r.w5_claim_text if isinstance(r.w5_claim_text,str) else None
        if lane['lane']=='Moonbirds':
            lane['summary']='The core is owned by a 2-of-4 Safe. The renderer is held by one wallet key: onlyOwner setBaseUri changes illustrated-image URLs and setAnimationBaseUri changes animation URLs. Token holders choose pixelated versus illustrated art; the EOA also controls pixel-art scaling.'
    write_public_json(p,data,hosts)
    # Central public counts contain no per-host evidence or private input rows.
    write_public_json(SITE/'data/claims_summary.json',doc,hosts)


def main():
    review();score();mutability()
    subprocess.run([sys.executable,'-I',str(ROOT/'scripts/claims/report.py')],
                   stdout=subprocess.DEVNULL,check=True)
    p=OUT/'collections_enriched.parquet';f=pd.read_parquet(p)
    cols=[c for c in f if c.startswith(('claim_','w6_claim','w6_repointable')) or c in ['strength_site','source_url','source_type','n_claim_rows','outcome_evidence']]
    base=f.drop(columns=cols)
    f=base.merge(load_claims(),on='a',how='left')
    f['claim_tier']=f.claim_strength.map({'explicit-100%/fully':'explicit','on-chain-generic':'generic','storage-forever':'forever'}).fillna('')
    w6=load_w6()
    w6=w6[[c for c in w6 if c=='a' or c.startswith(('w6_claim','w6_repointable'))]]
    f=f.merge(w6,on='a',how='left')
    oc=pd.read_csv(ROOT/'data/claims/claim_outcomes.csv').set_index('address')
    for field in ['claim_outcome','claim_verdict','claim_reason','outcome_evidence']:f[field]=f.a.map(oc[field])
    pd.testing.assert_frame_equal(base,f[base.columns],check_dtype=True)
    f.to_parquet(p,index=False)
    hpath=OUT/'headlines.json';h=json.loads(hpath.read_text());h['claims_funnel']=funnel(f)
    doc=summary(f,h['claims_funnel']);h['claims_summary']=doc['metrics']
    jdump(doc,OUT/'claims_summary.json');jdump(h,hpath)
    refresh_site(f,doc,pd.read_csv(ROOT/'data/mutability/mutability.csv'))
    print('claims-only refresh:', {k:doc['metrics'][k]['value'] for k in ['claimants','explicit_100_fully_claimants','claimants_repointable_one_account','explicit_repointable_one_account','contradicted_claims','claimants_in_census']})


if __name__=='__main__':main()
