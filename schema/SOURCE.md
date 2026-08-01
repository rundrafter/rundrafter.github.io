# Contract source

Vendored from the upstream `rundrafter` repo's intake contract
(`src/rundrafter/validate/`):

- `intake-schema.json`
- `intake-example.json`

Also generated from upstream `config/defaults.yaml` (the keys named in
`scripts/sync_contract.py`'s `CONSTRAINTS_KEYS`), under the same pin:

- `form-constraints.json`

Pinned upstream revision:

revision: a809cca40b2c3f8c494aad20d160aedc17207ce8

Re-sync with `just sync-contract` (`uv run python scripts/sync_contract.py`).

## Cross-field rule parity

The cross-field rules in `assets/assemble.js` mirror upstream
`src/rundrafter/validate/validate.py` (constraints documented in
`docs/spec/contracts.md`). These aren't vendored - only their upstream
revision is pinned, checked by `just check-contract` against the sibling
checkout.

rules_revision: a809cca40b2c3f8c494aad20d160aedc17207ce8

After syncing assemble.js (and, if the rule text needs updating, upstream's
docs/webform-architecture.md) to a rule change upstream, run
`uv run python scripts/sync_contract.py --update-rules-revision` (sibling
checkout required) to record the new pin.
