"""Acquire CryptoSlam's first 200 Ethereum all-time rows and contract identities."""
import json
import re
from common import ROOT, OUT, get, write

BASE = 'https://web-api.cryptoslam.io/v1'
RANK_URL = BASE + '/sales/rank-by-volume?timeRange=all&orderBy=rank&sortDirection=asc&offset={offset}&limit=100&blockchainId=0&hideInscriptions=false'


def main():
    rows = []
    for offset in (0, 100):
        response = get(RANK_URL.format(offset=offset), f'cryptoslam-ranking-{offset}')
        page = response['data']
        assert page['timePeriod'] == 'all'
        assert len(page['saleSummaries']) == 100
        for row in page['saleSummaries']:
            assert row['platformName'] == 'Ethereum'
            slug = row['productPath']
            info = get(BASE + '/collections/' + slug, 'cryptoslam-info-' + slug)
            identity = (info or {}).get('data') or {}
            row = {**row, 'identity': identity, 'source_url': RANK_URL.format(offset=offset),
                   'ranking_evidence': f'data/raw/top100-api/cryptoslam-ranking-{offset}.json',
                   'identity_evidence': f'data/raw/top100-api/cryptoslam-info-{slug}.json'}
            rows.append(row)
            if len(rows) % 10 == 0:
                print('identities', len(rows), flush=True)
    # Same contract under two source labels is one collection. Retain the larger
    # reported total, never sum potentially overlapping source histories.
    seen, selected, exclusions = {}, [], []
    for row in rows:
        addresses = str(row['identity'].get('contractAddress') or '').lower().split('|')
        if not all(re.fullmatch('0x[0-9a-f]{40}', a) for a in addresses):
            exclusions.append({'source_rank': row['rank'], 'name': row['contractName'],
                               'reason': 'no single Ethereum contract in source identity', 'identity_evidence': row['identity_evidence']})
            continue
        # A source collection may span migrations or multiple NFT contracts.
        # Keep that collection and preserve the full set; canonical addresses
        # identify the widely recognized collection, not an extra volume row.
        prefer = {'loot': '0xff9c1b15b16263c61d017ee9f65c50e4ae0113d7',
                  'superrare': '0xb932a70a57673d89f4acffbe830e8ed7f75fb9e0'}
        address = prefer.get(row['productPath'], addresses[0])
        if address in seen:
            exclusions.append({'source_rank': row['rank'], 'name': row['contractName'], 'contract': address,
                               'reason': 'duplicate contract; retained higher-volume source row',
                               'retained_source_rank': seen[address], 'identity_evidence': row['identity_evidence']})
            continue
        seen[address] = row['rank']
        if len(selected) < 100:
            selected.append({'rank': len(selected)+1, 'source_rank': row['rank'], 'name': row['contractName'].strip(),
                             'contract': address, 'contracts': addresses, 'slug': row['productPath'], 'volume_usd': row['valueUSD'],
                             'volume_source': 'CryptoSlam all-time Ethereum owner-to-owner sales, wash-filtered USD',
                             'source_url': row['source_url'], 'ranking_evidence': row['ranking_evidence'],
                             'identity_evidence': row['identity_evidence'], 'token_count': row['identity'].get('tokenCount')})
    assert len(selected) == 100
    write(OUT / 'ranking.json', selected)
    write(OUT / 'ranking_exclusions.json', exclusions)
    print('selected',len(selected),'exclusions',len(exclusions),flush=True)


if __name__ == '__main__':
    main()
