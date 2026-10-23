"""Independent OpenSea Ethereum all-time ranking, plus contract-bound comparisons."""
import json
import re
from common import ROOT, OUT, get, write, evidence
import rawfetch as rf

BASE='https://api.opensea.io/api/v2'
WEB='https://opensea.io/collections/top?chains=ethereum&sortBy=volume&timeframe=all_time&page='


def parse_page(text):
    variables=None
    data=None
    for script in re.findall(r'<script[^>]*>(.*?)</script>', text, re.S):
        if 'ApolloSSRDataTransport' not in script:
            continue
        literal=script.split('.push(',1)[1].rstrip(';')[:-1]
        # Parse serialized data only. Never evaluate source JavaScript.
        obj=json.loads(re.sub(r'(?<=:)undefined(?=[,}])','null',literal))
        for event in obj.get('events',[]):
            if event['type']=='started' and 'CollectionRankingsQuery' in event['options'].get('query',''):
                variables=event['options']['variables']
            if event['type']=='next' and 'collectionRankings' in event.get('value',{}).get('data',{}):
                data=event['value']['data']['collectionRankings']
    assert variables['timeframe']=='ALL_TIME'
    assert variables['filter']['chains']==['ethereum']
    assert variables['sort']=={'direction':'DESC','by':'VOLUME'}
    assert data and len(data['items'])==50
    return variables,data['items']


def main():
    secondary=[]
    for page in (1,2,3):
        url=WEB+str(page)
        response=rf.get_soft(url,source='top100-api',key=f'opensea-ranking-page-{page}',ext='html',retries=1,timeout=45)
        assert response['status']==200
        variables,items=parse_page(response['body'].decode())
        assert (variables.get('offset') or 0)==(page-1)*50
        for item in items:
            coll=item['collection'];slug=coll['slug']
            info=get(BASE+'/collections/'+slug,'opensea-info-'+slug)
            contracts=[v['address'].lower() for v in info.get('contracts',[]) if v.get('chain')=='ethereum']
            volume=coll['stats']['volume']
            secondary.append({'rank':len(secondary)+1,'name':coll['name'],'slug':slug,'contracts':contracts,
                              'volume_eth':volume['native']['unit'],'volume_usd':volume['usd'],
                              'ranking_evidence':f'data/raw/top100-api/opensea-ranking-page-{page}.html',
                              'identity_evidence':evidence('opensea-info-'+slug)})
            write(OUT/'secondary_ranking.json',secondary)
            if len(secondary)%10==0:print('secondary identities',len(secondary),flush=True)
    primary=json.loads((OUT/'ranking.json').read_text())
    comparisons=[]
    for row in primary:
        addresses=set(row['contracts'])
        matches=[r for r in secondary if addresses.intersection(r['contracts'])]
        match=min(matches,key=lambda r:r['rank']) if matches else None
        mapped=get(BASE+'/chain/ethereum/contract/'+row['contract'],'opensea-contract-'+row['contract'])
        slug=match['slug'] if match else mapped.get('collection')
        stats=get(BASE+'/collections/'+slug+'/stats','opensea-stats-'+slug) if slug else {}
        info=get(BASE+'/collections/'+slug,'opensea-info-'+slug) if slug else {}
        bound=bool(match) or any(v.get('chain')=='ethereum' and v['address'].lower() in addresses for v in info.get('contracts',[]))
        project_scope=len(matches)>1 or row['slug']=='art-blocks'
        comparisons.append({'rank':row['rank'],'name':row['name'],'contract':row['contract'],
                            'opensea_rank':match['rank'] if match else None,
                            'opensea_in_top100':bool(match and match['rank']<=100),
                            'opensea_slug':slug,'contract_bound':bound,'opensea_total':stats.get('total'),
                            'opensea_matches':[{'rank':r['rank'],'name':r['name'],'slug':r['slug']} for r in matches],
                            'scope_disagreement':project_scope,
                            'opensea_evidence':evidence('opensea-stats-'+slug) if slug else None,
                            'rank_delta':match['rank']-row['rank'] if match and not project_scope else None,
                            'resolution':'retain CryptoSlam wash-filtered USD order; OpenSea differs in coverage, aggregation and sales filters'})
        write(OUT/'ranking_crosscheck.json',comparisons)
        print('crosschecked',row['rank'],row['name'],match['rank'] if match else '>150 / source coverage',flush=True)


if __name__=='__main__':
    main()
