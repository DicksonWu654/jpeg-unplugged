"""Build the public top-100 census from saved evidence; no network requests."""
import collections
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from common import ROOT, OUT, write
from refresh import c, PUNKS, PUNK_DATA
from pointers import audit
sys.path.insert(0,str(ROOT/'scripts/export'))
from public_redaction import PublicRedactor, load_hosts, load_domain_hints

HOSTS=Path(os.environ.get("WITHHELD_HOSTS_FILE", "withheld_hosts.csv"))
REDACTOR=PublicRedactor(load_hosts(HOSTS,required=True),load_domain_hints(HOSTS))
ORDER={'unknown':0,'immutable':1,'dao-or-timelock-mutable':2,'multisig-mutable':3,'eoa-mutable':4}
KINDS={
    'sorare':'game-sports','flying-tulip-put-1':'financial-position','pandora-9':'hybrid-fungible-nft',
    'otherdeed':'virtual-land','nft-worlds':'virtual-land','webbland1':'virtual-land',
    'metroverse-city-block':'virtual-land','arcade-land':'virtual-land','treeverse':'game-land',
    'wolf-game':'game','cyberkongz-vx-1':'game-avatar','vox-collectibles':'game-avatar','town-star':'game',
    'frontier-game':'game','fighter':'game','impostors-genesis':'game-avatar','rumblekongleague':'game-avatar',
    'premint-collector':'membership','full-send-metacard':'membership','888-inner-circle':'membership',
    'ethereum-name-service':'domain-name','0x57f1887a8bf19b14fc0df6fd9b2acc9af147ea85':'domain-name',
    'sewerpass':'access-pass','rtfkt-clonex-mintvial':'mint-pass','mysterybean':'mint-pass',
    'elemental-1':'art-avatar','emblem-vault-v4':'asset-vault','azuki-elemental-beans':'mint-pass',
}


def clean(obj):
    value=REDACTOR.value(obj)
    def replace(x):
        if isinstance(x,str):
            x=x.replace('[withheld-host]','a dead server')
            # Even a redacted authentication parameter is unnecessary in public
            # provenance URLs. Preserve all request-defining query parameters.
            return re.sub(r'''([?&])apikey=[^&\s"']*(&?)''',
                          lambda m:m[1] if m[2] else '',x,flags=re.I)
        if isinstance(x,list):return [replace(v) for v in x]
        if isinstance(x,dict):return {replace(k):replace(v) for k,v in x.items()}
        return x
    return replace(value)


def exported(path,obj):
    write(path,clean(obj))


def mixture(values):
    values=sorted(set(v for v in values if v))
    return values[0] if len(values)==1 else 'mixed('+','.join(values)+')' if values else 'unresolved'


def worst(classes):
    if any(v in classes for v in ('eoa-mutable','multisig-mutable','dao-or-timelock-mutable')):
        return max(classes,key=lambda k:ORDER.get(k,0))
    return 'unknown' if 'unknown' in classes or not classes else 'immutable'


def controls(address):
    a,path=audit(address)
    mutators=[m for m in a.get('mutators',[]) if m.get('category') in ('uri','renderer','upgrade')
              and not m.get('frozen') and m.get('effective')!='no']
    p=ROOT/f'data/raw/top100-pointers/{address}/result.json'
    pointers=json.loads(p.read_text())['getters'] if p.exists() else []
    return {'contract':address,'class':a.get('class_final','unknown'),'pointer_power':a.get('pointer_power'),
            'reason':a.get('class_reason'),'owner':a.get('owner'),'proxy':a.get('proxy'),
            'live_mutators':[{k:m.get(k) for k in ('name','sig','category','power','holders','effective','reason')} for m in mutators],
            'lock_flags':a.get('lock_views'),'dependencies':[
                {'contract':d['address'],'via':d.get('via'),'class':d.get('analysis',{}).get('class_direct'),
                 'in_tokenuri_path':bool(d.get('in_tokenuri_path') or d.get('via_setter'))} for d in a.get('dependencies',[])],
            'pointer_getters':pointers,'analyzed_at':a.get('analyzed_at'),
            'history_incomplete':bool(a.get('roles_incomplete') or a.get('history',{}).get('incomplete')),
            'evidence':str(path.relative_to(ROOT)) if path else None}


