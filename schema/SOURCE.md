# Contract source

Vendored from the upstream `run-drafter` repo's intake contract:

- `intake-schema.json`
- `intake-example.json`

Pinned upstream revision:

revision: 4482c8097c17c8821f90e1cdd05239322820ff88

Re-sync with `just sync-contract` (`uv run python scripts/sync_contract.py`).

## Cross-field rule parity

The cross-field rules in `assets/assemble.js` mirror upstream
`src/rundrafter/validate.py` (constraints documented in
`docs/spec/contracts.md`). These aren't vendored - only their upstream
revision is pinned, checked by `just check-contract` against the sibling
checkout.

rules_revision: 4482c8097c17c8821f90e1cdd05239322820ff88

After syncing assemble.js (and webform.md) to a rule change upstream, run
`uv run python scripts/sync_contract.py --update-rules-revision` (sibling
checkout required) to record the new pin.
