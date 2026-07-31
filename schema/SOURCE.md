# Contract source

Vendored from the upstream `rundrafter` repo's intake contract
(`src/rundrafter/validate/`):

- `intake-schema.json`
- `intake-example.json`

Pinned upstream revision:

revision: f0a80b68fa8ee0dde08b6a89853dec3e2bcc3a34

Re-sync with `just sync-contract` (`uv run python scripts/sync_contract.py`).

## Cross-field rule parity

The cross-field rules in `assets/assemble.js` mirror upstream
`src/rundrafter/validate/validate.py` (constraints documented in
`docs/spec/contracts.md`). These aren't vendored - only their upstream
revision is pinned, checked by `just check-contract` against the sibling
checkout.

rules_revision: f0a80b68fa8ee0dde08b6a89853dec3e2bcc3a34

After syncing assemble.js (and, if the rule text needs updating, upstream's
docs/webform-architecture.md) to a rule change upstream, run
`uv run python scripts/sync_contract.py --update-rules-revision` (sibling
checkout required) to record the new pin.