def token_export(address,t):
    media=[]
    for m in t.get('media',[]):
        target=m.get('target') or {}
        media.append({'field':m['field'],'location':m['cls'],'host':m.get('host'),'gateway':m.get('gateway'),
                      'uri':target.get('uri'),'external_refs':m.get('external_refs',[]),
                      'liveness':target.get('verdict') or ('onchain' if m['cls'] in c.ONCHAIN else 'unknown'),
                      'reason':target.get('reason'),'attempts':target.get('attempts',[])})
    uri=t.get('uri_raw')
    if t['meta_class'] in c.ONCHAIN and address!=PUNKS:
        uri='[inline payload; full bytes in saved RPC response]'
    derived=dict(t['derived'])
    # A successful empty ERC-721 response is not the fallback ERC-1155 revert.
    if address=='0x7c40c393dc0f283f318791d746d894ddd3693572':
        assert any(r.get('fn')=='tokenURI' and r.get('ok') and r.get('empty_or_bad') for r in t['rpc'])
        for key in ('meta_verdict_reason','liveness_reason','liveness_exact_reason','meta_verdict_exact_reason'):
            derived[key]='empty-tokenuri'
    return {'contract':address,'token_id':t['token_id'],'sample_unit':t.get('sample_unit',1),
            'how_found':t.get('how_found'),'metadata_location':t['meta_class'],
            'metadata_uri':uri,'metadata_attempts':(t.get('meta_target') or {}).get('attempts',[]),
            'media':media,'derived':derived,'special_case':t.get('special_case'),
            'adapter_evidence':t.get('adapter_evidence'),'rpc':t.get('rpc'),
            'evidence':f'data/raw/top100-census/{address}/evidence.jsonl.gz'}


