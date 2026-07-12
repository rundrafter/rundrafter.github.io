# Contract source

Vendored from the upstream `rundrafter` repo's intake contract:

- `intake-schema.json`
- `intake-example.json`

Pinned upstream revision:

revision: 9b691fc8fb073a7970a32f9a3cab7ace3eda920c

Re-sync with `just sync-contract` (`uv run python scripts/sync_contract.py`).

## Cross-field rule parity

The cross-field rules in `assets/assemble.js` mirror upstream
`src/rundrafter/validate.py` (constraints documented in
`docs/spec/contracts.md`). These aren't vendored - only their upstream
revision is pinned, checked by `just check-contract` against the sibling
checkout.

rules_revision: 9e81780dd0aac1ea49b620f80fceaf7bce15246e

After syncing assemble.js (and docs/architecture.md) to a rule change
upstream, run `uv run python scripts/sync_contract.py --update-rules-revision`
(sibling checkout required) to record the new pin.
