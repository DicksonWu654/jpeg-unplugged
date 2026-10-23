"""Build data/claims/web_famous.csv from the spec below. For every row: (1) the quote must be a verbatim substring of the saved raw file
(HTML tags stripped / entities unescaped / whitespace collapsed; JSON files: decoded description), (2) the address must have been verified
by verify_all.py (Blockscout name match). Anything failing is printed and dropped. Run: .venv/bin/python -I scripts/claims/build_web_famous.py"""
import sys, re, json, csv, html, pathlib, collections
sys.path.insert(0, 'scripts/claims')
from web_famous_spec import PROJECTS

ROOT = pathlib.Path('.').resolve()
RAWDIR = ROOT / 'data/raw/claims-web'
CHECKS = json.load(open('scripts/claims/addr_checks.json'))

EX = 'explicit-100%/fully'; GEN = 'on-chain-generic'; FOREVER = 'storage-forever'; IMP = 'implied'; NONE = 'none-found'
MP = 'marketplace'; WEB = 'website'; DIR = 'directory'

# (project, slug, ext, quote, strength, source_type, extra_note)
ROWS = [
 ('loot', 'osapi_lootproject', 'json', 'Loot is randomized adventurer gear generated and stored on chain.', GEN, MP, ''),
 ('loot', 'loot_site', 'html', 'Loot is randomized adventurer gear generated and stored on chain.', GEN, WEB, ''),
 ('mloot', 'os_mloot', 'html', 'More Loot is additional randomized adventurer gear generated and stored on chain.', GEN, MP, 'OpenSea collection page (slug more-loot); contract address appears in the saved page'),
 ('bloot', 'osapi_blootofficial', 'json', '', NONE, MP, 'OpenSea description has no storage claim'),
 ('sloot', 'loot_site', 'html', '', NONE, WEB, 'contract 0x869A... is linked from the Synthetic Loot "View Contract" button on lootproject.com (href in saved HTML) (Blockscout lists it as a contract, not a token); site text: "Loot bags for everyone, free and tied to your Ethereum address."; no storage claim specific to it'),
 ('chainrunners', 'osapi_chain-runners-nft', 'json', 'Chain Runners are Mega City renegades 100% stored and generated on chain.', EX, MP, ''),
 ('chainrunners', 'wf_chainrunners_osblog', 'html', 'And importantly, it was fully onchain. All of the digital items and metadata were stored directly in the Ethereum contract', EX, WEB, 'OpenSea Blog article by a third-party builder (OnChainKevin creator), not by the Chain Runners team'),
 ('chainrunners', 'wf_chainrunners_iq', 'html', 'With being totally on-chain and decentralized', EX, DIR, 'IQ.wiki (community wiki) description'),
 ('nouns', 'wf_nouns_contracts_gh', 'html', 'All Noun artwork is stored and rendered on-chain.', GEN, WEB, 'nouns-monorepo packages/nouns-contracts README (raw GitHub)'),
 ('lilnouns', 'osapi_lil-nouns', 'json', '', NONE, MP, 'OpenSea description has no storage claim; lilnouns.wtf is JS-only (2.6 KB shell) and the GitHub README URLs tried returned 404'),
 ('blitmap', 'osapi_blitmap', 'json', 'All data is completely on chain.', EX, MP, ''),
 ('blitmap', 'wf_blitmap_iq', 'html', 'Since the Blitmap NFTs reside on-chain, their perpetuity is guaranteed till the Ethereum blockchain exists.', FOREVER, DIR, 'IQ.wiki (community wiki) description'),
 ('ocm', 'osapi_onchainmonkey', 'json', 'OCM Genesis is art on blockchain.', IMP, MP, 'current OpenSea description says the Ethereum NFT can be burned (teleburn) to claim a Bitcoin Ordinal: "7,836 have been claimed on Bitcoin via a teleburn"'),
 ('ocm', 'os_onchainmonkey', 'html', 'fully stored on-chain in a single Ethereum transaction', EX, MP, 'text is in the "about" section of the OpenSea collection page; authorship (creator vs OpenSea-generated) not determinable from the saved page'),
 ('anonymice', 'osapi_anonymice', 'json', 'Anonymice were randomly generated and stored 100% on-chain using solidity code only and are contract renounced.', EX, MP, 'same description says 10,000 minted, 6,450 burned, 3550 remain'),
 ('anonymice', 'osapi_anonymice', 'json', 'they will live on the Ethereum blockchain for as long as it exists', FOREVER, MP, ''),
 ('anonymice', 'wf_anonymice_iq', 'html', 'is a 100% on-chain, generative, PFP Non-Fungible Token (NFT)', EX, DIR, 'IQ.wiki (community wiki) description'),
 ('anonbabies', 'wf_os_anonymicebabies', 'html', 'The first 100% on-chain breeding NFT!', EX, MP, 'OpenSea collection page'),
 ('terraforms', 'osapi_terraforms', 'json', 'Onchain land art from a dynamically generated onchain 3D world.', GEN, MP, ''),
 ('terraforms', 'wf_terraforms_iq', 'html', 'collection consists of 11,000 NFTs that are fully on-chain', EX, DIR, 'IQ.wiki (community wiki); its supply figure (11,000) differs from Blockscout total_supply 9911 for the contract'),
 ('punks', 'wf_cp_blog_onchain', 'html', 'the Cryptopunks are now fully on-chain!', EX, WEB, 'Larva Labs post 2021-08-18; the 2017 contract held only a hash of the composite image (wf_cp_index.html: "we took a hash of the composite image of all the punks and embeded it into the contract"), images/attributes went on-chain four years later in a separate contract (next row)'),
 ('punks', 'wf_cp_index', 'html', 'we have managed to put the entire image and attribute data fully on chain', EX, WEB, 'archived Larva Labs CryptoPunks page (states official site is cryptopunks.app)'),
 ('punks', 'wf_cp_index', 'html', 'allows for arbitrary computer code to be executed on the blockchain and the results of the execution to be stored forever', FOREVER, WEB, 'generic statement about Ethereum in the 2017-era Larva Labs FAQ, not specifically about image storage'),
 ('punks', 'os_cryptopunks', 'html', '10,000 unique collectible characters with proof of ownership stored on the Ethereum blockchain.', IMP, MP, 'OpenSea collection page; "proof of ownership" stored, not images'),
 ('punksdata', 'wf_cp_blog_onchain', 'html', 'You can visit this contract on Etherscan and query directly for the Cryptopunk images as either a raw set of pixels or an SVG.', GEN, WEB, 'address taken from the Etherscan link in the saved Larva Labs post; contract is a separate data contract, not the NFT contract'),
 ('moonbirds', 'moonbirds_site', 'html', 'The pixelated art is fully on-chain (aka “in-chain”)—meaning that the images are rendered directly from the Ethereum smart contracts.', EX, WEB, 'claim is scoped to the pixelated art; same page offers a separate illustrated style; not tested whether the pixelated in-chain renderer is reachable independent of the pointer shown'),
 ('moonbirds', 'wf_moonbirds_young', 'html', 'making all its non-fungible tokens ‘in-chain’', GEN, WEB, 'Young Platform article 2022-09-12 reporting PROOF roadmap; it states Moonbirds were released in April 2022 and lists in-chain as a "planned feature"'),
 ('oddities', 'osapi_moonbirds-oddities', 'json', '', NONE, MP, 'OpenSea description has no storage claim'),
 ('autoglyphs', 'autoglyphs_site', 'html', 'Autoglyphs are the first art project that was both generated and stored entirely on-chain.', EX, WEB, 'Larva Labs'),
 ('autoglyphs', 'osapi_autoglyphs', 'json', 'Autoglyphs are the first “on-chain” generative art on the Ethereum blockchain.', GEN, MP, ''),
 ('ab_core', 'artblocks_docs', 'html', 'Artists write algorithms stored permanently on the Ethereum blockchain.', FOREVER, WEB, 'Art Blocks docs home (platform-level statement)'),
 ('ab_core', 'wf_ab_onchain_storage', 'html', 'Art Blocks tokens store their metadata fully on-chain, ensuring collectors that their NFTs will always remain accessible and immutable.', EX, WEB, 'same docs page says Engine Flex contracts also support "IPFS/Arweave decentralized storage" dependencies'),
 ('ab_curated', 'wf_ab_protocol_overview', 'html', 'Every generative art project on Art Blocks stores its creative code permanently on a blockchain, and every token produced by that code lives there too', FOREVER, WEB, 'Art Blocks docs protocol overview (platform-level)'),
 ('ab_curated', 'wf_ab_onchain_storage', 'html', 'Art Blocks tokens store their metadata fully on-chain, ensuring collectors that their NFTs will always remain accessible and immutable.', EX, WEB, 'same docs page says Engine Flex contracts also support "IPFS/Arweave decentralized storage" dependencies'),
 ('squiggle', 'artblocks_docs', 'html', 'with tokens living permanently on Ethereum, Arbitrum, and Base.', FOREVER, WEB, 'Art Blocks docs home; sentence names Chromie Squiggle as the first project (Nov 2020)'),
 ('ringers', 'osapi_ringers-by-dmitri-cherniak', 'json', "Each output from 'Ringers' is derived from a unique transaction hash and generated in Javascript in the browser.", IMP, MP, 'artist project description: output is generated in the browser from an on-chain hash'),
 ('fidenza', 'osapi_fidenza-by-tyler-hobbs', 'json', '', NONE, MP, 'OpenSea description is the artist statement; no storage claim'),
 ('toadz', 'osapi_cryptoadz-by-gremplin', 'json', '', NONE, MP, 'OpenSea description has no storage claim; cryptoadz.io is JS-only (3 KB shell)'),
 ('mooncats_acc', 'osapi_acclimatedmooncats', 'json', 'The 25440 MoonCats rescued are acclimating to their life as [fully on-chain](https://mooncatrescue.com/about) collectible critters.', EX, MP, 'Acclimated MoonCats is the ERC-721 wrapper collection; the original 2017 contract is a separate row'),
 ('mooncats_acc', 'mooncats_site', 'html', 'helped pioneer on-chain generation', GEN, WEB, 'mooncat.community'),
 ('mooncats_orig', 'wf_mooncat_about', 'html', 'The project was a pioneer of on-chain generation', GEN, WEB, 'mooncatrescue.com/about'),
 ('checks_vv', 'checks_site', 'html', 'A MECHANISM FOR MIGRATING OPEN EDITIONS TO IMMUTABLE ONCHAIN ARTWORK WAS DEPLOYED ON ETHEREUM.', GEN, WEB, 'same page: "Checks Editions are artist controlled, mutable canvases." and Editions are not the immutable onchain Originals'),
 ('checks_orig', 'checks_site', 'html', 'Checks originals are onchain, animated SVGs with no external render dependencies.', EX, WEB, ''),
 ('checks_elem', 'osapi_vv-checks-elements', 'json', '', NONE, MP, 'OpenSea description has no storage claim'),
 ('orcs', 'osapi_ether-orcs', 'json', 'With no IPFS or API, these Orcs are the very first game that takes place 100% on-chain.', EX, MP, 'OpenSea slug ether-orcs resolves to the Genesis Orcs contract'),
 ('orcs', 'os_etherorcs', 'html', 'This Horde of Orcs will stand the test of time and live on the blockchain for eternity.', FOREVER, MP, 'sentence is in the description embedded in the saved OpenSea collection page (no longer in the current API description)'),
 ('sproto', 'osapi_sproto-gremlins', 'json', '', NONE, MP, 'no storage claim in OpenSea description or sprotogremlins.com text'),
 ('tinydinos', 'osapi_tiny-dinos-eth', 'json', '', NONE, MP, 'OpenSea description says "omnichain nft powered by layerzero" (cross-chain, not on-chain storage)'),
 ('wizards', 'osapi_forgottenruneswizardscult', 'json', '10,000 unique Wizard NFTs, fully encoded on-chain.', EX, MP, ''),
 ('oxmons', 'osapi_0xmons-xyz', 'json', 'on-chain neural net generated pixel monsters', GEN, MP, 'OpenSea description links to the 0xmons on-chain encoding write-up'),
 ('rect', 'osapi_rect-8-bit', 'json', 'rect() is fully on-chain.', EX, MP, ''),
 ('rect', 'osapi_rect-8-bit', 'json', 'the artwork and all the important metadata info can be reproduced directly from the Ethereum blockchain forever!', FOREVER, MP, ''),
 ('meebits', 'osapi_meebits', 'json', 'The Meebits are 20,000 unique 3D voxel characters, created by a custom generative algorithm, then registered on the Ethereum blockchain.', IMP, MP, ''),
 ('hashmasks', 'osapi_hashmasks', 'json', '', NONE, MP, 'negative control: no storage claim in OpenSea description; thehashmasks.com is a JS shell'),
 ('mfers', 'osapi_mfers', 'json', '', NONE, MP, 'negative control: CC0/public-domain statement only'),
 ('opepen', 'osapi_opepen-edition', 'json', '', NONE, MP, 'negative control: description is "Consensus is temporary."; opepen.art says "Public Art On Ethereum" (venue, not storage)'),
 ('pudgy', 'osapi_pudgypenguins', 'json', '', NONE, MP, 'negative control: no storage claim'),
 ('doodles', 'osapi_doodles-official', 'json', '', NONE, MP, 'negative control: no storage claim'),
 ('bayc', 'osapi_boredapeyachtclub', 'json', 'unique digital collectibles living on the Ethereum blockchain', IMP, MP, ''),
 ('bakc', 'osapi_bored-ape-kennel-club', 'json', '', NONE, MP, 'negative control: no storage claim'),
 ('mayc', 'osapi_mutant-ape-yacht-club', 'json', '', NONE, MP, 'negative control: no storage claim'),
 ('azuki', 'osapi_azuki', 'json', '', NONE, MP, 'negative control: no storage claim'),
 ('coolcats', 'osapi_cool-cats-nft', 'json', 'NFTs that exist on the Ethereum Blockchain', IMP, MP, ''),
 ('clonex', 'osapi_clonex', 'json', '', NONE, MP, 'negative control: no storage claim'),
 ('milady', 'osapi_milady', 'json', '', NONE, MP, 'negative control: no storage claim'),
 ('goblin', 'osapi_goblintownwtf', 'json', '', NONE, MP, 'negative control: no storage claim'),
 ('otherdeed', 'osapi_otherdeed', 'json', '', NONE, MP, 'negative control: no storage claim'),
 ('kitties', 'osapi_cryptokitties', 'json', 'Each cat is one-of-a-kind and 100% owned by you; it cannot be replicated, taken away, or destroyed.', IMP, MP, 'ownership claim, not a storage claim'),
 ('invisible', 'osapi_invisiblefriends', 'json', '', NONE, MP, 'negative control: no storage claim'),
 ('veefriends', 'osapi_veefriends', 'json', '', NONE, MP, 'negative control: no storage claim'),
 ('lazylions', 'osapi_lazy-lions', 'json', '', NONE, MP, 'negative control: no storage claim'),
 ('larvalads', 'osapi_larva-lads', 'json', '', NONE, MP, 'OpenSea description has no storage claim'),
 ('brotchain', 'osapi_brotchain', 'json', 'No externalities, no rendering dependencies—just 100% Solidity.', EX, MP, ''),
 ('brotchain', 'wf_brotchain_art', 'html', 'Brotchain is generative NFT art with bitmaps generated and rendered entirely by a blockchain contract.', EX, WEB, 'brotchain.art'),
 ('chainfaces', 'osapi_chainfaces', 'json', 'All attributes and metadata are on-chain and easily viewable via the etherscan UI.', GEN, MP, ''),
 ('cypherworms', 'osapi_cypherworms', 'json', '', NONE, MP, 'OpenSea description has no storage claim'),
 ('avastars', 'osapi_avastar', 'json', 'Each one is unique and has their art and metadata stored on-chain.', GEN, MP, ''),
 ('skulls', 'wf_cryptoskulls_com', 'html', 'Every CryptoSkull is fully embedded on-chain. No external storage. No broken links. No missing files.', EX, WEB, 'cryptoskulls.com'),
 ('skulls', 'osapi_cryptoskulls', 'json', '10,000 collectible ERC-721 Non-Fungible Tokens (NFTs) stored on the Ethereum Blockchain', GEN, MP, ''),
 ('pixelmap', 'osapi_pixelmap', 'json', 'PixelMap is the first NFT to store image data directly on the Ethereum blockchain.', GEN, MP, 'description says the original 2016 contract is 0x015A06a433353f8db634dF4eDdF0C109882A15AB and this address is the later ERC-721 wrapper'),
 ('pixelmap', 'osapi_pixelmap', 'json', 'nothing short of every single Ethereum node shutting down can eliminate the data', FOREVER, MP, ''),
 ('okpc', 'osapi_okpc', 'json', '𝙾𝙺𝙿𝙲 𝙸𝚂 𝙰𝙽 𝙾𝙽 𝙲𝙷𝙰𝙸𝙽 𝚃𝙾𝚈 𝚃𝙷𝙰𝚃 𝙻𝙴𝚃𝚂 𝚈𝙾𝚄 𝙲𝚁𝙴𝙰𝚃𝙴, 𝙲𝙾𝙻𝙻𝙴𝙲𝚃 𝙰𝙽𝙳 𝚂𝙷𝙰𝚁𝙴 𝙰𝚁𝚃𝚆𝙾𝚁𝙺', GEN, MP, ''),
 ('cyberbrokers', 'osapi_cyberbrokers', 'json', '10,001 unique and on-chain CyberBroker NFTs.', GEN, MP, ''),
 ('normies', 'osapi_normies', 'json', '10,000 fully on-chain, CC0, generative faces.', EX, MP, ''),
 ('cc0mon', 'osapi_cc0mon', 'json', 'A fully on-chain CC0 world living on Ethereum.', EX, MP, ''),
 ('bytegans', 'osapi_bytegans', 'json', '100% on-chain art by Pindar Van Arman', EX, MP, ''),
]