def row_build(row,comparison):
    tokens=[];results=[];ctrl=[];empty=[]
    for address in row['contracts']:
        res=c.load_result(c.RAW/address)
        results.append(res)
        if not res.get('tokens'):empty.append(address)
        else:
            tokens.extend((address,t) for t in res['tokens'])
            ctrl.append(controls(address))
    assert len(tokens)>=3,(row['name'],len(tokens))
    if row['contract']==PUNKS:ctrl.append(controls(PUNK_DATA))
    aggregate=c.collection_row({'tokens':[t for a,t in tokens]})
    meta=[t['meta_class'] for a,t in tokens]
    fields=[m for a,t in tokens for m in t.get('media',[])]
    images=[t['derived'].get('image_class') for a,t in tokens]
    locations=[m['cls'] for m in fields]
    http=any(v=='http' for v in meta+locations)
    ipfs='ipfs' in meta+locations
    arweave='arweave' in meta+locations
    hosts=sorted({v for a,t in tokens for v in [t.get('meta_host')]+[m.get('host') for m in t.get('media',[])] if v})
    gateways=sorted({v for a,t in tokens for v in [t.get('meta_gateway')]+[m.get('gateway') for m in t.get('media',[])] if v})
    primary_onchain=all(t['meta_class'] in c.ONCHAIN and t['derived'].get('image_class') in c.ONCHAIN
                        and not t['derived']['external_refs'] for a,t in tokens)
    metadata_failed=any(t['derived']['meta_verdict']=='dead' for a,t in tokens)
    allmedia_bad=any((m.get('target') or {}).get('verdict')=='dead' for m in fields)
    allmedia_unknown=any((m.get('target') or {}).get('verdict')=='unknown' for m in fields)
    metadata_unknown=any(t['derived']['meta_verdict']=='unknown' for a,t in tokens)
    full_liveness=('dead' if all(t['derived']['meta_verdict']=='dead' for a,t in tokens)
                   else 'degraded' if metadata_failed or allmedia_bad
                   else 'unknown' if metadata_unknown or allmedia_unknown else 'alive')
    mutability=worst([v['class'] for v in ctrl])
    pointers=[f"{v['contract']}.{p['getter']} = {p['value']}" for v in ctrl for p in v['pointer_getters']
              if p.get('ok') and p.get('value') and re.search('base|renderer|descriptor|metadata',p['getter'],re.I)]
    fallback=[f'{PUNK_DATA}.punkImageSvg(uint16)' if a==PUNKS else f'{a}.tokenURI/uri' for a in row['contracts'] if a not in empty]
    adapters=[t.get('meta_target',{}).get('uri') for r in results if r.get('legacy_no_tokenURI') for t in r.get('tokens',[])]
    if adapters and not pointers:
        fallback=['external metadata adapter: '+u for u in adapters if u]
    result={**row,'all_time_volume':row['volume_usd'],'volume_currency':'USD','kind':KINDS.get(row['slug'],'art-avatar'),
            'metadata_location': 'legacy-no-tokenURI' if row['contract']==PUNKS else mixture(meta),
            'metadata_classes':sorted(set(meta)),'media_location':mixture(locations),
            'primary_image_location':mixture(images),'media_classes':sorted(set(locations)),
            'liveness':aggregate['liveness'],'liveness_exact':aggregate['liveness_exact'],
            'all_declared_media_liveness':full_liveness,'metadata_failed':metadata_failed,
            'n_alive':aggregate['n_alive'],'n_dead':aggregate['n_dead'],'n_unknown':aggregate['n_unknown'],
            'n_degraded':aggregate['n_degraded'],'key_domain_or_gateway':'; '.join(hosts+gateways),
            'hosts':hosts,'hardcoded_gateways':gateways,'http_origin_dependency':http,'uses_ipfs':ipfs,'uses_arweave':arweave,
            'fully_onchain_all_declared_media':aggregate['onchain_candidate_clean'],
            'metadata_and_primary_image_onchain':primary_onchain,'mutability_class':mutability,
            'single_key_mutable':mutability=='eoa-mutable',
            'single_key_repointable':any(v['pointer_power']=='eoa' for v in ctrl),
            'base_uri_or_renderer':'; '.join(pointers or fallback), 'control':ctrl,
            'samples':len(tokens),'distinct_token_ids':len({(a,t['token_id']) for a,t in tokens}),
            'sample_note':'; '.join(r['sampling_note'] for r in results if r.get('sampling_note')) or None,
            'source_contracts_without_sampleable_nfts':empty,
            'ownership_scope_gaps':[{'contract':r['address'],'note':r['ownership_scope_gap']} for r in results if r.get('ownership_scope_gap')],
            'refreshed_at':max(r['finished_at'] for r in results),'opensea_rank':comparison.get('opensea_rank'),
            'ranking_scope_disagreement':comparison.get('scope_disagreement',False),
            'metadata_adapter':any(r.get('legacy_no_tokenURI') and r.get('tokens') for r in results),
            'evidence':[f'data/raw/top100-census/{a}/result.json.gz' for a in row['contracts']]}
    result['delivery_note']={
        '0x7c40c393dc0f283f318791d746d894ddd3693572':
            'Wrapped MoonCatsRescue: owned IDs 4, 8 and 9 return empty tokenURI strings. Broken wrapper metadata, not a finding that the legacy MoonCats artwork is dead. The fallback uri call reverts; tokenURI itself succeeds.',
        '0x60bb1e2aa1c9acafb4d34f71585d7e959f387769':
            'Degraded, not dead: metadata and images for owned IDs 1 and 5000 load; owned ID 10000 returns HTTP 404 in both passes.'
    }.get(row['contract'])
    return result,[token_export(a,t) for a,t in tokens]


