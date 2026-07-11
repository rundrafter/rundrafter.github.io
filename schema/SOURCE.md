# Contract source

Vendored from the upstream `rundrafter` repo's intake contract:

- `intake-schema.json`
- `intake-example.json`

Pinned upstream revision:

revision: dcca9df815e22adcdd06e67706892e5f56ba6566

Re-sync with `just sync-contract` (`uv run python scripts/sync_contract.py`).

## Cross-field rule parity

The cross-field rules in `assets/assemble.js` mirror upstream
`src/rundrafter/validate.py` (constraints documented in
`docs/spec/contracts.md`). These aren't vendored - only their upstream
revision is pinned, checked by `just check-contract` against the sibling
checkout.

rules_revision: 41915651da2199aa4544f18d5ee5e137f49d937d

After syncing assemble.js (and docs/architecture.md) to a rule change
upstream, run `uv run python scripts/sync_contract.py --update-rules-revision`
(sibling checkout required) to record the new pin.