def norm(s):
    return re.sub(r'\s+', ' ', s).strip()

def candidates(path, ext):
    raw = path.read_text(errors='replace')
    out = []
    if ext == 'json':
        try:
            j = json.loads(raw)
            if isinstance(j, dict): out.append(norm(j.get('description') or ''))
        except Exception: pass
    out.append(norm(raw))
    out.append(norm(raw.replace('\\n', ' ').replace('\\"', '"').replace('\\u2019', '’')))
    t = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', raw)
    t = re.sub(r'<[^>]+>', ' ', t)
    out.append(norm(html.unescape(t)))
    return out

def manifest_lookup():
    d = {}
    for line in open('data/raw/MANIFEST.jsonl'):
        try: r = json.loads(line)
        except Exception: continue
        if r.get('path') and r.get('status') == 200: d[r['path']] = r
        elif r.get('path') and r['path'] not in d: d[r['path']] = r
    return d
MAN = manifest_lookup()

def evidence(key, strength):
    c = CHECKS.get(key) or {}
    t = c.get('token_uri') or {}
    parts = []
    off = False
    if t.get('uri_scheme'):
        sc = t['uri_scheme']
        if sc.startswith('data:application/json'):
            s = f"tokenURI({t['id']}): data-URI JSON"
            if t.get('image_scheme'):
                s += f", image {t['image_scheme']}"
            if t.get('animation_scheme'):
                s += f", animation_url {t['animation_scheme']}"
            if (t.get('image_scheme') or '').startswith(('ipfs', 'http', 'ar:')) or (t.get('animation_scheme') or '').startswith(('ipfs', 'http', 'ar:')): off = True
        elif sc.startswith('data:'):
            s = f"tokenURI({t['id']}): {sc}"
        else:
            s = f"tokenURI({t['id']}) = {t['uri_head']}"; off = True
        parts.append(s)
    elif t.get('error'):
        parts.append('tokenURI eth_call reverted for probed ids (inconclusive)')
    bi = c.get('blockscout_instance')
    if bi and not t.get('uri_scheme'):
        parts.append(f"Blockscout cached instance #{bi['id']} image_url = {bi['image_url_head']}" + (f", animation_url {bi['animation_scheme']}" if bi.get('animation_scheme') else ''))
        if not (bi['image_url_scheme'] or '').startswith('data:') and not (bi.get('animation_scheme') or '').startswith('data:'): off = True
    if bi and t.get('uri_scheme') and key == 'rect':
        parts.append(f"Blockscout cached instance #{bi['id']} image_url = {bi['image_url_head']}")
    ev = ' ; '.join(parts)
    return (ev + ' [data/raw/rpc-claims, claims-addr]') if ev else '', off

