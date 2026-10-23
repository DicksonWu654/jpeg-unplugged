"""Audit cardinality, raw provenance, liveness evidence and release redaction."""
import base64
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import zipfile
from common import ROOT,OUT
from build import REDACTOR,clean
from crosscheck import parse_page
from public_redaction import value_strings


def load(path):return json.loads(path.read_text())


def main():
    rows=load(OUT/'collections.json');tokens=load(OUT/'tokens.json');summary=load(OUT/'summary.json')
    site=load(ROOT/'site/data/top100.json');cross=load(OUT/'ranking_crosscheck.json')
    assert site['summary']==summary and site['collections']==rows
    assert len(rows)==len(cross)==100 and [r['rank'] for r in rows]==list(range(1,101))
    assert len({r['contract'] for r in rows})==100
    assert all(rows[i]['all_time_volume']>=rows[i+1]['all_time_volume'] for i in range(99))
    assert all(r['samples']>=3 for r in rows)
    assert next(r for r in rows if r['name']=='Ethereum Name Service')['kind']=='domain-name'
    assert len(list(csv.DictReader((OUT/'top100.csv').open())))==100
    assert len(tokens)==summary['counts']['sampled_units']
    # Independent primary-source identity/volume binding to saved responses.
    source=[]
    for offset in (0,100):
        page=load(ROOT/f'data/raw/top100-api/cryptoslam-ranking-{offset}.json')['data']
        assert page['timePeriod']=='all'
        source+=page['saleSummaries']
    byrank={r['rank']:r for r in source}
    for row in rows:
        raw=byrank[row['source_rank']]
        assert raw['valueUSD']==row['all_time_volume'] and raw['platformName']=='Ethereum'
        identity=load(ROOT/row['identity_evidence'])['data']
        assert set(identity['contractAddress'].lower().split('|'))==set(row['contracts'])
        assert row['contract'] in row['contracts']
        for address in row['contracts']:
            validity=load(ROOT/f'data/raw/top100-sample-validity/{address}/result.json')
            assert not validity.get('invalid'),(row['name'],'stale/burned sample remains')
            assert not validity.get('rpc_unknown'),(row['name'],'ownership check unresolved')
        for control in row['control']:
            assert control['evidence'] and (ROOT/control['evidence']).exists()
    # The secondary source must really be all-time and must contain all saved rows.
    slugs=[]
    for page in (1,2,3):
        variables,items=parse_page((ROOT/f'data/raw/top100-api/opensea-ranking-page-{page}.html').read_text())
        assert (variables.get('offset') or 0)==50*(page-1)
        slugs.extend(x['collection']['slug'] for x in items)
    assert slugs==[r['slug'] for r in load(OUT/'secondary_ranking.json')]
    for row in load(OUT/'secondary_ranking.json'):
        assert row['identity_evidence'] and (ROOT/row['identity_evidence']).is_file()
    for row in cross:
        if row.get('opensea_evidence'):assert (ROOT/row['opensea_evidence']).is_file()
    # A fresh verdict must refer to real recorded attempts, not a stale result label.
    evidence={};body_checks=0;attempt_checks=0
    for token in tokens:
        address=token['contract']
        if address not in evidence:
            directory=ROOT/f'data/raw/top100-census/{address}'
            records=[json.loads(l) for l in gzip.open(directory/'evidence.jsonl.gz','rt')]
            assert len({r['seq'] for r in records})==len(records)
            evidence[address]={r['seq']:r for r in records}
            with zipfile.ZipFile(directory/'bodies.zip') as archive:
                for record in records:
                    if record.get('body_file') and record.get('stored_bytes')==record.get('bytes'):
                        assert hashlib.sha256(archive.read(record['body_file'])).hexdigest()==record['sha256']
                        body_checks+=1
        targets=[token['metadata_attempts']]+[m['attempts'] for m in token['media']]
        for attempts in targets:
            for attempt in attempts:
                recorded=evidence[address][attempt['seq']]
                assert attempt['status']==recorded.get('status')
                if attempt.get('sha256') is None and recorded.get('bytes')==0:
                    # census can retain 2xx media headers followed by a body timeout;
                    # Evidence hashes the empty saved body, while the fetch hash is null.
                    assert recorded.get('sha256')==hashlib.sha256(b'').hexdigest()
                else:
                    assert attempt.get('sha256')==recorded.get('sha256')
                if attempt['v']=='alive':assert attempt['status'] and 200<=attempt['status']<300
                if attempt.get('error_kind') in ('timeout','dns-temp') or attempt['status'] in (408,425,429):
                    assert attempt['v']!='dead'
                attempt_checks+=1
        # Every network death has the required multiple passes/gateways.
        targets2=[(token['derived']['meta_verdict'],token['metadata_attempts'])]
        targets2 += [(m['liveness'],m['attempts']) for m in token['media']]
        for verdict,attempts in targets2:
            if verdict=='dead' and attempts:
                negatives=[a for a in attempts if a['v']=='dead']
                assert {1,2}.issubset({a['pass'] for a in attempts})
                assert len({a['pass'] for a in negatives})>=2 or len({a.get('gateway') for a in negatives})>=2
    # Verify the final hash index; repeated path entries are compared at their last revision.
    latest={r['path']:r for r in load(OUT/'evidence_index.json') if r.get('path') and r.get('sha256')}
    for name,record in latest.items():
        p=ROOT/name
        assert p.is_file(),name
        assert hashlib.sha256(p.read_bytes()).hexdigest()==record['sha256'],name
    from common import write
    write(OUT/'validation.json',{'status':'pass','collections':100,'sampled_units':len(tokens),
                                'attempt_references_checked':attempt_checks,'complete_body_hashes_checked':body_checks,
                                'evidence_files_checked':len(latest),'ownership':'no known stale/burned IDs in active samples',
                                'ranking':'primary volume/identity bindings and all-time secondary pages verified',
                                'release_safety':'all output paths and nested/encoded strings checked against withheld origin list'})
    # Scan every study area file, including uncommitted logs and nested payloads.
    paths=list((ROOT/'scripts/top100').glob('*.py'))+[p for p in OUT.rglob('*') if p.is_file()]
    paths += [ROOT/'docs/methods/top100.md',ROOT/'site/data/top100.json']
    for p in paths:
        if '__pycache__' in p.parts:continue
        text=p.read_text()
        values=load(p) if p.suffix=='.json' else text
        for value in value_strings(values):
            assert not REDACTOR.has_host(value),f'withheld origin in {p.relative_to(ROOT)}'
    # Real withheld names are tested without exposing them in test output/source.
    from public_redaction import load_hosts
    host=load_hosts(Path(os.environ.get("WITHHELD_HOSTS_FILE", "withheld_hosts.csv")),required=True)[0]
    payload='data:application/json;base64,'+base64.b64encode(json.dumps({'image':'https://'+host+'/art.png'}).encode()).decode()
    redacted=clean({'payload':payload,'host':host})
    assert redacted['host']=='a dead server'
    assert all(not REDACTOR.has_host(v) for v in value_strings(redacted))
    print(f'PASS: 100 ranked collections, {len(tokens)} units, {attempt_checks} attempt references, {body_checks} full-body hashes, {len(latest)} evidence files; all new files pass withheld-host scan.')


if __name__=='__main__':main()