def evidence_index(rows):
    files=set()
    # The manifest includes all API attempts, including unsuccessful discovery.
    records=[]
    with (ROOT/'data/raw/MANIFEST.jsonl').open() as f:
        for line in f:
            try:r=json.loads(line)
            except ValueError:continue
            if str(r.get('path','')).startswith('data/raw/top100'):
                records.append(r)
    for row in rows:
        for address in row['contracts']:
            files.update(p for p in (c.RAW/address).iterdir() if p.is_file())
            p=ROOT/f'data/raw/top100-pointers/{address}'
            if p.exists():files.update(x for x in p.iterdir() if x.is_file())
        for control in row['control']:
            if control['evidence']:files.add(ROOT/control['evidence'])
            pointer_dir=ROOT/f"data/raw/top100-pointers/{control['contract']}"
            if pointer_dir.exists():files.update(p for p in pointer_dir.iterdir() if p.is_file())
        for address in row['contracts']:
            validity=ROOT/f'data/raw/top100-sample-validity/{address}'
            if validity.exists():files.update(p for p in validity.iterdir() if p.is_file())
    files.update(p for p in (c.RAW/'_gateways').iterdir() if p.is_file())
    records += [{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
                for p in sorted(files)]
    exported(OUT/'evidence_index.json',records)


def main():
    ranking=json.loads((OUT/'ranking.json').read_text())
    cross=json.loads((OUT/'ranking_crosscheck.json').read_text());assert len(cross)==100
    rows=[];tokens=[]
    for r,x in zip(ranking,cross):
        assert r['contract']==x['contract']
        row,samples=row_build(r,x);rows.append(row);tokens.extend(samples)
    counts={'collections':len(rows),'sampled_units':len(tokens),
            'fully_onchain_all_declared_media':sum(r['fully_onchain_all_declared_media'] for r in rows),
            'metadata_and_primary_image_onchain':sum(r['metadata_and_primary_image_onchain'] for r in rows),
            'http_origin_dependency':sum(r['http_origin_dependency'] for r in rows),
            'uses_ipfs':sum(r['uses_ipfs'] for r in rows),'uses_arweave':sum(r['uses_arweave'] for r in rows),
            'dead_or_degraded':sum(r['liveness'] in ('dead','degraded') for r in rows),
            'metadata_failed':sum(r['metadata_failed'] for r in rows),
            'unknown_liveness':sum(r['liveness']=='unknown' for r in rows),
            'single_key_mutable':sum(r['single_key_mutable'] for r in rows),
            'single_key_repointable':sum(r['single_key_repointable'] for r in rows),
            'hardcoded_gateway':sum(bool(r['hardcoded_gateways']) for r in rows),
            'secondary_top100_contract_overlap':sum(x['opensea_in_top100'] for x in cross),
            'scope_disagreements':sum(x.get('scope_disagreement',False) for x in cross),
            'secondary_identity_gaps':sum(not x['contracts'] for x in json.loads((OUT/'secondary_ranking.json').read_text())),
            'secondary_stats_available':sum(bool(x['opensea_total']) for x in cross),
            'three_distinct_id_exceptions':sum(r['distinct_token_ids']<3 for r in rows)}
    counts['liveness']=dict(collections.Counter(r['liveness'] for r in rows))
    counts['all_declared_media_liveness']=dict(collections.Counter(r['all_declared_media_liveness'] for r in rows))
    counts['mutability']=dict(collections.Counter(r['mutability_class'] for r in rows))
    headlines=[
        f"{counts['fully_onchain_all_declared_media']} of the top 100 route metadata and every sampled declared media field fully on-chain (including the CryptoPunks data-contract special case).",
        f"{counts['metadata_and_primary_image_onchain']} have on-chain metadata and primary images; additional animation fields can still be off-chain.",
        f"{counts['http_origin_dependency']} depend on operator-controlled HTTP servers for sampled metadata or media.",
        f"{counts['uses_ipfs']} use IPFS for sampled metadata or media; categories overlap.",
        f"{counts['dead_or_degraded']} have dead or degraded metadata/image delivery; {counts['metadata_failed']} have at least one failed metadata sample.",
        f"{counts['unknown_liveness']} remain unknown, not dead.",
        f"{counts['single_key_mutable']} have a live EOA-controlled URI, renderer, upgrade or artwork-data mutation path in the mutability audit; {counts['single_key_repointable']} can repoint delivery."
    ]
    summary={'schema_version':1,'as_of_utc':c.now_iso(),'ranking_definition':'CryptoSlam Ethereum all-time wash-filtered owner-to-owner sales in historical USD; duplicate contract aliases removed, higher total retained',
             'counts':counts,'headlines':headlines,'onchain_names':[r['name'] for r in rows if r['fully_onchain_all_declared_media']],
             'definitions':{'fully_onchain':'census clean static metadata + ALL declared media test; CryptoPunks uses its separately sealed data renderer. This is a delivery-route test, not an inventory of every recovery contract.',
                            'liveness':'census collection collapse of metadata and primary-image verdicts; all-declared-media status is separate.',
                            'metadata_failed':'At least one sampled metadata target has repeated negative evidence, including reverting tokenURI; unknown excluded.',
                            'http_origin_dependency':'Any ordinary HTTP metadata/media target; content-addressed IPFS/Arweave gateways excluded. This does not establish legal company ownership.',
                            'single_key_mutable':'mutability eoa-mutable class for sampled NFT contracts and in-path dependencies. Does not include arbitrary web-server operators.',
                            'mutability_dates':'Reused mutability results retain their analyzed_at; new audits use the same mutability analyzer. Pointer getter values refreshed separately.'},
             'caveats':['Source-specific top 100, not an exhaustive global market census; rankings differ by USD/ETH, filters, coverage and project aggregation.',
                        'Small token samples do not prove collection-wide health, permanence or offline rendering.',
                        'Only two distinct IDs are indexed for 888 Inner Circle; three fungible units were checked.',
                        'Source-listed companion contracts with no sampleable NFT IDs are preserved as scope gaps.',
                        'Some Art Blocks and SuperRare source totals aggregate projects; a contract is not always one marketplace collection.',
                        'Alternate on-chain recovery contracts can exist even when the ordinary image URI is IPFS/HTTP (e.g. CyberBrokers).'],
             'sources':['https://www.cryptoslam.io/collections',WEB_SOURCE],
             'evidence_index':'data/top100/evidence_index.json'}
    exported(OUT/'summary.json',summary)
    exported(OUT/'collections.json',rows)
    exported(OUT/'tokens.json',tokens)
    evidence_index(rows)
    public=clean(rows)
    columns=['rank','source_rank','name','contract','contracts','all_time_volume','volume_currency','volume_source','source_url','kind',
             'metadata_location','media_location','primary_image_location','liveness','liveness_exact','all_declared_media_liveness',
             'key_domain_or_gateway','hardcoded_gateways','mutability_class','single_key_mutable','single_key_repointable',
             'base_uri_or_renderer','samples','distinct_token_ids','sample_note','metadata_adapter','refreshed_at','evidence',
             'fully_onchain_all_declared_media','http_origin_dependency','delivery_note']
    with (OUT/'top100.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,lineterminator='\n');w.writeheader()
        for r in public:w.writerow({k:json.dumps(r[k],ensure_ascii=False) if isinstance(r[k],(dict,list)) else r.get(k) for k in columns})
    exported(ROOT/'site/data/top100.json',{'schema_version':1,'generated_at':summary['as_of_utc'],'summary':summary,'collections':rows})
    # Public, same-origin receipts: raw packets stay private; their hashes and
    # redacted sample outcomes remain inspectable without a repository checkout.
    index=json.loads((OUT/'evidence_index.json').read_text())
    for row in rows:
        addresses=set(row['contracts'])|{v['contract'] for v in row['control']}
        receipts=[v for v in index if any(a in v.get('path','').lower() for a in addresses)]
        exported(ROOT/f"site/data/top100-evidence/{row['contract']}.json",{
            'collection':row,'samples':[t for t in tokens if t['contract'] in row['contracts']],
            'saved_packet_index':receipts,
            'interpretation':'Liveness describes sampled metadata and primary-image delivery, not permanent loss of the artwork.'})
    print(json.dumps(counts,indent=2))


WEB_SOURCE='https://opensea.io/collections/top?chains=ethereum&sortBy=volume&timeframe=all_time'
if __name__=='__main__':main()
