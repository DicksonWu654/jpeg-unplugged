# Changelog

## 2026-10-21: first public release

- Census universe: every Ethereum mainnet ERC-721 and ERC-1155 contract with at least 100 holders, with deploy date,
  creator, factory and spam flags (`data/universe/`).
- Census: sampled tokens per collection, where `tokenURI` / `uri` points, where the image points, and whether each target
  loads today (`data/census/`).
- Marketing claims: collections that say they are "fully on-chain", with the quoted text and its source (`data/claims/`).
- Mutability: setter surface, current holders, external dependencies and setter history for the claimed on-chain
  collections (`data/mutability/`).
- Gallery: on-chain artworks rendered normally, with the network blocked, and with the network blocked plus a local archive
  of declared dependencies (`data/gallery/`, `data/dep-archive/`).
- Site with the "unplug the internet" toggle (`site/`), article (`article/`), launch cards (`launch/`), prior-art review
  (`research/`), and the scripts that rebuild each table (`scripts/`).
- Methodology consolidated in `METHODS.md`. Raw evidence (RPC responses, fetched metadata, request logs) is not
  included because of size; see README.
