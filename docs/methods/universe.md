# Census universe

The universe consists of Ethereum mainnet ERC-721 and ERC-1155 contracts with at least 100 holders, enumerated from
Blockscout. Keyset segments overlap and are deduplicated by contract address. Creation transactions and timestamps are
used to derive deployment year, which is a proxy for mint year. Deployment and minting may be years apart.

The tables retain spam-suspect and infrastructure flags. These are classification aids, not proof that a collection is
fraudulent. Collection-weighted and holder-weighted results answer different questions. ERC-1155 total supply is often
unknown. See [Methods](../../METHODS.md) and `data/universe/` for the definitions and saved universe.
