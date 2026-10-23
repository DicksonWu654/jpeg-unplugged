# Mutability

The analysis records URI and renderer setters, freeze or lock mechanisms, proxies, upgradeability, current ownership and
external dependencies. Verified source and recorded calls provide the evidence. Setter detection is a heuristic: inherited
functions, access controls, ownership changes and separate data contracts can change its interpretation.

The ability to alter a marketplace pointer is distinct from whether artwork bytes already exist on-chain. Public outputs
retain the pointer and data distinctions and withhold sensitive origins. See [Methods](../../METHODS.md),
`scripts/mutability/`, `data/mutability/mutability.csv` and its per-contract evidence files.