rows_out, problems, per_proj = [], [], collections.Counter()
for key, slug, ext, quote, strength, stype, extra in ROWS:
    name, addr, _, _ = PROJECTS[key]
    chk = CHECKS.get(key)
    if not chk or not chk['name_matches']:
        problems.append(f'ADDR-UNVERIFIED {key}'); continue
    path = RAWDIR / f'{slug}.{ext}'
    if not path.exists():
        problems.append(f'MISSING-RAW {key} {path}'); continue
    cands = candidates(path, ext)
    if quote:
        if not any(norm(quote) in c for c in cands):
            problems.append(f'QUOTE-NOT-FOUND {key} {slug}: {quote[:70]}'); continue
    else:
        # none-found rows: description must really contain no storage-claim words
        j = json.loads(path.read_text()) if ext == 'json' else None
        d = (j.get('description') or '') if isinstance(j, dict) else cands[-1]
        if ext == 'json' and re.search(r'on.?chain|stored|ipfs|arweave|permanent', d, re.I):
            problems.append(f'NONE-ROW-HAS-KEYWORDS {key}: {d[:80]}'); continue
    rel = str(path.relative_to(ROOT))
    m = MAN.get(rel)
    if not m:
        problems.append(f'NO-MANIFEST {rel}'); continue
    ev, off = evidence(key, strength)
    if ev and off and strength in (EX, GEN, FOREVER):
        ev = 'CHECK claim vs pointer: ' + ev
    note = ' ; '.join(x for x in [extra, ev] if x)
    rows_out.append({'address': addr.lower(), 'collection': name, 'claim_text': quote, 'claim_strength': strength, 'source_type': stype,
                     'source_url': m['url'], 'raw_path': rel, 'retrieved_at': m['retrieved_at'], 'note': note})
    per_proj[key] += 1

missing = [k for k in PROJECTS if per_proj[k] == 0]
with open('data/claims/web_famous.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['address', 'collection', 'claim_text', 'claim_strength', 'source_type', 'source_url', 'raw_path', 'retrieved_at', 'note'])
    w.writeheader(); w.writerows(rows_out)
print('rows', len(rows_out), 'projects', len(per_proj), 'problems', len(problems))
print('strength counts', collections.Counter(r['claim_strength'] for r in rows_out))
for p in problems: print(' !', p)
print('projects with no row:', missing)
