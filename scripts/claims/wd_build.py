"""Build data/claims/web_directories.csv. Every claim_text is verified as a verbatim substring of the saved raw file."""
import sys, re, json, glob, csv, collections
sys.path.insert(0, 'scripts/claims'); import wd_common as C
rows = []; skipped = []
def add(address, collection, claim, strength, stype, key, url=None):
    p, rec = C.raw_for(key)
    if not rec: skipped.append((collection, 'no manifest', key)); return
    raw = open(C.ROOT/p, errors='replace').read()
    if claim not in raw: skipped.append((collection, 'quote not verbatim', key)); return
    a = (address or '').strip().lower()
    if a and not re.fullmatch(r'0x[0-9a-f]{40}', a): a = ''
    if a and a not in raw.lower(): skipped.append((collection, 'address not in raw', key)); a = ''
    rows.append(dict(address=a, collection=collection, claim_text=claim, claim_strength=strength, source_type=stype,
                     source_url=url or rec['url'], raw_path=p, retrieved_at=rec['retrieved_at']))

# 1+2. fullyonchain.art project pages (directory) and each project's own website
focs = []
for f in sorted(glob.glob('data/raw/claims-web/wd_foc_*.html')):
    key = f.split('/')[-1][:-5]
    if key.startswith(('wd_foc_list', 'wd_foc_scan', 'wd_foc_res', 'wd_foc_why')): continue
    raw = open(f, errors='replace').read()
    pr = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', raw, re.S).group(1))['props']['pageProps']['project']
    if pr.get('chain') != 'Ethereum': continue
    focs.append((key, pr, raw))
for key, pr, raw in focs:
    name = pr['projectName']; addr = pr.get('contractId')
    s, st = C.best_sentence([pr.get('description'), pr.get('body')], raw, name)
    if s: add(addr, name, s, st, 'directory', key)
    else:
        t = f'{name} | Fully On Chain'
        add(addr, name, t, 'implied', 'directory', key)
    skey = 'wd_site_' + key[len('wd_foc_'):]
    p, rec = C.raw_for(skey)
    if not rec: continue
    sraw = open(C.ROOT/p, errors='replace').read()
    cands = [x for x in C.html_candidates(sraw) if C.clean_ok(x)]
    s, st = C.best_sentence(cands, sraw, name, ok=lambda x: C.clean_ok(x) and len(x) >= 20 and re.sub(r'[^a-z0-9]','',x.lower()) != re.sub(r'[^a-z0-9]','',name.lower()))
    if s: add(addr if addr and addr.lower() in sraw.lower() else '', name, s, st, 'website', skey)

# 3. awesome-nft-onchain list (README on GitHub) -- addresses stated by the list
key = 'awesome_nft_onchain'; raw = open(f'data/raw/claims-web/{key}.html').read()
sect = raw.split('## On-Chain NFT Projects')[1].split('## Tutorials')[0]
for m in re.finditer(r'^\* (.+?) \( \[OpenSea\].*?etherscan\.io/address/(0x[0-9a-fA-F]{40})', sect, re.M | re.I):
    add(m.group(2), m.group(1).strip(), 'Awesome On-Chain NFT Projects, Boilerplates & Tutorials.', 'implied', 'directory', key,
        url='https://raw.githubusercontent.com/sesto-dev/awesome-nft-onchain/main/README.md')

# 4. manual rows (marketplace pages / articles) -- quotes verified above by add()
M = [
 ('TERMINALS', 'TERMINALS is a collection of 10,000 fully on-chain creatures on Ethereum.', 'explicit-100%/fully', 'marketplace', 'opensea_terminals'),
 ('TERMINALS', 'Your address deterministically seeds a one-of-a-kind animated SVG — what you see is what lives on-chain, forever.', 'storage-forever', 'marketplace', 'opensea_terminals'),
 ('FRONTRUN', 'FRONTRUN is a fully on-chain generative art collection of 420 pieces.', 'explicit-100%/fully', 'marketplace', 'opensea_frontrun'),
 ('FRONTRUN', 'FRONTRUN keeps all of it on Ethereum.', 'explicit-100%/fully', 'marketplace', 'opensea_frontrun'),
 ('Decentralists', 'Each NFT is stored 100% on the Ethereum blockchain and grants you access to the decentralist community.', 'explicit-100%/fully', 'marketplace', 'wd_opensea_decentralists'),
 ('BitmapPunks', 'A fully-onchain, ultra-large, hybrid collection.', 'explicit-100%/fully', 'marketplace', 'wd_opensea_bitmappunks'),
 ('Rooted in Code', 'A selection of 60 generative pieces, composed of layered, AI-generated face fragments with randomised dither and color, custom-animated with CSS and JS, and stored fully on-chain on Ethereum.', 'explicit-100%/fully', 'marketplace', 'wd_opensea_rootedincode'),
 ('Starry Night', 'collection of fully-on-chain, unique, randomly generated NFTs.', 'explicit-100%/fully', 'marketplace', 'wd_opensea_starrynight'),
 ('Starry Night', 'the entire metadata and image rendering code is stored on the Ethereum Blockchain.', 'explicit-100%/fully', 'marketplace', 'wd_opensea_starrynight'),
 ('CyberBrokers', 'Josie Bellini’s latest NFT project, CyberBrokers has been the talk of the town in the NFT space, and now the collection has moved entirely on-chain.', 'explicit-100%/fully', 'directory', 'dappradar_cyberbrokers'),
 ('Chain Runners', 'And importantly, it was fully onchain.', 'explicit-100%/fully', 'website', 'wd_opensea_blog_300_onchain'),
 ('Avastars', 'The base image of every Avastar trait combination lives within the Avastars smart contract, from which trait combos are rendered on-demand anytime someone scrolls for, finds, and then mints an Avastar from their browser.', 'on-chain-generic', 'directory', 'tokensmart_10'),
]
for name, claim, st, stype, key in M: add('', name, claim, st, stype, key)

# dedupe exact (collection, source_url, claim)
seen = set(); out = []
for r in rows:
    k = (r['collection'].lower(), r['source_url'], r['claim_text'])
    if k in seen: continue
    seen.add(k); out.append(r)
import os; os.makedirs('data/claims', exist_ok=True)
cols = ['address','collection','claim_text','claim_strength','source_type','source_url','raw_path','retrieved_at']
with open('data/claims/web_directories.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(out)
print('rows', len(out), 'skipped', len(skipped))
print('by strength', collections.Counter(r['claim_strength'] for r in out))
print('by type', collections.Counter(r['source_type'] for r in out))
print('distinct addresses', len({r['address'] for r in out if r['address']}), 'distinct collections', len({r['collection'].lower() for r in out}))
for s in skipped[:15]: print('SKIP', s)
